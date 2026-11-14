"""
Administração de subscrições, pagamentos e relatórios (/api/v1/admin/...): permissões, estado de
cada subscrição, números do resumo, falhados (novo pedido simulado e lembrete), relatórios e CSV.
"""

from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.subscriptions.models import UserSubscription
from apps.pagamentos.admin_api import metricas as m
from apps.pagamentos.admin_api.views import celula
from apps.pagamentos.models import Pagamento

from .test_mcx import User, criar_planos, definir_assinatura

URL = '/api/v1/admin/'
TEL_OK = '923456789'
TEL_RECUSA = '923450000'
TEL_PENDENTE = '923451111'


def tem_provincia():
    return m.user_tem_provincia()


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.agora = timezone.now()
        self.free, self.premium, self.plus = criar_planos()
        self.admin = User.objects.create_user(email='admin@example.com', name='Ana Admin',
                                              password='x' * 12, role='admin')
        self._n = 0

    def aluno(self, nome, dias_conta=60):
        self._n += 1
        u = User.objects.create_user(email=f'aluno{self._n}@example.com', name=nome,
                                     password='x' * 12, role='student')
        User.objects.filter(pk=u.pk).update(created_at=self.agora - timedelta(days=dias_conta))
        u.refresh_from_db()
        return u

    def pago(self, user, plan, inicio, fim, pago_em=None, periodo='mensal', desconto=0, codigo=None,
             telefone=TEL_OK, **campos):
        valor = int(plan.yearly_price if periodo == 'anual' else plan.monthly_price)
        p = Pagamento.objects.create(
            user=user, plan=plan, periodo=periodo, valor_kz=valor, desconto_kz=desconto,
            codigo_promocional=codigo, telefone=telefone, provedor='simulado', estado=Pagamento.PAGO,
            expira_em=inicio + timedelta(minutes=5), pago_em=pago_em or inicio,
            periodo_inicio=inicio, periodo_fim=fim, **campos)
        # O pedido foi criado pouco antes de ser pago
        Pagamento.objects.filter(pk=p.pk).update(created_at=p.pago_em - timedelta(minutes=1))
        p.refresh_from_db()
        return p

    def falhado(self, user, plan, estado=Pagamento.RECUSADO, motivo='Pagamento recusado no telemóvel.',
                telefone=TEL_RECUSA, ha=timedelta(hours=1)):
        p = Pagamento.objects.create(
            user=user, plan=plan, periodo='mensal', valor_kz=int(plan.monthly_price),
            telefone=telefone, provedor='simulado', estado=estado, motivo_falha=motivo,
            expira_em=self.agora - ha + timedelta(minutes=5))
        Pagamento.objects.filter(pk=p.pk).update(created_at=self.agora - ha, updated_at=self.agora - ha)
        p.refresh_from_db()
        return p

    def como_admin(self):
        self.client.force_authenticate(self.admin)


class PermissoesTests(Base):
    ROTAS_GET = ['subscricoes/resumo/', 'subscricoes/', 'pagamentos/', 'pagamentos/falhados/',
                 'relatorios/', 'relatorios/exportar/', 'ganhos/']

    def test_so_administradores(self):
        prof = User.objects.create_user(email='prof@example.com', name='Prof', password='x' * 12,
                                        role='teacher')
        aluno = self.aluno('Aluno')
        staff = User.objects.create_user(email='staff@example.com', name='Staff', password='x' * 12,
                                         role='student', is_staff=True)
        p = self.falhado(aluno, self.premium)
        for quem in (prof, aluno, staff):
            self.client.force_authenticate(quem)
            for rota in self.ROTAS_GET:
                self.assertEqual(self.client.get(URL + rota).status_code, 403, (quem.email, rota))
            for accao in ('novo-pedido', 'lembrete'):
                self.assertEqual(self.client.post(f'{URL}pagamentos/{p.pk}/{accao}/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL + 'subscricoes/').status_code, (401, 403))

        self.como_admin()
        for rota in self.ROTAS_GET:
            self.assertEqual(self.client.get(URL + rota).status_code, 200, rota)

    def test_superutilizador_entra(self):
        su = User.objects.create_superuser(email='su@example.com', name='Super', password='x' * 12)
        self.client.force_authenticate(su)
        self.assertEqual(self.client.get(URL + 'subscricoes/resumo/').status_code, 200)

    def test_erros_no_formato_comum(self):
        self.como_admin()
        r = self.client.get(URL + 'subscricoes/?estado=xpto')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()), {'error', 'message', 'code', 'details'})
        self.assertIsInstance(r.json()['details']['estado'], list)
        self.assertEqual(self.client.get(URL + 'relatorios/?periodo=7').json()['code'], 'periodo_invalido')
        self.assertEqual(self.client.get(URL + 'pagamentos/?estado=xpto').status_code, 400)


class CenarioTests(Base):
    """Um aluno em cada estado."""

    def setUp(self):
        super().setUp()
        a = self.agora
        # Activa: Premium, pagou há 40 dias um período até daqui a 20 dias
        self.u_activa = self.aluno('Bruno Activo')
        definir_assinatura(self.u_activa, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=20))
        self.p_activa = self.pago(self.u_activa, self.premium, a - timedelta(days=40), a + timedelta(days=20),
                                  pago_em=a - timedelta(hours=2), desconto=4950, codigo='BEMVINDO')
        # A expirar: Premium Plus anual, termina daqui a 3 dias, lembretes desligados
        self.u_expirar = self.aluno('Carla Expira')
        definir_assinatura(self.u_expirar, plan=self.plus, status='ACTIVE', expires_at=a + timedelta(days=3),
                           lembretes_renovacao=False)
        self.p_expirar = self.pago(self.u_expirar, self.plus, a - timedelta(days=27), a + timedelta(days=3),
                                   pago_em=a - timedelta(hours=1), periodo='anual')
        # Também termina em 3 dias, mas já tem um pedido de renovação pendente: activa
        self.u_pendente = self.aluno('Diogo Pendente')
        definir_assinatura(self.u_pendente, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=2))
        self.pago(self.u_pendente, self.premium, a - timedelta(days=28), a + timedelta(days=2),
                  pago_em=a - timedelta(days=28))
        Pagamento.objects.create(user=self.u_pendente, plan=self.premium, periodo='mensal', valor_kz=14950,
                                 telefone=TEL_PENDENTE, provedor='simulado')
        # Em teste
        self.u_teste = self.aluno('Eva Teste')
        definir_assinatura(self.u_teste, plan=self.premium, status='TRIAL',
                           expires_at=a + timedelta(days=5), trial_ends_at=a + timedelta(days=5))
        # Falhou: no Gratuito, tentou pagar e foi recusado
        self.u_falhou = self.aluno('Filipe Falha')
        self.p_falhou = self.falhado(self.u_falhou, self.premium)
        # Cancelada: pagou de 50 a 10 dias atrás e não renovou
        self.u_cancelada = self.aluno('Gina Cancelada')
        self.pago(self.u_cancelada, self.premium, a - timedelta(days=50), a - timedelta(days=10),
                  pago_em=a - timedelta(days=50))
        # Gratuito sem pagamentos: não aparece
        self.u_free = self.aluno('Hugo Gratuito')

    def _estados(self, **params):
        self.como_admin()
        r = self.client.get(URL + 'subscricoes/', params)
        self.assertEqual(r.status_code, 200)
        return r.json(), {x['utilizador']['email']: x for x in r.json()['resultados']}

    def test_classificacao(self):
        dados, por_email = self._estados()
        estado = {e: por_email[u.email]['estado'] for e, u in [
            ('activa', self.u_activa), ('a_expirar', self.u_expirar), ('pendente', self.u_pendente),
            ('teste', self.u_teste), ('falhou', self.u_falhou), ('cancelada', self.u_cancelada)]}
        self.assertEqual(estado, {'activa': 'activa', 'a_expirar': 'a_expirar', 'pendente': 'activa',
                                  'teste': 'em_teste', 'falhou': 'falhou', 'cancelada': 'cancelada'})
        self.assertNotIn(self.u_free.email, por_email)
        self.assertEqual(dados['total'], 6)
        self.assertEqual(dados['pagas'], 3)
        self.assertEqual(dados['em_teste'], 1)
        self.assertEqual(dados['contagens']['activa'], 2)

        expira = por_email[self.u_expirar.email]
        self.assertEqual(expira['nota'], 'Lembretes desligados')  # não cancelou: só desligou os lembretes
        self.assertEqual(expira['periodo'], 'anual')
        self.assertEqual(expira['plano'], 'Premium Plus')
        self.assertEqual(expira['pagamento'], 'MCX 9•• ••• 789')
        self.assertIsNotNone(expira['proxima_data'])
        falhou = por_email[self.u_falhou.email]
        self.assertEqual(falhou['nota'], 'Ainda sem pagamento')
        self.assertEqual(falhou['pagamento'], 'MCX 9•• ••• 000')
        self.assertIsNone(falhou['proxima_data'])
        self.assertEqual(por_email[self.u_teste.email]['nota'], 'Ainda sem pagamento')
        self.assertEqual(por_email[self.u_teste.email]['periodo'], 'teste')
        self.assertIsNone(por_email[self.u_activa.email]['nota'])
        self.assertIsNone(por_email[self.u_cancelada.email]['proxima_data'])
        # Ordem: falhados primeiro
        self.assertEqual(dados['resultados'][0]['estado'], 'falhou')

    def test_filtros_e_pesquisa(self):
        for filtro, esperado in [('activas', 2), ('a_expirar', 1), ('em_teste', 1), ('falhou', 1),
                                 ('canceladas', 1), ('todas', 6)]:
            dados, _ = self._estados(estado=filtro)
            self.assertEqual(dados['total'], esperado, filtro)
        dados, por_email = self._estados(q='carla')
        self.assertEqual(list(por_email), [self.u_expirar.email])
        self.assertEqual(dados['pagas'], 3)  # contagens dos separadores não dependem da pesquisa

    def test_falha_na_renovacao_tem_prioridade(self):
        self.falhado(self.u_activa, self.premium, estado=Pagamento.EXPIRADO,
                     motivo='O pagamento expirou sem confirmação no telemóvel.', telefone=TEL_PENDENTE)
        _, por_email = self._estados()
        linha = por_email[self.u_activa.email]
        self.assertEqual(linha['estado'], 'falhou')
        self.assertIsNone(linha['nota'])  # já pagou antes
        self.assertIsNotNone(linha['proxima_data'])  # ainda tem acesso até ao fim do período

    def test_resumo(self):
        self.como_admin()
        r = self.client.get(URL + 'subscricoes/resumo/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual((d['assinantes_pagos'], d['premium'], d['premium_plus'], d['em_teste']), (3, 2, 1, 1))
        # Pagos neste mês (Luanda): activa (14 950 - 4 950) + a expirar (anual 249 500); outros são antigos
        inicio = m.inicio_mes(self.agora)
        esperado = sum(p.total_kz for p in Pagamento.objects.filter(estado='pago', pago_em__gte=inicio))
        self.assertEqual(d['receita_mes_kz'], esperado)
        self.assertGreaterEqual(d['receita_mes_kz'], 10000 + 249500)
        self.assertEqual(d['receita_ate'], timezone.localtime(self.agora, m.FUSO_ANGOLA).date().isoformat())

        recentes = d['recentes']
        self.assertEqual(recentes[0]['descricao'], 'Premium Plus, anual')
        self.assertEqual(recentes[1]['descricao'], 'Premium, 1.º mês com BEMVINDO')
        self.assertEqual(recentes[1]['valor_kz'], 10000)
        self.assertEqual(recentes[1]['utilizador']['iniciais'], 'BA')
        self.assertLessEqual(len(recentes), 8)

        planos = {x['plano']: x for x in d['por_plano']}
        self.assertEqual(planos['PREMIUM'], {'plano': 'PREMIUM', 'nome': 'Premium', 'utilizadores': 3,
                                             'pagos': 2, 'em_teste': 1, 'atribuidos': 0})
        self.assertEqual((planos['PREMIUM_PLUS']['utilizadores'], planos['PREMIUM_PLUS']['pagos']), (1, 1))
        self.assertEqual(planos['FREE']['utilizadores'], 3)  # falhou, cancelada, gratuito

        self.assertEqual(d['atencao']['falhados_semana'], 1)
        self.assertEqual(d['atencao']['falhados_semana_kz'], 14950)
        # A expirar (3 dias); o "pendente" termina em 2 dias mas já tem um pedido em curso
        self.assertEqual(d['atencao']['terminam_3_dias'], 1)

        # Há 30 dias pagavam: activa, cancelada (e pendente? começou há 28 dias: não). Agora a cancelada
        # já não paga: 1 em 2 -> 50 %.
        self.assertEqual(d['cancelam_pct'], 50.0)
        # No Gratuito há 30 dias (contas criadas há 60): expira, pendente, teste, falhou, gratuito (5);
        # pagam agora: expira e pendente -> 40 %.
        self.assertEqual(d['passam_a_pagar_pct'], 40.0)

    def test_resumo_vazio_sem_divisoes_por_zero(self):
        Pagamento.objects.all().delete()
        UserSubscription.objects.update(plan=self.free, status='ACTIVE', trial_ends_at=None)
        self.como_admin()
        d = self.client.get(URL + 'subscricoes/resumo/').json()
        self.assertIsNone(d['cancelam_pct'])
        self.assertEqual(d['passam_a_pagar_pct'], 0.0)
        self.assertEqual(d['receita_mes_kz'], 0)
        r = self.client.get(URL + 'relatorios/').json()
        self.assertIsNone(r['receita_por_assinante_kz'])
        self.assertIsNone(r['receita_variacao_pct'])
        self.assertIsNone(r['retencao_3_meses_pct'])

    def test_lista_de_pagamentos(self):
        self.como_admin()
        d = self.client.get(URL + 'pagamentos/').json()
        self.assertEqual(d['total'], Pagamento.objects.count())
        self.assertEqual(d['paginas'], 1)
        linha = next(x for x in d['resultados'] if x['id'] == str(self.p_activa.pk))
        self.assertEqual((linha['valor_kz'], linha['desconto_kz'], linha['codigo_promocional']),
                         (14950, 4950, 'BEMVINDO'))
        self.assertEqual(linha['estado'], 'pago')
        falhou = self.client.get(URL + 'pagamentos/', {'estado': 'recusado'}).json()
        self.assertEqual([x['id'] for x in falhou['resultados']], [str(self.p_falhou.pk)])
        self.assertEqual(falhou['resultados'][0]['motivo_falha'], 'Pagamento recusado no telemóvel.')
        self.assertIsNone(falhou['resultados'][0]['pago_em'])
        q = self.client.get(URL + 'pagamentos/', {'q': 'bemvindo'}).json()
        self.assertEqual(q['total'], 1)

    def test_paginacao(self):
        u = self.aluno('Muitos Pagamentos')
        for i in range(30):
            self.falhado(u, self.premium, estado=Pagamento.CANCELADO, motivo='x', ha=timedelta(minutes=i + 1))
        self.como_admin()
        d = self.client.get(URL + 'pagamentos/', {'pagina': 2}).json()
        self.assertEqual(d['paginas'], 2)
        self.assertEqual(len(d['resultados']), d['total'] - 25)


@override_settings(PAGAMENTOS_SIMULADOS=True, PAGAMENTOS_PROVEDOR='simulado',
                   FRONTEND_URL='https://proenglish.ao')
class FalhadosTests(Base):
    def setUp(self):
        super().setUp()
        self.u = self.aluno('Filipe Falha')
        self.p1 = self.falhado(self.u, self.premium, ha=timedelta(days=2))
        self.p2 = self.falhado(self.u, self.premium, estado=Pagamento.EXPIRADO,
                               motivo='O pagamento expirou sem confirmação no telemóvel.')
        self.como_admin()

    def test_lista(self):
        d = self.client.get(URL + 'pagamentos/falhados/').json()
        self.assertEqual(d['total_em_risco_kz'], 14950)
        self.assertEqual(len(d['resultados']), 1)
        f = d['resultados'][0]
        self.assertEqual(f['id'], str(self.p2.pk))
        self.assertEqual((f['plano'], f['valor_kz'], f['pedidos']), ('Premium', 14950, 2))
        self.assertEqual(f['motivo'], 'Expirou sem confirmação')
        self.assertIsNotNone(f['falhou_a'])

    def test_motivos(self):
        p = Pagamento(estado=Pagamento.RECUSADO, motivo_falha='Saldo insuficiente na conta.')
        self.assertEqual(m.rotulo_motivo(p), 'Saldo insuficiente')
        p.motivo_falha = 'Pagamento recusado no telemóvel.'
        self.assertEqual(m.rotulo_motivo(p), 'Recusado no telemóvel')

    def test_pago_depois_sai_da_lista(self):
        self.pago(self.u, self.premium, self.agora, self.agora + timedelta(days=30))
        self.assertEqual(self.client.get(URL + 'pagamentos/falhados/').json()['resultados'], [])

    def test_novo_pedido_simulado(self):
        r = self.client.post(f'{URL}pagamentos/{self.p2.pk}/novo-pedido/')
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual(d['estado'], 'pendente')
        self.assertTrue(d['simulado'])
        self.assertEqual(d['telefone_mascarado'], '9•• ••• 000')
        novo = Pagamento.objects.get(pk=d['id'])
        self.assertEqual((novo.user_id, novo.plan_id, novo.telefone), (self.u.pk, self.premium.pk, TEL_RECUSA))
        # Com um pedido em curso, sai da lista de falhados e não se pede outro
        self.assertEqual(self.client.get(URL + 'pagamentos/falhados/').json()['resultados'], [])
        r = self.client.post(f'{URL}pagamentos/{self.p2.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'pedido_em_curso'))

    def test_novo_pedido_so_para_falhados(self):
        ok = self.pago(self.u, self.premium, self.agora, self.agora + timedelta(days=30))
        r = self.client.post(f'{URL}pagamentos/{ok.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'estado_invalido'))
        r = self.client.post(f'{URL}pagamentos/{self.p2.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'ja_pago'))
        import uuid
        self.assertEqual(self.client.post(f'{URL}pagamentos/{uuid.uuid4()}/novo-pedido/').status_code, 404)

    def test_lembrete_com_limite_diario(self):
        mail.outbox = []
        r = self.client.post(f'{URL}pagamentos/{self.p2.pk}/lembrete/')
        self.assertEqual((r.status_code, r.json()), (200, {'enviado': True}))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.u.email])
        self.assertIn('https://proenglish.ao/user/subscription', email.alternatives[0][0])
        self.assertIn('Premium', email.subject)
        r = self.client.post(f'{URL}pagamentos/{self.p2.pk}/lembrete/')
        self.assertEqual((r.status_code, r.json()['code']), (429, 'lembrete_ja_enviado'))
        self.assertGreater(r.json()['aguardar_segundos'], 0)
        self.assertEqual(len(mail.outbox), 1)
        # A falha anterior (p1) já foi substituída pela mais recente (p2): não está em aberto
        r = self.client.post(f'{URL}pagamentos/{self.p1.pk}/lembrete/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'ja_resolvido'))


class RelatoriosTests(Base):
    def setUp(self):
        super().setUp()
        self.mes = m.inicio_mes(self.agora)
        self.mes_anterior = m.somar_meses(self.mes, -1)
        a = self.agora
        self.u1 = self.aluno('Ivo Um', dias_conta=200)
        definir_assinatura(self.u1, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=10))
        self.pago(self.u1, self.premium, a - timedelta(days=20), a + timedelta(days=10),
                  pago_em=self.mes + timedelta(hours=1))  # 14 950 neste mês
        self.u2 = self.aluno('Joana Dois', dias_conta=200)
        definir_assinatura(self.u2, plan=self.plus, status='ACTIVE', expires_at=a + timedelta(days=15))
        self.pago(self.u2, self.plus, a - timedelta(days=15), a + timedelta(days=15),
                  pago_em=self.mes + timedelta(hours=2))  # 24 950 neste mês
        # Mês anterior: 10 000
        self.u3 = self.aluno('Lia Tres', dias_conta=200)
        self.pago(self.u3, self.premium, self.mes_anterior + timedelta(days=2),
                  self.mes_anterior + timedelta(days=3), pago_em=self.mes_anterior + timedelta(days=2),
                  desconto=4950)
        self.como_admin()

    def test_receita_e_variacao(self):
        r = self.client.get(URL + 'relatorios/', {'periodo': 30}).json()
        self.assertEqual(r['periodo'], 30)
        self.assertEqual(r['receita_mes_kz'], 14950 + 24950)
        self.assertEqual(r['receita_mes_anterior_kz'], 10000)
        self.assertEqual(r['receita_mes_variacao_pct'], round((39900 - 10000) * 100 / 10000, 1))
        self.assertEqual(r['assinantes_total'], 2)
        # Receita recorrente mensal: os dois pagamentos mensais que cobrem hoje
        self.assertEqual(r['receita_recorrente_mes_kz'], 39900)
        self.assertEqual(r['receita_por_assinante_kz'], round(39900 / 2))
        meses = r['receita_por_mes']
        self.assertEqual(len(meses), 3)
        self.assertEqual(meses[-1]['mes'], f'{self.mes.year}-{self.mes.month:02d}')
        self.assertEqual(meses[-1]['valor_kz'], 39900)
        self.assertEqual(meses[-2]['valor_kz'], 10000)
        self.assertEqual(meses[-1]['nome_curto'], m.NOMES_MES_CURTOS[self.mes.month - 1])
        self.assertEqual(meses[-1]['assinantes'], 2)
        self.assertEqual(len(self.client.get(URL + 'relatorios/', {'periodo': 365}).json()['receita_por_mes']), 12)
        self.assertEqual(len(self.client.get(URL + 'relatorios/', {'periodo': 180}).json()['receita_por_mes']), 6)

    def test_retencao_3_meses(self):
        a = self.agora
        inicio = a - timedelta(days=100)
        fica = self.aluno('Retido', dias_conta=200)
        for i in range(4):
            self.pago(fica, self.premium, inicio + timedelta(days=30 * i), inicio + timedelta(days=30 * (i + 1)))
        sai = self.aluno('Saiu', dias_conta=200)
        self.pago(sai, self.premium, inicio, inicio + timedelta(days=30))
        r = self.client.get(URL + 'relatorios/', {'periodo': 30}).json()
        self.assertEqual(r['retencao_3_meses_pct'], 50.0)
        self.assertEqual(r['retencao_coorte'], 2)

    def test_teste_para_pago(self):
        a = self.agora
        converteu = self.aluno('Converteu')
        definir_assinatura(converteu, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=20),
                           trial_ends_at=a - timedelta(days=10))
        self.pago(converteu, self.premium, a - timedelta(days=10), a + timedelta(days=20),
                  pago_em=a - timedelta(days=12))
        nao = self.aluno('Nao Converteu')
        definir_assinatura(nao, plan=self.free, status='ACTIVE', expires_at=a + timedelta(days=3000),
                           trial_ends_at=a - timedelta(days=5))
        antigo = self.aluno('Antigo')  # teste terminou fora do período
        definir_assinatura(antigo, plan=self.free, status='ACTIVE', expires_at=a + timedelta(days=3000),
                           trial_ends_at=a - timedelta(days=60))
        r = self.client.get(URL + 'relatorios/', {'periodo': 30}).json()
        self.assertEqual((r['teste_para_pago_pct'], r['testes_terminados']), (50.0, 2))
        r = self.client.get(URL + 'relatorios/', {'periodo': 90}).json()
        self.assertEqual(r['testes_terminados'], 3)

    def test_provincias(self):
        if not tem_provincia():
            self.skipTest('User.provincia ainda não existe')
        User.objects.filter(pk=self.u1.pk).update(provincia='luanda')
        r = self.client.get(URL + 'relatorios/').json()
        self.assertEqual(r['por_provincia'], [{'provincia': 'luanda', 'nome': 'Luanda', 'assinantes': 1}])
        self.assertEqual(r['sem_provincia'], 1)

    def test_csv(self):
        r = self.client.get(URL + 'relatorios/exportar/', {'periodo': 90})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment;', r['Content-Disposition'])
        bruto = r.content
        self.assertTrue(bruto.startswith('﻿'.encode('utf-8')))
        texto = bruto.decode('utf-8-sig')
        self.assertIn('Mês;Receita (Kz);Assinantes pagos', texto)
        self.assertIn('Receita deste mês (Kz);39900', texto)
        self.assertIn('Província;Assinantes pagos', texto)
        self.assertIn('Sem província indicada;2', texto)
        self.assertEqual(self.client.get(URL + 'relatorios/exportar/', {'periodo': 'x'}).status_code, 400)

    def test_csv_sem_formulas(self):
        if tem_provincia():
            User.objects.filter(pk=self.u1.pk).update(provincia='=HYPERLINK("x")')
            texto = self.client.get(URL + 'relatorios/exportar/').content.decode('utf-8-sig')
            self.assertNotIn('\n=', texto)
            self.assertIn("'=Hyperlink", texto)


class CelulaTests(SimpleTestCase):
    def test_celula(self):
        for perigoso in ['=1+1', '+1', '-A1', '-2+3', '@SUM(A1)', '\tx', '\rx']:
            self.assertTrue(celula(perigoso).startswith("'"), perigoso)
        # Números (incluindo negativos em texto pt-PT) continuam numéricos
        self.assertEqual(celula('-12,5'), '-12,5')
        self.assertEqual(celula('-2'), '-2')
        self.assertEqual(celula('Luanda'), 'Luanda')
        self.assertEqual(celula(-5), -5)  # números não levam apóstrofo
        self.assertEqual(celula(None), '')


# ---------------------------------------------------------------------------
# Correcções: definições partilhadas Painel/Subscrições, lembrete, novo pedido, relatórios, ganhos
# ---------------------------------------------------------------------------

class DefinicoesPartilhadasTests(Base):
    """Painel e Subscrições contam o mesmo: pagos (> 0 Kz), em teste, atribuídos, a terminar, falhados."""

    def setUp(self):
        super().setUp()
        a = self.agora
        # Pago, termina daqui a 2 dias
        self.u_pago = self.aluno('Pago Breve')
        definir_assinatura(self.u_pago, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=2))
        self.pago(self.u_pago, self.premium, a - timedelta(days=28), a + timedelta(days=2))
        # Pago, termina daqui a 6 dias (a expirar, mas não em 3 dias)
        self.u_seis = self.aluno('Pago Seis')
        definir_assinatura(self.u_seis, plan=self.plus, status='ACTIVE', expires_at=a + timedelta(days=6))
        self.pago(self.u_seis, self.plus, a - timedelta(days=24), a + timedelta(days=6))
        # Código de 100 %: 0 Kz, não é "pago" (atribuído); termina em 2 dias mas não conta
        self.u_promo = self.aluno('Promo Cem')
        definir_assinatura(self.u_promo, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=2))
        self.pago(self.u_promo, self.premium, a - timedelta(days=28), a + timedelta(days=2),
                  desconto=14950, codigo='CEM')
        # Plano dado pela administração, sem pagamento
        self.u_dado = self.aluno('Plano Dado')
        definir_assinatura(self.u_dado, plan=self.plus, status='ACTIVE', expires_at=a + timedelta(days=1))
        # Em teste, termina em 2 dias: não conta em "terminam"
        self.u_teste = self.aluno('Em Teste')
        definir_assinatura(self.u_teste, plan=self.premium, status='TRIAL', expires_at=a + timedelta(days=2),
                           trial_ends_at=a + timedelta(days=2))
        # Falhados: expirado há 2 dias (conta), recusado há 10 dias (em aberto, fora da semana),
        # recusado seguido de pagamento (resolvido)
        self.u_exp = self.aluno('Expirou')
        self.falhado(self.u_exp, self.premium, estado=Pagamento.EXPIRADO, motivo='Expirou.', ha=timedelta(days=2))
        self.u_antigo = self.aluno('Antigo')
        self.falhado(self.u_antigo, self.premium, ha=timedelta(days=10))
        self.u_resolvido = self.aluno('Resolvido')
        self.falhado(self.u_resolvido, self.premium, ha=timedelta(days=1))
        definir_assinatura(self.u_resolvido, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=29))
        self.pago(self.u_resolvido, self.premium, a - timedelta(hours=1), a + timedelta(days=29))
        self.como_admin()

    def test_mesmos_numeros_no_painel_e_no_resumo(self):
        resumo = self.client.get(URL + 'subscricoes/resumo/').json()
        painel = self.client.get(URL + 'painel/').json()
        lista = self.client.get(URL + 'subscricoes/').json()
        self.assertEqual(resumo['assinantes_pagos'], 3)  # pago breve, pago seis, resolvido
        self.assertEqual(painel['numeros']['assinantes_pagos'], 3)
        self.assertEqual(lista['pagas'], 3)
        self.assertEqual(lista['em_teste'], resumo['em_teste'])
        self.assertEqual(resumo['por_plano'], painel['por_plano'])
        planos = {x['plano']: x for x in resumo['por_plano']}
        self.assertEqual(planos['PREMIUM'], {'plano': 'PREMIUM', 'nome': 'Premium', 'utilizadores': 4,
                                             'pagos': 2, 'em_teste': 1, 'atribuidos': 1})
        self.assertEqual(planos['PREMIUM_PLUS'], {'plano': 'PREMIUM_PLUS', 'nome': 'Premium Plus',
                                                  'utilizadores': 2, 'pagos': 1, 'em_teste': 0,
                                                  'atribuidos': 1})
        self.assertEqual(planos['FREE']['utilizadores'], 2)  # expirou, antigo

        self.assertEqual(resumo['atencao']['terminam_3_dias'], 1)
        self.assertEqual(painel['atencao']['terminam_3_dias'], 1)
        self.assertEqual(resumo['atencao']['falhados_semana'], 1)
        self.assertEqual(painel['atencao']['pagamentos_falhados_semana'], 1)

        por_email = {x['utilizador']['email']: x for x in lista['resultados']}
        self.assertEqual(por_email[self.u_dado.email]['nota'], 'Plano atribuído sem pagamento')
        self.assertEqual(por_email[self.u_promo.email]['nota'], 'Plano atribuído sem pagamento')

    def test_lista_a_expirar_com_dias_igual_ao_resumo(self):
        r = self.client.get(URL + 'subscricoes/', {'estado': 'a_expirar', 'dias': 3}).json()
        self.assertEqual([x['utilizador']['email'] for x in r['resultados']], [self.u_pago.email])
        self.assertEqual(r['total'], self.client.get(URL + 'subscricoes/resumo/').json()['atencao']['terminam_3_dias'])
        todos = self.client.get(URL + 'subscricoes/', {'estado': 'a_expirar'}).json()
        self.assertIn(self.u_seis.email, [x['utilizador']['email'] for x in todos['resultados']])
        for params in ({'estado': 'a_expirar', 'dias': 'x'}, {'estado': 'a_expirar', 'dias': 0},
                       {'estado': 'activas', 'dias': 3}):
            e = self.client.get(URL + 'subscricoes/', params)
            self.assertEqual((e.status_code, e.json()['code']), (400, 'dias_invalido'), params)
            self.assertIsInstance(e.json()['details']['dias'], list)

    def test_pendente_sai_dos_que_terminam(self):
        Pagamento.objects.create(user=self.u_pago, plan=self.premium, periodo='mensal', valor_kz=14950,
                                 telefone=TEL_PENDENTE, provedor='simulado')
        self.assertEqual(self.client.get(URL + 'painel/').json()['atencao']['terminam_3_dias'], 0)

    def test_janela_dos_falhados(self):
        d = self.client.get(URL + 'pagamentos/falhados/').json()
        self.assertEqual(d['janela_dias'], 30)
        self.assertEqual({x['utilizador']['email'] for x in d['resultados']},
                         {self.u_exp.email, self.u_antigo.email})

    def test_motivo_sem_cartao(self):
        p = Pagamento(estado=Pagamento.RECUSADO, motivo_falha='Limite diário excedido.')
        self.assertNotIn('cartão', m.rotulo_motivo(p).lower())
        self.assertIn('Multicaixa', m.rotulo_motivo(p))

    def test_cancelou_so_quando_cancelou(self):
        definir_assinatura(self.u_seis, plan=self.plus, status='CANCELED', expires_at=self.agora + timedelta(days=6),
                           lembretes_renovacao=True)
        por_email = {x['utilizador']['email']: x for x in
                     self.client.get(URL + 'subscricoes/').json()['resultados']}
        self.assertEqual(por_email[self.u_seis.email]['nota'], 'Cancelou a renovação')
        self.assertEqual(por_email[self.u_teste.email]['periodo'], 'teste')


@override_settings(PAGAMENTOS_SIMULADOS=True, PAGAMENTOS_PROVEDOR='simulado',
                   FRONTEND_URL='https://proenglish.ao')
class LembreteENovoPedidoTests(Base):
    def setUp(self):
        super().setUp()
        self.u = self.aluno('Filipe Falha')
        self.p = self.falhado(self.u, self.premium)
        self.como_admin()

    def _texto_email(self):
        return mail.outbox[-1].alternatives[0][0]

    def test_lembrete_no_gratuito_nao_fala_em_manter_acesso(self):
        mail.outbox = []
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/lembrete/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('manter o acesso', self._texto_email())
        self.assertIn('activar o plano Premium', self._texto_email())
        from apps.users.models import Notification
        aviso = Notification.objects.filter(user=self.u).latest('created_at')
        self.assertNotIn('manter o acesso', aviso.body)

    def test_lembrete_na_renovacao_fala_em_manter_acesso(self):
        definir_assinatura(self.u, plan=self.premium, status='ACTIVE', expires_at=self.agora + timedelta(days=2))
        self.pago(self.u, self.premium, self.agora - timedelta(days=28), self.agora + timedelta(days=2),
                  pago_em=self.agora - timedelta(days=28))
        mail.outbox = []
        self.assertEqual(self.client.post(f'{URL}pagamentos/{self.p.pk}/lembrete/').status_code, 200)
        self.assertIn('manter o acesso', self._texto_email())

    def test_lembrete_falha_resolvida(self):
        self.pago(self.u, self.premium, self.agora, self.agora + timedelta(days=30))
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/lembrete/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'ja_resolvido'))
        self.assertEqual(set(r.json()), {'error', 'message', 'code', 'details'})

    def test_novo_pedido_conta_suspensa(self):
        User.objects.filter(pk=self.u.pk).update(is_active=False)
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'utilizador_inactivo'))
        self.assertFalse(Pagamento.objects.filter(user=self.u, estado='pendente').exists())

    def test_novo_pedido_falha_antiga_ou_substituida(self):
        antigo = self.aluno('Antigo')
        p_antigo = self.falhado(antigo, self.premium, ha=timedelta(days=31))
        r = self.client.post(f'{URL}pagamentos/{p_antigo.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'ja_resolvido'))
        mais_recente = self.falhado(self.u, self.premium, ha=timedelta(minutes=5))
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'ja_resolvido'))
        self.assertEqual(self.client.post(f'{URL}pagamentos/{mais_recente.pk}/novo-pedido/').status_code, 201)

    def test_novo_pedido_limite_de_10_minutos(self):
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.json()['aviso'])
        Pagamento.objects.filter(pk=r.json()['id']).update(estado=Pagamento.RECUSADO)
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
        self.assertEqual((r.status_code, r.json()['code']), (429, 'novo_pedido_recente'))
        self.assertGreater(r.json()['aguardar_segundos'], 0)

    def test_novo_pedido_codigo_ja_invalido(self):
        p = self.falhado(self.u, self.premium, ha=timedelta(minutes=1))
        Pagamento.objects.filter(pk=p.pk).update(codigo_promocional='JAFOI', desconto_kz=4950)
        r = self.client.post(f'{URL}pagamentos/{p.pk}/novo-pedido/')
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertIn('JAFOI', d['aviso'])
        self.assertEqual((d['desconto_kz'], d['total_kz']), (0, 14950))

    def test_novo_pedido_plano_indisponivel(self):
        type(self.premium).objects.filter(pk=self.premium.pk).update(is_active=False)
        r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
        if r.status_code == 201:  # planos desactivados renováveis por quem os tem
            self.assertIn('já não está à venda', r.json()['aviso'])
        else:
            self.assertEqual((r.status_code, r.json()['code']), (409, 'plano_indisponivel'))
            # Pode tentar outra vez (o limite de 10 min não fica gasto)
            r = self.client.post(f'{URL}pagamentos/{self.p.pk}/novo-pedido/')
            self.assertEqual(r.json()['code'], 'plano_indisponivel')


class RelatorioPeriodoTests(Base):
    def setUp(self):
        super().setUp()
        a = self.agora
        # Anual a cobrir hoje: 249 500 / 12 por mês
        self.u1 = self.aluno('Anual', dias_conta=400)
        definir_assinatura(self.u1, plan=self.plus, status='ACTIVE', expires_at=a + timedelta(days=300))
        self.pago(self.u1, self.plus, a - timedelta(days=65), a + timedelta(days=300),
                  pago_em=a - timedelta(days=65), periodo='anual')
        # Mensal pago há 10 dias
        self.u2 = self.aluno('Mensal', dias_conta=400)
        definir_assinatura(self.u2, plan=self.premium, status='ACTIVE', expires_at=a + timedelta(days=20))
        self.pago(self.u2, self.premium, a - timedelta(days=10), a + timedelta(days=20),
                  pago_em=a - timedelta(days=10))
        self.como_admin()

    def test_receita_recorrente_e_periodo(self):
        r30 = self.client.get(URL + 'relatorios/', {'periodo': 30}).json()
        self.assertEqual(r30['receita_recorrente_mes_kz'], round(249500 / 12 + 14950))
        self.assertEqual(r30['receita_por_assinante_kz'], round(round(249500 / 12 + 14950) / 2))
        self.assertEqual(r30['periodo_receita_kz'], 14950)
        self.assertEqual(r30['periodo_anterior_receita_kz'], 0)
        self.assertIsNone(r30['receita_variacao_pct'])
        r90 = self.client.get(URL + 'relatorios/', {'periodo': 90}).json()
        self.assertEqual(r90['periodo_receita_kz'], 14950 + 249500)
        self.assertEqual(len(r30['receita_por_mes']), 3)
        self.assertEqual(len(r90['receita_por_mes']), 3)
        self.assertEqual(len(self.client.get(URL + 'relatorios/', {'periodo': 180}).json()['receita_por_mes']), 6)
        self.assertIn('receita_mes_kz', r30)

    def test_csv_variacao_negativa_fica_numerica(self):
        # Os 30 dias anteriores tiveram mais receita: variação negativa
        u3 = self.aluno('Antes', dias_conta=400)
        self.pago(u3, self.plus, self.agora - timedelta(days=45), self.agora - timedelta(days=15),
                  pago_em=self.agora - timedelta(days=45))
        r = self.client.get(URL + 'relatorios/', {'periodo': 30}).json()
        self.assertLess(r['receita_variacao_pct'], 0)
        texto = self.client.get(URL + 'relatorios/exportar/', {'periodo': 30}).content.decode('utf-8-sig')
        linha = next(l for l in texto.splitlines() if l.startswith('Variação face ao período anterior'))
        self.assertTrue(linha.split(';')[1].startswith('-'), linha)
        self.assertNotIn("'", linha)
        self.assertIn('Receita recorrente mensal por assinante (Kz)', texto)


class GanhosAdminTests(Base):
    def setUp(self):
        super().setUp()
        from datetime import date
        from apps.pagamentos import ganhos
        from apps.pagamentos.models import ContaRecebimento, GanhoMensal
        self.ganhos = ganhos
        self.prof = User.objects.create_user(email='prof@example.com', name='Prof Ana',
                                             password='x' * 12, role='teacher')
        self.mes = ganhos.mes_anterior(ganhos.hoje())
        self.g = GanhoMensal.objects.create(professor=self.prof, mes=self.mes, valor_kz=5000,
                                            quota='0.250000', segundos=600, alunos_pagantes=2)
        self.iban = 'AO06004000001234567890123'
        ContaRecebimento.objects.create(professor=self.prof, banco='bfa', iban=self.iban, titular='Ana',
                                        confirmada_em=timezone.now())
        self.date = date
        self.como_admin()

    def test_mes_limitado(self):
        hoje = self.ganhos.hoje()
        for mes in ('2019-12', f'{hoje:%Y-%m}', '2099-01', '2026-13', 'x'):
            r = self.client.get(URL + 'ganhos/', {'mes': mes})
            self.assertEqual((r.status_code, r.json()['code']), (400, 'mes_invalido'), mes)
        self.assertEqual(self.client.get(URL + 'ganhos/', {'mes': '2020-01'}).status_code, 200)
        r = self.client.get(URL + 'ganhos/', {'mes': f'{self.mes:%Y-%m}'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['linhas'][0]['quota'], 0.25)

    def test_marcar_pago_regista_e_aviso_nao_parte(self):
        from unittest import mock
        from apps.pagamentos.models import RegistoContaRecebimento
        from apps.users.models import Notification
        with mock.patch.object(Notification, 'notify', side_effect=RuntimeError('x')):
            r = self.client.post(f'{URL}ganhos/{self.g.pk}/pago/', {'referencia': 'TRF-9'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['estado'], 'pago')
        reg = RegistoContaRecebimento.objects.get(accao='pago')
        self.assertEqual((reg.professor_id, reg.autor_id, reg.ganho_id, reg.banco, reg.terminada_em),
                         (self.prof.pk, self.admin.pk, self.g.pk, 'bfa', self.iban[-4:]))

    def test_fecho_nao_cria_linhas_de_zero(self):
        from unittest import mock
        from apps.pagamentos.ganhos import Calculo, TempoProfessor
        from apps.pagamentos.models import GanhoMensal
        outro = User.objects.create_user(email='prof2@example.com', name='Prof Rui', password='x' * 12,
                                         role='teacher')
        mes = self.ganhos.mes_anterior(self.mes)
        GanhoMensal.objects.create(professor=outro, mes=mes, valor_kz=3)  # antigo, passa a 0 Kz
        calc = Calculo(mes=mes, receita_kz=10, bolo_kz=3,
                       professores={self.prof.pk: TempoProfessor(100, {1}), outro.pk: TempoProfessor(1, {2})},
                       valores={self.prof.pk: 3, outro.pk: 0}, quotas={self.prof.pk: 1, outro.pk: 0})
        with mock.patch.object(self.ganhos, 'calcular', return_value=calc):
            res = self.ganhos.fechar_mes(mes, notificar=False)
        self.assertEqual(list(GanhoMensal.objects.filter(mes=mes).values_list('professor_id', flat=True)),
                         [self.prof.pk])
        self.assertEqual((res.criados, res.removidos), (1, 1))
