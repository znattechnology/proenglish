"""
Estatísticas por período, liga semanal, privacidade do leaderboard e conquistas.

    ./venv/bin/python manage.py test apps.courses.api.tests.test_estatisticas_liga --settings=core.test_settings
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice.liga import limites_semana, nome_publico
from apps.practice.models import (
    Achievement, ChallengeAttempt, ChallengeProgress, DailyStudyLog, PointsEntry, PracticeChallenge,
    PracticeLesson, PracticeUnit, UserAchievement, UserProgress, UserStreak, VapiSession,
)

User = get_user_model()
P = '/api/v1/student/practice-courses/'


class Base(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-est@example.com', name='Professor Silva', password='x',
                                             role='teacher')
        self.aluno = User.objects.create_user(email='ana-est@example.com', name='Ana Maria Santos',
                                              password='x', role='student')
        self.outro = User.objects.create_user(email='bruno-est@example.com', name='Bruno Costa', password='x',
                                              role='student')
        curso = Course.objects.create(teacher=self.prof, teacherName='P', title='Lab', description='d',
                                      course_type='practice', status='Published')
        unidade = PracticeUnit.objects.create(course=curso, title='U', description='', order=1)
        self.licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        self.select = PracticeChallenge.objects.create(lesson=self.licao, type='SELECT', question='q1', order=1)
        self.listening = PracticeChallenge.objects.create(lesson=self.licao, type='LISTENING', question='q2',
                                                          order=2)
        self.hoje = timezone.localdate()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.aluno).access_token}')

    def tentativa(self, user, ch, certo, dias_atras=0):
        a = ChallengeAttempt.objects.create(user=user, challenge=ch, is_correct=certo)
        ChallengeAttempt.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))

    def log(self, user, dias_atras, minutos, licoes=0, conv=0):
        DailyStudyLog.objects.create(user=user, date=self.hoje - timedelta(days=dias_atras),
                                     lesson_minutes=minutos, conversation_minutes=conv,
                                     lessons_completed=licoes)


class EstatisticasTests(Base):

    def setUp(self):
        super().setUp()
        UserStreak.objects.create(user=self.aluno, current_streak=2, longest_streak=9,
                                  last_practice_date=self.hoje, daily_goal_minutes=10)
        self.log(self.aluno, 0, 10, licoes=2)
        self.log(self.aluno, 3, 5)
        self.log(self.aluno, 9, 20, licoes=3)  # período anterior (7 dias)
        self.log(self.outro, 0, 50, licoes=9)  # outro aluno: nunca conta
        self.tentativa(self.aluno, self.select, True)
        self.tentativa(self.aluno, self.select, True)
        self.tentativa(self.aluno, self.select, False)
        self.tentativa(self.aluno, self.listening, False, dias_atras=1)
        self.tentativa(self.aluno, self.listening, True, dias_atras=10)  # fora dos 7 dias
        self.tentativa(self.outro, self.select, False)
        VapiSession.objects.create(session_id='s1', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=8, overall_score=70, fluency_score=60,
                                   full_session_data={'summary': 'Boa conversa.'})

    def get(self, periodo):
        return self.client.get(f'{P}estatisticas/', {'periodo': periodo})

    def test_7_dias(self):
        r = self.get('7')
        self.assertEqual(r.status_code, 200)
        d = r.data
        self.assertEqual((d['dias'], d['fim'], d['meta_diaria_minutos']), (7, self.hoje.isoformat(), 10))
        self.assertEqual(d['tempo_estudo']['minutos'], 15)
        self.assertEqual(d['tempo_estudo']['periodo_anterior'], 20)
        self.assertEqual(d['licoes_concluidas'], {'total': 2, 'periodo_anterior': 3, 'variacao': -1,
                                                  'variacao_pct': -33})
        self.assertEqual(d['sequencia'], {'atual': 2, 'maior': 9, 'estudou_hoje': True})
        self.assertEqual(d['respostas'], {'certas': 2, 'total': 4, 'percentagem': 50})
        self.assertEqual(len(d['minutos_por_dia']), 7)
        self.assertEqual(d['minutos_por_dia'][-1], {'data': self.hoje.isoformat(),
                                                    'dia_semana': d['minutos_por_dia'][-1]['dia_semana'],
                                                    'minutos': 10, 'meta_cumprida': True})
        tipos = {t['tipo']: t for t in d['por_tipo_exercicio']}
        self.assertEqual(tipos['SELECT']['percentagem'], 67)
        self.assertEqual(tipos['SELECT']['rotulo'], 'Escolha múltipla')
        self.assertEqual((tipos['LISTENING']['certas'], tipos['LISTENING']['total']), (0, 1))
        conv = d['conversacao']
        # Minutos da conversação vêm só do DailyStudyLog (aqui sem minutos de conversa).
        self.assertEqual((conv['sessoes'], conv['minutos'], conv['pontuacao_media']), (1, 0, 70))
        self.assertEqual(conv['minutos'], d['tempo_estudo']['por_tipo']['conversacao'])
        self.assertEqual(conv['ultima_sessao']['resumo'], 'Boa conversa.')

    def test_30_dias_e_tudo(self):
        r = self.get('30')
        self.assertEqual(r.data['dias'], 30)
        self.assertEqual(r.data['respostas']['total'], 5)
        self.assertEqual(r.data['licoes_concluidas']['total'], 5)
        r = self.get('tudo')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['inicio'], (self.hoje - timedelta(days=10)).isoformat())
        self.assertIsNone(r.data['licoes_concluidas']['periodo_anterior'])
        self.assertEqual(r.data['tempo_estudo']['minutos'], 35)
        self.assertEqual(len(r.data['minutos_por_dia']), 11)

    def test_periodo_invalido_e_padrao(self):
        self.assertEqual(self.get('90').status_code, 400)
        self.assertEqual(self.client.get(f'{P}estatisticas/').data['periodo'], '7')

    def test_sem_dados(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.prof).access_token}')
        d = self.get('tudo').data
        self.assertEqual(d['dias'], 1)
        self.assertIsNone(d['respostas']['percentagem'])
        self.assertIsNone(d['conversacao']['ultima_sessao'])


class LigaSemanalTests(Base):

    def setUp(self):
        super().setUp()
        self.carla = User.objects.create_user(email='carla-est@example.com', name='Carla', password='x',
                                              role='student')
        self.rica = User.objects.create_user(email='rica-est@example.com', name='Rica Prata', password='x',
                                             role='student')
        for u, total in [(self.aluno, 400), (self.outro, 300), (self.carla, 900), (self.rica, 1500),
                         (self.prof, 100)]:
            UserProgress.objects.create(user=u, points=total)
        inicio, _ = limites_semana()
        for u, pts in [(self.aluno, 50), (self.outro, 80), (self.carla, 20), (self.rica, 999), (self.prof, 500)]:
            PointsEntry.objects.create(user=u, points=pts)
        antiga = PointsEntry.objects.create(user=self.carla, points=1000)  # semana passada
        PointsEntry.objects.filter(pk=antiga.pk).update(created_at=inicio - timedelta(minutes=1))

    def test_ranking_da_minha_liga(self):
        r = self.client.get(f'{P}liga/semana/')
        self.assertEqual(r.status_code, 200)
        d = r.data
        self.assertEqual(d['liga']['id'], 'bronze')
        self.assertEqual(d['participantes'], 3)  # sem o professor nem a aluna da Liga Prata
        self.assertEqual([(x['posicao'], x['nome'], x['pontos_semana'], x['sou_eu']) for x in d['ranking']],
                         [(1, 'Bruno C.', 80, False), (2, 'Ana S.', 50, True), (3, 'Carla', 20, False)])
        self.assertEqual(d['eu']['posicao'], 2)
        self.assertEqual(d['eu']['pontos_para_lugar_acima'], 31)
        self.assertEqual(d['regra_promocao']['proxima_liga']['id'], 'silver')
        self.assertEqual(d['regra_promocao']['pontos_em_falta'], 600)
        self.assertEqual(d['semana']['fuso_horario'], 'Africa/Luanda')
        corpo = r.content.decode()
        for proibido in ['@example.com', 'Ana Maria Santos', 'Bruno Costa', str(self.outro.id)]:
            self.assertNotIn(proibido, corpo)

    def test_add_points_regista_movimento(self):
        prog = UserProgress.objects.get(user=self.aluno)
        prog.add_points(10, check_achievements=False, reason='challenge')
        self.assertTrue(PointsEntry.objects.filter(user=self.aluno, points=10, reason='challenge').exists())

    def test_limites_semana_hora_de_angola(self):
        # Domingo 23:30 UTC = segunda 00:30 em Luanda -> já é a nova semana
        inicio, fim = limites_semana(datetime(2026, 11, 15, 23, 30, tzinfo=dt_timezone.utc))
        self.assertEqual(inicio.isoformat(), '2026-11-16T00:00:00+01:00')
        self.assertEqual(fim - inicio, timedelta(days=7))

    def test_nome_publico(self):
        self.assertEqual(nome_publico('ana maria santos'), 'ana S.')
        self.assertEqual(nome_publico('Carla'), 'Carla')
        self.assertEqual(nome_publico(''), 'Aluno')


class LeaderboardPrivacidadeTests(Base):

    def test_global_sem_emails_ids_nem_nomes_completos(self):
        UserProgress.objects.create(user=self.aluno, points=10)
        UserProgress.objects.create(user=self.outro, points=20)
        UserProgress.objects.create(user=self.prof, points=30)
        r = self.client.get(f'{P}leaderboard/global/')
        self.assertEqual(r.status_code, 200)
        nomes = [e['username'] for e in r.data['leaderboard']]
        self.assertEqual(nomes, ['Bruno C.', 'Ana S.'])  # só alunos
        corpo = r.content.decode()
        for proibido in ['@example.com', 'Bruno Costa', 'Ana Maria Santos', str(self.outro.id)]:
            self.assertNotIn(proibido, corpo)


class ConquistasTests(Base):

    def setUp(self):
        super().setUp()
        mk = lambda titulo, tipo, alvo, **kw: Achievement.objects.create(
            title=titulo, description='d', icon='*', category='learning', points=5,
            requirement_type=tipo, requirement_target=alvo, **kw)
        self.um = mk('Um exercício', 'challenges_completed', 1, order=1)
        self.dez = mk('Dez exercícios', 'challenges_completed', 10, order=2)
        self.secreta = mk('Secreta', 'early_bird', 1, is_secret=True, order=3)
        ChallengeProgress.objects.bulk_create([  # bulk: sem signals, como dados antigos
            ChallengeProgress(user=self.aluno, challenge=self.select, completed=True),
            ChallengeProgress(user=self.aluno, challenge=self.listening, completed=True),
        ])

    def test_lista_com_progresso_real_e_desbloqueio(self):
        r = self.client.get(f'{P}achievements/')
        self.assertEqual(r.status_code, 200)
        por_titulo = {a['title']: a for a in r.data}
        self.assertNotIn('Secreta', por_titulo)
        um = por_titulo['Um exercício']
        self.assertTrue(um['isUnlocked'])  # atingido mas nunca verificado -> desbloqueado agora
        self.assertIsNotNone(um['unlockedAtIso'])
        self.assertEqual(um['unlockedAt'], 'hoje')
        dez = por_titulo['Dez exercícios']
        self.assertFalse(dez['isUnlocked'])
        self.assertEqual(dez['progress'], {'current': 2, 'target': 10, 'unit': 'items', 'percentage': 20})

    def test_secreta_aparece_depois_de_desbloqueada(self):
        UserAchievement.objects.create(user=self.aluno, achievement=self.secreta, is_unlocked=True,
                                       unlocked_at=timezone.now() - timedelta(days=8), current_progress=1)
        r = self.client.get(f'{P}achievements/')
        sec = next(a for a in r.data if a['title'] == 'Secreta')
        self.assertTrue(sec['isSecret'])
        self.assertEqual(sec['unlockedAt'], 'há 1 semana')


class VapiSessionTests(Base):

    def test_melhoria_e_sequencia_calculadas_na_criacao(self):
        VapiSession.objects.create(session_id='a', user=self.aluno, level='B1', domain='g',
                                   duration_minutes=5, overall_score=60)
        s2 = VapiSession.objects.create(session_id='b', user=self.aluno, level='B1', domain='g',
                                        duration_minutes=5, overall_score=72)
        self.assertEqual(s2.improvement_from_last, 12)
        self.assertEqual(s2.streak_days, 1)  # segunda sessão no mesmo dia não aumenta a sequência
