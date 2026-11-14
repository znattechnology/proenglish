"""
Correcções verificadas: códigos "meses" só no mensal (validação na administração), bloqueio
dos códigos só por utilizações reais (bloqueado), PATCH parcial de "aplica", exemplo coerente
e minutos de conversa None = ilimitado.
"""

from datetime import timedelta

from django.utils import timezone

from apps.pagamentos import services
from apps.pagamentos.models import Pagamento
from apps.pagamentos.tests.test_mcx import TEL_EXPIRA
from apps.subscriptions.models import PromotionalCode, UserSubscription

from .test_admin_planos_codigos import URL_CODIGOS, BaseAdmin


class CodigoBase(BaseAdmin):
    def criar(self, **dados):
        corpo = {'codigo': 'BOAS20', 'desconto': {'tipo': 'percentagem', 'valor': 20},
                 'aplica': {'planos': [], 'periodo': 'todos'}, 'estado': 'activo'}
        corpo.update(dados)
        return self.client.post(URL_CODIGOS, corpo, format='json')

    def patch(self, cid, corpo):
        return self.client.patch(f'{URL_CODIGOS}{cid}/', corpo, format='json')


class MesesSoMensalTests(CodigoBase):
    def test_criar_meses_exige_mensal(self):
        for periodo in ('todos', 'anual'):
            r = self.criar(codigo=f'TRES{periodo.upper()}', duracao={'tipo': 'meses', 'meses': 3},
                           aplica={'planos': [], 'periodo': periodo})
            self.assertEqual(r.status_code, 400, r.data)
            self.assertEqual(r.data['code'], 'validacao')
            self.assertIn('aplica.periodo', r.data['details'])
            self.assertIsInstance(r.data['details']['aplica.periodo'], list)
        r = self.criar(codigo='TRES', duracao={'tipo': 'meses', 'meses': 3}, aplica={'planos': [], 'periodo': 'mensal'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('nos primeiros 3 meses', r.data['exemplo'])
        self.assertIn('mensal', r.data['exemplo'])

    def test_patch_meses_valida_com_os_valores_guardados(self):
        cid = self.criar().data['id']  # periodo "todos"
        r = self.patch(cid, {'duracao': {'tipo': 'meses', 'meses': 2}})
        self.assertEqual(r.status_code, 400)
        self.assertIn('aplica.periodo', r.data['details'])
        r = self.patch(cid, {'duracao': {'tipo': 'meses', 'meses': 2}, 'aplica': {'periodo': 'mensal'}})
        self.assertEqual(r.status_code, 200, r.data)
        r = self.patch(cid, {'aplica': {'periodo': 'anual'}})
        self.assertEqual(r.status_code, 400)

    def test_primeiro_no_anual_e_exemplo(self):
        r = self.criar(codigo='PRIM', aplica={'planos': ['PREMIUM'], 'periodo': 'todos'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['exemplo'].replace('\xa0', ' '), 'o Premium anual passa de 149 500 Kz para 119 600 Kz no 1.º pagamento')
        r = self.criar(codigo='PRIMM', aplica={'planos': ['PREMIUM'], 'periodo': 'mensal'})
        self.assertEqual(r.data['descricao'], '20% no 1.º mês, só no Premium mensal')
        self.assertEqual(r.data['exemplo'].replace('\xa0', ' '), 'o Premium mensal passa de 14 950 Kz para 11 960 Kz no 1.º mês')


class AplicaParcialTests(CodigoBase):
    def test_patch_so_planos_mantem_periodo(self):
        cid = self.criar(aplica={'planos': ['PREMIUM'], 'periodo': 'anual'}).data['id']
        r = self.patch(cid, {'aplica': {'planos': ['PREMIUM', 'PREMIUM_PLUS']}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['aplica'], {'planos': ['PREMIUM', 'PREMIUM_PLUS'], 'periodo': 'anual'})
        r = self.patch(cid, {'aplica': {'periodo': 'mensal'}})
        self.assertEqual(r.data['aplica'], {'planos': ['PREMIUM', 'PREMIUM_PLUS'], 'periodo': 'mensal'})
        self.assertEqual(set(PromotionalCode.objects.get(pk=cid).applicable_plans.values_list('plan_type', flat=True)),
                         {'PREMIUM', 'PREMIUM_PLUS'})


class BloqueadoTests(CodigoBase):
    def bloqueado(self, cid):
        d = self.client.get(f'{URL_CODIGOS}{cid}/').data
        lista = {c['id']: c['bloqueado'] for c in self.client.get(URL_CODIGOS).data['resultados']}
        self.assertEqual(lista[cid], d['bloqueado'])
        return d['bloqueado']

    def test_pagamento_falhado_nao_bloqueia(self):
        cid = self.criar().data['id']
        self.assertFalse(self.bloqueado(cid))
        p = services.criar_pagamento_mcx(self.aluno, telefone=TEL_EXPIRA, plan_id=str(self.premium.id),
                                         periodo='mensal', codigo_promocional='BOAS20')
        self.assertTrue(self.bloqueado(cid))  # reserva activa (pagamento pendente)
        self.assertEqual(self.patch(cid, {'desconto': {'tipo': 'percentagem', 'valor': 30}}).status_code, 409)
        services.cancelar_pagamento(p)
        self.assertFalse(self.bloqueado(cid))
        # Um pagamento cancelado com o código não impede editar
        self.assertTrue(Pagamento.objects.filter(codigo_promocional='BOAS20').exists())
        r = self.patch(cid, {'desconto': {'tipo': 'percentagem', 'valor': 30}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['bloqueado'])

    def test_reserva_caducada_nao_bloqueia(self):
        cid = self.criar().data['id']
        p = services.criar_pagamento_mcx(self.aluno, telefone=TEL_EXPIRA, plan_id=str(self.premium.id),
                                         periodo='mensal', codigo_promocional='BOAS20')
        Pagamento.objects.filter(pk=p.pk).update(expira_em=timezone.now() - timedelta(minutes=1))
        self.assertFalse(self.bloqueado(cid))

    def test_pago_bloqueia(self):
        cid = self.criar().data['id']
        self.pagar(self.aluno, self.premium, codigo='BOAS20')
        self.assertTrue(self.bloqueado(cid))
        self.assertTrue(self.patch(cid, {'max_usos': 10}).data['bloqueado'])


class ConversaIlimitadaTests(BaseAdmin):
    def test_none_e_ilimitado_e_zero_bloqueado(self):
        from apps.subscriptions.utils import check_subscription_limits as check_feature_access
        sub = UserSubscription.objects.get(user=self.aluno)
        sub.plan = self.premium
        sub.expires_at = timezone.now() + timedelta(days=10)
        sub.save()
        self.premium.daily_speaking_minutes = None
        self.premium.trial_days = 0
        self.premium.save()
        sub.refresh_from_db()
        self.assertIsNone(sub.get_effective_speaking_limit())
        self.assertTrue(sub.can_use_speaking(500))
        self.assertTrue(check_feature_access(self.aluno, 'speaking', 500)['allowed'])
        self.premium.daily_speaking_minutes = 0
        self.premium.save()
        sub.refresh_from_db()
        self.assertEqual(sub.get_effective_speaking_limit(), 0)
        self.assertFalse(sub.can_use_speaking())
        self.assertFalse(check_feature_access(self.aluno, 'speaking', 1)['allowed'])
        self.premium.daily_speaking_minutes = 10
        self.premium.save()
        sub.refresh_from_db()
        self.assertTrue(sub.can_use_speaking(10))
        self.assertFalse(sub.can_use_speaking(11))
