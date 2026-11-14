"""
Cursos na administração: permissões (só administradores), lista e números, análise (contas em
fixtures), exportação CSV, detalhe para revisão, arquivo pelo administrador e publicação directa
para professores de confiança (PerfilProfessor.publica_sem_revisao).
"""
from datetime import timedelta
from unittest import mock, skipUnless

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.api import admin_painel_cursos as painel
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterResource, Course, CourseEnrollment, CourseSection, UserCourseProgress,
    VideoWatchLog,
)
from apps.practice.models import (
    ChallengeAttempt, ChallengeOption, ChallengeProgress, LessonCompletion, PracticeChallenge, PracticeLesson,
    PracticeUnit, VapiSession,
)
from apps.users.models import Notification, PerfilProfessor, User

ADMIN = '/api/v1/admin/cursos/'
PROF = '/api/v1/teacher/'

TEM_CAMPO_CONFIANCA = any(f.name == 'publica_sem_revisao' for f in PerfilProfessor._meta.get_fields())


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-adm@example.com', name='Prof Ana', password='x12345678',
                                             role='teacher')
        self.outro_prof = User.objects.create_user(email='outro-adm@example.com', name='Prof Rui',
                                                   password='x12345678', role='teacher')
        self.admin = User.objects.create_user(email='admin-adm@example.com', name='Admin', password='x12345678',
                                              role='admin')
        self.staff = User.objects.create_user(email='staff-adm@example.com', name='Staff', password='x12345678',
                                              role='student', is_staff=True)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def aluno(self, n):
        return User.objects.create_user(email=f'aluno{n}-adm@example.com', name=f'Aluno {n}',
                                        password='x12345678', role='student')

    def curso_video(self, status='Draft', prof=None, titulo='Inglês para Plataformas', aulas=1,
                    categoria='Industry English', **extra):
        prof = prof or self.prof
        curso = Course.objects.create(teacher=prof, teacherName=prof.name, title=titulo, description='Vídeo',
                                      category=categoria, level='Beginner', course_type='video', status=status,
                                      image='https://exemplo.ao/capa.jpg', **extra)
        seccao = CourseSection.objects.create(course=curso, sectionTitle='Secção 1', order=1)
        curso.aulas = [Chapter.objects.create(section=seccao, title=f'Aula {i + 1}', content='x', type='Video',
                                              video=f'https://exemplo.ao/v{i}.mp4', order=i + 1)
                       for i in range(aulas)]
        return curso

    def curso_pratica(self, status='Draft', prof=None, titulo='Inglês no Terminal', licoes=1, **extra):
        prof = prof or self.prof
        curso = Course.objects.create(teacher=prof, teacherName=prof.name, title=titulo, description='Prática',
                                      category='Oil & Gas', level='Intermediate', course_type='practice',
                                      status=status, **extra)
        unidade = PracticeUnit.objects.create(course=curso, title='Unidade 1', description='', order=1)
        curso.licoes = []
        for n in range(licoes):
            licao = PracticeLesson.objects.create(unit=unidade, title=f'Lição {n + 1}', order=n + 1)
            licao.exs = []
            for i in range(3):
                ch = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question=f'Pergunta {i}', order=i)
                ChallengeOption.objects.create(challenge=ch, text='Certa', is_correct=True, order=1)
                ChallengeOption.objects.create(challenge=ch, text='Errada', is_correct=False, order=2)
                licao.exs.append(ch)
            curso.licoes.append(licao)
        return curso


class PermissoesTests(Base):
    def setUp(self):
        super().setUp()
        self.curso = self.curso_video(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft')
        self.aluno1 = self.aluno(1)

    def _pedidos(self):
        cid = self.curso.id
        return [
            ('get', ADMIN, None), ('get', f'{ADMIN}analise/', None), ('get', f'{ADMIN}analise/exportar/', None),
            ('get', f'{ADMIN}revisao/', None), ('get', f'{ADMIN}{cid}/', None),
            ('post', f'{ADMIN}{cid}/aprovar/', {}), ('post', f'{ADMIN}{cid}/recusar/', {'motivo': 'Falta o vídeo 2'}),
            ('post', f'{ADMIN}{cid}/arquivar/', {'modo': 'manter', 'motivo': 'Conteúdo duplicado'}),
            ('get', '/api/v1/courses/admin/list/', None),
            ('get', '/api/v1/courses/admin/analytics/real-time/', None),
        ]

    def test_professor_aluno_e_so_staff_recebem_403(self):
        for user in (self.prof, self.aluno1, self.staff):
            self.entrar(user)
            for metodo, url, dados in self._pedidos():
                r = getattr(self.client, metodo)(url, dados, format='json') if dados is not None \
                    else getattr(self.client, metodo)(url)
                self.assertEqual(r.status_code, 403, f'{user.email} {metodo} {url}: {r.status_code}')
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.status, 'InReview')

    def test_sem_sessao_nao_entra(self):
        r = self.client.get(ADMIN)
        self.assertIn(r.status_code, (401, 403))

    def test_admin_e_superutilizador_entram(self):
        su = User.objects.create_user(email='su-adm@example.com', name='SU', password='x12345678', role='student',
                                      is_superuser=True)
        for user in (self.admin, su):
            self.entrar(user)
            for url in (ADMIN, f'{ADMIN}analise/', f'{ADMIN}revisao/', f'{ADMIN}{self.curso.id}/',
                        '/api/v1/courses/admin/list/'):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_admin_abre_endpoints_do_professor_em_qualquer_curso(self):
        pratica = self.curso_pratica()
        self.entrar(self.admin)
        for url in (f'{PROF}cursos/{self.curso.id}/', f'{PROF}cursos/{self.curso.id}/estrutura/',
                    f'{PROF}cursos/{self.curso.id}/verificacao/', f'{PROF}pratica/{pratica.id}/estrutura/',
                    f'{PROF}cursos/{pratica.id}/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.patch(f'{PROF}cursos/{pratica.id}/', {'descricao': 'Revisto pela administração'},
                              format='json')
        self.assertEqual(r.status_code, 200)

    def test_so_staff_nao_age_como_professor(self):
        self.entrar(self.staff)
        self.assertEqual(self.client.get(f'{PROF}cursos/{self.curso.id}/').status_code, 403)
        # Um professor com is_staff continua a ser só professor: não abre cursos dos outros.
        self.outro_prof.is_staff = True
        self.outro_prof.save(update_fields=['is_staff'])
        self.entrar(self.outro_prof)
        self.assertEqual(self.client.get(f'{PROF}cursos/{self.curso.id}/').status_code, 404)


class ListaTests(Base):
    def setUp(self):
        super().setUp()
        self.pub_video = self.curso_video(status='Published', titulo='Segurança no Convés')
        self.pub_pratica = self.curso_pratica(status='Published', titulo='Terminal Prático')
        self.rascunho = self.curso_video(titulo='Rascunho Antigo')
        Course.objects.filter(pk=self.rascunho.pk).update(updated_at=timezone.now() - timedelta(days=40))
        self.rascunho_novo = self.curso_pratica(titulo='Rascunho Novo', prof=self.outro_prof)
        self.revisao = self.curso_video(status='InReview', titulo='Em Revisão', prof=self.outro_prof,
                                        submetido_em=timezone.now(), estado_antes_revisao='Draft')
        self.arquivado = self.curso_video(status='Archived', titulo='Velho', modo_arquivo='manter')
        # Alunos: 2 inscritos no vídeo publicado (um a 100%), 1 a fazer o curso de prática.
        a1, a2, a3 = self.aluno(1), self.aluno(2), self.aluno(3)
        for a, pct in ((a1, 100.0), (a2, 0.0)):
            CourseEnrollment.objects.create(user=a, course=self.pub_video)
            p = UserCourseProgress.objects.create(user=a, course=self.pub_video, enrollmentDate=timezone.now())
            if pct:
                ChapterProgress.objects.create(user_progress=p, chapter=self.pub_video.aulas[0], completed=True)
        ch = self.pub_pratica.licoes[0].exs[0]
        ChallengeProgress.objects.create(user=a3, challenge=ch, completed=True)
        self.entrar(self.admin)

    def test_numeros(self):
        r = self.client.get(ADMIN)
        self.assertEqual(r.status_code, 200)
        n = r.json()['numeros']
        self.assertEqual(n['publicados'], 2)
        self.assertEqual(n['publicados_video'], 1)
        self.assertEqual(n['publicados_pratica'], 1)
        self.assertEqual(n['rascunhos'], 2)
        self.assertEqual(n['rascunhos_parados_30d'], 1)
        self.assertEqual(n['em_revisao'], 1)
        self.assertEqual(n['inscricoes'], 3)
        self.assertEqual(n['inscricoes_mes'], 3)
        # Vídeo: (100 + 0) / 2 = 50 com 2 alunos; prática: 0 lições completas de 1 -> 0 com 1 aluno.
        self.assertAlmostEqual(n['conclusao_media'], round((50 * 2 + 0) / 3, 1))

    def test_inscricoes_so_activas_e_de_alunos(self):
        # Inscrição inactiva, inscrição de um professor e prática de um professor: nada disto conta.
        a4 = self.aluno(4)
        CourseEnrollment.objects.create(user=a4, course=self.pub_video, is_active=False)
        CourseEnrollment.objects.create(user=self.outro_prof, course=self.pub_video)
        ChallengeProgress.objects.create(user=self.outro_prof, challenge=self.pub_pratica.licoes[0].exs[0],
                                         completed=True)
        n = self.client.get(ADMIN).json()['numeros']
        self.assertEqual((n['inscricoes'], n['inscricoes_mes']), (3, 3))
        # Uma inscrição activa criada no mês passado conta no total, não em "este mês".
        e = CourseEnrollment.objects.create(user=a4, course=self.arquivado)
        CourseEnrollment.objects.filter(pk=e.pk).update(enrollment_date=timezone.now() - timedelta(days=40))
        # E a prática pré-filtrada por data: quem começou há 40 dias e respondeu hoje não é inscrição nova.
        a5 = self.aluno(5)
        velho = ChallengeProgress.objects.create(user=a5, challenge=self.pub_pratica.licoes[0].exs[1], completed=True)
        ChallengeProgress.objects.filter(pk=velho.pk).update(completed_at=timezone.now() - timedelta(days=40))
        ChallengeProgress.objects.create(user=a5, challenge=self.pub_pratica.licoes[0].exs[2], completed=True)
        n = self.client.get(ADMIN).json()['numeros']
        self.assertEqual((n['inscricoes'], n['inscricoes_mes']), (5, 3))

    def test_item_e_filtros(self):
        d = self.client.get(ADMIN).json()
        self.assertEqual(d['total'], 6)
        self.assertEqual(d['paginas'], 1)
        item = next(x for x in d['resultados'] if x['id'] == str(self.pub_video.id))
        self.assertEqual(item['tipo'], 'video')
        self.assertEqual(item['professor'], {'id': str(self.prof.id), 'nome': 'Prof Ana'})
        self.assertEqual(item['area'], 'Petróleo e Gás')
        self.assertEqual(item['estado'], 'publicado')
        self.assertEqual(item['alunos'], 2)
        self.assertEqual(item['conclusao'], 50)
        self.assertIsNone(item['submetido_em'])
        self.assertIsNone(next(x for x in d['resultados'] if x['id'] == str(self.rascunho.id))['conclusao'])

        ids = lambda q: {x['id'] for x in self.client.get(ADMIN + q).json()['resultados']}  # noqa: E731
        self.assertEqual(ids('?tipo=pratica'), {str(self.pub_pratica.id), str(self.rascunho_novo.id)})
        self.assertEqual(ids('?estado=rascunho'), {str(self.rascunho.id), str(self.rascunho_novo.id)})
        self.assertEqual(ids('?tipo=video&estado=publicado'), {str(self.pub_video.id)})
        self.assertEqual(ids(f'?professor={self.outro_prof.id}'), {str(self.rascunho_novo.id), str(self.revisao.id)})
        self.assertEqual(ids('?q=convés'), {str(self.pub_video.id)})
        self.assertEqual(ids('?q=prof rui&estado=em_revisao'), {str(self.revisao.id)})
        rev = self.client.get(ADMIN + '?estado=em_revisao').json()['resultados'][0]
        self.assertIsNotNone(rev['submetido_em'])
        # Os números não dependem dos filtros.
        self.assertEqual(self.client.get(ADMIN + '?tipo=pratica').json()['numeros']['publicados'], 2)

    def test_paginacao(self):
        for i in range(25):
            Course.objects.create(teacher=self.prof, teacherName='Prof Ana', title=f'Extra {i}', course_type='video')
        d = self.client.get(ADMIN).json()
        self.assertEqual((d['total'], d['paginas'], len(d['resultados'])), (31, 2, 25))
        d2 = self.client.get(ADMIN + '?pagina=2').json()
        self.assertEqual(len(d2['resultados']), 6)
        self.assertFalse({x['id'] for x in d['resultados']} & {x['id'] for x in d2['resultados']})

    def test_parametros_invalidos(self):
        for q, campo in (('?tipo=audio', 'tipo'), ('?estado=x', 'estado'), ('?professor=abc', 'professor'),
                         ('?pagina=0', 'pagina')):
            r = self.client.get(ADMIN + q)
            self.assertEqual(r.status_code, 400, q)
            corpo = r.json()
            self.assertEqual(corpo['code'], 'validation_error')
            self.assertIsInstance(corpo['details'][campo], list)
            self.assertTrue(corpo['message'])


class AnaliseActividadeTests(Base):
    """Contas da actividade, inscrições e lições numa fixture pequena (dias de Luanda)."""

    def setUp(self):
        super().setUp()
        hoje = painel._hoje()
        meio_dia = lambda dias: painel._inicio_dia(hoje - timedelta(days=dias)) + timedelta(hours=12)  # noqa: E731
        self.a, self.b, self.c, self.d = self.aluno(1), self.aluno(2), self.aluno(3), self.aluno(4)
        pratica = self.curso_pratica(status='Published')
        ch = pratica.licoes[0].exs[0]
        video = self.curso_video(status='Published')
        negocios = self.curso_video(status='Published', titulo='Reuniões', categoria='Business English')

        # A: responde hoje; conclui uma lição há 3 dias.
        x = ChallengeAttempt.objects.create(user=self.a, challenge=ch, is_correct=True)
        ChallengeAttempt.objects.filter(pk=x.pk).update(created_at=meio_dia(0))
        lc = LessonCompletion.objects.create(user=self.a, lesson=pratica.licoes[0], last_completed_at=meio_dia(3))
        LessonCompletion.objects.filter(pk=lc.pk).update(first_completed_at=meio_dia(3))
        # B: vê vídeo ontem; conclui uma aula há 2 dias; uma conversa que nunca ligou (não conta).
        w = VideoWatchLog.objects.create(user=self.b, chapter=video.aulas[0], date=hoje, seconds=60)
        VideoWatchLog.objects.filter(pk=w.pk).update(updated_at=meio_dia(1))
        p = UserCourseProgress.objects.create(user=self.b, course=video, enrollmentDate=timezone.now())
        cp = ChapterProgress.objects.create(user_progress=p, chapter=video.aulas[0], completed=True)
        ChapterProgress.objects.filter(pk=cp.pk).update(updated_at=meio_dia(2), completed_at=meio_dia(2))
        v = VapiSession.objects.create(session_id='adm-nl', user=self.b, level='B1', domain='general',
                                       duration_minutes=0, status=VapiSession.STATUS_NAO_LIGOU)
        VapiSession.objects.filter(pk=v.pk).update(created_at=meio_dia(0))
        # C: conversa com o tutor hoje; responde há 10 dias.
        v = VapiSession.objects.create(session_id='adm-c', user=self.c, level='B1', domain='general',
                                       duration_minutes=5)
        VapiSession.objects.filter(pk=v.pk).update(created_at=meio_dia(0))
        x = ChallengeAttempt.objects.create(user=self.c, challenge=ch, is_correct=False)
        ChallengeAttempt.objects.filter(pk=x.pk).update(created_at=meio_dia(10))
        # O professor também responde hoje, mas não é aluno.
        ChallengeAttempt.objects.create(user=self.prof, challenge=ch, is_correct=True)

        # Inscrições: 2 no período (B e D), 1 no período anterior.
        CourseEnrollment.objects.create(user=self.b, course=video)
        CourseEnrollment.objects.create(user=self.d, course=negocios)
        e = CourseEnrollment.objects.create(user=self.c, course=video)
        CourseEnrollment.objects.filter(pk=e.pk).update(enrollment_date=meio_dia(40))
        self.hoje = hoje
        self.entrar(self.admin)

    def test_contas(self):
        r = self.client.get(f'{ADMIN}analise/?periodo=30')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['periodo'], 30)
        self.assertEqual(len(d['activos_dia']), 30)
        self.assertEqual(d['activos_dia'][-1]['dia'], self.hoje.isoformat())
        por_dia = {x['dia']: x['n'] for x in d['activos_dia']}
        dia = lambda n: (self.hoje - timedelta(days=n)).isoformat()  # noqa: E731
        self.assertEqual(por_dia[dia(0)], 2)   # A e C
        self.assertEqual(por_dia[dia(1)], 1)   # B (vídeo)
        self.assertEqual(por_dia[dia(2)], 1)   # B (aula concluída)
        self.assertEqual(por_dia[dia(3)], 1)   # A (lição)
        self.assertEqual(por_dia[dia(10)], 1)  # C
        self.assertEqual(sum(por_dia.values()), 6)
        self.assertEqual(d['activos_dia_media'], round(6 / 30, 1))
        self.assertEqual(d['activos_semana'], 3)
        self.assertEqual(d['alunos'], 5)  # 4 alunos + a conta só staff (papel student)
        self.assertEqual(d['pct_activos_semana'], 60.0)
        self.assertEqual(d['inscricoes_novas'], 2)
        self.assertEqual(d['inscricoes_variacao_pct'], 100.0)
        self.assertEqual(d['licoes_concluidas'], 2)
        self.assertEqual(d['licoes_por_dia'], round(2 / 30, 1))
        self.assertEqual(d['por_area'], [{'area': 'Negócios', 'inscricoes': 1},
                                         {'area': 'Petróleo e Gás', 'inscricoes': 1}])
        self.assertEqual(d['conclusao_baixa'], [])

    def test_periodo_7_e_variacao_nula(self):
        d = self.client.get(f'{ADMIN}analise/?periodo=7').json()
        self.assertEqual(len(d['activos_dia']), 7)
        self.assertEqual(sum(x['n'] for x in d['activos_dia']), 5)  # sem os 10 dias atrás
        self.assertIsNone(d['inscricoes_variacao_pct'])  # nada nos 7 dias anteriores

    def test_periodo_invalido(self):
        r = self.client.get(f'{ADMIN}analise/?periodo=15')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'periodo_invalido')
        self.assertIsInstance(r.json()['details']['periodo'], list)

    def test_cache_de_10_minutos(self):
        primeiro = self.client.get(f'{ADMIN}analise/?periodo=30').json()
        CourseEnrollment.objects.create(user=self.a, course=Course.objects.filter(course_type='video').first())
        self.assertEqual(self.client.get(f'{ADMIN}analise/?periodo=30').json()['inscricoes_novas'],
                         primeiro['inscricoes_novas'])
        cache.clear()
        self.assertEqual(self.client.get(f'{ADMIN}analise/?periodo=30').json()['inscricoes_novas'],
                         primeiro['inscricoes_novas'] + 1)

    def test_erro_interno_nao_mostra_a_excepcao(self):
        with mock.patch.object(painel, 'calcular_analise', side_effect=RuntimeError('segredo da BD')):
            r = self.client.get(f'{ADMIN}analise/?periodo=90')
        self.assertEqual(r.status_code, 500)
        self.assertNotIn('segredo', r.content.decode())
        self.assertEqual(r.json()['code'], 'erro_interno')


class ConclusaoBaixaTests(Base):
    def setUp(self):
        super().setUp()
        # 6 aulas; 6 alunos com [1, 1, 2, 3, 6, 3] aulas concluídas -> param em 2, 2, 3, 4, 4.
        self.baixo = self.curso_video(status='Published', titulo='=HYPERLINK("http://x")', aulas=6)
        for i, feitas in enumerate((1, 1, 2, 3, 6, 3)):
            a = self.aluno(i)
            CourseEnrollment.objects.create(user=a, course=self.baixo)
            p = UserCourseProgress.objects.create(user=a, course=self.baixo, enrollmentDate=timezone.now())
            for aula in self.baixo.aulas[:feitas]:
                ChapterProgress.objects.create(user_progress=p, chapter=aula, completed=True)
        # 5 alunos que acabaram tudo.
        self.alto = self.curso_video(status='Published', titulo='Fácil', aulas=2)
        for i in range(10, 15):
            a = self.aluno(i)
            CourseEnrollment.objects.create(user=a, course=self.alto)
            p = UserCourseProgress.objects.create(user=a, course=self.alto, enrollmentDate=timezone.now())
            for aula in self.alto.aulas:
                ChapterProgress.objects.create(user_progress=p, chapter=aula, completed=True)
        # Prática com 2 alunos: fica de fora (menos de 5).
        pratica = self.curso_pratica(status='Published', licoes=2)
        for i in range(20, 22):
            ChallengeProgress.objects.create(user=self.aluno(i), challenge=pratica.licoes[0].exs[0], completed=True)
        self.entrar(self.admin)

    def test_lista_e_desistencia(self):
        d = self.client.get(f'{ADMIN}analise/?periodo=30').json()
        lista = d['conclusao_baixa']
        self.assertEqual([x['id'] for x in lista], [str(self.baixo.id), str(self.alto.id)])
        primeiro = lista[0]
        self.assertEqual(primeiro['alunos'], 6)
        self.assertEqual(primeiro['conclusao'], round(16 / 36 * 100))
        self.assertEqual(primeiro['tipo'], 'video')
        # Os 5 que pararam (2, 2, 3, 4, 4) pararam todos entre a aula 2 e a 4.
        self.assertEqual(primeiro['desistencia'], {'texto': 'entre a aula 2 e a 4', 'alunos': 5, 'pct': 100})
        self.assertEqual(lista[1]['conclusao'], 100)
        self.assertIsNone(lista[1]['desistencia'])  # ninguém parou

    def test_janela(self):
        self.assertIsNone(painel._janela([1, 2], 5, 'aula'))           # poucos alunos
        self.assertEqual(painel._janela([5, 5, 5], 5, 'aula'), {'texto': 'entre a aula 3 e a 5', 'alunos': 3, 'pct': 100})
        self.assertEqual(painel._janela([1, 1, 2], 2, 'lição'), {'texto': 'entre a lição 1 e a 2', 'alunos': 3, 'pct': 100})
        # 3 em 10 = 30%: chega; 3 em 11 = 27%: não há um ponto claro.
        self.assertEqual(painel._janela(list(range(1, 11)), 10, 'aula'),
                         {'texto': 'entre a aula 1 e a 3', 'alunos': 3, 'pct': 30})
        self.assertIsNone(painel._janela(list(range(1, 12)), 11, 'aula'))
        # A janela mais cheia tem só 2 alunos (mesmo sendo 50%): null.
        self.assertIsNone(painel._janela([1, 1, 9, 9], 10, 'aula'))

    def test_desistencia_so_conta_alunos(self):
        # Um professor (não aluno) inscrito e parado não entra nas contas.
        CourseEnrollment.objects.create(user=self.outro_prof, course=self.baixo)
        d = self.client.get(f'{ADMIN}analise/?periodo=30').json()
        self.assertEqual(d['conclusao_baixa'][0]['desistencia']['alunos'], 5)
        self.assertEqual(d['conclusao_baixa'][0]['alunos'], 6)
        self.assertEqual(d['cache_segundos'], painel.CACHE_SEGUNDOS)
        self.assertIn('gerado_em', d)

    def test_csv(self):
        r = self.client.get(f'{ADMIN}analise/exportar/?periodo=30')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment;', r['Content-Disposition'])
        texto = r.content.decode('utf-8')
        self.assertTrue(texto.startswith('﻿'))
        linhas = texto.lstrip('﻿').split('\r\n')
        self.assertEqual(linhas[1], 'Indicador;Valor')
        self.assertIn('Dia;Alunos activos', linhas)
        self.assertIn('Curso;Tipo;Alunos;Conclusão (%);Onde desistem', linhas)
        linha_curso = next(l for l in linhas if 'HYPERLINK' in l)
        self.assertTrue(linha_curso.startswith('"\'=HYPERLINK') or linha_curso.startswith("'=HYPERLINK"))
        self.assertIn(';Vídeo;6;44;entre a aula 2 e a 4', linha_curso)
        self.assertFalse(any(l.startswith(('=', '+', '-', '@')) for l in linhas))

    def test_celula(self):
        self.assertEqual(painel.celula('=1+1'), "'=1+1")
        self.assertEqual(painel.celula('@soma'), "'@soma")
        self.assertEqual(painel.celula('-x'), "'-x")
        self.assertEqual(painel.celula(-12.5), '-12,5')  # número, não texto
        self.assertEqual(painel.celula(None), '')

    def test_csv_periodo_invalido(self):
        self.assertEqual(self.client.get(f'{ADMIN}analise/exportar/?periodo=1').status_code, 400)


class DetalheRevisaoTests(Base):
    def test_video(self):
        curso = self.curso_video(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft',
                                 aulas=2)
        aula = curso.aulas[0]
        aula.quiz_enabled = True
        aula.quiz_data = {'questions': [{'id': 'q1', 'question': 'Q?', 'options': [
            {'id': 'a', 'text': 'A', 'isCorrect': True}, {'id': 'b', 'text': 'B'}]}]}
        aula.save()
        ChapterResource.objects.create(chapter=aula, title='Guia', resource_type='PDF', created_by=self.prof,
                                       external_url='https://exemplo.ao/guia.pdf')
        Course.objects.create(teacher=self.prof, teacherName='Prof Ana', title='Outro', course_type='video',
                              status='Published')
        self.entrar(self.admin)
        r = self.client.get(f'{ADMIN}{curso.id}/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        for chave in ('descricao', 'imagem', 'area', 'nivel', 'acesso', 'estado', 'motivo_recusa', 'submetido_em',
                      'estado_antes_revisao'):
            self.assertIn(chave, d['curso'])
        self.assertEqual(d['curso']['estado'], 'em_revisao')
        self.assertEqual(d['curso']['estado_antes_revisao'], 'rascunho')
        self.assertEqual(d['professor'], {'id': str(self.prof.id), 'nome': 'Prof Ana', 'email': 'prof-adm@example.com',
                                          'cursos_publicados': 1, 'publica_sem_revisao': False})
        self.assertIn('itens', d['verificacao'])
        self.assertIn('pode_submeter', d['verificacao'])
        self.assertEqual(d['estrutura']['tipo'], 'video')
        a = d['estrutura']['seccoes'][0]['aulas'][0]
        self.assertEqual(a['video']['url'], 'https://exemplo.ao/v0.mp4')
        self.assertEqual(a['materiais'][0]['url'], 'https://exemplo.ao/guia.pdf')
        self.assertEqual(a['questionario']['perguntas'], 1)
        self.assertTrue(a['questionario']['activo'])

    def test_pratica_com_respostas(self):
        curso = self.curso_pratica(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft',
                                   licoes=2)
        self.entrar(self.admin)
        d = self.client.get(f'{ADMIN}{curso.id}/').json()
        self.assertEqual(d['estrutura']['tipo'], 'pratica')
        licoes = d['estrutura']['unidades'][0]['licoes']
        self.assertEqual(len(licoes), 2)
        self.assertEqual(licoes[0]['n_exercicios'], 3)
        ex = licoes[0]['exercicios'][0]
        self.assertEqual(ex['tipo'], 'escolher')
        self.assertEqual(ex['enunciado'], 'Pergunta 0')
        self.assertEqual([o['certa'] for o in ex['opcoes']], [True, False])
        self.assertTrue(d['verificacao']['pode_submeter'])

    def test_curso_inexistente(self):
        self.entrar(self.admin)
        r = self.client.get(f'{ADMIN}00000000-0000-0000-0000-000000000000/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['code'], 'not_found')


class ArquivarAdminTests(Base):
    def setUp(self):
        super().setUp()
        self.curso = self.curso_video(status='Published')
        self.entrar(self.admin)

    def test_arquiva_e_avisa(self):
        r = self.client.post(f'{ADMIN}{self.curso.id}/arquivar/', {'modo': 'fechar', 'motivo': 'Direitos de autor'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['curso']['estado'], 'arquivado')
        self.curso.refresh_from_db()
        self.assertEqual((self.curso.status, self.curso.modo_arquivo), ('Archived', 'fechar'))
        self.assertIsNotNone(self.curso.arquivado_em)
        aviso = Notification.objects.filter(user=self.prof, kind=Notification.KIND_COURSE).latest('created_at')
        self.assertIn('Direitos de autor', aviso.body)
        self.assertEqual((self.curso.motivo_moderacao, self.curso.moderacao_accao, self.curso.moderado_por_id),
                         ('Direitos de autor', 'arquivar', self.admin.id))
        self.assertIsNotNone(self.curso.moderado_em)
        # Outra vez no mesmo modo: 400; noutro modo: muda.
        r = self.client.post(f'{ADMIN}{self.curso.id}/arquivar/', {'modo': 'fechar', 'motivo': 'De novo aqui'},
                             format='json')
        self.assertEqual(r.json()['code'], 'ja_arquivado')
        r = self.client.post(f'{ADMIN}{self.curso.id}/arquivar/', {'modo': 'manter', 'motivo': 'Afinal manter'},
                             format='json')
        self.assertEqual(r.status_code, 200)

    def test_arquiva_curso_em_revisao(self):
        c = self.curso_video(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft')
        r = self.client.post(f'{ADMIN}{c.id}/arquivar/', {'modo': 'manter', 'motivo': 'Duplicado de outro'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual((c.status, c.estado_antes_revisao, c.submetido_em), ('Archived', '', None))

    def test_validacao(self):
        r = self.client.post(f'{ADMIN}{self.curso.id}/arquivar/', {'modo': 'apagar'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(r.json()['details']['modo'], list)
        self.assertIsInstance(r.json()['details']['motivo'], list)
        r = self.client.post(f'{ADMIN}00000000-0000-0000-0000-000000000000/arquivar/',
                             {'modo': 'manter', 'motivo': 'Qualquer motivo'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.status, 'Published')


class ModeracaoTests(Base):
    """O professor vê porque é que o administrador recusou/arquivou o curso (motivo_moderacao)."""

    def test_arquivar_guarda_motivo_e_limpa_recusa_antiga(self):
        curso = self.curso_video(status='Published', motivo_recusa='Recusa antiga')
        self.entrar(self.admin)
        r = self.client.post(f'{ADMIN}{curso.id}/arquivar/', {'modo': 'fechar', 'motivo': 'Conteúdo copiado'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        curso.refresh_from_db()
        self.assertEqual(curso.motivo_recusa, '')
        self.entrar(self.prof)
        for url in (f'{PROF}cursos/{curso.id}/', f'{PROF}cursos/{curso.id}/estrutura/'):
            d = self.client.get(url).json()
            d = d.get('curso', d)
            self.assertEqual(d['estado'], 'arquivado', url)
            self.assertEqual(d['motivo_moderacao'], 'Conteúdo copiado', url)
            self.assertIsNone(d['motivo_recusa'], url)
            self.assertEqual(d['moderacao']['accao'], 'arquivar', url)

    def test_recusar_republicacao_de_arquivado_mostra_motivo(self):
        curso = self.curso_pratica(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Archived',
                                   modo_arquivo='manter')
        self.entrar(self.admin)
        r = self.client.post(f'{ADMIN}{curso.id}/recusar/', {'motivo': 'Faltam exemplos.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['curso']['motivo_moderacao'], 'Faltam exemplos.')
        self.entrar(self.prof)
        d = self.client.get(f'{PROF}pratica/{curso.id}/estrutura/').json()['curso']
        self.assertEqual((d['estado'], d['motivo_moderacao']), ('arquivado', 'Faltam exemplos.'))
        self.assertEqual(d['moderacao']['accao'], 'recusar')

    def test_aprovar_limpa_motivo(self):
        curso = self.curso_pratica(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft',
                                   motivo_moderacao='Antigo', moderacao_accao='recusar')
        self.entrar(self.admin)
        self.assertEqual(self.client.post(f'{ADMIN}{curso.id}/aprovar/', {}, format='json').status_code, 200)
        curso.refresh_from_db()
        self.assertEqual((curso.motivo_moderacao, curso.moderacao_accao), ('', ''))

    def test_aprovar_com_verificacao_incompleta_traz_verificacao_fresca(self):
        curso = self.curso_video(status='InReview', submetido_em=timezone.now(), estado_antes_revisao='Draft')
        Chapter.objects.filter(section__course=curso).delete()
        self.entrar(self.admin)
        r = self.client.post(f'{ADMIN}{curso.id}/aprovar/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        corpo = r.json()
        self.assertEqual(corpo['code'], 'verificacao_incompleta')
        self.assertFalse(corpo['verificacao']['pode_submeter'])
        self.assertTrue(any(not i['ok'] for i in corpo['verificacao']['itens']))

    def test_avisos_no_mesmo_segundo_nao_colidem(self):
        c1 = self.curso_video(status='Published', titulo='Um')
        self.entrar(self.admin)
        agora = timezone.now()
        with mock.patch('django.utils.timezone.now', return_value=agora):
            self.client.post(f'{ADMIN}{c1.id}/arquivar/', {'modo': 'fechar', 'motivo': 'Primeiro motivo'},
                             format='json')
            self.client.post(f'{ADMIN}{c1.id}/arquivar/', {'modo': 'manter', 'motivo': 'Segundo motivo'},
                             format='json')
        avisos = Notification.objects.filter(user=self.prof, kind=Notification.KIND_COURSE)
        self.assertEqual(avisos.count(), 2)


class PublicacaoDirectaTests(Base):
    """Professor de confiança: submeter publica logo (se a lista de verificação passar)."""

    def _confianca(self, valor=True):
        return mock.patch.object(painel, 'professor_publica_sem_revisao', return_value=valor)

    def test_sem_marca_vai_para_revisao(self):
        curso = self.curso_pratica()
        self.entrar(self.prof)
        with self._confianca(False):
            r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 200)
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'InReview')
        self.assertEqual(curso.estado_antes_revisao, 'Draft')

    def test_com_marca_publica_e_avisa(self):
        curso = self.curso_pratica(motivo_recusa='Antigo')
        self.entrar(self.prof)
        with self._confianca():
            r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['curso']['estado'], 'publicado')
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'Published')
        self.assertIsNotNone(curso.aprovado_em)
        self.assertIsNone(curso.aprovado_por)
        self.assertEqual((curso.motivo_recusa, curso.estado_antes_revisao), ('', ''))
        aviso = Notification.objects.filter(user=self.prof, kind=Notification.KIND_COURSE).latest('created_at')
        self.assertEqual(aviso.title, 'Curso publicado')

    def test_com_marca_republica_arquivado(self):
        curso = self.curso_video(status='Archived', modo_arquivo='manter', arquivado_em=timezone.now())
        self.entrar(self.prof)
        with self._confianca():
            r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 200)
        curso.refresh_from_db()
        self.assertEqual((curso.status, curso.modo_arquivo, curso.arquivado_em, curso.estado_antes_revisao),
                         ('Published', '', None, ''))

    def test_com_marca_mas_lista_incompleta(self):
        curso = self.curso_pratica()
        PracticeChallenge.objects.filter(lesson=curso.licoes[0]).first().delete()
        self.entrar(self.prof)
        with self._confianca():
            r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verificacao_incompleta')
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'Draft')

    @skipUnless(TEM_CAMPO_CONFIANCA, 'PerfilProfessor.publica_sem_revisao ainda não existe')
    def test_campo_real(self):
        self.assertFalse(painel.professor_publica_sem_revisao(self.prof.id))  # sem perfil
        PerfilProfessor.objects.create(user=self.prof, publica_sem_revisao=True)
        self.assertTrue(painel.professor_publica_sem_revisao(self.prof.id))
        curso = self.curso_pratica()
        self.entrar(self.prof)
        r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.json()['curso']['estado'], 'publicado')
        self.assertTrue(self.client.get(f'{ADMIN}{curso.id}/').status_code in (403,))  # professor não é admin
        self.entrar(self.admin)
        self.assertTrue(self.client.get(f'{ADMIN}{curso.id}/').json()['professor']['publica_sem_revisao'])
