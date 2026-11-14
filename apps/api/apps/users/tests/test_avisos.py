"""
Avisos do aluno: preferências, Web Push, produtores e lembrete diário da meta.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.users.tests.test_avisos
"""
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from pywebpush import WebPushException

from apps.users.models import Notification, PreferenciasAvisos, PushSubscription
from apps.users.push import enviar_push

User = get_user_model()
LUANDA = ZoneInfo('Africa/Luanda')
VAPID = dict(VAPID_PUBLIC_KEY='BPubTeste', VAPID_PRIVATE_KEY='privTeste', VAPID_CLAIMS_EMAIL='teste@proenglish.ao')
SEM_VAPID = dict(VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='')
ENDPOINT = 'https://fcm.googleapis.com/fcm/send/abc123'
NOTIF = '/api/v1/student/practice-courses/notifications/'


def _cliente(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return c


def _aluno(email):
    return User.objects.create_user(email=email, name='Ana Martins', password='Segura!2026x', role='student')


@override_settings(**SEM_VAPID)
class PreferenciasTests(APITestCase):
    def setUp(self):
        self.user = _aluno('prefs@example.com')
        self.client = _cliente(self.user)

    def test_valores_por_omissao(self):
        r = self.client.get('/api/v1/users/avisos/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {
            'tipos': {'meta': True, 'liga': True, 'certificados': True, 'cursos': True, 'subscricao': True},
            'lembrete': {'ligado': False, 'hora': '19:00'},
            'push': {'disponivel': False, 'chave_publica': None, 'subscricoes': 0},
        })

    def test_patch_parcial_e_subscricao_sempre_ligada(self):
        r = self.client.patch('/api/v1/users/avisos/', {
            'tipos': {'liga': False, 'subscricao': False},
            'lembrete': {'ligado': True, 'hora': '07:30'},
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertFalse(d['tipos']['liga'])
        self.assertTrue(d['tipos']['meta'])
        self.assertTrue(d['tipos']['subscricao'])
        self.assertEqual(d['lembrete'], {'ligado': True, 'hora': '07:30'})
        p = PreferenciasAvisos.objects.get(user=self.user)
        self.assertEqual(p.lembrete_hora, time(7, 30))
        # só a hora muda; o resto fica
        d = self.client.patch('/api/v1/users/avisos/', {'lembrete': {'hora': '21:15'}}, format='json').json()
        self.assertEqual(d['lembrete'], {'ligado': True, 'hora': '21:15'})
        self.assertFalse(d['tipos']['liga'])

    def test_validacao(self):
        for corpo in ({'lembrete': {'hora': '25:00'}}, {'lembrete': {'hora': '7:3'}},
                      {'tipos': {'xpto': True}}, {'tipos': {'meta': 'sim'}}, {'lembrete': {'ligado': 1}}):
            r = self.client.patch('/api/v1/users/avisos/', corpo, format='json')
            self.assertEqual(r.status_code, 400, corpo)
            self.assertIn('message', r.json())

    def test_exige_sessao(self):
        self.assertEqual(APIClient().get('/api/v1/users/avisos/').status_code, 401)

    @override_settings(**VAPID)
    def test_push_disponivel_com_chaves(self):
        d = self.client.get('/api/v1/users/avisos/').json()
        self.assertEqual(d['push'], {'disponivel': True, 'chave_publica': 'BPubTeste', 'subscricoes': 0})


@override_settings(**SEM_VAPID)
class NotifyTests(TestCase):
    def setUp(self):
        self.user = _aluno('notify@example.com')

    def test_tipo_desligado_suprime(self):
        PreferenciasAvisos.objects.create(user=self.user, meta=False, liga=False, certificados=False, cursos=False)
        for kind in ('streak', 'achievement', 'league', 'certificate', 'course'):
            self.assertIsNone(Notification.notify(self.user, kind, title='x'))
        self.assertIsNotNone(Notification.notify(self.user, 'subscription', title='Serviço'))
        self.assertIsNotNone(Notification.notify(self.user, 'system', title='Sistema'))
        self.assertIsNotNone(Notification.notify(self.user, 'streak', title='forçado', respeitar_preferencias=False))
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 3)

    def test_sem_preferencias_tudo_ligado(self):
        self.assertIsNotNone(Notification.notify(self.user, 'course', title='Curso'))

    def test_dedupe(self):
        a = Notification.notify(self.user, 'system', title='Um', dedupe_key='k:1')
        b = Notification.notify(self.user, 'system', title='Dois', dedupe_key='k:1')
        self.assertIsNotNone(a)
        self.assertIsNone(b)
        outro = _aluno('outro-notify@example.com')
        self.assertIsNotNone(Notification.notify(outro, 'system', title='Um', dedupe_key='k:1'))

    @override_settings(AVISOS_PUSH_SINCRONO=True, **VAPID)
    def test_notify_envia_push_depois_do_commit(self):
        PushSubscription.objects.create(user=self.user, endpoint=ENDPOINT, p256dh='p', auth='a')
        with mock.patch('apps.users.push.enviar_push') as enviar:
            with self.captureOnCommitCallbacks(execute=True):
                n = Notification.notify(self.user, 'system', title='Olá', body='Corpo', link='/user/x')
            enviar.assert_called_once_with(self.user, 'Olá', 'Corpo', '/user/x', f'system-{n.pk}')
            # tipo desligado: nem aviso nem push
            PreferenciasAvisos.objects.create(user=self.user, cursos=False)
            enviar.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                Notification.notify(self.user, 'course', title='Curso')
            enviar.assert_not_called()


@override_settings(**VAPID)
class PushSubscricaoTests(APITestCase):
    URL = '/api/v1/users/avisos/push/'

    def setUp(self):
        self.user = _aluno('push@example.com')
        self.outro = _aluno('push-outro@example.com')
        self.client = _cliente(self.user)

    def _corpo(self, endpoint=ENDPOINT, p256dh='chaveP', auth='chaveA'):
        return {'endpoint': endpoint, 'keys': {'p256dh': p256dh, 'auth': auth}}

    def test_upsert(self):
        r = self.client.post(self.URL, self._corpo(), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json(), {'criada': True, 'subscricoes': 1})
        r = self.client.post(self.URL, self._corpo(p256dh='nova'), format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PushSubscription.objects.get().p256dh, 'nova')
        # só com o endpoint (chaves diferentes) outra conta não fica com a subscrição
        r = _cliente(self.outro).post(self.URL, self._corpo(), format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(PushSubscription.objects.get().user, self.user)
        # o mesmo navegador (mesmas chaves) numa outra conta passa a pertencer a essa conta
        _cliente(self.outro).post(self.URL, self._corpo(p256dh='nova'), format='json')
        self.assertEqual(PushSubscription.objects.get().user, self.outro)

    def test_delete_so_do_proprio(self):
        PushSubscription.objects.create(user=self.outro, endpoint=ENDPOINT, p256dh='p', auth='a')
        r = self.client.delete(self.URL, {'endpoint': ENDPOINT}, format='json')
        self.assertEqual(r.json(), {'removidas': 0, 'subscricoes': 0})
        self.assertTrue(PushSubscription.objects.filter(endpoint=ENDPOINT).exists())
        r = _cliente(self.outro).delete(self.URL, {'endpoint': ENDPOINT}, format='json')
        self.assertEqual(r.json(), {'removidas': 1, 'subscricoes': 0})

    def test_validacao(self):
        for corpo in (self._corpo(endpoint='http://fcm.googleapis.com/x'),
                      self._corpo(endpoint='https://169.254.169.254/latest'),
                      self._corpo(endpoint='https://evil.com/fcm.googleapis.com'),
                      self._corpo(auth=''), {'keys': {}}):
            self.assertEqual(self.client.post(self.URL, corpo, format='json').status_code, 400, corpo)
        ok = self._corpo(endpoint='https://web.push.apple.com/QWERTY')
        self.assertEqual(self.client.post(self.URL, ok, format='json').status_code, 201)

    @override_settings(**SEM_VAPID)
    def test_push_indisponivel(self):
        self.assertEqual(self.client.post(self.URL, self._corpo(), format='json').status_code, 503)


@override_settings(**VAPID)
class EnviarPushTests(TestCase):
    def setUp(self):
        self.user = _aluno('enviar@example.com')
        self.ok = PushSubscription.objects.create(user=self.user, endpoint=ENDPOINT, p256dh='p', auth='a')
        self.morta = PushSubscription.objects.create(
            user=self.user, endpoint='https://updates.push.services.mozilla.com/wpush/v2/x', p256dh='p', auth='a')

    def test_remove_410_e_nunca_lanca(self):
        def falso(subscription_info, **kwargs):
            if subscription_info['endpoint'] == self.morta.endpoint:
                raise WebPushException('Gone', response=SimpleNamespace(status_code=410))
            self.assertIn('"link": "/user/x"', kwargs['data'])
            self.assertEqual(kwargs['timeout'], 5)
            return SimpleNamespace(status_code=201)

        with mock.patch('pywebpush.webpush', side_effect=falso):
            self.assertEqual(enviar_push(self.user, 'Título', 'Corpo', '/user/x'), 1)
        self.assertFalse(PushSubscription.objects.filter(pk=self.morta.pk).exists())
        self.ok.refresh_from_db()
        self.assertIsNotNone(self.ok.last_used_at)

    def test_erro_temporario_mantem(self):
        erro = WebPushException('Erro', response=SimpleNamespace(status_code=500))
        with mock.patch('pywebpush.webpush', side_effect=erro):
            self.assertEqual(enviar_push(self.user, 'T'), 0)
        with mock.patch('pywebpush.webpush', side_effect=RuntimeError('rede')):
            self.assertEqual(enviar_push(self.user, 'T'), 0)
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 2)

    @override_settings(**SEM_VAPID)
    def test_sem_chaves_nao_envia(self):
        with mock.patch('pywebpush.webpush') as w:
            self.assertEqual(enviar_push(self.user, 'T'), 0)
            w.assert_not_called()


@override_settings(**SEM_VAPID)
class LembreteMetaTests(TestCase):
    def setUp(self):
        from apps.practice.models import UserStreak
        self.user = _aluno('lembrete@example.com')
        PreferenciasAvisos.objects.create(user=self.user, lembrete_ligado=True, lembrete_hora=time(19, 0))
        UserStreak.objects.create(user=self.user, daily_goal_minutes=15)

    def _correr(self, h, m, **kw):
        from apps.practice.lembretes_meta import enviar_lembretes_meta
        return enviar_lembretes_meta(agora=datetime(2026, 11, 13, h, m, tzinfo=LUANDA), **kw)

    def test_janela_e_dedupe(self):
        self.assertEqual(self._correr(18, 45)['enviados'], [])  # ainda não chegou a hora
        self.assertEqual(self._correr(19, 20)['enviados'], [])  # fora da janela
        r = self._correr(19, 0)
        self.assertEqual(len(r['enviados']), 1)
        n = Notification.objects.get(user=self.user)
        self.assertEqual(n.title, 'Faltam 15 minutos para a meta de hoje')
        self.assertEqual(n.body, 'Uma lição curta chega.')
        self.assertEqual(n.link, '/user/laboratory/learn')
        self.assertEqual(n.kind, 'streak')
        r = self._correr(19, 10)  # mesma janela, segunda execução
        self.assertEqual((r['enviados'], r['ja_enviados']), ([], 1))
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_dry_run_nao_cria(self):
        r = self._correr(19, 5, dry_run=True)
        self.assertEqual(len(r['enviados']), 1)
        self.assertFalse(Notification.objects.exists())

    def test_minutos_em_falta_e_sequencia(self):
        from apps.practice.models import DailyStudyLog, UserStreak
        agora = datetime(2026, 11, 13, 19, 5, tzinfo=LUANDA)
        dia = timezone.localdate(agora)
        DailyStudyLog.objects.create(user=self.user, date=dia, lesson_minutes=11.2)
        UserStreak.objects.filter(user=self.user).update(current_streak=4, last_practice_date=dia - timedelta(days=1))
        self._correr(19, 5)
        n = Notification.objects.get(user=self.user)
        self.assertEqual(n.title, 'Faltam 4 minutos para a meta de hoje')
        self.assertEqual(n.body, 'Uma lição curta chega para não perder a sua sequência de 4 dias.')

    def test_meta_cumprida_nao_avisa(self):
        from apps.practice.models import DailyStudyLog
        dia = timezone.localdate(datetime(2026, 11, 13, 19, 5, tzinfo=LUANDA))
        DailyStudyLog.objects.create(user=self.user, date=dia, lesson_minutes=16, goal_met_at=timezone.now())
        r = self._correr(19, 5)
        self.assertEqual((r['enviados'], r['meta_cumprida']), ([], 1))

    def test_lembrete_desligado_ou_tipo_meta_desligado(self):
        PreferenciasAvisos.objects.filter(user=self.user).update(meta=False)  # o lembrete tem interruptor próprio
        self.assertEqual(len(self._correr(19, 5)['enviados']), 1)
        Notification.objects.all().delete()
        PreferenciasAvisos.objects.filter(user=self.user).update(lembrete_ligado=False)
        self.assertEqual(self._correr(19, 5)['enviados'], [])

    def test_janela_a_meia_noite(self):
        PreferenciasAvisos.objects.filter(user=self.user).update(lembrete_hora=time(23, 55))
        self.assertEqual(len(self._correr(0, 5)['enviados']), 1)


@override_settings(**SEM_VAPID)
class NotificacoesApiTests(APITestCase):
    def setUp(self):
        self.user = _aluno('lista@example.com')
        self.outro = _aluno('lista-outro@example.com')
        self.client = _cliente(self.user)
        self.n1 = Notification.notify(self.user, 'system', title='Um', link='/user/x')
        Notification.notify(self.user, 'system', title='Dois')
        self.alheia = Notification.notify(self.outro, 'system', title='Alheia')

    def test_lista_e_contagem(self):
        d = self.client.get(NOTIF).json()
        self.assertEqual(d['count'], 2)
        self.assertEqual(d['unread'], 2)
        self.assertIsNone(d['next'])
        item = d['results'][1]
        for chave in ('id', 'kind', 'title', 'body', 'link', 'created_at', 'read'):
            self.assertIn(chave, item)
        self.assertFalse(item['read'])
        self.assertEqual(self.client.get(f'{NOTIF}unread-count/').json(), {'unread': 2})

    def test_marcar_lida_so_do_proprio(self):
        self.assertEqual(self.client.post(f'{NOTIF}{self.alheia.id}/read/').status_code, 404)
        self.alheia.refresh_from_db()
        self.assertIsNone(self.alheia.read_at)
        r = self.client.post(f'{NOTIF}{self.n1.id}/read/').json()
        self.assertTrue(r['notification']['read'])
        self.assertEqual(r['unread'], 1)
        self.assertEqual(self.client.get(f'{NOTIF}unread-count/').json(), {'unread': 1})
        self.assertEqual(_cliente(self.outro).get(f'{NOTIF}unread-count/').json(), {'unread': 1})


@override_settings(**SEM_VAPID)
class ProdutoresTests(TestCase):
    def setUp(self):
        self.user = _aluno('produtores@example.com')

    def test_pagamento_confirmado(self):
        from apps.pagamentos.signals import pagamento_confirmado
        p = SimpleNamespace(pk='p1', user=self.user, numero_recibo='PE-R-2026-000042', total_kz=15000,
                            descricao='Plano Pro - Mensal',
                            periodo_fim=datetime(2026, 12, 13, 12, 0, tzinfo=LUANDA))
        pagamento_confirmado.send(sender=None, pagamento=p)
        pagamento_confirmado.send(sender=None, pagamento=p)  # repetido: não duplica
        n = Notification.objects.get(user=self.user)
        self.assertEqual((n.kind, n.title, n.link), ('subscription', 'Pagamento recebido', '/user/billing'))
        self.assertEqual(n.body, 'Recebemos 15 000 Kz por Multicaixa Express (Plano Pro - Mensal). '
                                 'O plano está activo até 13/12/2026. Recibo n.º PE-R-2026-000042.')

    def test_renovacao_e_expiracao_mesmo_com_tudo_desligado(self):
        from apps.pagamentos.signals import lembrete_renovacao, subscricao_expirada
        PreferenciasAvisos.objects.create(user=self.user, meta=False, liga=False, certificados=False, cursos=False)
        sub = SimpleNamespace(pk='s1', user=self.user, plan=SimpleNamespace(name='Pro'))
        fim = timezone.now() + timedelta(days=3)
        lembrete_renovacao.send(sender=None, subscription=sub, tipo='D3', fim_periodo=fim)
        lembrete_renovacao.send(sender=None, subscription=sub, tipo='D3', fim_periodo=fim)
        # D0 sai quando faltam <= 24 h: o fim é hoje ou amanhã (dia de Luanda)
        lembrete_renovacao.send(sender=None, subscription=sub, tipo='D0',
                                fim_periodo=timezone.now() + timedelta(hours=20))
        subscricao_expirada.send(sender=None, subscription=sub, plano_anterior=SimpleNamespace(name='Pro'))
        titulos = list(Notification.objects.filter(user=self.user).order_by('created_at').values_list('title', flat=True))
        self.assertEqual(len(titulos), 3)
        self.assertTrue(titulos[0].startswith('A sua subscrição termina '))
        self.assertIn(titulos[1], ['A sua subscrição termina hoje', 'A sua subscrição termina amanhã'])
        self.assertEqual(titulos[2], 'O seu plano terminou')
        self.assertEqual(set(Notification.objects.values_list('link', flat=True)), {'/user/subscription'})

    def test_subida_de_liga(self):
        from apps.practice.models import LeaguePromotion, UserLeague, UserProgress
        prog = UserProgress.objects.create(user=self.user, points=990)
        prog.add_points(20, check_achievements=False)
        n = Notification.objects.get(user=self.user, kind='league')
        self.assertEqual(n.title, 'Subiu para a Liga Prata')
        self.assertEqual(n.link, '/user/laboratory/achievements#liga')
        self.assertEqual(UserLeague.objects.get(user=self.user).current_league, 'silver')
        self.assertEqual(LeaguePromotion.objects.filter(user=self.user, to_league='silver').count(), 1)
        prog.add_points(20, check_achievements=False)  # mesma liga: nada
        self.assertEqual(Notification.objects.filter(user=self.user, kind='league').count(), 1)

    def test_liga_desligada(self):
        from apps.practice.models import UserLeague, UserProgress
        PreferenciasAvisos.objects.create(user=self.user, liga=False)
        UserProgress.objects.create(user=self.user, points=1990).add_points(20, check_achievements=False)
        self.assertFalse(Notification.objects.filter(user=self.user).exists())
        self.assertEqual(UserLeague.objects.get(user=self.user).current_league, 'gold')

    def test_novo_capitulo(self):
        from apps.courses.models import Chapter, Course, CourseEnrollment, CourseSection
        prof = User.objects.create_user(email='prof-avisos@example.com', name='Prof', password='x', role='teacher')
        curso = Course.objects.create(teacher=prof, teacherName='Prof', title='Inglês Bancário',
                                      course_type='video', status='Published')
        rascunho = Course.objects.create(teacher=prof, teacherName='Prof', title='Rascunho',
                                         course_type='video', status='Draft')
        CourseEnrollment.objects.create(user=self.user, course=curso)
        CourseEnrollment.objects.create(user=self.user, course=rascunho)
        inativo = _aluno('inativo-cap@example.com')
        CourseEnrollment.objects.create(user=inativo, course=curso, is_active=False)
        sec = CourseSection.objects.create(course=curso, order=1, sectionTitle='S1')
        sec_r = CourseSection.objects.create(course=rascunho, order=1, sectionTitle='S1')

        # Aula nova ainda sem vídeo: está escondida dos alunos, não avisa.
        with self.captureOnCommitCallbacks(execute=True):
            cap = Chapter.objects.create(section=sec, order=1, title='Abrir uma conta', type='Video', content='x')
            Chapter.objects.create(section=sec_r, order=1, title='Nada', type='Text', content='x')
        self.assertFalse(Notification.objects.filter(user=self.user).exists())
        # O vídeo é confirmado pela primeira vez: a aula fica visível e os inscritos são avisados.
        with self.captureOnCommitCallbacks(execute=True):
            cap.video = 'https://cdn.exemplo.ao/videos/abrir-conta.mp4'
            cap.save()
        n = Notification.objects.get(user=self.user)
        self.assertEqual((n.kind, n.title), ('course', 'Novo capítulo em Inglês Bancário'))
        self.assertEqual(n.link, f'/user/courses/{curso.pk}/chapters/{cap.pk}')
        self.assertFalse(Notification.objects.filter(user=inativo).exists())
        # Trocar o vídeo ou mudar o título não volta a avisar (deduplicado pelo id da aula).
        with self.captureOnCommitCallbacks(execute=True):
            cap.video = 'https://cdn.exemplo.ao/videos/abrir-conta-v2.mp4'
            cap.title = 'Abrir uma conta (revisto)'
            cap.save()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        # Uma aula diferente, já com vídeo, com o mesmo título: avisa (é outra aula).
        with self.captureOnCommitCallbacks(execute=True):
            Chapter.objects.create(section=sec, order=2, title='Abrir uma conta', type='Video', content='x',
                                   video='https://cdn.exemplo.ao/videos/outra.mp4')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)
