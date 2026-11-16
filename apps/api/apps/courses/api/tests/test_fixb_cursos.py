"""
Regressões da revisão dos cursos em vídeo (certificados, progresso, tempo de vídeo, questionários,
frases da aula, níveis, recálculo das notas).

    ./venv/bin/python manage.py test apps.courses.api.tests.test_fixb_cursos --settings=core.test_settings
"""
import importlib
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.apps import apps as django_apps
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.api.student.video_courses.conteudo import codigo_opcao
from apps.courses import tempo_video, transcricao
from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseCertificate, FraseAula, StudentCourseGrade,
    StudentQuizAttempt, TentativasExtraQuestionario, UserCourseProgress, VideoWatchLog,
)
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.practice.limite_licoes import hoje_luanda
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
V = '/api/v1/student/video-courses'
PROF = '/api/v1/teacher'
FRASES = (('Could you send me the report by Friday?', 'frase'),
          ('Please check the pressure before you start the pump.', 'frase'), ('pressure', 'palavra'))

QUIZ_DATA = {'questions': [{'id': 'q1', 'text': 'Pick A', 'points': 1,
                            'options': [{'id': 'a', 'text': 'A', 'isCorrect': True}, {'id': 'b', 'text': 'B'}]}]}


class Base(APITestCase):
    """Curso em vídeo publicado com uma aula (com vídeo e 3 frases aprovadas) e um aluno Premium
    Plus inscrito. Sem Claude nem Vapi (nada aqui os chama)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        plano = SubscriptionPlan.objects.update_or_create(plan_type='PREMIUM_PLUS', defaults=dict(
            name='Premium Plus', description='-', monthly_price=Decimal('0'), daily_speaking_minutes=10,
            ai_tutor=True, certificates=True))[0]
        self.prof = User.objects.create_user(email='fxb-prof@example.com', name='FXB- Prof', password='x',
                                             role='teacher')
        self.outro_prof = User.objects.create_user(email='fxb-outro@example.com', name='FXB- Outro', password='x',
                                                   role='teacher')
        self.aluno = User.objects.create_user(email='fxb-aluno@example.com', name='FXB- Aluna', password='x',
                                              role='student')
        UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=plano, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30),
            daily_speaking_minutes_used=0, last_reset_date=hoje_luanda()))
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='FXB- Curso', description='x',
                                           category='Industry English', level='B1', course_type='video',
                                           status='Published', access_level='free')
        self.sec = self.curso.sections.create(sectionTitle='S1', order=1)
        self.aula = Chapter.objects.create(section=self.sec, title='Pedir um relatório', content='Pedir com prazo.',
                                           type='Video', order=1, video='https://x.ao/v.mp4')
        for i, (texto, tipo) in enumerate(FRASES):
            FraseAula.objects.create(chapter=self.aula, texto=texto, traducao='pt', tipo=tipo,
                                     estado=FraseAula.APROVADA, ordem=i)
        matricular_em_curso(self.aluno, self.curso)
        self.entrar(self.aluno)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def concluir(self):
        prog = UserCourseProgress.objects.get(user=self.aluno, course=self.curso)
        ChapterProgress.objects.update_or_create(user_progress=prog, chapter=self.aula, defaults={'completed': True})
        UserCourseProgress.objects.get(pk=prog.pk).update_overall_progress()


class FixB(Base):

    def url_prog(self, prefixo=V):
        return f'{prefixo}/users/{self.aluno.id}/progress/{self.curso.id}/update/'

    def marcar(self, completed=True, prefixo=V, **extra):
        return self.client.put(self.url_prog(prefixo), {**extra, 'sections': [{'sectionId': str(self.sec.id), 'chapters': [
            {'chapterId': str(self.aula.id), 'completed': completed}]}]}, format='json')

    def aberta_ha(self, segundos):
        cache.set(tempo_video._chave_aberta(self.aluno.pk, self.aula.pk),
                  (timezone.now() - timedelta(seconds=segundos)).timestamp(), 3600)

    def com_quiz(self, max_attempts=2):
        Chapter.objects.filter(pk=self.aula.pk).update(quiz_data=QUIZ_DATA, quiz_enabled=True)
        return ChapterQuiz.objects.create(chapter=self.aula, title='Q', is_active=True, max_attempts=max_attempts,
                                          passing_score=70, created_by=self.prof)

    def responder(self, opcao):
        return self.client.post(f'{V}/chapters/{self.aula.id}/quiz/attempts/', {'respostas': {'q1': codigo_opcao(self.aula.id, 'q1', opcao)}},
                                format='json')

    # -- 1. certificado com nota antiga -------------------------------------
    def test_nota_antiga_elegivel_nao_emite_certificado_sem_exame(self):
        StudentCourseGrade.objects.create(user=self.aluno, course=self.curso, final_grade_percentage=90,
                                          final_grade_letter='A', is_eligible_for_certificate=True,
                                          calculation_version=1)
        r = self.marcar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UserCourseProgress.objects.get(user=self.aluno, course=self.curso).overallProgress, 100.0)
        self.assertFalse(CourseCertificate.objects.filter(user=self.aluno).exists())
        g = StudentCourseGrade.objects.get(user=self.aluno, course=self.curso)
        self.assertEqual(g.calculation_version, GradeCalculatorService.CALCULATION_VERSION)
        self.assertFalse(g.is_eligible_for_certificate)
        self.assertFalse(g.eligibility_details['oral_exam']['met'])

    def test_emitir_se_elegivel_recalcula_a_nota_passada(self):
        from apps.courses.certificados import emitir_se_elegivel
        self.concluir()
        falsa = StudentCourseGrade(user=self.aluno, course=self.curso, final_grade_percentage=95,
                                   final_grade_letter='A', is_eligible_for_certificate=True, calculation_version=1)
        self.assertIsNone(emitir_se_elegivel(self.aluno, self.curso, grade=falsa))
        self.assertFalse(CourseCertificate.objects.filter(user=self.aluno).exists())

    def test_notas_todas_recalcula_versao_antiga(self):
        StudentCourseGrade.objects.create(user=self.aluno, course=self.curso, final_grade_percentage=90,
                                          final_grade_letter='A', is_eligible_for_certificate=True,
                                          calculation_version=1)
        self.concluir()
        CourseCertificate.objects.filter(user=self.aluno).delete()
        r = self.client.get(f'{V}/grades/all/')
        self.assertEqual(r.status_code, 200)
        linha = r.data['data']['courses'][0]
        self.assertFalse(linha['is_eligible_for_certificate'])
        self.assertEqual(StudentCourseGrade.objects.get(user=self.aluno, course=self.curso).calculation_version,
                         GradeCalculatorService.CALCULATION_VERSION)

    # -- 2. rotas antigas de progresso / tentativas ---------------------------
    def test_rota_antiga_de_progresso_aplica_as_regras(self):
        Chapter.objects.filter(pk=self.aula.pk).update(duracao_s=600)
        self.com_quiz()
        for prefixo in ('/api/v1/courses', '/api/v1/courses/v1', '/api/v1/courses/v2'):
            r = self.marcar(prefixo=prefixo)
            # vídeo de 600 s por ver: não se marca como visto
            self.assertEqual(r.status_code, 400, prefixo)
        self.assertFalse(ChapterProgress.objects.filter(chapter=self.aula, completed=True).exists())

    def test_rota_antiga_nao_mexe_em_aulas_de_outro_curso(self):
        outro = Course.objects.create(teacher=self.prof, teacherName='Prof', title='FXB- Outro', description='x',
                                      category='Industry English', level='B1', course_type='video',
                                      status='Published', access_level='free')
        r = self.client.put(f'/api/v1/courses/users/{self.aluno.id}/progress/{outro.id}/update/', {
            'sections': [{'sectionId': str(self.sec.id), 'chapters': [{'chapterId': str(self.aula.id), 'completed': True}]}]},
            format='json')
        self.assertEqual(r.status_code, 403)  # não inscrito no outro curso
        self.assertFalse(ChapterProgress.objects.filter(chapter=self.aula, completed=True).exists())

    def test_rota_antiga_de_tentativas_nao_aceita_nota_do_browser(self):
        self.com_quiz()
        r = self.client.post(f'/api/v1/courses/chapters/{self.aula.id}/quiz/attempts/',
                             {'score': 100, 'max_score': 100, 'is_completed': True, 'is_passed': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(StudentQuizAttempt.objects.filter(student=self.aluno, is_passed=True).exists())

    # -- 3. tempo de vídeo ------------------------------------------------------
    def test_primeiro_envio_sem_abrir_a_aula_nao_credita(self):
        Chapter.objects.filter(pk=self.aula.pk).update(duracao_s=600, percentagem_vista=80)
        r = self.marcar(chapter_id=str(self.aula.id), watched_seconds=99999)
        self.assertEqual(r.status_code, 400)  # vídeo por ver
        self.assertEqual(tempo_video.segundos_vistos(self.aluno, self.aula), 0)

    def test_credito_limitado_ao_tempo_desde_a_abertura(self):
        Chapter.objects.filter(pk=self.aula.pk).update(duracao_s=600, percentagem_vista=80)
        self.assertEqual(self.client.get(f'{V}/chapters/{self.aula.id}/').status_code, 200)
        self.aberta_ha(120)
        r = self.client.put(self.url_prog(), {'chapter_id': str(self.aula.id), 'watched_seconds': 99999,
                                              'sections': []}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(120 <= r.data['segundos_creditados'] <= 120 + tempo_video.FOLGA_SEGUNDOS + 2)
        self.assertFalse(r.data['aula_concluida'])
        # logo a seguir: o envio anterior é a referência, quase nada passou
        r = self.client.put(self.url_prog(), {'chapter_id': str(self.aula.id), 'watched_seconds': 99999,
                                              'sections': []}, format='json')
        self.assertLessEqual(r.data['segundos_creditados'], tempo_video.FOLGA_SEGUNDOS + 2)

    def test_aula_concluida_vem_do_estado_antes_e_depois(self):
        Chapter.objects.filter(pk=self.aula.pk).update(duracao_s=100, percentagem_vista=80)
        self.aberta_ha(200)
        r = self.marcar(chapter_id=str(self.aula.id), watched_seconds=99999)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['segundos_creditados'], 100)
        self.assertTrue(r.data['aula_concluida'])
        r = self.marcar(chapter_id=str(self.aula.id), watched_seconds=10)
        self.assertFalse(r.data['aula_concluida'])  # já estava concluída

    def test_abrir_a_aula_regista_a_hora(self):
        self.assertIsNone(tempo_video.aberta_em(self.aluno, self.aula))
        self.client.get(f'{V}/chapters/{self.aula.id}/')
        self.assertIsNotNone(tempo_video.aberta_em(self.aluno, self.aula))

    # -- 4. questionário sem saída ---------------------------------------------
    def test_esgotar_tentativas_conclui_a_aula_com_o_video_visto(self):
        self.com_quiz(max_attempts=2)
        prog = UserCourseProgress.objects.get(user=self.aluno, course=self.curso)
        ChapterProgress.objects.update_or_create(user_progress=prog, chapter=self.aula, defaults={'video_visto': True})
        r = self.responder('b')
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data['data']['aula_concluida'])
        r = self.responder('b')
        self.assertEqual(r.data['data']['tentativas_restantes'], 0)
        self.assertTrue(r.data['data']['aula_concluida'])
        self.assertTrue(ChapterProgress.objects.get(user_progress=prog, chapter=self.aula).completed)
        # a falta continua a contar na nota
        g = GradeCalculatorService(self.aluno, self.curso).calcular_sem_guardar()
        self.assertEqual(g.quiz_passed, 0)

    def test_esgotar_tentativas_sem_ver_o_video_nao_conclui(self):
        self.com_quiz(max_attempts=1)
        r = self.responder('b')
        self.assertFalse(r.data['data']['aula_concluida'])
        self.assertFalse(ChapterProgress.objects.filter(chapter=self.aula, completed=True).exists())

    def test_professor_da_mais_tentativas(self):
        quiz = self.com_quiz(max_attempts=1)
        self.responder('b')
        self.assertEqual(self.responder('a').status_code, 400)  # sem tentativas
        self.entrar(self.prof)
        lista = self.client.get(f'{PROF}/alunos/{self.aluno.id}/questionarios/')
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(lista.data['questionarios'][0]['restantes'], 0)
        url = f'{PROF}/alunos/{self.aluno.id}/questionarios/{quiz.id}/tentativas/'
        self.assertEqual(self.client.post(url, {'extra': 9}, format='json').status_code, 400)
        r = self.client.post(url, {'extra': 1}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['limite'], r.data['restantes']), (2, 1))
        self.entrar(self.outro_prof)
        self.assertEqual(self.client.post(url, {'extra': 1}, format='json').status_code, 404)
        self.entrar(self.aluno)
        self.assertEqual(self.client.post(url, {'extra': 1}, format='json').status_code, 403)
        r = self.responder('a')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data['data']['is_passed'])
        self.assertEqual(TentativasExtraQuestionario.objects.get(user=self.aluno, chapter_quiz=quiz).extra, 1)

    # -- 5. tempos das frases ----------------------------------------------------
    def test_relocalizar_limpa_frases_que_ja_nao_estao_na_transcricao(self):
        FraseAula.objects.filter(chapter=self.aula).update(inicio=1.0, fim=3.0)
        Chapter.objects.filter(pk=self.aula.pk).update(transcript=json.dumps([
            {'start': 10, 'end': 14, 'text': 'Could you send me the report by Friday?'}]))
        aula = Chapter.objects.get(pk=self.aula.pk)
        transcricao.relocalizar_frases(aula)
        f1 = FraseAula.objects.get(chapter=aula, texto__startswith='Could you')
        f2 = FraseAula.objects.get(chapter=aula, texto__startswith='Please check')
        self.assertEqual((f1.inicio, f1.fim), (10.0, 14.0))
        self.assertEqual((f2.inicio, f2.fim), (None, None))

    def test_patch_do_texto_relocaliza_a_frase(self):
        Chapter.objects.filter(pk=self.aula.pk).update(transcript=json.dumps([
            {'start': 2, 'end': 5, 'text': 'Good morning team.'},
            {'start': 20, 'end': 24, 'text': 'We will close the valve at noon.'}]))
        f = FraseAula.objects.get(chapter=self.aula, texto__startswith='Could you')
        FraseAula.objects.filter(pk=f.pk).update(inicio=2.0, fim=5.0)
        self.entrar(self.prof)
        r = self.client.patch(f'{PROF}/frases/{f.pk}/', {'texto': 'We will close the valve at noon.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['inicio'], r.data['fim']), (20.0, 24.0))
        r = self.client.patch(f'{PROF}/frases/{f.pk}/', {'texto': 'Nothing like this in the video.'}, format='json')
        self.assertEqual((r.data['inicio'], r.data['fim']), (None, None))
        # com tempos enviados, ficam os do professor
        r = self.client.patch(f'{PROF}/frases/{f.pk}/', {'texto': 'Good morning team.', 'inicio': 1, 'fim': 3},
                              format='json')
        self.assertEqual((r.data['inicio'], r.data['fim']), (1.0, 3.0))

    # -- 6. pequenos -----------------------------------------------------------
    def test_migracao_0028_normaliza_valores_antigos_por_linha(self):
        mig = importlib.import_module('apps.courses.migrations.0028_niveis_cefr')
        ids = {}
        for nivel in ('intermediate', 'b1', ' Advanced ', 'qualquer'):
            c = Course.objects.create(teacher=self.prof, teacherName='P', title=f'FXB- {nivel}', description='x',
                                      category='Industry English', level='A2', course_type='video')
            Course.objects.filter(pk=c.pk).update(level=nivel)
            ids[nivel] = c.pk
        mig.para_cefr(django_apps, None)
        niveis = {k: Course.objects.get(pk=v).level for k, v in ids.items()}
        self.assertEqual(niveis, {'intermediate': 'B1', 'b1': 'B1', ' Advanced ': 'B2', 'qualquer': 'A2'})

    def test_aprovar_e_apagar_frases_recalcula_as_notas(self):
        antes = GradeCalculatorService(self.aluno, self.curso).calculate_and_save().phrases_total
        self.entrar(self.prof)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(f'{PROF}/aulas/{self.aula.id}/frases/', {'texto': 'Close the valve.'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(StudentCourseGrade.objects.get(user=self.aluno, course=self.curso).phrases_total, antes + 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(f'{PROF}/frases/{r.data["id"]}/').status_code, 204)
        self.assertEqual(StudentCourseGrade.objects.get(user=self.aluno, course=self.curso).phrases_total, antes)

    @override_settings(RECALCULO_NOTAS_EM_FUNDO=True)
    def test_recalculo_das_definicoes_corre_numa_thread(self):
        from apps.courses.api.teacher.cursos import _recalcular_notas
        with mock.patch('apps.courses.recalculo.threading.Thread') as thread, \
                mock.patch('apps.courses.recalculo.recalcular_notas_agora') as agora:
            _recalcular_notas(self.curso.pk)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
        agora.assert_not_called()
        from apps.courses import recalculo
        recalculo._a_correr.clear()

    def test_definicoes_mostram_o_peso_do_exame(self):
        from apps.courses.models import CourseGradingConfig
        cfg, _ = CourseGradingConfig.objects.get_or_create(course=self.curso)
        cfg.exam_weight, cfg.phrases_weight, cfg.conversation_weight, cfg.study_weight = 50, 25, 15, 10
        cfg.save()
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}/cursos/{self.curso.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['definicoes']['peso_exame'], 50)

    def test_ficheiro_local_grande_nao_e_transcrito(self):
        with tempfile.TemporaryDirectory() as raiz:
            Path(raiz, 'videos').mkdir()
            Path(raiz, 'videos', 'grande.mp4').write_bytes(b'x' * 2048)
            with override_settings(MEDIA_ROOT=raiz, MEDIA_URL='/media/', TRANSCRICAO_MAX_BYTES=1024):
                with self.assertRaises(transcricao.ErroTranscricao):
                    transcricao.ficheiro_do_video('/media/videos/grande.mp4', raiz)
            with override_settings(MEDIA_ROOT=raiz, MEDIA_URL='/media/', TRANSCRICAO_MAX_BYTES=4096):
                self.assertTrue(transcricao.ficheiro_do_video('/media/videos/grande.mp4', raiz).is_file())

    def test_transcricoes_em_simultaneo_limitadas_a_duas(self):
        self.assertEqual(transcricao.TRANSCRICOES_EM_SIMULTANEO._initial_value, 2)
