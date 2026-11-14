"""Correcções da administração de utilizadores: tomada de contas por mudança de email, plano
atribuído (preço/promoção/teste), suspensão, login de conta suspensa, convites, email a vários,
sessões ao mudar a palavra-passe e testemunhos."""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.pagamentos.models import Pagamento
from apps.subscriptions.models import SubscriptionHistory, UserSubscription
from apps.users.models import (ConviteProfessor, EmailVerification, RegistoAdmin, User, UserFeedback)

from .test_admin_utilizadores import BASE, SENHA, Base, criar, dar_plano, plano

LOGIN = '/api/v1/users/login/'
RESET = '/api/v1/users/password-reset/'
CONFIRMAR = '/api/v1/users/confirmar-email-novo/'
TEL_PENDENTE = '923451111'


def cliente_com_token(user):
    """Cliente de outro dispositivo, com um token de acesso emitido há uns segundos."""
    access = RefreshToken.for_user(user).access_token
    access['iat'] = int((timezone.now() - timedelta(seconds=5)).timestamp())
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return c


def como(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


# ---------------------------------------------------------------------------
# 1. Mudança de email / contas de administradores
# ---------------------------------------------------------------------------

class TomadaDeContaTests(Base):
    def setUp(self):
        super().setUp()
        self.sup = criar('root@pe.ao', role='admin', is_superuser=True, name='Raiz Super')
        self.outro_admin = criar('ad2@pe.ao', role='admin', name='Outro Admin')
        self.aluno = criar('al@pe.ao', name='Ana Costa')

    def test_admin_nao_altera_superutilizador_nem_outro_admin(self):
        for alvo in (self.sup, self.outro_admin):
            for dados in ({'email': 'meu@atacante.ao'}, {'nome': 'Outro Nome'}, {'telefone': None}):
                with self.subTest(alvo=alvo.email, dados=dados):
                    r = self.c.patch(BASE + f'utilizadores/{alvo.id}/', dados, format='json')
                    self.assertEqual(r.status_code, 403, r.content)
                    self.assertEqual(r.json()['code'], 'alvo_administrador')
            r = self.c.patch(f'/api/v1/users/admin/users/{alvo.id}/update/',
                             {'name': 'X Y', 'email': 'meu@atacante.ao'}, format='json')
            self.assertEqual(r.status_code, 403)
            alvo.refresh_from_db()
            self.assertIsNone(alvo.email_pendente)
            self.assertNotEqual(alvo.email, 'meu@atacante.ao')
        # O superutilizador pode; o próprio administrador edita os seus dados.
        r = como(self.sup).patch(BASE + f'utilizadores/{self.outro_admin.id}/', {'nome': 'Admin Dois'}, format='json')
        self.assertEqual(r.status_code, 200)
        r = self.c.patch(BASE + f'utilizadores/{self.admin.id}/', {'nome': 'Admin Geral Novo'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_email_so_muda_depois_de_confirmado(self):
        mail.outbox.clear()
        r = como(self.sup).patch(BASE + f'utilizadores/{self.outro_admin.id}/', {'email': 'novo@pe.ao'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['utilizador']['email'], 'ad2@pe.ao')
        self.assertEqual(r.json()['utilizador']['email_pendente'], 'novo@pe.ao')
        self.assertIn('só muda quando', r.json()['message'])
        destinos = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(destinos), {'novo@pe.ao', 'ad2@pe.ao'})  # código + aviso ao email antigo
        self.assertIn('novo@pe.ao', destinos['ad2@pe.ao'].body)
        codigo = EmailVerification.objects.get(email='novo@pe.ao',
                                               finalidade=EmailVerification.FINALIDADE_MUDAR_EMAIL).code
        u = User.objects.get(pk=self.outro_admin.pk)
        self.assertEqual((u.email, u.email_verified), ('ad2@pe.ao', True))

        # Entra-se com o email antigo; o novo ainda não serve.
        self.assertEqual(APIClient().post(LOGIN, {'email': 'ad2@pe.ao', 'password': SENHA}, format='json').status_code, 200)
        self.assertEqual(APIClient().post(LOGIN, {'email': 'novo@pe.ao', 'password': SENHA}, format='json').status_code, 401)
        # Recuperar a palavra-passe para o email pendente não envia nada.
        mail.outbox.clear()
        APIClient().post(RESET, {'email': 'novo@pe.ao'}, format='json')
        self.assertEqual(mail.outbox, [])
        self.assertFalse(EmailVerification.objects.filter(finalidade=EmailVerification.FINALIDADE_RECUPERAR).exists())

        # Código errado, depois o certo.
        r = APIClient().post(CONFIRMAR, {'email': 'novo@pe.ao', 'code': '000000' if codigo != '000000' else '111111'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'codigo_invalido')
        r = APIClient().post(CONFIRMAR, {'email': 'novo@pe.ao', 'code': codigo}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        u.refresh_from_db()
        self.assertEqual((u.email, u.email_verified, u.email_pendente), ('novo@pe.ao', True, None))
        self.assertEqual(APIClient().post(LOGIN, {'email': 'novo@pe.ao', 'password': SENHA}, format='json').status_code, 200)
        # O código não volta a servir.
        self.assertEqual(APIClient().post(CONFIRMAR, {'email': 'novo@pe.ao', 'code': codigo}, format='json').status_code, 400)

    def test_rota_antiga_tambem_fica_pendente(self):
        r = self.c.patch(f'/api/v1/users/admin/users/{self.aluno.id}/update/',
                         {'name': 'Ana Costa', 'email': 'ana.nova@pe.ao'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.aluno.refresh_from_db()
        self.assertEqual((self.aluno.email, self.aluno.email_pendente), ('al@pe.ao', 'ana.nova@pe.ao'))
        self.assertEqual(r.json()['user']['email_pendente'], 'ana.nova@pe.ao')

    def test_recuperacao_so_para_email_confirmado(self):
        criar('naoconf@pe.ao', verified=False)
        mail.outbox.clear()
        APIClient().post(RESET, {'email': 'naoconf@pe.ao'}, format='json')
        self.assertEqual(mail.outbox, [])
        APIClient().post(RESET, {'email': 'al@pe.ao'}, format='json')
        self.assertEqual([m.to for m in mail.outbox], [['al@pe.ao']])

    def test_pode_gerir_no_detalhe(self):
        casos = [(self.c, self.aluno, True), (self.c, self.outro_admin, False), (self.c, self.sup, False),
                 (self.c, self.admin, False), (como(self.sup), self.outro_admin, True)]
        for cliente, alvo, esperado in casos:
            with self.subTest(alvo=alvo.email):
                r = cliente.get(BASE + f'utilizadores/{alvo.id}/')
                self.assertEqual(r.json()['utilizador']['pode_gerir'], esperado)
                self.assertIn('email_pendente', r.json()['utilizador'])


# ---------------------------------------------------------------------------
# 2. Plano atribuído
# ---------------------------------------------------------------------------

class AtribuirPlanoTests(Base):
    def setUp(self):
        super().setUp()
        self.aluno = criar('al@pe.ao')

    def patch(self, dados):
        return self.c.patch(BASE + f'utilizadores/{self.aluno.id}/', dados, format='json')

    def test_preco_e_promocao_do_plano_novo(self):
        sub = dar_plano(self.aluno, 'PREMIUM', dias=10)
        sub.preco_mensal_kz = 3000  # preço antigo contratado
        sub.promo_meses_usados = 2
        sub.save()
        self.assertEqual(self.patch({'plano': 'PREMIUM_PLUS'}).status_code, 200)
        sub.refresh_from_db()
        self.assertEqual((sub.plan.plan_type, sub.preco_mensal_kz, sub.promo_codigo, sub.promo_meses_usados),
                         ('PREMIUM_PLUS', int(sub.plan.monthly_price), None, 0))
        self.assertEqual(self.patch({'plano': 'FREE'}).status_code, 200)
        sub.refresh_from_db()
        self.assertEqual((sub.preco_mensal_kz, sub.preco_anual_kz), (None, None))
        self.assertEqual(self.patch({'plano': 'PREMIUM'}).status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.preco_mensal_kz, int(sub.plan.monthly_price))

    def test_durante_o_teste_converte_em_assinatura_normal(self):
        from apps.pagamentos.teste import terminar_testes
        agora = timezone.now()
        sub = UserSubscription.objects.get(user=self.aluno)
        sub.plan = plano('PREMIUM', '5000')
        sub.status = 'TRIAL'
        sub.trial_ends_at = sub.expires_at = agora + timedelta(days=3)
        sub.save()
        r = self.patch({'plano': 'PREMIUM'})
        self.assertEqual(r.status_code, 200, r.content)
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.trial_ends_at, sub.preco_mensal_kz),
                         ('ACTIVE', None, int(sub.plan.monthly_price)))
        self.assertGreater(sub.expires_at, agora + timedelta(days=29))
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=sub, notes__icontains='teste grátis').exists())
        # O trabalho que termina os testes já não a reverte.
        terminar_testes(agora=agora + timedelta(days=4))
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.plan.plan_type), ('ACTIVE', 'PREMIUM'))


# ---------------------------------------------------------------------------
# 3 e 4. Suspensão e login
# ---------------------------------------------------------------------------

class SuspensaoTests(Base):
    def setUp(self):
        super().setUp()
        self.aluno = criar('al@pe.ao')

    def suspender(self):
        return self.c.post(BASE + f'utilizadores/{self.aluno.id}/suspender/', {'motivo': 'outro'}, format='json')

    def test_cancela_pagamentos_pendentes(self):
        p = Pagamento.objects.create(user=self.aluno, plan=plano('PREMIUM', '5000'), periodo='mensal',
                                     valor_kz=5000, telefone=TEL_PENDENTE, provedor='simulado')
        self.assertEqual(self.suspender().status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.estado, Pagamento.CANCELADO)
        self.assertIn('suspensa', p.motivo_falha)

    def test_plano_recusado_enquanto_suspensa(self):
        self.suspender()
        r = self.c.patch(BASE + f'utilizadores/{self.aluno.id}/', {'plano': 'PREMIUM'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'conta_suspensa')

    def test_reactivar_nao_encurta(self):
        sub = dar_plano(self.aluno, 'PREMIUM', dias=10)
        self.suspender()
        mais_tarde = timezone.now() + timedelta(days=40)
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=mais_tarde, status='ACTIVE')
        self.assertEqual(self.c.post(BASE + f'utilizadores/{self.aluno.id}/reactivar/').status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.expires_at, mais_tarde)

    def test_reactivar_retoma_o_tempo_em_pausa(self):
        sub = dar_plano(self.aluno, 'PREMIUM', dias=10)
        self.suspender()
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=timezone.now() - timedelta(days=1))
        self.c.post(BASE + f'utilizadores/{self.aluno.id}/reactivar/')
        sub.refresh_from_db()
        self.assertGreater(sub.expires_at, timezone.now() + timedelta(days=9))

    def test_login_conta_suspensa(self):
        self.suspender()
        r = APIClient().post(LOGIN, {'email': 'al@pe.ao', 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'conta_suspensa')
        self.assertEqual(r.json()['message'], 'A sua conta está suspensa. Fale com a equipa ProEnglish.')
        # Palavra-passe errada: a mensagem de sempre (não revela que a conta existe).
        r = APIClient().post(LOGIN, {'email': 'al@pe.ao', 'password': 'errada'}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertNotEqual(r.json()['code'], 'conta_suspensa')


# ---------------------------------------------------------------------------
# 5. Convites
# ---------------------------------------------------------------------------

class ConvitesAreaTests(Base):
    def criar(self, **extra):
        return self.c.post(BASE + 'convites/', {'email': 'prof@pe.ao', 'nome': 'Paulo Prof', **extra}, format='json')

    def test_area_em_portugues(self):
        mail.outbox.clear()
        r = self.criar(area='Industry English')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['area'], 'Petróleo e Gás')
        self.assertTrue(r.json()['email_enviado'])
        self.assertIn('prof@pe.ao', r.json()['message'])
        self.assertIn('Petróleo e Gás', mail.outbox[-1].alternatives[0][0])
        self.assertNotIn('Industry English', mail.outbox[-1].alternatives[0][0])
        self.assertEqual(self.c.get(BASE + 'convites/').json()[0]['area'], 'Petróleo e Gás')

    def test_sem_area_omite(self):
        r = self.criar()
        self.assertNotIn('area', r.json())
        self.assertNotIn('area', self.c.get(BASE + 'convites/').json()[0])

    def test_reenviar_cancela_outros_pendentes(self):
        antigo = self.criar().json()['id']
        self.c.delete(BASE + f'convites/{antigo}/')
        novo = self.criar().json()['id']
        r = self.c.post(BASE + f'convites/{antigo}/reenviar/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('message', r.json())
        self.assertEqual(ConviteProfessor.objects.get(pk=novo).estado, ConviteProfessor.CANCELADO)
        self.assertEqual(ConviteProfessor.objects.filter(email='prof@pe.ao', estado='pendente').count(), 1)


# ---------------------------------------------------------------------------
# 6. Email a vários, rotas antigas, sessões ao mudar a palavra-passe
# ---------------------------------------------------------------------------

class VariosTests(Base):
    def test_assunto_numa_linha(self):
        aluno = criar('al@pe.ao')
        for assunto in ('Olá\r\nBcc: x@y.ao', 'Linha\nOutra'):
            r = self.c.post(BASE + 'utilizadores/email/', {'ids': [str(aluno.id)], 'assunto': assunto,
                                                           'mensagem': 'Texto'}, format='json')
            self.assertEqual(r.status_code, 400)
            self.assertIn('assunto', r.json()['details'])
            self.assertIsInstance(r.json()['details']['assunto'], list)

    def test_envio_em_segundo_plano(self):
        aluno = criar('al@pe.ao')
        with mock.patch('apps.users.admin_api.utilizadores.lancar_envio') as lancar:
            r = self.c.post(BASE + 'utilizadores/email/', {'ids': [str(aluno.id)], 'assunto': 'Olá',
                                                           'mensagem': 'Texto'}, format='json')
        self.assertEqual(r.status_code, 202)
        lancar.assert_called_once()

    def test_rotas_antigas_ignoram_contas_apagadas(self):
        apagado = criar('x1@apagado.invalid')
        r = self.c.get('/api/v1/users/admin/users/?limit=100')
        self.assertNotIn(str(apagado.id), [u['id'] for u in r.json()['users']])
        r = self.c.patch(f'/api/v1/users/admin/users/{apagado.id}/status/')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'conta_apagada')

    def test_mudar_palavra_passe_corta_tokens_dos_outros_dispositivos(self):
        aluno = criar('al@pe.ao')
        outro = cliente_com_token(aluno)
        self.assertEqual(outro.get('/api/v1/users/profile/').status_code, 200)
        actual = RefreshToken.for_user(aluno)
        c = APIClient()
        c.cookies['access_token'] = str(actual.access_token)
        c.cookies['refresh_token'] = str(actual)
        r = c.post('/api/v1/users/change-password/', {'current_password': SENHA, 'new_password': 'OutraSegura!2027',
                                                      'new_password_confirm': 'OutraSegura!2027'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access_token', r.cookies)
        self.assertEqual(outro.get('/api/v1/users/profile/').status_code, 401)
        self.assertEqual(c.get('/api/v1/users/profile/').status_code, 200)

    def test_recuperar_palavra_passe_corta_tokens(self):
        aluno = criar('al@pe.ao')
        c = cliente_com_token(aluno)
        APIClient().post(RESET, {'email': 'al@pe.ao'}, format='json')
        codigo = EmailVerification.objects.get(user=aluno, finalidade=EmailVerification.FINALIDADE_RECUPERAR).code
        r = APIClient().post('/api/v1/users/password-reset-confirm/',
                             {'email': 'al@pe.ao', 'code': codigo, 'new_password': 'OutraSegura!2027'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        aluno.refresh_from_db()
        self.assertIsNotNone(aluno.sessoes_invalidas_antes)
        self.assertEqual(c.get('/api/v1/users/profile/').status_code, 401)


# ---------------------------------------------------------------------------
# 7. Testemunhos
# ---------------------------------------------------------------------------

class TestemunhosTests(Base):
    def opiniao(self, user, comentario='Muito bom.', **extra):
        return UserFeedback.objects.create(user=user, feedback_type='general', rating=5, comment=comentario,
                                           allow_public=True, **extra)

    def test_aprovar_fica_em_ultimo(self):
        a = self.opiniao(criar('a@pe.ao'), estado='aprovada', ordem=7)
        b = self.opiniao(criar('b@pe.ao'))
        r = self.c.patch(BASE + f'opinioes/{b.id}/', {'estado': 'aprovada'}, format='json')
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.ordem, a.ordem + 1)
        # Rota antiga também.
        c = self.opiniao(criar('c@pe.ao'))
        sup = criar('root@pe.ao', role='admin', is_superuser=True, is_staff=True)
        r = como(sup).patch(f'/api/v1/users/feedback/admin/{c.id}/', {'is_reviewed': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db()
        self.assertEqual((c.estado, c.ordem), ('aprovada', b.ordem + 1))

    def test_nome_curto_igual_no_site_e_na_administracao(self):
        self.opiniao(criar('j@pe.ao', name='João'), estado='aprovada', ordem=1)
        self.opiniao(criar('m@pe.ao', name='Maria José Silva'), estado='aprovada', ordem=2)
        site = [t['name'] for t in APIClient().get('/api/v1/users/feedback/testimonials/').json()['testimonials']]
        admin = [t['nome_curto'] for t in self.c.get(BASE + 'testemunhos/').json()]
        self.assertEqual(site, ['João', 'Maria S.'])
        self.assertEqual(site, admin)

    def test_site_sem_contas_suspensas_ou_apagadas(self):
        activo = criar('a@pe.ao', name='Ana Activa')
        suspenso = criar('s@pe.ao', name='Sara Suspensa')
        apagado = criar('x@apagado.invalid', name='Conta apagada')
        for u in (activo, suspenso, apagado):
            self.opiniao(u, estado='aprovada')
        self.c.post(BASE + f'utilizadores/{suspenso.id}/suspender/', {'motivo': 'outro'}, format='json')
        site = [t['name'] for t in APIClient().get('/api/v1/users/feedback/testimonials/').json()['testimonials']]
        self.assertEqual(site, ['Ana A.'])

    def test_nota_interna_ate_2000(self):
        f = self.opiniao(criar('a@pe.ao'))
        r = self.c.patch(BASE + f'opinioes/{f.id}/', {'nota_interna': 'x' * 2001}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.patch(BASE + f'opinioes/{f.id}/', {'nota_interna': 'x' * 2000},
                                      format='json').status_code, 200)
        sup = criar('root@pe.ao', role='admin', is_superuser=True, is_staff=True)
        r = como(sup).patch(f'/api/v1/users/feedback/admin/{f.id}/', {'admin_notes': 'y' * 2001}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('admin_notes', r.json()['details'])
