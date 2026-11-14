"""
Conversa com o tutor: /api/v1/practice/conversa/

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_conversa
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.practice.conversa import regras
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import DailyStudyLog, PointsEntry, UserProgress, VapiSession
from apps.subscriptions.models import SubscriptionPlan, UserSubscription

User = get_user_model()
C = '/api/v1/practice/conversa/'

FALAS_BOAS = [
    'Yes, I can send the report on Thursday because the data is almost ready.',
    'It include the monthly figures and a short summary for the team.',
    'I need the sales data from you, and then I will finish the draft in Thursday.',
    'The final deadline is Friday morning, I will send it by email.',
]


def _plano(tipo, nome, minutos, trial_days=0, trial_min=0):
    return SubscriptionPlan.objects.update_or_create(plan_type=tipo, defaults=dict(
        name=nome, description='-', monthly_price=Decimal('0'), daily_speaking_minutes=minutos,
        trial_days=trial_days, trial_speaking_minutes=trial_min, ai_tutor=(tipo == 'PREMIUM_PLUS'),
    ))[0]


@override_settings(CONVERSA_SIMULADA=True, CONVERSA_MAX_MINUTOS_SESSAO=15)
class Base(APITestCase):

    def setUp(self):
        cache.clear()
        self.free = _plano('FREE', 'Gratuito', 5, trial_days=7, trial_min=5)
        self.premium = _plano('PREMIUM', 'Premium', 10)
        self.plus = _plano('PREMIUM_PLUS', 'Premium Plus', 20)
        self.aluno = User.objects.create_user(email='ana-conv@example.com', name='Ana Maria Santos',
                                              password='x', role='student')
        self.aluno.preferences = {'area': 'Industry English', 'nivel': 'B1', 'cidade': 'Luanda'}
        self.aluno.save(update_fields=['preferences'])
        self.outro = User.objects.create_user(email='bruno-conv@example.com', name='Bruno Costa',
                                              password='x', role='student')
        self.sub = self.assinar(self.aluno, self.plus)
        self.client = APIClient()
        self.entrar(self.aluno)

    def assinar(self, user, plano, usados=0):
        sub, _ = UserSubscription.objects.update_or_create(user=user, defaults=dict(
            plan=plano, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30),
            daily_speaking_minutes_used=usados, last_reset_date=hoje_luanda(),
        ))
        return sub

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def criar(self, **extra):
        corpo = {'situacao': 'pedir_relatorio', 'nivel': 'B1', 'correcao': 'suave', 'area': 'general', **extra}
        return self.client.post(f'{C}sessoes/', corpo, format='json')

    def recuar_inicio(self, sessao_id, segundos):
        """A chamada ligou há `segundos` e o aluno esteve activo até agora."""
        agora = timezone.now()
        VapiSession.objects.filter(pk=sessao_id).update(
            started_at=agora - timedelta(seconds=segundos), connected_at=agora - timedelta(seconds=segundos),
            last_activity_at=agora)

    def terminar(self, sessao_id, transcricao=None):
        return self.client.post(f'{C}sessoes/{sessao_id}/terminar/', {'transcricao': transcricao or []},
                                format='json')

    def usados(self):
        self.sub.refresh_from_db()
        return self.sub.daily_speaking_minutes_used


class PrepararTests(Base):

    def test_forma_e_preferencias(self):
        r = self.client.get(f'{C}preparar/')
        self.assertEqual(r.status_code, 200)
        d = r.data
        self.assertEqual([s['id'] for s in d['situacoes']],
                         ['pedir_relatorio', 'reuniao_seguranca', 'atender_cliente', 'apresentar_equipa',
                          'conversa_livre'])
        self.assertEqual(d['situacoes'][0]['titulo'], 'Pedir um relatório')
        self.assertEqual(set(d['situacoes'][0]), {'id', 'titulo', 'descricao', 'minutos_sugeridos', 'nivel', 'area',
                                                  'correcao', 'curso'})
        self.assertIsNone(d['situacoes'][0]['curso'])
        self.assertEqual(d['niveis'], ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'])
        self.assertEqual([a['nome'] for a in d['areas']], ['Geral', 'Petróleo e Gás', 'Tecnologia', 'Negócios'])
        self.assertEqual(d['preferencias'], {'nivel': 'B1', 'correcao': 'suave', 'area': 'petroleum'})
        self.assertEqual(d['modo'], 'simulado')
        self.assertIsNone(d['vapi'])
        self.assertEqual(d['quota'], {'plano': 'Premium Plus', 'minutos_dia': 20, 'minutos_usados': 0,
                                      'minutos_restantes': 20, 'max_minutos_sessao': 15,
                                      'pode_comecar': True, 'motivo': None})

    def test_exige_autenticacao(self):
        self.client.credentials()
        self.assertEqual(self.client.get(f'{C}preparar/').status_code, 401)
        self.assertEqual(self.criar().status_code, 401)

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')
    def test_modo_vapi(self):
        d = self.client.get(f'{C}preparar/').data
        self.assertEqual(d['modo'], 'vapi')
        self.assertEqual(d['vapi'], {'public_key': 'pk_test', 'assistant_id': 'asst_1'})


class QuotaTests(Base):

    def test_sem_minutos_403(self):
        self.assinar(self.aluno, self.plus, usados=20)
        r = self.criar()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['codigo'], 'sem_minutos')
        self.assertIn('minutos', r.data['mensagem'])
        self.assertFalse(VapiSession.objects.filter(user=self.aluno).exists())
        q = self.client.get(f'{C}preparar/').data['quota']
        self.assertEqual((q['pode_comecar'], q['motivo'], q['minutos_restantes']), (False, 'sem_minutos', 0))

    def test_plano_sem_minutos_403(self):
        self.premium.daily_speaking_minutes = 0
        self.premium.save()
        self.assinar(self.aluno, self.premium)
        r = self.criar()
        self.assertEqual((r.status_code, r.data['codigo']), (403, 'plano_sem_tutor'))

    def test_teste_expirado_403(self):
        self.free.daily_speaking_minutes = 0
        self.free.save()
        User.objects.filter(pk=self.aluno.pk).update(created_at=timezone.now() - timedelta(days=30))
        self.assinar(self.aluno, self.free)
        r = self.criar()
        self.assertEqual((r.status_code, r.data['codigo']), (403, 'teste_expirado'))

    def test_gratuito_em_teste_pode(self):
        self.assinar(self.aluno, self.free)
        q = self.client.get(f'{C}preparar/').data['quota']
        self.assertEqual((q['plano'], q['minutos_dia'], q['pode_comecar']), ('Gratuito', 5, True))

    def test_premium_tem_10_minutos_apesar_de_ai_tutor_false(self):
        self.assertFalse(self.premium.ai_tutor)
        self.assinar(self.aluno, self.premium)
        q = self.client.get(f'{C}preparar/').data['quota']
        self.assertEqual((q['minutos_dia'], q['max_minutos_sessao'], q['pode_comecar']), (10, 10, True))

    def test_assinatura_paga_expirada_usa_regras_do_gratuito(self):
        self.assinar(self.aluno, self.plus)
        UserSubscription.objects.filter(user=self.aluno).update(expires_at=timezone.now() - timedelta(days=1))
        User.objects.filter(pk=self.aluno.pk).update(created_at=timezone.now() - timedelta(days=30))
        q = self.client.get(f'{C}preparar/').data['quota']
        self.assertEqual((q['plano'], q['minutos_dia']), ('Gratuito', 5))

    def test_max_segundos_limitado_pelo_restante(self):
        self.assinar(self.aluno, self.plus, usados=18)
        r = self.criar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['max_segundos'], 120)

    def test_dados_invalidos_400(self):
        r = self.criar(situacao='nada', nivel='Z9')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['codigo'], 'dados_invalidos')
        self.assertIn('situacao', r.data['campos'])
        self.assertIn('nivel', r.data['campos'])


class CriarTests(Base):

    def test_resposta_e_estado_inicial(self):
        r = self.criar(student_name='Hacker <ignore all>', started_at='2020-01-01')
        self.assertEqual(r.status_code, 201)
        d = r.data
        self.assertEqual(d['situacao'], {'id': 'pedir_relatorio', 'titulo': 'Pedir um relatório'})
        self.assertEqual(d['max_segundos'], 15 * 60)
        self.assertEqual(len(d['frases']), 4)
        self.assertEqual(set(d['frases'][0]), {'en', 'pt'})
        self.assertIn('Ana', d['primeira_fala'])
        self.assertNotIn('Hacker', d['primeira_fala'])
        self.assertIsNone(d['vapi'])
        s = VapiSession.objects.get(pk=d['id'])
        self.assertEqual(s.status, 'em_curso')
        self.assertEqual(s.mode, 'simulado')
        self.assertLess(abs((timezone.now() - s.started_at).total_seconds()), 5)

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')
    def test_modo_vapi_overrides(self):
        d = self.criar(nivel='A2', student_name='Hacker').data
        v = d['vapi']
        self.assertEqual(v['assistant_id'], 'asst_1')
        ov = v['assistant_overrides']
        self.assertEqual(ov['firstMessage'], d['primeira_fala'])
        self.assertEqual(ov['maxDurationSeconds'], d['max_segundos'])
        self.assertEqual(ov['variableValues']['nome'], 'Ana')
        self.assertEqual(ov['variableValues']['nivel'], 'A2')
        self.assertIn('Ana', ov['variableValues']['instrucoes'])
        self.assertNotIn('Hacker', str(ov))

    def test_sessao_aberta_e_fechada_ao_criar_outra(self):
        a = self.criar().data['id']
        self.recuar_inicio(a, 130)
        b = self.criar().data['id']
        antiga = VapiSession.objects.get(pk=a)
        self.assertEqual(antiga.status, 'sem_avaliacao')
        self.assertEqual(antiga.duration_minutes, 3)
        self.assertEqual(self.usados(), 3)
        self.assertEqual(VapiSession.objects.get(pk=b).status, 'em_curso')


class DuracaoTests(Base):

    def test_duracao_do_servidor_limitada_por_max_segundos(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 3600)  # "esqueceu-se" uma hora
        r = self.client.post(f'{C}sessoes/{sid}/terminar/',
                             {'transcricao': [], 'elapsed_seconds': 5, 'segundos': 5}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['segundos'], 15 * 60)
        self.assertEqual(r.data['minutos'], 15)
        self.assertEqual(self.usados(), 15)

    def test_duracao_limitada_pela_quota_restante_ao_terminar(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 600)
        UserSubscription.objects.filter(pk=self.sub.pk).update(daily_speaking_minutes_used=17)  # outra sessão
        r = self.terminar(sid)
        self.assertEqual((r.data['segundos'], r.data['minutos']), (180, 3))
        self.assertEqual(self.usados(), 20)

    def test_cliente_nao_controla_duracao(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 61)
        r = self.client.post(f'{C}sessoes/{sid}/terminar/', {'transcricao': [], 'elapsed_seconds': 7200},
                             format='json')
        self.assertIn(r.data['segundos'], (61, 62))
        self.assertEqual(r.data['minutos'], 2)


class TerminarTests(Base):

    def conversar(self, falas=FALAS_BOAS, situacao='pedir_relatorio'):
        sid = self.criar(situacao=situacao).data['id']
        for f in falas:
            r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': f}, format='json')
            self.assertEqual(r.status_code, 200)
        self.recuar_inicio(sid, 240)
        return sid

    def test_idempotente(self):
        sid = self.conversar()
        r1 = self.terminar(sid)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['estado'], 'avaliada')
        pontos = PointsEntry.objects.filter(user=self.aluno, reason='conversa').count()
        log = DailyStudyLog.objects.get(user=self.aluno, date=timezone.localdate()).conversation_minutes
        usados = self.usados()

        self.recuar_inicio(sid, 900)
        r2 = self.terminar(sid, [{'quem': 'aluno', 'texto': 'something else entirely'}])
        self.assertEqual(r2.status_code, 200)
        sem_inicio = lambda d: {k: v for k, v in d.items() if k != 'iniciada_em'}  # noqa: E731 (movemos started_at)
        self.assertEqual(sem_inicio(r2.data), sem_inicio(r1.data))
        self.assertEqual(VapiSession.objects.get(pk=sid).duration_seconds, r1.data['segundos'])
        self.assertEqual(PointsEntry.objects.filter(user=self.aluno, reason='conversa').count(), pontos)
        self.assertEqual(DailyStudyLog.objects.get(user=self.aluno, date=timezone.localdate()).conversation_minutes,
                         log)
        self.assertEqual(self.usados(), usados)

    def test_avaliacao_simulada_deterministica(self):
        r1 = self.terminar(self.conversar()).data
        r2 = self.terminar(self.conversar()).data
        self.assertEqual(r1['notas'], r2['notas'])
        notas = r1['notas']
        self.assertEqual(set(notas), {'geral', 'fluencia', 'gramatica', 'pronuncia', 'vocabulario'})
        self.assertIsNone(notas['pronuncia'])
        for k in ('fluencia', 'gramatica', 'vocabulario', 'geral'):
            self.assertIsInstance(notas[k], int)
            self.assertTrue(0 <= notas[k] <= 100)
        self.assertEqual(notas['geral'], round((notas['fluencia'] + notas['gramatica'] + notas['vocabulario']) / 3))
        self.assertNotEqual((notas['gramatica'], notas['vocabulario']), (75, 80))
        certos = {c['certo'] for c in r1['correccoes']}
        self.assertIn('on Thursday', certos)
        self.assertIn('It includes', certos)
        self.assertIn('report', r1['palavras_bem_usadas'])
        self.assertTrue(r1['resumo'])
        # a transcrição é a do servidor (tutor + aluno), começando pela primeira fala
        self.assertEqual(r1['transcricao'][0]['quem'], 'tutor')
        self.assertEqual(sum(1 for t in r1['transcricao'] if t['quem'] == 'aluno'), len(FALAS_BOAS))

    def test_mais_erros_menos_gramatica(self):
        boas = self.terminar(self.conversar([
            'Yes, I can send the report on Thursday because the data is ready.',
            'It includes the monthly figures and a short summary for the team.',
            'The final deadline is Friday morning and I will send it by email.',
        ])).data['notas']['gramatica']
        mas = self.terminar(self.conversar([
            'Yes, I can send the report in Thursday because the data is ready.',
            'It include the monthly figures and the informations for the team.',
            'I am agree, the deadline depend of the manager, I didn\'t went there.',
        ])).data['notas']['gramatica']
        self.assertGreater(boas, mas)

    def test_actualiza_quota_registo_pontos_e_estatisticas(self):
        sid = self.conversar()
        r = self.terminar(sid).data
        self.assertEqual(r['minutos'], 4)
        self.assertEqual(self.usados(), 4)
        log = DailyStudyLog.objects.get(user=self.aluno, date=timezone.localdate())
        self.assertAlmostEqual(log.conversation_minutes, 4.0, delta=0.1)
        self.assertEqual(PointsEntry.objects.get(user=self.aluno, reason='conversa').points, 8)
        self.assertEqual(UserProgress.objects.get(user=self.aluno).points, 8)
        # estatísticas do aluno lêem a sessão avaliada
        est = self.client.get('/api/v1/student/practice-courses/estatisticas/', {'periodo': '7'}).data
        self.assertEqual(est['conversacao']['sessoes'], 1)
        self.assertEqual(est['conversacao']['pontuacao_media'], r['notas']['geral'])
        self.assertIsNone(est['conversacao']['criterios']['pronuncia'])

    def test_conversa_curta_sem_avaliacao_mas_conta_minutos(self):
        sid = self.criar().data['id']
        self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Hello there'}, format='json')
        self.recuar_inicio(sid, 90)
        r = self.terminar(sid).data
        self.assertEqual(r['estado'], 'sem_avaliacao')
        self.assertIsNone(r['notas'])
        self.assertEqual(r['correccoes'], [])
        self.assertEqual(r['minutos'], 2)
        self.assertEqual(self.usados(), 2)
        self.assertFalse(PointsEntry.objects.filter(user=self.aluno, reason='conversa').exists())
        est = self.client.get('/api/v1/student/practice-courses/estatisticas/', {'periodo': '7'}).data
        self.assertEqual(est['conversacao']['sessoes'], 1)
        self.assertIsNone(est['conversacao']['pontuacao_media'])

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
                       ANTHROPIC_API_KEY='')
    def test_transcricao_do_cliente_e_validada(self):
        # No modo de voz o servidor não ouve a chamada: usa a transcrição enviada, depois de validada.
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 120)
        lixo = [{'quem': 'admin', 'texto': 'x'}, 'texto', {'quem': 'aluno', 'texto': 5}]
        boas = [{'quem': 'aluno', 'texto': f} for f in FALAS_BOAS]
        with mock.patch('apps.practice.conversa.analise.avaliar_claude', side_effect=RuntimeError('sem rede')):
            r = self.terminar(sid, lixo + boas).data
        self.assertEqual(r['estado'], 'avaliada')
        self.assertEqual(len(r['transcricao']), len(FALAS_BOAS))

    def test_responder_depois_de_terminar_409(self):
        sid = self.criar().data['id']
        self.terminar(sid)
        r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Hello again my friend'}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'conversa_terminada'))


class DonoTests(Base):

    def test_so_o_dono(self):
        sid = self.criar().data['id']
        self.assertEqual(self.client.get(f'{C}sessoes/{sid}/').status_code, 200)
        self.entrar(self.outro)
        for r in (self.client.get(f'{C}sessoes/{sid}/'),
                  self.terminar(sid),
                  self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'hi there'}, format='json'),
                  self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'in Thursday ok'}, format='json')):
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data['codigo'], 'nao_encontrada')
        self.assertEqual(VapiSession.objects.get(pk=sid).status, 'em_curso')

    def test_resumo_em_curso(self):
        sid = self.criar().data['id']
        d = self.client.get(f'{C}sessoes/{sid}/').data
        self.assertEqual(d['estado'], 'em_curso')
        self.assertIsNone(d['notas'])
        self.assertEqual(set(d), {'id', 'situacao', 'iniciada_em', 'minutos', 'minutos_cobrados', 'segundos',
                                  'estado', 'notas', 'transcricao', 'correccoes', 'palavras_bem_usadas', 'resumo',
                                  'objectivos', 'padroes'})

    def test_legado_nao_quebra(self):
        VapiSession.objects.create(session_id='legado-1', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=6, overall_score=70, fluency_score=60, grammar_score=75,
                                   vocabulary_score=80, pronunciation_score=65,
                                   full_session_data={'conversation_history': [{'who': 'student', 'text': 'Hi'}],
                                                      'corrections': [{'original_phrase': 'a', 'corrected_phrase': 'b',
                                                                       'explanation_pt': 'c'}]})
        d = self.client.get(f'{C}sessoes/legado-1/').data
        self.assertEqual(d['estado'], 'avaliada')
        self.assertEqual(d['situacao']['titulo'], 'Conversa com o tutor')
        self.assertEqual(d['transcricao'], [{'quem': 'aluno', 'texto': 'Hi'}])
        self.assertEqual(d['correccoes'], [{'disse': 'a', 'certo': 'b', 'porque': 'c'}])


class AjusteTests(Base):

    def test_regras(self):
        casos = {
            'I will send it in Thursday': ('in Thursday', 'on Thursday'),
            'It include the figures': ('It include', 'It includes'),
            'she have a meeting': ('she have', 'she has'),
            "I didn't went to the site": ("didn't went", "didn't go"),
            'I am agree with you': ('I am agree', 'I agree'),
            'We need more informations': ('informations', 'information'),
            'I work here since 3 years': ('since 3 years', 'for 3 years'),
        }
        for frase, (disse, certo) in casos.items():
            a = regras.primeiro_ajuste(frase)
            self.assertIsNotNone(a, frase)
            self.assertEqual((a['disse'], a['certo']), (disse, certo), frase)
            self.assertTrue(a['porque'])
        for ok in ('I will send it on Thursday', 'It includes the figures', 'I have 5 years of experience',
                   'We were on site'):
            self.assertIsNone(regras.primeiro_ajuste(ok), ok)

    def test_endpoint_simulado(self):
        sid = self.criar().data['id']
        r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I can send it in Thursday'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['ajuste'], {'disse': 'in Thursday', 'certo': 'on Thursday',
                                            'porque': 'Com dias da semana usa-se «on».'})
        r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I can send it on Thursday'}, format='json')
        self.assertEqual(r.data, {'ajuste': None})

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')
    def test_real_falha_devolve_null(self):
        sid = self.criar().data['id']
        with mock.patch('apps.practice.conversa.analise._json', side_effect=TimeoutError('lento')):
            r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I can send it in Thursday'},
                                 format='json')
        self.assertEqual((r.status_code, r.data), (200, {'ajuste': None}))

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')
    def test_real_ok_validado(self):
        sid = self.criar().data['id']
        resposta = {'tem_erro': True, 'disse': 'in Thursday', 'certo': 'on Thursday', 'porque': 'Dias: «on».'}
        with mock.patch('apps.practice.conversa.analise._json', return_value=resposta):
            r = self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'I send it in Thursday'}, format='json')
        self.assertEqual(r.data['ajuste']['certo'], 'on Thursday')

    @override_settings(CONVERSA_LIMITE_AJUSTE='2/min')
    def test_limite(self):
        sid = self.criar().data['id']
        codigos = [self.client.post(f'{C}sessoes/{sid}/ajuste/', {'frase': 'hello my friend'},
                                    format='json').status_code for _ in range(3)]
        self.assertEqual(codigos, [200, 200, 429])


class ResponderTests(Base):

    def test_guiao_por_situacao_e_correccao(self):
        sid = self.criar(situacao='reuniao_seguranca', correcao='directa').data['id']
        r1 = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'There was a leak near the pump'},
                              format='json').data['tutor']
        self.assertEqual(r1, 'Thank you. Where exactly did it happen?')
        r2 = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'It happen in Monday on the rig'},
                              format='json').data['tutor']
        self.assertTrue(r2.startswith('Quick correction: we say "on Monday"'))
        self.assertTrue(r2.endswith('Was anyone injured?'))
        r3 = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Não sei dizer isso'},
                              format='json').data['tutor']
        self.assertIn('in English', r3)

    def test_texto_vazio_400(self):
        sid = self.criar().data['id']
        r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': '   '}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (400, 'texto_vazio'))

    @override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1')
    def test_vapi_escrever_409_sem_claude(self):
        # Na chamada de voz o texto escrito vai pelo Vapi (add-message): responder/ é só do simulado.
        sid = self.criar().data['id']
        with mock.patch('apps.practice.conversa.analise.resposta_claude') as claude:
            r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Can I send it Friday?'}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'so_simulado'))
        claude.assert_not_called()

    def test_tempo_esgotado_409(self):
        sid = self.criar().data['id']
        self.recuar_inicio(sid, 16 * 60)
        r = self.client.post(f'{C}sessoes/{sid}/responder/', {'texto': 'Hello again my friend'}, format='json')
        self.assertEqual((r.status_code, r.data['codigo']), (409, 'tempo_esgotado'))


class ProgressoTests(Base):

    def sessao(self, n, dias_atras, geral, estado='avaliada', minutos=5, correccoes=None, **notas):
        s = VapiSession.objects.create(
            session_id=f'p{n}', user=self.aluno, level='B1', domain='general', duration_minutes=minutos,
            status=estado, situation='pedir_relatorio', overall_score=geral,
            fluency_score=notas.get('f', geral), grammar_score=notas.get('g', geral),
            vocabulary_score=notas.get('v', geral), pronunciation_score=None,
            full_session_data={'versao': 'conversa-1', 'correccoes': correccoes or []},
        )
        quando = timezone.now() - timedelta(days=dias_atras)
        VapiSession.objects.filter(pk=s.pk).update(created_at=quando, date=quando.date(), started_at=quando)

    def test_vazio(self):
        d = self.client.get(f'{C}progresso/').data
        self.assertEqual((d['media'], d['variacao_mes'], d['sessoes'], d['minutos'], d['ultimas']),
                         (None, None, 0, 0, []))
        self.assertEqual([c['chave'] for c in d['por_competencia']],
                         ['fluencia', 'gramatica', 'pronuncia', 'vocabulario'])

    def test_agregacao(self):
        erro = [{'disse': 'in Thursday', 'certo': 'on Thursday', 'porque': '-'}]
        self.sessao(1, 45, 50, g=40, correccoes=erro)          # mês anterior
        self.sessao(2, 40, 60, g=50, correccoes=erro)          # mês anterior
        self.sessao(3, 10, 70, f=80, g=60, v=70, correccoes=erro)
        self.sessao(4, 2, 80, f=90, g=70, v=80)
        self.sessao(5, 1, 0, estado='sem_avaliacao', minutos=1)
        self.sessao(6, 0, 0, estado='em_curso', minutos=0)     # não conta
        VapiSession.objects.create(session_id='outro', user=self.outro, level='B1', domain='general',
                                   duration_minutes=9, overall_score=99)
        d = self.client.get(f'{C}progresso/').data
        self.assertEqual(d['media'], 65)            # (50+60+70+80)/4
        self.assertEqual(d['variacao_mes'], 20)     # 75 - 55
        self.assertEqual(d['sessoes'], 5)
        self.assertEqual(d['minutos'], 21)
        comp = {c['chave']: c for c in d['por_competencia']}
        self.assertEqual(comp['gramatica']['valor'], 55)
        self.assertIn('on Thursday', comp['gramatica']['nota'])
        self.assertIsNone(comp['pronuncia']['valor'])
        self.assertIn('pronúncia', comp['pronuncia']['nota'])
        self.assertTrue(comp['fluencia']['nota'])
        self.assertEqual([u['id'] for u in d['ultimas']], ['p5', 'p4', 'p3', 'p2', 'p1'])
        self.assertIsNone(d['ultimas'][0]['geral'])
        self.assertEqual(d['ultimas'][1], {'id': 'p4', 'titulo': 'Pedir um relatório',
                                           'iniciada_em': d['ultimas'][1]['iniciada_em'], 'minutos': 5,
                                           'geral': 80})

    def test_maximo_10(self):
        for i in range(12):
            self.sessao(i, i, 60)
        self.assertEqual(len(self.client.get(f'{C}progresso/').data['ultimas']), 10)


class LegadoTests(Base):

    def test_rotas_antigas_da_vapi_retiradas(self):
        # O fluxo antigo (sessão, resumo, progresso, painel, assistentes, quota) já não existe:
        # a conversa vive em /practice/conversa/.
        VapiSession.objects.create(session_id='leg-x', user=self.outro, level='B1', domain='general',
                                   duration_minutes=3, overall_score=70)
        self.entrar(self.outro)
        for metodo, url in [
            ('get', '/api/v1/practice/vapi/session/leg-x/summary/'),
            ('post', '/api/v1/practice/vapi/session/'),
            ('get', '/api/v1/practice/vapi/session/'),
            ('get', '/api/v1/practice/vapi/progress/'),
            ('get', '/api/v1/practice/vapi/dashboard/'),
            ('get', '/api/v1/practice/vapi/assistants/'),
            ('get', '/api/v1/practice/vapi/templates/'),
            ('get', '/api/v1/practice/vapi/quota/check/'),
            ('get', '/api/v1/practice/vapi/quota/status/'),
            ('get', '/api/v1/practice/vapi/quota/plans/'),
            ('get', '/api/v1/practice/vapi/test/'),
            ('post', '/api/v1/practice/vapi/simulate/'),
            ('post', '/api/v1/practice/vapi/complete/'),
        ]:
            with self.subTest(url=url, metodo=metodo):
                self.assertEqual(getattr(self.client, metodo)(url, {}, format='json').status_code, 404)


class PalavrasCorrigidasTest(SimpleTestCase):
    def test_palavra_corrigida_nao_conta_como_bem_usada(self):
        from apps.practice.conversa.analise import sem_palavras_corrigidas
        bem = ['send', 'thursday', 'include', 'drilling']
        correccoes = [{'disse': 'in Thursday', 'certo': 'on Thursday', 'porque': ''}, {'disse': 'it include', 'certo': 'it includes', 'porque': ''}]
        self.assertEqual(sem_palavras_corrigidas(bem, correccoes), ['send', 'drilling'])


class ClaudeTest(SimpleTestCase):
    """A camada do Claude, com o cliente simulado (sem rede)."""

    def _resposta(self, texto, stop='end_turn'):
        bloco = mock.Mock(type='text', text=texto)
        return mock.Mock(stop_reason=stop, content=[bloco])

    def _cliente(self, resposta):
        c = mock.Mock()
        c.beta.messages.create.return_value = resposta
        return mock.patch('apps.practice.conversa.analise._cliente', return_value=c), c

    @override_settings(ANTHROPIC_API_KEY='x', CONVERSA_CLAUDE_MODELO='claude-opus-5-5',
                       CONVERSA_CLAUDE_MODELO_AJUSTE='claude-haiku-5-5', CONVERSA_CLAUDE_FALLBACKS=True)
    def test_ajuste_com_erro(self):
        from apps.practice.conversa import analise
        p, c = self._cliente(self._resposta('{"tem_erro": true, "disse": "he don\'t", "certo": "he doesn\'t", "porque": "Com he, usa-se doesn\'t."}'))
        with p:
            a = analise.ajuste_claude("He don't use the harness.")
        self.assertEqual(a['certo'], "he doesn't")
        kw = c.beta.messages.create.call_args.kwargs
        # Haiku: sem recurso no servidor (o parâmetro dá 400 neste modelo)
        self.assertEqual(kw['model'], 'claude-haiku-5-5')
        self.assertNotIn('fallbacks', kw)
        self.assertNotIn('betas', kw)
        self.assertEqual(kw['max_tokens'], 1024)
        self.assertEqual(kw['output_config']['format']['type'], 'json_schema')

    @override_settings(ANTHROPIC_API_KEY='x', CONVERSA_CLAUDE_MODELO='claude-opus-5-5', CONVERSA_CLAUDE_FALLBACKS=True)
    def test_avaliacao_opus_com_fallbacks(self):
        from apps.practice.conversa import analise
        from apps.practice.conversa.situacoes import SITUACOES
        corpo = ('{"fluencia": 70, "gramatica": 60, "vocabulario": 65, "correccoes": [], '
                 '"palavras_bem_usadas": [], "resumo": "Bom."}')
        p, c = self._cliente(self._resposta(corpo))
        t = [{'quem': 'aluno', 'texto': f} for f in FALAS_BOAS]
        with p:
            r = analise.avaliar(t, SITUACOES[0], 'B1', 'general', 120, simulado=False)
        self.assertEqual(r['fonte'], 'claude')
        kw = c.beta.messages.create.call_args.kwargs
        self.assertEqual(kw['model'], 'claude-opus-5-5')
        self.assertEqual(kw['fallbacks'], 'default')
        self.assertEqual(kw['betas'], [analise.BETA_FALLBACK])

    @override_settings(ANTHROPIC_API_KEY='x', CONVERSA_CLAUDE_FALLBACKS=False)
    def test_ajuste_sem_erro_e_recusa(self):
        from apps.practice.conversa import analise
        p, c = self._cliente(self._resposta('{"tem_erro": false, "disse": "", "certo": "", "porque": ""}'))
        with p:
            self.assertIsNone(analise.ajuste_claude('The team checked the valves.'))
        self.assertNotIn('fallbacks', c.beta.messages.create.call_args.kwargs)
        p, _ = self._cliente(self._resposta('', stop='refusal'))
        with p:
            self.assertIsNone(analise.ajuste_claude('x'))

    @override_settings(ANTHROPIC_API_KEY='')
    def test_sem_chave_avaliacao_usa_regras(self):
        from apps.practice.conversa import analise
        from apps.practice.conversa.situacoes import SITUACOES
        situacao = next(iter(SITUACOES.values())) if isinstance(SITUACOES, dict) else SITUACOES[0]
        t = [{'quem': 'tutor', 'texto': 'When can you send it?'}, {'quem': 'aluno', 'texto': 'I will send it in Thursday afternoon with the drilling figures.'},
             {'quem': 'tutor', 'texto': 'Great.'}, {'quem': 'aluno', 'texto': 'It include the safety incidents from last week too.'}]
        r = analise.avaliar(t, situacao, 'B1', 'petroleum', 120, simulado=False)
        self.assertEqual(r['fonte'], 'regras')
