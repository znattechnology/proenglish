"""
Área do professor (fase 1): permissões do conteúdo, ciclo de vida do curso (submeter, aprovar,
recusar, arquivar), efeitos no lado do aluno, definições e números do painel.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import (
    Chapter, Course, CourseEnrollment, CourseGradingConfig, CourseSection, UserCourseProgress,
)
from apps.practice.models import (
    ChallengeAttempt, ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit,
)
from apps.users.models import Notification, User

PRATICA = '/api/v1/practice/'
PROF = '/api/v1/teacher/'
ADMIN = '/api/v1/admin/cursos/'
ALUNO_PRATICA = '/api/v1/student/practice-courses/'
ALUNO_VIDEO = '/api/v1/student/video-courses/'


class Base(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-ciclo@example.com', name='Prof', password='x12345678',
                                             role='teacher')
        self.outro_prof = User.objects.create_user(email='outro-ciclo@example.com', name='Outro',
                                                   password='x12345678', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-ciclo@example.com', name='Aluno', password='x12345678',
                                              role='student')
        self.admin = User.objects.create_user(email='admin-ciclo@example.com', name='Admin', password='x12345678',
                                              role='admin')

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def curso_pratica(self, status='Draft', licoes=1, exercicios=3, **extra):
        curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Inglês no Terminal',
                                      description='Curso de prática', category='Oil & Gas', level='Intermediate',
                                      course_type='practice', status=status, **extra)
        unidade = PracticeUnit.objects.create(course=curso, title='Unidade 1', description='', order=1)
        curso.licoes = []
        for n in range(licoes):
            licao = PracticeLesson.objects.create(unit=unidade, title=f'Lição {n + 1}', order=n + 1)
            licao.exs = []
            for i in range(exercicios):
                ch = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question=f'Pergunta {i}', order=i)
                ch.certa = ChallengeOption.objects.create(challenge=ch, text='Certa', is_correct=True, order=1)
                ch.errada = ChallengeOption.objects.create(challenge=ch, text='Errada', is_correct=False, order=2)
                licao.exs.append(ch)
            curso.licoes.append(licao)
        return curso

    def curso_video(self, status='Draft', com_video=True, **extra):
        curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Inglês para Plataformas',
                                      description='Curso em vídeo', category='Industry English', level='Beginner',
                                      course_type='video', status=status,
                                      image='https://exemplo.ao/capa.jpg', **extra)
        seccao = CourseSection.objects.create(course=curso, sectionTitle='Secção 1', order=1)
        curso.aula = Chapter.objects.create(section=seccao, title='Assinar a passagem', content='x', type='Video',
                                            video='https://exemplo.ao/v.mp4' if com_video else '', order=1)
        return curso


class PermissoesConteudoPraticaTests(Base):
    def setUp(self):
        super().setUp()
        self.curso = self.curso_pratica()
        self.licao = self.curso.licoes[0]
        self.ex = self.licao.exs[0]

    def test_aluno_nao_cria_unidade(self):
        self.entrar(self.aluno)
        r = self.client.post(f'{PRATICA}units/', {'course': str(self.curso.id), 'title': 'X', 'order': 2},
                             format='json')
        self.assertEqual(r.status_code, 403)

    def test_outro_professor_nao_cria_nem_altera(self):
        # As escritas nas rotas antigas foram retiradas (410): edita-se em /api/v1/teacher/pratica/.
        self.entrar(self.outro_prof)
        r = self.client.post(f'{PRATICA}lessons/', {'unit': str(self.licao.unit_id), 'title': 'X', 'order': 9},
                             format='json')
        self.assertEqual(r.status_code, 410)
        r = self.client.patch(f'{PRATICA}challenges/{self.ex.id}/', {'question': 'Mudada'}, format='json')
        self.assertEqual(r.status_code, 410)
        r = self.client.delete(f'{PRATICA}units/{self.licao.unit_id}/')
        self.assertEqual(r.status_code, 410)
        r = self.client.patch(f'{PRATICA}challenge-options/{self.ex.certa.id}/', {'is_correct': False}, format='json')
        self.assertEqual(r.status_code, 410)
        r = self.client.post(f'{PRATICA}challenge-options/', {'challenge_id': str(self.ex.id), 'text': 'Y'},
                             format='json')
        self.assertEqual(r.status_code, 410)
        self.ex.refresh_from_db()
        self.assertEqual(self.ex.question, 'Pergunta 0')

    def test_leituras_de_rascunho_so_para_o_dono(self):
        for user in (self.aluno, self.outro_prof):
            self.entrar(user)
            self.assertEqual(self.client.get(f'{PRATICA}lessons/{self.licao.id}/').status_code, 404)
            self.assertEqual(self.client.get(f'{PRATICA}challenge-options/{self.ex.certa.id}/').status_code, 404)
            self.assertEqual(self.client.get(f'{PRATICA}units/{self.licao.unit_id}/lessons/').status_code, 404)
            self.assertEqual(self.client.get(f'{PRATICA}courses/{self.curso.id}/units-with-progress/').status_code, 404)
            r = self.client.get(f'{PRATICA}challenges/?lesson={self.licao.id}')
            self.assertEqual(r.json()['data'], [])

    def test_dono_ve_respostas_aluno_nao(self):
        self.entrar(self.prof)
        r = self.client.get(f'{PRATICA}lessons/{self.licao.id}/')
        self.assertEqual(r.status_code, 200)
        opcoes = r.json()['challenges'][0]['options']
        self.assertTrue(any(o['is_correct'] for o in opcoes))
        # Publicado: o aluno vê a estrutura pelo endpoint do aluno, sem respostas.
        Course.objects.filter(pk=self.curso.pk).update(status='Published')
        self.entrar(self.aluno)
        r = self.client.get(f'{ALUNO_PRATICA}courses/{self.curso.id}/units-with-progress/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('is_correct', r.content.decode())

    def test_escritas_antigas_retiradas_410(self):
        # Nem o dono escreve pelas rotas antigas (não passavam pelas validações do editor novo).
        self.entrar(self.prof)
        antes = PracticeChallenge.objects.count()
        for prefixo in (PRATICA, '/api/v1/teacher/practice-courses/'):
            r = self.client.post(f'{prefixo}challenges/', {
                'lesson': str(self.licao.id), 'type': 'SELECT', 'question': 'Nova', 'order': 10,
                'options': [{'text': 'A', 'is_correct': True}, {'text': 'B', 'is_correct': False}],
            }, format='json')
            self.assertEqual(r.status_code, 410, r.content)
            self.assertEqual(r.json()['code'], 'rota_removida')
            self.assertIn('editor', r.json()['message'])
            for metodo, rota in (('put', f'challenges/{self.ex.id}/'), ('delete', f'lessons/{self.licao.id}/'),
                                 ('post', 'units/'), ('patch', f'units/{self.licao.unit_id}/'),
                                 ('post', 'challenge-options/'), ('delete', f'challenge-options/{self.ex.certa.id}/')):
                r = getattr(self.client, metodo)(f'{prefixo}{rota}', {}, format='json')
                self.assertEqual(r.status_code, 410, (prefixo, metodo, rota))
        self.assertEqual(PracticeChallenge.objects.count(), antes)
        self.assertTrue(ChallengeOption.objects.filter(id=self.ex.certa.id).exists())

    def test_ajudas_ia_so_professores(self):
        self.entrar(self.aluno)
        for rota in ('generate-translation-suggestions/', 'generate-pronunciation-exercise/',
                     'generate-reference-audio/'):
            self.assertEqual(self.client.post(f'{PRATICA}{rota}', {}, format='json').status_code, 403, rota)

    def test_lista_de_cursos_do_professor_so_os_seus(self):
        alheio = Course.objects.create(teacher=self.outro_prof, title='Alheio', course_type='practice', status='Draft')
        self.entrar(self.prof)
        ids = {c['id'] for c in self.client.get(f'{PRATICA}courses/?include_stats=true').json()}
        self.assertIn(str(self.curso.id), ids)
        self.assertNotIn(str(alheio.id), ids)
        r = self.client.get(f'{PRATICA}courses/?include_drafts=false')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_analytics_de_curso_alheio(self):
        self.entrar(self.outro_prof)
        self.assertEqual(self.client.get(f'{PRATICA}analytics/?course={self.curso.id}').status_code, 404)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{PRATICA}analytics/').status_code, 403)


class PermissoesVideoTests(Base):
    def setUp(self):
        super().setUp()
        self.curso = self.curso_video()

    def test_gets_de_gestao_so_para_o_dono(self):
        seccao = self.curso.sections.first()
        rotas = [
            f'/api/v1/teacher/video-courses/{self.curso.id}/sections/',
            f'/api/v1/teacher/video-courses/sections/{seccao.id}/chapters/',
            f'/api/v1/teacher/video-courses/chapters/{self.curso.aula.id}/resources/',
            f'/api/v1/teacher/video-courses/chapters/{self.curso.aula.id}/quiz/',
            f'/api/v1/teacher/video-courses/chapters/{self.curso.aula.id}/comments/',
        ]
        for user in (self.aluno, self.outro_prof):
            self.entrar(user)
            for rota in rotas:
                self.assertEqual(self.client.get(rota).status_code, 404, (user.email, rota))
        self.entrar(self.prof)
        for rota in rotas:
            self.assertEqual(self.client.get(rota).status_code, 200, rota)

    def test_professor_nao_publica_nem_destaca(self):
        self.entrar(self.prof)
        r = self.client.post('/api/v1/teacher/video-courses/', {'title': 'Novo', 'status': 'Published',
                                                                'is_featured': True}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        novo = Course.objects.get(id=r.json()['data']['courseId'])
        self.assertEqual((novo.status, novo.is_featured), ('Draft', False))
        # A edição antiga foi retirada (410): edita-se no editor novo (teacher/cursos/).
        r = self.client.put(f'/api/v1/teacher/video-courses/{self.curso.id}/', {'status': 'Published'}, format='json')
        self.assertEqual(r.status_code, 410)
        r = self.client.patch(f'/api/v1/courses/{self.curso.id}/', {'status': 'Published'}, format='json')
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.json()['code'], 'rota_removida')
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.status, 'Draft')

    def test_legado_nao_mostra_rascunhos(self):
        self.client.credentials()
        self.assertEqual(self.client.get(f'/api/v1/courses/{self.curso.id}/').status_code, 404)


class CicloDeVidaTests(Base):
    def test_verificacao_e_submeter_video(self):
        curso = self.curso_video(com_video=False)
        self.entrar(self.prof)
        r = self.client.get(f'{PROF}cursos/{curso.id}/verificacao/')
        self.assertEqual(r.status_code, 200)
        corpo = r.json()
        self.assertFalse(corpo['pode_submeter'])
        videos = next(i for i in corpo['itens'] if i['chave'] == 'videos')
        self.assertEqual(videos['detalhe'], '1 aula sem vídeo: Secção 1, "Assinar a passagem".')
        r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verificacao_incompleta')
        self.assertIn('itens', r.json())
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'Draft')

        Chapter.objects.filter(pk=curso.aula.pk).update(video='https://exemplo.ao/v.mp4')
        r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 200, r.content)
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'InReview')
        self.assertEqual(r.json()['curso']['estado'], 'em_revisao')

    def test_verificacao_pratica(self):
        curso = self.curso_pratica(exercicios=2)
        self.entrar(self.prof)
        corpo = self.client.get(f'{PROF}cursos/{curso.id}/verificacao/').json()
        itens = {i['chave']: i for i in corpo['itens']}
        self.assertFalse(itens['exercicios']['ok'])
        self.assertIn('Unidade 1, "Lição 1"', itens['exercicios']['detalhe'])
        PracticeChallenge.objects.create(lesson=curso.licoes[0], type='SELECT', question='Sem certa', order=9)
        corpo = self.client.get(f'{PROF}cursos/{curso.id}/verificacao/').json()
        itens = {i['chave']: i for i in corpo['itens']}
        self.assertTrue(itens['exercicios']['ok'])
        self.assertFalse(itens['respostas']['ok'])
        self.assertFalse(corpo['pode_submeter'])

    def test_outro_professor_e_aluno_nao_mexem_no_ciclo(self):
        curso = self.curso_pratica()
        for user in (self.outro_prof, self.aluno):
            self.entrar(user)
            r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
            self.assertIn(r.status_code, (403, 404))
        self.entrar(self.prof)
        self.assertEqual(self.client.post(f'{ADMIN}{curso.id}/aprovar/').status_code, 403)

    def test_aprovar_e_recusar_com_aviso(self):
        curso = self.curso_pratica()
        self.entrar(self.prof)
        self.assertEqual(self.client.post(f'{PROF}cursos/{curso.id}/submeter/').status_code, 200)
        self.entrar(self.admin)
        lista = self.client.get(f'{ADMIN}revisao/').json()
        self.assertEqual([c['id'] for c in lista['resultados']], [str(curso.id)])
        r = self.client.post(f'{ADMIN}{curso.id}/recusar/', {'motivo': ''}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f'{ADMIN}{curso.id}/recusar/', {'motivo': 'Faltam exemplos de áudio.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        curso.refresh_from_db()
        self.assertEqual((curso.status, curso.motivo_recusa), ('Draft', 'Faltam exemplos de áudio.'))
        aviso = Notification.objects.get(user=self.prof, title='Curso não aprovado')
        self.assertIn('Faltam exemplos de áudio.', aviso.body)

        self.entrar(self.prof)
        item = next(c for c in self.client.get(f'{PROF}cursos/?tipo=pratica').json()['resultados']
                    if c['id'] == str(curso.id))
        self.assertEqual((item['estado'], item['motivo_recusa']), ('rascunho', 'Faltam exemplos de áudio.'))
        self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.entrar(self.admin)
        r = self.client.post(f'{ADMIN}{curso.id}/aprovar/')
        self.assertEqual(r.status_code, 200, r.content)
        curso.refresh_from_db()
        self.assertEqual((curso.status, curso.aprovado_por_id), ('Published', self.admin.id))
        self.assertTrue(Notification.objects.filter(user=self.prof, title='Curso aprovado').exists())

    def test_cancelar_revisao(self):
        curso = self.curso_pratica()
        self.entrar(self.prof)
        self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        r = self.client.post(f'{PROF}cursos/{curso.id}/cancelar-revisao/')
        self.assertEqual(r.status_code, 200)
        curso.refresh_from_db()
        self.assertEqual(curso.status, 'Draft')
        self.assertEqual(self.client.post(f'{PROF}cursos/{curso.id}/cancelar-revisao/').status_code, 400)

    def test_em_revisao_fora_do_catalogo(self):
        curso = self.curso_pratica(status='InReview')
        self.entrar(self.aluno)
        ids = {c['id'] for c in self.client.get(f'{ALUNO_PRATICA}courses/').json()}
        self.assertNotIn(str(curso.id), ids)
        r = self.client.get(f'{ALUNO_PRATICA}lessons/{curso.licoes[0].id}/jogar/')
        self.assertEqual(r.status_code, 404)

    def test_modo_de_arquivo_obrigatorio(self):
        curso = self.curso_pratica(status='Published')
        self.entrar(self.prof)
        self.assertEqual(self.client.post(f'{PROF}cursos/{curso.id}/arquivar/', {}, format='json').status_code, 400)


class ArquivoEfeitosAlunoTests(Base):
    def setUp(self):
        super().setUp()
        self.pratica = self.curso_pratica(status='Published')
        self.video = self.curso_video(status='Published')
        CourseEnrollment.objects.create(user=self.aluno, course=self.video)
        UserCourseProgress.objects.create(user=self.aluno, course=self.video, enrollmentDate=timezone.now())
        ChallengeProgress.objects.create(user=self.aluno, challenge=self.pratica.licoes[0].exs[0], completed=True)
        self.novo = User.objects.create_user(email='novo-ciclo@example.com', name='Novo', password='x12345678',
                                             role='student')

    def arquivar(self, curso, modo):
        self.entrar(self.prof)
        r = self.client.post(f'{PROF}cursos/{curso.id}/arquivar/', {'modo': modo}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_manter(self):
        self.arquivar(self.pratica, 'manter')
        self.arquivar(self.video, 'manter')
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{ALUNO_PRATICA}lessons/{self.pratica.licoes[0].id}/jogar/').status_code, 200)
        self.assertEqual(self.client.get(f'{ALUNO_VIDEO}chapters/{self.video.aula.id}/').status_code, 200)
        catalogo = self.client.get(ALUNO_VIDEO).json()
        self.assertNotIn(str(self.video.id), [c['courseId'] for c in catalogo['data']['results']])
        # Sem inscrições novas
        self.entrar(self.novo)
        r = self.client.post(f'{ALUNO_VIDEO}transactions/create/', {
            'courseId': str(self.video.id), 'transactionId': 'x', 'amount': 0, 'paymentProvider': 'stripe'},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'curso_arquivado')
        r = self.client.get(f'{ALUNO_PRATICA}lessons/{self.pratica.licoes[0].id}/jogar/')
        self.assertEqual(r.status_code, 403)

    def test_fechar(self):
        self.arquivar(self.pratica, 'fechar')
        self.arquivar(self.video, 'fechar')
        self.entrar(self.aluno)
        r = self.client.get(f'{ALUNO_PRATICA}lessons/{self.pratica.licoes[0].id}/jogar/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'curso_fechado')
        self.assertIn(self.client.get(f'{ALUNO_VIDEO}chapters/{self.video.aula.id}/').status_code, (403, 404))


class DefinicoesTests(Base):
    def test_patch_lista_fechada_e_nota_minima(self):
        curso = self.curso_pratica()
        self.entrar(self.prof)
        r = self.client.patch(f'{PROF}cursos/{curso.id}/', {'status': 'Published'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f'{PROF}cursos/{curso.id}/', {
            'titulo': 'Inglês no Terminal II', 'area': 'Petróleo e Gás', 'nivel': 'avançado',
            'visivel_catalogo': False, 'maximo_alunos': 30, 'nota_minima': 80, 'pode_repetir': False,
            'tempo_limite_questionario_min': 15,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        corpo = r.json()
        self.assertEqual(corpo['titulo'], 'Inglês no Terminal II')
        self.assertEqual(corpo['area'], 'Petróleo e Gás')
        self.assertEqual(corpo['definicoes']['nota_minima'], 80)
        self.assertFalse(corpo['definicoes']['pode_repetir'])
        curso.refresh_from_db()
        self.assertEqual((curso.category, curso.level, curso.maximo_alunos), ('Oil & Gas', 'Advanced', 30))
        self.assertEqual(CourseGradingConfig.objects.get(course=curso).min_final_grade, 80)
        r = self.client.patch(f'{PROF}cursos/{curso.id}/', {'nota_minima': 40}, format='json')
        self.assertEqual(r.status_code, 400)
        self.entrar(self.outro_prof)
        self.assertEqual(self.client.patch(f'{PROF}cursos/{curso.id}/', {'titulo': 'Roubado'},
                                           format='json').status_code, 404)

    def test_visivel_catalogo_e_maximo_alunos(self):
        curso = self.curso_video(status='Published', visivel_catalogo=False)
        self.entrar(self.aluno)
        ids = [c['courseId'] for c in self.client.get(ALUNO_VIDEO).json()['data']['results']]
        self.assertNotIn(str(curso.id), ids)
        Course.objects.filter(pk=curso.pk).update(visivel_catalogo=True, maximo_alunos=1)
        CourseEnrollment.objects.create(user=self.outro_prof, course=curso)
        r = self.client.post(f'{ALUNO_VIDEO}transactions/create/', {
            'courseId': str(curso.id), 'transactionId': 'x', 'amount': 0, 'paymentProvider': 'stripe'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'curso_cheio')

    def test_pode_repetir(self):
        curso = self.curso_pratica(status='Published', definicoes={'pode_repetir': False})
        for ch in curso.licoes[0].exs:
            ChallengeProgress.objects.create(user=self.aluno, challenge=ch, completed=True)
        self.entrar(self.aluno)
        r = self.client.get(f'{ALUNO_PRATICA}lessons/{curso.licoes[0].id}/jogar/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'repeticao_desligada')


class ResumosTests(Base):
    def test_cursos_e_painel(self):
        pratica = self.curso_pratica(status='Published', licoes=2)
        video = self.curso_video(status='InReview')
        self.curso_video(status='Draft', com_video=False)
        Course.objects.create(teacher=self.outro_prof, title='Alheio', course_type='practice', status='Published')
        ex = pratica.licoes[0].exs[0]
        for ch in pratica.licoes[0].exs:
            ChallengeProgress.objects.create(user=self.aluno, challenge=ch, completed=True)
        for correcto in (False, False, True):
            ChallengeAttempt.objects.create(user=self.aluno, challenge=ex, is_correct=correcto)
        CourseEnrollment.objects.create(user=self.aluno, course=video)
        UserCourseProgress.objects.create(user=self.aluno, course=video, enrollmentDate=timezone.now(),
                                          overallProgress=40)

        self.entrar(self.prof)
        r = self.client.get(f'{PROF}cursos/?tipo=pratica')
        self.assertEqual(r.status_code, 200)
        corpo = r.json()
        self.assertEqual(len(corpo['resultados']), 1)
        item = corpo['resultados'][0]
        self.assertEqual(item['tipo'], 'pratica')
        self.assertEqual(item['estado'], 'publicado')
        self.assertEqual(item['area'], 'Petróleo e Gás')
        self.assertEqual(item['nivel'], 'Intermédio (B1)')
        self.assertEqual((item['alunos'], item['unidades'], item['licoes'], item['exercicios']), (1, 1, 2, 6))
        self.assertEqual(item['conclusao'], 50.0)
        self.assertEqual(item['acerto'], 33.3)
        self.assertIsNone(item['aulas'])
        self.assertEqual(corpo['numeros']['publicados'], 1)
        self.assertEqual(corpo['numeros']['acerto_medio'], 33.3)

        r = self.client.get(f'{PROF}cursos/?tipo=video&estado=em_revisao')
        corpo = r.json()
        self.assertEqual([c['id'] for c in corpo['resultados']], [str(video.id)])
        self.assertEqual(corpo['numeros']['em_revisao'], 1)
        self.assertEqual(corpo['numeros']['rascunhos'], 1)
        self.assertEqual(corpo['resultados'][0]['conclusao'], 40.0)
        self.assertEqual(self.client.get(f'{PROF}cursos/?estado=xpto').status_code, 400)

        painel = self.client.get(f'{PROF}painel/').json()
        self.assertEqual(painel['numeros']['publicados'], 1)
        self.assertEqual(painel['numeros']['alunos'], 1)
        self.assertEqual(painel['numeros']['alunos_activos_7d'], 1)
        self.assertEqual(len(painel['cursos']), 3)
        self.assertEqual(painel['tropecos'][0]['challenge_id'], str(ex.id))
        self.assertEqual(painel['tropecos'][0]['erros'], 2)
        self.assertEqual(painel['tropecos'][0]['onde'], 'Unidade 1, lição 1')
        self.assertEqual(painel['tropecos'][0]['acerto'], 33)
        self.assertEqual(painel['tropecos'][0]['licao_id'], str(ex.lesson_id))
        self.assertEqual(painel['tropecos'][0]['unidade_id'], str(ex.lesson.unit_id))

    def test_aluno_nao_tem_painel(self):
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{PROF}painel/').status_code, 403)
        self.assertEqual(self.client.get(f'{PROF}cursos/').status_code, 403)

    def test_painel_sem_dados(self):
        self.entrar(self.prof)
        painel = self.client.get(f'{PROF}painel/').json()
        self.assertEqual(painel['tropecos'], [])
        self.assertEqual(painel['cursos'], [])
        self.assertIsNone(painel['numeros']['conclusao_media'])
