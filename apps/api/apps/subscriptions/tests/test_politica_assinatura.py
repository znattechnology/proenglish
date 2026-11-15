"""
Política de assinatura: oferta do plano certo em cada limite, vidas sem assinatura ou com a paga
terminada (regras do Gratuito), exame oral só nos planos pagos, Gratuito mais apertado (migração)
e avisos do teste grátis com o que se perde.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.subscriptions.tests.test_politica_assinatura
"""
import importlib
from datetime import timedelta
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.practice import study_services
from apps.practice.models import UserProgress
from apps.subscriptions import oferta as of
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()


def planos():
    gratuito, _ = SubscriptionPlan.objects.update_or_create(plan_type='FREE', defaults=dict(
        name='Gratuito', monthly_price=Decimal('0'), yearly_price=Decimal('0'), daily_lessons_limit=2,
        daily_speaking_minutes=3, trial_speaking_minutes=3, daily_ai_analyses_limit=3,
        daily_detailed_pronunciation_limit=0, hearts_limit=3, hearts_recharge_hours=4, trial_days=0,
        certificates=False, offline_downloads=False, dias_teste=0, is_active=True, sort_order=1))
    premium, _ = SubscriptionPlan.objects.update_or_create(plan_type='PREMIUM', defaults=dict(
        name='Premium', monthly_price=Decimal('14950'), yearly_price=Decimal('149500'),
        daily_lessons_limit=None, daily_speaking_minutes=10, daily_ai_analyses_limit=20,
        daily_detailed_pronunciation_limit=10, hearts_limit=0, hearts_recharge_hours=0, trial_days=0,
        certificates=True, offline_downloads=True, dias_teste=7, is_active=True, sort_order=2))
    plus, _ = SubscriptionPlan.objects.update_or_create(plan_type='PREMIUM_PLUS', defaults=dict(
        name='Premium Plus', monthly_price=Decimal('24950'), yearly_price=Decimal('249500'),
        daily_lessons_limit=None, daily_speaking_minutes=20, daily_ai_analyses_limit=None,
        daily_detailed_pronunciation_limit=20, hearts_limit=0, hearts_recharge_hours=0, trial_days=0,
        certificates=True, offline_downloads=True, dias_teste=0, is_active=True, sort_order=3))
    return gratuito, premium, plus


class Base(TestCase):
    def setUp(self):
        self.gratuito, self.premium, self.plus = planos()
        self.aluno = User.objects.create_user(email='politica@exemplo.ao', username='politica',
                                              password='x-teste-politica', role='student', name='Aluno')
        self.sub = UserSubscription.objects.get(user=self.aluno)

    def no_plano(self, plano, expira_em=timedelta(days=30), status='ACTIVE'):
        self.sub.plan = plano
        self.sub.status = status
        self.sub.expires_at = timezone.now() + expira_em
        self.sub.current_hearts = 999 if not plano.hearts_limit else plano.hearts_limit
        self.sub.save()
        return self.sub


class OfertaTests(Base):
    def test_gratuito_sem_vidas_recebe_o_premium_com_o_ganho_primeiro(self):
        o = of.oferta(self.aluno, of.VIDAS)
        self.assertEqual(o['plano']['tipo'], 'PREMIUM')
        self.assertEqual(o['plano']['preco_mensal_kz'], 14950)
        self.assertEqual(o['ganhos'][0], 'Vidas ilimitadas')
        self.assertTrue(o['plano']['pode_experimentar'])
        self.assertEqual(o['plano']['dias_teste'], 7)
        self.assertEqual(o['ligacao'], '/user/upgrade?plan=PREMIUM')

    def test_cada_recurso_do_gratuito_leva_ao_premium(self):
        for recurso in of.RECURSOS:
            self.assertEqual(of.oferta(self.aluno, recurso)['plano']['tipo'], 'PREMIUM', recurso)
        self.assertEqual(of.oferta(self.aluno, of.EXAME)['ganhos'][0], 'Exame oral e certificado de cada curso')

    def test_premium_sem_minutos_recebe_o_plus_e_vidas_nada(self):
        self.no_plano(self.premium)
        self.assertEqual(of.oferta(self.aluno, of.CONVERSA)['plano']['tipo'], 'PREMIUM_PLUS')
        self.assertEqual(of.oferta(self.aluno, of.ANALISES)['plano']['tipo'], 'PREMIUM_PLUS')
        self.assertIsNone(of.oferta(self.aluno, of.VIDAS))
        self.assertIsNone(of.oferta(self.aluno, of.EXAME))

    def test_plus_nao_tem_oferta(self):
        self.no_plano(self.plus)
        for recurso in of.RECURSOS:
            self.assertIsNone(of.oferta(self.aluno, recurso), recurso)

    def test_premium_expirado_conta_como_gratuito(self):
        self.no_plano(self.premium, expira_em=-timedelta(hours=1))
        self.assertEqual(of.oferta(self.aluno, of.VIDAS)['plano']['tipo'], 'PREMIUM')

    def test_plano_desactivado_nao_e_oferecido(self):
        self.premium.is_active = False
        self.premium.save()
        self.assertEqual(of.oferta(self.aluno, of.VIDAS)['plano']['tipo'], 'PREMIUM_PLUS')

    def test_quem_ja_experimentou_nao_ve_o_teste(self):
        from apps.subscriptions.models import TesteGratis
        TesteGratis.objects.create(user=self.aluno, plan=self.premium, telefone='923000111',
                                   termina_em=timezone.now() - timedelta(days=1))
        self.assertFalse(of.oferta(self.aluno, of.VIDAS)['plano']['pode_experimentar'])

    def test_corpo_sem_vidas(self):
        c = study_services.corpo_sem_vidas(self.aluno)
        self.assertEqual((c['error'], c['codigo']), ('hearts', 'sem_vidas'))
        self.assertEqual(c['oferta']['plano']['tipo'], 'PREMIUM')
        self.assertIn('custo_recarga_pontos', c)


class VidasTests(Base):
    def test_sem_assinatura_passa_ao_gratuito_com_recarga(self):
        UserSubscription.objects.filter(user=self.aluno).delete()
        e = study_services.get_hearts_state(self.aluno)
        self.assertEqual((e['maximum'], e['recharge_hours'], e['unlimited']), (3, 4, False))
        self.assertEqual(UserSubscription.objects.get(user=self.aluno).plan, self.gratuito)

    def test_sem_assinatura_a_propriedade_das_vidas_tambem_cria(self):
        UserSubscription.objects.filter(user=self.aluno).delete()
        progresso = UserProgress.objects.create(user=self.aluno, points=0)
        self.assertEqual(progresso.hearts, 3)
        self.assertTrue(UserSubscription.objects.filter(user=self.aluno).exists())

    def test_pago_expirado_segue_o_gratuito_e_recarrega(self):
        sub = self.no_plano(self.premium, expira_em=-timedelta(hours=1))
        self.assertEqual(sub.current_hearts, 999)
        e = study_services.get_hearts_state(self.aluno)
        self.assertEqual((e['current'], e['maximum'], e['unlimited']), (3, 3, False))
        sub.refresh_from_db()
        self.assertEqual(sub.current_hearts, 3)
        # Perde as 3 e, 4 horas depois, volta uma (antes: sem recarga nenhuma).
        sub.current_hearts = 0
        sub.last_heart_recharge = timezone.now() - timedelta(hours=4, minutes=5)
        sub.save()
        self.assertEqual(study_services.get_hearts_state(self.aluno)['current'], 1)
        self.assertEqual(UserProgress.objects.create(user=self.aluno).hearts, 1)

    def test_pago_activo_continua_ilimitado(self):
        self.no_plano(self.premium)
        self.assertTrue(study_services.get_hearts_state(self.aluno)['unlimited'])


class ExameTests(Base):
    def setUp(self):
        super().setUp()
        from apps.courses.models import Course
        self.curso = Course.objects.create(
            title='Inglês para a refinaria', course_type='video',
            teacher=User.objects.create_user(email='prof-politica@exemplo.ao', username='prof-politica',
                                             password='x-teste-politica', role='teacher', name='Prof'))

    def estado(self):
        from apps.practice.conversa import exame
        from unittest import mock
        with mock.patch.object(exame, 'exame_ligado', return_value=True):
            return exame.estado(self.aluno, self.curso, progresso=100)

    def test_gratuito_nao_faz_o_exame_e_ve_a_oferta(self):
        e = self.estado()
        self.assertFalse(e['disponivel'])
        self.assertEqual(e['motivo'], 'plano')
        self.assertEqual(e['oferta']['recurso'], 'exame')
        self.assertEqual(e['oferta']['plano']['tipo'], 'PREMIUM')

    def test_comecar_no_gratuito_da_403_com_oferta(self):
        from unittest import mock
        from apps.practice.conversa import exame
        from apps.practice.conversa.servico import ErroConversa
        with mock.patch.object(exame, 'exame_ligado', return_value=True), \
                mock.patch('apps.courses.certificados.progresso_actual', return_value=100):
            with self.assertRaises(ErroConversa) as ctx:
                exame.comecar(self.aluno, self.curso, consentimento=False)
        self.assertEqual((ctx.exception.status, ctx.exception.codigo), (403, 'plano'))
        self.assertEqual(ctx.exception.oferta['plano']['tipo'], 'PREMIUM')

    def test_premium_e_teste_gratis_fazem_o_exame(self):
        self.no_plano(self.premium)
        self.assertIsNone(self.estado()['motivo'])
        self.no_plano(self.premium, expira_em=timedelta(days=7), status='TRIAL')
        self.assertIsNone(self.estado()['motivo'])

    def test_premium_expirado_volta_a_ver_a_oferta(self):
        self.no_plano(self.premium, expira_em=-timedelta(minutes=1))
        self.assertEqual(self.estado()['motivo'], 'plano')


class CertificadoTests(Base):
    def test_emitir_no_gratuito_traz_oferta(self):
        from apps.courses.certificados import CertificadoIndisponivel, emitir_certificado
        from apps.courses.models import Course
        curso = Course.objects.create(title='Curso', course_type='video', teacher=self.aluno)
        with self.assertRaises(CertificadoIndisponivel) as ctx:
            emitir_certificado(self.aluno, curso)
        self.assertEqual(ctx.exception.codigo, 'CERTIFICADOS_NAO_INCLUIDOS')
        self.assertEqual(ctx.exception.detalhes['oferta']['recurso'], 'certificado')


class MigracaoGratuitoTests(TestCase):
    def setUp(self):
        self.mod = importlib.import_module('apps.subscriptions.migrations.0014_gratuito_mais_apertado')

    def test_aperta_so_os_valores_antigos(self):
        g, _ = SubscriptionPlan.objects.update_or_create(plan_type='FREE', defaults=dict(
            name='Gratuito', monthly_price=Decimal('0'), daily_lessons_limit=3, daily_ai_analyses_limit=5,
            daily_speaking_minutes=4, trial_speaking_minutes=5))  # 4: mudado pelo administrador
        self.mod.apertar(django_apps, None)
        g.refresh_from_db()
        self.assertEqual((g.daily_lessons_limit, g.daily_ai_analyses_limit, g.daily_speaking_minutes,
                          g.trial_speaking_minutes), (2, 3, 4, 3))
        self.mod.desapertar(django_apps, None)
        g.refresh_from_db()
        self.assertEqual((g.daily_lessons_limit, g.daily_ai_analyses_limit, g.trial_speaking_minutes), (3, 5, 5))


class AvisosTesteTests(Base):
    def test_fim_do_teste_diz_o_que_se_perde(self):
        from apps.pagamentos.avisos import avisar_teste_terminado
        from apps.users.models import Notification
        self.no_plano(self.gratuito)
        avisar_teste_terminado(None, subscription=self.sub, plano_anterior=self.premium)
        n = Notification.objects.filter(user=self.aluno).latest('created_at')
        self.assertIn('Deixou de ter vidas ilimitadas, lições novas sem limite', n.body)
        self.assertIn('exame oral e certificado de cada curso', n.body)

    def test_dois_dias_antes_diz_o_que_se_perde(self):
        from apps.pagamentos.avisos import avisar_teste_a_terminar
        from apps.users.models import Notification
        sub = self.no_plano(self.premium, expira_em=timedelta(days=2), status='TRIAL')
        avisar_teste_a_terminar(None, subscription=sub, fim=sub.expires_at)
        n = Notification.objects.filter(user=self.aluno).latest('created_at')
        self.assertIn('No Gratuito deixa de ter vidas ilimitadas', n.body)


class ConversaTests(Base):
    def test_sem_minutos_responde_com_a_oferta(self):
        from apps.practice.conversa import servico, views
        r = views._erro(servico._erro_quota(self.aluno, 'sem_minutos'))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['codigo'], 'sem_minutos')
        self.assertEqual(r.data['oferta']['recurso'], 'conversa')
        self.assertEqual(r.data['oferta']['ganhos'][0], '10 minutos de conversa com o tutor por dia')


class EstadoVidasTests(Base):
    def test_estado_das_vidas_traz_a_oferta_so_a_zero(self):
        self.assertIsNone(study_services.build_hearts_status(self.aluno)['oferta'])
        UserSubscription.objects.filter(pk=self.sub.pk).update(current_hearts=0, last_heart_recharge=timezone.now())
        self.assertEqual(study_services.build_hearts_status(self.aluno)['oferta']['recurso'], 'vidas')
        self.no_plano(self.premium)
        self.assertIsNone(study_services.build_hearts_status(self.aluno)['oferta'])
