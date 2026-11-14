"""Administração de utilizadores: permissões, painel, lista, detalhe, PATCH, suspensão, sessões,
mudança de palavra-passe obrigatória, email a vários e registo das acções."""
import json
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.pagamentos.models import Pagamento
from apps.subscriptions.models import SubscriptionHistory, SubscriptionPlan, UserSubscription
from apps.users.models import (EmailVerification, PerfilProfessor, RegistoAdmin, SuspensaoConta, User)

BASE = '/api/v1/admin/'
SENHA = 'Segura!2026x'


def plano(tipo, preco):
    p, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=tipo, defaults={'name': {'FREE': 'Gratuito', 'PREMIUM': 'Premium',
                                           'PREMIUM_PLUS': 'Premium Plus'}[tipo],
                                  'description': tipo, 'monthly_price': Decimal(preco)})
    return p


def criar(email, role='student', verified=True, **extra):
    u = User.objects.create_user(email=email, name=extra.pop('name', 'Ana Maria Costa'), password=SENHA, role=role)
    u.email_verified = verified
    for k, v in extra.items():
        setattr(u, k, v)
    u.save()
    return u


def dar_plano(user, tipo, dias=10):
    sub = UserSubscription.objects.get(user=user)
    sub.plan = plano(tipo, '5000' if tipo == 'PREMIUM' else '9000')
    sub.expires_at = timezone.now() + timedelta(days=dias)
    sub.status = 'ACTIVE'
    sub.save()
    return sub


def cliente_com_token(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        plano('FREE', '0'), plano('PREMIUM', '5000'), plano('PREMIUM_PLUS', '9000')
        self.admin = criar('admin@pe.ao', role='admin', name='Admin Geral')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)


class PermissoesTests(Base):
    ROTAS = ['painel/', 'utilizadores/', 'convites/', 'opinioes/', 'testemunhos/']

    def test_so_administradores(self):
        aluno = criar('a@pe.ao')
        prof = criar('p@pe.ao', role='teacher')
        staff = criar('s@pe.ao', is_staff=True)
        for u in (aluno, prof, staff):
            c = APIClient()
            c.force_authenticate(u)
            for rota in self.ROTAS + [f'utilizadores/{aluno.id}/']:
                with self.subTest(u=u.email, rota=rota):
                    self.assertEqual(c.get(BASE + rota).status_code, 403)
            r = c.post(BASE + f'utilizadores/{aluno.id}/suspender/', {'motivo': 'outro'}, format='json')
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()['code'], 'permission_denied')
        self.assertEqual(APIClient().get(BASE + 'painel/').status_code, 401)

    def test_admin_inactivo_nao_entra(self):
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(self.c.get(BASE + 'painel/').status_code, 403)

    def test_rotas_antigas_410(self):
        r = self.c.get(BASE + 'dashboard/')
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.json()['substituida_por'], '/api/v1/admin/painel/')
        aluno = criar('a@pe.ao')
        c = APIClient()
        c.force_authenticate(aluno)
        self.assertEqual(c.get(BASE + 'stats/').status_code, 403)


class PainelListaTests(Base):
    def setUp(self):
        super().setUp()
        self.verificado = criar('v@pe.ao', phone='+244923111222')
        self.por_verificar = criar('nv@pe.ao', verified=False)
        User.objects.filter(pk=self.por_verificar.pk).update(date_joined=timezone.now() - timedelta(days=4))
        self.suspenso = criar('sus@pe.ao', is_active=False)
        self.prof = criar('prof@pe.ao', role='teacher')
        self.premium = criar('prem@pe.ao')
        dar_plano(self.premium, 'PREMIUM')
        Pagamento.objects.create(user=self.premium, plan=plano('PREMIUM', '5000'), periodo='mensal',
                                 valor_kz=5000, desconto_kz=500, telefone='923456789', provedor='simulado',
                                 estado=Pagamento.PAGO, pago_em=timezone.now(), periodo_inicio=timezone.now(),
                                 periodo_fim=timezone.now() + timedelta(days=10))
        Pagamento.objects.create(user=self.verificado, plan=plano('PREMIUM', '5000'), periodo='mensal',
                                 valor_kz=5000, telefone='923456789', provedor='simulado',
                                 estado=Pagamento.RECUSADO)

    def test_painel(self):
        r = self.c.get(BASE + 'painel/')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        n = d['numeros']
        self.assertEqual(n['utilizadores'], 6)
        self.assertEqual(n['estudantes'], 4)
        self.assertEqual(n['professores'], 1)
        self.assertEqual(n['pagantes'], 1)
        self.assertEqual(n['assinantes_pagos'], 1)
        self.assertEqual(n['email_por_verificar'], 1)
        self.assertEqual(n['email_por_verificar_3d'], 1)
        self.assertEqual(n['receita_mes_kz'], 4500)
        self.assertEqual(d['atencao']['pagamentos_falhados_semana'], 1)
        self.assertEqual(d['atencao']['terminam_3_dias'], 0)
        self.assertEqual({p['plano']: p['utilizadores'] for p in d['por_plano']},
                         {'FREE': 3, 'PREMIUM': 1, 'PREMIUM_PLUS': 0})
        self.assertEqual(len(d['recentes']), 6)
        self.assertEqual(set(d['recentes'][0]), {'id', 'nome', 'email', 'papel', 'criado_em'})

    def test_terminam_3_dias(self):
        dar_plano(self.premium, 'PREMIUM', dias=2)
        self.assertEqual(self.c.get(BASE + 'painel/').json()['atencao']['terminam_3_dias'], 1)
        Pagamento.objects.create(user=self.premium, plan=plano('PREMIUM', '5000'), periodo='mensal',
                                 valor_kz=5000, telefone='923456789', provedor='simulado')
        self.assertEqual(self.c.get(BASE + 'painel/').json()['atencao']['terminam_3_dias'], 0)

    def test_lista_e_filtros(self):
        r = self.c.get(BASE + 'utilizadores/')
        d = r.json()
        self.assertEqual(d['total'], 6)
        self.assertEqual(d['paginas'], 1)
        self.assertEqual(d['numeros']['professores'], 1)
        item = next(x for x in d['resultados'] if x['email'] == 'prem@pe.ao')
        self.assertEqual(item['plano'], 'Premium')
        self.assertEqual(item['iniciais'], 'AM')
        self.assertIsNone(next(x for x in d['resultados'] if x['email'] == 'prof@pe.ao')['plano'])

        def emails(qs):
            return {x['email'] for x in self.c.get(BASE + 'utilizadores/' + qs).json()['resultados']}
        self.assertEqual(emails('?estado=suspenso'), {'sus@pe.ao'})
        self.assertEqual(emails('?estado=email_por_verificar'), {'nv@pe.ao'})
        self.assertEqual(emails('?papel=teacher'), {'prof@pe.ao'})
        self.assertEqual(emails('?plano=PREMIUM'), {'prem@pe.ao'})
        self.assertEqual(emails('?plano=FREE'), {'v@pe.ao', 'nv@pe.ao', 'sus@pe.ao'})
        self.assertEqual(emails('?q=923111'), {'v@pe.ao'})
        self.assertEqual(emails('?q=PREM@'), {'prem@pe.ao'})
        r = self.c.get(BASE + 'utilizadores/?estado=x')
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(r.json()['details']['estado'], list)

    def test_paginacao(self):
        for i in range(25):
            criar(f'extra{i}@pe.ao')
        d = self.c.get(BASE + 'utilizadores/?pagina=2').json()
        self.assertEqual((d['total'], d['paginas'], len(d['resultados'])), (31, 2, 6))


class DetalheTests(Base):
    def test_forma_e_sem_segredos(self):
        aluno = criar('al@pe.ao', provincia='huila', preferences={'area': 'Industry English', 'cidade': 'Lubango'})
        Pagamento.objects.create(user=aluno, plan=plano('PREMIUM', '5000'), periodo='mensal', valor_kz=5000,
                                 telefone='923456789', provedor='simulado', estado=Pagamento.RECUSADO)
        r = self.c.get(BASE + f'utilizadores/{aluno.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(set(d), {'utilizador', 'numeros', 'actividade', 'pagamentos', 'professor'})
        u = d['utilizador']
        for k in ('id', 'nome', 'email', 'telefone', 'papel', 'provincia', 'profissao', 'cidade', 'plano', 'estado',
                  'suspensao', 'email_verificado', 'verificado_em', 'entra_com_google', 'tem_senha', 'criado_em',
                  'ultima_entrada'):
            self.assertIn(k, u)
        self.assertEqual((u['provincia'], u['profissao'], u['cidade']), ('huila', 'Petróleo e Gás', 'Lubango'))
        self.assertEqual(u['plano']['tipo'], 'FREE')
        self.assertEqual(set(d['numeros']), {'cursos', 'concluidos', 'pontos', 'dias_seguidos'})
        self.assertEqual(d['pagamentos'][0]['estado'], 'falhou')
        self.assertTrue(any(a['texto'] == 'Criou a conta.' for a in d['actividade']))
        self.assertIsNone(d['professor'])
        texto = json.dumps(d)
        self.assertNotIn('md5$', texto)
        self.assertNotIn(aluno.password, texto)

    def test_professor_e_404(self):
        prof = criar('pr@pe.ao', role='teacher')
        PerfilProfessor.objects.create(user=prof, publica_sem_revisao=True)
        d = self.c.get(BASE + f'utilizadores/{prof.id}/').json()
        self.assertEqual(d['professor'], {'cursos_publicados': 0, 'alunos': 0, 'publica_sem_revisao': True})
        self.assertIsNone(d['utilizador']['plano'])
        import uuid
        self.assertEqual(self.c.get(BASE + f'utilizadores/{uuid.uuid4()}/').status_code, 404)


class PatchTests(Base):
    def setUp(self):
        super().setUp()
        self.aluno = criar('al@pe.ao')

    def patch(self, user, dados, c=None):
        return (c or self.c).patch(BASE + f'utilizadores/{user.id}/', dados, format='json')

    def test_proprio_papel_403(self):
        r = self.patch(self.admin, {'papel': 'student'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'propria_conta')

    def test_papel_de_admin_so_superutilizador(self):
        outro = criar('ad2@pe.ao', role='admin')
        self.assertEqual(self.patch(outro, {'papel': 'student'}).status_code, 403)
        self.assertEqual(self.patch(self.aluno, {'papel': 'admin'}).status_code, 403)
        sup = criar('root@pe.ao', role='admin', is_superuser=True)
        c = APIClient()
        c.force_authenticate(sup)
        self.assertEqual(self.patch(outro, {'papel': 'student'}, c).status_code, 200)

    def test_email_novo_volta_a_confirmar(self):
        mail.outbox.clear()
        r = self.patch(self.aluno, {'email': 'Novo@PE.ao', 'nome': 'Ana Nova'})
        self.assertEqual(r.status_code, 200, r.content)
        self.aluno.refresh_from_db()
        # O email só muda depois de confirmado: fica pendente, o actual continua a valer.
        self.assertEqual((self.aluno.email, self.aluno.email_verified, self.aluno.name, self.aluno.email_pendente),
                         ('al@pe.ao', True, 'Ana Nova', 'novo@pe.ao'))
        self.assertTrue(EmailVerification.objects.filter(
            user=self.aluno, email='novo@pe.ao', finalidade=EmailVerification.FINALIDADE_MUDAR_EMAIL).exists())
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['al@pe.ao', 'novo@pe.ao'])
        self.assertEqual(r.json()['utilizador']['email_pendente'], 'novo@pe.ao')
        self.assertEqual(r.json()['utilizador']['estado'], 'activo')
        criar('ocupado@pe.ao')
        r = self.patch(self.aluno, {'email': 'ocupado@pe.ao'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['details']['email'], ['Já existe outra conta com este email.'])

    def test_mudar_papel_termina_sessoes(self):
        refresh = RefreshToken.for_user(self.aluno)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.assertEqual(c.get('/api/v1/users/profile/').status_code, 200)
        import time
        time.sleep(1.05)  # o corte é ao segundo (iat)
        r = self.patch(self.aluno, {'papel': 'teacher', 'publica_sem_revisao': True})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists())
        r = c.get('/api/v1/users/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'token_not_valid')
        self.assertTrue(PerfilProfessor.objects.get(user=self.aluno).publica_sem_revisao)
        self.assertEqual(cliente_com_token(self.aluno).get('/api/v1/users/profile/').status_code, 200)

    def test_plano_gratis_30_dias(self):
        r = self.patch(self.aluno, {'plano': 'PREMIUM'})
        self.assertEqual(r.status_code, 200, r.content)
        sub = UserSubscription.objects.get(user=self.aluno)
        self.assertEqual(sub.plan.plan_type, 'PREMIUM')
        self.assertAlmostEqual((sub.expires_at - timezone.now()).days, 29, delta=1)
        h = SubscriptionHistory.objects.filter(subscription=sub).first()
        self.assertIsNone(h.amount_paid)
        self.assertIn('sem pagamento', h.notes)
        self.assertEqual(r.json()['utilizador']['plano']['tipo'], 'PREMIUM')

    def test_plano_mantem_o_fim(self):
        sub = dar_plano(self.aluno, 'PREMIUM', dias=12)
        fim = sub.expires_at
        self.patch(self.aluno, {'plano': 'PREMIUM_PLUS'})
        sub.refresh_from_db()
        self.assertEqual((sub.plan.plan_type, sub.expires_at), ('PREMIUM_PLUS', fim))
        self.patch(self.aluno, {'plano': 'FREE'})
        sub.refresh_from_db()
        self.assertEqual(sub.plan.plan_type, 'FREE')
        self.assertIsNotNone(sub.canceled_at)
        self.assertEqual(self.c.get(BASE + f'utilizadores/{self.aluno.id}/').json()['utilizador']['plano']['tipo'], 'FREE')

    def test_validacoes(self):
        prof = criar('pp@pe.ao', role='teacher')
        r = self.patch(prof, {'plano': 'PREMIUM'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['details']['plano'], ['Só os estudantes têm plano.'])
        self.assertEqual(self.patch(self.aluno, {'publica_sem_revisao': True}).status_code, 400)
        r = self.patch(self.aluno, {'provincia': 'atlantida', 'password': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.json()['details'])
        r = self.patch(self.aluno, {'provincia': 'icolo-e-bengo', 'telefone': '923 456 789'})
        self.assertEqual(r.status_code, 200, r.content)
        self.aluno.refresh_from_db()
        self.assertEqual((self.aluno.provincia, self.aluno.phone), ('icolo-e-bengo', '+244923456789'))

    def test_registo(self):
        self.patch(self.aluno, {'nome': 'Outro Nome', 'plano': 'PREMIUM'})
        accoes = set(RegistoAdmin.objects.filter(alvo_id=str(self.aluno.id)).values_list('accao', flat=True))
        self.assertEqual(accoes, {'editar_utilizador', 'atribuir_plano'})
        reg = RegistoAdmin.objects.get(accao='editar_utilizador')
        self.assertEqual(reg.autor, self.admin)
        self.assertEqual(reg.detalhes['alterado']['nome'], ['Ana Maria Costa', 'Outro Nome'])


class SuspensaoTests(Base):
    def setUp(self):
        super().setUp()
        self.aluno = criar('al@pe.ao')

    def test_suspender_e_reactivar(self):
        sub = dar_plano(self.aluno, 'PREMIUM', dias=10)
        refresh = RefreshToken.for_user(self.aluno)
        mail.outbox.clear()
        r = self.c.post(BASE + f'utilizadores/{self.aluno.id}/suspender/',
                        {'motivo': 'partilha_conta', 'nota': 'Três dispositivos.', 'avisar': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['utilizador']
        self.assertEqual(d['estado'], 'suspenso')
        self.assertEqual(d['suspensao']['motivo'], 'partilha_conta')
        self.assertEqual(d['suspensao']['por'], 'Admin Geral')
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.is_active)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists())
        s = SuspensaoConta.objects.get(user=self.aluno)
        self.assertEqual(s.plano_pausado, 'PREMIUM')
        self.assertTrue(s.avisado)
        self.assertIn('Partilha de conta', mail.outbox[-1].body)
        self.assertEqual(self.c.post(BASE + f'utilizadores/{self.aluno.id}/suspender/', {'motivo': 'outro'},
                                     format='json').status_code, 409)
        # Passam 5 dias suspenso: ao reactivar, o plano dura o que faltava (~10 dias).
        SuspensaoConta.objects.filter(pk=s.pk).update(desde=timezone.now() - timedelta(days=5))
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=timezone.now() + timedelta(days=5))
        r = self.c.post(BASE + f'utilizadores/{self.aluno.id}/reactivar/')
        self.assertEqual(r.status_code, 200, r.content)
        sub.refresh_from_db()
        self.assertAlmostEqual((sub.expires_at - timezone.now()).total_seconds(), 10 * 86400, delta=120)
        self.aluno.refresh_from_db()
        self.assertTrue(self.aluno.is_active)
        self.assertEqual(self.c.post(BASE + f'utilizadores/{self.aluno.id}/reactivar/').status_code, 409)
        self.assertEqual(list(RegistoAdmin.objects.filter(alvo_id=str(self.aluno.id))
                              .order_by('criado_em').values_list('accao', flat=True)), ['suspender', 'reactivar'])

    def test_validacao_e_limites(self):
        r = self.c.post(BASE + f'utilizadores/{self.aluno.id}/suspender/', {'motivo': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(r.json()['details']['motivo'], list)
        self.assertEqual(self.c.post(BASE + f'utilizadores/{self.admin.id}/suspender/', {'motivo': 'outro'},
                                     format='json').status_code, 403)
        outro = criar('ad2@pe.ao', role='admin')
        r = self.c.post(BASE + f'utilizadores/{outro.id}/suspender/', {'motivo': 'outro'}, format='json')
        self.assertEqual(r.json()['code'], 'alvo_administrador')
        sup = criar('root@pe.ao', role='admin', is_superuser=True)
        c = APIClient()
        c.force_authenticate(sup)
        self.assertEqual(c.post(BASE + f'utilizadores/{outro.id}/suspender/', {'motivo': 'outro'},
                                format='json').status_code, 200)

    def test_terminar_sessoes(self):
        refresh = RefreshToken.for_user(self.aluno)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        import time
        time.sleep(1.05)
        r = self.c.post(BASE + f'utilizadores/{self.aluno.id}/terminar-sessoes/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['sessoes_terminadas'], 1)
        self.assertEqual(c.get('/api/v1/users/profile/').status_code, 401)
        r = APIClient().post('/api/v1/users/refresh-token/', {'refresh': str(refresh)}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertTrue(RegistoAdmin.objects.filter(accao='terminar_sessoes').exists())

    def test_apagar_de_vez(self):
        self.assertEqual(self.c.delete(BASE + f'utilizadores/{self.aluno.id}/').status_code, 403)
        sup = criar('root@pe.ao', role='admin', is_superuser=True)
        c = APIClient()
        c.force_authenticate(sup)
        pago = criar('pago@pe.ao')
        Pagamento.objects.create(user=pago, plan=plano('PREMIUM', '5000'), periodo='mensal', valor_kz=5000,
                                 telefone='923456789', provedor='simulado', estado=Pagamento.PAGO)
        self.assertEqual(c.delete(BASE + f'utilizadores/{pago.id}/').status_code, 409)
        self.assertEqual(c.delete(BASE + f'utilizadores/{self.aluno.id}/').status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.aluno.pk).exists())
        self.assertTrue(RegistoAdmin.objects.filter(accao='apagar', alvo_id=str(self.aluno.id)).exists())


class MudarSenhaTests(Base):
    def test_obrigar_mudar_senha(self):
        aluno = criar('al@pe.ao')
        r = self.c.post(BASE + f'utilizadores/{aluno.id}/obrigar-mudar-senha/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['utilizador']['deve_mudar_senha'])

        r = APIClient().post('/api/v1/users/login/', {'email': 'al@pe.ao', 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['user']['deve_mudar_senha'])

        c = cliente_com_token(aluno)
        r = c.get('/api/v1/users/notification-settings/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), {
            'error': 'A administração pediu-lhe para mudar a palavra-passe. Mude-a para continuar.',
            'message': 'A administração pediu-lhe para mudar a palavra-passe. Mude-a para continuar.',
            'code': 'mudar_senha', 'details': {}})
        r = c.get('/api/v1/users/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['deve_mudar_senha'])
        r = c.post('/api/v1/users/change-password/', {'current_password': SENHA, 'new_password': 'OutraSegura!2027',
                                                      'new_password_confirm': 'OutraSegura!2027'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['deve_mudar_senha'])
        # A sessão continua com os cookies novos (os tokens de acesso anteriores deixam de valer).
        c.credentials()
        self.assertEqual(c.get('/api/v1/users/notification-settings/').status_code, 200)
        self.assertTrue(RegistoAdmin.objects.filter(accao='obrigar_mudar_senha', alvo_id=str(aluno.id)).exists())


class EmailVariosTests(Base):
    def setUp(self):
        super().setUp()
        from unittest import mock
        # O envio corre numa thread à parte; nos testes corre já, no mesmo pedido.
        p = mock.patch('apps.users.admin_api.utilizadores.lancar_envio', side_effect=lambda f: f())
        p.start()
        self.addCleanup(p.stop)

    def test_envio_e_limite(self):
        alunos = [criar(f'm{i}@pe.ao') for i in range(3)]
        import uuid
        ids = [str(a.id) for a in alunos] + [str(uuid.uuid4())]
        mail.outbox.clear()
        r = self.c.post(BASE + 'utilizadores/email/', {'ids': ids, 'assunto': 'Novidades',
                                                       'mensagem': 'Olá.\n\nHá cursos novos.'}, format='json')
        self.assertEqual(r.status_code, 202, r.content)
        self.assertEqual({k: r.json()[k] for k in ('a_enviar', 'enviados', 'falhados', 'em_segundo_plano')},
                         {'a_enviar': 3, 'enviados': 3, 'falhados': 1, 'em_segundo_plano': True})
        self.assertIn('message', r.json())
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn('Há cursos novos.', mail.outbox[0].alternatives[0][0])
        self.assertEqual(RegistoAdmin.objects.filter(accao='email_varios').count(), 1)
        self.assertEqual(RegistoAdmin.objects.get(accao='email_varios').detalhes['enviados'], 3)
        r = self.c.post(BASE + 'utilizadores/email/', {'ids': [str(uuid.uuid4()) for _ in range(201)],
                                                       'assunto': 'a', 'mensagem': 'b'}, format='json')
        self.assertEqual(r.status_code, 400)
        for _ in range(8):
            self.c.post(BASE + 'utilizadores/email/', {'ids': ids[:1], 'assunto': 'a', 'mensagem': 'b'}, format='json')
        r = self.c.post(BASE + 'utilizadores/email/', {'ids': ids[:1], 'assunto': 'a', 'mensagem': 'b'}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()['code'], 'throttled')


class ProvinciaPerfilTests(APITestCase):
    def test_lista_e_perfil(self):
        cache.clear()
        r = self.client.get('/api/v1/users/provincias/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 21)
        self.assertIn({'valor': 'huila', 'nome': 'Huíla'}, r.json())
        u = criar('p@pe.ao')
        c = APIClient()
        c.force_authenticate(u)
        self.assertIsNone(c.get('/api/v1/users/profile/').json()['provincia'])
        r = c.patch('/api/v1/users/profile/', {'provincia': 'moxico-leste'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['provincia'], 'moxico-leste')
        self.assertEqual(c.patch('/api/v1/users/profile/', {'provincia': 'xx'}, format='json').status_code, 400)
        r = c.patch('/api/v1/users/profile/', {'provincia': None}, format='json')
        self.assertIsNone(r.json()['provincia'])
