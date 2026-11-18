"""
Unidades de amostra: um curso pago (access_level premium / premium_plus) pode abrir as primeiras N
unidades a todos, também ao plano Gratuito.

N vem de Course.definicoes['unidades_amostra'] (inteiro, 0 por omissão = sem amostra). As unidades
são as secções (CourseSection, por order e created_at) num curso em vídeo e as unidades de prática
(PracticeUnit, por order) num curso de laboratório. O questionário de revisão no fim de uma secção
é uma aula dessa secção: segue a secção.

Quem não tem o plano do curso (acesso "amostra"):
- pode inscrever-se no curso (pode_inscrever);
- abre as aulas, questionários, recursos e lições de laboratório das unidades da amostra, e as
  conversas com o tutor ligadas a essas aulas (o tutor tem ainda os minutos do plano);
- nas outras unidades vê só a estrutura (títulos, tipos, ordem) e recebe 403 com o código
  CODIGO_PLANO (o mesmo que o laboratório já usava para cursos pagos) e MENSAGEM_PLANO.

É sempre o servidor a decidir: os clientes só mostram os cadeados que a API marca.
O professor do curso e os administradores vêem tudo (Course.user_has_access já o diz).
"""

from rest_framework import status
from rest_framework.exceptions import APIException

CODIGO_PLANO = 'plano_insuficiente'
MENSAGEM_PLANO = 'Esta unidade está disponível nos planos pagos.'

TOTAL = 'total'
AMOSTRA = 'amostra'


class PlanoNecessario(APIException):
    """403 de uma aula fora da amostra: {code: 'plano_insuficiente', message: MENSAGEM_PLANO}."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = MENSAGEM_PLANO
    default_code = CODIGO_PLANO


def unidades_amostra(course):
    """Quantas unidades do curso estão abertas a todos (0 = nenhuma). Só em cursos pagos."""
    if course is None or course.access_level == 'free':
        return 0
    definicoes = course.definicoes if isinstance(course.definicoes, dict) else {}
    valor = definicoes.get('unidades_amostra')
    if isinstance(valor, bool):
        return 0
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return 0
    return max(0, min(valor, 1000))


def ids_seccoes_amostra(course):
    """Ids das secções da amostra de um curso em vídeo (uma consulta, guardada na instância)."""
    cache = getattr(course, '_ids_seccoes_amostra', None)
    if cache is not None:
        return cache
    n = unidades_amostra(course)
    ids = set()
    if n:
        from apps.courses.models import CourseSection
        ids = set(CourseSection.objects.filter(course=course).order_by('order', 'created_at')
                  .values_list('id', flat=True)[:n])
    course._ids_seccoes_amostra = ids
    return ids


def ids_unidades_pratica_amostra(course):
    """Ids das unidades da amostra de um curso de laboratório (uma consulta, guardada na instância)."""
    cache = getattr(course, '_ids_unidades_amostra', None)
    if cache is not None:
        return cache
    n = unidades_amostra(course)
    ids = set()
    if n:
        from apps.practice.models import PracticeUnit
        ids = set(PracticeUnit.objects.filter(course=course).order_by('order', 'created_at')
                  .values_list('id', flat=True)[:n])
    course._ids_unidades_amostra = ids
    return ids


def acesso_total(user, course):
    """O plano dá acesso ao curso todo (ou é o professor do curso, ou administrador)."""
    if course.access_level == 'free':
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return bool(course.user_has_access(user))


def acesso(user, course, total=None):
    """'total' | 'amostra' | None. `total` evita repetir a consulta quando já se sabe."""
    if total is None:
        total = acesso_total(user, course)
    if total:
        return TOTAL
    return AMOSTRA if unidades_amostra(course) > 0 else None


def pode_inscrever(user, course):
    """O plano dá acesso ao curso, ou o curso tem unidades de amostra."""
    return acesso_total(user, course) or unidades_amostra(course) > 0


def seccoes_bloqueadas(user, course, total=None):
    """
    Ids das secções que esta pessoa não pode abrir num curso com amostra (set vazio com acesso
    total). Num curso pago sem amostra devolve None: o curso está todo fechado, como antes.
    """
    if total is None:
        total = acesso_total(user, course)
    if total:
        return set()
    if unidades_amostra(course) <= 0:
        return None
    from apps.courses.models import CourseSection
    abertas = ids_seccoes_amostra(course)
    return set(CourseSection.objects.filter(course=course).exclude(id__in=abertas).values_list('id', flat=True))


def unidades_pratica_bloqueadas(user, course, total=None):
    """Como seccoes_bloqueadas, para as unidades de um curso de laboratório."""
    if total is None:
        total = acesso_total(user, course)
    if total:
        return set()
    if unidades_amostra(course) <= 0:
        return None
    from apps.practice.models import PracticeUnit
    abertas = ids_unidades_pratica_amostra(course)
    return set(PracticeUnit.objects.filter(course=course).exclude(id__in=abertas).values_list('id', flat=True))


def seccao_na_amostra(section, course=None):
    course = course or section.course
    return section.id in ids_seccoes_amostra(course)


def aula_aberta(user, chapter):
    """O plano dá acesso ao curso da aula, ou a aula está numa secção da amostra."""
    course = chapter.section.course
    return acesso_total(user, course) or chapter.section_id in ids_seccoes_amostra(course)


def licao_aberta(user, licao):
    """O plano dá acesso ao curso de laboratório, ou a lição está numa unidade da amostra."""
    course = licao.unit.course
    return acesso_total(user, course) or licao.unit_id in ids_unidades_pratica_amostra(course)


def situacao_bloqueada(user, situacao, cache=None):
    """
    Uma situação do tutor ligada a uma aula (Situacao.aula) de uma unidade fechada de um curso
    com amostra. As outras situações (sem aula, ou de cursos sem amostra) não mudam aqui.
    `cache` ({id do curso: secções bloqueadas}) evita repetir consultas numa lista.
    """
    if not getattr(situacao, 'aula_id', None):
        return False
    aula = situacao.aula
    course = aula.section.course
    if unidades_amostra(course) <= 0:
        return False
    if cache is None:
        cache = {}
    if course.id not in cache:
        cache[course.id] = seccoes_bloqueadas(user, course) or set()
    return aula.section_id in cache[course.id]
