"""
Recalcular as notas de todos os alunos de um curso fora do pedido HTTP.

Quando o professor muda as regras da nota (definições do curso) ou as frases aprovadas do curso
(contam na nota: "frases do curso ditas sozinho"), as notas guardadas de todos os inscritos ficam
desactualizadas. Recalcular dentro do pedido demorava (um cálculo completo por aluno), por isso
corre numa thread à parte depois do commit.

- Um curso de cada vez por processo: um pedido novo para um curso que já está a ser recalculado
  só marca "outra vez no fim" (não arranca outra thread).
- settings.RECALCULO_NOTAS_EM_FUNDO = False (testes) corre logo, no mesmo pedido.
- Uma nota que falhe (ou um reinício a meio) é corrigida quando o aluno abre as notas, e o comando
  recalcular_notas_cursos refaz tudo.
"""
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)

_trinco = threading.Lock()
_a_correr = {}  # curso_id -> True se pediram outra vez enquanto corria


def recalcular_notas_agora(curso_id, motivo='recalculation'):
    """Recalcula e grava a nota de cada inscrito activo do curso. Devolve quantas."""
    from apps.courses.models import CourseEnrollment
    from apps.courses.services.grade_calculator import GradeCalculatorService
    n = 0
    for insc in CourseEnrollment.objects.filter(course_id=curso_id, is_active=True).select_related('user', 'course'):
        try:
            GradeCalculatorService(insc.user, insc.course).calculate_and_save(change_reason=motivo)
            n += 1
        except Exception:
            logger.exception('Falha ao recalcular a nota de %s no curso %s', insc.user_id, curso_id)
    return n


def _correr(curso_id, motivo):
    try:
        while True:
            try:
                recalcular_notas_agora(curso_id, motivo)
            except Exception:
                logger.exception('Falha ao recalcular as notas do curso %s', curso_id)
            with _trinco:
                if _a_correr.get(curso_id):
                    _a_correr[curso_id] = False
                    continue
                _a_correr.pop(curso_id, None)
                return
    finally:
        close_old_connections()


def recalcular_notas_em_fundo(curso_id, motivo='recalculation'):
    """Agenda o recálculo das notas do curso (thread à parte). Chamar depois do commit."""
    if not getattr(settings, 'RECALCULO_NOTAS_EM_FUNDO', True):
        recalcular_notas_agora(curso_id, motivo)
        return None
    with _trinco:
        if curso_id in _a_correr:
            _a_correr[curso_id] = True
            return None
        _a_correr[curso_id] = False
    t = threading.Thread(target=_correr, args=(curso_id, motivo), name='notas-recalcular', daemon=True)
    t.start()
    return t


def recalcular_notas_depois_do_commit(curso_id, motivo='recalculation'):
    transaction.on_commit(lambda: recalcular_notas_em_fundo(curso_id, motivo))
