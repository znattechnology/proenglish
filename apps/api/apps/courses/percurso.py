"""
Percurso de um curso em vídeo: a ordem em que o aluno deve fazer as três peças (aula, laboratório e
conversa com o tutor), e o passo seguinte.

Cada aula (Chapter) dá até quatro tipos de passo, por esta ordem:

  aula          ver o vídeo ou ler a aula (não existe nas aulas do tipo Quiz);
  questionario  o questionário activo da aula (ChapterQuiz.is_active);
  pratica       a lição de laboratório ligada à aula (Chapter.practice_lesson), se os alunos a vêem;
  conversa      as conversas com o tutor ligadas à aula (Situacao.aula), a guiada antes da livre.

Estado de um passo: "feito", "actual" (o primeiro por fazer em todo o curso: é o passo seguinte) ou
"por_fazer".

Unidades de amostra (apps/courses/amostra.py): sem o plano do curso, os passos das secções fora da
amostra (e as lições de laboratório fora das unidades da amostra) vêm com bloqueado = true e nunca
são o passo seguinte. Quando só faltam passos bloqueados, proximo é None e plano_necessario = true. O percurso é uma recomendação: não bloqueia nada (as regras de acesso de cada peça
continuam nos sítios delas).

O que conta como feito é decidido aqui, no servidor:
  - aula: o vídeo foi visto ou a aula está concluída (ChapterProgress);
  - questionario: passou, ou gastou as tentativas (courses/conclusao.py);
  - pratica: todos os exercícios da lição estão concluídos (practice/acesso_licoes.py);
  - conversa: há uma conversa terminada e avaliada (ou a avaliar) nessa situação. Uma chamada que
    não ligou, ou que acabou cedo de mais para ser avaliada, não conta.
"""
import datetime
import math

from django.db.models import Q

AULA = 'aula'
QUESTIONARIO = 'questionario'
PRATICA = 'pratica'
CONVERSA = 'conversa'

FEITO = 'feito'
ACTUAL = 'actual'
POR_FAZER = 'por_fazer'

MINUTOS_PRATICA = 8
MINUTOS_QUESTIONARIO = 5
ORDEM_TIPO_CONVERSA = {'guiada': 0, 'livre': 1}


def _minutos_video(aula):
    if aula.duracao_s:
        return max(1, math.ceil(aula.duracao_s / 60))
    return None


def _situacoes_por_aula(curso):
    from apps.practice.conversa.exame import q_situacao_de_exame
    from apps.practice.models import Situacao

    por_aula = {}
    situacoes = (Situacao.objects.filter(curso=curso, aula__isnull=False, estado=Situacao.ACTIVO)
                 .exclude(q_situacao_de_exame()).order_by('ordem', 'created_at'))
    for s in situacoes:
        por_aula.setdefault(s.aula_id, []).append(s)
    for lista in por_aula.values():
        lista.sort(key=lambda s: ORDEM_TIPO_CONVERSA.get(s.tipo_conversa, 2))
    return por_aula


def _conversas_feitas(user, slugs):
    from apps.practice.models import VapiSession
    if not slugs:
        return set()
    return set(VapiSession.objects.filter(
        user=user, situation__in=list(slugs),
        status__in=(VapiSession.STATUS_AVALIADA, VapiSession.STATUS_A_AVALIAR),
    ).values_list('situation', flat=True))


def _licoes_feitas(user, aulas):
    """{id da lição de prática: feita?} só para as lições que os alunos vêem."""
    from apps.practice.acesso_licoes import estados_das_licoes

    cursos = {}
    for aula in aulas:
        licao = aula.practice_lesson
        if licao is not None:
            cursos[licao.unit.course_id] = licao.unit.course
    estados = {}
    for curso in cursos.values():
        for licao, estado in estados_das_licoes(user, curso):
            estados[licao.id] = estado == 'feita'
    return estados


def _questionarios(user, aulas):
    """{id da aula: feito?} para as aulas com questionário activo."""
    from apps.courses.conclusao import questionario_feito
    from apps.courses.models import ChapterQuiz

    activos = ChapterQuiz.objects.filter(chapter__in=aulas, is_active=True)
    return {q.chapter_id: questionario_feito(user, q) for q in activos}


def _licao_fechada(user, licao, cache):
    """A lição de laboratório está fora das unidades de amostra e a pessoa não tem o plano."""
    from apps.courses import amostra
    curso = licao.unit.course
    if curso.id not in cache:
        cache[curso.id] = amostra.unidades_pratica_bloqueadas(user, curso) or set()
    return licao.unit_id in cache[curso.id]


def _marcar_pratica_anterior(unidades):
    """
    Em cada aula, 'pratica_anterior': o laboratório da aula imediatamente anterior (na ordem do curso,
    mesmo de outra unidade), se ainda está por fazer e o aluno o pode abrir; senão None. Serve para o
    aviso «pratique primeiro» ao abrir a aula seguinte: recomenda, nunca bloqueia. Só a aula anterior,
    para não acumular avisos de aulas antigas.
    """
    anterior = None
    for unidade in unidades:
        for item in unidade['aulas']:
            item['pratica_anterior'] = None
            if anterior is not None:
                passo = next((p for p in anterior['passos'] if p['tipo'] == PRATICA), None)
                if passo and passo['estado'] != FEITO and not passo['bloqueado']:
                    item['pratica_anterior'] = {
                        'aula_id': anterior['id'], 'aula_titulo': anterior['titulo'],
                        'licao_id': passo['licao_id'], 'curso_pratica_id': passo['curso_pratica_id'],
                        'minutos': passo['minutos'],
                    }
            anterior = item


def percurso(user, curso):
    """O percurso do curso para este aluno (ver o topo do módulo)."""
    from apps.courses import amostra
    from apps.courses.models import Chapter, ChapterProgress, CourseSection

    seccoes = list(CourseSection.objects.filter(course=curso).order_by('order', 'created_at'))
    aulas = list(Chapter.objects.filter(section__course=curso)
                 .select_related('practice_lesson__unit__course')
                 .order_by('section__order', 'section__created_at', 'order', 'created_at'))
    progresso = {p.chapter_id: p for p in ChapterProgress.objects.filter(
        user_progress__user=user, user_progress__course=curso)}
    questionarios = _questionarios(user, aulas)
    licoes = _licoes_feitas(user, aulas)
    situacoes = _situacoes_por_aula(curso)
    conversas = _conversas_feitas(user, [s.slug for lista in situacoes.values() for s in lista])

    seccoes_fechadas = amostra.seccoes_bloqueadas(user, curso) or set()
    unidades_fechadas = {}

    aulas_por_seccao = {}
    for aula in aulas:
        aulas_por_seccao.setdefault(aula.section_id, []).append(aula)

    passos_todos = []
    unidades = []
    for seccao in seccoes:
        itens = []
        for aula in aulas_por_seccao.get(seccao.id, []):
            passos = []
            registo = progresso.get(aula.id)
            if aula.type != 'Quiz':
                passos.append({
                    'tipo': AULA, 'titulo': aula.title,
                    'feito': bool(registo and (registo.video_visto or registo.completed)),
                    'minutos': _minutos_video(aula),
                })
            if aula.id in questionarios:
                passos.append({
                    'tipo': QUESTIONARIO, 'titulo': 'Questionário',
                    'feito': questionarios[aula.id], 'minutos': MINUTOS_QUESTIONARIO,
                })
            licao = aula.practice_lesson
            if licao is not None and licao.id in licoes:
                passos.append({
                    'tipo': PRATICA, 'titulo': licao.title, 'feito': licoes[licao.id],
                    'minutos': MINUTOS_PRATICA, 'licao_id': licao.id,
                    'curso_pratica_id': str(licao.unit.course_id),
                })
            for s in situacoes.get(aula.id, []):
                extras = s.extras if isinstance(s.extras, dict) else {}
                passos.append({
                    'tipo': CONVERSA, 'titulo': s.nome, 'feito': s.slug in conversas,
                    'minutos': extras.get('minutos_sugeridos') or s.duracao_min,
                    'situacao': s.slug, 'tipo_conversa': s.tipo_conversa,
                })
            seccao_fechada = seccao.id in seccoes_fechadas
            for i, passo in enumerate(passos):
                passo['chave'] = f"{aula.id}:{passo['tipo']}:{passo.get('situacao') or i}"
                passo['aula_id'] = str(aula.id)
                passo['unidade'] = seccao.sectionTitle
                passo['bloqueado'] = seccao_fechada or (
                    passo['tipo'] == PRATICA and _licao_fechada(user, licao, unidades_fechadas))
            passos_todos.extend(passos)
            itens.append({'id': str(aula.id), 'titulo': aula.title, 'bloqueada': seccao_fechada, 'passos': passos})
        unidades.append({'id': str(seccao.id), 'titulo': seccao.sectionTitle, 'bloqueada': seccao.id in seccoes_fechadas,
                         'aulas': itens})

    proximo = None
    plano_necessario = False
    for passo in passos_todos:
        if passo.pop('feito'):
            passo['estado'] = FEITO
        elif proximo is None and not passo['bloqueado']:
            passo['estado'] = ACTUAL
            proximo = passo
        else:
            passo['estado'] = POR_FAZER
            if passo['bloqueado'] and proximo is None:
                plano_necessario = True
    _marcar_pratica_anterior(unidades)
    feitos = sum(1 for p in passos_todos if p['estado'] == FEITO)
    return {
        'curso': {'id': str(curso.id), 'titulo': curso.title},
        # Unidades de amostra: 'total' | 'amostra' | None, e quantas (apps/courses/amostra.py).
        'acesso': amostra.acesso(user, curso),
        'unidades_amostra': amostra.unidades_amostra(curso),
        'unidades': unidades,
        'proximo': proximo,
        # Só faltam passos fechados pelo plano (unidades de amostra): o "a seguir" é assinar um plano.
        'plano_necessario': proximo is None and plano_necessario,
        'feitos': feitos,
        'total': len(passos_todos),
    }


def cursos_em_curso(user):
    """Os cursos em vídeo que o aluno pode abrir agora, do mais recentemente usado para o mais antigo."""
    from django.utils import timezone

    from apps.courses import ciclo
    from apps.courses.models import Course, CourseEnrollment, UserCourseProgress

    agora = timezone.now()
    inscritos = CourseEnrollment.objects.filter(user=user, is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=agora)).values_list('course_id', flat=True)
    # Com o plano do curso, ou num curso com unidades de amostra (apps/courses/amostra.py).
    from apps.courses import amostra
    cursos = [c for c in Course.objects.filter(ciclo.q_conteudo_aluno(), course_type='video', id__in=list(inscritos))
              if amostra.pode_inscrever(user, c)]
    ultimos = dict(UserCourseProgress.objects.filter(user=user, course__in=cursos)
                   .values_list('course_id', 'lastAccessedTimestamp'))
    antigo = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    cursos.sort(key=lambda c: ultimos.get(c.id) or antigo, reverse=True)
    return cursos


def _curso_do_contexto(licao_id=None, situacao=None):
    """Id do curso em vídeo a que pertence a lição de laboratório ou a conversa que o aluno acabou."""
    import uuid

    from apps.courses.models import Chapter
    from apps.practice.models import Situacao

    if licao_id:
        try:
            licao_id = uuid.UUID(str(licao_id))
        except (ValueError, TypeError):
            return None
        return (Chapter.objects.filter(practice_lesson_id=licao_id)
                .values_list('section__course_id', flat=True).first())
    if situacao:
        return (Situacao.objects.filter(slug=str(situacao)[:40], aula__isnull=False)
                .values_list('curso_id', flat=True).first())
    return None


def proximo_passo(user, licao_id=None, situacao=None):
    """
    O passo seguinte do aluno em toda a plataforma: o primeiro passo por fazer do curso em que
    mexeu mais recentemente (ou, se esse já está todo feito, do seguinte). None se não há nada
    por fazer.

    licao_id / situacao: o que o aluno acabou de fazer (uma lição de laboratório ou uma conversa).
    Se pertence ao percurso de um curso dele, esse curso passa à frente: o "a seguir" continua
    no mesmo curso.
    """
    cursos = cursos_em_curso(user)
    do_contexto = _curso_do_contexto(licao_id, situacao)
    if do_contexto:
        cursos.sort(key=lambda c: c.id != do_contexto)
    for curso in cursos:
        dados = percurso(user, curso)
        if dados['proximo']:
            return {'curso': dados['curso'], 'passo': dados['proximo'],
                    'feitos': dados['feitos'], 'total': dados['total']}
    return None
