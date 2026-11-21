"""
Questionários das aulas de um aluno e tentativas extra (área do professor).

  GET  /api/v1/teacher/alunos/<aluno>/questionarios/
       Questionários dos cursos do professor que o aluno já tentou e ainda não passou:
       [{id, curso:{id,titulo}, aula:{id,titulo}, tentativas, limite, restantes, melhor_nota,
         nota_minima}]
  POST /api/v1/teacher/alunos/<aluno>/questionarios/<quiz>/tentativas/   {extra?: 1..5 (1)}
       Dá mais tentativas ao aluno nesse questionário (o limite passa a max_attempts + extra).

Quem gasta as tentativas todas sem passar já conclui a aula (com o vídeo visto, ver
apps.courses.conclusao), mas o questionário falhado continua a pesar na nota do curso e pode
impedir o certificado ("todos os questionários aprovados"). Mais tentativas deixam o aluno
corrigir isso. Só o professor dono do curso (ou um administrador), e só para alunos inscritos.
"""
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo
from apps.courses.api.teacher.cursos import PERMISSOES, _erro
from apps.courses.models import ChapterQuiz, CourseEnrollment, StudentQuizAttempt, TentativasExtraQuestionario

MAXIMO_EXTRA_POR_PEDIDO = 5


def _cursos_do_aluno(request, aluno_id):
    """Ids dos cursos do professor (todos, para um administrador) em que o aluno está inscrito."""
    inscricoes = CourseEnrollment.objects.filter(user_id=aluno_id, course__course_type='video')
    if not ciclo.e_staff(request.user):
        inscricoes = inscricoes.filter(course__teacher=request.user)
    return set(inscricoes.values_list('course_id', flat=True))


def _linha(quiz, aluno_id, feitas, melhor, extra):
    limite = quiz.max_attempts + extra
    curso = quiz.chapter.section.course
    return {
        'id': str(quiz.pk),
        'curso': {'id': str(curso.pk), 'titulo': curso.title},
        'aula': {'id': str(quiz.chapter_id), 'titulo': quiz.chapter.title},
        'tentativas': feitas,
        'limite': limite,
        'restantes': max(0, limite - feitas),
        'melhor_nota': round(melhor) if melhor is not None else None,
        'nota_minima': quiz.passing_score,
    }


def _linhas(aluno_id, cursos, quiz_id=None):
    tentativas = (StudentQuizAttempt.objects
                  .filter(student_id=aluno_id, chapter_quiz__chapter__section__course_id__in=cursos,
                          chapter_quiz__is_active=True)
                  .values_list('chapter_quiz_id', 'score', 'max_score', 'is_passed'))
    if quiz_id is not None:
        tentativas = tentativas.filter(chapter_quiz_id=quiz_id)
    resumo = {}
    for qid, score, maximo, passou in tentativas:
        t = resumo.setdefault(qid, {'n': 0, 'passou': False, 'melhor': None})
        t['n'] += 1
        t['passou'] = t['passou'] or passou
        if maximo:
            pct = score * 100.0 / maximo
            t['melhor'] = pct if t['melhor'] is None else max(t['melhor'], pct)
    por_quiz = {qid: t for qid, t in resumo.items() if not t['passou']}
    if not por_quiz:
        return []
    extras = dict(TentativasExtraQuestionario.objects.filter(user_id=aluno_id, chapter_quiz_id__in=list(por_quiz))
                  .values_list('chapter_quiz_id', 'extra'))
    quizzes = (ChapterQuiz.objects.filter(pk__in=list(por_quiz)).filter(ciclo.q_aula_visivel('chapter__'))
               .select_related('chapter__section__course')
               .order_by('chapter__section__course__title', 'chapter__section__order', 'chapter__order'))
    return [_linha(q, aluno_id, por_quiz[q.pk]['n'], por_quiz[q.pk]['melhor'], extras.get(q.pk, 0))
            for q in quizzes]


@api_view(['GET'])
@permission_classes(PERMISSOES)
def questionarios_do_aluno(request, aluno_id):
    cursos = _cursos_do_aluno(request, aluno_id)
    if not cursos:
        raise NotFound('Aluno não encontrado.')
    return Response({'questionarios': _linhas(aluno_id, cursos)})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def dar_tentativas(request, aluno_id, quiz_id):
    cursos = _cursos_do_aluno(request, aluno_id)
    quiz = (ChapterQuiz.objects.select_related('chapter__section__course')
            .filter(pk=quiz_id, chapter__section__course_id__in=cursos).first())
    if quiz is None:
        raise NotFound('Questionário não encontrado.')
    dados = request.data if isinstance(request.data, dict) else {}
    extra = dados.get('extra', 1)
    if isinstance(extra, bool) or not isinstance(extra, int) or not 1 <= extra <= MAXIMO_EXTRA_POR_PEDIDO:
        return _erro(f'Escolha entre 1 e {MAXIMO_EXTRA_POR_PEDIDO} tentativas.', 'validation_error',
                     details={'extra': [f'Escolha entre 1 e {MAXIMO_EXTRA_POR_PEDIDO} tentativas.']})
    if StudentQuizAttempt.objects.filter(student_id=aluno_id, chapter_quiz=quiz, is_passed=True).exists():
        return _erro('O aluno já passou neste questionário.', 'ja_passou', 409)
    with transaction.atomic():
        registo, _ = TentativasExtraQuestionario.objects.select_for_update().get_or_create(
            chapter_quiz=quiz, user_id=aluno_id)
        registo.extra += extra
        registo.concedido_por = request.user
        registo.save(update_fields=['extra', 'concedido_por', 'actualizado_em'])
    linhas = _linhas(aluno_id, cursos, quiz_id=quiz.pk)
    if linhas:
        return Response(linhas[0])
    # Ainda sem tentativas: devolve a linha com 0 feitas.
    return Response(_linha(quiz, aluno_id, 0, None, registo.extra))
