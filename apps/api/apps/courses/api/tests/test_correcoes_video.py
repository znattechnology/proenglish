"""
Correcções do lado do professor nos cursos em vídeo: rotas antigas retiradas, apagar só rascunhos,
acesso no detalhe, revisão de um curso arquivado, aulas escondidas até terem vídeo, avisos,
ficheiros apagados e chaves de envio de uso único, protecção de cursos publicados e aprovação.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_correcoes_video
"""
import os
import shutil
import tempfile
from unittest import mock

from django.db.models.deletion import ProtectedError
from django.test import override_settings

from apps.courses import ciclo
from apps.courses.certificados import progresso_actual
from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterResource, Course, CourseCertificate, CourseSection, UserCourseProgress,
)
from apps.users.models import Notification

from .test_editor_video import ALUNO, MP4, PROF, Base

VIDEO = 'https://cdn.exemplo.ao/videos/abc/aula.mp4'


def perguntas(n):
    return [{'enunciado': f'Pergunta {i}?', 'opcoes': ['a', 'b'], 'correcta': 0} for i in range(n)]


class CursoCompleto(Base):
    def curso_completo(self, status=ciclo.PUBLICADO, aulas=1):
        curso = Course.objects.create(
            teacher=self.prof, teacherName='Prof', title='Inglês na Plataforma', category='Industry English',
            level='B1', image='https://cdn.exemplo.ao/courses/images/capa.png', course_type='video',
            status=status, access_level='free')
        seccao = CourseSection.objects.create(course=curso, sectionTitle='Chegada', order=1)
        for i in range(aulas):
            Chapter.objects.create(section=seccao, title=f'Aula {i + 1}', content='', type='Video',
                                   order=i + 1, video=f'https://cdn.exemplo.ao/videos/{i}/aula.mp4')
        return curso, seccao


class RotasAntigasTests(CursoCompleto):
    def test_apagar_so_rascunho_sem_alunos(self):
        publicado, _ = self.curso_completo()
        for url in (f'/api/v1/teacher/video-courses/{publicado.id}/', f'/api/v1/courses/{publicado.id}/'):
            r = self.client.delete(url)
            self.assertEqual(r.status_code, 409, url)
            self.assertEqual(r.json()['code'], 'curso_nao_apagavel')
        self.assertTrue(Course.objects.filter(id=publicado.id).exists())

        rascunho, _ = self.curso_completo(status=ciclo.RASCUNHO)
        matricular_em_curso(self.aluno, rascunho)
        self.assertEqual(self.client.delete(f'/api/v1/courses/{rascunho.id}/').status_code, 409)
        rascunho.enrollments.all().delete()
        r = self.client.delete(f'/api/v1/teacher/video-courses/{rascunho.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(Course.objects.filter(id=rascunho.id).exists())

        # Outro professor não apaga (403/404), mesmo um rascunho.
        alheio, _ = self.curso_completo(status=ciclo.RASCUNHO)
        self.entrar(self.outro)
        self.assertIn(self.client.delete(f'/api/v1/courses/{alheio.id}/').status_code, (403, 404))
        self.assertTrue(Course.objects.filter(id=alheio.id).exists())

    def test_certificado_protege_o_curso(self):
        curso, _ = self.curso_completo()
        CourseCertificate.objects.create(user=self.aluno, course=curso, certificate_number='PE-C-2026-999999')
        with self.assertRaises(ProtectedError):
            curso.delete()

    def test_envios_e_escritas_antigas_respondem_410(self):
        curso, seccao = self.curso_completo(status=ciclo.RASCUNHO)
        aula = seccao.chapters.first()
        for base in ('/api/v1/courses/', '/api/v1/teacher/video-courses/'):
            pedidos = [
                ('post', f'{base}{curso.id}/sections/{seccao.id}/chapters/{aula.id}/get-upload-url/',
                 {'fileName': 'x.html', 'fileType': 'text/html'}),
                ('post', f'{base}{curso.id}/sections/{seccao.id}/chapters/{aula.id}/get-resource-upload-url/',
                 {'fileName': 'x.html', 'fileType': 'text/html'}),
                ('post', f'{base}{curso.id}/get-image-upload-url/', {'fileName': 'x.png', 'fileType': 'image/png'}),
                ('put', f'{base}{curso.id}/update-image-url/', {'imageUrl': 'https://mal.example/x.png'}),
                ('post', f'{base}{curso.id}/upload-image/', {}),
                ('put', f'{base}{curso.id}/', {'title': 'Outro'}),
                ('patch', f'{base}{curso.id}/', {'title': 'Outro'}),
                ('post', f'{base}{curso.id}/sections/', {'sectionTitle': 'S'}),
                ('put', f'{base}sections/{seccao.id}/', {'sectionTitle': 'S'}),
                ('delete', f'{base}sections/{seccao.id}/', None),
                ('post', f'{base}sections/{seccao.id}/chapters/', {'title': 'C', 'type': 'Video'}),
                ('put', f'{base}chapters/{aula.id}/', {'title': 'C', 'quiz_data': {'questions': []}}),
                ('patch', f'{base}chapters/{aula.id}/', {'video': 'https://mal.example/v.mp4'}),
                ('delete', f'{base}chapters/{aula.id}/', None),
            ]
            for metodo, url, corpo in pedidos:
                r = getattr(self.client, metodo)(url, corpo, format='json')
                self.assertEqual(r.status_code, 410, f'{metodo} {url}: {r.status_code}')
                self.assertEqual(r.json()['code'], 'rota_removida')
        aula.refresh_from_db()
        self.assertEqual((aula.title, aula.video), ('Aula 1', 'https://cdn.exemplo.ao/videos/0/aula.mp4'))
        # As leituras continuam.
        self.assertEqual(self.client.get(f'/api/v1/teacher/video-courses/{curso.id}/').status_code, 200)

    def test_lista_publica_antiga_so_mostra_o_catalogo(self):
        visivel, _ = self.curso_completo()
        escondido, _ = self.curso_completo()
        Course.objects.filter(id=escondido.id).update(visivel_catalogo=False)
        self.client.credentials()
        r = self.client.get('/api/v1/courses/?page_size=100')
        ids = {c.get('courseId') or c.get('id') for c in r.json()['data']['results']}
        self.assertIn(str(visivel.id), ids)
        self.assertNotIn(str(escondido.id), ids)


class DetalheEOpcoesTests(CursoCompleto):
    def test_acesso_no_detalhe(self):
        curso, _ = self.curso_completo(status=ciclo.RASCUNHO)
        r = self.client.get(f'{PROF}cursos/{curso.id}/')
        self.assertEqual(r.data['acesso'], 'todos')
        r = self.client.patch(f'{PROF}cursos/{curso.id}/', {'acesso': 'premium'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['acesso'], 'premium')

    def test_opcoes_por_tipo_com_valores_antigos(self):
        video = self.client.get(f'{PROF}cursos/opcoes/?tipo=video').data['areas']
        pratica = self.client.get(f'{PROF}cursos/opcoes/?tipo=pratica').data['areas']
        valores_video = {a['valor'] for a in video}
        self.assertTrue({'Technology English', 'Inglês Geral', 'Industry English'} <= valores_video)
        self.assertNotIn('Oil & Gas', valores_video)
        self.assertIn('Oil & Gas', {a['valor'] for a in pratica})
        self.assertNotIn('Industry English', {a['valor'] for a in pratica})
        self.assertEqual(len(valores_video), len(video))

    def test_aulas_publicadas_nos_numeros(self):
        self.curso_completo(aulas=2)
        _, seccao = self.curso_completo(status=ciclo.RASCUNHO, aulas=3)
        Chapter.objects.create(section=seccao, title='Sem vídeo', content='', type='Video', order=9)
        numeros = self.client.get(f'{PROF}cursos/?tipo=video').data['numeros']
        self.assertEqual((numeros['aulas'], numeros['aulas_total']), (2, 6))


class RevisaoDeArquivadoTests(CursoCompleto):
    def test_arquivado_a_manter_volta_a_arquivado_e_alunos_mantem_acesso(self):
        curso, seccao = self.curso_completo()
        aula = seccao.chapters.first()
        matricular_em_curso(self.aluno, curso)
        self.assertEqual(self.client.post(f'{PROF}cursos/{curso.id}/arquivar/', {'modo': 'manter'},
                                          format='json').status_code, 200)

        def aluno_ve():
            self.entrar(self.aluno)
            r = self.client.get(f'{ALUNO}chapters/{aula.id}/')
            self.entrar(self.prof)
            return r.status_code == 200

        self.assertTrue(aluno_ve())
        r = self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['curso']['estado'], r.data['curso']['estado_antes_revisao']),
                         ('em_revisao', 'arquivado'))
        self.assertTrue(aluno_ve())  # em revisão, os inscritos continuam

        r = self.client.post(f'{PROF}cursos/{curso.id}/cancelar-revisao/')
        self.assertEqual(r.data['curso']['estado'], 'arquivado')
        self.assertEqual(r.data['curso']['modo_arquivo'], 'manter')
        self.assertTrue(aluno_ve())

        self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.entrar(self.admin)
        r = self.client.post(f'/api/v1/admin/cursos/{curso.id}/recusar/', {'motivo': 'Falta rever o áudio.'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        curso.refresh_from_db()
        self.assertEqual((curso.status, curso.modo_arquivo), (ciclo.ARQUIVADO, ciclo.MANTER))
        self.entrar(self.prof)
        self.assertTrue(aluno_ve())

        self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        self.entrar(self.admin)
        self.assertEqual(self.client.post(f'/api/v1/admin/cursos/{curso.id}/aprovar/').status_code, 200)
        curso.refresh_from_db()
        self.assertEqual((curso.status, curso.estado_antes_revisao), (ciclo.PUBLICADO, ''))

    def test_rascunho_volta_a_rascunho(self):
        curso, _ = self.curso_completo(status=ciclo.RASCUNHO)
        self.client.post(f'{PROF}cursos/{curso.id}/submeter/')
        r = self.client.post(f'{PROF}cursos/{curso.id}/cancelar-revisao/')
        self.assertEqual(r.data['curso']['estado'], 'rascunho')

    def test_aprovar_recusa_curso_que_ja_nao_cumpre(self):
        curso, _ = self.curso_completo(status=ciclo.RASCUNHO)
        self.assertEqual(self.client.post(f'{PROF}cursos/{curso.id}/submeter/').status_code, 200)
        Course.objects.filter(id=curso.id).update(image='')
        self.entrar(self.admin)
        r = self.client.post(f'/api/v1/admin/cursos/{curso.id}/aprovar/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'verificacao_incompleta')
        self.assertFalse(r.data['pode_submeter'])
        curso.refresh_from_db()
        self.assertEqual(curso.status, ciclo.EM_REVISAO)


class CursoPublicadoTests(CursoCompleto):
    def test_alteracoes_que_quebram_o_curso_dao_409(self):
        curso, seccao = self.curso_completo()
        aula = seccao.chapters.first()
        casos = [
            ('delete', f'{PROF}aulas/{aula.id}/', None),
            ('delete', f'{PROF}seccoes/{seccao.id}/', None),
            ('put', f'{PROF}aulas/{aula.id}/questionario/', {'activo': True, 'perguntas': perguntas(2)}),
            ('patch', f'{PROF}cursos/{curso.id}/', {'imagem': ''}),
        ]
        for metodo, url, corpo in casos:
            r = getattr(self.client, metodo)(url, corpo, format='json')
            self.assertEqual(r.status_code, 409, f'{metodo} {url}: {r.content}')
            self.assertEqual(r.data['code'], 'quebra_curso')
            self.assertTrue(r.data['details']['itens'])
        self.assertTrue(Chapter.objects.filter(id=aula.id).exists())
        aula.refresh_from_db()
        self.assertFalse(aula.quiz_enabled)
        curso.refresh_from_db()
        self.assertTrue(curso.image)

        # O que não quebra continua a funcionar: questionário com 3 perguntas, aula nova sem vídeo
        # (fica escondida) e apagá-la outra vez.
        r = self.client.put(f'{PROF}aulas/{aula.id}/questionario/', {'activo': True, 'perguntas': perguntas(3)},
                            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        nova = self.client.post(f'{PROF}seccoes/{seccao.id}/aulas/', {'titulo': 'Nova'}, format='json')
        self.assertEqual(nova.status_code, 201)
        self.assertEqual(self.client.delete(f'{PROF}aulas/{nova.data["id"]}/').status_code, 204)

    def test_rascunho_nao_tem_guarda(self):
        curso, seccao = self.curso_completo(status=ciclo.RASCUNHO)
        self.assertEqual(self.client.delete(f'{PROF}seccoes/{seccao.id}/').status_code, 204)


class AulasEscondidasTests(CursoCompleto):
    def test_aula_sem_video_nao_aparece_nem_conta(self):
        curso, seccao = self.curso_completo()
        vista = seccao.chapters.first()
        matricular_em_curso(self.aluno, curso)
        nova = self.client.post(f'{PROF}seccoes/{seccao.id}/aulas/', {'titulo': 'Por gravar'}, format='json').data

        self.entrar(self.aluno)
        r = self.client.get(f'{ALUNO}{curso.id}/')
        self.assertEqual(r.data['data']['total_chapters'], 1)
        capitulos = [str(c['chapterId']) for s in r.data['data']['sections'] for c in s['chapters']]
        self.assertEqual(capitulos, [str(vista.id)])
        r = self.client.get(f'{ALUNO}sections/{seccao.id}/chapters/')
        dados = r.data.get('results', r.data) if isinstance(r.data, dict) else r.data
        self.assertEqual(len(dados), 1)
        self.assertEqual(self.client.get(f'{ALUNO}chapters/{nova["id"]}/').status_code, 404)

        progresso = UserCourseProgress.objects.get(user=self.aluno, course=curso)
        ChapterProgress.objects.update_or_create(user_progress=progresso, chapter=vista,
                                                 defaults={'completed': True})
        self.assertEqual(progresso_actual(self.aluno, curso), 100.0)
        r = self.client.get(f'{ALUNO}users/{self.aluno.id}/progress/{curso.id}/')
        self.assertEqual(r.data['data']['overallProgress'], 100.0)
        self.assertEqual([len(s['chapters']) for s in r.data['data']['sections']], [1])

        # Com vídeo, a aula aparece e passa a contar.
        Chapter.objects.filter(id=nova['id']).update(video=VIDEO)
        self.assertEqual(progresso_actual(self.aluno, curso), 50.0)


@override_settings(USE_S3=False, ENVIOS_LOCAIS=True)
class EnviosTests(CursoCompleto):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def enviar_video(self, aula_id, nome='aula.mp4'):
        r = self.client.post(f'{PROF}aulas/{aula_id}/video/',
                             {'nome': nome, 'tamanho_bytes': len(MP4), 'tipo_mime': 'video/mp4'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.put(r.data['upload_url'], MP4, content_type='video/mp4').status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            c = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json')
        self.assertEqual(c.status_code, 200, c.content)
        return r.data, c.data

    def caminho(self, url):
        return os.path.join(self.media, url.split('/media/', 1)[1])

    def test_chave_de_uso_unico_e_ficheiro_substituido_apagado(self):
        curso, seccao = self.curso_completo(status=ciclo.RASCUNHO)
        aula = Chapter.objects.create(section=seccao, title='Nova', content='', type='Video', order=5, duracao_s=300)
        pedido, primeiro = self.enviar_video(aula.id)
        self.assertIsNone(Chapter.objects.get(id=aula.id).duracao_s)
        antigo = self.caminho(primeiro['video']['url'])
        self.assertTrue(os.path.exists(antigo))
        # A mesma chave já não serve: nem para reenviar os bytes nem para confirmar outra vez.
        r = self.client.put(pedido['upload_url'], b'outro conteudo', content_type='video/mp4')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'envio_ja_confirmado')
        r = self.client.post(f'{PROF}envios/confirmar/', {'chave': pedido['chave']}, format='json')
        self.assertEqual(r.status_code, 409)

        # Trocar o vídeo apaga o ficheiro anterior e repõe a duração.
        Chapter.objects.filter(id=aula.id).update(duracao_s=120)
        _, segundo = self.enviar_video(aula.id, 'aula-v2.mp4')
        self.assertFalse(os.path.exists(antigo))
        self.assertIsNone(Chapter.objects.get(id=aula.id).duracao_s)

        # Apagar a aula apaga o vídeo e os materiais.
        r = self.client.post(f'{PROF}aulas/{aula.id}/materiais/',
                             {'nome': 'lista.csv', 'tamanho_bytes': 3, 'tipo_mime': 'application/vnd.ms-excel'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['cabecalhos']['Content-Type'], 'text/csv')
        self.client.put(r.data['upload_url'], b'a,b', content_type='text/csv')
        with self.captureOnCommitCallbacks(execute=True):
            m = self.client.post(f'{PROF}envios/confirmar/', {'chave': r.data['chave']}, format='json').data
        material = self.caminho(m['url'])
        video = self.caminho(segundo['video']['url'])
        self.assertTrue(os.path.exists(material) and os.path.exists(video))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(f'{PROF}aulas/{aula.id}/').status_code, 204)
        self.assertFalse(os.path.exists(material) or os.path.exists(video))

    def test_aviso_so_quando_o_video_e_confirmado_pela_primeira_vez(self):
        curso, seccao = self.curso_completo()
        matricular_em_curso(self.aluno, curso)
        with self.captureOnCommitCallbacks(execute=True):
            nova = self.client.post(f'{PROF}seccoes/{seccao.id}/aulas/', {'titulo': 'Nova'}, format='json').data
        self.assertFalse(Notification.objects.filter(user=self.aluno).exists())
        self.enviar_video(nova['id'])
        self.assertEqual(Notification.objects.filter(user=self.aluno).count(), 1)
        self.enviar_video(nova['id'], 'outra.mp4')
        self.assertEqual(Notification.objects.filter(user=self.aluno).count(), 1)

    @override_settings(ENVIOS_LOCAIS=False)
    def test_modo_local_fora_de_desenvolvimento(self):
        curso, seccao = self.curso_completo(status=ciclo.RASCUNHO)
        aula = seccao.chapters.first()
        r = self.client.post(f'{PROF}aulas/{aula.id}/video/',
                             {'nome': 'v.mp4', 'tamanho_bytes': 10, 'tipo_mime': 'video/mp4'}, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.data['code'], 'armazenamento_indisponivel')


@override_settings(USE_S3=True, AWS_ACCESS_KEY_ID='k', AWS_SECRET_ACCESS_KEY='s', AWS_STORAGE_BUCKET_NAME='b',
                   AWS_S3_CUSTOM_DOMAIN='b.s3.us-east-1.amazonaws.com', AWS_CLOUDFRONT_DOMAIN='')
class ApagarNoS3Tests(CursoCompleto):
    def test_apagar_material_e_seccao_apaga_objectos(self):
        curso, seccao = self.curso_completo(status=ciclo.RASCUNHO)
        aula = seccao.chapters.first()
        Chapter.objects.filter(id=aula.id).update(video='https://b.s3.us-east-1.amazonaws.com/videos/x/aula.mp4')
        m = ChapterResource.objects.create(
            chapter=aula, title='m', resource_type='PDF', created_by=self.prof,
            external_url='https://b.s3.us-east-1.amazonaws.com/chapter_resources/documents/y/m.pdf')
        cliente = mock.Mock()
        with mock.patch('apps.courses.api.teacher.envios._s3', return_value=cliente):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.delete(f'{PROF}materiais/{m.id}/').status_code, 204)
            cliente.delete_object.assert_called_once_with(Bucket='b', Key='chapter_resources/documents/y/m.pdf')
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.delete(f'{PROF}seccoes/{seccao.id}/').status_code, 204)
            cliente.delete_object.assert_called_with(Bucket='b', Key='videos/x/aula.mp4')
            # Falhas do S3 não partem o pedido.
            cliente.delete_object.side_effect = RuntimeError('rede')
            outra = CourseSection.objects.create(course=curso, sectionTitle='S2', order=2)
            Chapter.objects.create(section=outra, title='A', content='', type='Video', order=1,
                                   video='https://b.s3.us-east-1.amazonaws.com/videos/z/a.mp4')
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.delete(f'{PROF}seccoes/{outra.id}/').status_code, 204)
