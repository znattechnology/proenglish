"""
Imagens nas opções dos exercícios do laboratório (pratica_formato e carregar_unidades).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.courses.api.tests.test_imagens_exercicios --settings=core.test_settings
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.courses import carregar_unidades as cu
from apps.courses.api.teacher import pratica_formato as formato
from apps.courses.models import Course
from apps.practice.models import PracticeChallenge, PracticeLesson, PracticeUnit

URL = 'https://media.proenglish.ao/conteudo/imagens/receipt.webp'


def _escolher(imagem=URL, tipo='escolher'):
    return {'tipo': tipo, 'enunciado': 'Escolha a imagem: a receipt',
            'opcoes': [{'texto': 'a receipt', 'certa': True, 'imagem': imagem},
                       {'texto': 'a key', 'certa': False}]}


class FormatoImagensTests(TestCase):
    def test_escolher_guarda_a_imagem_e_volta_igual(self):
        limpo, erros = formato.validar(_escolher())
        self.assertEqual(erros, {})
        self.assertEqual([o['imagem'] for o in limpo['opcoes']], [URL, None])
        prof = get_user_model().objects.create_user(email='p-img@exemplo.ao', name='p', password='x', role='teacher')
        curso = Course.objects.create(teacher=prof, teacherName='P', title='Lab', description='-', category='General',
                                      level='A1', course_type='practice', access_level='free')
        licao = PracticeLesson.objects.create(unit=PracticeUnit.objects.create(course=curso, title='U', description='', order=1),
                                              title='1A', order=1)
        ch = formato.guardar(PracticeChallenge(lesson=licao, order=1), limpo)
        self.assertEqual(ch.options.order_by('order').first().image_url, URL)
        volta, erros = formato.validar(formato.para_normalizado(ch))
        self.assertEqual(erros, {})
        self.assertEqual([(o['texto'], o['imagem']) for o in volta['opcoes']], [('a receipt', URL), ('a key', None)])

    def test_so_https(self):
        for mau in ('http://x.ao/a.webp', 'javascript:alert(1)', 'nao-e-url', 'https://' + 'a' * 300 + '.ao/x.webp'):
            _, erros = formato.validar(_escolher(mau))
            self.assertIn('opcoes', erros, mau)

    def test_tipos_sem_imagem_ignoram_a_imagem(self):
        limpo, erros = formato.validar({'tipo': 'completar', 'enunciado': 'Complete', 'frase': 'I [am] here.',
                                        'opcoes': [{'texto': 'is', 'certa': False, 'imagem': URL}]})
        self.assertEqual(erros, {})
        self.assertTrue(all(o['imagem'] is None for o in limpo['opcoes']))


@override_settings(AWS_CLOUDFRONT_DOMAIN='', AWS_S3_CUSTOM_DOMAIN='media.proenglish.ao')
class CarregarImagensTests(TestCase):
    def test_nome_do_banco_vira_endereco_publico(self):
        ex = cu._endereco_das_imagens(_escolher('receipt'), 'teste')
        self.assertEqual(ex['opcoes'][0]['imagem'], URL)
        self.assertNotIn('imagem', ex['opcoes'][1])

    def test_endereco_https_fica_e_nome_invalido_e_erro(self):
        self.assertEqual(cu._endereco_das_imagens(_escolher(URL), 't')['opcoes'][0]['imagem'], URL)
        for mau in ('../segredo', 'Recibo Grande', 'a/b'):
            with self.assertRaises(cu.ErroDeConteudo):
                cu._endereco_das_imagens(_escolher(mau), 't')
