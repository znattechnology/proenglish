"""
Pode esta pessoa abrir/jogar esta lição de prática agora?

A mesma regra que o trilho (GET .../courses/<id>/trilho/) mostra:
- uma lição "feita" (todos os exercícios concluídos) pode sempre ser repetida;
- a primeira lição por fazer, pela ordem unidade -> lição, é a "actual" e pode ser jogada;
- as outras estão bloqueadas, salvo se forem a lição de prática ligada a uma aula de um curso
  em vídeo em que o aluno está inscrito (ligada_a_aula_do_aluno).
O curso tem de estar publicado (ou arquivado a manter, para quem já o fazia; ver
apps/courses/ciclo.py), e o professor pode desligar a repetição (definição pode_repetir).
E o plano tem de dar acesso ao curso (Course.access_level: free / premium / premium_plus).

O professor do curso e os administradores não têm restrições.

Lições escondidas (licoes_visiveis): as alterações a um curso publicado ficam logo visíveis, mas
uma lição só aparece aos alunos quando está completa. Uma lição sem exercícios nunca aparece; uma
lição criada depois da última aprovação do curso (Course.aprovado_em) só aparece quando tem pelo
menos 3 exercícios e todos passam a lista de verificação (apps.courses.ciclo.exercicio_valido:
resposta certa, escuta com áudio, conversa curta com pelo menos 2 frases-alvo). As lições que já
estavam no curso quando foi aprovado continuam visíveis (os exercícios incompletos são saltados); a
guarda do editor (apps/courses/api/teacher/pratica.py) não deixa partir as que os alunos vêem.
"""
from django.db.models import Count, Prefetch, Q

MINIMO_EXERCICIOS = 3

CODIGO_BLOQUEADA = 'licao_bloqueada'
MENSAGEM_BLOQUEADA = 'Termine as lições anteriores para abrir esta.'
CODIGO_REPETIR = 'repeticao_desligada'
MENSAGEM_REPETIR = 'O professor deste curso não permite repetir lições já feitas.'
CODIGO_PLANO = 'plano_insuficiente'
MENSAGENS_PLANO = {
    'premium': 'Este curso requer um plano Premium ou superior.',
    'premium_plus': 'Este curso é exclusivo para assinantes Premium Plus.',
}


def _sem_restricoes(user, curso):
    from apps.core.permissions import e_administrador
    return bool(curso.teacher_id == user.id or e_administrador(user))


def estados_das_licoes(user, curso):
    """
    Lista de (lição anotada com total/feitos, estado) pela ordem do trilho.
    estado: "feita" | "actual" | "bloqueada".
    """
    from apps.practice.models import PracticeLesson

    licoes = (
        PracticeLesson.objects.filter(unit__course=curso)
        .select_related('unit')
        .annotate(
            total=Count('challenges', distinct=True),
            feitos=Count(
                'challenges__user_progress',
                filter=Q(challenges__user_progress__user=user, challenges__user_progress__completed=True),
                distinct=True,
            ),
        )
        .order_by('unit__order', 'order')
    )
    licoes = licoes_visiveis(curso, licoes)
    resultado = []
    actual_atribuida = False
    for licao in licoes:
        if licao.total > 0 and licao.feitos >= licao.total:
            estado = 'feita'
        elif not actual_atribuida:
            estado = 'actual'
            actual_atribuida = True
        else:
            estado = 'bloqueada'
        resultado.append((licao, estado))
    return resultado


def licao_completa(exercicios):
    """exercicios: PracticeChallenge com as opções (prefetch). True se passa a lista de verificação."""
    from apps.courses.ciclo import exercicio_valido
    exercicios = list(exercicios)
    return len(exercicios) >= MINIMO_EXERCICIOS and all(
        exercicio_valido(ch, list(ch.options.all()))[0] for ch in exercicios)


def ids_escondidas(curso, licoes=None):
    """Ids das lições do curso que os alunos não vêem (ver o início do ficheiro)."""
    from apps.practice.models import ChallengeOption, PracticeChallenge, PracticeLesson

    if licoes is None:
        licoes = PracticeLesson.objects.filter(unit__course=curso).annotate(total=Count('challenges'))
    escondidas, novas = set(), []
    for l in licoes:
        total = getattr(l, 'total', None)
        if total is None:
            total = l.challenges.count()
        if total == 0:
            escondidas.add(l.id)
        elif curso.aprovado_em and l.created_at and l.created_at > curso.aprovado_em:
            if total < MINIMO_EXERCICIOS:
                escondidas.add(l.id)
            else:
                novas.append(l.id)
    if novas:
        for l in PracticeLesson.objects.filter(id__in=novas).prefetch_related(
                Prefetch('challenges', queryset=PracticeChallenge.objects.order_by('order')),
                Prefetch('challenges__options', queryset=ChallengeOption.objects.order_by('order'))):
            if not licao_completa(l.challenges.all()):
                escondidas.add(l.id)
    return escondidas


def licoes_visiveis(curso, licoes):
    """Filtra uma lista/queryset de lições do curso, tirando as escondidas aos alunos."""
    licoes = list(licoes)
    escondidas = ids_escondidas(curso, licoes)
    return [l for l in licoes if l.id not in escondidas]


CODIGO_INDISPONIVEL = 'licao_indisponivel'


def ligada_a_aula_do_aluno(user, licao):
    """
    A lição é a "lição de prática a seguir" (Chapter.practice_lesson) de uma aula de um curso em
    vídeo em que a pessoa está inscrita: abre-se a partir da aula sem ter de seguir a ordem do trilho.
    """
    from apps.courses.models import Chapter, CourseEnrollment
    cursos = Chapter.objects.filter(practice_lesson=licao).values('section__course_id')
    return CourseEnrollment.objects.filter(user=user, is_active=True, course_id__in=cursos).exists()


def erro_acesso_licao(user, licao):
    """None se a pessoa pode jogar a lição; senão o corpo do 403."""
    curso = licao.unit.course
    if _sem_restricoes(user, curso):
        return None
    # Estado do curso (publicado / arquivado a manter / fechado) e máximo de alunos.
    from apps.courses.ciclo import bloqueio_pratica, definicao
    bloqueio = bloqueio_pratica(user, curso)
    if bloqueio:
        return {'codigo': bloqueio[0], 'mensagem': bloqueio[1]}
    from apps.courses.ciclo import bloqueio_requisito_pratica
    requisito = None if ligada_a_aula_do_aluno(user, licao) else bloqueio_requisito_pratica(user, curso)
    if requisito:
        return {'codigo': requisito[0], 'mensagem': requisito[1], 'teste': '/user/teste-basico'}
    if not curso.user_has_access(user):
        return {
            'codigo': CODIGO_PLANO,
            'mensagem': MENSAGENS_PLANO.get(curso.access_level, 'O seu plano não dá acesso a este curso.'),
        }
    for outra, estado in estados_das_licoes(user, curso):
        if outra.id == licao.id:
            if estado == 'bloqueada' and not ligada_a_aula_do_aluno(user, licao):
                return {'codigo': CODIGO_BLOQUEADA, 'mensagem': MENSAGEM_BLOQUEADA}
            if estado == 'feita' and not definicao(curso, 'pode_repetir'):
                return {'codigo': CODIGO_REPETIR, 'mensagem': MENSAGEM_REPETIR}
            return None
    # Não está no trilho: lição escondida (ainda incompleta).
    return {'codigo': CODIGO_INDISPONIVEL, 'mensagem': 'Esta lição ainda não está disponível.'}
