"""
Unidades de amostra (apps/courses/amostra.py): um curso pago com definicoes.unidades_amostra = N abre
as primeiras N unidades a quem não tem o plano (aulas, questionários, progresso, recursos, lições de
laboratório e conversas ligadas a essas aulas). O resto continua fechado: 403 plano_insuficiente.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_unidades_amostra \
        --settings=core.test_settings
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses import amostra, colocacao, percurso
from apps.courses.api.student.video_courses.conteudo import codigo_opcao
from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterQuiz, ChapterResource, Course, CourseEnrollment, CourseSection, StudentQuizAttempt,
)
from apps.practice.models import ChallengeOption, PracticeChallenge, PracticeLesson, PracticeUnit, Situacao
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
V = '/api/v1/student/video-courses'
P = '/api/v1/student/practice-courses'
C = '/api/v1/practice/conversa/'


def _quiz_data():
    return {'settings': {'passingScore': 50, 'maxAttempts': 3},
            'questions': [{'id': 'q1', 'points': 1, 'question': 'Hello?',
                           'options': [{'id': 'a', 'text': 'Hi', 'isCorrect': True},
                                       {'id': 'b', 'text': 'Bye', 'isCorrect': False}]}]}


@override_settings(CONVERSA_SIMULADA=True)
class UnidadesAmostraTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.prof = User.objects.create_user(email='am-prof@example.com', name='Prof', password='x', role='teacher')
        self.admin = User.objects.create_user(email='am-admin@example.com', name='Admin', password='x', role='admin')
        self.gratis = User.objects.create_user(email='am-free@example.com', name='Free', password='x', role='student')
        self.pago = User.objects.create_user(email='am-pago@example.com', name='Pago', password='x', role='student')
        premium, _ = SubscriptionPlan.objects.get_or_create(plan_type='PREMIUM', defaults={'name': 'Premium'})
        UserSubscription.objects.update_or_create(
            user=self.pago, defaults={'plan': premium, 'status': 'ACTIVE',
                                      'expires_at': timezone.now() + timedelta(days=30)})

        # Laboratório: 3 unidades com uma lição cada.
        self.lab = Course.objects.create(
            teacher=self.prof, teacherName='Prof', title='A1.1 English Communication Skills · Laboratório',
            description='-', category='General', level='A1', course_type='practice', status='Published',
            access_level='premium', definicoes={'unidades_amostra': 2})
        self.licoes = []
        for i in range(1, 4):
            u = PracticeUnit.objects.create(course=self.lab, title=f'Unidade {i}', description='', order=i)
            licao = PracticeLesson.objects.create(unit=u, title=f'{i}A', order=1)
            ch = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question='Hello?', order=1)
            ChallengeOption.objects.create(challenge=ch, text='Hi', is_correct=True, order=1)
            ChallengeOption.objects.create(challenge=ch, text='Bye', is_correct=False, order=2)
            self.licoes.append(licao)

        # Curso em vídeo: 3 unidades (secções), cada uma com um vídeo e um questionário de revisão.
        self.curso = Course.objects.create(
            teacher=self.prof, teacherName='Prof', title='A1.1 English Communication Skills', description='-',
            category='Inglês Geral', level='A1', course_type='video', status='Published',
            access_level='premium', definicoes={'unidades_amostra': 2})
        self.seccoes, self.videos, self.quizzes = [], [], []
        for i in range(1, 4):
            s = CourseSection.objects.create(course=self.curso, sectionTitle=f'Unidade {i}', order=i)
            v = Chapter.objects.create(section=s, title=f'{i}A', content=f'texto {i}', type='Video',
                                       video=f'https://example.com/{i}.mp4', order=1,
                                       practice_lesson=self.licoes[i - 1])
            q = Chapter.objects.create(section=s, title=f'Revisão {i}', content='x', type='Quiz', order=2,
                                       quiz_data=_quiz_data())
            ChapterQuiz.objects.create(chapter=q, title=f'Revisão {i}', created_by=self.prof, max_attempts=3,
                                       passing_score=50)
            ChapterResource.objects.create(chapter=v, title=f'Guia {i}', resource_type='PDF', created_by=self.prof,
                                           external_url=f'https://example.com/guia{i}.pdf')
            self.seccoes.append(s)
            self.videos.append(v)
            self.quizzes.append(q)

        self.sit_aberta = Situacao.objects.create(
            slug='am-sit-1', nome='Conversa 1', descricao='Hello', curso=self.curso, aula=self.videos[0],
            estado=Situacao.ACTIVO, nivel='A1', tipo_conversa='guiada')
        self.sit_fechada = Situacao.objects.create(
            slug='am-sit-3', nome='Conversa 3', descricao='Hello', curso=self.curso, aula=self.videos[2],
            estado=Situacao.ACTIVO, nivel='A1', tipo_conversa='guiada')

    # -- ajudas --------------------------------------------------------------------------------

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def inscrever(self, user):
        self.entrar(user)
        r = self.client.post(f'{V}/transactions/create/', {'courseId': str(self.curso.id)}, format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def tentativa(self, quiz):
        return self.client.post(f'{V}/chapters/{quiz.id}/quiz/attempts/',
                                {'respostas': {'q1': codigo_opcao(quiz.id, 'q1', 'a')}}, format='json')

    def progresso(self, user, chapter):
        return self.client.put(
            f'{V}/users/{user.id}/progress/{self.curso.id}/update/',
            {'sections': [{'sectionId': str(chapter.section_id),
                           'chapters': [{'chapterId': str(chapter.id), 'completed': False}]}]},
            format='json')

    def assert_plano(self, r):
        self.assertEqual(r.status_code, 403, r.content)
        corpo = r.json()
        self.assertEqual(corpo.get('code') or corpo.get('codigo'), amostra.CODIGO_PLANO)

    # -- módulo --------------------------------------------------------------------------------

    def test_unidades_amostra_le_as_definicoes_com_seguranca(self):
        self.assertEqual(amostra.unidades_amostra(self.curso), 2)
        for valor, esperado in (('3', 3), (-1, 0), ('x', 0), (None, 0), (True, 0)):
            self.curso.definicoes = {'unidades_amostra': valor}
            self.assertEqual(amostra.unidades_amostra(self.curso), esperado, valor)
        self.curso.definicoes = {'unidades_amostra': 2}
        self.curso.access_level = 'free'
        self.assertEqual(amostra.unidades_amostra(self.curso), 0)

    # -- inscrição e conteúdo do curso em vídeo -------------------------------------------------

    def test_gratuito_inscreve_se_e_abre_as_unidades_da_amostra(self):
        self.inscrever(self.gratis)
        self.assertTrue(CourseEnrollment.objects.filter(user=self.gratis, course=self.curso).exists())
        for i in (0, 1):
            r = self.client.get(f'{V}/chapters/{self.videos[i].id}/')
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.json()['video'], f'https://example.com/{i + 1}.mp4')
            self.assertFalse(r.json()['bloqueada'])
            self.assertEqual(self.client.get(f'{V}/chapters/{self.quizzes[i].id}/quiz/').status_code, 200)
            self.assertEqual(self.client.get(f'{V}/chapters/{self.quizzes[i].id}/quiz/summary/').status_code, 200)
            self.assertEqual(self.client.get(f'{V}/chapters/{self.videos[i].id}/resources/').status_code, 200)
            self.assertEqual(self.client.get(f'{V}/chapters/{self.videos[i].id}/comments/').status_code, 200)
            self.assertEqual(self.tentativa(self.quizzes[i]).status_code, 201)
            self.assertEqual(self.progresso(self.gratis, self.videos[i]).status_code, 200)

    def test_gratuito_recebe_403_fora_da_amostra(self):
        self.inscrever(self.gratis)
        video, quiz = self.videos[2], self.quizzes[2]
        self.assert_plano(self.client.get(f'{V}/chapters/{video.id}/'))
        self.assert_plano(self.client.get(f'{V}/chapters/{quiz.id}/quiz/'))
        self.assert_plano(self.client.get(f'{V}/chapters/{quiz.id}/quiz/summary/'))
        self.assert_plano(self.client.get(f'{V}/chapters/{video.id}/resources/'))
        recurso = ChapterResource.objects.get(chapter=video)
        self.assert_plano(self.client.get(f'{V}/chapters/{video.id}/resources/{recurso.id}/'))
        self.assert_plano(self.client.get(f'{V}/chapters/{video.id}/comments/'))
        self.assert_plano(self.tentativa(quiz))
        self.assertFalse(StudentQuizAttempt.objects.filter(student=self.gratis).exists())
        self.assert_plano(self.progresso(self.gratis, video))
        # Um pedido que mistura uma aula aberta e uma fechada também é recusado.
        r = self.client.put(
            f'{V}/users/{self.gratis.id}/progress/{self.curso.id}/update/',
            {'sections': [{'sectionId': str(s.id), 'chapters': [{'chapterId': str(v.id), 'completed': False}]}
                          for s, v in zip(self.seccoes, self.videos)]}, format='json')
        self.assert_plano(r)
        self.assertEqual(r.json()['message'], amostra.MENSAGEM_PLANO)

    def test_detalhe_do_curso_marca_as_unidades_e_nao_mostra_conteudo_fechado(self):
        self.inscrever(self.gratis)
        r = self.client.get(f'{V}/{self.curso.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        dados = r.json()
        self.assertEqual(dados['access_info']['acesso'], 'amostra')
        self.assertEqual(dados['access_info']['unidades_amostra'], 2)
        self.assertFalse(dados['access_info']['has_access'])
        self.assertFalse(dados['data']['user_has_access'])
        self.assertEqual(dados['data']['acesso'], 'amostra')
        seccoes = dados['data']['sections']
        self.assertEqual([s['bloqueada'] for s in seccoes], [False, False, True])
        for s in seccoes[:2]:
            self.assertTrue(all('video' in c or c['type'] == 'Quiz' for c in s['chapters']))
            self.assertTrue(all(not c['bloqueada'] for c in s['chapters']))
        for c in seccoes[2]['chapters']:
            self.assertTrue(c['bloqueada'])
            for campo in ('content', 'video', 'quiz_data', 'resources_data', 'transcript', 'practice_lesson'):
                self.assertNotIn(campo, c)
        # As listas de secções e de aulas seguem as mesmas regras.
        r = self.client.get(f'{V}/{self.curso.id}/sections/')
        self.assertEqual(r.status_code, 200, r.content)
        lista = r.json()['results'] if isinstance(r.json(), dict) and 'results' in r.json() else r.json()
        fechada = [s for s in lista if s['sectionId'] == str(self.seccoes[2].id)][0]
        self.assertTrue(fechada['bloqueada'])
        self.assertTrue(all('video' not in c and 'content' not in c for c in fechada['chapters']))
        r = self.client.get(f'{V}/sections/{self.seccoes[2].id}/chapters/')
        self.assertEqual(r.status_code, 200, r.content)
        corpo = r.json()
        aulas = corpo['results'] if isinstance(corpo, dict) else corpo
        self.assertTrue(aulas and all(a['bloqueada'] and 'video' not in a for a in aulas))
        r = self.client.get(f'{V}/sections/{self.seccoes[0].id}/chapters/')
        corpo = r.json()
        aulas = corpo['results'] if isinstance(corpo, dict) else corpo
        self.assertEqual([a.get('video') for a in aulas if a['type'] == 'Video'], ['https://example.com/1.mp4'])

    def test_estado_da_inscricao(self):
        self.entrar(self.gratis)
        d = self.client.get(f'{V}/{self.curso.id}/enrollment-status/').json()['data']
        self.assertEqual((d['has_access'], d['can_enroll'], d['acesso'], d['unidades_amostra']),
                         (False, True, 'amostra', 2))

    def test_curso_sem_amostra_fica_como_antes(self):
        self.curso.definicoes = {}
        self.curso.save()
        self.entrar(self.gratis)
        r = self.client.post(f'{V}/transactions/create/', {'courseId': str(self.curso.id)}, format='json')
        self.assertEqual(r.status_code, 400)  # recusado já na validação do pedido, como antes
        self.assertFalse(CourseEnrollment.objects.filter(user=self.gratis, course=self.curso).exists())
        d = self.client.get(f'{V}/{self.curso.id}/').json()
        self.assertIsNone(d['access_info']['acesso'])
        self.assertTrue(all('chapters' not in s or not s['chapters'] for s in d['data']['sections']))
        # Mesmo inscrito (p.ex. o plano acabou), nenhuma aula abre.
        matricular_em_curso(self.gratis, self.curso)
        r = self.client.get(f'{V}/chapters/{self.videos[0].id}/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'permission_denied')
        self.assertEqual(self.client.get(f'{V}/{self.curso.id}/percurso/').status_code, 403)
        # Laboratório sem amostra: todas as lições fechadas, com a mensagem de sempre.
        self.lab.definicoes = {}
        self.lab.save()
        r = self.client.get(f'{P}/lessons/{self.licoes[0].id}/jogar/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), {'codigo': 'plano_insuficiente',
                                    'mensagem': 'Este curso requer um plano Premium ou superior.'})

    def test_pago_professor_e_administrador_vem_tudo(self):
        self.inscrever(self.pago)
        for aula in (self.videos[2], self.quizzes[2]):
            self.assertEqual(self.client.get(f'{V}/chapters/{aula.id}/').status_code, 200)
        self.assertEqual(self.tentativa(self.quizzes[2]).status_code, 201)
        self.assertEqual(self.progresso(self.pago, self.videos[2]).status_code, 200)
        d = self.client.get(f'{V}/{self.curso.id}/').json()
        self.assertEqual(d['access_info']['acesso'], 'total')
        self.assertTrue(all(not s['bloqueada'] for s in d['data']['sections']))
        self.assertEqual(d['data']['sections'][2]['chapters'][0]['video'], 'https://example.com/3.mp4')
        self.assertEqual(self.client.get(f'{P}/lessons/{self.licoes[2].id}/jogar/').status_code, 200)
        for user in (self.prof, self.admin):
            self.entrar(user)
            d = self.client.get(f'{V}/{self.curso.id}/').json()
            self.assertEqual(d['access_info']['acesso'], 'total')
            self.assertEqual(d['data']['sections'][2]['chapters'][0]['video'], 'https://example.com/3.mp4')
            self.assertFalse(d['data']['sections'][2]['bloqueada'])
            self.assertEqual(self.client.get(f'{P}/lessons/{self.licoes[2].id}/jogar/').status_code, 200)

    # -- laboratório -----------------------------------------------------------------------------

    def test_licoes_do_laboratorio(self):
        self.inscrever(self.gratis)
        for licao in self.licoes[:2]:
            r = self.client.get(f'{P}/lessons/{licao.id}/jogar/')
            self.assertEqual(r.status_code, 200, r.content)
        r = self.client.get(f'{P}/lessons/{self.licoes[2].id}/jogar/')
        self.assert_plano(r)
        self.assertEqual(r.json()['mensagem'], amostra.MENSAGEM_PLANO)
        trilho = self.client.get(f'{P}/courses/{self.lab.id}/trilho/').json()
        self.assertEqual(trilho['curso']['acesso'], 'amostra')
        self.assertEqual([u['bloqueada'] for u in trilho['unidades']], [False, False, True])
        self.assertEqual([u['licoes'][0]['bloqueada_plano'] for u in trilho['unidades']], [False, False, True])
        self.assertNotEqual(trilho['unidades'][2]['licoes'][0]['estado'], 'actual')
        unidades = self.client.get(f'{P}/courses/{self.lab.id}/units-with-progress/').json()
        self.assertEqual([u['bloqueada'] for u in unidades['units']], [False, False, True])
        self.assertEqual(unidades['course']['acesso'], 'amostra')
        cursos = {c['id']: c for c in self.client.get(f'{P}/courses/').json()}
        self.assertEqual(cursos[str(self.lab.id)]['acesso'], 'amostra')
        self.assertEqual(cursos[str(self.lab.id)]['unidades_amostra'], 2)

    # -- percurso --------------------------------------------------------------------------------

    def test_percurso_marca_passos_fechados_e_nunca_os_propoe(self):
        self.inscrever(self.gratis)
        r = self.client.get(f'{V}/{self.curso.id}/percurso/')
        self.assertEqual(r.status_code, 200, r.content)
        dados = r.json()
        self.assertEqual(dados['acesso'], 'amostra')
        self.assertEqual([u['bloqueada'] for u in dados['unidades']], [False, False, True])
        fechados = [p for p in dados['unidades'][2]['aulas'][0]['passos']]
        self.assertTrue(fechados and all(p['bloqueado'] for p in fechados))
        self.assertTrue(all(not p['bloqueado'] for u in dados['unidades'][:2] for a in u['aulas'] for p in a['passos']))
        self.assertFalse(dados['proximo']['bloqueado'])
        self.assertFalse(dados['plano_necessario'])
        # Tudo feito nas unidades da amostra: não há passo seguinte, é preciso o plano.
        from apps.courses.models import ChapterProgress, UserCourseProgress
        prog = UserCourseProgress.objects.get(user=self.gratis, course=self.curso)
        for aula in self.videos[:2] + self.quizzes[:2]:
            ChapterProgress.objects.update_or_create(user_progress=prog, chapter=aula,
                                                     defaults={'completed': True, 'video_visto': True})
        for quiz in self.quizzes[:2]:
            self.assertEqual(self.tentativa(quiz).status_code, 201)
        from apps.practice.models import ChallengeProgress
        for licao in self.licoes[:2]:
            for ch in licao.challenges.all():
                ChallengeProgress.objects.create(user=self.gratis, challenge=ch, completed=True)
        Situacao.objects.filter(pk=self.sit_aberta.pk).update(estado='rascunho')
        dados = percurso.percurso(self.gratis, self.curso)
        self.assertIsNone(dados['proximo'])
        self.assertTrue(dados['plano_necessario'])
        self.assertIsNone(percurso.proximo_passo(self.gratis))
        # Quem paga continua a ter o passo seguinte nas unidades seguintes.
        matricular_em_curso(self.pago, self.curso)
        self.assertEqual(percurso.percurso(self.pago, self.curso)['proximo']['unidade'], 'Unidade 1')

    def test_cursos_em_curso_inclui_o_curso_de_amostra(self):
        matricular_em_curso(self.gratis, self.curso)
        self.assertIn(self.curso, percurso.cursos_em_curso(self.gratis))
        self.curso.definicoes = {}
        self.curso.save()
        self.assertNotIn(self.curso, percurso.cursos_em_curso(self.gratis))

    # -- colocação -------------------------------------------------------------------------------

    def test_colocacao_inscreve_o_gratuito_no_a1_com_amostra(self):
        r = colocacao.colocar(self.gratis, 'A1')
        self.assertTrue(r['inscrito'], r)
        self.assertIsNone(r['motivo'])
        self.assertEqual(r['curso']['id'], str(self.curso.id))
        self.curso.definicoes = {}
        self.curso.save()
        CourseEnrollment.objects.filter(user=self.gratis).delete()
        self.assertEqual(colocacao.colocar(self.gratis, 'A1')['motivo'], 'plano')

    # -- conversas com o tutor -------------------------------------------------------------------

    def _conversa(self, slug):
        return self.client.post(f'{C}sessoes/', {'situacao': slug, 'nivel': 'A1', 'correcao': 'suave',
                                                 'area': 'general'}, format='json')

    def test_conversa_ligada_a_aula_fechada_nao_comeca(self):
        self.inscrever(self.gratis)
        self.assert_plano(self._conversa(self.sit_fechada.slug))
        r = self._conversa(self.sit_aberta.slug)
        self.assertNotEqual((r.json() or {}).get('codigo'), amostra.CODIGO_PLANO, r.content)
        situacoes = {s['id']: s for s in self.client.get(f'{C}preparar/').json()['situacoes']}
        self.assertTrue(situacoes['am-sit-3']['bloqueada'])
        self.assertFalse(situacoes['am-sit-1']['bloqueada'])
        # A conversa no fim de uma aula fechada (fala da aula) também não abre.
        self.assert_plano(self.client.get(f'{V}/chapters/{self.videos[2].id}/fala/'))
        # Quem paga começa a conversa da unidade 3.
        self.inscrever(self.pago)
        r = self._conversa(self.sit_fechada.slug)
        self.assertNotEqual((r.json() or {}).get('codigo'), amostra.CODIGO_PLANO, r.content)
