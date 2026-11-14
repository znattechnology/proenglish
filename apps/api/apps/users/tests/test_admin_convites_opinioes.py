"""Convites de professor (fluxo completo) e opiniões/testemunhos na administração."""
import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.users.models import ConviteProfessor, PerfilProfessor, RegistoAdmin, User, UserFeedback

BASE = '/api/v1/admin/'
SENHA = 'Segura!2026x'


def criar(email, role='student', name='Ana Maria Costa', **extra):
    u = User.objects.create_user(email=email, name=name, password=SENHA, role=role)
    u.email_verified = True
    for k, v in extra.items():
        setattr(u, k, v)
    u.save()
    return u


class ConvitesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = criar('admin@pe.ao', role='admin', name='Admin Geral')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def convidar(self, email='novo.prof@pe.ao', **extra):
        mail.outbox.clear()
        dados = {'email': email, 'nome': 'Paulo Neto', 'area': 'Petróleo e Gás', 'publica_sem_revisao': True}
        dados.update(extra)
        r = self.c.post(BASE + 'convites/', dados, format='json')
        token = None
        if mail.outbox:
            token = re.search(r'/convite/([A-Za-z0-9_-]+)', mail.outbox[-1].body).group(1)
        return r, token

    def test_fluxo_completo(self):
        r, token = self.convidar()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['estado'], 'pendente')
        self.assertNotIn('token', r.json())
        self.assertIn('http', mail.outbox[-1].body)
        lista = self.c.get(BASE + 'convites/').json()
        self.assertEqual(set(lista[0]) >= {'id', 'email', 'nome', 'area', 'publica_sem_revisao', 'estado',
                                           'enviado_em', 'expira_em'}, True)
        self.assertEqual(self.c.get(BASE + 'painel/').json()['numeros']['professores_por_activar'], 1)

        anon = APIClient()
        r = anon.get(f'/api/v1/convites/{token}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'nome': 'Paulo Neto', 'email': 'novo.prof@pe.ao', 'area': 'Petróleo e Gás',
                                    'valido': True, 'estado': 'pendente'})
        r = anon.post(f'/api/v1/convites/{token}/aceitar/', {'nome': 'Paulo Neto', 'password': '123'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIsInstance(r.json()['details']['password'], list)

        r = anon.post(f'/api/v1/convites/{token}/aceitar/', {'nome': 'Paulo J. Neto', 'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['user']['role'], 'teacher')
        self.assertIn('access_token', r.cookies)
        self.assertIn('refresh_token', r.cookies)
        self.assertTrue(r.cookies['access_token']['httponly'])
        user = User.objects.get(email='novo.prof@pe.ao')
        self.assertEqual((user.role, user.email_verified, user.name), ('teacher', True, 'Paulo J. Neto'))
        self.assertTrue(PerfilProfessor.objects.get(user=user).publica_sem_revisao)
        # Os cookies dão sessão
        self.assertEqual(anon.get('/api/v1/users/profile/').json()['email'], 'novo.prof@pe.ao')

        # Já usado
        r = APIClient().post(f'/api/v1/convites/{token}/aceitar/', {'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.json()['code'], 'convite_aceite')
        self.assertFalse(APIClient().get(f'/api/v1/convites/{token}/').json()['valido'])
        self.assertEqual(self.c.get(BASE + 'convites/').json()[0]['estado'], 'aceite')

    def test_expirado_cancelado_reenviado(self):
        r, token = self.convidar()
        cid = r.json()['id']
        ConviteProfessor.objects.filter(pk=cid).update(expira_em=timezone.now() - timedelta(minutes=1))
        r = APIClient().get(f'/api/v1/convites/{token}/')
        self.assertEqual((r.json()['valido'], r.json()['estado']), (False, 'expirado'))
        r = APIClient().post(f'/api/v1/convites/{token}/aceitar/', {'password': SENHA}, format='json')
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.json()['code'], 'convite_expirado')

        mail.outbox.clear()
        r = self.c.post(BASE + f'convites/{cid}/reenviar/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['estado'], 'pendente')
        novo = re.search(r'/convite/([A-Za-z0-9_-]+)', mail.outbox[-1].body).group(1)
        self.assertNotEqual(novo, token)
        self.assertEqual(APIClient().get(f'/api/v1/convites/{token}/').status_code, 404)
        self.assertTrue(APIClient().get(f'/api/v1/convites/{novo}/').json()['valido'])

        r = self.c.delete(BASE + f'convites/{cid}/')
        self.assertEqual(r.json()['estado'], 'cancelado')
        r = APIClient().post(f'/api/v1/convites/{novo}/aceitar/', {'password': SENHA}, format='json')
        self.assertEqual(r.json()['code'], 'convite_cancelado')
        accoes = list(RegistoAdmin.objects.filter(alvo_tipo='convite').order_by('criado_em')
                      .values_list('accao', flat=True))
        self.assertEqual(accoes, ['convite_criar', 'convite_reenviar', 'convite_cancelar'])

    def test_email_ja_existe_e_validacao(self):
        criar('existe@pe.ao')
        r, _ = self.convidar('Existe@pe.ao')
        self.assertEqual(r.status_code, 409)
        r, _ = self.convidar('não-é-email')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['details']['email'], ['Escreva um email válido.'])
        self.assertEqual(APIClient().get('/api/v1/convites/inexistente/').status_code, 404)

    def test_so_administradores(self):
        prof = criar('p@pe.ao', role='teacher')
        c = APIClient()
        c.force_authenticate(prof)
        self.assertEqual(c.post(BASE + 'convites/', {'email': 'x@pe.ao', 'nome': 'X Y'}, format='json').status_code, 403)


class OpinioesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = criar('admin@pe.ao', role='admin')
        self.c = APIClient()
        self.c.force_authenticate(self.admin)
        self.aluno = criar('al@pe.ao', name='Tomás Kiala', preferences={'area': 'Industry English'})
        self.publica = UserFeedback.objects.create(user=self.aluno, rating=5, comment='O tutor ajuda muito.',
                                                   allow_public=True, trigger='first_lesson',
                                                   context_data={'chave': 'primeira_licao'})
        self.privada = UserFeedback.objects.create(user=self.aluno, rating=2, comment='Lento.', allow_contact=True)

    def test_lista_e_aprovar(self):
        r = self.c.get(BASE + 'opinioes/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['numeros'], {'total': 2, 'novas_mes': 2, 'media': 3.5, 'por_rever': 2,
                                        'por_rever_publicas': 1, 'no_site': 0})
        item = next(x for x in d['resultados'] if x['id'] == str(self.publica.id))
        self.assertEqual((item['momento'], item['area'], item['plano'], item['estado']),
                         ('Depois da primeira lição', 'Petróleo e Gás', 'Gratuito', 'por_rever'))
        self.assertEqual(self.client.get('/api/v1/users/feedback/testimonials/').json()['count'], 0)

        r = self.c.patch(BASE + f'opinioes/{self.publica.id}/', {'estado': 'aprovada', 'nota_interna': 'Boa.'},
                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['no_site'])
        self.c.patch(BASE + f'opinioes/{self.privada.id}/', {'estado': 'recusada'}, format='json')
        self.assertEqual(self.c.get(BASE + 'opinioes/?estado=recusada').json()['total'], 1)
        self.assertEqual(self.c.get(BASE + 'opinioes/?estado=todas').json()['numeros']['no_site'], 1)
        self.assertEqual(self.c.get(BASE + 'opinioes/?estado=x').status_code, 400)
        self.assertEqual(self.c.patch(BASE + f'opinioes/{self.privada.id}/', {'estado': 'x'},
                                      format='json').status_code, 400)
        t = self.client.get('/api/v1/users/feedback/testimonials/').json()
        self.assertEqual(t['count'], 1)
        self.assertEqual((t['testimonials'][0]['name'], t['testimonials'][0]['area']), ('Tomás K.', 'Petróleo e Gás'))
        self.assertEqual(RegistoAdmin.objects.filter(accao='opiniao').count(), 2)

    def test_testemunhos_mostrar_e_ordem(self):
        outro = criar('o@pe.ao', name='Rita Bento')
        segunda = UserFeedback.objects.create(user=outro, rating=4, comment='Muito prático.', allow_public=True)
        for f in (self.publica, segunda, self.privada):
            self.c.patch(BASE + f'opinioes/{f.id}/', {'estado': 'aprovada'}, format='json')
        lista = self.c.get(BASE + 'testemunhos/').json()
        self.assertEqual({x['nome_curto'] for x in lista}, {'Tomás K.', 'Rita B.'})  # a privada não entra
        self.assertEqual(set(lista[0]), {'id', 'nome_curto', 'area', 'texto', 'nota', 'mostrar', 'ordem', 'conta_activa'})

        r = self.c.post(BASE + 'testemunhos/ordem/', {'ids': [str(segunda.id), str(self.publica.id)]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([x['nome_curto'] for x in r.json()], ['Rita B.', 'Tomás K.'])
        site = self.client.get('/api/v1/users/feedback/testimonials/').json()['testimonials']
        self.assertEqual([x['name'] for x in site], ['Rita B.', 'Tomás K.'])

        r = self.c.patch(BASE + f'testemunhos/{segunda.id}/', {'mostrar': False}, format='json')
        self.assertFalse(r.json()['mostrar'])
        site = self.client.get('/api/v1/users/feedback/testimonials/').json()['testimonials']
        self.assertEqual([x['name'] for x in site], ['Tomás K.'])
        self.assertEqual(self.c.patch(BASE + f'testemunhos/{self.privada.id}/', {'mostrar': True},
                                      format='json').status_code, 404)
        self.assertEqual(self.c.post(BASE + 'testemunhos/ordem/', {'ids': [str(self.privada.id)]},
                                     format='json').status_code, 400)
        self.assertTrue(RegistoAdmin.objects.filter(accao='testemunhos_ordem').exists())
        self.assertTrue(RegistoAdmin.objects.filter(accao='testemunho_mostrar').exists())

    def test_lista_antiga_nota_invalida_400(self):
        r = self.c.get('/api/v1/users/feedback/admin/list/?rating=abc')
        self.assertEqual(r.status_code, 400)
        staff = criar('s@pe.ao', is_staff=True)
        c = APIClient()
        c.force_authenticate(staff)
        self.assertEqual(c.get('/api/v1/users/feedback/admin/list/').status_code, 403)
