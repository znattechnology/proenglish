"""
Editor de cursos em vídeo do professor (base nova): criação, estrutura, secções, aulas,
questionário, envios de ficheiros e o efeito da percentagem vista no lado do aluno.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_editor_video
"""
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.api.student.video_courses.conteudo import codigo_opcao
from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, ChapterResource, Course, CourseSection,
)
from apps.practice.models import PracticeUnit
from apps.subscriptions.models import SubscriptionPlan, UserSubscription
from apps.users.models import User

PROF = '/api/v1/teacher/'
ALUNO = '/api/v1/student/video-courses/'
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 200


@override_settings(ENVIOS_LOCAIS=True)  # o modo local de envios só existe em desenvolvimento
class Base(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-editor@example.com', name='Prof', password='x12345678',
                                             role='teacher')
        self.outro = User.objects.create_user(email='outro-editor@example.com', name='Outro', password='x12345678',
                                              role='teacher')
        self.aluno = User.objects.create_user(email='aluno-editor@example.com', name='Aluno', password='x12345678',
                                              role='student')
        self.admin = User.objects.create_user(email='admin-editor@example.com', name='Admin', password='x12345678',
                                              role='admin')
        self.entrar(self.prof)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def criar(self, **extra):
        corpo = {'tipo': 'video', 'titulo': 'Inglês na Plataforma', 'descricao': 'Segurança a bordo',
                 'area': 'Petróleo e Gás', 'nivel': 'B1', 'acesso': 'premium',
                 'seccoes': ['Chegada', 'Turno']}
        corpo.update(extra)
        return self.client.post(f'{PROF}cursos/', corpo, format='json')

    def curso_com_aulas(self):
        r = self.criar()
        self.assertEqual(r.status_code, 201, r.content)
        curso = Course.objects.get(id=r.data['id'])
        s1, s2 = CourseSection.objects.filter(course=curso).order_by('order')
        a1 = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/', {'titulo': 'Aula 1'}, format='json').data
        a2 = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/', {'titulo': 'Aula 2'}, format='json').data
        return curso, s1, s2, a1, a2


class CriarCursoTests(Base):
    def test_opcoes(self):
        r = self.client.get(f'{PROF}cursos/opcoes/')
        self.assertEqual(r.status_code, 200)
        self.assertIn({'valor': 'Industry English', 'nome': 'Petróleo e Gás'}, r.data['areas'])
        self.assertEqual([n['valor'] for n in r.data['niveis']], ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'])
        self.assertIn({'valor': 'B1', 'nome': 'B1 (Intermédio)',
                       'descricao': 'Consigo conversar sobre o trabalho com algum apoio'}, r.data['niveis'])
        # Os valores antigos com o mesmo rótulo vêm marcados como legado (para mostrar o valor actual).
        nomes = [a['nome'] for a in r.data['areas'] if not a.get('legado')]
        self.assertEqual(len(nomes), len(set(nomes)))
        self.assertIn({'valor': 'Technology English', 'nome': 'Tecnologia', 'legado': True}, r.data['areas'])
        r = self.client.get(f'{PROF}cursos/opcoes/?tipo=pratica')
        self.assertIn({'valor': 'Oil & Gas', 'nome': 'Petróleo e Gás'}, r.data['areas'])

    def test_criar_video_com_seccoes(self):
        r = self.criar()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['estado'], 'rascunho')
        self.assertEqual(r.data['tipo'], 'video')
        self.assertEqual(r.data['area'], 'Petróleo e Gás')
        self.assertEqual(r.data['nivel'], 'Nível B1')
        self.assertEqual(r.data['nivel_codigo'], 'B1')
        self.assertEqual(r.data['acesso'], 'premium')
        self.assertEqual(r.data['seccoes'], 2)
        curso = Course.objects.get(id=r.data['id'])
        self.assertEqual((curso.status, curso.access_level, curso.category, curso.level, curso.teacher_id),
                         ('Draft', 'premium', 'Industry English', 'B1', self.prof.id))
        self.assertEqual(list(curso.sections.order_by('order').values_list('sectionTitle', flat=True)),
                         ['Chegada', 'Turno'])
        # Mesmo formato que o GET do detalhe.
        detalhe = self.client.get(f'{PROF}cursos/{curso.id}/').data
        self.assertTrue(set(detalhe) <= set(r.data))

    def test_criar_pratica_com_unidades_e_acesso_todos(self):
        r = self.criar(tipo='pratica', area='Banca', nivel='a2', acesso='todos', seccoes=None,
                       unidades=['Saudações', 'Números'])
        self.assertEqual(r.status_code, 201, r.content)
        curso = Course.objects.get(id=r.data['id'])
        self.assertEqual((curso.course_type, curso.category, curso.access_level, curso.status),
                         ('practice', 'Banking', 'free', 'Draft'))
        self.assertEqual(curso.level, 'A2')
        self.assertEqual(list(PracticeUnit.objects.filter(course=curso).order_by('order')
                              .values_list('title', flat=True)), ['Saudações', 'Números'])

    def test_nivel_so_aceita_cefr(self):
        for antigo in ('Beginner', 'Intermediate', 'Advanced', 'iniciante', 'Intermédio (B1)', 'D1'):
            r = self.criar(nivel=antigo)
            self.assertEqual(r.status_code, 400, antigo)
            self.assertIn('nivel', r.data['details'])
        for codigo in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'):
            r = self.criar(nivel=codigo)
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual(Course.objects.get(id=r.data['id']).level, codigo)

    def test_validacao(self):
        r = self.criar(titulo='x' * 61, area='Astronomia', nivel='Expert', acesso='vip', tipo='outro')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'validation_error')
        self.assertEqual(set(r.data['details']), {'titulo', 'area', 'nivel', 'acesso', 'tipo'})
        self.assertEqual(Course.objects.count(), 0)

    def test_estado_nao_vem_do_pedido(self):
        r = self.criar(estado='publicado', status='Published')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Course.objects.get(id=r.data['id']).status, 'Draft')

    def test_aluno_nao_cria(self):
        self.entrar(self.aluno)
        self.assertEqual(self.criar().status_code, 403)


class PermissoesTests(Base):
    def test_outro_professor_recebe_404_e_aluno_403(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        mat = ChapterResource.objects.create(chapter_id=a1['id'], title='m', resource_type='PDF',
                                             external_url='https://x.ao/m.pdf', created_by=self.prof)
        pedidos = [
            ('get', f'{PROF}cursos/{curso.id}/estrutura/', None),
            ('post', f'{PROF}cursos/{curso.id}/seccoes/', {'titulo': 'X'}),
            ('post', f'{PROF}cursos/{curso.id}/seccoes/ordem/', {'ids': [str(s2.id), str(s1.id)]}),
            ('patch', f'{PROF}seccoes/{s1.id}/', {'titulo': 'X'}),
            ('delete', f'{PROF}seccoes/{s1.id}/', None),
            ('post', f'{PROF}seccoes/{s1.id}/aulas/', {'titulo': 'X'}),
            ('post', f'{PROF}seccoes/{s1.id}/aulas/ordem/', {'ids': [a2['id'], a1['id']]}),
            ('patch', f'{PROF}aulas/{a1["id"]}/', {'titulo': 'X'}),
            ('delete', f'{PROF}aulas/{a1["id"]}/', None),
            ('get', f'{PROF}aulas/{a1["id"]}/questionario/', None),
            ('put', f'{PROF}aulas/{a1["id"]}/questionario/', {'activo': False, 'perguntas': []}),
            ('post', f'{PROF}aulas/{a1["id"]}/video/', {'nome': 'v.mp4', 'tamanho_bytes': 10, 'tipo_mime': 'video/mp4'}),
            ('post', f'{PROF}aulas/{a1["id"]}/materiais/', {'nome': 'a.pdf', 'tamanho_bytes': 10, 'tipo_mime': 'application/pdf'}),
            ('post', f'{PROF}cursos/{curso.id}/capa/', {'nome': 'c.png', 'tamanho_bytes': 10, 'tipo_mime': 'image/png'}),
            ('delete', f'{PROF}materiais/{mat.id}/', None),
        ]
        for user, esperado in ((self.outro, 404), (self.aluno, 403)):
            self.entrar(user)
            for metodo, url, corpo in pedidos:
                r = getattr(self.client, metodo)(url, corpo, format='json')
                self.assertEqual(r.status_code, esperado, f'{user.email} {metodo} {url}: {r.status_code}')
        # Nada mudou.
        self.assertEqual(Chapter.objects.filter(section__course=curso).count(), 2)
        self.assertEqual(CourseSection.objects.filter(course=curso).count(), 2)
        self.assertTrue(ChapterResource.objects.filter(id=mat.id).exists())
        # O administrador pode.
        self.entrar(self.admin)
        self.assertEqual(self.client.get(f'{PROF}cursos/{curso.id}/estrutura/').status_code, 200)

    def test_confirmar_chave_de_outro_utilizador(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}aulas/{a1["id"]}/video/',
                             {'nome': 'v.mp4', 'tamanho_bytes': len(MP4), 'tipo_mime': 'video/mp4'}, format='json')
        self.entrar(self.outro)
        r2 = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.data['code'], 'envio_invalido')
        r3 = self.client.put(r.data['upload_url'], MP4, content_type='video/mp4')
        self.assertEqual(r3.status_code, 404)


class EstruturaTests(Base):
    def test_estrutura_e_ordem(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        a3 = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/', {'titulo': 'Aula 3'}, format='json').data
        self.assertEqual([a1['ordem'], a2['ordem'], a3['ordem']], [1, 2, 3])
        self.assertEqual(a1['percentagem_vista'], 80)
        self.assertIsNone(a1['video'])
        self.assertEqual(a1['questionario'], {'activo': False, 'perguntas': 0, 'nota_minima': 70})

        r = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/ordem/', {'ids': [a3['id'], a1['id'], a2['id']]},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([a['titulo'] for a in r.data['aulas']], ['Aula 3', 'Aula 1', 'Aula 2'])
        r = self.client.post(f'{PROF}cursos/{curso.id}/seccoes/ordem/', {'ids': [str(s2.id), str(s1.id)]},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)

        e = self.client.get(f'{PROF}cursos/{curso.id}/estrutura/').data
        self.assertEqual([s['titulo'] for s in e['seccoes']], ['Turno', 'Chegada'])
        self.assertEqual([s['ordem'] for s in e['seccoes']], [1, 2])
        self.assertEqual([a['titulo'] for a in e['seccoes'][1]['aulas']], ['Aula 3', 'Aula 1', 'Aula 2'])
        self.assertEqual(e['curso']['id'], str(curso.id))
        aula = e['seccoes'][1]['aulas'][0]
        for chave in ('id', 'titulo', 'ordem', 'video', 'duracao_s', 'percentagem_vista', 'resumo',
                      'materiais', 'questionario'):
            self.assertIn(chave, aula)

    def test_ordem_invalida(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/ordem/', {'ids': [a1['id']]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'ordem_invalida')
        r = self.client.post(f'{PROF}seccoes/{s1.id}/aulas/ordem/', {'ids': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_seccoes_criar_mudar_apagar(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}cursos/{curso.id}/seccoes/', {'titulo': 'Partida'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data['ordem'], r.data['aulas']), (3, []))
        r = self.client.patch(f'{PROF}seccoes/{s1.id}/', {'titulo': 'Chegada ao heliporto'}, format='json')
        self.assertEqual(r.data['titulo'], 'Chegada ao heliporto')
        self.assertEqual(len(r.data['aulas']), 2)
        self.assertEqual(self.client.patch(f'{PROF}seccoes/{s1.id}/', {'titulo': ''}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'{PROF}seccoes/{s1.id}/').status_code, 204)
        self.assertFalse(Chapter.objects.filter(id=a1['id']).exists())

    def test_mudar_e_mover_aula(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        b1 = self.client.post(f'{PROF}seccoes/{s2.id}/aulas/', {'titulo': 'B1'}, format='json').data
        r = self.client.patch(f'{PROF}aulas/{a1["id"]}/', {
            'titulo': 'Briefing', 'resumo': 'O que dizer no briefing.', 'percentagem_vista': 100,
            'duracao_s': 312, 'seccao': str(s2.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['titulo'], r.data['resumo'], r.data['percentagem_vista'], r.data['duracao_s']),
                         ('Briefing', 'O que dizer no briefing.', 100, 312))
        self.assertEqual(r.data['ordem'], b1['ordem'] + 1)
        self.assertEqual(r.data['seccao'], str(s2.id))
        e = self.client.get(f'{PROF}cursos/{curso.id}/estrutura/').data
        self.assertEqual([a['titulo'] for a in e['seccoes'][1]['aulas']], ['B1', 'Briefing'])
        self.assertEqual([a['titulo'] for a in e['seccoes'][0]['aulas']], ['Aula 2'])

    def test_mover_para_seccao_de_outro_curso_e_validacao(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        outro = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Outro')
        s_outro = CourseSection.objects.create(course=outro, sectionTitle='S', order=1)
        r = self.client.patch(f'{PROF}aulas/{a1["id"]}/', {'seccao': str(s_outro.id), 'percentagem_vista': 70,
                                                         'duracao_s': -1}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data['details']), {'seccao', 'percentagem_vista', 'duracao_s'})
        self.assertEqual(str(Chapter.objects.get(id=a1['id']).section_id), str(s1.id))

    def test_apagar_aula(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        self.assertEqual(self.client.delete(f'{PROF}aulas/{a1["id"]}/').status_code, 204)
        self.assertFalse(Chapter.objects.filter(id=a1['id']).exists())

    def test_estrutura_de_curso_de_pratica(self):
        r = self.criar(tipo='pratica', seccoes=None, unidades=['U'])
        r = self.client.get(f'{PROF}cursos/{r.data["id"]}/estrutura/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'tipo_invalido')


def perguntas(n=3):
    return [{'enunciado': f'Pergunta {i}?', 'opcoes': ['Sim', 'Não', 'Talvez'], 'correcta': i % 3,
             'explicacao': f'Porque {i}.'} for i in range(n)]


class QuestionarioTests(Base):
    def test_validacao(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        url = f'{PROF}aulas/{a1["id"]}/questionario/'
        maus = [
            {'enunciado': '  ', 'opcoes': ['a', 'b'], 'correcta': 0},
            {'enunciado': 'P', 'opcoes': ['a'], 'correcta': 0},
            {'enunciado': 'P', 'opcoes': ['a', 'b', 'c', 'd', 'e', 'f'], 'correcta': 0},
            {'enunciado': 'P', 'opcoes': ['a', ''], 'correcta': 0},
            {'enunciado': 'P', 'opcoes': ['a', 'b'], 'correcta': 2},
            {'enunciado': 'P', 'opcoes': ['a', 'b'], 'correcta': True},
        ]
        for p in maus:
            r = self.client.put(url, {'activo': True, 'nota_minima': 70, 'perguntas': [p]}, format='json')
            self.assertEqual(r.status_code, 400, p)
            self.assertIn('0', r.data['details']['perguntas'])
        r = self.client.put(url, {'activo': True, 'nota_minima': 170, 'perguntas': perguntas()}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.put(url, {'activo': True, 'perguntas': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ChapterQuiz.objects.filter(chapter_id=a1['id']).exists())

    def test_guardar_ler_e_aluno_ve_as_perguntas(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        url = f'{PROF}aulas/{a1["id"]}/questionario/'
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.put(url, {'activo': True, 'nota_minima': 60, 'perguntas': perguntas()}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['nota_minima'], 60)
        self.assertEqual([p['correcta'] for p in r.data['perguntas']], [0, 1, 2])
        ids = [p['id'] for p in r.data['perguntas']]
        self.assertTrue(all(ids))
        self.assertEqual(self.client.get(url).data, r.data)
        e = self.client.get(f'{PROF}cursos/{curso.id}/estrutura/').data
        self.assertEqual(e['seccoes'][0]['aulas'][0]['questionario'], {'activo': True, 'perguntas': 3, 'nota_minima': 60})

        quiz = ChapterQuiz.objects.get(chapter_id=a1['id'])
        self.assertTrue(quiz.is_active)
        self.assertEqual(quiz.passing_score, 60)

        # Reescrever mantém os ids enviados (as tentativas dos alunos usam-nos).
        novas = r.data['perguntas'][:2]
        novas[0]['enunciado'] = 'Mudada?'
        with self.captureOnCommitCallbacks(execute=True):
            r2 = self.client.put(url, {'activo': True, 'nota_minima': 60, 'perguntas': novas}, format='json')
        self.assertEqual([p['id'] for p in r2.data['perguntas']], ids[:2])

        # O aluno inscrito vê as perguntas sem as respostas e consegue responder
        # (a aula precisa de vídeo: sem vídeo fica escondida dos alunos).
        Chapter.objects.filter(id=a1['id']).update(video='https://cdn.exemplo.ao/videos/a1.mp4')
        Course.objects.filter(id=curso.id).update(status='Published', access_level='free')
        matricular_em_curso(self.aluno, Course.objects.get(id=curso.id))
        self.entrar(self.aluno)
        q = self.client.get(f'{ALUNO}chapters/{a1["id"]}/quiz/')
        self.assertEqual(q.status_code, 200)
        self.assertEqual(q.data['data']['passing_score'], 60)
        cap = self.client.get(f'{ALUNO}chapters/{a1["id"]}/')
        self.assertEqual(cap.status_code, 200)
        qs = cap.data['quiz_data']['questions']
        self.assertEqual([x['question'] for x in qs], ['Mudada?', 'Pergunta 1?'])
        self.assertNotIn('correctOptionId', qs[0])
        self.assertNotIn('isCorrect', qs[0]['options'][0])
        respostas = {ids[0]: codigo_opcao(a1['id'], ids[0], 'a'), ids[1]: codigo_opcao(a1['id'], ids[1], 'b')}
        t = self.client.post(f'{ALUNO}chapters/{a1["id"]}/quiz/attempts/', {'respostas': respostas}, format='json')
        self.assertEqual(t.status_code, 201, t.content)
        self.assertEqual(t.data['data']['score_percentage'], 100)

    def test_desactivar(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        url = f'{PROF}aulas/{a1["id"]}/questionario/'
        with self.captureOnCommitCallbacks(execute=True):
            self.client.put(url, {'activo': True, 'nota_minima': 70, 'perguntas': perguntas()}, format='json')
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.put(url, {'activo': False, 'nota_minima': 70, 'perguntas': perguntas()}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['activo'])
        self.assertFalse(ChapterQuiz.objects.get(chapter_id=a1['id']).is_active)


class EnviosLocaisTests(Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media, USE_S3=False, ENVIOS_LOCAIS=True)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_video_ida_e_volta(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}aulas/{a1["id"]}/video/',
                             {'nome': 'Briefing de segurança.mp4', 'tamanho_bytes': len(MP4), 'tipo_mime': 'video/mp4'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data['modo'], r.data['metodo']), ('local', 'PUT'))
        self.assertTrue(r.data['upload_url'].startswith('/api/v1/teacher/envios/'))
        # Confirmar antes de enviar os bytes.
        r0 = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(r0.status_code, 400)
        self.assertEqual(r0.data['code'], 'envio_em_falta')
        put = self.client.put(r.data['upload_url'], MP4, content_type='video/mp4')
        self.assertEqual(put.status_code, 200, put.content)
        self.assertEqual(put.data['tamanho_bytes'], len(MP4))
        c = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(c.status_code, 200, c.content)
        self.assertEqual(c.data['id'], a1['id'])
        self.assertEqual(c.data['video']['nome'], 'Briefing de segurança.mp4')
        self.assertEqual(c.data['video']['tamanho_bytes'], len(MP4))
        self.assertIn('/media/videos/', c.data['video']['url'])
        self.assertTrue(c.data['video']['url'].endswith('Briefing-de-seguranca.mp4'))
        self.assertEqual(Chapter.objects.get(id=a1['id']).video, c.data['video']['url'])

    def test_material_e_capa(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}aulas/{a1["id"]}/materiais/',
                             {'nome': 'vocabulario.pdf', 'tamanho_bytes': 5, 'tipo_mime': 'application/pdf'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.client.put(r.data['upload_url'], b'%PDF-', content_type='application/pdf')
        c = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(c.status_code, 200, c.content)
        self.assertEqual((c.data['nome'], c.data['tamanho_bytes'], c.data['tipo']), ('vocabulario.pdf', 5, 'pdf'))
        # Confirmar duas vezes não duplica.
        self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(ChapterResource.objects.filter(chapter_id=a1['id']).count(), 1)
        e = self.client.get(f'{PROF}cursos/{curso.id}/estrutura/').data
        self.assertEqual(e['seccoes'][0]['aulas'][0]['materiais'][0]['id'], c.data['id'])
        self.assertEqual(self.client.delete(f'{PROF}materiais/{c.data["id"]}/').status_code, 204)
        self.assertFalse(ChapterResource.objects.filter(id=c.data['id']).exists())

        r = self.client.post(f'{PROF}cursos/{curso.id}/capa/',
                             {'nome': 'capa.png', 'tamanho_bytes': 4, 'tipo_mime': 'image/png'}, format='json')
        self.client.put(r.data['upload_url'], b'\x89PNG', content_type='image/png')
        c = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(c.status_code, 200, c.content)
        self.assertEqual(c.data['id'], str(curso.id))
        self.assertIn('/media/courses/images/', c.data['imagem'])

    def test_tipos_e_tamanhos(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        casos = [
            (f'{PROF}aulas/{a1["id"]}/video/', 'v.avi', 10, 'video/x-msvideo'),
            (f'{PROF}aulas/{a1["id"]}/video/', 'v.mp4', 2 * 1024 ** 3 + 1, 'video/mp4'),
            (f'{PROF}aulas/{a1["id"]}/materiais/', 'a.exe', 10, 'application/octet-stream'),
            (f'{PROF}aulas/{a1["id"]}/materiais/', 'a.pdf', 20 * 1024 ** 2 + 1, 'application/pdf'),
            (f'{PROF}cursos/{curso.id}/capa/', 'c.gif', 10, 'image/gif'),
            (f'{PROF}cursos/{curso.id}/capa/', 'c.png', 5 * 1024 ** 2 + 1, 'image/png'),
        ]
        for url, nome, tamanho, mime in casos:
            r = self.client.post(url, {'nome': nome, 'tamanho_bytes': tamanho, 'tipo_mime': mime}, format='json')
            self.assertEqual(r.status_code, 400, nome)
            self.assertEqual(r.data['code'], 'ficheiro_invalido')
        for url, nome, mime in [(f'{PROF}aulas/{a1["id"]}/video/', 'v.mov', 'video/quicktime'),
                                (f'{PROF}aulas/{a1["id"]}/materiais/', 'f.xlsx',
                                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                                (f'{PROF}aulas/{a1["id"]}/materiais/', 'a.m4a', 'audio/x-m4a')]:
            r = self.client.post(url, {'nome': nome, 'tamanho_bytes': 10, 'tipo_mime': mime}, format='json')
            self.assertEqual(r.status_code, 201, nome)

    def test_corpo_maior_do_que_o_indicado(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        r = self.client.post(f'{PROF}aulas/{a1["id"]}/video/',
                             {'nome': 'v.mp4', 'tamanho_bytes': 10, 'tipo_mime': 'video/mp4'}, format='json')
        put = self.client.put(r.data['upload_url'], b'x' * 5000, content_type='video/mp4')
        self.assertEqual(put.status_code, 400)

    def test_chave_adulterada(self):
        r = self.client.post(f'{PROF}envios/confirmar/', {'chave': 'abc'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'envio_invalido')


@override_settings(USE_S3=True, AWS_ACCESS_KEY_ID='k', AWS_SECRET_ACCESS_KEY='s', AWS_STORAGE_BUCKET_NAME='b',
                   AWS_S3_CUSTOM_DOMAIN='b.s3.us-east-1.amazonaws.com', AWS_CLOUDFRONT_DOMAIN='')
class EnviosS3Tests(Base):
    def test_s3_url_pre_assinado_e_confirmar(self):
        curso, s1, s2, a1, a2 = self.curso_com_aulas()
        cliente = mock.Mock()
        cliente.generate_presigned_url.return_value = 'https://b.s3.amazonaws.com/videos/x?assinatura'
        cliente.head_object.return_value = {'ContentLength': 1234}
        with mock.patch('apps.courses.api.teacher.envios._s3', return_value=cliente):
            r = self.client.post(f'{PROF}aulas/{a1["id"]}/video/',
                                 {'nome': 'aula.mp4', 'tamanho_bytes': 1234, 'tipo_mime': 'video/mp4'}, format='json')
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual((r.data['modo'], r.data['metodo']), ('s3', 'PUT'))
            self.assertEqual(r.data['cabecalhos'], {'Content-Type': 'video/mp4'})
            params = cliente.generate_presigned_url.call_args.kwargs['Params']
            self.assertTrue(params['Key'].startswith('videos/') and params['Key'].endswith('/aula.mp4'))
            c = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(c.status_code, 200, c.content)
        self.assertEqual(c.data['video']['url'], f'https://b.s3.us-east-1.amazonaws.com/{params["Key"]}')
        self.assertEqual(c.data['video']['tamanho_bytes'], 1234)


class PercentagemVistaTests(Base):
    def setUp(self):
        super().setUp()
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='C', course_type='video',
                                           status='Published', access_level='free', category='Industry English')
        sec = CourseSection.objects.create(course=self.curso, sectionTitle='S', order=1)
        self.aula = Chapter.objects.create(section=sec, title='A', content='', type='Video', order=1,
                                           video='https://x.ao/v.mp4', duracao_s=100, percentagem_vista=50)
        Chapter.objects.create(section=sec, title='B', content='', type='Video', order=2, video='https://x.ao/b.mp4')
        matricular_em_curso(self.aluno, self.curso)
        self.entrar(self.aluno)

    def enviar(self, segundos, completed=None):
        corpo = {'chapter_id': str(self.aula.id), 'watched_seconds': segundos, 'sections': []}
        if completed is not None:
            corpo['sections'] = [{'sectionId': str(self.aula.section_id),
                                  'chapters': [{'chapterId': str(self.aula.id), 'completed': completed}]}]
        return self.client.put(f'{ALUNO}users/{self.aluno.id}/progress/{self.curso.id}/update/', corpo,
                               format='json')

    def concluida(self):
        return ChapterProgress.objects.filter(chapter=self.aula, user_progress__user=self.aluno,
                                              completed=True).exists()

    def test_conta_como_vista_ao_chegar_a_percentagem(self):
        # O aluno abriu a aula há 10 minutos (o crédito não passa do tempo real desde a abertura).
        from apps.courses.tempo_video import _chave_aberta
        from django.core.cache import cache
        cache.set(_chave_aberta(self.aluno.pk, self.aula.pk), (timezone.now() - timedelta(minutes=10)).timestamp(), 3600)
        r = self.enviar(40)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.data['aula_concluida'])
        self.assertFalse(self.concluida())
        # Mais 10 s (no mesmo dia o servidor só aceita o tempo real que passou).
        from apps.courses.models import VideoWatchLog
        VideoWatchLog.objects.filter(user=self.aluno, chapter=self.aula).update(
            updated_at=timezone.now() - timedelta(minutes=5))
        r = self.enviar(10)
        self.assertTrue(r.data['aula_concluida'])
        self.assertTrue(self.concluida())
        self.assertEqual(r.data['data']['overallProgress'], 50.0)

    def test_com_80_nao_chega(self):
        Chapter.objects.filter(id=self.aula.id).update(percentagem_vista=80)
        r = self.enviar(60)
        self.assertFalse(r.data['aula_concluida'])
        self.assertFalse(self.concluida())

    def test_desmarcar_nao_e_contrariado(self):
        r = self.enviar(100, completed=False)
        self.assertFalse(r.data['aula_concluida'])
        self.assertFalse(self.concluida())

    def test_aluno_ve_duracao_e_percentagem(self):
        r = self.client.get(f'{ALUNO}chapters/{self.aula.id}/')
        self.assertEqual((r.data['duracao_s'], r.data['percentagem_vista']), (100, 50))
