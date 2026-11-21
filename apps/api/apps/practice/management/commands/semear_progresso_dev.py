"""
Dados de desenvolvimento para as páginas Estatísticas, Certificados e Conquistas e liga
do aluno de teste (aluno@local.test). Só corre com DEBUG ligado. Pode correr várias
vezes: repõe sempre o mesmo estado (aleatório com semente fixa).

O que cria/repõe:
- DailyStudyLog dos últimos 30 dias (minutos variados, 4 dias sem estudo) e UserStreak
- ChallengeAttempt em todos os tipos de exercício, com taxas de acerto diferentes
- PointsEntry (10 pts por resposta certa, 10 por lição) e UserProgress.points = soma
- 5 sessões de conversação com o tutor (VapiSession, nível B1)
- Conquistas (Achievement) e as que o aluno já desbloqueou, com datas
- 8 alunos fictícios (dev.liga.N@local.test) na mesma liga, com pontos da semana à volta
- Curso "[DEV] E-mails profissionais em inglês" concluído, com quiz aprovado e
  certificado emitido (pelo fluxo real: signals / apps.courses.certificados)

ATENÇÃO: apaga as tentativas, registos diários, pontos e sessões de conversação
anteriores do aluno de teste.

    python manage.py semear_progresso_dev
"""
import random
from contextlib import contextmanager
from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, Course, CourseCertificate, CourseSection,
    StudentQuizAttempt, UserCourseProgress,
)
from apps.practice.models import (
    Achievement, AchievementNotification, ChallengeAttempt, ChallengeOption, ChallengeProgress,
    DailyStudyLog, PointsEntry, PracticeChallenge, PracticeLesson, PracticeUnit, UserAchievement,
    UserLeague, UserProgress, UserStreak, VapiSession,
)

ALUNO_EMAIL = 'aluno@local.test'
PROFESSOR_EMAIL = 'professor@local.test'
SEMENTE = 20261113
DIAS = 30
DIAS_SEM_ESTUDO = {6, 19, 20, 27}  # dias atrás -> sequência actual 6, maior 12

# Taxa de acerto por tipo de exercício
ACERTO_POR_TIPO = {
    'SELECT': 0.90, 'ASSIST': 0.85, 'TRUE_FALSE': 0.92, 'MATCH_PAIRS': 0.80,
    'FILL_BLANK': 0.74, 'SENTENCE_ORDER': 0.70, 'TRANSLATION': 0.68,
    'LISTENING': 0.63, 'SPEAKING': 0.55,
}

# (dias atrás, pontuação, duração, resumo)
CONVERSAS = [
    (25, 58, 6, 'Primeira conversa: apresentação no turno. Muitas pausas; reveja o past simple.'),
    (18, 64, 7, 'Relato de um quase-acidente. Vocabulário bom; atenção a "was/were".'),
    (10, 70, 8, 'Toolbox talk simulado. Mais fluente; pronúncia de "hazard" a melhorar.'),
    (3, 76, 9, 'Pedido de autorização de trabalho. Frases completas e claras.'),
    (1, 81, 10, 'Briefing de emergência. Boa fluência e gramática; continue assim.'),
]

# Por conversa (mesma ordem de CONVERSAS): situação, falas do aluno, correcções, palavras bem usadas
CONVERSAS_DETALHE = [
    ('apresentar_equipa',
     ['My name is Aluno and I work as a technician on the platform.',
      'I have 5 years of experience. Before this I work at a refinery.',
      'I am responsible for the maintenance of the pumps.'],
     [('I work at a refinery', 'I worked at a refinery', 'Para o passado usa-se o past simple.'),
      ('I have 5 years', 'I have 5 years of experience', 'Diga «of experience» para a experiência.')],
     ['technician', 'responsible', 'experience']),
    ('reuniao_seguranca',
     ['Yesterday there was a small leak near the wellhead.',
      'The workers was near the valve but nobody was injured.',
      'We stopped the work and we called the supervisor immediately.'],
     [('The workers was', 'The workers were', 'Com plural usa-se «were».')],
     ['leak', 'wellhead', 'injured', 'supervisor', 'immediately']),
    ('reuniao_seguranca',
     ['Today the toolbox talk is about hazards on the deck.',
      'Everybody need to wear the helmet and the gloves.',
      'If you see a hazard, you stop and you report it.'],
     [('Everybody need', 'Everybody needs', 'Com «everybody» o verbo leva -s.')],
     ['hazard', 'helmet', 'gloves', 'report']),
    ('pedir_relatorio',
     ['Good morning, I need the permit to work for the pipeline repair.',
      'The job starts on Thursday and it takes two days.',
      'I will send the risk assessment today in the afternoon.'],
     [('today in the afternoon', 'this afternoon', 'Forma mais natural: «this afternoon».')],
     ['pipeline', 'thursday', 'send']),
    ('conversa_livre',
     ['In an emergency, the first thing is to go to the muster point.',
      'The supervisor counts the people and checks the list.',
      'After that we wait for the instructions of the emergency team.'],
     [],
     ['emergency', 'supervisor', 'instructions']),
]

CONQUISTAS = [
    # título, descrição, ícone, categoria, raridade, pontos, tipo, objectivo, unidade, ordem, secreta
    ('Primeiro passo', 'Conclua o primeiro exercício no laboratório.', '🎯', 'learning', 'common', 10,
     'challenges_completed', 1, 'exercícios', 1, False),
    ('Mão na massa', 'Conclua 25 exercícios.', '🛠️', 'learning', 'common', 25,
     'challenges_completed', 25, 'exercícios', 2, False),
    ('Profissional dedicado', 'Conclua 100 exercícios.', '📚', 'learning', 'rare', 50,
     'challenges_completed', 100, 'exercícios', 3, False),
    ('Primeira lição', 'Conclua uma lição inteira.', '✅', 'milestone', 'common', 10,
     'lessons_completed', 1, 'lições', 4, False),
    ('Dez lições', 'Conclua 10 lições.', '🏅', 'milestone', 'rare', 40,
     'lessons_completed', 10, 'lições', 5, False),
    ('Três dias seguidos', 'Estude três dias seguidos.', '🔥', 'streak', 'common', 15,
     'streak_days', 3, 'dias', 6, False),
    ('Uma semana a fio', 'Estude sete dias seguidos.', '📅', 'streak', 'rare', 30,
     'streak_days', 7, 'dias', 7, False),
    ('Mês de ferro', 'Estude 30 dias seguidos.', '🏆', 'streak', 'epic', 100,
     'streak_days', 30, 'dias', 8, False),
    ('Quinhentos pontos', 'Junte 500 pontos.', '⭐', 'milestone', 'common', 20,
     'points_earned', 500, 'pontos', 9, False),
    ('Três mil pontos', 'Junte 3000 pontos.', '💎', 'milestone', 'legendary', 150,
     'points_earned', 3000, 'pontos', 10, False),
    ('Madrugador', 'Conquista secreta.', '🌅', 'special', 'epic', 30,
     'early_bird', 1, 'vezes', 11, True),
]
# título -> dias atrás em que foi desbloqueada (se o valor real o permitir)
DATAS_DESBLOQUEIO = {
    'Primeiro passo': 29, 'Mão na massa': 24, 'Profissional dedicado': 4, 'Primeira lição': 28,
    'Dez lições': 12, 'Três dias seguidos': 26, 'Uma semana a fio': 14, 'Quinhentos pontos': 17,
}

COLEGAS = [  # nome fictício, diferença de pontos da semana face ao aluno
    ('Ana Exemplo', +140), ('Bruno Fictício', +65), ('Carla Demonstração', +20),
    ('Domingos Teste', +5), ('Eva Simulada', -15), ('Filipe Exemplo', -45),
    ('Graça Fictícia', -90), ('Hugo Teste', -160),
]

CURSO_CONCLUIDO = '[DEV] E-mails profissionais em inglês'


@contextmanager
def sem_auto_now(*campos):
    """Permite gravar datas no passado em campos auto_now_add."""
    guardados = []
    for model, nome in campos:
        f = model._meta.get_field(nome)
        guardados.append((f, f.auto_now_add))
        f.auto_now_add = False
    try:
        yield
    finally:
        for f, valor in guardados:
            f.auto_now_add = valor


class Command(BaseCommand):
    help = 'Dados de progresso [DEV] do aluno de teste (estatísticas, certificados, conquistas e liga).'

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError('Só para desenvolvimento (DEBUG=True).')
        User = get_user_model()
        aluno = User.objects.filter(email=ALUNO_EMAIL).first()
        if not aluno:
            raise CommandError(f'{ALUNO_EMAIL} não existe.')
        professor = (User.objects.filter(email=PROFESSOR_EMAIL).first()
                     or User.objects.filter(role='teacher').order_by('created_at').first())
        if not professor:
            raise CommandError('Crie primeiro um utilizador com papel de professor.')

        self.rng = random.Random(SEMENTE)
        self.agora = timezone.now()
        self.hoje = timezone.localdate()

        with transaction.atomic():
            self._limpar(aluno)
            self._estudo(aluno)
            self._conversas(aluno)
            curso, cert = self._curso_concluido(aluno, professor)
            self._conquistas(aluno)
            total = self._pontos_totais(aluno)
            semana = self._colegas(User, total)

        streak = UserStreak.objects.get(user=aluno)
        self.stdout.write(self.style.SUCCESS('Progresso [DEV] semeado para ' + ALUNO_EMAIL))
        self.stdout.write(f'  dias com estudo: {DailyStudyLog.objects.filter(user=aluno).count()}, '
                          f'sequência {streak.current_streak} (maior {streak.longest_streak}), '
                          f'meta {streak.daily_goal_minutes} min')
        self.stdout.write(f'  tentativas: {ChallengeAttempt.objects.filter(user=aluno).count()}, '
                          f'conversas: {VapiSession.objects.filter(user=aluno).count()}')
        self.stdout.write(f'  pontos totais: {total} (liga {UserLeague.get_league_for_points(total)}), '
                          f'pontos desta semana: {semana}')
        self.stdout.write(f'  conquistas desbloqueadas: '
                          f'{UserAchievement.objects.filter(user=aluno, is_unlocked=True).count()}'
                          f'/{Achievement.objects.filter(is_active=True).count()}')
        self.stdout.write(f'  curso concluído: {curso.title} ({curso.id})')
        if cert:
            self.stdout.write(f'  certificado: {cert.certificate_number} ({cert.id}), nota {cert.final_grade}%')
        else:
            self.stdout.write(self.style.WARNING('  certificado NÃO emitido (ver requisitos em falta)'))

    # ------------------------------------------------------------------ util
    def _momento(self, dias_atras, i=0):
        """Hora plausível (08h-21h) nesse dia, nunca no futuro."""
        dia = self.hoje - timedelta(days=dias_atras)
        ts = timezone.make_aware(datetime.combine(dia, time(hour=self.rng.randint(8, 21),
                                                            minute=self.rng.randint(0, 59))))
        limite = self.agora - timedelta(minutes=3 * (i + 1))
        return min(ts, limite)

    def _limpar(self, aluno):
        ChallengeAttempt.objects.filter(user=aluno).delete()
        DailyStudyLog.objects.filter(user=aluno).delete()
        PointsEntry.objects.filter(user=aluno).delete()
        VapiSession.objects.filter(user=aluno).delete()

    # ------------------------------------------------------------------ estudo
    def _estudo(self, aluno):
        por_tipo = {}
        for t in ACERTO_POR_TIPO:
            ids = list(PracticeChallenge.objects.filter(type=t).order_by('id').values_list('id', flat=True)[:4])
            if ids:
                por_tipo[t] = ids
        if not por_tipo:
            raise CommandError('Não há exercícios (PracticeChallenge). Corra semear_laboratorio_dev primeiro.')
        tipos = sorted(por_tipo)

        meta = UserStreak.objects.get_or_create(user=aluno)[0].daily_goal_minutes
        tentativas, pontos = [], []
        for dias_atras in range(DIAS - 1, -1, -1):
            if dias_atras in DIAS_SEM_ESTUDO:
                continue
            dia = self.hoje - timedelta(days=dias_atras)
            minutos = self.rng.choice([4, 7, 9, 12, 12, 15, 18, 22, 26]) if dias_atras else 16
            licoes = max(1, minutos // 9)
            DailyStudyLog.objects.create(
                user=aluno, date=dia, lesson_minutes=round(minutos * 0.75, 1),
                video_minutes=round(minutos * 0.25, 1), lessons_completed=licoes,
                goal_met_at=self._momento(dias_atras) if minutos >= meta else None,
            )
            for i in range(licoes):
                pontos.append(PointsEntry(user=aluno, points=10, reason='lesson',
                                          created_at=self._momento(dias_atras, i)))
            for i in range(max(3, minutos // 2)):
                t = tipos[(dias_atras + i) % len(tipos)]
                certo = self.rng.random() < ACERTO_POR_TIPO[t]
                ts = self._momento(dias_atras, i)
                tentativas.append(ChallengeAttempt(user=aluno, challenge_id=self.rng.choice(por_tipo[t]),
                                                   is_correct=certo, created_at=ts))
                if certo:
                    pontos.append(PointsEntry(user=aluno, points=10, reason='challenge', created_at=ts))
        with sem_auto_now((ChallengeAttempt, 'created_at'), (PointsEntry, 'created_at')):
            ChallengeAttempt.objects.bulk_create(tentativas)
            PointsEntry.objects.bulk_create(pontos)

        # Sequência a partir dos dias estudados
        estudados = set(DailyStudyLog.objects.filter(user=aluno).values_list('date', flat=True))
        atual, maior, corrida = 0, 0, 0
        for dias_atras in range(DIAS - 1, -1, -1):
            if self.hoje - timedelta(days=dias_atras) in estudados:
                corrida += 1
                maior = max(maior, corrida)
            else:
                corrida = 0
        atual = corrida
        UserStreak.objects.update_or_create(user=aluno, defaults=dict(
            current_streak=atual, longest_streak=maior, last_practice_date=self.hoje,
        ))

    def _conversas(self, aluno):
        from apps.practice.conversa.situacoes import SITUACOES_POR_ID
        with sem_auto_now((VapiSession, 'created_at'), (VapiSession, 'date')):
            for n, (dias_atras, nota, duracao, resumo) in enumerate(CONVERSAS, start=1):
                ts = self._momento(dias_atras)
                sit_id, falas, correccoes, bem = CONVERSAS_DETALHE[n - 1]
                sit = SITUACOES_POR_ID[sit_id]
                transcricao = [{'quem': 'tutor', 'texto': sit['primeira_fala'].format(nome='Aluno')}]
                for i, fala in enumerate(falas):
                    transcricao.append({'quem': 'aluno', 'texto': fala})
                    transcricao.append({'quem': 'tutor', 'texto': sit['guiao'][min(i, len(sit['guiao']) - 1)]
                                        .format(nome='Aluno')})
                notas = {'geral': nota, 'fluencia': nota - 4, 'gramatica': nota + 1, 'pronuncia': None,
                         'vocabulario': nota + 3}
                VapiSession.objects.create(
                    session_id=f'dev-progresso-{n}', user=aluno, level='B1', domain='petroleum',
                    duration_minutes=duracao, duration_seconds=duracao * 60 - 20, max_seconds=15 * 60,
                    status=VapiSession.STATUS_AVALIADA, situation=sit_id, mode='simulado',
                    started_at=ts, ended_at=ts + timedelta(seconds=duracao * 60 - 20),
                    overall_score=nota, fluency_score=notas['fluencia'], pronunciation_score=None,
                    grammar_score=notas['gramatica'], vocabulary_score=notas['vocabulario'],
                    total_words=duracao * 55, words_per_minute=55 + n * 4, corrections_count=len(correccoes),
                    full_session_data={
                        'versao': 'conversa-1', 'dev': True,
                        'config': {'situacao': sit_id, 'nivel': 'B1', 'correcao': 'suave', 'area': 'petroleum'},
                        'transcricao': transcricao, 'historico': transcricao, 'notas': notas,
                        'correccoes': [{'disse': d, 'certo': c, 'porque': p} for d, c, p in correccoes],
                        'palavras_bem_usadas': bem, 'resumo': resumo, 'summary': resumo,
                        'fonte_avaliacao': 'dev',
                    },
                    created_at=ts, date=ts.date(),
                )
                log, _ = DailyStudyLog.objects.get_or_create(user=aluno, date=ts.date())
                log.conversation_minutes += duracao
                log.save(update_fields=['conversation_minutes', 'updated_at'])

    # ------------------------------------------------------------------ certificado
    def _curso_concluido(self, aluno, professor):
        curso, _ = Course.objects.update_or_create(
            title=CURSO_CONCLUIDO, course_type='video',
            defaults=dict(
                teacher=professor, teacherName=professor.name, category='Business English',
                description='Curso curto [DEV]: escrever e responder a e-mails de trabalho em inglês.',
                level='B1', status='Published', template='technology', access_level='premium',
            ),
        )
        seccao, _ = CourseSection.objects.update_or_create(
            course=curso, order=1, defaults=dict(sectionTitle='E-mails do dia-a-dia',
                                                 sectionDescription='Pedidos, respostas e follow-ups.'))
        caps = []
        for ordem, (tipo, titulo, quiz) in enumerate([
            ('Text', 'Abrir e fechar um e-mail', False),
            ('Text', 'Pedir e confirmar informação', False),
            ('Quiz', 'Quiz: e-mails profissionais', True),
        ], start=1):
            cap, _ = Chapter.objects.update_or_create(
                section=seccao, order=ordem,
                defaults=dict(title=titulo, type=tipo, content=f'## {titulo}\n\nConteúdo [DEV].',
                              quiz_enabled=quiz),
            )
            caps.append(cap)
        seccao.chapters.exclude(order__in=[1, 2, 3]).delete()

        unidade, _ = PracticeUnit.objects.update_or_create(
            course=curso, order=1, defaults=dict(title='Quizzes do curso', description='[DEV]'))
        licao, _ = PracticeLesson.objects.update_or_create(
            unit=unidade, order=1, defaults=dict(title='Quiz: e-mails profissionais'))
        perguntas = [
            ('Como se fecha um e-mail formal?', [('Kind regards,', True), ('See ya,', False)]),
            ('"Could you please confirm...?" serve para...', [('pedir confirmação', True), ('agradecer', False)]),
            ('"Please find attached" quer dizer...', [('segue em anexo', True), ('responda já', False)]),
        ]
        if licao.challenges.count() != len(perguntas):
            licao.challenges.all().delete()
            for o, (q, opcoes) in enumerate(perguntas, start=1):
                ch = PracticeChallenge.objects.create(lesson=licao, type='SELECT', question=q, order=o)
                for k, (txt, ok) in enumerate(opcoes, start=1):
                    ChallengeOption.objects.create(challenge=ch, text=txt, is_correct=ok, order=k)
        quiz, _ = ChapterQuiz.objects.update_or_create(
            chapter=caps[2], defaults=dict(
                practice_lesson=licao, title='Quiz: e-mails profissionais', description='[DEV]',
                passing_score=70, max_attempts=3, points_reward=30, hearts_cost=1, is_active=True,
                created_by=professor,
            ),
        )

        cert = CourseCertificate.objects.filter(user=aluno, course=curso).first()
        if cert:  # mantém o número já emitido
            return curso, cert

        _, progresso = matricular_em_curso(aluno, curso)
        for ch in licao.challenges.all():
            ChallengeProgress.objects.update_or_create(user=aluno, challenge=ch, defaults=dict(completed=True))
        if not StudentQuizAttempt.objects.filter(student=aluno, chapter_quiz=quiz, is_passed=True).exists():
            StudentQuizAttempt.objects.create(student=aluno, chapter_quiz=quiz, score=9, max_score=10,
                                              is_completed=True, time_taken=240)
        for cap in caps:
            ChapterProgress.objects.update_or_create(
                user_progress=progresso, chapter=cap,
                defaults=dict(completed=True, completed_at=self.agora - timedelta(days=2), time_spent=8))
        # Progresso a 100% -> signal emite o certificado (nota já elegível pelo quiz).
        UserCourseProgress.objects.get(pk=progresso.pk).update_overall_progress()

        cert = CourseCertificate.objects.filter(user=aluno, course=curso).first()
        if cert:
            self.stdout.write('  certificado emitido automaticamente (signal)')
        else:
            from apps.courses.certificados import CertificadoIndisponivel, emitir_certificado
            try:
                cert, _ = emitir_certificado(aluno, curso)
                self.stdout.write('  certificado emitido por emitir_certificado()')
            except CertificadoIndisponivel as e:
                self.stdout.write(self.style.WARNING(f'  {e.codigo}: {e.detalhes}'))
        if cert:
            CourseCertificate.objects.filter(pk=cert.pk).update(issued_at=self.agora - timedelta(days=2))
            cert.refresh_from_db()
        return curso, cert

    # ------------------------------------------------------------------ conquistas
    def _conquistas(self, aluno):
        from apps.practice.achievement_utils import live_achievement_values

        conquistas = []
        for (titulo, desc, icone, cat, rar, pts, tipo, alvo, unid, ordem, secreta) in CONQUISTAS:
            a, _ = Achievement.objects.update_or_create(title=titulo, defaults=dict(
                description=desc, icon=icone, category=cat, rarity=rar, points=pts,
                requirement_type=tipo, requirement_target=alvo, requirement_unit=unid,
                order=ordem, is_secret=secreta, is_active=True,
            ))
            conquistas.append(a)
        valores = live_achievement_values(aluno, {a.requirement_type for a in conquistas})
        UserAchievement.objects.filter(user=aluno, achievement__in=conquistas).delete()
        AchievementNotification.objects.filter(user=aluno, achievement__in=conquistas).delete()
        PointsEntry.objects.filter(user=aluno, reason='achievement').delete()
        for a in conquistas:
            valor = valores.get(a.requirement_type, 0)
            desbloqueada = valor >= a.requirement_target and a.title in DATAS_DESBLOQUEIO
            quando = self._momento(DATAS_DESBLOQUEIO[a.title]) if desbloqueada else None
            UserAchievement.objects.create(user=aluno, achievement=a, is_unlocked=desbloqueada,
                                           current_progress=min(valor, a.requirement_target),
                                           unlocked_at=quando)
            if desbloqueada:
                AchievementNotification.objects.create(user=aluno, achievement=a, is_read=True,
                                                       is_celebrated=True, read_at=quando)
                with sem_auto_now((PointsEntry, 'created_at')):
                    PointsEntry.objects.create(user=aluno, points=a.points, reason='achievement',
                                               created_at=quando)

    def _pontos_totais(self, aluno):
        from django.db.models import Sum
        total = PointsEntry.objects.filter(user=aluno).aggregate(s=Sum('points'))['s'] or 0
        progresso, _ = UserProgress.objects.get_or_create(user=aluno)
        UserProgress.objects.filter(pk=progresso.pk).update(points=total)
        UserLeague.objects.update_or_create(user=aluno, defaults=dict(
            current_league=UserLeague.get_league_for_points(total)))
        return total

    # ------------------------------------------------------------------ liga
    def _colegas(self, User, total_aluno):
        from django.db.models import Sum
        from apps.practice.liga import limites_semana

        aluno = User.objects.get(email=ALUNO_EMAIL)
        inicio, _ = limites_semana()
        semana = (PointsEntry.objects.filter(user=aluno, created_at__gte=inicio)
                  .aggregate(s=Sum('points'))['s'] or 0)
        info = UserLeague.get_league_info(UserLeague.get_league_for_points(total_aluno))
        minimo = info['min_points']
        maximo = info['max_points'] if info['max_points'] is not None else minimo + 2000
        dias_semana = max(1, (timezone.localtime(self.agora).date() - inicio.date()).days + 1)

        for n, (nome, diferenca) in enumerate(COLEGAS, start=1):
            email = f'dev.liga.{n}@local.test'
            colega = User.objects.filter(email=email).first()
            if not colega:
                colega = User.objects.create_user(email=email, name=nome, password=None, role='student')
                colega.set_unusable_password()
                colega.save(update_fields=['password'])
            elif colega.name != nome:
                colega.name = nome
                colega.save(update_fields=['name'])
            pts_semana = max(0, semana + diferenca)
            total = min(maximo, max(minimo + pts_semana, minimo + self.rng.randint(80, maximo - minimo - 50)))
            progresso, _ = UserProgress.objects.get_or_create(user=colega)
            UserProgress.objects.filter(pk=progresso.pk).update(points=total)
            UserLeague.objects.update_or_create(user=colega, defaults=dict(
                current_league=UserLeague.get_league_for_points(total)))
            UserStreak.objects.update_or_create(user=colega, defaults=dict(
                current_streak=self.rng.randint(0, 9), longest_streak=12, last_practice_date=self.hoje))

            PointsEntry.objects.filter(user=colega).delete()
            entradas, resto = [], pts_semana
            for d in range(dias_semana):
                parte = resto if d == dias_semana - 1 else (pts_semana // dias_semana)
                resto -= parte
                if parte:
                    ts = min(inicio + timedelta(days=d, hours=self.rng.randint(8, 20)),
                             self.agora - timedelta(minutes=10 + n))
                    entradas.append(PointsEntry(user=colega, points=parte, reason='dev', created_at=ts))
            # Algum histórico de semanas anteriores (não conta para esta semana)
            entradas.append(PointsEntry(user=colega, points=self.rng.randint(100, 400), reason='dev',
                                        created_at=inicio - timedelta(days=3)))
            with sem_auto_now((PointsEntry, 'created_at')):
                PointsEntry.objects.bulk_create(entradas)
        return semana
