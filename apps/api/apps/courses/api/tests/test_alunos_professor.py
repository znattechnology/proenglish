"""
Área do professor: alunos e resultados (alunos.py): permissões, âmbito (só os alunos dos
cursos do professor), classificação do estado, privacidade do CSV e contas dos resultados.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import (
    Chapter, ChapterProgress, Course, CourseEnrollment, CourseSection, StudentCourseGrade, UserCourseProgress,
)
from apps.practice.models import (
    ChallengeAttempt, ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit,
    UserProgress,
)
from apps.users.models import User

PROF = '/api/v1/teacher/'


class Base(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.agora = timezone.now()
        self.prof = self.utilizador('prof-alunos@example.com', 'Prof Ana', 'teacher')
        self.outro_prof = self.utilizador('outro-alunos@example.com', 'Prof Rui', 'teacher')
        self.admin = self.utilizador('admin-alunos@example.com', 'Admin', 'admin')

        self.video = Course.objects.create(
            teacher=self.prof, teacherName='Prof Ana', title='Inglês para Plataformas', description='x',
            category='Industry English', level='Beginner', course_type='video', status='Published')
        seccao = CourseSection.objects.create(course=self.video, sectionTitle='S1', order=1)
        self.cap1 = Chapter.objects.create(section=seccao, title='A1', content='x', type='Video', video='https://example.com/a1.mp4', order=1)
        self.cap2 = Chapter.objects.create(section=seccao, title='A2', content='x', type='Video', video='https://example.com/a2.mp4', order=2)

        self.pratica = Course.objects.create(
            teacher=self.prof, teacherName='Prof Ana', title='Inglês no Terminal', description='x',
            category='Oil & Gas', level='Intermediate', course_type='practice', status='Published')
        unidade = PracticeUnit.objects.create(course=self.pratica, title='U1', description='', order=1)
        licao = PracticeLesson.objects.create(unit=unidade, title='L1', order=1)
        self.ex_dificil = PracticeChallenge.objects.create(
            lesson=licao, type='SELECT', question='Choose the correct safety word for the muster point', order=1)
        self.ex_facil = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question='Hello', order=2)
        for ch in (self.ex_dificil, self.ex_facil):
            ChallengeOption.objects.create(challenge=ch, text='Certa', is_correct=True, order=1)

        self.curso_outro = Course.objects.create(
            teacher=self.outro_prof, teacherName='Prof Rui', title='Curso do Rui', description='x',
            category='Business English', level='Beginner', course_type='video', status='Published')

        # activo: inscrito há 20 dias, concluiu um capítulo há 2 dias
        self.activo = self.utilizador('activo@example.com', 'Bruno Activo')
        self.inscrever(self.activo, self.video, dias=20)
        up = UserCourseProgress.objects.create(user=self.activo, course=self.video, enrollmentDate=self.agora)
        cp = ChapterProgress.objects.create(user_progress=up, chapter=self.cap1, completed=True)
        ChapterProgress.objects.filter(pk=cp.pk).update(completed_at=self.agora - timedelta(days=2))

        # em risco (teve actividade): respondeu há 15 dias no curso de prática
        self.risco = self.utilizador('risco@example.com', 'Carla Risco', phone='+244923000000')
        self.responder(self.risco, self.ex_dificil, [True] + [False] * 4, dias=15)
        self.responder(self.risco, self.ex_facil, [True] * 5, dias=15)

        # em risco (nunca activo): inscrito há 15 dias
        self.parado = self.utilizador('parado@example.com', 'Dina Parada')
        self.inscrever(self.parado, self.video, dias=15)

        # novo: inscrito há 3 dias, sem actividade
        self.novo = self.utilizador('novo@example.com', 'Eva Nova')
        self.inscrever(self.novo, self.video, dias=3)

        # aluno só do outro professor
        self.alheio = self.utilizador('alheio@example.com', 'Zé Alheio')
        self.inscrever(self.alheio, self.curso_outro, dias=1)

    def utilizador(self, email, nome, role='student', **extra):
        return User.objects.create_user(email=email, name=nome, password='x12345678', role=role, **extra)

    def inscrever(self, user, curso, dias):
        e = CourseEnrollment.objects.create(user=user, course=curso)
        CourseEnrollment.objects.filter(pk=e.pk).update(enrollment_date=self.agora - timedelta(days=dias))

    def responder(self, user, ch, resultados, dias):
        quando = self.agora - timedelta(days=dias)
        ids = [ChallengeAttempt.objects.create(user=user, challenge=ch, is_correct=r).pk for r in resultados]
        ChallengeAttempt.objects.filter(pk__in=ids).update(created_at=quando)
        cp, _ = ChallengeProgress.objects.get_or_create(user=user, challenge=ch, defaults={'completed': True})
        ChallengeProgress.objects.filter(pk=cp.pk).update(completed_at=quando, updated_at=quando)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')


class PermissoesTests(Base):
    def test_aluno_recebe_403(self):
        self.entrar(self.activo)
        for url in ('alunos/', 'alunos/exportar/', f'alunos/{self.activo.id}/', 'resultados/',
                    'resultados/exportar/'):
            self.assertEqual(self.client.get(PROF + url).status_code, 403, url)

    def test_outro_professor_nao_ve_aluno(self):
        self.entrar(self.outro_prof)
        r = self.client.get(f'{PROF}alunos/{self.activo.id}/')
        self.assertEqual(r.status_code, 404)
        self.assertIn('error', r.json())

    def test_curso_de_outro_professor_404(self):
        self.entrar(self.prof)
        self.assertEqual(self.client.get(f'{PROF}alunos/?curso={self.curso_outro.id}').status_code, 404)
        self.assertEqual(self.client.get(f'{PROF}alunos/?curso=nao-e-uuid').status_code, 404)

    def test_filtro_invalido_400(self):
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}alunos/?filtro=xpto')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'filtro_invalido')
        self.assertEqual(r.json()['details'], {'filtro': ['Use todos, activos ou em_risco.']})
        r = self.client.get(f'{PROF}resultados/?periodo=14')
        self.assertEqual(r.json()['details'], {'periodo': ['Use 7, 30 ou 90 dias.']})


class ListaTests(Base):
    def lista(self, query=''):
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}alunos/{query}')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_ambito_e_estados(self):
        dados = self.lista()
        estados = {l['nome']: l['estado'] for l in dados['resultados']}
        self.assertEqual(estados, {'Bruno Activo': 'activo', 'Carla Risco': 'em_risco',
                                   'Dina Parada': 'em_risco', 'Eva Nova': 'novo'})
        self.assertNotIn('Zé Alheio', estados)
        self.assertNotIn('Prof Ana', estados)
        n = dados['numeros']
        self.assertEqual((n['alunos'], n['cursos'], n['activos_7d'], n['pct_activos'], n['em_risco']),
                         (4, 2, 1, 25, 2))
        self.assertEqual(n['acerto_medio'], 60)  # 6 certas em 10
        self.assertEqual((dados['total'], dados['paginas']), (4, 1))

    def test_linha(self):
        dados = self.lista()
        primeira = dados['resultados'][0]  # actividade mais recente primeiro
        self.assertEqual(primeira['nome'], 'Bruno Activo')
        self.assertEqual(primeira['iniciais'], 'BA')
        self.assertEqual(primeira['curso'], {'id': str(self.video.id), 'titulo': self.video.title, 'tipo': 'video'})
        self.assertEqual(primeira['progresso'], 50)
        self.assertIsNone(primeira['acerto'])
        self.assertEqual(primeira['outros_cursos'], 0)
        carla = next(l for l in dados['resultados'] if l['nome'] == 'Carla Risco')
        self.assertEqual(carla['curso']['tipo'], 'pratica')
        self.assertEqual(carla['acerto'], 60)
        self.assertEqual(carla['progresso'], 100)  # a única lição tem os dois exercícios feitos
        for l in dados['resultados']:
            self.assertEqual(set(l), {'id', 'nome', 'iniciais', 'curso', 'outros_cursos', 'progresso', 'acerto',
                                      'ultima_actividade', 'estado'})

    def test_filtros_pesquisa_e_curso(self):
        self.assertEqual([l['nome'] for l in self.lista('?filtro=activos')['resultados']], ['Bruno Activo'])
        em_risco = self.lista('?filtro=em_risco')
        self.assertEqual([l['nome'] for l in em_risco['resultados']], ['Dina Parada', 'Carla Risco'])
        self.assertEqual(em_risco['numeros']['alunos'], 4)  # os números ignoram o filtro
        self.assertEqual([l['nome'] for l in self.lista('?q=eva')['resultados']], ['Eva Nova'])
        so_pratica = self.lista(f'?curso={self.pratica.id}')
        self.assertEqual([l['nome'] for l in so_pratica['resultados']], ['Carla Risco'])
        self.assertEqual(so_pratica['numeros']['alunos'], 1)

    def test_admin_ve_todos(self):
        self.entrar(self.admin)
        nomes = {l['nome'] for l in self.client.get(f'{PROF}alunos/').json()['resultados']}
        self.assertIn('Zé Alheio', nomes)

    def test_csv_sem_emails_nem_telefones(self):
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}alunos/exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('alunos.csv', r['Content-Disposition'])
        texto = r.content.decode('utf-8')
        self.assertTrue(texto.startswith('﻿Aluno;Curso;Progresso;Acerto;Última actividade;Estado'))
        self.assertNotIn('@', texto)
        self.assertNotIn('923000000', texto)
        self.assertIn('Carla Risco;Inglês no Terminal;100%;60%;', texto)
        self.assertEqual(len(texto.strip().splitlines()), 5)


class DetalheTests(Base):
    def test_ficha(self):
        self.risco.preferences = {'area': 'Industry English', 'cidade': 'Luanda'}
        self.risco.save()
        UserProgress.objects.create(user=self.risco, points=120)
        self.inscrever(self.risco, self.video, dias=30)
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}alunos/{self.risco.id}/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['aluno']['nome'], 'Carla Risco')
        self.assertEqual(d['aluno']['profissao'], 'Petróleo e Gás')
        self.assertEqual(d['aluno']['cidade'], 'Luanda')
        self.assertEqual(d['aluno']['plano'], 'Gratuito')
        self.assertTrue(d['aluno']['inscrito_em'].startswith(
            (self.agora - timedelta(days=30)).date().isoformat()))
        n = d['numeros']
        self.assertEqual(n['pontos'], 120)
        self.assertEqual(n['acerto'], 60)
        self.assertIsNone(n['acerto_variacao_30d'])
        self.assertEqual(n['liga']['nome'], 'Liga Bronze')
        self.assertIn(n['pratica_de'], ('manhã', 'tarde', 'noite'))
        self.assertEqual((n['conversa_min'], n['conversas']), (0, 0))
        self.assertEqual({c['tipo'] for c in d['cursos']}, {'video', 'pratica'})
        self.assertEqual(d['onde_erra'], [{
            'tema': 'Choose the correct safety word for the muster point',
            'onde': 'Inglês no Terminal, unidade 1, lição 1', 'erros': 4}])
        corpo = r.content.decode()
        self.assertNotIn('@', corpo)
        self.assertNotIn('923000000', corpo)

    def test_aluno_de_outro_professor_404(self):
        self.entrar(self.prof)
        self.assertEqual(self.client.get(f'{PROF}alunos/{self.alheio.id}/').status_code, 404)

    def test_variacao_30d(self):
        self.responder(self.risco, self.ex_facil, [False] * 4, dias=45)  # 0% entre 30 e 60 dias
        self.entrar(self.prof)
        n = self.client.get(f'{PROF}alunos/{self.risco.id}/').json()['numeros']
        self.assertEqual(n['acerto_variacao_30d'], 60)  # 6/10 nos últimos 30 dias
        self.assertEqual(n['acerto'], 43)  # 6/14


class ResultadosTests(Base):
    def test_contas(self):
        outro = self.utilizador('outro-aluno@example.com', 'Filipe')
        self.responder(outro, self.ex_dificil, [False, False], dias=3)  # 2 respostas: fora das faixas
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}resultados/?periodo=30')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['periodo'], 30)
        faixas = {f['nome']: f['alunos'] for f in d['faixas']}
        self.assertEqual(faixas, {'90% ou mais': 0, '70% a 89%': 0, '50% a 69%': 1, 'Menos de 50%': 0})
        dificeis = d['perguntas_dificeis']
        self.assertEqual([p['challenge_id'] for p in dificeis], [str(self.ex_dificil.id), str(self.ex_facil.id)])
        self.assertEqual((dificeis[0]['acerto'], dificeis[0]['respostas']), (14, 7))  # 1 certa em 7
        self.assertEqual(dificeis[0]['onde'], 'Unidade 1, lição 1')
        self.assertEqual((dificeis[1]['acerto'], dificeis[1]['respostas']), (100, 5))
        por_curso = {c['id']: c for c in d['conclusao_por_curso']}
        self.assertEqual(por_curso[str(self.pratica.id)]['alunos'], 2)
        self.assertNotIn(str(self.curso_outro.id), por_curso)

    def test_periodo_curto_e_invalido(self):
        self.entrar(self.prof)
        d = self.client.get(f'{PROF}resultados/?periodo=7').json()
        self.assertEqual(d['perguntas_dificeis'], [])
        self.assertEqual(sum(f['alunos'] for f in d['faixas']), 0)
        self.assertEqual(self.client.get(f'{PROF}resultados/?periodo=14').status_code, 400)

    def test_csv(self):
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}resultados/exportar/?periodo=30')
        self.assertEqual(r.status_code, 200)
        texto = r.content.decode('utf-8')
        self.assertTrue(texto.startswith('﻿'))
        self.assertIn('Curso;Tipo;Alunos;Conclusão', texto)
        self.assertIn('Pergunta;Tipo;Curso;Onde;Acerto;Respostas', texto)
        self.assertNotIn('@', texto)


class EstadosTests(Base):
    """activo < 7 dias (= filtro "activos" = activos_7d); pouco_activo 7 a 9 dias; em_risco >= 10."""

    def setUp(self):
        super().setUp()
        self.pouco = self.utilizador('pouco@example.com', 'Gil Pouco')
        self.responder(self.pouco, self.ex_facil, [True], dias=8)
        self.limite = self.utilizador('limite@example.com', 'Hugo Seis')
        self.responder(self.limite, self.ex_facil, [True], dias=6)
        self.entrar(self.prof)

    def test_baldes_e_numeros_coerentes(self):
        d = self.client.get(f'{PROF}alunos/').json()
        estados = {l['nome']: l['estado'] for l in d['resultados']}
        self.assertEqual(estados['Gil Pouco'], 'pouco_activo')
        self.assertEqual(estados['Hugo Seis'], 'activo')
        self.assertEqual(estados['Bruno Activo'], 'activo')
        activos = self.client.get(f'{PROF}alunos/?filtro=activos').json()
        self.assertEqual({l['nome'] for l in activos['resultados']}, {'Bruno Activo', 'Hugo Seis'})
        self.assertEqual(d['numeros']['activos_7d'], len(activos['resultados']))
        em_risco = self.client.get(f'{PROF}alunos/?filtro=em_risco').json()
        self.assertNotIn('Gil Pouco', {l['nome'] for l in em_risco['resultados']})
        self.assertEqual(d['numeros']['em_risco'], 2)

    def test_csv_pouco_activo(self):
        texto = self.client.get(f'{PROF}alunos/exportar/').content.decode('utf-8')
        self.assertIn('Gil Pouco;Inglês no Terminal;', texto)
        linha = next(l for l in texto.splitlines() if l.startswith('Gil Pouco'))
        self.assertTrue(linha.endswith(';Pouco activo'))


class NotaTests(Base):
    def nota(self, user, final, letra='C'):
        StudentCourseGrade.objects.create(user=user, course=self.video, final_grade_percentage=final,
                                          final_grade_letter=letra, conversation_score=final,
                                          conversation_sessions=9)

    def curso(self, user):
        self.entrar(self.prof)
        cursos = self.client.get(f'{PROF}alunos/{user.id}/').json()['cursos']
        return next(c for c in cursos if c['id'] == str(self.video.id))

    def test_sem_comecar_nao_tem_nota(self):
        # A nota guardada vem só das conversas (do nível): o aluno nunca abriu o curso.
        self.nota(self.novo, 68.0)
        c = self.curso(self.novo)
        self.assertEqual(c['progresso'], 0)
        self.assertIsNone(c['nota'])
        self.assertFalse(c['abaixo_minimo'])

    def test_abaixo_minimo_usa_a_nota_sem_arredondar(self):
        self.nota(self.activo, 69.6)  # mostra 70, mas está abaixo do mínimo (70)
        c = self.curso(self.activo)
        self.assertEqual((c['nota'], c['abaixo_minimo']), (70, True))

    def test_sem_componentes_nao_tem_nota(self):
        self.nota(self.activo, 0.0, letra='N/A')
        self.assertIsNone(self.curso(self.activo)['nota'])


class DificeisIdsTests(Base):
    def test_licao_e_unidade(self):
        self.entrar(self.prof)
        p = self.client.get(f'{PROF}resultados/?periodo=30').json()['perguntas_dificeis'][0]
        self.assertEqual(p['licao_id'], str(self.ex_dificil.lesson_id))
        self.assertEqual(p['unidade_id'], str(self.ex_dificil.lesson.unit_id))
