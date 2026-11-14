"""Conteúdo do site: versão pública, números automáticos, rascunho/publicação, permissões, validação."""
import io
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.courses.models import Course
from apps.site import conteudo as ct
from apps.site.models import ConfiguracaoSite, Empresa, Numero, Pergunta
from apps.subscriptions.models import SubscriptionPlan
from apps.users.models import RegistoAdmin, User, UserFeedback

PUB = '/api/v1/site/'
ADM = '/api/v1/admin/site/'
SENHA = 'Segura!2026x'

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'\x00' * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def criar(email, role='student', name='Ana Maria Costa', **extra):
    u = User.objects.create_user(email=email, name=name, password=SENHA, role=role)
    for k, v in extra.items():
        setattr(u, k, v)
    u.save()
    return u


def planos():
    for tipo, nome, mensal, anual, ordem in (('FREE', 'Gratuito', 0, None, 0),
                                              ('PREMIUM', 'Premium', 14950, 149500, 1),
                                              ('PREMIUM_PLUS', 'Premium Plus', 24950, 249500, 2)):
        SubscriptionPlan.objects.update_or_create(plan_type=tipo, defaults={
            'name': nome, 'description': nome, 'monthly_price': mensal, 'yearly_price': anual,
            'sort_order': ordem, 'is_active': True, 'daily_lessons_limit': 3 if tipo == 'FREE' else 0})


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        planos()
        self.admin = criar('admin@pe.ao', role='admin', name='Admin Geral')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)
        self.anon = APIClient()

    def publicar(self):
        r = self.c.post(ADM + 'publicar/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()


class PublicoTests(Base):
    def test_forma_e_conteudo_inicial(self):
        r = self.anon.get(PUB)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(set(d), {'topo', 'numeros', 'empresas', 'servicos', 'areas', 'precos', 'testemunhos',
                                  'perguntas', 'definicoes', 'manutencao', 'publicado_em'})
        self.assertEqual(d['topo']['titulo'], 'Fale inglês no seu trabalho')
        self.assertEqual(d['topo']['etiqueta'], 'Novo: conversa com tutor de IA')
        self.assertEqual(d['topo']['botao_principal'], {'texto': 'Experimentar grátis', 'href': '/signup'})
        self.assertEqual(d['topo']['botao_secundario'], {'texto': 'Ver como funciona', 'href': '#como-funciona'})
        self.assertIsNone(d['topo']['nota'])  # menos de 5 opiniões
        self.assertEqual(d['empresas'], [])
        self.assertEqual([s['icone'] for s in d['servicos']], ['livro', 'laboratorio', 'bot', 'certificado'])
        self.assertEqual(len(d['perguntas']), 5)
        self.assertEqual(set(d['perguntas'][0]), {'id', 'pergunta', 'resposta'})
        self.assertEqual(set(d['numeros'][0]), {'id', 'valor', 'texto', 'onde'})
        self.assertIn('15 min', [n['valor'] for n in d['numeros']])
        self.assertIsNotNone(d['publicado_em'])
        self.assertEqual(d['manutencao'], {'activa': False, 'mensagem': '', 'volta_em': None})
        self.assertEqual(set(d['definicoes']), {'titulo', 'descricao', 'palavras_chave', 'ga_id', 'pixel_id',
                                                'email', 'telefone', 'instagram', 'linkedin', 'facebook'})
        self.assertIsNone(d['definicoes']['email'])
        p = d['precos']
        self.assertTrue(p['mostrar_anual'])
        self.assertEqual([x['tipo'] for x in p['planos']], ['FREE', 'PREMIUM', 'PREMIUM_PLUS'])
        prem = p['planos'][1]
        self.assertEqual(prem['preco_mensal_kz'], 14950)
        self.assertEqual(prem['preco_anual_kz'], 149500)
        self.assertEqual(prem['nota_angola'], 'Pague em kwanzas por Multicaixa Express.')
        self.assertIsNone(p['planos'][0]['preco_anual_kz'])
        self.assertIsInstance(prem['caracteristicas'], list)
        self.assertIn('Lições ilimitadas', prem['caracteristicas'])

    def test_numeros_automaticos(self):
        User.objects.bulk_create([User(email=f'a{i}@pe.ao', username=f'a{i}', name='A', role='student') for i in range(1230)])
        criar('susp@pe.ao', is_active=False)
        criar('x@apagado.invalid')
        criar('prof@pe.ao', role='teacher')
        prof = User.objects.get(email='prof@pe.ao')
        for cat in ('Industry English', 'Oil & Gas', 'Financial English', 'General English'):
            Course.objects.create(teacher=prof, teacherName='P', title=cat, description='x', course_type='video',
                                  status='Published', category=cat)
        Course.objects.create(teacher=prof, teacherName='P', title='Escondido', description='x', course_type='video',
                              status='Published', category='Medical English', visivel_catalogo=False)
        Course.objects.create(teacher=prof, teacherName='P', title='Rascunho', description='x', course_type='video',
                              status='Draft', category='Legal English')
        d = self.anon.get(PUB).json()
        por_texto = {n['texto']: n['valor'] for n in d['numeros']}
        self.assertEqual(por_texto['profissionais registados'], '1 230')
        self.assertEqual(por_texto['áreas profissionais'], '2')  # Petróleo e Gás, Banca (Geral não conta)
        self.assertEqual(d['areas'], [{'valor': 'petroleo-e-gas', 'nome': 'Petróleo e Gás', 'cursos': 2},
                                      {'valor': 'banca', 'nome': 'Banca', 'cursos': 1}])  # sem Geral

    def test_formatar_numero(self):
        self.assertEqual(ct.formatar_numero(999), '999')
        self.assertEqual(ct.formatar_numero(1234567), '1 234 567')

    def test_nota_e_testemunhos(self):
        alunos = [criar(f'al{i}@pe.ao', name=f'João Pedro Silva{i}') for i in range(5)]
        for i, a in enumerate(alunos):
            UserFeedback.objects.create(user=a, rating=4 if i else 5, comment=f'Bom {i}', allow_public=True,
                                        estado=UserFeedback.APROVADA, ordem=5 - i)
        UserFeedback.objects.create(user=alunos[0], rating=1, comment='Mau', estado=UserFeedback.POR_REVER)
        d = self.anon.get(PUB).json()
        self.assertEqual(d['topo']['nota'], {'media': 4.2, 'total': 5})
        self.assertEqual(len(d['testemunhos']), 3)
        t = d['testemunhos'][0]
        self.assertEqual(set(t), {'id', 'nome', 'area', 'texto', 'nota'})
        self.assertEqual(t['texto'], 'Bom 4')  # menor ordem primeiro
        self.assertEqual(t['nome'], 'João S.')
        # mostrar_nota desligado: nota null
        self.c.patch(ADM + 'topo/', {'mostrar_nota': False}, format='json')
        self.publicar()
        self.assertIsNone(self.anon.get(PUB).json()['topo']['nota'])

    def test_cache_e_invalidacao(self):
        self.anon.get(PUB)
        self.c.patch(ADM + 'topo/', {'titulo': 'Outro título'}, format='json')
        # O rascunho não muda o site
        self.assertEqual(self.anon.get(PUB).json()['topo']['titulo'], 'Fale inglês no seu trabalho')
        # Em cache: uma alteração directa à base de dados não se vê
        cfg = ConfiguracaoSite.obter()
        pub = cfg.publicado
        pub['topo']['texto'] = 'Mudado por fora'
        ConfiguracaoSite.objects.filter(pk=1).update(publicado=pub)
        self.assertNotEqual(self.anon.get(PUB).json()['topo']['texto'], 'Mudado por fora')
        # Publicar limpa a cache
        self.publicar()
        self.assertEqual(self.anon.get(PUB).json()['topo']['titulo'], 'Outro título')

    def test_manutencao_imediata_e_desliga_sozinha(self):
        self.anon.get(PUB)  # fica em cache
        volta = timezone.now() + timedelta(hours=1)
        r = self.c.post(ADM + 'manutencao/', {'activa': True, 'mensagem': 'Voltamos às 15h.',
                                              'volta_em': volta.isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['manutencao']['activa'])
        self.assertTrue(self.anon.get(PUB).json()['manutencao']['activa'])
        m = self.anon.get(PUB + 'manutencao/').json()
        self.assertEqual(m['mensagem'], 'Voltamos às 15h.')
        self.assertTrue(m['activa'])
        self.assertTrue(RegistoAdmin.objects.filter(accao='site_manutencao').exists())
        with mock.patch('django.utils.timezone.now', return_value=volta + timedelta(seconds=1)):
            self.assertFalse(self.anon.get(PUB + 'manutencao/').json()['activa'])
        self.assertFalse(ConfiguracaoSite.obter().manutencao_activa)
        self.assertFalse(self.anon.get(PUB).json()['manutencao']['activa'])

    def test_manutencao_validacao(self):
        r = self.c.post(ADM + 'manutencao/', {'activa': True, 'volta_em': '2020-01-01T10:00:00Z'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('volta_em', r.json()['details'])
        r = self.c.post(ADM + 'manutencao/', {'mensagem': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(r.json()['details']['activa'], list)
        r = self.c.post(ADM + 'manutencao/', {'activa': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.anon.get(PUB + 'manutencao/').json()['mensagem'], ct.MENSAGEM_MANUTENCAO)
        r = self.c.post(ADM + 'manutencao/', {'activa': False}, format='json')
        self.assertFalse(self.anon.get(PUB + 'manutencao/').json()['activa'])

    def test_rotas_antigas_cms_410(self):
        self.assertEqual(self.anon.get('/api/v1/cms/landing-page-data/').status_code, 410)


class AdminTests(Base):
    def test_permissoes(self):
        aluno = criar('al@pe.ao')
        prof = criar('pr@pe.ao', role='teacher')
        staff = criar('st@pe.ao', is_staff=True)
        for u in (aluno, prof, staff):
            c = APIClient()
            c.force_authenticate(u)
            self.assertEqual(c.get(ADM).status_code, 403, u.email)
            self.assertEqual(c.post(ADM + 'publicar/').status_code, 403)
            self.assertEqual(c.patch(ADM + 'topo/', {'titulo': 'x'}, format='json').status_code, 403)
            self.assertEqual(c.post(ADM + 'numeros/', {'texto': 'x', 'valor': '1'}, format='json').status_code, 403)
            self.assertEqual(c.post(ADM + 'manutencao/', {'activa': True}, format='json').status_code, 403)
        self.assertIn(self.anon.get(ADM).status_code, (401, 403))

    def test_estado_admin(self):
        d = self.c.get(ADM).json()
        self.assertEqual(set(d), {'rascunho', 'publicado_em', 'alterado_em', 'ha_alteracoes', 'manutencao',
                                  'contagens'})
        self.assertFalse(d['ha_alteracoes'])
        self.assertEqual(set(d['alterado_em']), set(ct.SECCOES))
        self.assertEqual(d['contagens'], {'numeros': 3, 'empresas': 0, 'servicos': 4, 'perguntas': 5,
                                          'testemunhos_no_site': 0})
        n = d['rascunho']['numeros'][0]
        self.assertEqual(set(n), {'id', 'valor', 'texto', 'onde', 'fonte', 'mostrar', 'ordem', 'valor_mostrado'})
        self.assertEqual(n['fonte'], 'utilizadores')
        self.assertIn('id', d['rascunho']['precos']['planos'][0])

    def test_publicar_e_descartar(self):
        r = self.c.patch(ADM + 'topo/', {'titulo': 'Novo título', 'etiqueta': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertTrue(d['ha_alteracoes'])
        self.assertIsNotNone(d['alterado_em']['topo'])
        self.assertIsNone(d['rascunho']['topo']['etiqueta'])
        r = self.c.post(ADM + 'perguntas/', {'pergunta': 'Há aulas ao vivo?', 'resposta': 'Não.'}, format='json')
        self.assertEqual(r.status_code, 201)
        nova_id = r.json()['id']
        self.c.delete(ADM + f'numeros/{Numero.objects.first().id}/')
        # descartar volta ao publicado
        d = self.c.post(ADM + 'descartar/').json()
        self.assertFalse(d['ha_alteracoes'])
        self.assertEqual(d['rascunho']['topo']['titulo'], 'Fale inglês no seu trabalho')
        self.assertFalse(Pergunta.objects.filter(id=nova_id).exists())
        self.assertEqual(Numero.objects.count(), 3)
        self.assertTrue(RegistoAdmin.objects.filter(accao='site_descartar').exists())
        # depois de descartar, novos itens continuam a ter ids novos
        r = self.c.post(ADM + 'perguntas/', {'pergunta': 'Outra?', 'resposta': 'Sim.'}, format='json')
        self.assertEqual(r.status_code, 201)
        # sem alterações: publicar recusa
        self.c.delete(ADM + f'perguntas/{r.json()["id"]}/')
        self.assertEqual(self.c.post(ADM + 'publicar/').status_code, 400)
        # publicar
        self.c.patch(ADM + 'topo/', {'titulo': 'Novo título'}, format='json')
        self.c.post(ADM + 'perguntas/', {'pergunta': 'Há aulas ao vivo?', 'resposta': 'Não.'}, format='json')
        d = self.publicar()
        self.assertFalse(d['ha_alteracoes'])
        reg = RegistoAdmin.objects.filter(accao='site_publicar').first()
        self.assertEqual(set(reg.detalhes['seccoes']), {'topo', 'perguntas'})
        pub = self.anon.get(PUB).json()
        self.assertEqual(pub['topo']['titulo'], 'Novo título')
        self.assertEqual(pub['perguntas'][-1]['pergunta'], 'Há aulas ao vivo?')

    def test_numeros_crud_e_ordem(self):
        r = self.c.post(ADM + 'numeros/', {'texto': 'cursos publicados', 'fonte': 'cursos', 'onde': 'sobre'},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['valor'], '')
        r = self.c.post(ADM + 'numeros/', {'texto': 'sem valor', 'fonte': 'manual'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('valor', r.json()['details'])
        r = self.c.post(ADM + 'numeros/', {'texto': 'x', 'valor': '1', 'fonte': 'inventada', 'onde': 'lado'},
                        format='json')
        self.assertEqual(set(r.json()['details']), {'fonte', 'onde'})
        ids = [n['id'] for n in self.c.get(ADM + 'numeros/').json()]
        r = self.c.post(ADM + 'numeros/ordem/', {'ids': ids[::-1]}, format='json')
        self.assertEqual([n['id'] for n in r.json()], ids[::-1])
        self.assertEqual(self.c.post(ADM + 'numeros/ordem/', {'ids': ids[:2]}, format='json').status_code, 400)
        r = self.c.patch(ADM + f'numeros/{ids[0]}/', {'mostrar': False}, format='json')
        self.assertFalse(r.json()['mostrar'])
        self.assertEqual(self.c.patch(ADM + 'numeros/99999/', {'mostrar': False}, format='json').status_code, 404)
        self.publicar()
        pub = self.anon.get(PUB).json()
        self.assertNotIn(ids[0], [n['id'] for n in pub['numeros']])
        self.assertEqual(pub['numeros'][0]['id'], ids[-1])

    def test_servicos_e_empresas_validacao(self):
        r = self.c.post(ADM + 'servicos/', {'titulo': 'X', 'texto': 'Y', 'icone': 'foguete',
                                            'leva_a': 'javascript:alert(1)'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['details']), {'icone', 'leva_a'})
        r = self.c.post(ADM + 'servicos/', {'titulo': 'X', 'texto': 'Y', 'icone': 'microfone', 'leva_a': '/planos'},
                        format='json')
        self.assertEqual(r.status_code, 201)
        r = self.c.post(ADM + 'empresas/', {'nome': '', 'area': 'Banca'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.post(ADM + 'empresas/', {'nome': 'Empresa A', 'area': 'Banca', 'no_topo': True}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['logo_url'], None)

    def test_validacao_topo_e_definicoes(self):
        r = self.c.patch(ADM + 'topo/', {'titulo': 'x' * 81, 'botao_principal': {'texto': 'Ir', 'href': '//mal.com'}},
                         format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['details']), {'titulo', 'botao_principal'})
        r = self.c.patch(ADM + 'topo/', {'botao_secundario': None}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['rascunho']['topo']['botao_secundario'])
        r = self.c.patch(ADM + 'definicoes/', {
            'titulo': 'x' * 71, 'descricao': 'y' * 161, 'ga_id': 'UA-123', 'pixel_id': 'abc', 'email': 'nao',
            'telefone': 'abc', 'instagram': 'http://instagram.com/x', 'facebook': 'https://mal.com/x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['details']), {'titulo', 'descricao', 'ga_id', 'pixel_id', 'email', 'telefone',
                                                    'instagram', 'facebook'})
        self.assertEqual(r.json()['code'], 'validation_error')
        r = self.c.patch(ADM + 'definicoes/', {
            'ga_id': 'g-ab12cd34', 'pixel_id': '123456789', 'email': 'Ola@ProEnglish.ao', 'telefone': '+244 923 000 000',
            'instagram': 'https://www.instagram.com/proenglish', 'linkedin': None}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        dd = r.json()['rascunho']['definicoes']
        self.assertEqual(dd['ga_id'], 'G-AB12CD34')
        self.assertEqual(dd['email'], 'ola@proenglish.ao')
        self.assertIsNone(dd['linkedin'])
        self.assertTrue(r.json()['ha_alteracoes'])

    def test_precos(self):
        r = self.c.patch(ADM + 'precos/', {'mostrar_anual': False, 'planos': [
            {'tipo': 'PREMIUM', 'subtitulo': 'Para todos os dias', 'etiqueta': 'Mais escolhido', 'botao': 'Quero',
             'nota_angola': None}]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self.c.patch(ADM + 'precos/', {'planos': [{'tipo': 'OURO', 'botao': 'x'},
                                                      {'tipo': 'FREE', 'botao': ''}]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['details']), {'planos', 'planos.FREE.botao'})
        self.publicar()
        p = self.anon.get(PUB).json()['precos']
        self.assertFalse(p['mostrar_anual'])
        prem = [x for x in p['planos'] if x['tipo'] == 'PREMIUM'][0]
        self.assertEqual((prem['subtitulo'], prem['etiqueta'], prem['botao'], prem['nota_angola']),
                         ('Para todos os dias', 'Mais escolhido', 'Quero', None))
        # Preço vivo: muda o plano, o site acompanha (depois da cache)
        SubscriptionPlan.objects.filter(plan_type='PREMIUM').update(monthly_price=15000)
        cache.clear()
        prem = [x for x in self.anon.get(PUB).json()['precos']['planos'] if x['tipo'] == 'PREMIUM'][0]
        self.assertEqual(prem['preco_mensal_kz'], 15000)
        # Plano inactivo não aparece
        SubscriptionPlan.objects.filter(plan_type='PREMIUM_PLUS').update(is_active=False)
        cache.clear()
        self.assertNotIn('PREMIUM_PLUS', [x['tipo'] for x in self.anon.get(PUB).json()['precos']['planos']])


class LogoTests(Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.empresa = Empresa.objects.create(nome='Empresa A', ordem=1)

    def enviar(self, conteudo, nome='logo.png', tipo='image/png'):
        f = SimpleUploadedFile(nome, conteudo, content_type=tipo)
        return self.c.post(ADM + f'empresas/{self.empresa.id}/logo/', {'logo': f}, format='multipart')

    def test_tipos_e_tamanho(self):
        with override_settings(MEDIA_ROOT=self.media, USE_S3=False, ENVIOS_LOCAIS=True):
            r = self.enviar(SVG, 'logo.svg', 'image/svg+xml')
            self.assertEqual(r.status_code, 400)
            self.assertIn('logo', r.json()['details'])
            r = self.enviar(b'GIF89a' + b'\x00' * 20, 'logo.png')  # extensão mentirosa
            self.assertEqual(r.status_code, 400)
            r = self.enviar(PNG + b'\x00' * (1024 * 1024), 'grande.png')
            self.assertEqual(r.status_code, 400)
            self.assertIn('1 MB', r.json()['message'])
            r = self.enviar(PNG)
            self.assertEqual(r.status_code, 200, r.content)
            url1 = r.json()['logo_url']
            self.assertIn('/media/site/empresas/', url1)
            self.assertTrue(url1.endswith('.png'))
            with self.captureOnCommitCallbacks(execute=True):
                r = self.enviar(WEBP, 'logo.webp', 'image/webp')
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()['logo_url'].endswith('.webp'))
            import os
            ficheiros = os.listdir(os.path.join(self.media, 'site', 'empresas'))
            self.assertEqual(len(ficheiros), 1)  # o primeiro (não publicado) foi apagado
            self.assertTrue(ficheiros[0].endswith('.webp'))

    def test_sem_armazenamento(self):
        with override_settings(MEDIA_ROOT=self.media, USE_S3=False, ENVIOS_LOCAIS=False):
            self.assertEqual(self.enviar(PNG).status_code, 503)

    def test_s3(self):
        cliente = mock.MagicMock()
        with override_settings(USE_S3=True, AWS_STORAGE_BUCKET_NAME='bucket', AWS_CLOUDFRONT_DOMAIN='cdn.pe.ao'), \
                mock.patch('apps.courses.api.teacher.envios._s3', return_value=cliente):
            r = self.enviar(PNG)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['logo_url'].startswith('https://cdn.pe.ao/site/empresas/'))
        kwargs = cliente.put_object.call_args.kwargs
        self.assertEqual(kwargs['ContentType'], 'image/png')
        self.assertTrue(kwargs['Key'].startswith('site/empresas/'))
