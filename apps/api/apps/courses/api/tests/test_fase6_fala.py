"""
Fase 6: teste de nível falado, exame oral do curso, nova nota do curso, certificado com o nível
de fala, revisão do professor e gravações (só exame + consentimento).

O Claude e o Vapi são sempre simulados aqui (analise._json e exame._vapi substituídos).

    ./venv/bin/python manage.py test apps.courses.api.tests.test_fase6_fala --settings=core.test_settings
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, Course, CourseCertificate, CourseGradingConfig, CourseSection, ExameOral, FraseAula,
    StudentCourseGrade, UserCourseProgress,
)
from apps.courses.services.grade_calculator import GradeCalculatorService
from apps.perfil.models import ItemBanco, PerfilFala
from apps.perfil.servico import registar_item
from apps.practice.conversa import diagnostico, exame
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import VapiSession
from apps.subscriptions.models import UserSubscription

User = get_user_model()
V = '/api/v1/student/video-courses'
C = '/api/v1/practice/conversa/'
PROF = '/api/v1/teacher'
WEBHOOK = '/api/v1/practice/vapi/webhook/'
SEGREDO = 'f6-segredo-proprio-123'
FRASE_1 = 'Could you send me the report by Friday?'
FRASE_2 = 'Please check the pressure before you start the pump.'
GRAVACAO = 'https://storage.vapi.ai/f6-gravacao.wav'

EXAME_BOM = {
    'fluencia': 80, 'gramatica': 70, 'vocabulario': 75, 'tarefa': 85,
    'nivel_cefr': {'falar': 'B1', 'gramatica': 'B1', 'vocabulario': 'B2'},
    'frases_usadas': [FRASE_1],
    'relatorio': 'Cumpriu bem as tarefas. Treine os tempos do passado.',
    'a_treinar': ['Passado simples dos verbos irregulares', 'Ligar ideias com «because»'],
    'correccoes': [], 'padroes': [],
}
EXAME_FRACO = dict(EXAME_BOM, fluencia=50, gramatica=45, vocabulario=55, tarefa=60, frases_usadas=[])
DIAGNOSTICO = {
    'niveis': {'falar': 'B2', 'ouvir': 'B1', 'gramatica': 'B1', 'vocabulario': 'B2'},
    'notas': {'fluencia': 70, 'gramatica': 60, 'vocabulario': 72},
    'explicacoes': {'falar': 'Fala do trabalho com à-vontade.', 'ouvir': 'Percebe perguntas claras.',
                    'gramatica': 'Ainda erra nos tempos do passado.', 'vocabulario': 'Usa termos da sua área.'},
    'resumo': 'Bom nível para reuniões.', 'padroes': [],
}
FALAS_EXAME = [
    ('tutor', 'Hello, welcome to your oral exam. Please introduce yourself.'),
    ('aluno', 'Hello, my name is Ana and I work as an engineer at the refinery in Luanda.'),
    ('tutor', 'Imagine I am your manager. You need a report from the team. What do you ask?'),
    ('aluno', f'{FRASE_1} We need the figures for the safety meeting next week.'),
    ('tutor', 'Fine. And what will you do if the pump has a problem?'),
    ('aluno', 'I will stop the line, call the supervisor and write a short incident report for the team.'),
]


def _transcricao(falas=FALAS_EXAME):
    return [{'quem': q, 'texto': t} for q, t in falas]


def _claude(exame_dados=EXAME_BOM, diag=DIAGNOSTICO):
    def responder(system, user, *a, **k):
        if system == exame.EXAME_SYSTEM:
            return exame_dados
        if system == diagnostico.DIAGNOSTICO_SYSTEM:
            return diag
        raise RuntimeError('sem claude')  # conversas normais: regras
    return responder


@override_settings(CONVERSA_SIMULADA=False, VAPI_PUBLIC_KEY='pk_test', VAPI_ENGLISH_ASSISTANT_ID='asst_1',
                   VAPI_WEBHOOK_SECRET=SEGREDO, VAPI_WEBHOOK_URL='https://api.exemplo.ao/api/v1/practice/vapi/webhook/',
                   CONVERSA_MAX_MINUTOS_SESSAO=15, VAPI_PRIVATE_KEY=None)
class Base(APITestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        from apps.practice.tests.test_conversa import _plano
        self.plano = _plano('PREMIUM_PLUS', 'Premium Plus', 10)
        self.plano.certificates = True
        self.plano.save(update_fields=['certificates'])
        self.prof = User.objects.create_user(email='f6-prof@example.com', name='Prof Paulo', password='x',
                                             role='teacher')
        self.outro_prof = User.objects.create_user(email='f6-outro@example.com', name='Outro', password='x',
                                                   role='teacher')
        self.aluno = User.objects.create_user(email='f6-aluno@example.com', name='Ana Aluna', password='x',
                                              role='student')
        self.aluno.preferences = {'area': 'Industry English', 'nivel': 'A1'}
        self.aluno.save(update_fields=['preferences'])
        self.sub, _ = UserSubscription.objects.update_or_create(user=self.aluno, defaults=dict(
            plan=self.plano, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30),
            daily_speaking_minutes_used=0, last_reset_date=hoje_luanda()))
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='F6- Curso', description='x',
                                           category='Industry English', level='B1', course_type='video',
                                           status='Published', access_level='free')
        self.sec = CourseSection.objects.create(course=self.curso, sectionTitle='S1', order=1)
        self.aula = Chapter.objects.create(section=self.sec, title='Pedir um relatório', content='Pedir com prazo.',
                                           type='Video', order=1, video='https://x.ao/v.mp4')
        for i, (texto, tipo) in enumerate(((FRASE_1, 'frase'), (FRASE_2, 'frase'), ('pressure', 'palavra'))):
            FraseAula.objects.create(chapter=self.aula, texto=texto, traducao='pt', tipo=tipo,
                                     estado=FraseAula.APROVADA, ordem=i)
        matricular_em_curso(self.aluno, self.curso)
        self.entrar(self.aluno)
        for nome, alvo, kw in (
                ('claude', 'apps.practice.conversa.analise._json', {'side_effect': _claude()}),
                ('fundo', 'apps.practice.conversa.webhook.executar_em_fundo', {'side_effect': lambda f, *a: f(*a)}),
                ('vapi', 'apps.practice.conversa.exame._vapi', {'return_value': {}})):
            p = mock.patch(alvo, **kw)
            self.addCleanup(p.stop)
            setattr(self, nome, p.start())

    # -- helpers ------------------------------------------------------------
    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def concluir(self, user=None):
        user = user or self.aluno
        prog = UserCourseProgress.objects.get(user=user, course=self.curso)
        ChapterProgress.objects.filter(user_progress=prog).update(completed=True)
        UserCourseProgress.objects.get(pk=prog.pk).update_overall_progress()

    def ligar(self, sessao_id, segundos=300):
        agora = timezone.now()
        VapiSession.objects.filter(pk=sessao_id).update(
            started_at=agora - timedelta(seconds=segundos), connected_at=agora - timedelta(seconds=segundos),
            last_activity_at=agora)

    def terminar(self, sessao_id, falas=FALAS_EXAME):
        return self.client.post(f'{C}sessoes/{sessao_id}/terminar/', {'transcricao': _transcricao(falas)},
                                format='json')

    def usados(self):
        self.sub.refresh_from_db()
        return self.sub.daily_speaking_minutes_used

    def comecar_exame(self, consentimento=True):
        return self.client.post(f'{V}/{self.curso.id}/exame/', {'consentimento': consentimento}, format='json')

    def fazer_exame(self, consentimento=True, dados=EXAME_BOM):
        self.claude.side_effect = _claude(exame_dados=dados)
        r = self.comecar_exame(consentimento)
        self.assertEqual(r.status_code, 201, r.content)
        sid = r.data['sessao']['id']
        self.ligar(sid)
        t = self.terminar(sid)
        self.assertEqual(t.status_code, 200, t.content)
        return ExameOral.objects.get(pk=r.data['exame_id']), r

    def webhook(self, sessao_id, recording=GRAVACAO):
        msg = {'type': 'end-of-call-report', 'endedReason': 'customer-ended-call', 'call': {'id': 'f6-call'},
               'artifact': {'messages': [{'role': 'bot', 'message': t} if q == 'tutor' else {'role': 'user', 'message': t}
                                         for q, t in FALAS_EXAME]}}
        if recording:
            msg['artifact']['recordingUrl'] = recording
        msg['call']['assistantOverrides'] = {'metadata': {'sessao_id': sessao_id}}
        return self.client.post(WEBHOOK, {'message': msg}, format='json', HTTP_X_VAPI_SECRET=SEGREDO)


# ---------------------------------------------------------------------------
# 1. Teste de nível falado
# ---------------------------------------------------------------------------

class DiagnosticoTests(Base):

    def test_sem_minutos_define_niveis_directos_e_nao_gasta_quota(self):
        PerfilFala.objects.create(user=self.aluno, nivel_falar='A1', nivel_ouvir='A1', nivel_gramatica='A1',
                                  nivel_vocabulario='A1', pontos_falar=0, pontos_ouvir=0, pontos_gramatica=0,
                                  pontos_vocabulario=0)
        self.sub.daily_speaking_minutes_used = 10  # os 10 minutos do dia já foram usados
        self.sub.save(update_fields=['daily_speaking_minutes_used'])
        self.assertEqual(self.client.post(f'{C}sessoes/', {'situacao': 'pedir_relatorio', 'nivel': 'B1',
                                                           'correcao': 'suave', 'area': 'general'},
                                          format='json').status_code, 403)

        r = self.client.post(f'{C}diagnostico/comecar/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        sid = r.data['sessao']['id']
        self.assertEqual(r.data['sessao']['max_segundos'], 240)
        ov = r.data['sessao']['vapi']['assistant_overrides']
        self.assertEqual(ov['artifactPlan'], {'recordingEnabled': False})  # o teste de nível nunca grava
        self.assertIn('placement test', ov['model']['messages'][0]['content'])
        self.ligar(sid, 200)
        self.assertEqual(self.terminar(sid).status_code, 200)

        perfil = PerfilFala.objects.get(user=self.aluno)
        # Colocação directa (A1 -> B2 de uma vez, sem média móvel).
        self.assertEqual(perfil.niveis(), {'falar': 'B2', 'ouvir': 'B1', 'vocabulario': 'B2', 'gramatica': 'B1'})
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.preferences['nivel'], 'B2')
        self.assertEqual(self.usados(), 10)
        s = VapiSession.objects.get(pk=sid)
        self.assertEqual(s.full_session_data['minutos_cobrados'], 0)

        res = self.client.get(f'{C}diagnostico/{sid}/').data
        self.assertEqual(res['nivel'], 'B2')
        self.assertEqual(res['niveis']['ouvir'], 'B1')
        self.assertTrue(res['explicacoes']['gramatica'])

    def test_limite_de_dois_em_30_dias(self):
        agora = timezone.now()
        for i, dias in enumerate((1, 5, 40)):
            s = VapiSession.objects.create(session_id=f'f6-diag-{i}', user=self.aluno, level='A2', domain='general',
                                           duration_minutes=0, situation=diagnostico.SLUG, mode='vapi',
                                           status=VapiSession.STATUS_AVALIADA, connected_at=agora)
            VapiSession.objects.filter(pk=s.pk).update(created_at=agora - timedelta(days=dias))
        e = self.client.get(f'{C}diagnostico/').data
        self.assertFalse(e['disponivel'])
        self.assertEqual(e['feitos_30_dias'], 2)
        self.assertTrue(e['proximo_em'])
        r = self.client.post(f'{C}diagnostico/comecar/', {}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.data['codigo'], 'limite_diagnostico')
        # Um que nunca ligou não conta.
        VapiSession.objects.filter(pk='f6-diag-0').update(connected_at=None)
        self.assertTrue(self.client.get(f'{C}diagnostico/').data['disponivel'])


# ---------------------------------------------------------------------------
# 2. Exame oral
# ---------------------------------------------------------------------------

class ExameTests(Base):

    def test_so_abre_com_80_por_cento(self):
        e = self.client.get(f'{V}/{self.curso.id}/exame/').data
        self.assertFalse(e['disponivel'])
        self.assertEqual(e['motivo'], 'progresso')
        self.assertEqual(e['duracao_minutos'], 10)
        self.assertEqual(e['nota_minima'], 60.0)
        self.assertEqual([f['en'] for f in e['frases']], [FRASE_1, FRASE_2])  # as palavras ficam de fora
        self.assertEqual(self.comecar_exame().status_code, 409)
        self.concluir()
        self.assertTrue(self.client.get(f'{V}/{self.curso.id}/exame/').data['disponivel'])

    def test_outro_aluno_nao_inscrito_nao_ve(self):
        outro = User.objects.create_user(email='f6-outro-aluno@example.com', name='X', password='x', role='student')
        self.entrar(outro)
        self.assertEqual(self.client.get(f'{V}/{self.curso.id}/exame/').status_code, 403)

    def test_com_consentimento_grava_avalia_e_fica_fora_da_quota(self):
        self.concluir()
        self.sub.daily_speaking_minutes_used = 10
        self.sub.save(update_fields=['daily_speaking_minutes_used'])
        ex, r = self.fazer_exame(consentimento=True)
        ov = r.data['sessao']['vapi']['assistant_overrides']
        self.assertEqual(ov['artifactPlan'], {'recordingEnabled': True})
        self.assertEqual(r.data['sessao']['max_segundos'], 600)
        prompt = ov['model']['messages'][0]['content']
        self.assertIn('ORAL EXAM', prompt)
        self.assertIn('do NOT correct mistakes', prompt)
        self.assertIn(FRASE_1, prompt)
        self.assertEqual(self.usados(), 10)

        self.assertEqual(ex.estado, ExameOral.AVALIADO)
        self.assertEqual(ex.notas(), {'fluencia': 80, 'gramatica': 70, 'vocabulario': 75, 'tarefa': 85,
                                      'pronuncia': None})
        self.assertEqual(ex.nota_final, 77.5)
        self.assertTrue(ex.aprovado)
        self.assertEqual(ex.nivel_cefr, 'B1')
        self.assertEqual(ex.frases_usadas, [FRASE_1])
        self.assertIsNone(ex.pode_repetir_em)
        # A frase do curso dita sozinho no exame conta no perfil.
        self.assertEqual(ItemBanco.objects.get(user=self.aluno, texto=FRASE_1).estado, ItemBanco.SOZINHO)

        # O end-of-call-report chega depois: guarda o URL da gravação.
        self.assertEqual(self.webhook(ex.sessao_id).status_code, 200)
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, GRAVACAO)
        d = self.client.get(f'{V}/exames/{ex.pk}/').data
        self.assertEqual(d['gravacao_url'], GRAVACAO)
        self.assertEqual(d['a_treinar'][0], 'Passado simples dos verbos irregulares')

        # Já passou: não há segundo exame.
        e = self.client.get(f'{V}/{self.curso.id}/exame/').data
        self.assertEqual((e['disponivel'], e['motivo']), (False, 'aprovado'))

    def test_sem_consentimento_nao_grava_nem_guarda_url(self):
        self.concluir()
        ex, r = self.fazer_exame(consentimento=False)
        self.assertEqual(r.data['sessao']['vapi']['assistant_overrides']['artifactPlan'], {'recordingEnabled': False})
        self.webhook(ex.sessao_id)
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, '')
        self.assertNotIn('gravacao_url', VapiSession.objects.get(pk=ex.sessao_id).full_session_data)
        self.assertIsNone(self.client.get(f'{V}/exames/{ex.pk}/').data['gravacao_url'])

    def test_conversa_normal_nunca_grava(self):
        r = self.client.post(f'{C}sessoes/', {'situacao': 'pedir_relatorio', 'nivel': 'B1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.data['vapi']['assistant_overrides']['artifactPlan'], {'recordingEnabled': False})
        self.webhook(r.data['id'])
        self.assertNotIn('gravacao_url', VapiSession.objects.get(pk=r.data['id']).full_session_data)

    def test_reprovado_so_repete_7_dias_depois(self):
        self.concluir()
        ex, _ = self.fazer_exame(dados=EXAME_FRACO)
        self.assertFalse(ex.aprovado)
        self.assertEqual(ex.nota_final, 52.5)
        self.assertAlmostEqual((ex.pode_repetir_em - timezone.now()).total_seconds(), 7 * 86400, delta=120)
        e = self.client.get(f'{V}/{self.curso.id}/exame/').data
        self.assertEqual(e['motivo'], 'aguardar')
        self.assertTrue(e['pode_repetir_em'])
        self.assertEqual(self.comecar_exame().status_code, 409)
        ExameOral.objects.filter(pk=ex.pk).update(pode_repetir_em=timezone.now() - timedelta(minutes=1))
        self.assertTrue(self.client.get(f'{V}/{self.curso.id}/exame/').data['disponivel'])

    def test_tentativa_que_nao_ligou_nao_bloqueia(self):
        self.concluir()
        r = self.comecar_exame()
        sid = r.data['sessao']['id']
        self.terminar(sid, [])  # nunca ligou
        self.assertEqual(ExameOral.objects.get(pk=r.data['exame_id']).estado, ExameOral.ANULADO)
        self.assertTrue(self.client.get(f'{V}/{self.curso.id}/exame/').data['disponivel'])

    def test_aluno_apaga_a_gravacao(self):
        self.concluir()
        ex, _ = self.fazer_exame()
        self.webhook(ex.sessao_id)
        VapiSession.objects.filter(pk=ex.sessao_id).update(
            full_session_data={**VapiSession.objects.get(pk=ex.sessao_id).full_session_data, 'vapi_call_id': 'f6-call'})
        r = self.client.delete(f'{V}/exames/{ex.pk}/gravacao/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['gravacao_url'])
        self.assertTrue(r.data['gravacao_apagada'])
        self.vapi.assert_called_with('DELETE', '/call/f6-call')
        # Um novo relatório não a volta a pôr.
        exame.guardar_gravacao_da_sessao(ex.sessao_id, GRAVACAO)
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, '')

    def test_gravacoes_com_mais_de_12_meses_sao_apagadas(self):
        self.concluir()
        ex, _ = self.fazer_exame()
        self.webhook(ex.sessao_id)
        self.assertEqual(exame.apagar_gravacoes_antigas(), 0)
        ExameOral.objects.filter(pk=ex.pk).update(created_at=timezone.now() - timedelta(days=366))
        self.assertEqual(exame.apagar_gravacoes_antigas(), 1)
        ex.refresh_from_db()
        self.assertEqual(ex.gravacao_url, '')


# ---------------------------------------------------------------------------
# 3. Nota do curso e certificado
# ---------------------------------------------------------------------------

class NotaECertificadoTests(Base):

    def criar_exame(self, nota, aprovado, **extra):
        return ExameOral.objects.create(user=self.aluno, course=self.curso, estado=ExameOral.AVALIADO,
                                        nota_fluencia=nota, nota_gramatica=nota, nota_vocabulario=nota,
                                        nota_tarefa=nota, nota_final=nota, aprovado=aprovado, nivel_cefr='B1',
                                        avaliado_em=timezone.now(), **extra)

    def test_pesos_e_renormalizacao(self):
        cfg = CourseGradingConfig.objects.get_or_create(course=self.curso)[0]
        self.assertEqual((cfg.exam_weight, cfg.phrases_weight, cfg.conversation_weight, cfg.study_weight),
                         (40, 25, 20, 15))
        self.criar_exame(80, True)
        registar_item(self.aluno, FRASE_1, estado=ItemBanco.SOZINHO)  # 1 de 2 frases do curso
        g = GradeCalculatorService(self.aluno, self.curso).calculate_and_save()
        # Sem conversas nem estudo no curso: exame 40 e frases 25 renormalizados (61.5 / 38.5).
        self.assertEqual(g.weight_info['exam_weight'], 61.5)
        self.assertEqual(g.weight_info['phrases_weight'], 38.5)
        self.assertEqual(g.weight_info['study_weight'], 0)
        self.assertEqual((g.exam_score, g.phrases_score, g.phrases_total, g.phrases_mastered), (80, 50.0, 2, 1))
        self.assertAlmostEqual(g.final_grade_percentage, 80 * 40 / 65 + 50 * 25 / 65, places=1)

        # Sem frases aprovadas no curso: o componente sai e fica só o exame.
        FraseAula.objects.all().delete()
        g = GradeCalculatorService(self.aluno, self.curso).calculate_and_save()
        self.assertEqual(g.weight_info['exam_weight'], 100.0)
        self.assertEqual(g.final_grade_percentage, 80.0)

    def test_quatro_componentes(self):
        from apps.practice.models import Situacao
        Situacao.objects.create(slug='f6-sit', nome='Reunião', descricao='Reunião de segurança', curso=self.curso,
                                estado=Situacao.ACTIVO)
        VapiSession.objects.create(session_id='f6-conv', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=3, overall_score=70, situation='f6-sit',
                                   status=VapiSession.STATUS_AVALIADA)
        # O exame não conta como conversa do curso.
        VapiSession.objects.create(session_id='f6-exame', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=9, overall_score=10, situation='exame-' + 'a' * 32,
                                   status=VapiSession.STATUS_AVALIADA,
                                   full_session_data={'config': {'curso_id': str(self.curso.id)}})
        self.criar_exame(80, True)
        registar_item(self.aluno, FRASE_1, estado=ItemBanco.SOZINHO)
        registar_item(self.aluno, FRASE_2, estado=ItemBanco.SOZINHO)
        calc = GradeCalculatorService(self.aluno, self.curso)
        quiz = {'score': 90.0, 'count': 2, 'completed': 2, 'passed': 2, 'details': []}
        pratica = {'score': 50.0, 'count': 4, 'completed': 2, 'details': []}
        conv = calc.calculate_conversation_scores()
        self.assertEqual((conv['sessions'], conv['score']), (1, 70))
        final, _, w = calc.calculate_final_grade(quiz, pratica, conv)
        estudo = (90 * 50 + 50 * 30) / 80  # proporção interna quiz:prática = 50:30
        self.assertEqual(w['study_score'], round(estudo, 2))
        self.assertEqual((w['exam_weight'], w['phrases_weight'], w['conversation_weight'], w['study_weight']),
                         (40, 25, 20, 15))
        self.assertAlmostEqual(final, 0.4 * 80 + 0.25 * 100 + 0.2 * 70 + 0.15 * estudo, places=1)

    def test_certificado_exige_exame_e_mostra_nivel_de_fala(self):
        self.concluir()
        registar_item(self.aluno, FRASE_1, estado=ItemBanco.SOZINHO)
        registar_item(self.aluno, FRASE_2, estado=ItemBanco.SOZINHO)
        d = self.client.get(f'{V}/{self.curso.id}/grade/').json()['data']
        self.assertIn('oral_exam', [m['requirement'] for m in d['certificate_eligibility']['missing_requirements']])
        self.assertFalse(CourseCertificate.objects.exists())

        ex, _ = self.fazer_exame()  # aprovado com 77.5 -> nota final elegível -> certificado automático
        cert = CourseCertificate.objects.get(user=self.aluno, course=self.curso)
        self.assertEqual(cert.nivel_fala, 'B1')
        self.assertEqual(cert.area_fala, 'Petróleo e Gás')
        self.assertEqual(cert.notas_fala['exame'], 78)
        self.assertEqual(cert.notas_fala['tarefa'], 85)

        self.client.credentials()
        v = self.client.get(f'/api/v1/certificados/verificar/{cert.certificate_number}/').data
        self.assertEqual(v['nivel_fala_texto'], 'Nível de fala B1 em situações de trabalho de Petróleo e Gás')
        self.assertEqual([n['chave'] for n in v['notas_fala']], ['fluencia', 'gramatica', 'vocabulario', 'tarefa'])
        from apps.courses.certificados import gerar_pdf
        pdf, _ = gerar_pdf(cert)
        self.assertTrue(pdf.startswith(b'%PDF'))


# ---------------------------------------------------------------------------
# 4. Professor
# ---------------------------------------------------------------------------

class ProfessorTests(Base):

    def setUp(self):
        super().setUp()
        self.concluir()
        registar_item(self.aluno, FRASE_1, estado=ItemBanco.SOZINHO)
        registar_item(self.aluno, FRASE_2, estado=ItemBanco.SOZINHO)
        self.exame, _ = self.fazer_exame(dados=EXAME_FRACO)  # 52.5: reprovado pela IA
        self.webhook(self.exame.sessao_id)

    def test_rever_a_nota_ganha_a_ia_e_recalcula(self):
        self.assertFalse(CourseCertificate.objects.exists())
        self.entrar(self.prof)
        r = self.client.post(f'{PROF}/exames/{self.exame.pk}/rever/', {'nota': 72, 'comentario': 'Boa interacção.'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['nota'], r.data['nota_ia'], r.data['aprovado']), (72.0, 52.5, True))
        self.assertEqual(r.data['revisao']['comentario'], 'Boa interacção.')
        g = StudentCourseGrade.objects.get(user=self.aluno, course=self.curso)
        self.assertEqual(g.exam_score, 72.0)
        self.assertTrue(g.exam_passed)
        self.assertTrue(CourseCertificate.objects.filter(user=self.aluno, course=self.curso).exists())

        # Confirmar a nota da IA volta a 52.5 (reprovado).
        r = self.client.post(f'{PROF}/exames/{self.exame.pk}/rever/', {'confirmar': True}, format='json')
        self.assertEqual((r.data['nota'], r.data['aprovado']), (52.5, False))
        self.assertTrue(r.data['pode_repetir_em'])

    def test_validacao_da_nota(self):
        self.entrar(self.prof)
        for nota in (101, -1, 'x', None):
            r = self.client.post(f'{PROF}/exames/{self.exame.pk}/rever/', {'nota': nota}, format='json')
            self.assertEqual(r.status_code, 400, nota)

    def test_professor_de_outro_curso_e_aluno_nao_podem_rever(self):
        self.entrar(self.outro_prof)
        self.assertEqual(self.client.post(f'{PROF}/exames/{self.exame.pk}/rever/', {'nota': 90},
                                          format='json').status_code, 404)
        self.assertEqual(self.client.get(f'{PROF}/alunos/{self.aluno.id}/fala/').status_code, 404)
        self.entrar(self.aluno)
        self.assertEqual(self.client.post(f'{PROF}/exames/{self.exame.pk}/rever/', {'nota': 90},
                                          format='json').status_code, 403)
        self.exame.refresh_from_db()
        self.assertIsNone(self.exame.nota_revista)

    def test_perfil_de_fala_e_exames_do_aluno(self):
        self.entrar(self.prof)
        d = self.client.get(f'{PROF}/alunos/{self.aluno.id}/fala/').data
        self.assertEqual(d['perfil']['frases_sozinho'], 2)
        self.assertIn('falar', d['perfil']['niveis'])
        self.assertEqual(len(d['exames']), 1)
        self.assertEqual(d['exames'][0]['gravacao_url'], GRAVACAO)
        self.assertEqual(d['exames'][0]['aluno']['nome'], 'Ana Aluna')
        self.assertNotIn('transcricao', d['exames'][0])
        lista = self.client.get(f'{PROF}/exames/', {'curso': str(self.curso.id)}).data['exames']
        self.assertEqual([e['id'] for e in lista], [str(self.exame.pk)])
