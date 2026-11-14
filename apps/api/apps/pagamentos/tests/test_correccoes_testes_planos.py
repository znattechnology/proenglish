"""
Teste grátis: um por número Multicaixa Express e por caixa de correio, só alunos.
Planos desactivados: saem do catálogo para pessoas novas, mas quem os tem continua a renovar.
"""

from datetime import timedelta

from django.core import mail
from django.utils import timezone

from apps.pagamentos.renovacao import expirar_subscricoes
from apps.pagamentos.teste import avisar_testes_a_terminar, terminar_testes
from apps.subscriptions.models import SubscriptionHistory, TesteGratis, UserSubscription, normalizar_email
from apps.users.models import Notification

from .test_fase2 import BaseFase2
from .test_mcx import User

URL_TESTE = '/api/v1/pagamentos/teste/'
URL_PLANOS = '/api/v1/subscriptions/plans/'
URL_SUB = '/api/v1/subscriptions/my-subscription/'


class Base(BaseFase2):
    def setUp(self):
        super().setUp()
        self.premium.dias_teste = 7
        self.premium.save()

    def comecar(self, plano='PREMIUM', telefone='923 456 789', user=None):
        if user is not None:
            self.client.force_authenticate(user)
        corpo = {'plano': plano}
        if telefone is not None:
            corpo['telefone'] = telefone
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(URL_TESTE, corpo, format='json')

    def aluno(self, email):
        return User.objects.create_user(email=email, name='Outro aluno', password='password123')


class NormalizarEmailTests(Base):
    def test_gmail_pontos_etiqueta_e_maiusculas(self):
        self.assertEqual(normalizar_email(' A.Na+promo@GoogleMail.com '), 'ana@gmail.com')
        self.assertEqual(normalizar_email('ana@gmail.com'), 'ana@gmail.com')
        self.assertEqual(normalizar_email('A.Na+x@Empresa.ao'), 'a.na@empresa.ao')


class TestePorTelefoneTests(Base):
    def test_telefone_obrigatorio_e_valido(self):
        r = self.comecar(telefone=None)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'telefone_em_falta')
        self.assertIn('telefone', r.data['details'])
        r = self.comecar(telefone='12345')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'telefone_invalido')
        self.assertFalse(TesteGratis.objects.exists())
        self.assertEqual(UserSubscription.objects.get(user=self.user).status, 'ACTIVE')

    def test_guarda_o_numero_normalizado(self):
        r = self.comecar(telefone='+244 923 456 789')
        self.assertEqual(r.status_code, 201, r.data)
        t = TesteGratis.objects.get(user=self.user)
        self.assertEqual((t.telefone, t.email_normalizado, t.plan), ('923456789', 'aluno@example.com', self.premium))

    def test_mesmo_numero_noutra_conta_e_recusado(self):
        self.assertEqual(self.comecar().status_code, 201)
        outro = self.aluno('novo@example.com')
        r = self.comecar(telefone='244923456789', user=outro)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'telefone_ja_usado')
        self.assertIn('telefone', r.data['details'])
        self.assertIn('já foi usado', r.data['message'])
        self.assertEqual(UserSubscription.objects.get(user=outro).plan.plan_type, 'FREE')
        # Outro número funciona
        self.assertEqual(self.comecar(telefone='923 000 111', user=outro).status_code, 201)

    def test_mesma_caixa_de_correio_e_recusada(self):
        a = self.aluno('maria.silva@gmail.com')
        self.assertEqual(self.comecar(user=a).status_code, 201)
        b = self.aluno('MariaSilva+2@googlemail.com')
        r = self.comecar(telefone='923 111 222', user=b)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'teste_ja_usado')
        self.assertFalse(self.client.get(URL_SUB).data['pode_experimentar'])

    def test_so_alunos(self):
        r = self.comecar(user=self.teacher)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['code'], 'so_alunos')
        admin = User.objects.create_user(email='adm@example.com', name='Adm', password='password123', role='admin')
        self.assertEqual(self.comecar(user=admin).status_code, 403)
        self.assertFalse(TesteGratis.objects.exists())
        self.assertFalse(self.client.get(URL_SUB).data['pode_experimentar'])

    def test_plano_teste_aponta_para_o_plano_com_teste(self):
        self.premium.dias_teste = 0
        self.premium.save()
        self.plus.dias_teste = 14
        self.plus.save()
        d = self.client.get(URL_SUB).data
        self.assertEqual((d['pode_experimentar'], d['dias_teste'], d['plano_teste']), (True, 14, 'PREMIUM_PLUS'))
        self.assertEqual(self.comecar('PREMIUM_PLUS').status_code, 201)
        d = self.client.get(URL_SUB).data
        self.assertEqual((d['em_teste'], d['dias_teste'], d['plano_teste']), (True, 14, 'PREMIUM_PLUS'))


class PlanoDesactivadoTests(Base):
    def desactivar(self, plano=None):
        plano = plano or self.premium
        plano.is_active = False
        plano.save()

    def tipos_no_catalogo(self):
        d = self.client.get(URL_PLANOS).data
        d = d['results'] if isinstance(d, dict) else d
        return {p['plan_type']: p['so_renovacao'] for p in d}

    def test_pessoa_nova_nao_ve_nem_compra(self):
        self.desactivar()
        self.assertNotIn('PREMIUM', self.tipos_no_catalogo())
        for ref in ('PREMIUM', str(self.premium.id)):
            r = self.orcar(ref)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data['code'], 'plano_indisponivel')
            self.assertIn('já não está disponível', r.data['message'])
        r = self.criar()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.comecar().status_code, 404)

    def test_assinante_continua_a_renovar_ao_preco_contratado(self):
        self.pagar()
        self.desactivar()
        self.premium.monthly_price = 20000
        self.premium.save()
        self.assertEqual(self.tipos_no_catalogo()['PREMIUM'], True)
        sub = UserSubscription.objects.get(user=self.user)
        self.recuar((sub.expires_at - timezone.now()).days - 3)
        r = self.orcar('PREMIUM')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['operacao'], r.data['final_kz']), ('renovacao', 14950))
        self.assertEqual(self.pagar().total_kz, 14950)
        # Outra pessoa continua sem o ver
        self.client.force_authenticate(self.outro)
        self.assertNotIn('PREMIUM', self.tipos_no_catalogo())
        self.assertEqual(self.orcar('PREMIUM').status_code, 404)

    def test_em_teste_pode_converter_e_avisos_oferecem_pagar(self):
        self.assertEqual(self.comecar().status_code, 201)
        self.desactivar()
        o = self.orcar('PREMIUM')
        self.assertEqual(o.status_code, 200, o.data)
        self.assertEqual(o.data['operacao'], 'conversao_teste')
        self.assertFalse(o.data['pode_experimentar'])
        sub = UserSubscription.objects.get(user=self.user)
        fim = timezone.now() + timedelta(hours=40)
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=fim, trial_ends_at=fim)
        mail.outbox.clear()
        self.assertEqual(len(avisar_testes_a_terminar()), 1)
        n = Notification.objects.filter(user=self.user, title__icontains='termina').first()
        self.assertEqual(n.link, '/user/upgrade?plan=PREMIUM')
        self.assertIn('Pagar o Premium', mail.outbox[-1].body)
        # Depois de o teste terminar ainda pode pagar o plano (janela de recuperação)
        UserSubscription.objects.filter(pk=sub.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(terminar_testes(), 1)
        n = Notification.objects.filter(user=self.user, title__icontains='terminou').first()
        self.assertEqual(n.link, '/user/upgrade?plan=PREMIUM')
        self.assertEqual(self.orcar('PREMIUM').status_code, 200)
        self.assertEqual(self.tipos_no_catalogo()['PREMIUM'], True)
        self.assertEqual(self.pagar().total_kz, 14950)

    def test_expirado_ha_pouco_pode_voltar_mas_nao_depois_da_janela(self):
        self.pagar()
        UserSubscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        expirar_subscricoes()
        self.desactivar()
        self.assertEqual(self.orcar('PREMIUM').status_code, 200)
        SubscriptionHistory.objects.filter(event_type='EXPIRED').update(
            created_at=timezone.now() - timedelta(days=31))
        self.assertEqual(self.orcar('PREMIUM').status_code, 404)
        self.assertNotIn('PREMIUM', self.tipos_no_catalogo())
