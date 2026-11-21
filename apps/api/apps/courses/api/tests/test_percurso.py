"""
Percurso do curso e passo seguinte (apps/courses/percurso.py): a ligação entre a aula em vídeo, o
laboratório e as conversas com o tutor.

    ./venv/bin/python manage.py test apps.courses.api.tests.test_percurso --settings=core.test_settings
"""
import json
import tempfile
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses import percurso
from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import Chapter, ChapterProgress, Course, CourseSection, UserCourseProgress
from apps.practice.models import (
    ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit, Situacao, VapiSession,
)

User = get_user_model()
V = '/api/v1/student/video-courses'
PROF = '/api/v1/teacher/situacoes/'


class Base(APITestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.prof = User.objects.create_user(email='pc-prof@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='pc-aluno@example.com', name='Ana', password='x', role='student')
        self.outro = User.objects.create_user(email='pc-outro@example.com', name='Rui', password='x', role='student')
        self.curso = self.criar_curso('PC- Curso C1')
        self.u1 = CourseSection.objects.create(course=self.curso, sectionTitle='Unit 1', order=1)
        self.u2 = CourseSection.objects.create(course=self.curso, sectionTitle='Unit 2', order=2)
        self.a1 = self.criar_aula(self.u1, '1A — What we need is…', 1, duracao_s=780)
        self.a2 = self.criar_aula(self.u1, '1C — I take your point', 2)
        self.a3 = self.criar_aula(self.u2, '2A — It would appear that…', 1)
        # Laboratório: um curso de prática com uma lição ligada à aula 1A.
        self.lab = Course.objects.create(teacher=self.prof, teacherName='Prof', title='PC- Lab', description='x',
                                         category='General', level='C1', course_type='practice',
                                         status='Published', access_level='free')
        unidade = PracticeUnit.objects.create(course=self.lab, title='U1', order=1)
        self.licao = PracticeLesson.objects.create(unit=unidade, title='Lab 1A', order=1)
        self.exercicios = []
        for i in range(3):
            ex = PracticeChallenge.objects.create(lesson=self.licao, type='SELECT', question=f'Q{i}', order=i + 1)
            ChallengeOption.objects.create(challenge=ex, text='certa', is_correct=True, order=1)
            ChallengeOption.objects.create(challenge=ex, text='errada', is_correct=False, order=2)
            self.exercicios.append(ex)
        self.a1.practice_lesson = self.licao
        self.a1.save(update_fields=['practice_lesson'])
        # Conversas: a guiada e a livre depois da 1C (a livre criada primeiro, para testar a ordem).
        self.livre = self.criar_situacao('pc-livre', 'The sceptical director', self.a2, 'livre', ordem=1)
        self.guiada = self.criar_situacao('pc-guiada', 'Convince me', self.a2, 'guiada', ordem=2)
        matricular_em_curso(self.aluno, self.curso)

    def criar_curso(self, titulo):
        return Course.objects.create(teacher=self.prof, teacherName='Prof', title=titulo, description='x',
                                     category='General', level='C1', course_type='video',
                                     status='Published', access_level='free')

    def criar_aula(self, seccao, titulo, ordem, **extra):
        return Chapter.objects.create(section=seccao, title=titulo, content='x', type='Video', order=ordem,
                                      video='https://x.ao/v.mp4', **extra)

    def criar_situacao(self, slug, nome, aula, tipo, ordem=1, **extra):
        dados = dict(nome=nome, descricao='Uma conversa de treino com o tutor.', papel_tutor='Colega',
                     curso=self.curso, nivel='C1', duracao_min=10, estado=Situacao.ACTIVO, criado_por=self.prof,
                     ordem=ordem, aula=aula, tipo_conversa=tipo, extras={'minutos_sugeridos': 7})
        dados.update(extra)
        return Situacao.objects.create(slug=slug, **dados)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def ver_aula(self, aula, user=None):
        progresso, _ = UserCourseProgress.objects.get_or_create(
            user=user or self.aluno, course=self.curso,
            defaults={'enrollmentDate': timezone.now(), 'overallProgress': 0.0})
        ChapterProgress.objects.update_or_create(user_progress=progresso, chapter=aula,
                                                 defaults={'video_visto': True, 'completed': True})

    def fazer_licao(self, user=None):
        for ex in self.exercicios:
            ChallengeProgress.objects.update_or_create(user=user or self.aluno, challenge=ex,
                                                       defaults={'completed': True})

    def conversar(self, situacao, estado=VapiSession.STATUS_AVALIADA, user=None):
        return VapiSession.objects.create(
            session_id=f'pc-{situacao.slug}-{VapiSession.objects.count()}', user=user or self.aluno, level='C1',
            domain='general', duration_minutes=5, status=estado, situation=situacao.slug)

    def passos(self, dados):
        return [p for u in dados['unidades'] for a in u['aulas'] for p in a['passos']]


class PercursoTests(Base):

    def test_ordem_dos_passos_e_primeiro_actual(self):
        dados = percurso.percurso(self.aluno, self.curso)
        passos = self.passos(dados)
        self.assertEqual([p['tipo'] for p in passos],
                         ['aula', 'pratica', 'aula', 'conversa', 'conversa', 'aula'])
        # A guiada vem antes da livre, mesmo com a ordem ao contrário.
        self.assertEqual([p.get('tipo_conversa') for p in passos if p['tipo'] == 'conversa'], ['guiada', 'livre'])
        self.assertEqual([p['estado'] for p in passos], ['actual'] + ['por_fazer'] * 5)
        self.assertEqual(dados['proximo']['titulo'], '1A — What we need is…')
        self.assertEqual(dados['proximo']['minutos'], 13)
        self.assertEqual((dados['feitos'], dados['total']), (0, 6))
        self.assertEqual([u['titulo'] for u in dados['unidades']], ['Unit 1', 'Unit 2'])
        self.assertNotIn('feito', passos[0])

    def test_depois_do_video_o_passo_seguinte_e_o_laboratorio(self):
        self.ver_aula(self.a1)
        dados = percurso.percurso(self.aluno, self.curso)
        self.assertEqual(dados['proximo']['tipo'], 'pratica')
        self.assertEqual(dados['proximo']['licao_id'], self.licao.id)
        self.assertEqual(dados['proximo']['curso_pratica_id'], str(self.lab.id))
        self.assertEqual(dados['feitos'], 1)

    def test_laboratorio_so_conta_com_todos_os_exercicios(self):
        self.ver_aula(self.a1)
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.exercicios[0], completed=True)
        self.assertEqual(percurso.percurso(self.aluno, self.curso)['proximo']['tipo'], 'pratica')
        self.fazer_licao()
        self.assertEqual(percurso.percurso(self.aluno, self.curso)['proximo']['titulo'], '1C — I take your point')

    def test_conversa_so_conta_se_foi_avaliada(self):
        self.ver_aula(self.a1)
        self.fazer_licao()
        self.ver_aula(self.a2)
        proximo = percurso.percurso(self.aluno, self.curso)['proximo']
        self.assertEqual((proximo['tipo'], proximo['situacao'], proximo['minutos']), ('conversa', 'pc-guiada', 7))
        # Uma chamada que não ligou, ou curta de mais para ser avaliada, não conta.
        self.conversar(self.guiada, VapiSession.STATUS_NAO_LIGOU)
        self.conversar(self.guiada, VapiSession.STATUS_SEM_AVALIACAO)
        self.assertEqual(percurso.percurso(self.aluno, self.curso)['proximo']['situacao'], 'pc-guiada')
        self.conversar(self.guiada, VapiSession.STATUS_A_AVALIAR)
        self.assertEqual(percurso.percurso(self.aluno, self.curso)['proximo']['situacao'], 'pc-livre')

    def test_conversa_de_outro_aluno_nao_conta(self):
        self.conversar(self.guiada, user=self.outro)
        passos = self.passos(percurso.percurso(self.aluno, self.curso))
        self.assertEqual([p['estado'] for p in passos if p['tipo'] == 'conversa'], ['por_fazer', 'por_fazer'])

    def test_situacoes_de_exame_rascunho_e_sem_aula_ficam_de_fora(self):
        self.criar_situacao('pc-exame', 'Exame', self.a3, '', extras={'exame': True})
        self.criar_situacao('pc-rascunho', 'Rascunho', self.a3, 'guiada', estado=Situacao.RASCUNHO)
        self.criar_situacao('pc-solta', 'Solta', None, '')
        passos = self.passos(percurso.percurso(self.aluno, self.curso))
        self.assertEqual(sorted(p['situacao'] for p in passos if p['tipo'] == 'conversa'), ['pc-guiada', 'pc-livre'])

    def test_licao_que_os_alunos_nao_veem_nao_e_passo(self):
        vazia = PracticeLesson.objects.create(unit=self.licao.unit, title='Vazia', order=2)
        self.a3.practice_lesson = vazia
        self.a3.save(update_fields=['practice_lesson'])
        passos = self.passos(percurso.percurso(self.aluno, self.curso))
        self.assertEqual([p['tipo'] for p in passos if p['aula_id'] == str(self.a3.id)], ['aula'])

    def test_tudo_feito_sem_passo_seguinte(self):
        for aula in (self.a1, self.a2, self.a3):
            self.ver_aula(aula)
        self.fazer_licao()
        self.conversar(self.guiada)
        self.conversar(self.livre)
        dados = percurso.percurso(self.aluno, self.curso)
        self.assertIsNone(dados['proximo'])
        self.assertEqual((dados['feitos'], dados['total']), (6, 6))


class PraticaAnteriorTests(Base):
    """O aviso «pratique primeiro»: o laboratório da aula anterior por fazer (recomenda, não bloqueia)."""

    def aulas(self, dados):
        return {a['id']: a for u in dados['unidades'] for a in u['aulas']}

    def test_aula_seguinte_traz_o_laboratorio_por_fazer_da_anterior(self):
        self.ver_aula(self.a1)
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertIsNone(aulas[str(self.a1.id)]['pratica_anterior'])
        self.assertEqual(aulas[str(self.a2.id)]['pratica_anterior'], {
            'aula_id': str(self.a1.id), 'aula_titulo': '1A — What we need is…', 'licao_id': self.licao.id,
            'curso_pratica_id': str(self.lab.id), 'minutos': percurso.MINUTOS_PRATICA})
        # Só a aula imediatamente anterior: a 2A não fala do laboratório da 1A.
        self.assertIsNone(aulas[str(self.a3.id)]['pratica_anterior'])

    def test_tambem_sem_ter_visto_o_video_e_nunca_bloqueia_a_aula(self):
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertEqual(aulas[str(self.a2.id)]['pratica_anterior']['licao_id'], self.licao.id)
        self.assertFalse(aulas[str(self.a2.id)]['bloqueada'])

    def test_laboratorio_feito_tira_o_aviso(self):
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.exercicios[0], completed=True)
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertIsNotNone(aulas[str(self.a2.id)]['pratica_anterior'])  # meio feito ainda conta
        self.fazer_licao()
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertIsNone(aulas[str(self.a2.id)]['pratica_anterior'])

    def test_passa_de_uma_unidade_para_a_outra(self):
        self.a1.practice_lesson = None
        self.a1.save(update_fields=['practice_lesson'])
        self.a2.practice_lesson = self.licao
        self.a2.save(update_fields=['practice_lesson'])
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertEqual(aulas[str(self.a3.id)]['pratica_anterior']['aula_titulo'], '1C — I take your point')

    def test_laboratorio_fechado_pelo_plano_nao_gera_aviso(self):
        from unittest import mock
        with mock.patch.object(percurso, '_licao_fechada', return_value=True):
            aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertIsNone(aulas[str(self.a2.id)]['pratica_anterior'])

    def test_cada_aluno_ve_o_seu(self):
        self.fazer_licao(user=self.outro)
        aulas = self.aulas(percurso.percurso(self.aluno, self.curso))
        self.assertIsNotNone(aulas[str(self.a2.id)]['pratica_anterior'])


class ApiTests(Base):

    def test_percurso_traz_a_pratica_anterior(self):
        self.entrar(self.aluno)
        r = self.client.get(f'{V}/{self.curso.id}/percurso/')
        aula2 = next(a for u in r.data['unidades'] for a in u['aulas'] if a['id'] == str(self.a2.id))
        self.assertEqual(str(aula2['pratica_anterior']['licao_id']), str(self.licao.id))

    def test_percurso_do_curso(self):
        self.entrar(self.aluno)
        r = self.client.get(f'{V}/{self.curso.id}/percurso/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['curso'], {'id': str(self.curso.id), 'titulo': 'PC- Curso C1'})
        self.assertEqual(r.data['proximo']['estado'], 'actual')
        self.assertEqual(r.data['total'], 6)

    def test_percurso_exige_inscricao_e_autenticacao(self):
        self.assertEqual(self.client.get(f'{V}/{self.curso.id}/percurso/').status_code, 401)
        self.entrar(self.outro)
        self.assertEqual(self.client.get(f'{V}/{self.curso.id}/percurso/').status_code, 403)

    def test_percurso_de_curso_por_publicar_404(self):
        self.curso.status = 'Draft'
        self.curso.save(update_fields=['status'])
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{V}/{self.curso.id}/percurso/').status_code, 404)

    def test_proximo_passo_escolhe_o_curso_mais_recente(self):
        segundo = self.criar_curso('PC- Segundo')
        seccao = CourseSection.objects.create(course=segundo, sectionTitle='Unit 1', order=1)
        self.criar_aula(seccao, 'Aula do segundo', 1)
        matricular_em_curso(self.aluno, segundo)
        agora = timezone.now()
        for curso, quando in ((self.curso, agora - timedelta(days=3)), (segundo, agora)):
            UserCourseProgress.objects.update_or_create(
                user=self.aluno, course=curso,
                defaults={'enrollmentDate': agora, 'overallProgress': 0.0, 'lastAccessedTimestamp': quando})
        self.entrar(self.aluno)
        r = self.client.get(f'{V}/percurso/proximo/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['proximo']['curso']['titulo'], 'PC- Segundo')
        self.assertEqual(r.data['proximo']['passo']['titulo'], 'Aula do segundo')
        self.assertEqual((r.data['proximo']['feitos'], r.data['proximo']['total']), (0, 1))

    def test_proximo_passo_fica_no_curso_do_que_o_aluno_acabou(self):
        segundo = self.criar_curso('PC- Segundo')
        seccao = CourseSection.objects.create(course=segundo, sectionTitle='Unit 1', order=1)
        self.criar_aula(seccao, 'Aula do segundo', 1)
        matricular_em_curso(self.aluno, segundo)
        agora = timezone.now()
        for curso, quando in ((self.curso, agora - timedelta(days=3)), (segundo, agora)):
            UserCourseProgress.objects.update_or_create(
                user=self.aluno, course=curso,
                defaults={'enrollmentDate': agora, 'overallProgress': 0.0, 'lastAccessedTimestamp': quando})
        self.entrar(self.aluno)
        # Sem contexto: o curso mais recente. Com a lição ou a conversa do outro curso: esse curso.
        self.assertEqual(self.client.get(f'{V}/percurso/proximo/').data['proximo']['curso']['titulo'], 'PC- Segundo')
        for parametros in ({'licao': str(self.licao.id)}, {'situacao': 'pc-guiada'}):
            r = self.client.get(f'{V}/percurso/proximo/', parametros)
            self.assertEqual(r.data['proximo']['curso']['titulo'], 'PC- Curso C1', parametros)
        # Contexto inválido ou de um curso em que o aluno não está: ignora-se, sem erro.
        alheio = self.criar_curso('PC- Alheio')
        seccao = CourseSection.objects.create(course=alheio, sectionTitle='U', order=1)
        aula = self.criar_aula(seccao, 'Alheia', 1)
        Situacao.objects.create(slug='pc-alheia', nome='x', descricao='x', curso=alheio, aula=aula,
                                estado=Situacao.ACTIVO)
        for parametros in ({'licao': 'nao-e-id'}, {'situacao': 'nao-existe'}, {'situacao': 'pc-alheia'}):
            r = self.client.get(f'{V}/percurso/proximo/', parametros)
            self.assertEqual(r.status_code, 200, parametros)
            self.assertEqual(r.data['proximo']['curso']['titulo'], 'PC- Segundo', parametros)

    def test_opcoes_do_professor_trazem_as_aulas_de_cada_curso(self):
        # As aulas vêm pela ordem do curso, sem os questionários e só dos cursos do professor.
        Chapter.objects.create(section=self.u1, title='Quiz U1', type='Quiz', order=9)
        alheio = self.criar_curso('PC- De outro professor')
        outro_prof = User.objects.create_user(email='pc-prof2@example.com', name='P2', password='x', role='teacher')
        Course.objects.filter(pk=alheio.pk).update(teacher=outro_prof)
        self.criar_aula(CourseSection.objects.create(course=alheio, sectionTitle='U', order=1), 'Alheia', 1)
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}opcoes/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data['aulas']), {str(self.curso.id)})
        self.assertEqual([(a['titulo'], a['unidade']) for a in r.data['aulas'][str(self.curso.id)]],
                         [('1A — What we need is…', 'Unit 1'), ('1C — I take your point', 'Unit 1'),
                          ('2A — It would appear that…', 'Unit 2')])

    def test_proximo_passo_sem_cursos_e_null(self):
        self.entrar(self.outro)
        r = self.client.get(f'{V}/percurso/proximo/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['proximo'])

    def test_proximo_passo_exige_autenticacao(self):
        self.assertEqual(self.client.get(f'{V}/percurso/proximo/').status_code, 401)

    def test_lista_de_conversas_traz_a_aula_e_o_tipo(self):
        self.entrar(self.aluno)
        r = self.client.get('/api/v1/practice/conversa/preparar/')
        self.assertEqual(r.status_code, 200)
        guiada = next(s for s in r.data['situacoes'] if s['id'] == 'pc-guiada')
        self.assertEqual(guiada['aula'], {'id': str(self.a2.id), 'titulo': '1C — I take your point',
                                          'unidade': 'Unit 1'})
        self.assertEqual(guiada['tipo_conversa'], 'guiada')
        geral = next(s for s in r.data['situacoes'] if s['curso'] is None)
        self.assertIsNone(geral['aula'])
        self.assertIsNone(geral['tipo_conversa'])


class ProfessorTests(Base):

    def setUp(self):
        super().setUp()
        self.entrar(self.prof)

    def test_ligar_a_conversa_a_uma_aula(self):
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'aula': str(self.a1.id), 'tipo_conversa': 'livre'},
                              format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['aula'], {'id': str(self.a1.id), 'titulo': '1A — What we need is…'})
        self.assertEqual(r.data['tipo_conversa'], 'livre')
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'aula': None, 'tipo_conversa': ''}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['aula'])
        self.assertIsNone(r.data['tipo_conversa'])

    def test_aula_de_outro_curso_ou_de_outro_professor_400(self):
        outro_curso = self.criar_curso('PC- Outro')
        seccao = CourseSection.objects.create(course=outro_curso, sectionTitle='U', order=1)
        aula = self.criar_aula(seccao, 'Outra', 1)
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'aula': str(aula.id)}, format='json')
        self.assertEqual(r.status_code, 400)
        alheio = User.objects.create_user(email='pc-alheio@example.com', name='X', password='x', role='teacher')
        curso_alheio = Course.objects.create(teacher=alheio, teacherName='X', title='PC- Alheio', description='x',
                                             category='General', level='C1', course_type='video',
                                             status='Published', access_level='free')
        seccao = CourseSection.objects.create(course=curso_alheio, sectionTitle='U', order=1)
        aula = self.criar_aula(seccao, 'Alheia', 1)
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'aula': str(aula.id)}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'aula': 'nao-e-um-id'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.guiada.refresh_from_db()
        self.assertEqual(self.guiada.aula_id, self.a2.id)

    def test_tipo_de_conversa_invalido_400(self):
        r = self.client.patch(f'{PROF}{self.guiada.pk}/', {'tipo_conversa': 'outra'}, format='json')
        self.assertEqual(r.status_code, 400)


class CarregarConversasTests(Base):

    def ficheiro(self, cenarios):
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump({'cenarios': cenarios}, f)
        f.close()
        return f.name

    def cenario(self, slug, tipo, depois, **extra):
        dados = {'slug': slug, 'nome': f'C1 Unit 1 · {slug}', 'tipo': tipo, 'depois_da_aula': depois,
                 'descricao': 'O tutor é um colega.', 'papel_tutor': 'Jordan, colega.', 'nivel': 'C1',
                 'duracao_min': 10, 'correccao': 'suave', 'area': 'general', 'frases': ['What we need is…'],
                 'extras': {'brief': 'Guided practice.', 'primeira_fala': 'Hi, {nome}!', 'guiao': ['Why?'],
                            'frases': [{'en': 'What we need is time.', 'pt': 'Precisamos de tempo.'}],
                            'palavras': ['what'], 'minutos_sugeridos': 7},
                 'criterios': ['Usa clivadas.'] if tipo == 'livre' else None}
        dados.update(extra)
        return dados

    def test_carrega_e_liga_as_aulas_pelo_codigo(self):
        caminho = self.ficheiro([self.cenario('c1-u1-guiada', 'guiada', '1C'),
                                 self.cenario('c1-u1-livre', 'livre', '1A')])
        saida = StringIO()
        call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=saida)
        self.assertIn('2 conversas carregadas', saida.getvalue())
        guiada = Situacao.objects.get(slug='c1-u1-guiada')
        livre = Situacao.objects.get(slug='c1-u1-livre')
        self.assertEqual((guiada.aula_id, guiada.tipo_conversa), (self.a2.id, 'guiada'))
        self.assertEqual((livre.aula_id, livre.tipo_conversa), (self.a1.id, 'livre'))
        self.assertEqual(guiada.estado, Situacao.ACTIVO)
        self.assertEqual(guiada.curso_id, self.curso.id)
        self.assertEqual(guiada.extras['minutos_sugeridos'], 7)
        self.assertEqual(livre.extras['criterios'], ['Usa clivadas.'])
        self.assertNotIn('criterios', guiada.extras)
        # Correr outra vez actualiza, não duplica.
        call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=StringIO())
        self.assertEqual(Situacao.objects.filter(slug__startswith='c1-u1-').count(), 2)
        # E entram no percurso do aluno.
        passos = self.passos(percurso.percurso(self.aluno, self.curso))
        self.assertIn('c1-u1-livre', [p.get('situacao') for p in passos])

    def test_sem_aula_avisa_ou_falha(self):
        caminho = self.ficheiro([self.cenario('c1-u9-guiada', 'guiada', '9C')])
        saida = StringIO()
        call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=saida)
        self.assertIn('Sem aula', saida.getvalue())
        self.assertIsNone(Situacao.objects.get(slug='c1-u9-guiada').aula_id)
        Situacao.objects.filter(slug='c1-u9-guiada').delete()
        with self.assertRaises(CommandError):
            call_command('carregar_conversas_curso', str(self.curso.id), caminho, exigir_aulas=True,
                         stdout=StringIO())
        self.assertFalse(Situacao.objects.filter(slug='c1-u9-guiada').exists())

    def test_codigo_nao_confunde_1a_com_1ab_nem_com_11a(self):
        self.criar_aula(self.u2, '11A — Another', 5)
        from apps.courses.management.commands.carregar_conversas_curso import aula_do_codigo
        aulas = list(Chapter.objects.filter(section__course=self.curso))
        self.assertEqual(aula_do_codigo(aulas, '1A').id, self.a1.id)
        self.assertIsNone(aula_do_codigo(aulas, '1'))
        self.assertIsNone(aula_do_codigo(aulas, ''))

    def test_situacao_de_outro_curso_e_dados_invalidos(self):
        outro = self.criar_curso('PC- Outro')
        Situacao.objects.create(slug='c1-u1-guiada', nome='x', descricao='x', curso=outro, estado=Situacao.ACTIVO)
        caminho = self.ficheiro([self.cenario('c1-u1-guiada', 'guiada', '1C')])
        with self.assertRaises(CommandError):
            call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=StringIO())
        caminho = self.ficheiro([self.cenario('c1-u1-x', 'outra', '1C')])
        with self.assertRaises(CommandError):
            call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=StringIO())
        caminho = self.ficheiro([self.cenario('c1-u1-y', 'guiada', '1C', duracao_min=7)])
        with self.assertRaises(CommandError):
            call_command('carregar_conversas_curso', str(self.curso.id), caminho, stdout=StringIO())
        self.assertFalse(Situacao.objects.filter(slug__in=['c1-u1-x', 'c1-u1-y']).exists())
