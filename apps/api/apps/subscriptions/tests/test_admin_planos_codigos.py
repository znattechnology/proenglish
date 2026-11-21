"""
Administração de planos e códigos promocionais (/api/v1/admin/planos/, /api/v1/admin/codigos/):
permissões (EAdministrador), regras do PATCH dos planos, destaque único, preço contratado
(grandfathering) e gestão dos códigos.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.pagamentos import services
from apps.pagamentos.models import Pagamento
from apps.pagamentos.tests.test_mcx import TEL_EXPIRA, User, criar_planos
from apps.subscriptions.models import PromotionalCode, SubscriptionPlan, UserSubscription

URL_PLANOS = '/api/v1/admin/planos/'
URL_CODIGOS = '/api/v1/admin/codigos/'


class BaseAdmin(APITestCase):
    def setUp(self):
        self.free, self.premium, self.plus = criar_planos()
        self.admin = User.objects.create_user(email='admin@example.com', name='Admin', password='x12345678',
                                              role='admin')
        self.aluno = User.objects.create_user(email='aluno@example.com', name='Aluno', password='x12345678')
        self.client.force_authenticate(self.admin)

    def pagar(self, user, plan, periodo='mensal', codigo=None):
        p = services.criar_pagamento_mcx(user, telefone=TEL_EXPIRA, plan_id=str(plan.id), periodo=periodo,
                                         codigo_promocional=codigo)
        return services.confirmar_pagamento(p)


class PermissoesTests(BaseAdmin):
    def _estado(self, user, url):
        self.client.force_authenticate(user)
        return self.client.get(url).status_code

    def test_so_administradores(self):
        staff = User.objects.create_user(email='staff@example.com', name='Staff', password='x12345678')
        staff.is_staff = True
        staff.save()
        root = User.objects.create_superuser(email='root@example.com', name='Root', password='x12345678')
        for url in (URL_PLANOS, URL_CODIGOS, '/api/v1/subscriptions/admin/plans/',
                    '/api/v1/subscriptions/admin/promo-codes/', '/api/v1/subscriptions/admin/stats/'):
            self.assertEqual(self._estado(self.admin, url), 200, url)
            self.assertEqual(self._estado(root, url), 200, url)
            self.assertEqual(self._estado(self.aluno, url), 403, url)
            self.assertEqual(self._estado(staff, url), 403, url)  # is_staff sozinho não é admin

    def test_sem_sessao(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL_PLANOS).status_code, (401, 403))


class PlanosTests(BaseAdmin):
    def patch(self, plano, dados):
        return self.client.patch(f'{URL_PLANOS}{plano.id}/', dados, format='json')

    def test_lista(self):
        self.pagar(self.aluno, self.premium)
        r = self.client.get(URL_PLANOS)
        self.assertEqual(r.status_code, 200)
        por_tipo = {p['tipo']: p for p in r.data}
        prem = por_tipo['PREMIUM']
        self.assertEqual(prem['preco_mensal_kz'], 14950)
        self.assertEqual(prem['preco_anual_kz'], 149500)
        self.assertEqual(set(prem['limites']), {'licoes_dia', 'vidas', 'conversa_min_dia', 'conversa_min_mes',
                                                'teste_conversa_min_dia', 'teste_conversa_dias', 'sessoes_nativo_mes',
                                                'protecoes_semana', 'pronuncia_detalhada_dia'})
        self.assertIsNone(prem['limites']['vidas'])  # 0 no modelo = ilimitadas
        self.assertEqual(prem['utilizadores'], 1)
        self.assertEqual(prem['assinantes'], 1)
        self.assertEqual(por_tipo['FREE']['assinantes'], 0)

    def test_validacoes(self):
        r = self.patch(self.premium, {'preco_anual_kz': 14950 * 12 + 1})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'validacao')
        self.assertIn('preco_anual_kz', r.data['details'])
        self.assertIsInstance(r.data['details']['preco_anual_kz'], list)
        self.assertEqual(self.patch(self.premium, {'dias_teste': 31}).status_code, 400)
        self.assertEqual(self.patch(self.premium, {'preco_mensal_kz': 0}).status_code, 400)
        self.assertEqual(self.patch(self.free, {'activo': False}).status_code, 400)
        self.assertEqual(self.patch(self.free, {'preco_mensal_kz': 500}).status_code, 400)
        self.assertEqual(self.patch(self.free, {'dias_teste': 7}).status_code, 400)
        self.premium.refresh_from_db()
        self.assertEqual(self.premium.monthly_price, Decimal('14950'))

    def test_altera_campos_e_limites(self):
        r = self.patch(self.free, {'nome': 'Grátis', 'limites': {'licoes_dia': 5, 'vidas': 4, 'conversa_min_dia': 3,
                                                                  'protecoes_semana': 1}, 'certificados': True})
        self.assertEqual(r.status_code, 200, r.data)
        self.free.refresh_from_db()
        self.assertEqual((self.free.name, self.free.daily_lessons_limit, self.free.hearts_limit,
                          self.free.daily_speaking_minutes, self.free.streak_freeze, self.free.certificates),
                         ('Grátis', 5, 4, 3, 1, True))
        r = self.patch(self.premium, {'limites': {'licoes_dia': None, 'vidas': None}, 'dias_teste': 10,
                                      'preco_anual_kz': None})
        self.assertEqual(r.status_code, 200, r.data)
        self.premium.refresh_from_db()
        self.assertEqual((self.premium.daily_lessons_limit, self.premium.hearts_limit, self.premium.dias_teste,
                          self.premium.yearly_price), (None, 0, 10, None))

    def test_baixar_vidas_ajusta_quem_tem_mais(self):
        sub = UserSubscription.objects.get(user=self.aluno)
        sub.current_hearts = 5
        sub.save()
        self.patch(self.free, {'limites': {'vidas': 2}})
        sub.refresh_from_db()
        self.assertEqual(sub.current_hearts, 2)

    def test_so_um_plano_em_destaque(self):
        self.assertEqual(self.patch(self.plus, {'destaque': True}).status_code, 200)
        self.assertEqual(list(SubscriptionPlan.objects.filter(destaque=True)), [self.plus])
        self.assertEqual(self.patch(self.premium, {'destaque': True}).status_code, 200)
        self.assertEqual(list(SubscriptionPlan.objects.filter(destaque=True)), [self.premium])
        planos = self.client.get('/api/v1/subscriptions/plans/').data
        planos = planos['results'] if isinstance(planos, dict) else planos
        self.assertEqual([p['plan_type'] for p in planos if p['is_most_popular']], ['PREMIUM'])


class PrecoContratadoTests(BaseAdmin):
    """Quem já paga mantém o preço nas renovações; o preço novo só vale para subscrições novas."""

    def test_renovacao_usa_o_preco_contratado(self):
        self.pagar(self.aluno, self.premium)
        sub = UserSubscription.objects.get(user=self.aluno)
        self.assertEqual((sub.preco_mensal_kz, sub.preco_anual_kz), (14950, 149500))
        r = self.client.patch(f'{URL_PLANOS}{self.premium.id}/', {'preco_mensal_kz': 19950, 'preco_anual_kz': 199500},
                              format='json')
        self.assertEqual(r.status_code, 200, r.data)

        # Entrar na janela de renovação (faltam < 7 dias)
        sub.expires_at = timezone.now() + timedelta(days=3)
        sub.save()
        o = services.calcular_orcamento(self.aluno, self.premium, 'mensal')
        self.assertEqual(o.operacao, 'renovacao')
        self.assertEqual(o.valor_kz, 14950)
        self.assertEqual(services.calcular_orcamento(self.aluno, self.premium, 'anual').valor_kz, 149500)
        p = self.pagar(self.aluno, self.premium)
        self.assertEqual(p.valor_kz, 14950)
        self.assertEqual(services.periodo_atual(UserSubscription.objects.get(user=self.aluno))['valor_periodo_kz'],
                         14950)

        novo = User.objects.create_user(email='novo@example.com', name='Novo', password='x12345678')
        self.assertEqual(services.calcular_orcamento(novo, 'PREMIUM', 'mensal').valor_kz, 19950)

    def test_preco_contratado_acaba_quando_a_subscricao_termina(self):
        from apps.pagamentos.renovacao import expirar_subscricoes
        self.pagar(self.aluno, self.premium)
        SubscriptionPlan.objects.filter(pk=self.premium.pk).update(monthly_price=Decimal('19950'))
        UserSubscription.objects.filter(user=self.aluno).update(expires_at=timezone.now() - timedelta(minutes=1))
        expirar_subscricoes()
        sub = UserSubscription.objects.get(user=self.aluno)
        self.assertEqual(sub.plan.plan_type, 'FREE')
        self.assertIsNone(sub.preco_mensal_kz)
        self.assertEqual(services.calcular_orcamento(self.aluno, 'PREMIUM', 'mensal').valor_kz, 19950)

    def test_mudar_de_plano_fixa_o_preco_do_plano_novo(self):
        self.pagar(self.aluno, self.premium)
        self.pagar(self.aluno, self.plus)
        sub = UserSubscription.objects.get(user=self.aluno)
        self.assertEqual(sub.preco_mensal_kz, 24950)


class CodigosAdminTests(BaseAdmin):
    def criar(self, **dados):
        corpo = {'codigo': 'boas20', 'desconto': {'tipo': 'percentagem', 'valor': 40},
                 'aplica': {'planos': ['PREMIUM'], 'periodo': 'anual'}}
        corpo.update(dados)
        return self.client.post(URL_CODIGOS, corpo, format='json')

    def test_cria_rascunho_com_exemplo_e_descricao(self):
        r = self.criar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['codigo'], 'BOAS20')
        self.assertEqual(r.data['estado'], 'rascunho')
        self.assertEqual(r.data['desconto'], {'tipo': 'percentagem', 'valor': 40})
        self.assertEqual(r.data['aplica'], {'planos': ['PREMIUM'], 'periodo': 'anual'})
        self.assertEqual(r.data['duracao'], {'tipo': 'primeiro', 'meses': None})
        self.assertEqual(r.data['usos'], 0)
        self.assertIsNone(r.data['max_usos'])
        self.assertEqual(r.data['exemplo'],
                         'o Premium anual passa de 149 500 Kz para 89 700 Kz no 1.º pagamento')
        self.assertEqual(r.data['descricao'], '40% no 1.º pagamento, só no Premium anual')
        c = PromotionalCode.objects.get(code='BOAS20')
        self.assertFalse(c.is_active)

    def test_descricao_meses(self):
        r = self.criar(codigo='TRES', desconto={'tipo': 'valor', 'valor': 5000}, aplica={'planos': [], 'periodo': 'mensal'},
                       duracao={'tipo': 'meses', 'meses': 3})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['descricao'], '5 000 Kz nos primeiros 3 meses, só no pagamento mensal')
        self.assertIn('nos primeiros 3 meses', r.data['exemplo'])

    def test_validacoes(self):
        self.assertEqual(self.criar().status_code, 201)
        r = self.criar()
        self.assertEqual(r.status_code, 400)
        self.assertIn('codigo', r.data['details'])
        self.assertEqual(self.criar(codigo='AB').status_code, 400)
        self.assertEqual(self.criar(codigo='COM ESPACO').status_code, 400)
        self.assertEqual(self.criar(codigo='X1', desconto={'tipo': 'percentagem', 'valor': 120}).status_code, 400)
        self.assertEqual(self.criar(codigo='OUTRO1', aplica={'planos': ['FREE']}).status_code, 400)
        self.assertEqual(self.criar(codigo='OUTRO2', duracao={'tipo': 'meses'}).status_code, 400)
        ontem = (timezone.now() - timedelta(days=2)).date().isoformat()
        self.assertEqual(self.criar(codigo='OUTRO3', termina=ontem).status_code, 400)

    def test_activar_desligar_e_filtros(self):
        cid = self.criar().data['id']
        r = self.client.post(f'{URL_CODIGOS}{cid}/activar/')
        self.assertEqual(r.data['estado'], 'activo')
        self.assertTrue(PromotionalCode.objects.get(pk=cid).is_active)
        self.criar(codigo='RASC')
        lista = self.client.get(URL_CODIGOS, {'estado': 'activos'}).data
        self.assertEqual([c['codigo'] for c in lista['resultados']], ['BOAS20'])
        self.assertEqual(lista['numeros']['activos'], 1)
        self.assertEqual(lista['numeros']['rascunhos'], 1)
        self.assertEqual(len(self.client.get(URL_CODIGOS).data['resultados']), 2)
        r = self.client.post(f'{URL_CODIGOS}{cid}/desligar/')
        self.assertEqual(r.data['estado'], 'desligado')
        # Esgotado e expirado são derivados
        c = PromotionalCode.objects.get(pk=cid)
        c.estado, c.max_uses, c.current_uses = 'activo', 1, 1
        c.save()
        self.assertEqual([x['codigo'] for x in self.client.get(URL_CODIGOS, {'estado': 'esgotados'}).data['resultados']],
                         ['BOAS20'])
        PromotionalCode.objects.filter(pk=cid).update(valid_until=timezone.now() - timedelta(days=1))
        self.assertEqual(len(self.client.get(URL_CODIGOS, {'estado': 'expirados'}).data['resultados']), 1)
        self.assertEqual(self.client.post(f'{URL_CODIGOS}{cid}/activar/').status_code, 409)

    def test_depois_de_usado_nao_muda_desconto_nem_regras(self):
        r = self.criar(estado='activo', aplica={'planos': [], 'periodo': 'todos'})
        cid = r.data['id']
        self.pagar(self.aluno, self.premium, codigo='BOAS20')
        d = self.client.get(f'{URL_CODIGOS}{cid}/').data
        self.assertEqual(d['usos'], 1)
        self.assertEqual(len(d['utilizacoes']), 1)
        self.assertEqual(d['utilizacoes'][0]['utilizador']['nome'], 'Aluno')
        self.assertEqual(d['utilizacoes'][0]['valor_desconto_kz'], 5980)
        for corpo in ({'desconto': {'tipo': 'percentagem', 'valor': 10}}, {'aplica': {'planos': ['PREMIUM']}},
                      {'duracao': {'tipo': 'sempre'}}, {'codigo': 'NOVO'}):
            r = self.client.patch(f'{URL_CODIGOS}{cid}/', corpo, format='json')
            self.assertEqual(r.status_code, 409, corpo)
            self.assertEqual(r.data['code'], 'codigo_em_uso')
        self.assertEqual(self.client.patch(f'{URL_CODIGOS}{cid}/', {'max_usos': 0}, format='json').status_code, 400)
        r = self.client.patch(f'{URL_CODIGOS}{cid}/', {'max_usos': 50, 'termina': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['max_usos'], 50)
        numeros = self.client.get(URL_CODIGOS).data['numeros']
        self.assertEqual((numeros['usados_mes'], numeros['pessoas_mes'], numeros['desconto_mes_kz']), (1, 1, 5980))
        self.assertIsNone(numeros['continuam_2_mes_pct'])

    def test_antes_de_usado_pode_mudar_tudo(self):
        cid = self.criar().data['id']
        r = self.client.patch(f'{URL_CODIGOS}{cid}/', {'desconto': {'tipo': 'valor', 'valor': 2000},
                                                       'duracao': {'tipo': 'sempre'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['descricao'], '2 000 Kz em todos os pagamentos, só no Premium anual')
        self.assertEqual(Pagamento.objects.count(), 0)
