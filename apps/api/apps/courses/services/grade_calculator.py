"""
Grade Calculator Service

This service handles all grade calculations for video courses:
- Quiz score aggregation from StudentQuizAttempt
- Practice score calculation from ChallengeProgress (via Chapter/ChapterQuiz -> PracticeLesson)
- Conversation score aggregation from VapiSession (only conversations tied to the course)
- Final grade calculation with configurable weights
- Certificate eligibility determination
- Dynamic weight adjustment when components don't exist
"""

from typing import Optional, Dict, List, Tuple
from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone

from apps.courses.ciclo import q_aula_visivel
from apps.courses.models import (
    Course, CourseSection, Chapter, ChapterQuiz, StudentQuizAttempt,
    StudentCourseGrade, CourseGradingConfig, GradeHistory
)
from apps.practice.models import ChallengeProgress, VapiSession, PracticeLesson
from apps.users.models import User


# Course.level já está em CEFR (A1..C2): o nível do curso é o nível das sessões do tutor.
COURSE_LEVEL_TO_CEFR = {c: [c] for c in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')}


def curso_tem_conversa(course) -> bool:
    """O curso tem pelo menos uma situação de conversa activa (practice.Situacao.curso)."""
    from apps.practice.models import Situacao
    return Situacao.objects.filter(curso=course, estado=Situacao.ACTIVO).exists()


def sessoes_de_conversa_do_curso(user, course):
    """Conversas avaliadas do aluno que contam para este curso (o exame oral conta à parte)."""
    from apps.practice.models import Situacao
    slugs = Situacao.objects.filter(curso=course).values('slug')
    return VapiSession.objects.filter(user=user, status=VapiSession.STATUS_AVALIADA).filter(
        Q(situation__in=slugs) | Q(full_session_data__config__curso_id=str(course.id))).exclude(
        situation__startswith='exame-')


def frases_do_curso(course):
    """As frases aprovadas (FraseAula, tipo frase) das aulas visíveis do curso, sem repetidas: [(texto, traducao)].
    As palavras soltas ficam de fora: nunca chegam a 'sozinho' (apps/perfil, MIN_PALAVRAS_BANCO)."""
    from apps.courses.models import FraseAula
    from apps.perfil.servico import normalizar
    vistas, out = set(), []
    for texto, traducao in (FraseAula.objects.filter(q_aula_visivel('chapter__'), chapter__section__course=course,
                                                     estado=FraseAula.APROVADA, tipo=FraseAula.TIPO_FRASE)
                            .order_by('chapter__section__order', 'chapter__order', 'ordem', 'id')
                            .values_list('texto', 'traducao')):
        chave = normalizar(texto)
        if chave and chave not in vistas:
            vistas.add(chave)
            out.append((texto, traducao))
    return out


def curso_da_sessao(vapi_session):
    """O curso a que uma conversa conta (ou None): o curso_id da configuração ou o da situação."""
    from apps.practice.models import Situacao
    dados = vapi_session.full_session_data if isinstance(vapi_session.full_session_data, dict) else {}
    config = dados.get('config') if isinstance(dados.get('config'), dict) else {}
    curso_id = config.get('curso_id')
    if curso_id:
        curso = Course.objects.filter(pk=curso_id).first() if _uuid_valido(curso_id) else None
        if curso is not None:
            return curso
    if vapi_session.situation:
        situacao = Situacao.objects.select_related('curso').filter(slug=vapi_session.situation).first()
        if situacao is not None and situacao.curso_id:
            return situacao.curso
    return None


def _uuid_valido(valor) -> bool:
    import uuid
    try:
        uuid.UUID(str(valor))
        return True
    except (TypeError, ValueError):
        return False


def cursos_da_licao_pratica(lesson_id):
    """Cursos em vídeo com aulas (ou questionários) ligados a esta lição de prática."""
    return Course.objects.filter(
        Q(sections__chapters__practice_lesson_id=lesson_id)
        | Q(sections__chapters__quiz__practice_lesson_id=lesson_id)
    ).distinct()


class GradeCalculatorService:
    """
    Service for calculating student grades in video courses.

    Componentes (fase 6, pesos por omissão em CourseGradingConfig):
    1. Exame oral (40%) - ExameOral avaliado; a nota revista pelo professor ganha à da IA
    2. Frases do curso ditas sozinho (25%) - FraseAula aprovadas no estado 'sozinho' do perfil
    3. Conversas do curso (20%) - VapiSession do curso (regras da fase 1, sem o exame)
    4. Estudo (15%) - questionários e prática, na proporção interna quiz_weight:practice_weight
    Passar no exame oral é requisito do certificado (exam_enabled).
    """

    CALCULATION_VERSION = 2  # fase 6: exame oral, frases do curso, conversas, estudo

    def __init__(self, user: User, course: Course):
        self.user = user
        self.course = course
        self.config = self._get_or_create_config()

    def _get_or_create_config(self) -> CourseGradingConfig:
        """Get or create grading configuration for the course."""
        config, _ = CourseGradingConfig.objects.get_or_create(course=self.course)
        return config

    # ------------------------------------------------------------------
    # Fase 6: exame oral e frases do curso
    # ------------------------------------------------------------------

    def calculate_exam_scores(self) -> Dict:
        """
        Exame oral: a melhor nota efectiva (a revista pelo professor ganha à da IA) das tentativas
        avaliadas; passou = alguma tentativa com nota efectiva >= nota mínima ACTUAL do curso
        (config.min_exam_score de agora, não a guardada no momento do exame).
        """
        from apps.courses.models import ExameOral
        if not self.config.exam_enabled:
            return {'score': None, 'passed': False, 'attempts': 0, 'details': {}, 'component_disabled': True}
        exames = list(ExameOral.objects.filter(user=self.user, course=self.course, estado=ExameOral.AVALIADO)
                      .order_by('-created_at'))
        if not exames:
            return {'score': None, 'passed': False, 'attempts': 0, 'details': {},
                    'min_score': self.config.min_exam_score}
        melhor = max(exames, key=lambda e: (e.nota_efectiva or 0, e.created_at))
        minima = self.config.min_exam_score
        aprovados = [e for e in exames if e.nota_efectiva is not None and e.nota_efectiva >= minima]
        passou = bool(aprovados)
        aprovado = aprovados[0] if aprovados else None
        ref = aprovado if aprovado is not None and (aprovado.nota_efectiva or 0) >= (melhor.nota_efectiva or 0) else melhor
        return {
            'score': round(melhor.nota_efectiva or 0, 2),
            'passed': passou,
            'attempts': len(exames),
            'min_score': self.config.min_exam_score,
            'details': {
                'exame_id': str(ref.id),
                'nota': ref.nota_efectiva,
                'nota_ia': ref.nota_final,
                'nota_revista': ref.nota_revista,
                'nivel_cefr': ref.nivel_cefr,
                'notas': ref.notas(),
                'data': ref.created_at.isoformat(),
            },
        }

    def calculate_phrase_scores(self) -> Dict:
        """% das frases aprovadas do curso que o aluno já disse sozinho numa conversa (apps/perfil)."""
        from apps.perfil.models import ItemBanco
        from apps.perfil.servico import normalizar
        frases = frases_do_curso(self.course)
        if not frases:
            return {'score': 0.0, 'total': 0, 'mastered': 0}
        chaves = [normalizar(t) for t, _ in frases]
        sozinho = ItemBanco.objects.filter(user=self.user, chave__in=chaves, estado=ItemBanco.SOZINHO).count()
        return {'score': round(sozinho * 100.0 / len(frases), 2), 'total': len(frases), 'mastered': sozinho}

    def study_score(self, quiz_data: Dict, practice_data: Dict):
        """Estudo = questionários e prática na proporção quiz_weight:practice_weight (só os que existem)."""
        partes = []
        if quiz_data.get('count', 0) > 0 and self.config.quiz_enabled:
            partes.append((quiz_data['score'], self.config.quiz_weight))
        if practice_data.get('count', 0) > 0 and self.config.practice_enabled:
            partes.append((practice_data['score'], self.config.practice_weight))
        total = sum(p for _, p in partes)
        if not partes:
            return None
        if total <= 0:
            return sum(v for v, _ in partes) / len(partes)
        return sum(v * p for v, p in partes) / total

    def calculate_quiz_scores(self) -> Dict:
        """
        Calculate quiz scores for the student.

        Returns dict with:
        - score: Average quiz score (0-100)
        - count: Total quizzes in course
        - completed: Quizzes completed by student
        - passed: Quizzes passed by student
        - details: Per-quiz scores
        """
        # Check if quiz component is enabled
        if not self.config.quiz_enabled:
            return {
                'score': 0.0,
                'count': 0,
                'completed': 0,
                'passed': 0,
                'details': [],
                'component_disabled': True
            }

        # Get all quizzes in the course
        quizzes = ChapterQuiz.objects.filter(
            chapter__section__course=self.course,
            is_active=True
        ).filter(q_aula_visivel('chapter__')).select_related('chapter', 'chapter__section')

        quiz_count = quizzes.count()

        if quiz_count == 0:
            return {
                'score': 0.0,
                'count': 0,
                'completed': 0,
                'passed': 0,
                'details': []
            }

        quiz_details = []
        total_score = 0.0
        completed_count = 0
        passed_count = 0

        for quiz in quizzes:
            # Get student's attempts for this quiz
            attempts = StudentQuizAttempt.objects.filter(
                student=self.user,
                chapter_quiz=quiz,
                is_completed=True
            )

            if attempts.exists():
                completed_count += 1

                # Use best attempt or latest based on config
                if self.config.use_best_quiz_attempt:
                    best_attempt = attempts.order_by('-score').first()
                else:
                    best_attempt = attempts.order_by('-created_at').first()

                score_percentage = best_attempt.score_percentage
                is_passed = best_attempt.is_passed

                if is_passed:
                    passed_count += 1

                total_score += score_percentage

                quiz_details.append({
                    'quiz_id': str(quiz.id),
                    'quiz_title': quiz.title,
                    'chapter_title': quiz.chapter.title,
                    'section_title': quiz.chapter.section.sectionTitle,
                    'score': score_percentage,
                    'is_passed': is_passed,
                    'attempts_used': attempts.count(),
                    'max_attempts': quiz.max_attempts,
                    'passing_score': quiz.passing_score,
                })
            else:
                quiz_details.append({
                    'quiz_id': str(quiz.id),
                    'quiz_title': quiz.title,
                    'chapter_title': quiz.chapter.title,
                    'section_title': quiz.chapter.section.sectionTitle,
                    'score': 0,
                    'is_passed': False,
                    'attempts_used': 0,
                    'max_attempts': quiz.max_attempts,
                    'passing_score': quiz.passing_score,
                })

        # Calculate average score
        average_score = total_score / quiz_count if quiz_count > 0 else 0.0

        return {
            'score': round(average_score, 2),
            'count': quiz_count,
            'completed': completed_count,
            'passed': passed_count,
            'details': quiz_details
        }

    def calculate_practice_scores(self) -> Dict:
        """
        Calculate practice exercise scores.

        Practice scores are based on completion of challenges linked to
        the course via ChapterQuiz -> PracticeLesson -> Units -> Challenges.

        Returns dict with:
        - score: Completion percentage (0-100)
        - count: Total challenges
        - completed: Challenges completed
        - details: Per-chapter breakdown
        """
        # Check if practice component is enabled
        if not self.config.practice_enabled:
            return {
                'score': 0.0,
                'count': 0,
                'completed': 0,
                'details': [],
                'component_disabled': True
            }

        # Lições de prática ligadas às aulas visíveis do curso: a "lição a seguir" da aula
        # (Chapter.practice_lesson) e a do questionário (ChapterQuiz.practice_lesson). Cada lição
        # conta uma vez, mesmo que esteja ligada a várias aulas.
        from apps.practice.models import PracticeChallenge

        ligacoes = []
        for chapter in (Chapter.objects.filter(q_aula_visivel(), section__course=self.course,
                                               practice_lesson__isnull=False)
                        .select_related('practice_lesson', 'section')
                        .order_by('section__order', 'order', 'created_at')):
            ligacoes.append((chapter, chapter.practice_lesson))
        for quiz in (ChapterQuiz.objects.filter(chapter__section__course=self.course, is_active=True,
                                                practice_lesson__isnull=False)
                     .filter(q_aula_visivel('chapter__'))
                     .select_related('practice_lesson', 'chapter', 'chapter__section')):
            ligacoes.append((quiz.chapter, quiz.practice_lesson))

        practice_details = []
        total_challenges = 0
        completed_challenges = 0
        vistas = set()

        for chapter, licao in ligacoes:
            if licao.id in vistas:
                continue
            vistas.add(licao.id)

            challenges = PracticeChallenge.objects.filter(lesson=licao)
            chapter_total = challenges.count()
            if chapter_total == 0:
                continue

            # Count completed challenges for this user
            # Exercícios saltados (análise indisponível, sem microfone) não contam como prática feita.
            chapter_completed = ChallengeProgress.objects.filter(
                user=self.user,
                challenge__in=challenges,
                completed=True,
                skipped=False
            ).count()

            total_challenges += chapter_total
            completed_challenges += chapter_completed

            practice_details.append({
                'chapter_id': str(chapter.id),
                'chapter_title': chapter.title,
                'section_title': chapter.section.sectionTitle,
                'practice_lesson_id': str(licao.id),
                'total_challenges': chapter_total,
                'completed_challenges': chapter_completed,
                'completion_percentage': round(
                    (chapter_completed / chapter_total) * 100 if chapter_total > 0 else 0, 2
                ),
            })

        # Calculate overall completion percentage
        completion_percentage = (
            (completed_challenges / total_challenges) * 100
            if total_challenges > 0 else 0.0
        )

        return {
            'score': round(completion_percentage, 2),
            'count': total_challenges,
            'completed': completed_challenges,
            'details': practice_details
        }

    def calculate_conversation_scores(self) -> Dict:
        """
        Calculate conversation practice scores from Vapi sessions.

        Only conversations tied to this course count (sessoes_de_conversa_do_curso).

        Returns dict with:
        - score: Average conversation score (0-100)
        - sessions: Total sessions completed
        - minutes: Total practice minutes
        - details: Per-session breakdown
        - has_requirement: Whether course requires conversation practice
        """
        # Check if conversation component is enabled for this course
        if not self.config.conversation_enabled:
            return {
                'score': 0.0,
                'sessions': 0,
                'minutes': 0,
                'details': [],
                'has_requirement': False,
                'component_disabled': True
            }

        # A conversa só é requisito se o curso tiver pelo menos uma situação de conversa activa;
        # sem situações o componente não existe e os pesos dos outros são renormalizados.
        has_requirement = bool(self.config.require_conversation_if_available
                               and curso_tem_conversa(self.course))

        # Só as conversas deste curso (avaliadas): numa situação do curso, ou iniciadas a partir
        # dele (full_session_data.config.curso_id). As de outros cursos ou gerais não contam.
        sessions = sessoes_de_conversa_do_curso(self.user, self.course).order_by('-created_at')

        session_count = sessions.count()

        if session_count == 0:
            return {
                'score': 0.0,
                'sessions': 0,
                'minutes': 0,
                'details': [],
                'has_requirement': has_requirement
            }

        # Aggregate scores
        # Minutos reais (duration_seconds, como no DailyStudyLog e nas estatísticas); sessões
        # antigas sem segundos usam duration_minutes.
        from django.db.models import Case, When, F, IntegerField
        aggregates = sessions.aggregate(
            avg_score=Avg('overall_score'),
            total_seconds=Sum(Case(
                When(duration_seconds__gt=0, then=F('duration_seconds')),
                default=F('duration_minutes') * 60,
                output_field=IntegerField(),
            )),
            avg_fluency=Avg('fluency_score'),
            avg_pronunciation=Avg('pronunciation_score'),
            avg_grammar=Avg('grammar_score'),
            avg_vocabulary=Avg('vocabulary_score'),
        )

        # Get detailed session info (last 10)
        session_details = []
        for session in sessions[:10]:
            session_details.append({
                'session_id': session.session_id,
                'date': session.created_at.isoformat(),
                'level': session.level,
                'domain': session.domain,
                'duration_minutes': session.duration_minutes,
                'overall_score': session.overall_score,
                'fluency': session.fluency_score,
                'pronunciation': session.pronunciation_score,
                'grammar': session.grammar_score,
                'vocabulary': session.vocabulary_score,
            })

        return {
            'score': round(aggregates['avg_score'] or 0, 2),
            'sessions': session_count,
            'minutes': round((aggregates['total_seconds'] or 0) / 60),
            'fluency_average': round(aggregates['avg_fluency'] or 0, 2),
            'pronunciation_average': round(aggregates['avg_pronunciation'] or 0, 2),
            'grammar_average': round(aggregates['avg_grammar'] or 0, 2),
            'vocabulary_average': round(aggregates['avg_vocabulary'] or 0, 2),
            'details': session_details,
            'has_requirement': has_requirement
        }

    def calculate_final_grade(
        self,
        quiz_data: Dict,
        practice_data: Dict,
        conversation_data: Dict,
        exam_data: Optional[Dict] = None,
        phrase_data: Optional[Dict] = None,
    ) -> Tuple[float, str, Dict]:
        """
        Nota final (fase 6): exame oral 40 %, frases do curso ditas sozinho 25 %, conversas do
        curso 20 % e estudo (questionários + prática) 15 %, com os pesos de CourseGradingConfig.

        Componentes que não existem saem e os pesos dos outros são renormalizados:
        - exame: desligado no curso (exam_enabled=False). Ligado conta sempre (0 até haver nota);
        - frases: o curso não tem frases aprovadas;
        - conversas: as regras da fase 1 (situação de conversa do curso e pelo menos uma conversa);
        - estudo: sem questionários nem prática.

        Returns:
        - final_percentage: Weighted average (0-100)
        - final_letter: Letter grade (A+, A, B+, etc.)
        - weight_info: Dict with actual weights used (for transparency)
        """
        exam_data = exam_data if exam_data is not None else self.calculate_exam_scores()
        phrase_data = phrase_data if phrase_data is not None else self.calculate_phrase_scores()

        quiz_active = quiz_data.get('count', 0) > 0 and self.config.quiz_enabled
        practice_active = practice_data.get('count', 0) > 0 and self.config.practice_enabled
        conversation_active = (
            conversation_data.get('has_requirement', False) and
            conversation_data.get('sessions', 0) > 0 and
            self.config.conversation_enabled and
            not conversation_data.get('component_disabled', False)
        )
        exam_active = self.config.exam_enabled and not exam_data.get('component_disabled', False)
        phrases_active = phrase_data.get('total', 0) > 0
        estudo = self.study_score(quiz_data, practice_data)
        study_active = estudo is not None

        pesos = {
            'exam': self.config.exam_weight if exam_active else 0,
            'phrases': self.config.phrases_weight if phrases_active else 0,
            'conversation': self.config.conversation_weight if conversation_active else 0,
            'study': self.config.study_weight if study_active else 0,
        }
        total = sum(pesos.values())

        if total == 0:
            return 0.0, 'N/A', {
                'quiz_weight': 0, 'practice_weight': 0, 'conversation_weight': 0,
                'exam_weight': 0, 'phrases_weight': 0, 'study_weight': 0,
                'mode': 'no_content',
                'active_components': [],
                'message': 'Nenhum componente de avaliação disponível no curso'
            }

        norm = {k: (v / total) * 100 for k, v in pesos.items()}
        valores = {
            'exam': exam_data.get('score') or 0.0,
            'phrases': phrase_data.get('score') or 0.0,
            'conversation': conversation_data.get('score') or 0.0,
            'study': estudo or 0.0,
        }
        final_percentage = round(sum(valores[k] * norm[k] / 100 for k in norm), 2)
        final_letter = self.config.get_grade_with_plus_minus(final_percentage)

        # Dentro do estudo: a parte de cada um (para os ecrãs antigos que mostram quiz/practice).
        qw = self.config.quiz_weight if quiz_active else 0
        pw = self.config.practice_weight if practice_active else 0
        if qw + pw == 0 and study_active:
            qw, pw = (1 if quiz_active else 0), (1 if practice_active else 0)
        quiz_share = norm['study'] * qw / (qw + pw) if (qw + pw) else 0
        practice_share = norm['study'] * pw / (qw + pw) if (qw + pw) else 0

        active_components = [k for k in ('exam', 'phrases', 'conversation') if pesos[k]]
        if quiz_active:
            active_components.append('quizzes')
        if practice_active:
            active_components.append('practice')
        if study_active:
            active_components.append('study')

        weight_info = {
            'exam_weight': round(norm['exam'], 1),
            'phrases_weight': round(norm['phrases'], 1),
            'conversation_weight': round(norm['conversation'], 1),
            'study_weight': round(norm['study'], 1),
            'quiz_weight': round(quiz_share, 1),
            'practice_weight': round(practice_share, 1),
            'study_score': round(estudo, 2) if estudo is not None else None,
            'original_exam_weight': self.config.exam_weight,
            'original_phrases_weight': self.config.phrases_weight,
            'original_conversation_weight': self.config.conversation_weight,
            'original_study_weight': self.config.study_weight,
            'original_quiz_weight': self.config.quiz_weight,
            'original_practice_weight': self.config.practice_weight,
            'mode': 'full' if all(pesos.values()) else 'simplified',
            'active_components': active_components,
            'weights_adjusted': total != 100,
        }
        return final_percentage, final_letter, weight_info

    def check_certificate_eligibility(
        self,
        quiz_data: Dict,
        practice_data: Dict,
        conversation_data: Dict,
        final_percentage: float,
        weight_info: Dict = None,
        exam_data: Optional[Dict] = None,
    ) -> Tuple[bool, Dict]:
        """
        Check if student meets all requirements for certificate.

        Dynamically adjusts requirements based on what components exist:
        - If no quizzes in course, quiz requirements are skipped
        - If no practice lessons linked, practice requirements are skipped
        - If no conversation sessions or component disabled, conversation requirements are skipped

        Returns:
        - is_eligible: Boolean indicating eligibility
        - details: Dict with each requirement's status
        """
        eligibility_details = {}
        all_met = True
        weight_info = weight_info or {}

        # Determine which components have content
        quiz_exists = quiz_data.get('count', 0) > 0 and self.config.quiz_enabled
        practice_exists = practice_data.get('count', 0) > 0 and self.config.practice_enabled
        conversation_exists = (
            conversation_data.get('sessions', 0) > 0 and
            self.config.conversation_enabled and
            not conversation_data.get('component_disabled', False)
        )

        # 1. Check minimum quiz average (only if quizzes exist)
        if quiz_exists:
            quiz_met = quiz_data['score'] >= self.config.min_quiz_average
            eligibility_details['quiz_average'] = {
                'met': quiz_met,
                'required': self.config.min_quiz_average,
                'actual': quiz_data['score'],
                'message': f"Média dos quizzes: {quiz_data['score']}% (mínimo: {self.config.min_quiz_average}%)"
            }
            if not quiz_met:
                all_met = False

            # 2. Check all quizzes passed (if required)
            if self.config.require_all_quizzes_passed:
                all_quizzes_passed = quiz_data['passed'] == quiz_data['count']
                eligibility_details['all_quizzes_passed'] = {
                    'met': all_quizzes_passed,
                    'required': quiz_data['count'],
                    'actual': quiz_data['passed'],
                    'message': f"Quizzes aprovados: {quiz_data['passed']}/{quiz_data['count']}"
                }
                if not all_quizzes_passed:
                    all_met = False
        else:
            eligibility_details['quiz_average'] = {
                'met': True,
                'required': None,
                'actual': 0,
                'message': "Sem quizzes configurados neste curso",
                'skipped': True
            }

        # 3. Check minimum practice completion (only if practice exists)
        if practice_exists:
            practice_met = practice_data['score'] >= self.config.min_practice_completion
            eligibility_details['practice_completion'] = {
                'met': practice_met,
                'required': self.config.min_practice_completion,
                'actual': practice_data['score'],
                'message': f"Exercícios práticos: {practice_data['score']}% completos (mínimo: {self.config.min_practice_completion}%)"
            }
            if not practice_met:
                all_met = False
        else:
            eligibility_details['practice_completion'] = {
                'met': True,
                'required': None,
                'actual': 0,
                'message': "Sem exercícios práticos vinculados neste curso",
                'skipped': True
            }

        # 4. Check conversation score (if required, enabled, and available)
        if self.config.conversation_enabled and conversation_data.get('has_requirement', False):
            if conversation_exists:
                conversation_met = conversation_data['score'] >= self.config.min_conversation_score
                eligibility_details['conversation_score'] = {
                    'met': conversation_met,
                    'required': self.config.min_conversation_score,
                    'actual': conversation_data['score'],
                    'message': f"Pontuação de conversação: {conversation_data['score']}% (mínimo: {self.config.min_conversation_score}%)"
                }
                if not conversation_met:
                    all_met = False
            else:
                # Conversation is required but no sessions
                eligibility_details['conversation_score'] = {
                    'met': False,
                    'required': self.config.min_conversation_score,
                    'actual': 0,
                    'message': "Ainda não fez nenhuma conversa deste curso"
                }
                all_met = False
        else:
            eligibility_details['conversation_score'] = {
                'met': True,
                'required': None,
                'actual': conversation_data.get('score', 0),
                'message': "Conversação não é requisito para este curso" if not self.config.require_conversation_if_available else "Componente de conversação desativado",
                'skipped': True
            }

        # 5. Exame oral (fase 6): passar no exame é obrigatório para o certificado.
        if exam_data is None:
            exam_data = self.calculate_exam_scores()
        if self.config.exam_enabled and not exam_data.get('component_disabled'):
            passou = bool(exam_data.get('passed'))
            if passou:
                msg = f"Exame oral: aprovado com {round(exam_data.get('score') or 0)}% (mínimo: {self.config.min_exam_score:.0f}%)"
            elif exam_data.get('attempts'):
                msg = (f"Exame oral: {round(exam_data.get('score') or 0)}% "
                       f"(mínimo para passar: {self.config.min_exam_score:.0f}%)")
            else:
                msg = "Exame oral: ainda não fez o exame deste curso"
            eligibility_details['oral_exam'] = {
                'met': passou,
                'required': self.config.min_exam_score,
                'actual': exam_data.get('score') or 0,
                'message': msg,
            }
            if not passou:
                all_met = False

        # 6. Check minimum final grade
        final_grade_met = final_percentage >= self.config.min_final_grade
        eligibility_details['final_grade'] = {
            'met': final_grade_met,
            'required': self.config.min_final_grade,
            'actual': final_percentage,
            'message': f"Nota final: {final_percentage}% (mínimo: {self.config.min_final_grade}%)"
        }
        if not final_grade_met:
            all_met = False

        # Add weight adjustment info if weights were adjusted
        if weight_info.get('weights_adjusted'):
            eligibility_details['weight_adjustment'] = {
                'met': True,
                'required': None,
                'actual': None,
                'message': f"Pesos ajustados automaticamente: {', '.join(weight_info.get('active_components', []))}",
                'info_only': True
            }

        return all_met, eligibility_details

    def _calcular(self):
        """Calcula todos os componentes. Devolve (quiz, practice, conversation, final, letter, weights, eligible, details)."""
        quiz_data = self.calculate_quiz_scores()
        practice_data = self.calculate_practice_scores()
        conversation_data = self.calculate_conversation_scores()
        exam_data = self.calculate_exam_scores()
        phrase_data = self.calculate_phrase_scores()
        final_percentage, final_letter, weight_info = self.calculate_final_grade(
            quiz_data, practice_data, conversation_data, exam_data, phrase_data
        )
        is_eligible, eligibility_details = self.check_certificate_eligibility(
            quiz_data, practice_data, conversation_data, final_percentage, weight_info, exam_data
        )
        # O exame e as frases seguem em weight_info (o _preencher guarda-os nos campos próprios).
        weight_info = dict(weight_info, _exam=exam_data, _phrases=phrase_data)
        return (quiz_data, practice_data, conversation_data, final_percentage, final_letter,
                weight_info, is_eligible, eligibility_details)

    @staticmethod
    def _preencher(grade, quiz_data, practice_data, conversation_data, final_percentage, final_letter,
                   weight_info, is_eligible, eligibility_details):
        grade.quiz_score = quiz_data['score']
        grade.quiz_count = quiz_data['count']
        grade.quiz_completed = quiz_data['completed']
        grade.quiz_passed = quiz_data['passed']
        grade.quiz_details = quiz_data['details']

        grade.practice_score = practice_data['score']
        grade.practice_count = practice_data['count']
        grade.practice_completed = practice_data['completed']
        grade.practice_details = practice_data['details']

        grade.conversation_score = conversation_data['score']
        grade.conversation_sessions = conversation_data['sessions']
        grade.conversation_minutes = conversation_data['minutes']
        grade.conversation_details = conversation_data['details']
        grade.has_conversation_requirement = conversation_data['has_requirement']

        weight_info = dict(weight_info)
        exam_data = weight_info.pop('_exam', None) or {}
        phrase_data = weight_info.pop('_phrases', None) or {}
        grade.exam_score = exam_data.get('score')
        grade.exam_passed = bool(exam_data.get('passed'))
        grade.exam_details = {k: v for k, v in exam_data.items() if k != 'score'}
        grade.phrases_score = phrase_data.get('score') or 0.0
        grade.phrases_total = phrase_data.get('total') or 0
        grade.phrases_mastered = phrase_data.get('mastered') or 0

        grade.final_grade_percentage = final_percentage
        grade.final_grade_letter = final_letter
        grade.is_eligible_for_certificate = is_eligible
        grade.eligibility_details = eligibility_details
        grade.weight_info = weight_info
        grade.calculation_version = GradeCalculatorService.CALCULATION_VERSION

    def calcular_sem_guardar(self) -> StudentCourseGrade:
        """
        A nota calculada agora, num StudentCourseGrade NÃO guardado (para leituras: GET não
        escreve na base de dados nem dispara signals).
        """
        from django.utils import timezone
        resultado = self._calcular()
        grade = (StudentCourseGrade.objects.filter(user=self.user, course=self.course).first()
                 or StudentCourseGrade(user=self.user, course=self.course))
        self._preencher(grade, *resultado)
        grade.last_calculated_at = timezone.now()
        return grade

    @transaction.atomic
    def calculate_and_save(self, change_reason: str = 'recalculation') -> StudentCourseGrade:
        """
        Calculate all grades and save to database.

        Args:
            change_reason: Reason for this calculation (for audit trail)

        Returns:
            StudentCourseGrade: Updated grade record
        """
        resultado = self._calcular()
        (quiz_data, practice_data, conversation_data, final_percentage, final_letter,
         weight_info, is_eligible, eligibility_details) = resultado

        # Get or create grade record
        grade, created = StudentCourseGrade.objects.get_or_create(
            user=self.user,
            course=self.course,
            defaults={'calculation_version': self.CALCULATION_VERSION}
        )

        # Track if grade changed
        grade_changed = (
            created or
            grade.final_grade_percentage != final_percentage or
            grade.is_eligible_for_certificate != is_eligible
        )

        self._preencher(grade, *resultado)
        grade.save()

        # Create history entry if grade changed
        if grade_changed:
            GradeHistory.objects.create(
                student_grade=grade,
                quiz_score=quiz_data['score'],
                practice_score=practice_data['score'],
                conversation_score=conversation_data['score'],
                final_grade_percentage=final_percentage,
                final_grade_letter=final_letter,
                is_eligible=is_eligible,
                change_reason=change_reason,
                change_details={
                    'quiz_data': {
                        'score': quiz_data['score'],
                        'completed': quiz_data['completed'],
                        'passed': quiz_data['passed'],
                    },
                    'practice_data': {
                        'score': practice_data['score'],
                        'completed': practice_data['completed'],
                    },
                    'conversation_data': {
                        'score': conversation_data['score'],
                        'sessions': conversation_data['sessions'],
                    },
                    'config': {
                        'quiz_weight': self.config.quiz_weight,
                        'practice_weight': self.config.practice_weight,
                        'conversation_weight': self.config.conversation_weight,
                        'exam_weight': self.config.exam_weight,
                        'phrases_weight': self.config.phrases_weight,
                        'study_weight': self.config.study_weight,
                    },
                    'exam_score': grade.exam_score,
                    'phrases_score': grade.phrases_score,
                    'weight_info': grade.weight_info
                }
            )

        return grade

    @classmethod
    def recalculate_for_course(cls, course: Course) -> int:
        """
        Recalculate grades for all enrolled students in a course.

        Returns:
            int: Number of grades updated
        """
        from apps.courses.models import CourseEnrollment

        enrollments = CourseEnrollment.objects.filter(
            course=course
        ).select_related('user')

        count = 0
        for enrollment in enrollments:
            calculator = cls(enrollment.user, course)
            calculator.calculate_and_save(change_reason='recalculation')
            count += 1

        return count

    @classmethod
    def trigger_update_on_quiz_complete(cls, user: User, chapter_quiz: ChapterQuiz):
        """
        Trigger grade recalculation when a quiz is completed.
        """
        course = chapter_quiz.chapter.section.course
        calculator = cls(user, course)
        return calculator.calculate_and_save(change_reason='quiz_completed')

    @classmethod
    def trigger_update_on_practice_complete(cls, user: User, challenge_progress: ChallengeProgress):
        """
        Trigger grade recalculation when a practice challenge is completed.

        Courses whose chapters (Chapter.practice_lesson) or chapter quizzes
        (ChapterQuiz.practice_lesson) link to the challenge's lesson, where the user is enrolled.
        """
        from apps.courses.models import CourseEnrollment

        lesson_id = challenge_progress.challenge.lesson_id
        grades = []
        for course in cursos_da_licao_pratica(lesson_id):
            if CourseEnrollment.objects.filter(user=user, course=course).exists():
                grades.append(cls(user, course).calculate_and_save(change_reason='practice_completed'))
        return grades

    @classmethod
    def trigger_update_on_conversation_session(cls, user: User, vapi_session: VapiSession):
        """
        Trigger grade recalculation when a conversation session is completed.

        Only the course the conversation belongs to (curso_da_sessao), if the user is enrolled.
        """
        from apps.courses.models import CourseEnrollment

        course = curso_da_sessao(vapi_session)
        if course is None or not CourseEnrollment.objects.filter(user=user, course=course).exists():
            return []
        return [cls(user, course).calculate_and_save(change_reason='conversation_session')]
