"""
Fase 2 dos pagamentos/planos: crédito na mudança de plano, um pendente por
utilizador, reserva de códigos promocionais, checkout a 0 Kz, upgrade/ sem
Gratuito para alunos, lembretes D-3/D-0 por horas, campos de renovação da
subscrição, limites efetivos e restos removidos.
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.subscriptions.models import (
    UserSubscription, SubscriptionHistory, PromotionalCode, PromoCodeUsage,
)
from apps.subscriptions.services import DURACAO_PLANO_GRATUITO, FUSO_ANGOLA
from apps.pagamentos import services
from apps.pagamentos.models import Pagamento, LembreteRenovacao
from apps.pagamentos.signals import lembrete_renovacao

from .test_mcx import (
    BasePagamentosTest, User, TEL_OK, TEL_RECUSA, TEL_EXPIRA, definir_assinatura, envelhecer,
)

DIA = 86400


def criar_promo(code='PROMO', tipo='PERCENTAGE', valor='20', **extra):
    dados = dict(
        code=code, name=code, description=f'Código {code}', discount_type=tipo,
        discount_value=Decimal(valor), max_uses=100,
        valid_from=timezone.now() - timedelta(days=1),
        valid_until=timezone.now() + timedelta(days=30),
    )
    dados.update(extra)
    return PromotionalCode.objects.create(**dados)


class BaseFase2(BasePagamentosTest):
    url_orcamento = '/api/v1/pagamentos/orcamento/'
    url_sem_pagamento = '/api/v1/pagamentos/sem-pagamento/'

    def pagar(self, plan=None, periodo='mensal', **dados):
        """Cria (telefone 1111: fica pendente) e confirma já."""
        r = self.criar(plan_id=str((plan or self.premium).id), periodo=periodo,
                       telefone=TEL_EXPIRA, **dados)
        self.assertEqual(r.status_code, 201, r.data)
        return services.confirmar_pagamento(Pagamento.objects.get(pk=r.data['id']))

    def recuar(self, dias):
        """Simula que o período pago atual começou há ``dias`` dias."""
        delta = timedelta(days=dias)
        for p in Pagamento.objects.filter(user=self.user, estado='pago'):
            Pagamento.objects.filter(pk=p.pk).update(
                periodo_inicio=p.periodo_inicio - delta, periodo_fim=p.periodo_fim - delta,
                pago_em=p.pago_em - delta, created_at=p.created_at - delta)
        sub = UserSubscription.objects.get(user=self.user)
        sub.expires_at -= delta
        sub.save()
        return sub

    def orcar(self, plan, periodo='mensal', codigo=None):
        q = {'plan': plan if isinstance(plan, str) else str(plan.id), 'periodo': periodo}
        if codigo:
            q['codigo'] = codigo
        return self.client.get(self.url_orcamento, q)


# ---------------------------------------------------------------------------
# 1. Mudança de plano: dias pagos viram crédito
# ---------------------------------------------------------------------------

class CreditoMudancaPlanoTests(BaseFase2):
    def test_orcamento_sem_plano_pago_nao_tem_credito(self):
        r = self.orcar('PREMIUM')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['operacao'], 'nova')
        self.assertEqual(r.data['credito_kz'], 0)
        self.assertEqual(r.data['final_kz'], 14950)
        self.assertTrue(r.data['requer_pagamento'])
        self.assertEqual(r.data['linhas'], [
            {'tipo': 'plano', 'descricao': 'Plano Premium - Mensal', 'valor_kz': 14950}])

    def test_upgrade_a_meio_do_periodo_desconta_os_dias_que_faltam(self):
        antigo = self.pagar()
        self.recuar(15)  # faltam 15 de 30 dias -> metade de 14 950
        r = self.orcar(self.plus)
        self.assertEqual(r.data['operacao'], 'mudanca_plano')
        self.assertEqual(r.data['credito_total_kz'], 7475)
        self.assertEqual(r.data['credito_kz'], 7475)
        self.assertEqual(r.data['credito_dias_restantes'], 15)  # 14 dias e quase 24 h = 15
        self.assertEqual(r.data['credito_plano']['tipo'], 'PREMIUM')
        self.assertEqual(r.data['final_kz'], 24950 - 7475)
        self.assertEqual(r.data['final'], r.data['final_kz'])
        self.assertEqual(r.data['dias_extra'], 0)
        self.assertEqual(r.data['linhas'][-1]['tipo'], 'credito')
        self.assertEqual(r.data['linhas'][-1]['valor_kz'], -7475)

        antes = timezone.now()
        r = self.criar(plan_id=str(self.plus.id), telefone=TEL_EXPIRA)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['total_kz'], 17475)
        self.assertEqual(r.data['credito_kz'], 7475)
        p = services.confirmar_pagamento(Pagamento.objects.get(pk=r.data['id']))

        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, self.plus)
        # O novo plano começa já: 30 dias a partir de agora (não perde nem soma os 15 dias)
        self.assertAlmostEqual((sub.expires_at - antes).total_seconds(), 30 * DIA, delta=60)
        self.assertAlmostEqual((p.periodo_inicio - antes).total_seconds(), 0, delta=60)
        hist = p.historico
        self.assertEqual(hist.event_type, 'UPGRADED')
        self.assertEqual(hist.amount_paid, Decimal('17475'))
        self.assertIn('Crédito do plano Premium: 7 475 Kz', hist.notes)
        antigo.refresh_from_db()
        self.assertIsNotNone(antigo.creditado_em)  # não volta a dar crédito

        recibo = self.client.get(reverse('pagamentos:recibo', args=[p.numero_recibo])).data
        self.assertEqual(recibo['subtotal_kz'], 24950)
        self.assertEqual(recibo['credito_kz'], 7475)
        self.assertEqual(recibo['total_kz'], 17475)
        self.assertEqual([l['total_kz'] for l in recibo['linhas']], [24950, -7475])
        self.assertIn('Crédito do plano Premium', recibo['credito_descricao'])

    def test_downgrade_com_credito_maior_que_o_preco_vira_dias_extra(self):
        self.pagar(self.plus, 'anual')  # 249 500 Kz por 365 dias
        r = self.orcar(self.premium, 'mensal')
        credito = r.data['credito_total_kz']
        self.assertAlmostEqual(credito, 249500, delta=2)
        self.assertEqual(r.data['credito_kz'], 14950)
        self.assertEqual(r.data['final_kz'], 0)
        self.assertFalse(r.data['requer_pagamento'])
        esperado = int((credito - 14950) // (Decimal(14950) / 30))
        self.assertEqual(r.data['dias_extra'], esperado)

        # Multicaixa recusa 0 Kz e indica o fluxo sem pagamento
        r = self.criar(plan_id=str(self.premium.id))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'valor_zero')

        antes = timezone.now()
        r = self.client.post(self.url_sem_pagamento, {
            'plan_id': str(self.premium.id), 'periodo': 'mensal'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['estado'], 'pago')
        self.assertEqual(r.data['total_kz'], 0)
        self.assertEqual(r.data['metodo'], 'Sem pagamento')
        self.assertEqual(r.data['dias_extra'], esperado)
        self.assertFalse(r.data['simulado'])
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, self.premium)
        self.assertAlmostEqual((sub.expires_at - antes).total_seconds(), (30 + esperado) * DIA, delta=60)
        self.assertEqual(r.data['ativacao']['plano']['expira_em'], sub.expires_at.isoformat())

        p = Pagamento.objects.get(pk=r.data['id'])
        self.assertEqual(p.historico.event_type, 'DOWNGRADED')
        self.assertEqual(p.historico.amount_paid, Decimal('0'))
        recibo = self.client.get(reverse('pagamentos:recibo', args=[p.numero_recibo])).data
        self.assertEqual(recibo['total_kz'], 0)
        self.assertEqual(recibo['linhas'][1]['total_kz'], -14950)
        self.assertIsNone(recibo['telefone_mascarado'])
        # Aparece no histórico de pagamentos
        hist = self.client.get(reverse('subscriptions:user-payment-history')).data
        self.assertIn(p.numero_recibo, [i['receipt_number'] for i in hist['payment_history']])

    def test_credito_encadeado_conta_o_valor_do_periodo(self):
        """Premium -> Plus (paga 10 000 + 14 950 de crédito) -> Premium: o crédito é ~24 950."""
        self.pagar(self.premium)
        self.pagar(self.plus)
        r = self.orcar(self.premium)
        self.assertAlmostEqual(r.data['credito_total_kz'], 24950, delta=2)
        self.assertEqual(r.data['final_kz'], 0)

    def test_plano_dado_por_administrador_nao_tem_credito(self):
        definir_assinatura(self.user, plan=self.premium, status='ACTIVE',
                           expires_at=timezone.now() + timedelta(days=20))
        r = self.orcar(self.plus)
        self.assertEqual(r.data['credito_kz'], 0)
        self.assertIsNone(r.data['credito_plano'])
        self.assertEqual(r.data['final_kz'], 24950)

    def test_mesmo_plano_e_renovacao_sem_credito(self):
        self.pagar()
        sub = self.recuar(25)
        fim = sub.expires_at
        r = self.orcar(self.premium)
        self.assertEqual(r.data['operacao'], 'renovacao')
        self.assertEqual(r.data['credito_kz'], 0)
        self.assertEqual(r.data['inicio'], fim.isoformat())
        self.pagar()
        sub.refresh_from_db()
        self.assertEqual(sub.expires_at, fim + timedelta(days=30))

    def test_renovacao_bloqueada_aparece_no_orcamento(self):
        self.pagar()
        r = self.orcar('PREMIUM')
        self.assertFalse(r.data['pode_comprar'])
        self.assertIn('Já tem o plano', r.data['motivo_bloqueio'])

    def test_codigo_com_credito(self):
        criar_promo('MENOS20')
        self.pagar()
        self.recuar(15)
        r = self.orcar(self.plus, codigo='menos20')
        # 20% sobre o preço base (4 990), depois do crédito de 7 475
        self.assertEqual(r.data['desconto_codigo_kz'], 4990)
        self.assertEqual(r.data['final_kz'], 24950 - 7475 - 4990)
        self.assertEqual([l['tipo'] for l in r.data['linhas']], ['plano', 'codigo', 'credito'])

    def test_codigo_desnecessario_quando_o_credito_cobre_tudo(self):
        promo = criar_promo('MENOS20')
        self.pagar(self.plus, 'anual')
        r = self.orcar(self.premium, codigo='MENOS20')
        self.assertEqual(r.data['desconto_codigo_kz'], 0)
        self.assertTrue(r.data['aviso_codigo'])
        r = self.client.post(self.url_sem_pagamento, {
            'plan_id': str(self.premium.id), 'periodo': 'mensal', 'codigo_promocional': 'MENOS20'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['codigo_promocional'])
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 0)

    def test_orcamento_erros(self):
        self.assertEqual(self.orcar('FREE').status_code, 400)
        self.assertEqual(self.orcar('XPTO').status_code, 404)
        r = self.orcar('PREMIUM', codigo='NAOEXISTE')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['erro_codigo']['code'], 'inexistente')
        self.assertEqual(r.data['final_kz'], 14950)
        self.client.force_authenticate(None)
        self.assertEqual(self.orcar('PREMIUM').status_code, 401)

    def test_apply_promo_code_inclui_credito(self):
        criar_promo('MENOS20')
        self.pagar()
        self.recuar(15)
        r = self.client.post(reverse('subscriptions:apply-promo-code'), {
            'promo_code': 'MENOS20', 'plan_id': str(self.plus.id), 'periodo': 'mensal'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['credito_kz'], 7475)
        self.assertEqual(int(r.data['final_price']), 24950 - 7475 - 4990)

    def test_representar_pagamento_mostra_a_ativacao_deste_pagamento(self):
        p1 = self.pagar()
        self.pagar(self.plus)
        r = self.detalhe(p1.id)
        self.assertEqual(r.data['ativacao']['plano']['tipo'], 'PREMIUM')
        self.assertEqual(r.data['ativacao']['plano']['expira_em'], p1.periodo_fim.isoformat())


# ---------------------------------------------------------------------------
# 2. Um pendente por utilizador e sem ativação dupla
# ---------------------------------------------------------------------------

class PendenteUnicoTests(BaseFase2):
    def test_constraint_um_pendente_por_utilizador(self):
        base = dict(user=self.user, periodo='mensal', valor_kz=14950, telefone=TEL_OK,
                    provedor='simulado')
        Pagamento.objects.create(plan=self.premium, **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pagamento.objects.create(plan=self.plus, **base)

    def test_novo_pedido_de_outro_plano_cancela_o_anterior_e_liberta_o_codigo(self):
        promo = criar_promo('MENOS20')
        r1 = self.criar(telefone=TEL_EXPIRA, codigo_promocional='MENOS20')
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 1)
        r2 = self.criar(telefone=TEL_EXPIRA, plan_id=str(self.plus.id), codigo_promocional='MENOS20')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(Pagamento.objects.get(pk=r1.data['id']).estado, 'cancelado')
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 1)  # a reserva passou do 1.º para o 2.º
        self.assertEqual(PromoCodeUsage.objects.filter(user=self.user).count(), 1)

    def test_pagamento_ultrapassado_e_anulado_na_confirmacao(self):
        promo = criar_promo('MENOS20')
        r = self.criar(telefone=TEL_EXPIRA, plan_id=str(self.plus.id), codigo_promocional='MENOS20')
        a = Pagamento.objects.get(pk=r.data['id'])
        # Outro pagamento do utilizador confirmado depois de A ter sido criado
        Pagamento.objects.create(
            user=self.user, plan=self.premium, periodo='mensal', valor_kz=14950,
            telefone=TEL_OK, provedor='simulado', estado='pago', pago_em=timezone.now(),
            numero_recibo='PE-R-TESTE-1')
        with self.assertRaises(services.ErroPagamento) as ctx:
            services.confirmar_pagamento(a)
        self.assertEqual(ctx.exception.codigo, 'anulado')
        a.refresh_from_db()
        self.assertEqual(a.estado, 'cancelado')
        self.assertIn('outro pagamento', a.motivo_falha)
        self.assertNotEqual(UserSubscription.objects.get(user=self.user).plan, self.plus)
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 0)
        self.assertFalse(PromoCodeUsage.objects.filter(user=self.user).exists())

    def test_polling_nao_da_500_se_a_confirmacao_falhar(self):
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        with mock.patch.object(services, 'atualizar_estado',
                               side_effect=services.ErroPagamento('x', 409, 'estado_invalido')):
            r = self.detalhe(pid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['estado'], 'pendente')

    def test_atualizar_estado_com_cancelamento_em_paralelo(self):
        pid = self.criar().data['id']
        p = envelhecer(Pagamento.objects.get(pk=pid), 10)
        Pagamento.objects.filter(pk=pid).update(estado='cancelado')  # outro pedido cancelou
        p.estado = 'pendente'  # cópia em memória desatualizada
        services.atualizar_estado(p)
        self.assertEqual(p.estado, 'cancelado')


# ---------------------------------------------------------------------------
# 3. Código promocional reservado na criação
# ---------------------------------------------------------------------------

class ReservaCodigoTests(BaseFase2):
    def setUp(self):
        super().setUp()
        self.promo = criar_promo('UNICO', max_uses=1)

    def _usos(self):
        self.promo.refresh_from_db()
        return self.promo.current_uses

    def test_reserva_conta_para_o_limite(self):
        r = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._usos(), 1)
        uso = PromoCodeUsage.objects.get(user=self.user)
        self.assertEqual(uso.estado, PromoCodeUsage.RESERVADO)
        self.client.force_authenticate(self.outro)
        r = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'codigo_promocional')

    def test_cancelar_liberta(self):
        pid = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').data['id']
        self.client.post(reverse('pagamentos:cancelar', args=[pid]))
        self.assertEqual(self._usos(), 0)
        self.assertFalse(PromoCodeUsage.objects.exists())
        self.client.force_authenticate(self.outro)
        self.assertEqual(self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').status_code, 201)

    def test_recusado_liberta(self):
        pid = self.criar(telefone=TEL_RECUSA, codigo_promocional='UNICO').data['id']
        envelhecer(Pagamento.objects.get(pk=pid), 7)
        self.assertEqual(self.detalhe(pid).data['estado'], 'recusado')
        self.assertEqual(self._usos(), 0)

    def test_expirado_liberta_mesmo_sem_ser_lido_cron(self):
        pid = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').data['id']
        envelhecer(Pagamento.objects.get(pk=pid), 400)
        call_command('enviar_lembretes_renovacao', stdout=StringIO())
        self.assertEqual(Pagamento.objects.get(pk=pid).estado, 'expirado')
        self.assertEqual(self._usos(), 0)

    def test_reserva_caducada_de_outro_aluno_e_resolvida_ao_pedir(self):
        self.client.force_authenticate(self.outro)
        pid = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').data['id']
        envelhecer(Pagamento.objects.get(pk=pid), 400)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').status_code, 201)

    def test_confirmar_torna_definitivo_mesmo_que_o_codigo_tenha_sido_desligado(self):
        pid = self.criar(telefone=TEL_EXPIRA, codigo_promocional='UNICO').data['id']
        PromotionalCode.objects.filter(pk=self.promo.pk).update(is_active=False)
        p = services.confirmar_pagamento(Pagamento.objects.get(pk=pid))
        self.assertEqual(p.estado, 'pago')
        self.assertEqual(p.desconto_kz, 2990)
        uso = PromoCodeUsage.objects.get(user=self.user)
        self.assertEqual(uso.estado, PromoCodeUsage.CONFIRMADO)
        self.assertEqual(self._usos(), 1)
        services.confirmar_pagamento(p)  # idempotente
        self.assertEqual(self._usos(), 1)


# ---------------------------------------------------------------------------
# 4. Validação dos códigos e checkout a 0 Kz
# ---------------------------------------------------------------------------

class ValidacaoCodigoTests(BaseFase2):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='admin-f2@example.com', name='Admin', password='password123', role='admin')
        self.url_admin = reverse('subscriptions:admin-promo-codes-list')

    def _criar_admin(self, **dados):
        corpo = dict(code='novo', name='Novo', description='x', discount_type='PERCENTAGE',
                     discount_value='10', max_uses=10,
                     valid_from=(timezone.now() - timedelta(days=1)).isoformat(),
                     valid_until=(timezone.now() + timedelta(days=10)).isoformat())
        corpo.update(dados)
        self.client.force_authenticate(self.admin)
        return self.client.post(self.url_admin, corpo, format='json')

    def test_valores_invalidos_recusados(self):
        for dados in [{'discount_value': '150'}, {'discount_value': '0'}, {'discount_value': '-5'},
                      {'discount_type': 'FIXED_AMOUNT', 'discount_value': '0'},
                      {'discount_type': 'FIXED_AMOUNT', 'discount_value': '-100'},
                      {'discount_type': 'FREE_TRIAL', 'discount_value': '7'},
                      {'max_uses': 0}]:
            r = self._criar_admin(**dados)
            self.assertEqual(r.status_code, 400, (dados, r.data))
        self.assertFalse(PromotionalCode.objects.exists())

    def test_valor_valido_aceite(self):
        r = self._criar_admin(discount_value='100')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['code'], 'NOVO')
        r = self._criar_admin(code='FIXO', discount_type='FIXED_AMOUNT', discount_value='5000')
        self.assertEqual(r.status_code, 201, r.data)

    def test_editar_para_valor_invalido_recusado(self):
        promo = criar_promo('EDITA')
        self.client.force_authenticate(self.admin)
        url = reverse('subscriptions:admin-promo-code-detail', args=[promo.pk])
        r = self.client.patch(url, {'discount_value': '120'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_dados_antigos_invalidos_nunca_dao_preco_negativo(self):
        criar_promo('MAU', valor='150')
        r = self.orcar('PREMIUM', codigo='MAU')
        self.assertEqual(r.data['final_kz'], 0)
        self.assertEqual(r.data['desconto_codigo_kz'], 14950)
        criar_promo('MAUFIXO', tipo='FIXED_AMOUNT', valor='-500')
        r = self.orcar('PREMIUM', codigo='MAUFIXO')
        self.assertEqual(r.data['final_kz'], 14950)
        criar_promo('TRIAL', tipo='FREE_TRIAL', valor='7')
        r = self.orcar('PREMIUM', codigo='TRIAL')
        self.assertEqual(r.data['erro_codigo']['code'], 'tipo_nao_suportado')

    def test_codigo_100_por_cento_ativa_sem_multicaixa(self):
        promo = criar_promo('GRATIS', valor='100')
        r = self.criar(codigo_promocional='GRATIS')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'valor_zero')
        self.assertFalse(Pagamento.objects.exists())

        r = self.client.post(self.url_sem_pagamento, {
            'plan_id': 'PREMIUM', 'periodo': 'anual', 'codigo_promocional': 'gratis'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['total_kz'], 0)
        self.assertEqual(r.data['desconto_kz'], 149500)
        self.assertRegex(r.data['numero_recibo'], r'^PE-R-\d{4}-\d{6}$')
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, self.premium)
        self.assertEqual(PromoCodeUsage.objects.get(user=self.user).estado, PromoCodeUsage.CONFIRMADO)
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 1)

    def test_sem_pagamento_recusa_quando_ha_valor(self):
        r = self.client.post(self.url_sem_pagamento, {
            'plan_id': str(self.premium.id), 'periodo': 'mensal'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'pagamento_necessario')
        self.assertFalse(Pagamento.objects.exists())

    def test_sem_pagamento_cancela_pendente_mcx(self):
        criar_promo('GRATIS', valor='100')
        pid = self.criar(telefone=TEL_EXPIRA).data['id']
        r = self.client.post(self.url_sem_pagamento, {
            'plan_id': 'PREMIUM', 'periodo': 'mensal', 'codigo_promocional': 'GRATIS'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Pagamento.objects.get(pk=pid).estado, 'cancelado')


# ---------------------------------------------------------------------------
# 5. upgrade/ e plano Gratuito
# ---------------------------------------------------------------------------

class GratuitoTests(BaseFase2):
    def test_aluno_nao_escolhe_o_gratuito(self):
        self.pagar()
        r = self.client.post(reverse('subscriptions:upgrade-subscription'), {
            'plan_id': str(self.free.id), 'billing_cycle': 'MONTHLY'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'FREE_NOT_ALLOWED')
        self.assertEqual(UserSubscription.objects.get(user=self.user).plan, self.premium)

    def test_aluno_com_preco_zero_nao_ativa_por_upgrade(self):
        criar_promo('GRATIS', valor='100')
        r = self.client.post(reverse('subscriptions:upgrade-subscription'), {
            'plan_id': str(self.premium.id), 'billing_cycle': 'MONTHLY', 'promo_code': 'GRATIS'},
            format='json')
        self.assertEqual(r.status_code, 402)
        self.assertNotEqual(UserSubscription.objects.get(user=self.user).plan, self.premium)

    def test_admin_muda_para_gratuito_sem_historico_pago(self):
        admin = User.objects.create_user(email='adm2@example.com', name='A', password='password123',
                                         role='admin')
        definir_assinatura(admin, plan=self.premium, status='ACTIVE', current_hearts=999,
                           expires_at=timezone.now() + timedelta(days=10))
        self.client.force_authenticate(admin)
        r = self.client.post(reverse('subscriptions:upgrade-subscription'), {
            'plan_id': str(self.free.id), 'billing_cycle': 'MONTHLY'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        sub = UserSubscription.objects.get(user=admin)
        self.assertEqual(sub.plan, self.free)
        self.assertGreater(sub.expires_at, timezone.now() + timedelta(days=365 * 9))
        self.assertEqual(sub.current_hearts, 5)
        self.assertFalse(SubscriptionHistory.objects.filter(
            subscription=sub, amount_paid__isnull=False).exists())

    def test_registo_cria_gratuito_sem_fim(self):
        novo = User.objects.create_user(email='novo-f2@example.com', name='N', password='password123')
        sub = UserSubscription.objects.get(user=novo)
        self.assertEqual(sub.plan, self.free)
        self.assertAlmostEqual((sub.expires_at - timezone.now()).total_seconds(),
                               DURACAO_PLANO_GRATUITO.total_seconds(), delta=120)
        self.assertEqual(sub.current_hearts, self.free.hearts_limit)


# ---------------------------------------------------------------------------
# 6. Lembretes D-3 (<= 72 h) e D-0 (<= 24 h), antes de expirar
# ---------------------------------------------------------------------------

class LembretesHorasTests(BaseFase2):
    def setUp(self):
        super().setUp()
        self.recebidos = []
        self.handler = lambda sender, subscription, tipo, **kw: self.recebidos.append(tipo)
        lembrete_renovacao.connect(self.handler)

    def tearDown(self):
        lembrete_renovacao.disconnect(self.handler)
        super().tearDown()

    def _sub(self, horas):
        return definir_assinatura(self.user, plan=self.premium, status='ACTIVE',
                                  expires_at=timezone.now() + timedelta(hours=horas))

    def _comando(self):
        call_command('enviar_lembretes_renovacao', stdout=StringIO())

    def test_d0_no_dia_anterior_do_calendario(self):
        # Termina amanhã às 08:00 de Luanda e o cron corre hoje às 10:00: faltam 22 h -> D0
        agora = timezone.localtime(timezone.now(), FUSO_ANGOLA).replace(
            hour=10, minute=0, second=0, microsecond=0)
        sub = self._sub(0)
        sub.expires_at = agora + timedelta(hours=22)
        sub.save()
        from apps.pagamentos.renovacao import enviar_lembretes
        enviar_lembretes(agora=agora)
        self.assertEqual(self.recebidos, ['D0'])

    def test_comando_de_hora_a_hora_idempotente(self):
        self._sub(20)
        for _ in range(3):
            self._comando()
        self.assertEqual(self.recebidos, ['D0'])  # D3 saltado: já faltava menos de 24 h
        self.assertEqual(LembreteRenovacao.objects.count(), 1)

    def test_d3_e_depois_d0(self):
        sub = self._sub(70)
        self._comando()
        self.assertEqual(self.recebidos, ['D3'])
        sub.expires_at = timezone.now() + timedelta(hours=23)
        sub.save()
        LembreteRenovacao.objects.filter(subscription=sub).update(fim_periodo=sub.expires_at)
        self._comando()
        self._comando()
        self.assertEqual(self.recebidos, ['D3', 'D0'])

    def test_lembrete_sai_antes_de_expirar_na_mesma_execucao(self):
        self._sub(0.5)
        self._comando()
        self.assertEqual(self.recebidos, ['D0'])
        self.assertEqual(UserSubscription.objects.get(user=self.user).plan, self.premium)

    def test_aviso_d0_diz_hoje_ou_amanha(self):
        from apps.users.models import Notification
        self._sub(1)
        self._comando()
        aviso = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertIsNotNone(aviso)
        self.assertRegex(aviso.title, r'termina (hoje|amanhã)$')


# ---------------------------------------------------------------------------
# 7. Campos de renovação na subscrição
# ---------------------------------------------------------------------------

class CamposSubscricaoTests(BaseFase2):
    def _minha(self):
        r = self.client.get(reverse('subscriptions:user-subscription'))
        self.assertEqual(r.status_code, 200)
        return r.data

    def test_gratuito(self):
        d = self._minha()
        self.assertIsNone(d['termina_em'])
        self.assertFalse(d['termina_hoje'])
        self.assertFalse(d['pode_renovar'])
        self.assertIsNone(d['renovavel_a_partir_de'])
        self.assertIsNone(d['periodo'])
        self.assertIsNone(d['valor_periodo_kz'])
        self.assertNotIn('stripe_subscription_id', d)

    def test_anual(self):
        self.pagar(self.premium, 'anual')
        sub = UserSubscription.objects.get(user=self.user)
        d = self._minha()
        self.assertEqual(d['termina_em'], sub.expires_at.isoformat())
        self.assertEqual(d['periodo'], 'anual')
        self.assertEqual(d['valor_periodo_kz'], 149500)
        self.assertFalse(d['pode_renovar'])
        self.assertEqual(d['renovavel_a_partir_de'], (sub.expires_at - timedelta(days=7)).isoformat())
        self.assertFalse(d['termina_hoje'])

    def test_termina_hoje_e_pode_renovar(self):
        self.pagar()
        agora_luanda = timezone.localtime(timezone.now(), FUSO_ANGOLA)
        fim = agora_luanda.replace(hour=23, minute=59, second=0, microsecond=0)
        if fim <= agora_luanda:
            fim = agora_luanda + timedelta(seconds=30)
        UserSubscription.objects.filter(user=self.user).update(expires_at=fim)
        d = self._minha()
        self.assertTrue(d['termina_hoje'])
        self.assertTrue(d['pode_renovar'])
        self.assertEqual(d['days_until_expiry'], 0)
        self.assertEqual(d['periodo'], 'mensal')
        self.assertEqual(d['valor_periodo_kz'], 14950)
        # Regra igual à do servidor: o pagamento de renovação é aceite
        self.assertEqual(self.criar(telefone=TEL_EXPIRA).status_code, 201)

    def test_plano_de_administrador_usa_o_historico(self):
        admin = User.objects.create_user(email='adm3@example.com', name='A', password='password123',
                                         role='admin')
        self.client.force_authenticate(admin)
        self.client.post(reverse('subscriptions:upgrade-subscription'), {
            'plan_id': str(self.plus.id), 'billing_cycle': 'YEARLY'}, format='json')
        d = self._minha()
        self.assertEqual(d['periodo'], 'anual')
        self.assertEqual(d['valor_periodo_kz'], 249500)


# ---------------------------------------------------------------------------
# 8. Limites efetivos, textos e restos removidos
# ---------------------------------------------------------------------------

class LimitesERestosTests(BaseFase2):
    def test_limites_premium(self):
        self.premium.daily_speaking_minutes = 10
        self.premium.daily_listening_minutes = None
        self.premium.daily_lessons_limit = None
        self.premium.hearts_limit = 0
        self.premium.save()
        self.pagar()
        d = self.client.get(reverse('subscriptions:subscription_limits_status')).data
        self.assertEqual(d['speaking']['limit'], 10)
        self.assertFalse(d['speaking']['unlimited'])
        self.assertIsNone(d['listening']['limit'])
        self.assertTrue(d['listening']['unlimited'])
        self.assertTrue(d['lessons']['unlimited'])
        self.assertTrue(d['hearts']['unlimited'])
        self.assertEqual(d['plan']['type'], 'PREMIUM')

    def test_limite_zero_e_bloqueado(self):
        self.free.daily_listening_minutes = 0
        self.free.daily_lessons_limit = 3
        self.free.save()
        d = self.client.get(reverse('subscriptions:subscription_limits_status')).data
        self.assertEqual(d['listening']['limit'], 0)
        self.assertFalse(d['listening']['unlimited'])
        self.assertTrue(d['listening']['blocked'])
        self.assertFalse(d['listening']['can_use'])
        self.assertEqual(d['lessons']['limit'], 3)

    def test_limite_conversa_no_periodo_de_teste(self):
        self.free.trial_days = 7
        self.free.trial_speaking_minutes = 15
        self.free.daily_speaking_minutes = 0
        self.free.save()
        d = self.client.get(reverse('subscriptions:subscription_limits_status')).data
        self.assertEqual(d['speaking']['limit'], 15)  # efetivo (teste), não o do plano
        self.assertTrue(d['plan']['is_trial'])

    def test_endpoints_removidos(self):
        self.assertEqual(self.client.get('/api/v1/users/transactions/').status_code, 404)
        self.assertEqual(self.client.post('/api/v1/subscriptions/cancel/').status_code, 404)

    def test_vantagens_em_pt_pt_e_verdadeiras(self):
        self.premium.daily_lessons_limit = None
        self.premium.daily_speaking_minutes = 10
        self.premium.hearts_limit = 0
        self.premium.save()
        planos = self.client.get(reverse('subscriptions:public-plans-list')).data
        planos = planos['results'] if isinstance(planos, dict) else planos
        premium = next(p for p in planos if p['plan_type'] == 'PREMIUM')
        self.assertIn('Lições ilimitadas', premium['features'])
        self.assertIn('10 minutos de conversa com o tutor por dia', premium['features'])
        self.assertIn('Vidas ilimitadas', premium['features'])
        self.assertFalse(any('ILIMITADO' in f or 'Speaking' in f for f in premium['features']))
