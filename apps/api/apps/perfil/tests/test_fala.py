"""
Fase 3: minutos a falar por dia (FalaDiaria), meta de fala, frase do painel, palavras difíceis
e as páginas de progresso.

    DATABASE_URL=... ./venv/bin/python manage.py test apps.perfil.tests.test_fala
"""
from datetime import date, datetime, timedelta, timezone as dt_tz
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.perfil import fala
from apps.perfil.models import FalaDiaria, ItemBanco, PadraoErro, PalavraDificil, PerfilFala
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import TentativaPronuncia, VapiSession
from apps.users.models import User

F = '/api/v1/student/fala/'


class Base(TestCase):

    def setUp(self):
        self.aluno = User.objects.create_user(email='f3-aluno@example.com', name='F3 Aluno', password='x', role='student')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.aluno).access_token}')

    def tentativa(self, segundos=10.0, origem='licao', quando=None, **extra):
        dados = dict(user=self.aluno, texto_esperado='Please check the valve.', transcricao='Please check the valve.',
                     aceite=True, segundos_fala=segundos, origem=origem, fonte_tempo='medido', palavras_ditas=4)
        dados.update(extra)
        with self.captureOnCommitCallbacks(execute=True):
            t = TentativaPronuncia.objects.create(**dados)
        if quando is not None:
            TentativaPronuncia.objects.filter(pk=t.pk).update(criada_em=quando)
            t.refresh_from_db()
            fala.recalcular_dia(self.aluno, hoje_luanda())
            fala.recalcular_dia(self.aluno, hoje_luanda(quando))
        return t

    def sessao(self, sid, segundos_aluno, situacao='pedir_relatorio', quando=None, **extra):
        quando = quando or timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            return VapiSession.objects.create(
                session_id=sid, user=self.aluno, level='B1', domain='general', duration_minutes=3,
                status=VapiSession.STATUS_AVALIADA, situation=situacao, connected_at=quando, started_at=quando,
                segundos_aluno=segundos_aluno, fonte_tempo='medido', **extra)


class FalaDiariaTests(Base):

    def test_soma_fontes_e_e_idempotente(self):
        self.tentativa(12.5)
        self.tentativa(7.5, origem='responder')
        self.tentativa(5, origem='revisao')
        self.sessao('F3-s1', 100)
        self.sessao('F3-s2', 50, situacao='exame-abc')
        hoje = hoje_luanda()
        reg = FalaDiaria.objects.get(user=self.aluno, dia=hoje)
        self.assertEqual(reg.segundos, 175.0)
        self.assertEqual(reg.fontes, {'licao': 12.5, 'responder': 7.5, 'revisao': 5.0, 'conversa': 100.0, 'exame': 50.0})
        fala.recalcular_dia(self.aluno, hoje)
        fala.recalcular_dia(self.aluno, hoje)
        self.assertEqual(FalaDiaria.objects.filter(user=self.aluno).count(), 1)
        self.assertEqual(FalaDiaria.objects.get(user=self.aluno).segundos, 175.0)

    def test_sem_tempo_nao_conta_e_sessao_nao_ligada_fica_fora(self):
        self.tentativa(None)
        VapiSession.objects.create(session_id='F3-s4', user=self.aluno, level='B1', domain='general', duration_minutes=0,
                                   status=VapiSession.STATUS_NAO_LIGOU, segundos_aluno=30, started_at=timezone.now())
        self.assertIsNone(fala.recalcular_dia(self.aluno, hoje_luanda()))
        self.assertFalse(FalaDiaria.objects.exists())

    def test_dia_de_luanda(self):
        # 23:30 UTC de 3 de Março = 00:30 de 4 de Março em Luanda (UTC+1).
        quando = datetime(2026, 3, 3, 23, 30, tzinfo=dt_tz.utc)
        self.tentativa(20, quando=quando)
        self.sessao('F3-s5', 40, quando=datetime(2026, 3, 3, 22, 30, tzinfo=dt_tz.utc))  # 23:30 do dia 3
        fala.recalcular_dia(self.aluno, date(2026, 3, 4))
        fala.recalcular_dia(self.aluno, date(2026, 3, 3))
        self.assertEqual(FalaDiaria.objects.get(dia=date(2026, 3, 4)).fontes, {'licao': 20.0})
        self.assertEqual(FalaDiaria.objects.get(dia=date(2026, 3, 3)).fontes, {'conversa': 40.0})


class MetaFalaTests(Base):

    def test_omissao_e_validacao(self):
        r = self.client.get(F + 'meta/')
        self.assertEqual(r.json(), {'meta_fala_min': 5, 'opcoes': [3, 5, 10, 15]})
        for mau in (4, 0, 20, 'x', None, True, 5.5):
            r = self.client.patch(F + 'meta/', {'meta_fala_min': mau}, format='json')
            self.assertEqual(r.status_code, 400, mau)
            self.assertEqual(r.json()['codigo'], 'meta_invalida')
        r = self.client.patch(F + 'meta/', {'meta_fala_min': 10}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PerfilFala.objects.get(user=self.aluno).meta_fala_min, 10)
        r = self.client.patch(F + 'meta/', {'meta_fala_min': '15'}, format='json')
        self.assertEqual(r.json()['meta_fala_min'], 15)

    def test_so_alunos(self):
        prof = User.objects.create_user(email='f3-prof@example.com', name='F3 Prof', password='x', role='teacher')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(prof).access_token}')
        self.assertEqual(self.client.get(F + 'resumo/').status_code, 403)


class FraseResumoTests(TestCase):

    def test_formas(self):
        self.assertEqual(fala.frase_resumo(0, 0), 'Ainda não falou esta semana. Comece por 5 minutos com o tutor.')
        self.assertEqual(fala.frase_resumo(0, 3, 'X', meta_min=10),
                         'Ainda não falou esta semana. Comece por 10 minutos com o tutor.')
        self.assertEqual(fala.frase_resumo(38 * 60 + 10, 6, 'Troca "in" por "on" nos dias da semana.'),
                         'Nos últimos 7 dias falou 38 minutos e disse sozinho 6 frases numa conversa. '
                         'Erro que ainda repete: Troca "in" por "on" nos dias da semana.')
        self.assertEqual(fala.frase_resumo(30, 1), 'Nos últimos 7 dias falou menos de 1 minuto e disse sozinho 1 frase numa conversa.')
        self.assertEqual(fala.frase_resumo(65, 0), 'Nos últimos 7 dias falou 1 minuto.')
        self.assertEqual(fala.frase_resumo(3900, 0), 'Nos últimos 7 dias falou 1 h 05 min.')


class ResumoPainelTests(Base):

    def test_aluno_novo(self):
        d = self.client.get(F + 'resumo/').json()
        self.assertEqual(d['frase'], 'Ainda não falou esta semana. Comece por 5 minutos com o tutor.')
        self.assertEqual(d['hoje'], {'segundos': 0, 'meta_min': 5, 'cumprida': False, 'percentagem': 0})
        self.assertEqual(len(d['semana']['dias']), 7)
        self.assertTrue(d['semana']['dias'][-1]['hoje'])
        self.assertIsNone(d['padrao'])

    def test_com_dados(self):
        self.tentativa(200)
        self.sessao('F3-s6', 160)
        FalaDiaria.objects.create(user=self.aluno, dia=hoje_luanda() - timedelta(days=3), segundos=600)
        FalaDiaria.objects.create(user=self.aluno, dia=hoje_luanda() - timedelta(days=9), segundos=999)  # fora
        ItemBanco.objects.create(user=self.aluno, texto='Could you send me the report?', chave='could you send me the report',
                                 estado=ItemBanco.SOZINHO, ultima_vez_sozinho=timezone.now())
        PadraoErro.objects.create(user=self.aluno, chave='on_days', descricao='Com dias da semana usa-se "on".',
                                  ocorrencias=3)
        d = self.client.get(F + 'resumo/').json()
        self.assertEqual(d['semana']['segundos'], 960)
        self.assertEqual(d['hoje']['segundos'], 360)
        self.assertTrue(d['hoje']['cumprida'])
        self.assertEqual(d['hoje']['percentagem'], 100)
        self.assertEqual(d['semana']['dias'][3]['segundos'], 600)
        self.assertEqual(d['frase'], 'Nos últimos 7 dias falou 16 minutos e disse sozinho 1 frase numa conversa. '
                                     'Erro que ainda repete: Com dias da semana usa-se "on".')


class PalavrasDificeisTests(Base):

    def test_texto_cria_conta_e_entra_no_banco(self):
        self.tentativa(3, texto_esperado='Please check the valve pressure.', palavras_problematicas=['valve', 'the valve', 42])
        p = PalavraDificil.objects.get(user=self.aluno)
        self.assertEqual((p.palavra, p.tentativas, p.falhas), ('valve', 1, 1))
        self.assertFalse(PalavraDificil.objects.filter(palavra='please').exists())  # só as que falharam criam linha
        self.assertFalse(ItemBanco.objects.filter(user=self.aluno, chave='valve').exists())
        self.tentativa(3, texto_esperado='The valve is open.', palavras_problematicas=['Valve.'])
        p.refresh_from_db()
        self.assertEqual((p.tentativas, p.falhas), (2, 2))
        item = ItemBanco.objects.get(user=self.aluno, chave='valve')
        self.assertEqual((item.tipo, item.origem), ('palavra', 'pronuncia'))
        # três gravações seguidas bem ditas: sai da lista
        for _ in range(3):
            self.tentativa(3, texto_esperado='Check the valve.', palavras_problematicas=[])
        p.refresh_from_db()
        self.assertEqual((p.tentativas, p.acertos_seguidos), (5, 3))
        self.assertEqual(fala.palavras_a_treinar(self.aluno), [])

    def test_avaliacao_detalhada(self):
        detalhe = [{'palavra': 'the', 'nota': 41, 'erro_tipo': 'Mispronunciation',
                    'fonemas': [{'fonema': 'ð', 'nota': 20}, {'fonema': 'ə', 'nota': 70}]},
                   {'palavra': 'valve', 'nota': 90, 'erro_tipo': 'None', 'fonemas': []}]
        self.tentativa(3, palavras_detalhe=detalhe, avaliacao='azure')
        self.tentativa(3, palavras_detalhe=[dict(detalhe[0], nota=61, erro_tipo='None')], avaliacao='azure')
        p = PalavraDificil.objects.get(user=self.aluno, palavra='the')
        self.assertEqual((p.tentativas, p.falhas, p.media, p.fonema, p.acertos_seguidos), (2, 1, 51.0, 'ð', 1))
        self.assertFalse(PalavraDificil.objects.filter(palavra='valve').exists())
        lista = fala.palavras_a_treinar(self.aluno)
        self.assertEqual(lista[0]['palavra'], 'the')
        self.assertEqual(lista[0]['fonema'], 'ð')

    def test_responder_nao_conta_as_palavras_da_frase_alvo(self):
        PalavraDificil.objects.create(user=self.aluno, palavra='ready', tentativas=1, falhas=1)
        self.tentativa(5, origem='responder', texto_esperado="I'll have it ready by...", palavras_problematicas=[])
        self.assertEqual(PalavraDificil.objects.get(palavra='ready').tentativas, 1)

    def test_falha_nao_parte_a_gravacao(self):
        with mock.patch('apps.perfil.fala.registar_palavras', side_effect=RuntimeError('x')):
            self.tentativa(3, palavras_problematicas=['valve'])
        self.assertTrue(FalaDiaria.objects.filter(user=self.aluno).exists())


class ProgressoTests(Base):

    def test_semanas_e_tendencias(self):
        agora = timezone.now()
        self.tentativa(30, origem='responder', ppm=100, palavras_ditas=12, pausas_longas=2)
        self.tentativa(30, ppm=120, palavras_ditas=6, pausas_longas=0)
        self.tentativa(10, ppm=None, palavras_ditas=3, fonte_tempo='estimado', pausas_longas=None)
        self.sessao('F3-s7', 120, ppm_aluno=90, palavras_por_turno=8)
        self.tentativa(20, ppm=60, quando=agora - timedelta(weeks=3))
        d = self.client.get(F + 'progresso/').json()
        self.assertEqual(len(d['semanas']), 8)
        actual = d['semanas'][-1]
        self.assertTrue(actual['actual'])
        self.assertEqual(actual['segundos'], 190)
        self.assertEqual(actual['ppm'], 100.0)                   # mediana de 100, 120, 90
        self.assertEqual(actual['palavras_por_resposta'], 10.0)  # Responder 12 e conversa 8
        self.assertEqual(actual['pausas_por_minuto'], 2.0)       # 2 pausas em 60 s medidos
        self.assertEqual(d['meta_min'], 5)
        self.assertIn('avaliacao_detalhada', d)
        vazias = [s for s in d['semanas'] if not s['segundos']]
        self.assertTrue(all(s['ppm'] is None for s in vazias))

    def test_professor_ve_o_aluno(self):
        from apps.courses.models import Course, CourseEnrollment
        prof = User.objects.create_user(email='f3-prof2@example.com', name='F3 Prof', password='x', role='teacher')
        curso = Course.objects.create(teacher=prof, teacherName='F3 Prof', title='F3 Curso', description='-',
                                      course_type='practice', status='Published')
        CourseEnrollment.objects.create(user=self.aluno, course=curso)
        self.tentativa(30, ppm=100)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(prof).access_token}')
        r = self.client.get(f'/api/v1/teacher/alunos/{self.aluno.id}/fala/')
        self.assertEqual(r.status_code, 200, r.content)
        f = r.json()['fala']
        self.assertEqual(f['semanas'][-1]['segundos'], 30)
        self.assertEqual(f['semanas'][-1]['ppm'], 100.0)
        self.assertEqual(f['meta_min'], 5)
