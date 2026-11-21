"""
Quando uma aula de um curso em vídeo conta como concluída.

- Aula sem questionário activo: quando o aluno a vê ou lê (como sempre).
- Aula com questionário activo (ChapterQuiz.is_active, qualquer tipo de aula): só quando o
  questionário está passado E, se a aula tem vídeo, o vídeo foi visto. Ver o vídeo antes de passar
  fica guardado em ChapterProgress.video_visto; passar o questionário depois conclui a aula.
- Rede de segurança: quem gastou as tentativas todas sem passar também conclui a aula (com o vídeo
  visto), para não ficar preso sem poder acabar o curso. O questionário falhado continua a contar
  na nota do curso (média e "todos os questionários aprovados" nas notas e no certificado), e o
  professor pode dar mais tentativas ao aluno (TentativasExtraQuestionario).

Uma aula já concluída não volta atrás por o professor lhe acrescentar um questionário.

Ver o vídeo também põe as frases aprovadas da aula (FraseAula) no banco de frases do aluno.
"""
from django.utils import timezone


def questionario_activo(chapter):
    from apps.courses.models import ChapterQuiz
    return ChapterQuiz.objects.filter(chapter=chapter, is_active=True).first()


def passou_questionario(user, chapter_quiz):
    from apps.courses.models import StudentQuizAttempt
    return StudentQuizAttempt.objects.filter(student=user, chapter_quiz=chapter_quiz, is_passed=True).exists()


def esgotou_tentativas(user, chapter_quiz):
    """Gastou as tentativas todas (max_attempts + as extra do professor) sem passar."""
    from apps.courses.models import StudentQuizAttempt
    feitas = StudentQuizAttempt.objects.filter(student=user, chapter_quiz=chapter_quiz).count()
    return feitas >= chapter_quiz.limite_tentativas(user)


def questionario_feito(user, chapter_quiz):
    """Passou, ou esgotou as tentativas (rede de segurança: ver o topo do módulo)."""
    return passou_questionario(user, chapter_quiz) or esgotou_tentativas(user, chapter_quiz)


def precisa_de_video(chapter):
    return bool(chapter.video) and chapter.type != 'Quiz'


def registar(progresso, chapter, vista=False, desmarcar=False):
    """
    Regista na aula o que o aluno fez e decide se fica concluída.

    vista: o aluno viu o vídeo / marcou a aula como vista ou lida.
    desmarcar: o aluno desmarcou a aula (volta a não concluída e não vista).
    Devolve True se o estado de conclusão mudou.
    """
    from apps.courses.models import ChapterProgress

    registo, _ = ChapterProgress.objects.get_or_create(user_progress=progresso, chapter=chapter)
    antes = registo.completed
    if vista and not desmarcar and chapter.video:
        _frases_para_o_banco(progresso.user, chapter)
    if desmarcar:
        registo.completed = False
        registo.video_visto = False
    else:
        if vista:
            registo.video_visto = True
        if not registo.completed:
            quiz = questionario_activo(chapter)
            if quiz is None:
                registo.completed = bool(vista)
            else:
                registo.completed = (questionario_feito(progresso.user, quiz)
                                     and (registo.video_visto or not precisa_de_video(chapter)))
    if registo.completed and not registo.completed_at:
        registo.completed_at = timezone.now()
    registo.save()
    return registo.completed != antes


def _frases_para_o_banco(user, chapter):
    """Vídeo visto: as frases aprovadas da aula entram no banco do aluno como 'vista' (fase 5)."""
    import logging
    from apps.courses import frases_aula
    try:
        frases_aula.registar_vistas(user, chapter)
    except Exception:  # o banco nunca impede de marcar a aula
        logging.getLogger(__name__).exception('conclusão: falha ao registar as frases da aula %s', chapter.pk)


def actualizar_progresso(progresso):
    """Recalcula overallProgress e a data de conclusão do curso (e grava)."""
    from apps.courses.certificados import progresso_actual
    progresso.overallProgress = progresso_actual(progresso.user, progresso.course)
    if progresso.overallProgress >= 100.0 and not progresso.completion_date:
        progresso.completion_date = timezone.now()
    elif progresso.overallProgress < 100.0 and progresso.completion_date:
        progresso.completion_date = None
    progresso.save()


def apos_questionario_passado(user, chapter):
    """
    O aluno passou o questionário da aula (ou gastou as tentativas todas): conclui-a se o resto
    também está feito.
    """
    from apps.courses.models import UserCourseProgress
    course = chapter.section.course
    progresso, _ = UserCourseProgress.objects.get_or_create(
        user=user, course=course, defaults={'enrollmentDate': timezone.now(), 'overallProgress': 0.0})
    if registar(progresso, chapter):
        actualizar_progresso(progresso)
        return True
    return False
