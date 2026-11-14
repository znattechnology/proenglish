"""
Regras dos códigos promocionais no checkout (planos, período, duração nas renovações,
1.ª compra, limite de utilizações, validade, rascunho/desligado) e o teste grátis dos planos
pagos (quem pode, início, fim -> Gratuito, conversão sem perder dias, avisos).
"""

from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from io import StringIO

from apps.pagamentos import services
from apps.pagamentos.models import LembreteRenovacao, Pagamento
from apps.pagamentos.renovacao import enviar_lembretes, expirar_subscricoes
from apps.pagamentos.teste import avisar_testes_a_terminar, terminar_testes
from apps.subscriptions.models import PromotionalCode, PromoCodeUsage, SubscriptionHistory, UserSubscription
from apps.users.models import Notification

from .test_fase2 import BaseFase2, criar_promo
from .test_mcx import TEL_EXPIRA, User

URL_TESTE = '/api/v1/pagamentos/teste/'


class BaseCodigos(BaseFase2):
    def para_janela_de_renovacao(self):
        """Põe o período pago actual a 3 dias do fim (renovação permitida)."""
        sub = UserSubscription.objects.get(user=self.user)
        return self.recuar((sub.expires_at - timezone.now()).days - 3)

    def erro(self, plan, periodo, codigo):
        r = self.orcar(plan, periodo, codigo)
        self.assertEqual(r.status_code, 200, r.data)
        return (r.data['erro_codigo'] or {}).get('code')


class RegrasCodigoTests(BaseCodigos):
    def test_periodo(self):
        criar_promo('ANUAL', periodo_aplicavel='anual')
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'ANUAL'), 'periodo_nao_aplicavel')
        self.assertIsNone(self.erro('PREMIUM', 'anual', 'ANUAL'))
        r = self.criar(periodo='mensal', codigo_promocional='ANUAL')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'codigo_promocional')

    def test_planos(self):
        c = criar_promo('PLUS')
        c.applicable_plans.set([self.plus])
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'PLUS'), 'nao_aplicavel')
        self.assertIsNone(self.erro('PREMIUM_PLUS', 'mensal', 'PLUS'))

    def test_rascunho_desligado_expirado(self):
        criar_promo('RASC', estado='rascunho')
        criar_promo('DESL', estado='desligado')
        criar_promo('VELHO', valid_until=timezone.now() - timedelta(hours=1),
                    valid_from=timezone.now() - timedelta(days=3))
        criar_promo('SEMFIM', valid_until=None)
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'RASC'), 'inexistente')
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'DESL'), 'desligado')
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'VELHO'), 'expirado')
        self.assertIsNone(self.erro('PREMIUM', 'mensal', 'SEMFIM'))

    def test_desligado_pelo_campo_antigo(self):
        c = criar_promo('ANTIGO')
        PromotionalCode.objects.filter(pk=c.pk).update(is_active=False)
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'ANTIGO'), 'desligado')

    def test_primeira_compra(self):
        criar_promo('NOVOS', first_time_users_only=True)
        self.assertIsNone(self.erro('PREMIUM', 'mensal', 'NOVOS'))
        self.pagar()
        self.para_janela_de_renovacao()
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'NOVOS'), 'so_primeira_compra')

    def test_limite_de_usos_com_reserva(self):
        criar_promo('UM', max_uses=1)
        r = self.criar(codigo_promocional='UM', telefone=TEL_EXPIRA)
        self.assertEqual(r.status_code, 201, r.data)
        self.client.force_authenticate(self.outro)
        self.assertEqual(self.erro('PREMIUM', 'mensal', 'UM'), 'esgotado')
        # O pendente é cancelado: a reserva é libertada
        self.client.force_authenticate(self.user)
        self.client.post(f'/api/v1/pagamentos/{r.data["id"]}/cancelar/')
        self.client.force_authenticate(self.outro)
        self.assertIsNone(self.erro('PREMIUM', 'mensal', 'UM'))


class DuracaoCodigoTests(BaseCodigos):
    def renovar(self, periodo='mensal', codigo=None):
        self.para_janela_de_renovacao()
        return self.pagar(periodo=periodo, **({'codigo_promocional': codigo} if codigo else {}))

    def test_primeiro_so_no_primeiro_pagamento(self):
        criar_promo('PRIM', duracao='primeiro')
        p1 = self.pagar(codigo_promocional='PRIM')
        self.assertEqual(p1.desconto_kz, 2990)
        p2 = self.renovar()
        self.assertEqual(p2.desconto_kz, 0)
        self.assertEqual(p2.total_kz, 14950)

    def test_meses_nos_primeiros_n_pagamentos_mensais(self):
        criar_promo('TRES', duracao='meses', duracao_meses=3)
        descontos = [self.pagar(codigo_promocional='TRES').desconto_kz]
        for _ in range(3):
            descontos.append(self.renovar().desconto_kz)
        self.assertEqual(descontos, [2990, 2990, 2990, 0])
        promo = PromotionalCode.objects.get(code='TRES')
        self.assertEqual(promo.current_uses, 1)  # as renovações não contam como novas utilizações
        self.assertEqual(PromoCodeUsage.objects.filter(promo_code=promo).count(), 1)
        renov = Pagamento.objects.filter(user=self.user, promo_renovacao=True)
        self.assertEqual(renov.count(), 2)
        self.assertTrue(all(p.codigo_promocional == 'TRES' for p in renov))

    def test_orcamento_de_renovacao_mostra_o_codigo_que_continua(self):
        criar_promo('SEMPRE', duracao='sempre')
        self.pagar(codigo_promocional='SEMPRE')
        self.para_janela_de_renovacao()
        r = self.orcar('PREMIUM')
        self.assertEqual(r.data['desconto_codigo_kz'], 2990)
        self.assertTrue(r.data['codigo']['continua'])
        self.assertIsNone(r.data['erro_codigo'])
        # Escrever o mesmo código outra vez não dá "já utilizou"
        r = self.orcar('PREMIUM', codigo='SEMPRE')
        self.assertIsNone(r.data['erro_codigo'])
        self.assertEqual(r.data['desconto_codigo_kz'], 2990)

    def test_sempre_em_todas_as_renovacoes(self):
        criar_promo('SEMPRE', duracao='sempre')
        self.pagar(codigo_promocional='SEMPRE')
        self.assertEqual([self.renovar().desconto_kz for _ in range(3)], [2990, 2990, 2990])

    def test_codigo_acaba_quando_a_subscricao_termina(self):
        criar_promo('SEMPRE', duracao='sempre')
        self.pagar(codigo_promocional='SEMPRE')
        UserSubscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        expirar_subscricoes()
        self.assertIsNone(UserSubscription.objects.get(user=self.user).promo_codigo)
        self.assertEqual(self.pagar().desconto_kz, 0)

    def test_meses_so_no_pagamento_mensal(self):
        # "Os primeiros N meses" num pagamento anual dava o desconto ao ano inteiro: é recusado
        criar_promo('TRES', duracao='meses', duracao_meses=3)
        self.assertEqual(self.erro('PREMIUM', 'anual', 'TRES'), 'so_mensal')
        r = self.orcar('PREMIUM', 'anual', 'TRES')
        self.assertEqual(r.data['desconto_codigo_kz'], 0)
        self.assertIn('mensal', r.data['erro_codigo']['mensagem'])
        r = self.criar(periodo='anual', codigo_promocional='TRES')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'codigo_promocional')
        self.assertIn('pagamento mensal', r.data['message'])
        self.assertEqual(PromotionalCode.objects.get(code='TRES').current_uses, 0)
        # No mensal funciona
        self.assertEqual(self.pagar(codigo_promocional='TRES').desconto_kz, 2990)

    def test_meses_em_curso_nao_continua_numa_renovacao_anual(self):
        criar_promo('TRES', duracao='meses', duracao_meses=3, periodo_aplicavel='todos')
        self.pagar(codigo_promocional='TRES')
        self.para_janela_de_renovacao()
        self.assertEqual(self.pagar(periodo='anual').desconto_kz, 0)

    def test_primeiro_no_anual_continua_permitido(self):
        criar_promo('PRIM', duracao='primeiro')
        self.assertEqual(self.pagar(periodo='anual', codigo_promocional='PRIM').desconto_kz, 29900)


class TesteGratisTests(BaseCodigos):
    def setUp(self):
        super().setUp()
        self.premium.dias_teste = 7
        self.premium.save()
        self.plus.dias_teste = 0
        self.plus.save()

    def comecar(self, plano='PREMIUM', telefone='923 456 789'):
        corpo = {'plano': plano}
        if telefone is not None:
            corpo['telefone'] = telefone
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(URL_TESTE, corpo, format='json')

    def test_quem_pode_experimentar(self):
        r = self.client.get('/api/v1/subscriptions/my-subscription/')
        self.assertTrue(r.data['pode_experimentar'])
        self.assertEqual(r.data['dias_teste'], 7)
        self.assertFalse(r.data['em_teste'])
        o = self.orcar('PREMIUM').data
        self.assertTrue(o['pode_experimentar'])
        self.assertEqual(o['dias_teste'], 7)
        self.assertFalse(self.orcar('PREMIUM_PLUS').data['pode_experimentar'])
        planos = self.client.get('/api/v1/subscriptions/plans/').data
        planos = planos['results'] if isinstance(planos, dict) else planos
        self.assertEqual({p['plan_type']: p['pode_experimentar'] for p in planos},
                         {'FREE': False, 'PREMIUM': True, 'PREMIUM_PLUS': False})

        self.assertEqual(self.comecar('PREMIUM_PLUS').status_code, 400)  # sem teste

    def test_comecar_teste(self):
        antes = timezone.now()
        r = self.comecar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['em_teste'])
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual((sub.plan, sub.status), (self.premium, 'TRIAL'))
        self.assertEqual(sub.trial_ends_at, sub.expires_at)
        self.assertAlmostEqual((sub.trial_ends_at - antes).total_seconds(), 7 * 86400, delta=60)
        self.assertTrue(sub.is_active())
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=sub, event_type='TRIAL_STARTED').exists())
        self.assertTrue(Notification.objects.filter(user=self.user, title__icontains='teste').exists())
        self.assertTrue(any('teste' in m.subject.lower() for m in mail.outbox))
        r = self.client.get('/api/v1/subscriptions/my-subscription/')
        self.assertTrue(r.data['em_teste'])
        self.assertIsNotNone(r.data['teste_termina_em'])
        self.assertFalse(r.data['pode_experimentar'])
        # Só um teste por pessoa
        r = self.comecar()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'teste_ja_usado')

    def test_quem_ja_pagou_nao_pode(self):
        self.pagar()
        UserSubscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        expirar_subscricoes()
        r = self.comecar()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'ja_assinante')

    def test_fim_do_teste_volta_ao_gratuito(self):
        self.comecar()
        sub = UserSubscription.objects.get(user=self.user)
        fim = timezone.now() - timedelta(minutes=1)
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=fim, trial_ends_at=fim)
        self.assertEqual(expirar_subscricoes(), 0)  # os testes não são tratados como planos pagos
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(terminar_testes(), 1)
        sub.refresh_from_db()
        self.assertEqual((sub.plan.plan_type, sub.status), ('FREE', 'ACTIVE'))
        self.assertEqual(sub.trial_ends_at, fim)  # fica registado
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=sub, event_type='TRIAL_ENDED').exists())
        self.assertTrue(Notification.objects.filter(user=self.user, title__icontains='terminou').exists())
        self.assertEqual(terminar_testes(), 0)  # idempotente
        r = self.client.get('/api/v1/subscriptions/my-subscription/')
        self.assertFalse(r.data['em_teste'])
        self.assertFalse(r.data['pode_experimentar'])

    def test_pagar_durante_o_teste_nao_perde_dias(self):
        self.comecar()
        sub = UserSubscription.objects.get(user=self.user)
        fim_teste = sub.trial_ends_at
        o = self.orcar('PREMIUM').data
        self.assertEqual(o['operacao'], 'conversao_teste')
        self.assertTrue(o['pode_comprar'])
        self.assertTrue(o['em_teste'])
        self.assertEqual(o['credito_kz'], 0)
        p = self.pagar()
        self.assertEqual(p.total_kz, 14950)
        self.assertEqual(p.periodo_inicio, fim_teste)
        self.assertEqual(p.periodo_fim, fim_teste + timedelta(days=30))
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.expires_at), ('ACTIVE', fim_teste + timedelta(days=30)))
        self.assertEqual(sub.preco_mensal_kz, 14950)
        self.assertEqual(terminar_testes(agora=fim_teste + timedelta(hours=1)), 0)
        self.assertEqual(sub.history.filter(event_type='CREATED').count(), 1)

    def test_codigo_de_primeira_compra_vale_ao_pagar_o_teste(self):
        criar_promo('NOVOS', first_time_users_only=True)
        self.comecar()
        self.assertIsNone(self.erro('PREMIUM', 'mensal', 'NOVOS'))

    def test_aviso_dois_dias_antes(self):
        self.comecar()
        sub = UserSubscription.objects.get(user=self.user)
        fim = timezone.now() + timedelta(hours=40)
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=fim, trial_ends_at=fim)
        mail.outbox.clear()
        self.assertEqual(len(enviar_lembretes()), 0)  # os lembretes de renovação não são para testes
        self.assertEqual(len(avisar_testes_a_terminar()), 1)
        self.assertEqual(len(avisar_testes_a_terminar()), 0)
        self.assertTrue(LembreteRenovacao.objects.filter(subscription=sub, tipo='T2').exists())
        n = Notification.objects.filter(user=self.user, title__icontains='termina').first()
        self.assertIsNotNone(n)
        self.assertIn('Multicaixa Express', n.body)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Multicaixa Express', mail.outbox[0].body)

    def test_comando(self):
        self.comecar()
        UserSubscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        out = StringIO()
        call_command('terminar_testes', stdout=out)
        self.assertIn('testes terminados (voltaram ao Gratuito): 1', out.getvalue())
