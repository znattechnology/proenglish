"""
Carregar as unidades de docs/conteudo num curso (manage.py carregar_unidades_curso):
aulas, questionário, lições de laboratório ligadas às aulas e conversas, sem estragar o que os
alunos já fizeram.
"""
import io
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.courses import carregar_unidades as cu
from apps.courses import percurso
from apps.courses.models import Chapter, ChapterQuiz, Course, CourseSection, StudentQuizAttempt
from apps.practice.models import ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit, Situacao

User = get_user_model()
CONTEUDO = os.path.normpath(os.path.join(settings.BASE_DIR, '..', '..', 'docs', 'conteudo'))
U1 = os.path.join(CONTEUDO, 'c1', 'unidade-01')
U2 = os.path.join(CONTEUDO, 'c1', 'unidade-02')
R1 = os.path.join(CONTEUDO, 'c1', 'revisao-1')


class CarregarUnidadesTests(TestCase):

    def setUp(self):
        self.prof = User.objects.create_user(email='cu-prof@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='cu-aluno@example.com', name='Ana', password='x', role='student')
        self.curso = self.criar('CU- C1.1', 'video')
        self.lab = self.criar('CU- Lab C1.1', 'practice')

    def criar(self, titulo, tipo, professor=None):
        professor = professor or self.prof
        return Course.objects.create(teacher=professor, teacherName=professor.name, title=titulo, description='x',
                                     category='General', level='C1', course_type=tipo, status='Published',
                                     access_level='free')

    def carregar(self, *pastas, **opcoes):
        saida = io.StringIO()
        opcoes.setdefault('laboratorio', str(self.lab.pk))
        call_command('carregar_unidades_curso', str(self.curso.pk), *pastas, stdout=saida, **opcoes)
        return saida.getvalue()

    def test_carrega_aulas_questionario_laboratorio_e_conversas(self):
        saida = self.carregar(U1, R1)
        self.assertIn('2 pastas carregadas', saida)
        seccoes = list(CourseSection.objects.filter(course=self.curso).order_by('order'))
        self.assertEqual([s.sectionTitle for s in seccoes], ['Unidade 1 — Making the case', 'Revisão 1 (unidades 1 a 5)'])
        aulas = list(Chapter.objects.filter(section=seccoes[0]).order_by('order'))
        self.assertEqual([a.title[:2] for a in aulas[:6]], ['1A', '1B', '1C', '1D', '1E', '1F'])
        self.assertEqual(aulas[0].title, '1A — What we need is…')
        self.assertEqual((aulas[0].type, aulas[0].duracao_s), ('Video', 13 * 60))
        self.assertTrue(aulas[0].content.startswith('No fim, o aluno consegue'))
        self.assertNotIn('Objectivo da unidade', aulas[0].content)
        # O questionário é a última aula da secção e fica activo, com as 12 perguntas.
        quiz = aulas[-1]
        self.assertEqual((quiz.type, len(aulas)), ('Quiz', 7))
        self.assertEqual(len(quiz.quiz_data['questions']), 12)
        self.assertTrue(ChapterQuiz.objects.get(chapter=quiz).is_active)
        # Laboratório: 7 lições; cada aula ligada à sua e a de reciclagem ligada ao questionário.
        unidade = PracticeUnit.objects.get(course=self.lab, title='Unidade 1 — Making the case')
        licoes = list(PracticeLesson.objects.filter(unit=unidade).order_by('order'))
        self.assertEqual([l.title.split(' ')[0] for l in licoes], ['1A', '1B', '1C', '1D', '1E', '1F', '1R'])
        self.assertEqual(PracticeChallenge.objects.filter(lesson__unit=unidade).count(), 93)
        for aula, licao in zip(aulas[:6], licoes[:6]):
            self.assertEqual(aula.practice_lesson_id, licao.id)
        self.assertEqual(quiz.practice_lesson_id, licoes[6].id)
        # Conversas ligadas às aulas.
        guiada = Situacao.objects.get(curso=self.curso, tipo_conversa='guiada', aula__section=seccoes[0])
        self.assertEqual(guiada.aula.title[:2], '1C')
        # O percurso do aluno junta tudo: 6 vídeos + 6 lições + questionário + reciclagem + 2 conversas.
        dados = percurso.percurso(self.aluno, self.curso)
        self.assertEqual(sum(len(a['passos']) for a in dados['unidades'][0]['aulas']), 16)
        self.assertEqual(dados['proximo']['titulo'], '1A — What we need is…')

    def test_correr_outra_vez_nao_duplica_nem_recria(self):
        self.carregar(U1)
        antes = (set(Chapter.objects.values_list('id', flat=True)), set(PracticeChallenge.objects.values_list('id', flat=True)),
                 set(PracticeLesson.objects.values_list('id', flat=True)), Situacao.objects.count())
        saida = self.carregar(U1)
        depois = (set(Chapter.objects.values_list('id', flat=True)), set(PracticeChallenge.objects.values_list('id', flat=True)),
                  set(PracticeLesson.objects.values_list('id', flat=True)), Situacao.objects.count())
        self.assertEqual(antes, depois)
        self.assertNotIn('ficou como estava', saida)

    def test_nao_substitui_o_que_os_alunos_ja_fizeram(self):
        self.carregar(U1)
        licao = PracticeLesson.objects.get(title__startswith='1A')
        primeiro = PracticeChallenge.objects.filter(lesson=licao).order_by('order').first()
        ChallengeProgress.objects.create(user=self.aluno, challenge=primeiro, completed=True)
        PracticeChallenge.objects.filter(pk=primeiro.pk).update(question='Alterado pelo professor')
        quiz = ChapterQuiz.objects.get(chapter__section__course=self.curso)
        StudentQuizAttempt.objects.create(student=self.aluno, chapter_quiz=quiz, score=5, max_score=12, attempt_number=1)
        capitulo = quiz.chapter
        capitulo.quiz_data = dict(capitulo.quiz_data, title='Alterado')
        capitulo.save()

        saida = self.carregar(U1)
        self.assertIn('lição 1A já tem respostas de alunos', saida)
        self.assertIn('questionário já tem tentativas', saida)
        self.assertTrue(PracticeChallenge.objects.filter(pk=primeiro.pk, question='Alterado pelo professor').exists())
        self.assertEqual(Chapter.objects.get(pk=capitulo.pk).quiz_data['title'], 'Alterado')
        # Com --forcar, substitui.
        self.carregar(U1, forcar=True)
        self.assertFalse(PracticeChallenge.objects.filter(pk=primeiro.pk).exists())
        self.assertNotEqual(Chapter.objects.get(pk=capitulo.pk).quiz_data['title'], 'Alterado')

    def test_vídeo_ja_enviado_mantem_a_duracao(self):
        self.carregar(U1)
        Chapter.objects.filter(title__startswith='1A').update(video='https://exemplo.test/v.mp4', duracao_s=700)
        self.carregar(U1)
        aula = Chapter.objects.get(title__startswith='1A')
        self.assertEqual((aula.video, aula.duracao_s), ('https://exemplo.test/v.mp4', 700))

    def test_sem_laboratorio_carrega_so_o_curso_em_video(self):
        self.carregar(U1, laboratorio=None)
        self.assertEqual(Chapter.objects.filter(section__course=self.curso).count(), 7)
        self.assertFalse(PracticeUnit.objects.exists())
        self.assertFalse(Chapter.objects.filter(practice_lesson__isnull=False).exists())

    def test_verificar_nao_escreve_e_nao_precisa_de_curso(self):
        saida = io.StringIO()
        call_command('carregar_unidades_curso', '-', U1, U2, verificar=True, stdout=saida)
        self.assertIn('2 pastas válidas', saida.getvalue())
        self.assertFalse(CourseSection.objects.exists())

    def test_recusas(self):
        with self.assertRaisesMessage(CommandError, 'Curso em vídeo não encontrado'):
            call_command('carregar_unidades_curso', str(self.lab.pk), U1)
        outro = User.objects.create_user(email='cu-outro@example.com', name='Rui', password='x', role='teacher')
        alheio = self.criar('CU- Lab alheio', 'practice', professor=outro)
        with self.assertRaisesMessage(CommandError, 'mesmo professor'):
            self.carregar(U1, laboratorio=str(alheio.pk))
        with self.assertRaisesMessage(CommandError, 'repetidos entre as pastas'):
            self.carregar(U1, U1)
        with self.assertRaisesMessage(CommandError, 'falta guioes.md'):
            self.carregar(CONTEUDO)
        # Nada ficou a meio.
        self.assertFalse(CourseSection.objects.exists())

    def test_erro_a_meio_desfaz_tudo(self):
        dados = cu.ler_pasta(U2)
        import json
        slug = json.load(open(dados['tutor'], encoding='utf-8'))['cenarios'][0]['slug']
        Situacao.objects.create(slug=slug, nome='x', descricao='x', estado=Situacao.ACTIVO,
                                curso=self.criar('CU- Outro', 'video'))
        with self.assertRaises(CommandError):
            self.carregar(U1, U2)
        self.assertFalse(CourseSection.objects.filter(course=self.curso).exists())
        self.assertFalse(PracticeUnit.objects.exists())
