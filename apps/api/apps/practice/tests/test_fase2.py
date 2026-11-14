"""
Fase 2: limite diário de lições novas (plano Gratuito) e cobrança/custo da conversa com o tutor.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_fase2

Nenhum teste chama o Claude ou o Vapi: o cliente da Anthropic é substituído por um que falha
(ou por um mock, quando o teste precisa de ver o pedido).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice import limite_licoes
from apps.practice.conversa import servico
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import (
    ChallengeOption, ChallengeProgress, DailyStudyLog, LessonCompletion, PointsEntry, PracticeChallenge,
    PracticeLesson, PracticeUnit, VapiSession,
)
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
P = '/api/v1/student/practice-courses/'
C = '/api/v1/practice/conversa/'
VAPI = dict(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')

FALAS = [
    'Yes, I can send the report on Thursday because the data is almost ready.',
    'It include the monthly figures and a short summary for the team.',
    'I need the sales data from you, and then I will finish the draft in Thursday.',
]


def _token(client, user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')


class SemClaude:
    """Qualquer pedido real ao Claude falha o teste."""

    def setUp(self):
        super().setUp()
        p = mock.patch('apps.practice.conversa.analise._cliente',
                       side_effect=AssertionError('chamada real ao Claude num teste'))
        p.start()
        self.addCleanup(p.stop)


# ---------------------------------------------------------------------------
# A. Limite diário de lições
# ---------------------------------------------------------------------------

class LicoesBase(APITestCase):

    def setUp(self):
        self.client = APIClient()
        prof = User.objects.create_user(email='prof-f2@example.com', name='Prof', password='x', role='teacher')
        self.aluno = User.objects.create_user(email='aluno-f2@example.com', name='Aluno F2', password='x',
                                              role='student')
        self.free = SubscriptionPlan.objects.get(plan_type='FREE')
        self.free.daily_lessons_limit = 3
        self.free.save(update_fields=['daily_lessons_limit'])
        self.sub = UserSubscription.objects.get(user=self.aluno)
        UserSubscription.objects.filter(pk=self.sub.pk).update(plan=self.free, status='ACTIVE')
        curso = Course.objects.create(teacher=prof, teacherName='Prof', title='Prática', description='-',
                                      course_type='practice', status='Published')
        unidade = PracticeUnit.objects.create(course=curso, title='U1', description='', order=1)
        self.licoes = []
        for i in range(5):
            lic = PracticeLesson.objects.create(unit=unidade, title=f'L{i}', order=i)
            ch = PracticeChallenge.objects.create(lesson=lic, type='SELECT', question=f'Q{i}', order=1)
            ChallengeOption.objects.create(challenge=ch, text='certa', is_correct=True, order=1)
            ChallengeOption.objects.create(challenge=ch, text='errada', is_correct=False, order=2)
            lic.ch = ch
            self.licoes.append(lic)
        _token(self.client, self.aluno)

    def responder(self, lic):
        ChallengeProgress.objects.update_or_create(user=self.aluno, challenge=lic.ch, defaults={'completed': True})

    def concluir(self, lic):
        self.responder(lic)
        return self.client.post(f'{P}complete-lesson/', {'lesson_id': str(lic.id), 'duration_seconds': 60},
                                format='json')

    def jogar(self, lic):
        return self.client.get(f'{P}lessons/{lic.id}/jogar/')

    def fazer_tres(self):
        for lic in self.licoes[:3]:
            self.assertEqual(self.jogar(lic).status_code, 200)
            r = self.concluir(lic)
            self.assertEqual(r.status_code, 200, r.content)
            self.assertTrue(r.data['first_completion'])


class LimiteLicoesTests(LicoesBase):

    def test_quarta_licao_nova_bloqueada_com_403(self):
        self.fazer_tres()
        r = self.jogar(self.licoes[3])
        self.assertEqual(r.status_code, 403)
        d = r.json()
        self.assertEqual(set(d), {'codigo', 'mensagem', 'limite', 'feitas', 'renova_em'})
        self.assertEqual((d['codigo'], d['limite'], d['feitas']), ('limite_licoes', 3, 3))
        self.assertEqual(d['mensagem'], 'Já fez as 3 lições de hoje. Amanhã há mais, ou passe para o Premium '
                                        'para lições sem limite.')
        renova = datetime.fromisoformat(d['renova_em'])
        self.assertEqual(renova, limite_licoes.proxima_meia_noite())
        self.assertEqual((renova.hour, renova.minute, renova.utcoffset()), (0, 0, timedelta(hours=1)))

    def test_repetir_licao_feita_nunca_conta_e_e_permitido(self):
        self.fazer_tres()
        r = self.jogar(self.licoes[0])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['repeticao'])
        ChallengeProgress.objects.filter(user=self.aluno).update(updated_at=timezone.now() + timedelta(seconds=5))
        r = self.concluir(self.licoes[0])
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['first_completion'])
        self.assertEqual(limite_licoes.licoes_novas_hoje(self.aluno), 3)

    def test_concluir_licao_nao_comecada_depois_do_limite_403(self):
        self.fazer_tres()
        r = self.concluir(self.licoes[3])  # respostas criadas já depois do limite
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'limite_licoes')
        self.assertFalse(LessonCompletion.objects.filter(user=self.aluno, lesson=self.licoes[3]).exists())

    def test_licao_comecada_antes_do_limite_pode_ser_terminada(self):
        for lic in self.licoes[:3]:  # respondidas (ainda sem conclusão): a 4.ª fica desbloqueada
            self.responder(lic)
        self.assertEqual(self.jogar(self.licoes[3]).status_code, 200)
        self.responder(self.licoes[3])  # começou (1.ª resposta) antes de esgotar o limite
        ChallengeProgress.objects.filter(user=self.aluno).update(completed_at=timezone.now() - timedelta(minutes=5))
        self.fazer_tres()
        self.assertEqual(self.jogar(self.licoes[3]).status_code, 200)
        r = self.concluir(self.licoes[3])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.jogar(self.licoes[4]).status_code, 403)

    def test_dia_de_angola(self):
        self.fazer_tres()
        # as três foram "ontem" em Luanda: hoje há lições outra vez
        ontem = limite_licoes.inicio_do_dia(hoje_luanda()) - timedelta(minutes=1)
        LessonCompletion.objects.filter(user=self.aluno).update(first_completed_at=ontem)
        self.assertEqual(self.jogar(self.licoes[3]).status_code, 200)

    def test_premium_sem_limite(self):
        premium = SubscriptionPlan.objects.get(plan_type='PREMIUM')
        UserSubscription.objects.filter(pk=self.sub.pk).update(
            plan=premium, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30))
        self.fazer_tres()
        self.assertEqual(self.jogar(self.licoes[3]).status_code, 200)
        self.assertEqual(self.concluir(self.licoes[3]).status_code, 200)
        d = self.client.get(f'{P}hearts-status/').json()['licoes_hoje']
        self.assertEqual((d['feitas'], d['limite']), (4, None))

    def test_premium_expirado_tem_limite_do_gratuito(self):
        premium = SubscriptionPlan.objects.get(plan_type='PREMIUM')
        UserSubscription.objects.filter(pk=self.sub.pk).update(
            plan=premium, status='ACTIVE', expires_at=timezone.now() - timedelta(days=1))
        self.fazer_tres()
        self.assertEqual(self.jogar(self.licoes[3]).status_code, 403)

    def test_hearts_status_e_assinatura_mostram_licoes_de_hoje(self):
        d = self.client.get(f'{P}hearts-status/').json()['licoes_hoje']
        self.assertEqual((d['feitas'], d['limite']), (0, 3))
        self.assertEqual(datetime.fromisoformat(d['renova_em']), limite_licoes.proxima_meia_noite())
        self.concluir(self.licoes[0])
        self.concluir(self.licoes[1])
        self.assertEqual(self.client.get(f'{P}hearts-status/').json()['licoes_hoje']['feitas'], 2)
        sub = UserSubscription.objects.get(pk=self.sub.pk)
        self.assertEqual(sub.daily_lessons_used, 2)  # gravado na conclusão
        self.assertTrue(sub.can_take_lesson())
        self.concluir(self.licoes[2])
        sub = UserSubscription.objects.get(pk=self.sub.pk)
        sub.reset_daily_usage_if_needed()
        self.assertEqual(sub.daily_lessons_used, 3)
        self.assertFalse(sub.can_take_lesson())
        # um contador antigo/errado é corrigido ao ler
        UserSubscription.objects.filter(pk=self.sub.pk).update(daily_lessons_used=0)
        sub = UserSubscription.objects.get(pk=self.sub.pk)
        sub.reset_daily_usage_if_needed()
        self.assertEqual(sub.daily_lessons_used, 3)


class DiaLuandaTests(SimpleTestCase):

    def test_meia_noite_de_luanda(self):
        # domingo 23:30 UTC = segunda 00:30 em Luanda
        agora = datetime(2026, 11, 15, 23, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(hoje_luanda(agora).isoformat(), '2026-11-16')
        self.assertEqual(limite_licoes.proxima_meia_noite(agora).astimezone(dt_timezone.utc),
                         datetime(2026, 11, 16, 23, 0, tzinfo=dt_timezone.utc))


# ---------------------------------------------------------------------------
# B. Conversa: cobrança e custo
# ---------------------------------------------------------------------------

@override_settings(CONVERSA_SIMULADA=True, CONVERSA_MAX_MINUTOS_SESSAO=15, ANTHROPIC_API_KEY='')
class ConversaBase(SemClaude, APITestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.plus = SubscriptionPlan.objects.update_or_create(plan_type='PREMIUM_PLUS', defaults=dict(
            name='Premium Plus', description='-', monthly_price=Decimal('0'), daily_speaking_minutes=20))[0]
        self.aluno = User.objects.create_user(email='conv-f2@example.com', name='Ana Fase', password='x',
                                              role='student')
        self.sub, _ = UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=self.plus, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30),
            daily_speaking_minutes_used=0, last_reset_date=hoje_luanda()))
        self.client = APIClient()
        _token(self.client, self.aluno)

    def criar(self):
        r = self.client.post(f'{C}sessoes/', {'situacao': 'pedir_relatorio', 'nivel': 'B1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.data['id']

    def ligar(self, sid):
        return self.client.post(f'{C}sessoes/{sid}/ligada/', {}, format='json')

    def mover(self, sid, ligou_ha=None, actividade_ha=None, inicio_ha=None):
        agora = timezone.now()
        campos = {}
        if ligou_ha is not None:
            campos['connected_at'] = agora - timedelta(seconds=ligou_ha)
        if actividade_ha is not None:
            campos['last_activity_at'] = agora - timedelta(seconds=actividade_ha)
        if inicio_ha is not None:
            campos['started_at'] = agora - timedelta(seconds=inicio_ha)
        VapiSession.objects.filter(pk=sid).update(**campos)

    def terminar(self, sid, transcricao=None):
        return self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': transcricao or []}, format='json')

    def conversar(self, sid):
        for f in FALAS:
            r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': f}, format='json')
            self.assertEqual(r.status_code, 200, r.content)

    def usados(self):
        return UserSubscription.objects.get(pk=self.sub.pk).daily_speaking_minutes_used


class LigadaTests(ConversaBase):

    def test_ligada_idempotente_e_relogio_comeca_ai(self):
        sid = self.criar()
        self.mover(sid, inicio_ha=300)  # criada há 5 min, ligou agora
        r1 = self.ligar(sid)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(set(r1.data), {'id', 'ligada_em', 'max_segundos', 'termina_em'})
        r2 = self.ligar(sid)
        self.assertEqual(r2.data['ligada_em'], r1.data['ligada_em'])
        # o tempo de espera antes de ligar não conta: tempo_esgotado só depois de max_segundos desde a ligação
        self.mover(sid, inicio_ha=20 * 60)
        r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Hello there my friend'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_nunca_ligou_custa_zero(self):
        sid = self.criar()
        self.mover(sid, inicio_ha=600)
        r = self.terminar(sid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['estado'], r.data['minutos'], r.data['minutos_cobrados'], r.data['segundos']),
                         ('nao_ligou', 0, 0, 0))
        self.assertEqual(self.usados(), 0)
        self.assertFalse(DailyStudyLog.objects.filter(user=self.aluno).exists())
        # não conta no progresso nem nas estatísticas
        self.assertEqual(self.client.get(f'{C}progresso/').data['sessoes'], 0)
        est = self.client.get(f'{P}estatisticas/', {'periodo': '7'}).data
        self.assertEqual(est['conversacao']['sessoes'], 0)
        self.assertEqual(self.ligar(sid).status_code, 409)

    def test_tolerancia_e_arredondamento(self):
        self.assertEqual([servico.minutos_a_cobrar(s) for s in (0, 19, 20, 60, 61, 150, 900)],
                         [0, 0, 1, 1, 2, 3, 15])
        sid = self.criar()
        self.ligar(sid)
        self.mover(sid, ligou_ha=15, actividade_ha=0)
        r = self.terminar(sid).data
        self.assertEqual((r['estado'], r['minutos_cobrados']), ('sem_avaliacao', 0))
        self.assertEqual(self.usados(), 0)

    def test_actividade_sem_ligada_conta_como_ligacao(self):
        sid = self.criar()
        self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I send it in Thursday'}, format='json')
        s = VapiSession.objects.get(pk=sid)
        self.assertIsNotNone(s.connected_at)
        self.assertEqual(s.connected_at, s.last_activity_at)


class AbandonoTests(ConversaBase):

    def test_abandonada_cobra_ate_30s_depois_da_ultima_actividade(self):
        sid = self.criar()
        self.ligar(sid)
        self.mover(sid, ligou_ha=600, actividade_ha=480)  # 2 min de conversa, depois saiu
        r = self.terminar(sid).data
        self.assertEqual(r['segundos'], 150)
        self.assertEqual(r['minutos_cobrados'], 3)
        self.assertEqual(self.usados(), 3)

    def test_abandonada_fechada_ao_criar_outra(self):
        sid = self.criar()
        self.ligar(sid)
        self.mover(sid, ligou_ha=3600, actividade_ha=3540)  # esqueceu-se uma hora: 90 s contam
        self.criar()
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual((s.status, s.duration_seconds, s.duration_minutes), ('sem_avaliacao', 90, 2))
        self.assertEqual(self.usados(), 2)

    def test_sessao_de_ontem_nao_gasta_a_quota_de_hoje(self):
        sid = self.criar()
        self.ligar(sid)
        ontem = limite_licoes.inicio_do_dia(hoje_luanda()) - timedelta(minutes=10)
        VapiSession.objects.filter(pk=sid).update(started_at=ontem, connected_at=ontem,
                                                  last_activity_at=ontem + timedelta(seconds=150))
        r = self.terminar(sid).data
        self.assertEqual(r['minutos_cobrados'], 3)
        self.assertEqual(self.usados(), 0)
        dia = hoje_luanda(ontem)
        log = DailyStudyLog.objects.get(user=self.aluno, date=dia)
        self.assertAlmostEqual(log.conversation_minutes, 3.0, delta=0.01)

    def test_simulado_ignora_transcricao_do_cliente(self):
        sid = self.criar()
        self.ligar(sid)
        self.mover(sid, ligou_ha=120, actividade_ha=0)
        r = self.terminar(sid, [{'quem': 'aluno', 'texto': f} for f in FALAS]).data
        self.assertEqual(r['estado'], 'sem_avaliacao')
        self.assertFalse(any(t['quem'] == 'aluno' for t in r['transcricao']))


class AjusteCustoTests(ConversaBase):

    @override_settings(**VAPI)
    def test_ajuste_depois_do_tempo_409_sem_claude(self):
        sid = self.criar()
        self.ligar(sid)
        self.mover(sid, ligou_ha=16 * 60, actividade_ha=0)
        with mock.patch('apps.practice.conversa.analise.ajuste_claude') as claude:
            r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I send it in Thursday'}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'tempo_esgotado'))
        claude.assert_not_called()

    @override_settings(**VAPI)
    def test_ajuste_poucas_palavras_e_repetido_nao_chamam_claude(self):
        sid = self.criar()
        self.ligar(sid)
        with mock.patch('apps.practice.conversa.analise.ajuste_claude', return_value=None) as claude:
            for frase in ('Yes.', 'OK sure', 'I send it in Thursday', 'I send it in  Thursday'):
                r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': frase}, format='json')
                self.assertEqual(r.data, {'ajuste': None})
        self.assertEqual(claude.call_count, 1)

    @override_settings(**VAPI)
    def test_responder_em_vapi_409(self):
        sid = self.criar()
        with mock.patch('apps.practice.conversa.analise.resposta_claude') as claude:
            r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Hello my friend'}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'so_simulado'))
        claude.assert_not_called()


class AvaliacaoForaDaTransaccaoTests(ConversaBase):

    def test_avaliacao_corre_sem_bloqueios_e_terminar_devolve_resumo(self):
        sid = self.criar()
        self.ligar(sid)
        self.conversar(sid)
        self.mover(sid, ligou_ha=240, actividade_ha=0)
        base = len(connection.savepoint_ids)
        real = servico.analise.avaliar
        visto = {}

        def avaliar(*a, **kw):
            visto['savepoints'] = len(connection.savepoint_ids)
            s = VapiSession.objects.get(pk=sid)
            visto['estado'] = s.status
            visto['usados'] = self.usados()
            return real(*a, **kw)

        with mock.patch('apps.practice.conversa.analise.avaliar', side_effect=avaliar):
            r = self.terminar(sid).data
        self.assertEqual(visto, {'savepoints': base, 'estado': 'a_avaliar', 'usados': 4})
        self.assertEqual(r['estado'], 'avaliada')
        self.assertIsNotNone(r['notas'])
        self.assertEqual(r['minutos_cobrados'], 4)
        self.assertEqual(PointsEntry.objects.get(user=self.aluno, reason='conversa').points, 8)

    def test_get_resumo_a_avaliar(self):
        sid = self.criar()
        self.ligar(sid)
        self.conversar(sid)
        self.mover(sid, ligou_ha=120, actividade_ha=0)
        with mock.patch('apps.practice.conversa.servico.avaliar_pendente', side_effect=lambda pk, **k:
                        VapiSession.objects.get(pk=pk)):
            r = self.terminar(sid).data
        self.assertEqual((r['estado'], r['notas']), ('a_avaliar', None))
        # outro pedido está a avaliar (marca recente): o GET não repete a avaliação
        s = VapiSession.objects.get(pk=sid)
        s.full_session_data['avaliacao_iniciada_em'] = timezone.now().isoformat()
        s.save(update_fields=['full_session_data'])
        with mock.patch('apps.practice.conversa.analise.avaliar') as avaliar:
            self.assertEqual(self.client.get(f'{C}sessoes/{sid}/').data['estado'], 'a_avaliar')
        avaliar.assert_not_called()
        # marca antiga (o pedido caiu): o GET avalia
        s.full_session_data['avaliacao_iniciada_em'] = (timezone.now() - timedelta(minutes=5)).isoformat()
        s.save(update_fields=['full_session_data'])
        d = self.client.get(f'{C}sessoes/{sid}/').data
        self.assertEqual(d['estado'], 'avaliada')
        # a_avaliar conta nas sessões, mas sem nota
        self.assertEqual(self.client.get(f'{C}progresso/').data['sessoes'], 1)

    @override_settings(**VAPI, VAPI_PRIVATE_KEY='sk_test_falsa')
    def test_sessao_abandonada_avaliada_por_regras_ao_criar_outra(self):
        from apps.practice.tests.vapi_falso import VapiFalso
        vapi = VapiFalso()
        sid = self.criar()
        falas = [x for f in FALAS for x in (('tutor', 'Tell me more.'), ('aluno', f))]
        cid = vapi.chamada(sid, falas, duracao=180)
        self.client.post(f'{C}sessoes/{sid}/ligada/', {'call_id': cid}, format='json')
        self.mover(sid, ligou_ha=180, actividade_ha=0)
        with mock.patch('apps.practice.conversa.analise.avaliar_claude') as claude, \
                mock.patch('apps.practice.conversa.chamada.pedir', vapi):
            self.criar()
        claude.assert_not_called()
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.status, 'avaliada')
        self.assertEqual(s.full_session_data['fonte_avaliacao'], 'regras')
        self.assertEqual(s.duration_seconds, 180)  # a duração do Vapi

    def test_zero_minutos_sem_pontos(self):
        sid = self.criar()
        self.ligar(sid)
        self.conversar(sid)
        self.mover(sid, ligou_ha=10, actividade_ha=0)
        r = self.terminar(sid).data
        self.assertEqual((r['estado'], r['minutos_cobrados']), ('avaliada', 0))
        self.assertFalse(PointsEntry.objects.filter(user=self.aluno, reason='conversa').exists())
        self.assertEqual(VapiSession.objects.get(pk=sid).full_session_data['pontos'], 0)


class LegadoSituacaoTests(ConversaBase):

    def test_situacao_id_null(self):
        VapiSession.objects.create(session_id='leg-f2', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=4, overall_score=70)
        d = self.client.get(f'{C}sessoes/leg-f2/').data
        self.assertEqual(d['situacao'], {'id': None, 'titulo': 'Conversa com o tutor'})
        self.assertEqual(d['minutos_cobrados'], 4)
