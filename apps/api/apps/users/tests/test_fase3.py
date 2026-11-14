"""
Fase 3: mensagens em pt-PT e formato único dos erros, emails, conta (apagar, palavra-passe
das contas do Google), opiniões, push, IP atrás do proxy e defesa CSRF com cookies.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.users.tests.test_fase3
"""
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone
from django_ratelimit.exceptions import Ratelimited
from rest_framework import exceptions as drf_exc
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient, APIRequestFactory, APITestCase
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ip import ip_do_cliente
from apps.users.email_service import EmailVerificationService
from apps.users.models import (EmailVerification, Notification, PreferenciasAvisos, PushSubscription,
                               UserFeedback)

User = get_user_model()
U = '/api/v1/users/'
SENHA = 'Segura!2026xy'
SESSAO = 'A sessão terminou. Entre outra vez.'
FRONT = 'http://localhost:3000'


def _vista(exc):
    """Vista DRF que lança `exc` (para testar o tratamento de erros sem depender de rotas)."""
    class Vista(APIView):
        permission_classes = [AllowAny]
        authentication_classes = []

        def get(self, request):
            raise exc
    return Vista.as_view()


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def utilizador(self, email='ana-f3@example.com', senha=SENHA, **extra):
        u = User.objects.create_user(email=email, name='Ana Neto', password=senha,
                                     role=extra.pop('role', 'student'), **extra)
        if senha is None:
            u.set_unusable_password()
        u.email_verified = True
        u.save()
        return u

    def com_cookie(self, user):
        c = APIClient()
        c.cookies['access_token'] = str(RefreshToken.for_user(user).access_token)
        return c


# ---------------------------------------------------------------------------
# 1. Formato dos erros e língua
# ---------------------------------------------------------------------------

class FormatoErrosTests(Base):

    def assertFormato(self, r, estado, code, mensagem=None):
        self.assertEqual(r.status_code, estado, r.content)
        corpo = r.json()
        self.assertEqual(set(corpo) - {'aguardar_segundos'}, {'error', 'message', 'code', 'details'}, corpo)
        self.assertIsInstance(corpo['error'], str)
        self.assertEqual(corpo['error'], corpo['message'])
        self.assertEqual(corpo['code'], code)
        if mensagem is not None:
            self.assertEqual(corpo['error'], mensagem)
        return corpo

    def test_validacao_mensagem_e_o_primeiro_erro_de_campo(self):
        self.utilizador(email='dup-f3@example.com')
        r = self.client.post(f'{U}register/', {'email': 'dup-f3@example.com', 'name': 'Outra',
                                               'password': SENHA}, format='json')
        corpo = self.assertFormato(r, 400, 'validation_error', 'Já existe uma conta com este email.')
        self.assertEqual(corpo['details']['email'], ['Já existe uma conta com este email.'])

    def test_campo_obrigatorio_diz_qual(self):
        r = self.client.post(f'{U}register/', {'email': 'x-f3@example.com', 'name': 'X Y'}, format='json')
        corpo = self.assertFormato(r, 400, 'validation_error', 'Preencha o campo «palavra-passe».')
        self.assertEqual(corpo['details']['password'], ['Este campo é obrigatório.'])

    def test_validadores_de_palavra_passe_em_pt_pt(self):
        r = self.client.post(f'{U}register/', {'email': 'fraca-f3@example.com', 'name': 'Fraca',
                                               'password': 'password'}, format='json')
        corpo = self.assertFormato(r, 400, 'validation_error')
        texto = ' '.join(corpo['details']['password'])
        self.assertIn('demasiado comum', texto)
        self.assertNotIn('This password', texto)
        r = self.client.post(f'{U}register/', {'email': 'curta-f3@example.com', 'name': 'Curta',
                                               'password': '12a'}, format='json')
        texto = ' '.join(r.json()['details']['password'])
        self.assertIn('demasiado curta', texto)
        self.assertIn('Tem de ter pelo menos 8 caracteres', texto)

    def test_email_invalido_em_pt_pt(self):
        r = self.client.post(f'{U}register/', {'email': 'nao-e-email', 'name': 'X Y', 'password': SENHA},
                             format='json')
        self.assertFormato(r, 400, 'validation_error', 'Indique um email válido.')

    def test_401_sem_sessao(self):
        r = self.client.get(f'{U}profile/')
        self.assertFormato(r, 401, 'not_authenticated', SESSAO)

    def test_401_token_invalido_nao_mostra_dict(self):
        self.client.cookies['access_token'] = 'lixo.lixo.lixo'
        r = self.client.get(f'{U}profile/')
        corpo = self.assertFormato(r, 401, 'token_not_valid', SESSAO)
        self.assertNotIn('ErrorDetail', r.content.decode())
        self.assertEqual(corpo['details'], {})

    def test_refresh_sem_cookie_e_com_cookie_invalido(self):
        r = self.client.post(f'{U}refresh-token/', {}, format='json')
        self.assertFormato(r, 401, 'not_authenticated', SESSAO)
        self.client.cookies['refresh_token'] = 'lixo'
        r = self.client.post(f'{U}refresh-token/', {}, format='json')
        self.assertFormato(r, 401, 'token_not_valid', SESSAO)
        self.assertNotIn("{'detail'", r.content.decode())

    def test_refresh_com_token_na_lista_negra(self):
        u = self.utilizador()
        refresh = RefreshToken.for_user(u)
        refresh.blacklist()
        self.client.cookies['refresh_token'] = str(refresh)
        r = self.client.post(f'{U}refresh-token/', {}, format='json')
        self.assertFormato(r, 401, 'token_not_valid', SESSAO)

    def test_login_errado(self):
        self.utilizador()
        r = self.client.post(f'{U}login/', {'email': 'ana-f3@example.com', 'password': 'errada'}, format='json')
        self.assertFormato(r, 401, 'authentication_failed', 'O email ou a palavra-passe não estão certos.')
        r = self.client.post(f'{U}login/', {'email': '', 'password': ''}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'authentication_failed')

    def test_login_email_por_confirmar_mantem_mensagem_propria(self):
        u = self.utilizador()
        u.email_verified = False
        u.save()
        r = self.client.post(f'{U}login/', {'email': u.email, 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertIn('confirmou o seu email', r.json()['error'])

    def test_404_e_403_genericos(self):
        f = APIRequestFactory()
        from django.http import Http404
        r = _vista(Http404('No Pagamento matches the given query.'))(f.get('/x'))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data, {'error': 'Não encontrámos o que procura.', 'message': 'Não encontrámos o que procura.',
                                  'code': 'not_found', 'details': {}})
        r = _vista(drf_exc.PermissionDenied())(f.get('/x'))
        self.assertEqual((r.status_code, r.data['error'], r.data['code']), (403, 'Não tem permissão para isto.',
                                                                            'permission_denied'))
        r = _vista(drf_exc.NotFound())(f.get('/x'))
        self.assertEqual(r.data['error'], 'Não encontrámos o que procura.')

    def test_mensagens_proprias_mantem_se(self):
        f = APIRequestFactory()
        r = _vista(drf_exc.PermissionDenied('Não tem a subscrição necessária para este curso.'))(f.get('/x'))
        self.assertEqual(r.data['error'], 'Não tem a subscrição necessária para este curso.')
        r = _vista(drf_exc.NotFound('Curso não encontrado.'))(f.get('/x'))
        self.assertEqual(r.data['error'], 'Curso não encontrado.')

    def test_invalid_token_com_dict(self):
        f = APIRequestFactory()
        exc = InvalidToken({'detail': 'Given token not valid for any token type', 'code': 'token_not_valid',
                            'messages': [{'token_class': 'AccessToken', 'message': 'Token is invalid or expired'}]})
        r = _vista(exc)(f.get('/x'))
        self.assertEqual((r.status_code, r.data['error'], r.data['code']), (401, SESSAO, 'token_not_valid'))

    def test_throttle_do_drf(self):
        f = APIRequestFactory()
        r = _vista(drf_exc.Throttled(wait=37.2))(f.get('/x'))
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.data['error'], 'Fez muitos pedidos seguidos. Tente outra vez daqui a 38 segundos.')
        self.assertEqual(r.data['code'], 'throttled')
        self.assertEqual(r.data['aguardar_segundos'], 38)
        self.assertEqual(r['Retry-After'], '38')

    def test_ratelimited_e_429(self):
        f = APIRequestFactory()
        r = _vista(Ratelimited())(f.get('/x'))
        self.assertEqual(r.status_code, 429)
        self.assertIn('Fez muitos pedidos seguidos', r.data['error'])
        self.assertEqual(r.data['code'], 'throttled')

    def test_ratelimit_real_no_pedido_de_recuperacao(self):
        for _ in range(3):
            self.assertEqual(self.client.post(f'{U}password-reset/', {'email': 'ninguem@example.com'},
                                              format='json').status_code, 200)
        r = self.client.post(f'{U}password-reset/', {'email': 'ninguem@example.com'}, format='json')
        self.assertEqual(r.status_code, 429, r.content)
        self.assertIn('Fez muitos pedidos seguidos', r.json()['error'])

    def test_vistas_com_corpo_proprio_nao_mudam(self):
        u = self.utilizador()
        c = self.com_cookie(u)
        r = c.patch(f'{U}avisos/', {'tipos': 'x'}, format='json')
        self.assertEqual(r.json(), {'error': 'validation_error', 'message': '"tipos" tem de ser um objecto.'})


class MensagensTests(Base):

    def test_pedido_de_recuperacao_em_pt_pt(self):
        r = self.client.post(f'{U}password-reset/', {'email': 'ninguem@example.com'}, format='json')
        msg = r.json()['message']
        for proibida in ('cadastrado', 'você', 'senha'):
            self.assertNotIn(proibida, msg.lower())
        self.assertIn('palavra-passe', msg)

    def test_registo_em_pt_pt(self):
        r = self.client.post(f'{U}register/', {'email': 'reg-f3@example.com', 'name': 'Reg Aluno',
                                               'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('activar', r.json()['message'])
        self.assertNotIn('ativar', r.json()['message'])

    def test_palavras_passe_diferentes(self):
        r = self.client.post(f'{U}register/', {'email': 'dif-f3@example.com', 'name': 'Dif',
                                               'password': SENHA, 'password_confirm': SENHA + 'x'}, format='json')
        self.assertEqual(r.json()['error'], 'As duas palavras-passe não são iguais.')


# ---------------------------------------------------------------------------
# 2. Emails
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   FRONTEND_URL='https://proenglish.ao', SUPPORT_EMAIL='suporte@proenglish.ao')
class EmailsTests(Base):

    def _verificar_sem_promessas_falsas(self, html):
        for proibido in ('href="#"', '10,000', '500+', '4.9', '999 999 999', 'você', 'Você', 'senha', 'Senha',
                         'compartilhe', 'contato', 'registrar', '/braiders', '/profile', '/reset-password'):
            self.assertNotIn(proibido, html)

    def test_email_de_confirmacao(self):
        with mock.patch('builtins.print') as p:
            r = self.client.post(f'{U}register/', {'email': 'ana+f3@example.com', 'name': 'Ana Mais',
                                                   'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 201)
        p.assert_not_called()  # nada de códigos no stdout
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        codigo = EmailVerification.objects.get(email='ana+f3@example.com').code
        self.assertIn(codigo, html)
        self.assertIn('https://proenglish.ao/verify-email?email=ana%2Bf3%40example.com', html)
        self.assertIn('suporte@proenglish.ao', html)
        self._verificar_sem_promessas_falsas(html)

    def test_codigo_nao_vai_para_os_logs(self):
        u = self.utilizador()
        with self.assertLogs('apps.users.email_service', level='DEBUG') as logs:
            v = EmailVerificationService.create_verification_code(u)
            EmailVerificationService.send_verification_email(v)
        self.assertNotIn(v.code, ' '.join(logs.output))

    def test_email_de_recuperacao(self):
        self.utilizador(email='rec+f3@example.com')
        self.client.post(f'{U}password-reset/', {'email': 'rec+f3@example.com'}, format='json')
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('https://proenglish.ao/forgot-password?email=rec%2Bf3%40example.com', html)
        self.assertNotIn('Redefinir', mail.outbox[0].subject)
        self._verificar_sem_promessas_falsas(html)

    def test_email_de_boas_vindas(self):
        u = self.utilizador()
        self.assertTrue(EmailVerificationService.send_welcome_email(u))
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('https://proenglish.ao/user/dashboard', html)
        self.assertIn('https://proenglish.ao/user/settings', html)
        self._verificar_sem_promessas_falsas(html)


# ---------------------------------------------------------------------------
# 3. Conta: apagar, palavra-passe das contas do Google
# ---------------------------------------------------------------------------

class ContaTests(Base):

    def test_has_password_no_perfil(self):
        com = self.utilizador()
        sem = self.utilizador(email='google-f3@example.com', senha=None)
        self.assertTrue(self.com_cookie(com).get(f'{U}profile/').json()['has_password'])
        self.assertFalse(self.com_cookie(sem).get(f'{U}profile/').json()['has_password'])

    def test_apagar_conta_apaga_dados_ligados(self):
        u = self.utilizador()
        EmailVerificationService.create_verification_code(u)
        PushSubscription.objects.create(user=u, endpoint='https://fcm.googleapis.com/f3', p256dh='p', auth='a')
        PreferenciasAvisos.objects.create(user=u)
        Notification.objects.create(user=u, kind='system', title='Olá')
        fb = UserFeedback.objects.create(user=u, rating=5, comment='Bom', allow_public=True)
        c = self.com_cookie(u)
        r = c.post(f'{U}apagar-conta/', {'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertTrue(u.email.endswith('@apagado.invalid'))
        self.assertFalse(EmailVerification.objects.filter(user=u).exists())
        self.assertFalse(EmailVerification.objects.filter(email='ana-f3@example.com').exists())
        self.assertFalse(PushSubscription.objects.filter(user=u).exists())
        self.assertFalse(PreferenciasAvisos.objects.filter(user=u).exists())
        self.assertFalse(Notification.objects.filter(user=u).exists())
        fb.refresh_from_db()
        self.assertFalse(fb.allow_public)

    def test_apagar_conta_do_google_com_confirmar(self):
        u = self.utilizador(email='google-del@example.com', senha=None)
        c = self.com_cookie(u)
        r = c.post(f'{U}apagar-conta/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        r = c.post(f'{U}apagar-conta/', {'confirmar': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        u.refresh_from_db()
        self.assertFalse(u.is_active)

    def test_apagar_conta_com_senha_nao_aceita_so_confirmar(self):
        u = self.utilizador()
        r = self.com_cookie(u).post(f'{U}apagar-conta/', {'confirmar': True}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_definir_primeira_palavra_passe(self):
        u = self.utilizador(email='google-pw@example.com', senha=None)
        r = self.com_cookie(u).post(f'{U}change-password/', {'new_password': 'NovaSegura!2026',
                                                              'new_password_confirm': 'NovaSegura!2026'},
                                    format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['has_password'], True)
        self.assertIn('definida', r.json()['message'])
        u.refresh_from_db()
        self.assertTrue(u.check_password('NovaSegura!2026'))

    def test_mudar_palavra_passe_exige_a_actual(self):
        u = self.utilizador()
        c = self.com_cookie(u)
        r = c.post(f'{U}change-password/', {'new_password': 'NovaSegura!2026',
                                            'new_password_confirm': 'NovaSegura!2026'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'Escreva a palavra-passe actual.')
        self.assertIn('current_password', r.json()['details'])
        r = c.post(f'{U}change-password/', {'current_password': 'errada', 'new_password': 'NovaSegura!2026',
                                            'new_password_confirm': 'NovaSegura!2026'}, format='json')
        self.assertEqual(r.json()['error'], 'A palavra-passe actual não está certa.')
        r = c.post(f'{U}change-password/', {'current_password': SENHA, 'new_password': 'NovaSegura!2026',
                                            'new_password_confirm': 'NovaSegura!2026'}, format='json')
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertTrue(u.check_password('NovaSegura!2026'))


# ---------------------------------------------------------------------------
# 4. Opiniões
# ---------------------------------------------------------------------------

class OpinioesTests(Base):

    def test_aluno_nao_ve_notas_internas(self):
        u = self.utilizador()
        c = self.com_cookie(u)
        r = c.post(f'{U}feedback/submit/', {'rating': 4, 'comment': 'Bom'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('admin_notes', r.json()['feedback'])
        self.assertNotIn('is_reviewed', r.json()['feedback'])
        UserFeedback.objects.filter(user=u).update(admin_notes='aluno difícil', is_reviewed=True)
        r = c.get(f'{U}feedback/my-feedback/')
        self.assertNotIn('admin_notes', r.json()['feedbacks'][0])
        self.assertNotIn('aluno difícil', r.content.decode())

    def test_dismiss_valida_trigger(self):
        u = self.utilizador()
        c = self.com_cookie(u)
        r = c.post(f'{U}feedback/dismiss/', {'trigger': 'x' * 500}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('trigger', r.json()['details'])
        r = c.post(f'{U}feedback/dismiss/', {'trigger': 'first_lesson'}, format='json')
        self.assertEqual(r.status_code, 200)
        r = c.post(f'{U}feedback/dismiss/', {}, format='json')
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 5. IP do cliente atrás do proxy
# ---------------------------------------------------------------------------

class IPTests(SimpleTestCase):

    def pedido(self, **meta):
        return RequestFactory().get('/', REMOTE_ADDR='10.0.0.2', **meta)

    @override_settings(TRUSTED_PROXY=False)
    def test_sem_proxy_ignora_cabecalhos(self):
        r = self.pedido(HTTP_X_REAL_IP='1.2.3.4', HTTP_X_FORWARDED_FOR='5.6.7.8')
        self.assertEqual(ip_do_cliente(r), '10.0.0.2')
        self.assertEqual(AnonRateThrottle().get_ident(r), '10.0.0.2')

    @override_settings(TRUSTED_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_com_proxy(self):
        self.assertEqual(ip_do_cliente(self.pedido(HTTP_X_REAL_IP='1.2.3.4')), '1.2.3.4')
        # a entrada da esquerda vem do cliente (inventada); conta a que o proxy acrescentou
        r = self.pedido(HTTP_X_FORWARDED_FOR='6.6.6.6, 5.6.7.8')
        self.assertEqual(ip_do_cliente(r), '5.6.7.8')
        self.assertEqual(AnonRateThrottle().get_ident(r), '5.6.7.8')
        self.assertEqual(ip_do_cliente(self.pedido()), '10.0.0.2')

    def test_ratelimit_usa_o_helper(self):
        from django.conf import settings
        self.assertEqual(settings.RATELIMIT_IP_META_KEY, 'apps.core.ip.ip_do_cliente')


# ---------------------------------------------------------------------------
# 6. Defesa CSRF nos pedidos autenticados pelo cookie
# ---------------------------------------------------------------------------

@override_settings(CORS_ALLOWED_ORIGINS=[FRONT], CSRF_TRUSTED_ORIGINS=[], FRONTEND_URL=FRONT,
                   COOKIE_AUTH_ALLOWED_ORIGINS=[])
class OrigemCookieTests(Base):

    def setUp(self):
        super().setUp()
        self.u = self.utilizador()
        self.c = self.com_cookie(self.u)
        self.url = f'{U}feedback/dismiss/'

    def test_outra_origem_e_recusada(self):
        r = self.c.post(self.url, {}, format='json', HTTP_ORIGIN='https://mau.example')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'origem_invalida')
        self.assertIn('ProEnglish', r.json()['error'])

    def test_origem_null_e_referer_estranho_sao_recusados(self):
        self.assertEqual(self.c.post(self.url, {}, format='json', HTTP_ORIGIN='null').status_code, 403)
        self.assertEqual(self.c.post(self.url, {}, format='json',
                                     HTTP_REFERER='https://mau.example/pagina').status_code, 403)

    def test_origem_do_site_passa(self):
        self.assertEqual(self.c.post(self.url, {}, format='json', HTTP_ORIGIN=FRONT).status_code, 200)
        self.assertEqual(self.c.post(self.url, {}, format='json',
                                     HTTP_REFERER=f'{FRONT}/user/dashboard').status_code, 200)

    def test_sem_origem_passa(self):
        self.assertEqual(self.c.post(self.url, {}, format='json').status_code, 200)

    def test_get_nao_e_verificado(self):
        r = self.c.get(f'{U}profile/', HTTP_ORIGIN='https://mau.example')
        self.assertEqual(r.status_code, 200)

    def test_cabecalho_authorization_nao_e_verificado(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.u).access_token}')
        r = c.post(self.url, {}, format='json', HTTP_ORIGIN='https://mau.example')
        self.assertEqual(r.status_code, 200)

    @override_settings(COOKIE_AUTH_ALLOWED_ORIGINS=['https://proenglish.ao'])
    def test_lista_propria(self):
        self.assertEqual(self.c.post(self.url, {}, format='json', HTTP_ORIGIN=FRONT).status_code, 403)
        self.assertEqual(self.c.post(self.url, {}, format='json',
                                     HTTP_ORIGIN='https://proenglish.ao').status_code, 200)


class CacheTests(SimpleTestCase):

    def test_cache_por_omissao(self):
        from django.conf import settings
        self.assertIn('default', settings.CACHES)
