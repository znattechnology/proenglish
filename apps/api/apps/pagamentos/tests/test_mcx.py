"""
Testes da app pagamentos (Multicaixa Express simulado, AOA).
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.subscriptions.models import (
    SubscriptionPlan, UserSubscription, SubscriptionHistory,
    PromotionalCode, PromoCodeUsage,
)
from apps.courses.models import Course, UserCourseProgress

from apps.pagamentos import services
from apps.pagamentos.models import Pagamento, LembreteRenovacao
from apps.pagamentos.renovacao import enviar_lembretes, expirar_subscricoes
from apps.pagamentos.signals import pagamento_confirmado, lembrete_renovacao
from apps.pagamentos.telefone import normalizar_telefone, mascarar_telefone, TelefoneInvalido

User = get_user_model()

TEL_OK = '923456789'
TEL_RECUSA = '923450000'
TEL_EXPIRA = '923451111'


def criar_planos():
    free, _ = SubscriptionPlan.objects.update_or_create(
        plan_type='FREE',
        defaults={'name': 'Gratuito', 'description': 'Grátis',
                  'monthly_price': Decimal('0.00'), 'yearly_price': Decimal('0.00'),
                  'hearts_limit': 5, 'is_active': True},
    )
    premium, _ = SubscriptionPlan.objects.update_or_create(
        plan_type='PREMIUM',
        defaults={'name': 'Premium', 'description': 'Premium',
                  'monthly_price': Decimal('14950.00'), 'yearly_price': Decimal('149500.00'),
                  'is_active': True},
    )
    plus, _ = SubscriptionPlan.objects.update_or_create(
        plan_type='PREMIUM_PLUS',
        defaults={'name': 'Premium Plus', 'description': 'Premium Plus',
                  'monthly_price': Decimal('24950.00'), 'yearly_price': Decimal('249500.00'),
                  'is_active': True},
    )
    return free, premium, plus


def definir_assinatura(user, **campos):
    """A criação de utilizador já cria uma UserSubscription (sinal); atualiza-a."""
    sub, _ = UserSubscription.objects.update_or_create(user=user, defaults=campos)
    return sub


def envelhecer(pagamento, segundos):
    """Simula a passagem do tempo desde a criação do pagamento."""
    Pagamento.objects.filter(pk=pagamento.pk).update(
        created_at=pagamento.created_at - timedelta(seconds=segundos),
        expira_em=pagamento.expira_em - timedelta(seconds=segundos),
    )
    pagamento.refresh_from_db()
    return pagamento


class TelefoneTests(TestCase):
    def test_numeros_validos(self):
        for entrada in ['923456789', '923 456 789', '+244923456789', '244923456789',
                        '+244 923 456 789', ' 244 9234 56789 ']:
            self.assertEqual(normalizar_telefone(entrada), '923456789', entrada)

    def test_numeros_invalidos(self):
        for entrada in ['823456789', '92345678', '9234567890', '+351923456789',
                        '+923456789', '923-456-789', '(244)923456789', 'abc', '', None,
                        '00244923456789']:
            with self.assertRaises(TelefoneInvalido, msg=repr(entrada)):
                normalizar_telefone(entrada)

    def test_mascara(self):
        self.assertEqual(mascarar_telefone('923456123'), '9•• ••• 123')


@override_settings(PAGAMENTOS_SIMULADOS=True, PAGAMENTOS_PROVEDOR='simulado',
                   PAGAMENTOS_LIMITE_CRIACAO='1000/min')
class BasePagamentosTest(APITestCase):
    def setUp(self):
        self.free, self.premium, self.plus = criar_planos()
        self.user = User.objects.create_user(
            email='aluno@example.com', name='Aluno Teste', password='password123')
        self.outro = User.objects.create_user(
            email='outro@example.com', name='Outro', password='password123')
        self.teacher = User.objects.create_user(
            email='prof@example.com', name='Prof', password='password123', role='teacher')
        self.course = Course.objects.create(
            teacher=self.teacher, title='Inglês para Negócios', status='Published')
        self.client.force_authenticate(self.user)
        self.url_criar = reverse('pagamentos:multicaixa-criar')

    def criar(self, **dados):
        corpo = {'tipo': 'subscricao', 'plan_id': str(self.premium.id),
                 'periodo': 'mensal', 'telefone': TEL_OK}
        corpo.update(dados)
        corpo = {k: v for k, v in corpo.items() if v is not None}
        return self.client.post(self.url_criar, corpo, format='json')

    def detalhe(self, pid):
        return self.client.get(reverse('pagamentos:detalhe', args=[pid]))


class CriacaoTests(BasePagamentosTest):
    def test_cria_pagamento_pendente(self):
        r = self.criar(telefone='+244 923 456 789')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['estado'], 'pendente')
        self.assertEqual(r.data['valor_kz'], 14950)
        self.assertEqual(r.data['desconto_kz'], 0)
        self.assertEqual(r.data['total_kz'], 14950)
        self.assertEqual(r.data['telefone_mascarado'], '9•• ••• 789')
        self.assertTrue(r.data['simulado'])
        p = Pagamento.objects.get(pk=r.data['id'])
        self.assertEqual(p.telefone, '923456789')
        self.assertAlmostEqual((p.expira_em - p.created_at).total_seconds(), 300, delta=2)

    def test_preco_anual(self):
        r = self.criar(plan_id=str(self.plus.id), periodo='anual')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['total_kz'], 249500)

    def test_telefone_invalido(self):
        r = self.criar(telefone='823456789')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Número de telemóvel inválido', r.data['error'])

    def test_plano_gratuito_nao_pode_ser_comprado(self):
        r = self.criar(plan_id=str(self.free.id))
        self.assertEqual(r.status_code, 400)
        self.assertIn('gratuito', r.data['error'])

    def test_periodo_obrigatorio(self):
        r = self.criar(periodo=None)
        self.assertEqual(r.status_code, 400)

    def test_ja_tem_o_plano(self):
        definir_assinatura(
            self.user, plan=self.premium, status='ACTIVE',
            expires_at=timezone.now() + timedelta(days=20))
        r = self.criar()
        self.assertEqual(r.status_code, 400)
        self.assertIn('Já tem o plano', r.data['error'])

    def test_promo_percentual(self):
        PromotionalCode.objects.create(
            code='BEMVINDO', name='Bem-vindo', description='20% no primeiro pagamento',
            discount_type='PERCENTAGE', discount_value=Decimal('20'), max_uses=100,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30), first_time_users_only=True)
        r = self.criar(codigo_promocional='bemvindo')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['desconto_kz'], 2990)
        self.assertEqual(r.data['total_kz'], 11960)
        self.assertEqual(r.data['codigo_promocional'], 'BEMVINDO')

    def test_previsualizacao_promo_igual_ao_cobrado(self):
        PromotionalCode.objects.create(
            code='BEMVINDO', name='Bem-vindo', description='20% no primeiro pagamento',
            discount_type='PERCENTAGE', discount_value=Decimal('20'), max_uses=100,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30), first_time_users_only=True)
        url = reverse('subscriptions:apply-promo-code')
        for periodo in ('mensal', 'anual'):
            r = self.client.post(url, {'promo_code': 'bemvindo', 'plan_id': str(self.premium.id),
                                       'periodo': periodo}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
            cobrado = self.criar(codigo_promocional='BEMVINDO', periodo=periodo)
            self.assertEqual(cobrado.status_code, 201, cobrado.data)
            self.assertEqual(int(r.data['final_price']), cobrado.data['total_kz'])
            self.client.post(reverse('pagamentos:cancelar', args=[cobrado.data['id']]))
        # Código inexistente: mesma mensagem que no pagamento.
        r = self.client.post(url, {'promo_code': 'NAOEXISTE', 'plan_id': str(self.premium.id)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error'], 'Código promocional inválido.')

    def test_promo_inexistente(self):
        r = self.criar(codigo_promocional='NAOEXISTE')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'codigo_promocional')

    def test_promo_so_primeira_compra(self):
        PromotionalCode.objects.create(
            code='BEMVINDO', name='Bem-vindo', description='x',
            discount_type='PERCENTAGE', discount_value=Decimal('20'), max_uses=100,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30), first_time_users_only=True)
        sub = definir_assinatura(
            self.user, plan=self.free, expires_at=timezone.now() + timedelta(days=100))
        SubscriptionHistory.objects.create(subscription=sub, event_type='UPGRADED',
                                           amount_paid=Decimal('14950'))
        r = self.criar(codigo_promocional='BEMVINDO')
        self.assertEqual(r.status_code, 400)
        self.assertIn('primeiro pagamento', r.data['error'])

    def test_cursos_nao_se_compram_a_parte(self):
        # O acesso aos cursos vem do plano: não há pagamentos de cursos.
        r = self.criar(tipo='curso', plan_id=None, periodo=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn('incluídos nos planos', r.data['error'])
        self.assertFalse(Pagamento.objects.exists())

    def test_um_pendente_por_item(self):
        r1 = self.criar(telefone=TEL_EXPIRA)
        r2 = self.criar(telefone=TEL_EXPIRA, periodo='anual')
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(Pagamento.objects.get(pk=r1.data['id']).estado, 'cancelado')
        self.assertEqual(Pagamento.objects.get(pk=r2.data['id']).estado, 'pendente')
        # Um único pendente por utilizador: outro plano também substitui o anterior
        r3 = self.criar(telefone=TEL_EXPIRA, plan_id=str(self.plus.id))
        self.assertEqual(r3.status_code, 201)
        self.assertEqual(Pagamento.objects.get(pk=r2.data['id']).estado, 'cancelado')
        self.assertEqual(Pagamento.objects.filter(user=self.user, estado='pendente').count(), 1)

    def test_pendente_anterior_ja_pago_nao_e_cancelado(self):
        r1 = self.criar()
        envelhecer(Pagamento.objects.get(pk=r1.data['id']), 10)
        r2 = self.criar()
        # O anterior foi resolvido como pago -> já tem o plano
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(Pagamento.objects.get(pk=r1.data['id']).estado, 'pago')

    @override_settings(PAGAMENTOS_SIMULADOS=False)
    def test_simulador_indisponivel_sem_flag(self):
        r = self.criar()
        self.assertEqual(r.status_code, 503)


class SimuladorTests(BasePagamentosTest):
    def test_numero_normal_paga_apos_6s(self):
        pid = self.criar().data['id']
        self.assertEqual(self.detalhe(pid).data['estado'], 'pendente')
        envelhecer(Pagamento.objects.get(pk=pid), 7)
        r = self.detalhe(pid)
        self.assertEqual(r.data['estado'], 'pago')
        self.assertRegex(r.data['numero_recibo'], r'^PE-R-\d{4}-\d{6}$')
        self.assertEqual(r.data['ativacao']['plano']['tipo'], 'PREMIUM')

    def test_numero_0000_recusa(self):
        pid = self.criar(telefone=TEL_RECUSA).data['id']
        envelhecer(Pagamento.objects.get(pk=pid), 7)
        r = self.detalhe(pid)
        self.assertEqual(r.data['estado'], 'recusado')
        self.assertEqual(r.data['motivo_falha'], 'Pagamento recusado no telemóvel.')
        self.assertIsNone(r.data['numero_recibo'])
        self.assertFalse(UserSubscription.objects.filter(user=self.user, plan=self.premium).exists())

    def test_numero_1111_fica_pendente_e_expira(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        envelhecer(Pagamento.objects.get(pk=pid), 60)
        self.assertEqual(self.detalhe(pid).data['estado'], 'pendente')
        envelhecer(Pagamento.objects.get(pk=pid), 300)
        r = self.detalhe(pid)
        self.assertEqual(r.data['estado'], 'expirado')
        self.assertTrue(r.data['motivo_falha'])

    def test_simular_aprovar_recusar_expirar(self):
        url = lambda pid: reverse('pagamentos:simular', args=[pid])
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        r = self.client.post(url(pid), {'resultado': 'aprovar'}, format='json')
        self.assertEqual(r.data['estado'], 'pago')
        # já não está pendente
        r = self.client.post(url(pid), {'resultado': 'recusar'}, format='json')
        self.assertEqual(r.status_code, 409)

        pid = self.criar(plan_id=str(self.plus.id), telefone=TEL_EXPIRA).data['id']
        r = self.client.post(url(pid), {'resultado': 'recusar'}, format='json')
        self.assertEqual(r.data['estado'], 'recusado')

        pid = self.criar(plan_id=str(self.plus.id), telefone=TEL_EXPIRA).data['id']
        r = self.client.post(url(pid), {'resultado': 'expirar'}, format='json')
        self.assertEqual(r.data['estado'], 'expirado')

        r = self.client.post(url(pid), {'resultado': 'outra'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_simular_escondido_sem_flag(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        with override_settings(PAGAMENTOS_SIMULADOS=False):
            r = self.client.post(reverse('pagamentos:simular', args=[pid]),
                                 {'resultado': 'aprovar'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Pagamento.objects.get(pk=pid).estado, 'pendente')


class ConfirmacaoTests(BasePagamentosTest):
    def _pagar(self, **dados):
        dados.setdefault('telefone', TEL_EXPIRA)
        pid = self.criar(**dados).data['id']
        p = Pagamento.objects.get(pk=pid)
        return services.confirmar_pagamento(p)

    def test_subscricao_mensal(self):
        antes = timezone.now()
        p = self._pagar()
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, self.premium)
        self.assertEqual(sub.status, 'ACTIVE')
        self.assertAlmostEqual((sub.expires_at - antes).total_seconds(), 30 * 86400, delta=60)
        hist = SubscriptionHistory.objects.get(subscription=sub, amount_paid__isnull=False)
        self.assertEqual(hist.amount_paid, Decimal('14950'))
        self.assertEqual(p.historico_id, hist.id)
        self.assertEqual(p.periodo_fim, sub.expires_at)

    def test_subscricao_anual(self):
        antes = timezone.now()
        self._pagar(plan_id=str(self.plus.id), periodo='anual')
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, self.plus)
        self.assertAlmostEqual((sub.expires_at - antes).total_seconds(), 365 * 86400, delta=60)

    def test_confirmacao_idempotente_e_sinal(self):
        recebidos = []
        handler = lambda sender, pagamento, **kw: recebidos.append(pagamento.id)
        pagamento_confirmado.connect(handler)
        try:
            with self.captureOnCommitCallbacks(execute=True):
                p = self._pagar()
            with self.captureOnCommitCallbacks(execute=True):
                services.confirmar_pagamento(p)
                services.confirmar_pagamento(p)
        finally:
            pagamento_confirmado.disconnect(handler)
        self.assertEqual(recebidos, [p.id])
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(SubscriptionHistory.objects.filter(
            subscription=sub, amount_paid__isnull=False).count(), 1)
        exp = sub.expires_at
        services.confirmar_pagamento(p)
        sub.refresh_from_db()
        self.assertEqual(sub.expires_at, exp)

    def test_nao_confirma_cancelado(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        self.client.post(reverse('pagamentos:cancelar', args=[pid]))
        with self.assertRaises(services.ErroPagamento):
            services.confirmar_pagamento(Pagamento.objects.get(pk=pid))

    def test_promo_registada_no_pagamento(self):
        promo = PromotionalCode.objects.create(
            code='BEMVINDO', name='x', description='x', discount_type='PERCENTAGE',
            discount_value=Decimal('20'), max_uses=100, first_time_users_only=True,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30))
        p = self._pagar(codigo_promocional='BEMVINDO')
        services.confirmar_pagamento(p)
        self.assertEqual(PromoCodeUsage.objects.filter(user=self.user, promo_code=promo).count(), 1)
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 1)
        hist = SubscriptionHistory.objects.get(subscription__user=self.user, amount_paid__isnull=False)
        self.assertEqual(hist.amount_paid, Decimal('11960'))

    def test_numeracao_de_recibos(self):
        p1 = self._pagar()
        p2 = self._pagar(plan_id=str(self.plus.id))
        ano = timezone.localtime(p1.pago_em, services.FUSO_ANGOLA).year
        n1 = int(p1.numero_recibo.rsplit('-', 1)[1])
        self.assertTrue(p1.numero_recibo.startswith(f'PE-R-{ano}-'))
        self.assertEqual(p2.numero_recibo, f'PE-R-{ano}-{n1 + 1:06d}')

    def test_payment_history_inclui_mcx(self):
        p1 = self._pagar()
        p2 = self._pagar(plan_id=str(self.plus.id))
        r = self.client.get(reverse('subscriptions:user-payment-history'))
        self.assertEqual(r.status_code, 200)
        itens = {i.get('receipt_number'): i for i in r.data['payment_history']}
        sub_item = itens[p1.numero_recibo]
        self.assertEqual(sub_item['method'], 'Multicaixa Express')
        self.assertEqual(sub_item['phone_masked'], '9•• ••• 111')
        self.assertEqual(sub_item['amount_kz'], 14950)
        self.assertEqual(sub_item['status'], 'pago')
        self.assertIn('Premium', sub_item['description'])
        plus_item = itens[p2.numero_recibo]
        # Mudança de plano: os dias do Premium (quase 30) viram crédito
        self.assertEqual(plus_item['credit_kz'], 14950)
        self.assertEqual(plus_item['amount_kz'], 24950 - 14950)
        self.assertIn('Premium Plus', plus_item['description'])
        self.assertEqual(len(r.data['payment_history']), 2)
        self.assertEqual(r.data['summary']['total_amount_paid'], 14950 + 10000)
        self.assertEqual(r.data['summary']['total_payments'], 2)

    def test_recibo(self):
        p = self._pagar()
        r = self.client.get(reverse('pagamentos:recibo', args=[p.numero_recibo]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cliente'], {'nome': 'Aluno Teste', 'email': 'aluno@example.com'})
        self.assertEqual(r.data['quantidade'], 1)
        self.assertEqual(r.data['total_kz'], 14950)
        self.assertEqual(r.data['metodo'], 'Multicaixa Express')
        self.assertEqual(r.data['periodo'], 'mensal')
        self.assertIsNotNone(r.data['validade']['fim'])

    def test_upgrade_com_pagamento_pago(self):
        p = self._pagar()
        url = reverse('subscriptions:upgrade-subscription')
        r = self.client.post(url, {'plan_id': str(self.premium.id), 'billing_cycle': 'MONTHLY',
                                   'pagamento_id': str(p.id)}, format='json')
        self.assertEqual(r.status_code, 200)
        # Não reativa: só um registo de histórico pago
        self.assertEqual(SubscriptionHistory.objects.filter(
            subscription__user=self.user, amount_paid__isnull=False).count(), 1)
        r = self.client.post(url, {'plan_id': str(self.plus.id), 'billing_cycle': 'MONTHLY',
                                   'pagamento_id': str(p.id)}, format='json')
        self.assertEqual(r.status_code, 400)


class AcessoECancelamentoTests(BasePagamentosTest):
    def test_so_o_dono_ve_e_atua(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        services.confirmar_pagamento(Pagamento.objects.get(pk=pid))
        numero = Pagamento.objects.get(pk=pid).numero_recibo
        self.client.force_authenticate(self.outro)
        self.assertEqual(self.detalhe(pid).status_code, 404)
        self.assertEqual(self.client.post(reverse('pagamentos:cancelar', args=[pid])).status_code, 404)
        self.assertEqual(self.client.post(reverse('pagamentos:simular', args=[pid]),
                                          {'resultado': 'aprovar'}, format='json').status_code, 404)
        self.assertEqual(self.client.get(reverse('pagamentos:recibo', args=[numero])).status_code, 404)

    def test_nao_autenticado(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.criar().status_code, 401)

    def test_cancelar(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        r = self.client.post(reverse('pagamentos:cancelar', args=[pid]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['estado'], 'cancelado')
        r = self.client.post(reverse('pagamentos:cancelar', args=[pid]))
        self.assertEqual(r.status_code, 409)


# ---------------------------------------------------------------------------
# Renovação: lembretes, extensão e expiração
# ---------------------------------------------------------------------------

class RenovacaoTests(BasePagamentosTest):
    def _sub(self, dias, plan=None, **extra):
        return definir_assinatura(
            self.user, plan=plan or self.premium, status='ACTIVE',
            expires_at=timezone.now() + timedelta(days=dias), **extra)

    def _correr(self, agora):
        recebidos = []
        handler = lambda sender, subscription, tipo, **kw: recebidos.append(tipo)
        lembrete_renovacao.connect(handler)
        try:
            enviar_lembretes(agora=agora)
        finally:
            lembrete_renovacao.disconnect(handler)
        return recebidos

    def test_lembretes_d3_e_d0_uma_vez_cada(self):
        # 10h em Luanda para não depender da hora a que o teste corre
        agora = timezone.localtime(timezone.now(), services.FUSO_ANGOLA).replace(
            hour=10, minute=0, second=0, microsecond=0)
        sub = self._sub(0)
        sub.expires_at = agora + timedelta(days=3, hours=1)
        sub.save()
        self.assertEqual(self._correr(agora), [])  # faltam 73 h
        self.assertEqual(self._correr(agora + timedelta(hours=2)), ['D3'])  # faltam 71 h
        self.assertEqual(self._correr(agora + timedelta(hours=3)), [])  # repetido
        self.assertEqual(self._correr(agora + timedelta(days=1)), [])  # D-2: D3 já enviado
        self.assertEqual(self._correr(agora + timedelta(days=2, hours=1)), ['D0'])  # faltam 24 h
        self.assertEqual(self._correr(agora + timedelta(days=3)), [])
        self.assertEqual(LembreteRenovacao.objects.filter(subscription=sub).count(), 2)

    def test_sem_lembrete_fora_da_janela_ou_plano_gratuito(self):
        self._sub(10)
        self.assertEqual(self._correr(timezone.now()), [])

    def test_lembretes_desligados(self):
        self._sub(3, lembretes_renovacao=False)
        self.assertEqual(self._correr(timezone.now()), [])

    def test_patch_lembretes(self):
        self._sub(20)
        url = reverse('subscriptions:renewal-reminders')
        r = self.client.patch(url, {'lembretes_renovacao': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['lembretes_renovacao'])
        self.assertFalse(UserSubscription.objects.get(user=self.user).lembretes_renovacao)
        r = self.client.get(reverse('subscriptions:user-subscription'))
        self.assertFalse(r.data['lembretes_renovacao'])
        r = self.client.patch(url, {'lembretes_renovacao': 'talvez'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_renovacao_estende_a_partir_do_fim_atual(self):
        sub = self._sub(5)
        fim = sub.expires_at
        r = self.criar(telefone=TEL_EXPIRA)
        self.assertEqual(r.status_code, 201, r.data)
        services.confirmar_pagamento(Pagamento.objects.get(pk=r.data['id']))
        sub.refresh_from_db()
        self.assertEqual(sub.expires_at, fim + timedelta(days=30))
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=sub, event_type='RENEWED').exists())

    def test_renovacao_bloqueada_fora_da_janela(self):
        self._sub(8)
        r = self.criar(telefone=TEL_EXPIRA)
        self.assertEqual(r.status_code, 400)

    def test_expiracao_volta_ao_gratuito(self):
        sub = self._sub(-1, current_hearts=50)
        UserCourseProgress.objects.create(user=self.user, course=self.course,
                                          enrollmentDate=timezone.now(), overallProgress=40.0)
        self.assertEqual(expirar_subscricoes(), 1)
        sub.refresh_from_db()
        self.assertEqual(sub.plan, self.free)
        self.assertEqual(sub.status, 'ACTIVE')
        self.assertGreater(sub.expires_at, timezone.now() + timedelta(days=365))
        self.assertEqual(sub.current_hearts, 5)
        self.assertEqual(UserCourseProgress.objects.get(user=self.user).overallProgress, 40.0)
        self.assertTrue(SubscriptionHistory.objects.filter(
            subscription=sub, event_type='EXPIRED', new_plan=self.free).exists())
        self.assertEqual(expirar_subscricoes(), 0)  # idempotente

    def test_comando_diario(self):
        self._sub(-1)
        out = StringIO()
        call_command('enviar_lembretes_renovacao', stdout=out)
        self.assertIn('1 subscrição(ões) voltaram ao Gratuito', out.getvalue())
        self.assertEqual(UserSubscription.objects.get(user=self.user).plan, self.free)
