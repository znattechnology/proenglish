"""
Fluência, fase 1: questionários em aulas de vídeo, prática e conversa na nota do curso, e ligar
uma aula a uma lição de prática no editor.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_fluencia_fase1
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseGradingConfig, CourseSection, StudentCourseGrade,
)
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.practice.models import (
    ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit, Situacao, VapiSession,
)
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
V = '/api/v1/student/video-courses'
PROF = '/api/v1/teacher/'


def quiz_data(n=3, aprovacao=70):
    return {
        'title': 'Quiz', 'settings': {'passingScore': aprovacao, 'maxAttempts': 5},
        'questions': [
            {'id': f'q{i}', 'points': 10, 'question': f'P{i}?', 'correctOptionId': 'a',
             'options': [{'id': 'a', 'text': 'Certa', 'isCorrect': True},
                         {'id': 'b', 'text': 'Errada', 'isCorrect': False}]}
            for i in range(1, n + 1)
        ],
    }


class Base(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='f1a-prof@example.com', name='Prof', password='x', role='teacher')
        self.outro_prof = User.objects.create_user(email='f1a-outro@example.com', name='Outro', password='x',
                                                   role='teacher')
        self.aluno = User.objects.create_user(email='f1a-aluno@example.com', name='Aluno', password='x',
                                              role='student')
        UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=SubscriptionPlan.objects.get(plan_type='PREMIUM'), status='ACTIVE',
            expires_at=timezone.now() + timedelta(days=30)))
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='F1A Curso',
                                           description='x', category='Industry English', course_type='video',
                                           status='Published', access_level='free')
        self.sec = CourseSection.objects.create(course=self.curso, sectionTitle='S1', order=1)
        # Aula como as do editor novo: tipo Video, com vídeo e um questionário activo.
        with self.captureOnCommitCallbacks(execute=True):
            self.aula = Chapter.objects.create(section=self.sec, title='Aula com quiz', content='', type='Video',
                                               order=1, video='https://x.ao/v.mp4', quiz_enabled=True,
                                               quiz_data=quiz_data())
        self.outra = Chapter.objects.create(section=self.sec, title='Aula simples', content='', type='Video',
                                            order=2, video='https://x.ao/w.mp4')
        matricular_em_curso(self.aluno, self.curso)
        self.auth(self.aluno)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def marcar(self, aula, completed=True):
        corpo = {'sections': [{'sectionId': str(aula.section_id),
                               'chapters': [{'chapterId': str(aula.id), 'completed': completed}]}]}
        return self.client.put(f'{V}/users/{self.aluno.id}/progress/{self.curso.id}/update/', corpo, format='json')

    def responder(self, aula, certas):
        respostas = {f'q{i}': ('a' if i <= certas else 'b') for i in range(1, 4)}
        return self.client.post(f'{V}/chapters/{aula.id}/quiz/attempts/', {'respostas': respostas}, format='json')

    def concluida(self, aula):
        return ChapterProgress.objects.filter(chapter=aula, user_progress__user=self.aluno, completed=True).exists()

    def pratica(self, dono=None, publicado=True, n=4):
        curso = Course.objects.create(teacher=dono or self.prof, teacherName='Prof', title='F1A Prática',
                                      description='x', category='Oil & Gas', course_type='practice',
                                      status='Published' if publicado else 'Draft', access_level='free')
        unidade = PracticeUnit.objects.create(course=curso, title='U1', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L1', order=1)
        desafios = [PracticeChallenge.objects.create(lesson=licao, type='SELECT', question=f'Q{i}', order=i)
                    for i in range(1, n + 1)]
        return curso, unidade, licao, desafios


# 1 ---------------------------------------------------------------------------
class QuestionarioEmAulaDeVideoTests(Base):

    def test_aula_de_video_com_questionario_devolve_o_quiz(self):
        self.assertTrue(ChapterQuiz.objects.get(chapter=self.aula).is_active)
        r = self.client.get(f'{V}/chapters/{self.aula.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        d = d.get('data', d)
        self.assertEqual(d['type'], 'Video')
        self.assertTrue(d['quiz_enabled'])
        self.assertEqual(len(d['quiz_data']['questions']), 3)
        self.assertNotIn('isCorrect', str(d['quiz_data']))

    def test_ver_o_video_nao_conclui_sem_passar(self):
        r = self.marcar(self.aula)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(self.concluida(self.aula))
        cap = [c for s in r.data['data']['sections'] for c in s['chapters'] if c['chapterId'] == str(self.aula.id)][0]
        self.assertEqual((cap['completed'], cap['video_visto']), (False, True))
        # Falhar não conclui; passar conclui (o vídeo já estava visto).
        self.assertEqual(self.responder(self.aula, 0).status_code, 201)
        self.assertFalse(self.concluida(self.aula))
        r = self.responder(self.aula, 3)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['data']['aula_concluida'])
        self.assertTrue(self.concluida(self.aula))

    def test_passar_sem_ver_o_video_nao_conclui(self):
        r = self.responder(self.aula, 3)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()['data']['aula_concluida'])
        self.assertFalse(self.concluida(self.aula))
        # Ver o vídeo depois conclui.
        self.marcar(self.aula)
        self.assertTrue(self.concluida(self.aula))

    def test_aula_sem_questionario_conclui_ao_ver(self):
        self.marcar(self.outra)
        self.assertTrue(self.concluida(self.outra))
        self.marcar(self.outra, completed=False)
        self.assertFalse(self.concluida(self.outra))

    def test_aula_do_tipo_quiz_conclui_ao_passar(self):
        with self.captureOnCommitCallbacks(execute=True):
            q = Chapter.objects.create(section=self.sec, title='Quiz', content='', type='Quiz', order=3,
                                       quiz_data=quiz_data())
        r = self.responder(q, 3)
        self.assertTrue(r.json()['data']['aula_concluida'])
        self.assertTrue(self.concluida(q))


# 2 ---------------------------------------------------------------------------
class PraticaNaNotaTests(Base):

    def setUp(self):
        super().setUp()
        CourseGradingConfig.objects.update_or_create(course=self.curso, defaults=dict(
            quiz_enabled=False, practice_enabled=True, conversation_enabled=False))
        self.p_curso, _, self.licao, self.desafios = self.pratica()

    def test_aula_ligada_a_licao_conta_na_pratica(self):
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=self.licao)
        dados = GradeCalculatorService(self.aluno, self.curso).calculate_practice_scores()
        self.assertEqual((dados['count'], dados['completed']), (4, 0))

    def test_completar_desafio_recalcula_a_nota(self):
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=self.licao)
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.desafios[0], completed=True)
        nota = StudentCourseGrade.objects.get(user=self.aluno, course=self.curso)
        self.assertEqual((nota.practice_count, nota.practice_completed), (4, 1))
        self.assertEqual(nota.practice_score, 25.0)

    def test_licao_do_questionario_tambem_conta_e_nao_duplica(self):
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=self.licao)
        ChapterQuiz.objects.filter(chapter=self.aula).update(practice_lesson=self.licao)
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.desafios[0], completed=True)
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.desafios[1], completed=True)
        nota = StudentCourseGrade.objects.get(user=self.aluno, course=self.curso)
        self.assertEqual((nota.practice_count, nota.practice_completed), (4, 2))

    def test_trigger_de_classe(self):
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=self.licao)
        cp = ChallengeProgress.objects.create(user=self.aluno, challenge=self.desafios[0], completed=True)
        notas = GradeCalculatorService.trigger_update_on_practice_complete(self.aluno, cp)
        self.assertEqual([n.course_id for n in notas], [self.curso.id])

    def test_licao_nao_ligada_nao_mexe_na_nota(self):
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.desafios[0], completed=True)
        self.assertFalse(StudentCourseGrade.objects.filter(user=self.aluno, course=self.curso).exists())


# 3 ---------------------------------------------------------------------------
class ConversaDoCursoTests(Base):

    def setUp(self):
        super().setUp()
        CourseGradingConfig.objects.update_or_create(course=self.curso, defaults=dict(
            quiz_enabled=True, practice_enabled=False, conversation_enabled=True,
            require_conversation_if_available=True, min_conversation_score=60))
        self.outro_curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='F1A Outro',
                                                 description='x', category='Industry English',
                                                 course_type='video', status='Published', access_level='free')
        matricular_em_curso(self.aluno, self.outro_curso)

    def sessao(self, sid, nota, **extra):
        return VapiSession.objects.create(session_id=f'f1a-{sid}', user=self.aluno, level='B1', domain='general',
                                          duration_minutes=5, overall_score=nota, **extra)

    def test_sem_situacoes_a_conversa_nao_e_requisito(self):
        self.sessao('geral', 90)  # conversa geral, de nível igual: não conta
        calc = GradeCalculatorService(self.aluno, self.curso)
        conv = calc.calculate_conversation_scores()
        self.assertEqual((conv['sessions'], conv['has_requirement']), (0, False))
        nota = calc.calculate_and_save()
        self.assertNotIn('conversation', nota.weight_info.get('active_components', []))
        self.assertTrue(nota.eligibility_details['conversation_score'].get('skipped'))

    def test_so_contam_as_conversas_deste_curso(self):
        Situacao.objects.create(slug='f1a-sit', nome='Reunião', descricao='x', curso=self.curso,
                                estado=Situacao.ACTIVO)
        Situacao.objects.create(slug='f1a-sit-outro', nome='Outra', descricao='x', curso=self.outro_curso,
                                estado=Situacao.ACTIVO)
        self.sessao('a', 80, situation='f1a-sit')
        self.sessao('b', 60, full_session_data={'config': {'curso_id': str(self.curso.id)}})
        self.sessao('c', 10, situation='f1a-sit-outro')
        self.sessao('d', 20)
        conv = GradeCalculatorService(self.aluno, self.curso).calculate_conversation_scores()
        self.assertEqual((conv['sessions'], conv['score'], conv['has_requirement']), (2, 70.0, True))

    def test_com_situacao_activa_e_sem_conversa_bloqueia_o_certificado(self):
        Situacao.objects.create(slug='f1a-sit2', nome='Reunião', descricao='x', curso=self.curso,
                                estado=Situacao.ACTIVO)
        nota = GradeCalculatorService(self.aluno, self.curso).calculate_and_save()
        self.assertFalse(nota.eligibility_details['conversation_score']['met'])

    def test_avaliar_conversa_recalcula_so_o_curso_dela(self):
        from apps.practice.signals import recalcular_notas_conversa
        Situacao.objects.create(slug='f1a-sit3', nome='Reunião', descricao='x', curso=self.curso,
                                estado=Situacao.ACTIVO)
        s = self.sessao('e', 75, situation='f1a-sit3')
        StudentCourseGrade.objects.filter(user=self.aluno).delete()
        recalcular_notas_conversa(s)
        self.assertEqual(list(StudentCourseGrade.objects.filter(user=self.aluno).values_list('course_id', flat=True)),
                         [self.curso.id])
        # Uma conversa geral não mexe em nenhuma nota.
        StudentCourseGrade.objects.filter(user=self.aluno).delete()
        recalcular_notas_conversa(self.sessao('f', 75))
        self.assertFalse(StudentCourseGrade.objects.filter(user=self.aluno).exists())


# 4 ---------------------------------------------------------------------------
class LigarAulaALicaoTests(Base):

    def setUp(self):
        super().setUp()
        self.p_curso, self.unidade, self.licao, self.desafios = self.pratica()
        self.auth(self.prof)

    def test_lista_as_licoes_do_professor(self):
        _, _, alheia, _ = self.pratica(dono=self.outro_prof)
        r = self.client.get(f'{PROF}cursos/{self.curso.id}/licoes-pratica/')
        self.assertEqual(r.status_code, 200, r.content)
        ids = [l['id'] for c in r.data['cursos'] for u in c['unidades'] for l in u['licoes']]
        self.assertIn(str(self.licao.id), ids)
        self.assertNotIn(str(alheia.id), ids)
        self.assertEqual(r.data['cursos'][0]['unidades'][0]['titulo'], 'U1')

    def test_ligar_e_desligar(self):
        r = self.client.patch(f'{PROF}aulas/{self.outra.id}/', {'licao_pratica': str(self.licao.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['licao_pratica']['id'], str(self.licao.id))
        self.assertEqual(r.data['licao_pratica']['curso']['titulo'], 'F1A Prática')
        self.outra.refresh_from_db()
        self.assertEqual(self.outra.practice_lesson_id, self.licao.id)
        r = self.client.get(f'{PROF}cursos/{self.curso.id}/estrutura/')
        aulas = {a['id']: a for s in r.data['seccoes'] for a in s['aulas']}
        self.assertEqual(aulas[str(self.outra.id)]['licao_pratica']['id'], str(self.licao.id))
        r = self.client.patch(f'{PROF}aulas/{self.outra.id}/', {'licao_pratica': None}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.data['licao_pratica'])

    def test_recusa_licao_de_outro_professor(self):
        _, _, alheia, _ = self.pratica(dono=self.outro_prof)
        r = self.client.patch(f'{PROF}aulas/{self.outra.id}/', {'licao_pratica': str(alheia.id)}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('licao_pratica', r.data['details'])
        r = self.client.patch(f'{PROF}aulas/{self.outra.id}/', {'licao_pratica': 'xyz'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_aluno_ve_a_licao_so_com_curso_de_pratica_publicado(self):
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=self.licao)
        self.auth(self.aluno)
        d = self.client.get(f'{V}/chapters/{self.outra.id}/').json()
        self.assertEqual(d.get('data', d)['practice_lesson'], str(self.licao.id))
        Course.objects.filter(id=self.p_curso.id).update(status='Draft')
        d = self.client.get(f'{V}/chapters/{self.outra.id}/').json()
        self.assertIsNone(d.get('data', d)['practice_lesson'])

    def test_licao_ligada_abre_fora_de_ordem(self):
        from apps.practice.acesso_licoes import erro_acesso_licao
        segunda = PracticeLesson.objects.create(unit=self.unidade, title='L2', order=2)
        for i in range(1, 4):
            PracticeChallenge.objects.create(lesson=segunda, type='SELECT', question=f'Q{i}', order=i)
        self.assertEqual(erro_acesso_licao(self.aluno, segunda)['codigo'], 'licao_bloqueada')
        Chapter.objects.filter(id=self.outra.id).update(practice_lesson=segunda)
        self.assertIsNone(erro_acesso_licao(self.aluno, segunda))


class VideoVistoPeloServidorTests(Base):
    """Um vídeo com duração conhecida só conta como visto com os segundos registados no servidor."""

    def setUp(self):
        super().setUp()
        self.outra.duracao_s = 100
        self.outra.percentagem_vista = 80
        self.outra.save()

    def test_marcar_sem_ver_e_recusado(self):
        r = self.marcar(self.outra)
        self.assertEqual(r.status_code, 400)
        self.assertIn('80%', str(r.data))
        self.assertFalse(self.concluida(self.outra))

    def test_marcar_depois_de_ver_conta(self):
        from apps.courses.models import UserCourseProgress, VideoWatchLog
        VideoWatchLog.objects.create(user=self.aluno, chapter=self.outra, date=timezone.localdate(), seconds=85)
        r = self.marcar(self.outra)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(self.concluida(self.outra))
        self.assertTrue(UserCourseProgress.objects.filter(user=self.aluno, course=self.curso).exists())

    def test_video_sem_duracao_continua_a_aceitar_o_browser(self):
        self.outra.duracao_s = None
        self.outra.save()
        r = self.marcar(self.outra)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(self.concluida(self.outra))
