"""
Editor de cursos de prática da área do professor (base nova).

  GET    /api/v1/teacher/pratica/<curso>/estrutura/              {curso, unidades:[{..., licoes:[...]}]}
  POST   /api/v1/teacher/pratica/<curso>/unidades/               {titulo, descricao?}
  POST   /api/v1/teacher/pratica/<curso>/unidades/ordem/         {ids}
  PATCH  /api/v1/teacher/pratica/unidades/<id>/                  {titulo?, descricao?}
  DELETE /api/v1/teacher/pratica/unidades/<id>/
  POST   /api/v1/teacher/pratica/unidades/<id>/licoes/           {titulo}
  POST   /api/v1/teacher/pratica/unidades/<id>/licoes/ordem/     {ids}
  POST   /api/v1/teacher/pratica/unidades/<id>/licoes/com-exercicios/  {titulo, exercicios:[...]}
  PATCH  /api/v1/teacher/pratica/licoes/<id>/                    {titulo?, unidade?} (mudar de unidade põe-na no fim)
  DELETE /api/v1/teacher/pratica/licoes/<id>/
  GET    /api/v1/teacher/pratica/licoes/<id>/exercicios/
  POST   /api/v1/teacher/pratica/licoes/<id>/exercicios/         exercício (sem id) -> 201
  POST   /api/v1/teacher/pratica/licoes/<id>/exercicios/ordem/   {ids}
  PUT    /api/v1/teacher/pratica/exercicios/<id>/                substitui o exercício
  DELETE /api/v1/teacher/pratica/exercicios/<id>/
  POST   /api/v1/teacher/pratica/exercicios/<id>/audio/          gera o áudio de referência da frase

Só o professor dono do curso (ou um administrador); para os outros o recurso não existe (404).

Curso publicado ou em revisão (_com_guarda): as alterações ficam logo visíveis aos alunos, por
isso recusa-se (409 code "quebra_curso", details.problemas = [texto]) o que deixaria incompleta
uma lição que os alunos vêem: apagar a última lição de uma unidade ou a última unidade, ficar com
menos de 3 exercícios, guardar um exercício inválido (p.ex. escuta sem áudio: nesses cursos tenta-se
gerar o áudio da frase automaticamente). Lições novas ficam escondidas aos alunos até estarem
completas (apps.practice.acesso_licoes). Exercícios de conversa já não se criam (400).
O formato dos exercícios e a tradução para o modelo estão em pratica_formato.py; a geração com
o Claude em gerar_licao.py.
"""
import logging
import uuid

from django.db import transaction
from django.db.models import Count, F, Max, Prefetch, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo
from apps.courses.models import Course
from apps.practice.models import (
    ChallengeAttempt, ChallengeOption, PracticeChallenge, PracticeLesson, PracticeUnit,
)

from . import pratica_formato as formato
from .cursos import PERMISSOES, _curso_do_professor, _erro, detalhe_curso

logger = logging.getLogger(__name__)

TITULO_MAX = 200
DESCRICAO_MAX = 2000
MAX_EXERCICIOS_LICAO = 30
DESLOCAMENTO = 100000  # para reordenar sem violar unique_together (x, order)


# ---------------------------------------------------------------------------
# Ajudas
# ---------------------------------------------------------------------------

def _dados(request):
    return request.data if isinstance(request.data, dict) else {}


def _validacao(erros, code='validation_error'):
    primeiro = next(iter(erros.values()))[0]
    return _erro(primeiro, code, details=erros)


def _tocar(curso_id):
    Course.objects.filter(pk=curso_id).update(updated_at=timezone.now())


def _curso_pratica(request, curso_id):
    curso = _curso_do_professor(request, curso_id)
    if curso.course_type != 'practice':
        return curso, _erro('Esta acção só existe para cursos de prática.', 'tipo_invalido')
    return curso, None


def unidade_do_professor(request, unidade_id):
    unidade = PracticeUnit.objects.select_related('course').filter(id=unidade_id).first()
    if unidade is None or not ciclo.e_dono_ou_staff(request.user, unidade.course):
        raise NotFound('Unidade não encontrada.')
    return unidade


def _licao_do_professor(request, licao_id):
    licao = PracticeLesson.objects.select_related('unit__course').filter(id=licao_id).first()
    if licao is None or not ciclo.e_dono_ou_staff(request.user, licao.unit.course):
        raise NotFound('Lição não encontrada.')
    return licao


def _exercicio_do_professor(request, exercicio_id):
    ch = PracticeChallenge.objects.select_related('lesson__unit__course').filter(id=exercicio_id).first()
    if ch is None or not ciclo.e_dono_ou_staff(request.user, ch.lesson.unit.course):
        raise NotFound('Exercício não encontrado.')
    return ch


def _titulo(valor, erros, campo='titulo', minimo=2):
    titulo = ' '.join(valor.split()) if isinstance(valor, str) else ''
    if len(titulo) < minimo or len(titulo) > TITULO_MAX:
        erros[campo] = [f'O título deve ter entre {minimo} e {TITULO_MAX} caracteres.']
        return None
    return titulo


def _ids(valor):
    if not isinstance(valor, list) or not all(isinstance(i, str) for i in valor):
        return None
    try:
        return [str(uuid.UUID(i)) for i in valor]
    except ValueError:
        return None


def _reordenar(modelo, filtro, ids_novos):
    """Põe os objectos de `filtro` pela ordem de `ids_novos` (1..n) sem violar a unicidade."""
    modelo.objects.filter(**filtro).update(order=F('order') + DESLOCAMENTO)
    for i, oid in enumerate(ids_novos, start=1):
        modelo.objects.filter(pk=oid).update(order=i)


def _compactar(modelo, filtro):
    ids = list(modelo.objects.filter(**filtro).order_by('order', 'created_at').values_list('id', flat=True))
    _reordenar(modelo, filtro, ids)


def _ordenar(request, modelo, filtro, rotulo):
    ids = _ids(_dados(request).get('ids'))
    if ids is None:
        return _erro('Envie a lista completa de ids pela nova ordem.', 'validation_error',
                     details={'ids': ['Lista de ids inválida.']})
    actuais = {str(i) for i in modelo.objects.select_for_update().filter(**filtro).values_list('id', flat=True)}
    if len(ids) != len(set(ids)) or set(ids) != actuais:
        return _erro(f'A lista tem de ter todas as {rotulo}, cada uma uma vez.', 'ordem_invalida',
                     details={'ids': [f'Envie exactamente as {rotulo} existentes.']})
    _reordenar(modelo, filtro, ids)
    return None


def _proxima(modelo, filtro):
    return (modelo.objects.filter(**filtro).aggregate(m=Max('order'))['m'] or 0) + 1


# ---------------------------------------------------------------------------
# Curso publicado / em revisão: não deixar partir o que os alunos vêem
# ---------------------------------------------------------------------------

class _QuebraCurso(Exception):
    def __init__(self, problemas):
        super().__init__('quebra_curso')
        self.problemas = problemas


def _protegido(curso):
    return curso.status in (ciclo.PUBLICADO, ciclo.EM_REVISAO)


def _foto(curso):
    """Estado das lições do curso: {licoes: {id: {...}}, unidades: {id: titulo}}."""
    from apps.practice.acesso_licoes import ids_escondidas

    curso = Course.objects.get(pk=curso.pk)  # aprovado_em actual
    licoes = list(
        PracticeLesson.objects.filter(unit__course=curso).select_related('unit').prefetch_related(
            Prefetch('challenges', queryset=PracticeChallenge.objects.order_by('order')),
            Prefetch('challenges__options', queryset=ChallengeOption.objects.order_by('order')),
        )
    )
    escondidas = ids_escondidas(curso, licoes)
    foto = {'licoes': {}, 'unidades': dict(PracticeUnit.objects.filter(course=curso).values_list('id', 'title'))}
    for l in licoes:
        chs = list(l.challenges.all())
        invalidos = {}
        for ch in chs:
            ok, motivo = ciclo.exercicio_valido(ch, list(ch.options.all()))
            if not ok:
                frase = ' '.join((ch.question or formato.NOMES.get(formato.TIPO_API.get(ch.type), ch.type)).split())
                invalidos[ch.id] = (frase[:60], motivo)
        foto['licoes'][l.id] = {'unidade': l.unit_id, 'titulo': l.title, 'n': len(chs),
                                'invalidos': invalidos, 'visivel': l.id not in escondidas}
    return foto


def _problemas(antes, depois):
    """O que a alteração parte nas lições que os alunos viam (lista de textos pt-PT)."""
    from apps.practice.acesso_licoes import MINIMO_EXERCICIOS

    visiveis = {lid: d for lid, d in antes['licoes'].items() if d['visivel']}
    if not visiveis:
        return []
    problemas = []
    for lid, d in visiveis.items():
        dd = depois['licoes'].get(lid)
        if dd is None:
            continue
        if dd['n'] < MINIMO_EXERCICIOS <= d['n']:
            problemas.append(f'a lição "{dd["titulo"]}" ficava com menos de {MINIMO_EXERCICIOS} exercícios')
        for chid, (frase, motivo) in dd['invalidos'].items():
            if chid not in d['invalidos']:
                problemas.append(f'o exercício "{frase}" da lição "{dd["titulo"]}" ficava incompleto ({motivo})')
    for uid in {d['unidade'] for d in visiveis.values()}:
        if uid in depois['unidades'] and not any(
                dd['visivel'] and dd['unidade'] == uid for dd in depois['licoes'].values()):
            problemas.append(f'a unidade "{depois["unidades"][uid]}" ficava sem lições')
    if not any(dd['visivel'] for dd in depois['licoes'].values()):
        problemas.append('o curso ficava sem lições')
    return list(dict.fromkeys(problemas))


def _resposta_quebra(curso, problemas):
    onde = 'publicado' if curso.status == ciclo.PUBLICADO else 'em revisão'
    lista = '; '.join(problemas[:5]) + (f' e mais {len(problemas) - 5}' if len(problemas) > 5 else '')
    mensagem = (f'Este curso está {onde} e os alunos vêem as alterações logo. Esta alteração não foi feita '
                f'porque {lista}. Corrija primeiro ou arquive o curso.')
    return _erro(mensagem, 'quebra_curso', 409, details={'problemas': problemas})


def _com_guarda(curso, alterar):
    """
    Corre alterar() numa transacção. Num curso publicado ou em revisão, se a alteração partir uma
    lição que os alunos vêem (ver _problemas), desfaz tudo e devolve 409 "quebra_curso".
    """
    if not _protegido(curso):
        with transaction.atomic():
            return alterar()
    try:
        with transaction.atomic():
            antes = _foto(curso)
            resultado = alterar()
            if getattr(resultado, 'status_code', 200) < 400:
                problemas = _problemas(antes, _foto(curso))
                if problemas:
                    raise _QuebraCurso(problemas)
            return resultado
    except _QuebraCurso as e:
        return _resposta_quebra(curso, e.problemas)


def _audio_automatico(request, ch):
    """
    Num curso publicado / em revisão, uma escuta sem áudio partiria a lição: tenta gerar o áudio
    da frase (TTS). Se o serviço de voz falhar, fica sem áudio e a guarda decide.
    """
    if ch.type != 'LISTENING' or (ch.reference_audio_url or '').strip():
        return
    frase = (formato.para_normalizado(ch)['frase'] or '').strip()
    if not frase:
        return
    bytes_audio = gerar_audio_tts(frase[:500])
    if not bytes_audio:
        return
    try:
        url = _guardar_audio(request, ch, bytes_audio)
    except Exception as e:
        logger.warning('pratica: não foi possível guardar o áudio de %s: %s', ch.id, e)
        return
    PracticeChallenge.objects.filter(pk=ch.pk).update(reference_audio_url=url)
    ch.reference_audio_url = url


def sem_audio(exercicios):
    """Ids dos exercícios de escuta sem áudio (o aluno salta-os; a lista de verificação recusa-os)."""
    return [e['id'] for e in exercicios if e.get('tipo') == 'escuta' and not e.get('audio_url')]


def _pct(certas, total):
    return round(certas * 100 / total) if total else None


# ---------------------------------------------------------------------------
# Representações
# ---------------------------------------------------------------------------

def _tentativas_por_exercicio(filtro):
    return {r['challenge_id']: (r['t'], r['c']) for r in
            ChallengeAttempt.objects.filter(**filtro).values('challenge_id')
            .annotate(t=Count('id'), c=Count('id', filter=Q(is_correct=True)))}


def _licoes_dicts(licoes):
    """[PracticeLesson] -> {lesson_id: dict}, com poucas consultas."""
    ids = [l.id for l in licoes]
    exercicios = {}
    for ch in PracticeChallenge.objects.filter(lesson_id__in=ids).order_by('order').values('lesson_id', 'type'):
        exercicios.setdefault(ch['lesson_id'], []).append(ch['type'])
    stats = {r['challenge__lesson_id']: (r['t'], r['c']) for r in
             ChallengeAttempt.objects.filter(challenge__lesson_id__in=ids).values('challenge__lesson_id')
             .annotate(t=Count('id'), c=Count('id', filter=Q(is_correct=True)))}
    saida = {}
    for l in licoes:
        tipos = []
        for t in exercicios.get(l.id, []):
            nome = formato.NOMES.get(formato.TIPO_API.get(t), t)
            if nome not in tipos:
                tipos.append(nome)
        t, c = stats.get(l.id, (0, 0))
        saida[l.id] = {
            'id': str(l.id), 'titulo': l.title, 'ordem': l.order,
            'exercicios': len(exercicios.get(l.id, [])), 'tipos': tipos,
            'acerto': _pct(c, t), 'tentativas': t,
        }
    return saida


def licao_dict(licao):
    return _licoes_dicts([licao])[licao.id]


def unidade_dict(u, licoes=None):
    if licoes is None:
        licoes = list(PracticeLesson.objects.filter(unit=u).order_by('order'))
    dicts = _licoes_dicts(licoes)
    return {'id': str(u.id), 'titulo': u.title, 'descricao': u.description or '', 'ordem': u.order,
            'licoes': [dicts[l.id] for l in licoes]}


def exercicio_dict(ch, stats=None):
    ex = formato.para_normalizado(ch)
    if stats is None:
        stats = _tentativas_por_exercicio({'challenge_id': ch.id})
    t, c = stats.get(ch.id, (0, 0))
    ex['acerto'] = _pct(c, t)
    ex['tentativas'] = t
    return ex


def _exercicios_da_licao(licao):
    chs = list(PracticeChallenge.objects.filter(lesson=licao).order_by('order')
               .prefetch_related(Prefetch('options', queryset=ChallengeOption.objects.order_by('order'))))
    stats = _tentativas_por_exercicio({'challenge__lesson': licao})
    return [exercicio_dict(ch, stats) for ch in chs]


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def estrutura(request, curso_id):
    curso, erro = _curso_pratica(request, curso_id)
    if erro:
        return erro
    unidades = list(PracticeUnit.objects.filter(course=curso).order_by('order'))
    licoes = list(PracticeLesson.objects.filter(unit__course=curso).order_by('order'))
    dicts = _licoes_dicts(licoes)
    por_unidade = {}
    for l in licoes:
        por_unidade.setdefault(l.unit_id, []).append(dicts[l.id])
    return Response({
        'curso': detalhe_curso(curso),
        'unidades': [{'id': str(u.id), 'titulo': u.title, 'descricao': u.description or '', 'ordem': u.order,
                      'licoes': por_unidade.get(u.id, [])} for u in unidades],
    })


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

def _descricao(valor, erros):
    if valor is None:
        return ''
    if not isinstance(valor, str):
        erros['descricao'] = ['A descrição tem de ser texto.']
        return ''
    if len(valor.strip()) > DESCRICAO_MAX:
        erros['descricao'] = [f'A descrição pode ter no máximo {DESCRICAO_MAX} caracteres.']
    return valor.strip()


@api_view(['POST'])
@permission_classes(PERMISSOES)
def criar_unidade(request, curso_id):
    curso, erro = _curso_pratica(request, curso_id)
    if erro:
        return erro
    dados, erros = _dados(request), {}
    titulo = _titulo(dados.get('titulo'), erros)
    descricao = _descricao(dados.get('descricao'), erros)
    if erros:
        return _validacao(erros)
    with transaction.atomic():
        Course.objects.select_for_update().filter(pk=curso.pk).first()
        unidade = PracticeUnit.objects.create(course=curso, title=titulo, description=descricao,
                                              order=_proxima(PracticeUnit, {'course': curso}))
        _tocar(curso.pk)
    return Response(unidade_dict(unidade, []), status=201)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def ordenar_unidades(request, curso_id):
    curso, erro = _curso_pratica(request, curso_id)
    if erro:
        return erro
    with transaction.atomic():
        erro = _ordenar(request, PracticeUnit, {'course': curso}, 'unidades')
        if erro:
            return erro
        _tocar(curso.pk)
    unidades = list(PracticeUnit.objects.filter(course=curso).order_by('order'))
    licoes = list(PracticeLesson.objects.filter(unit__course=curso).order_by('order'))
    por_unidade = {}
    for l in licoes:
        por_unidade.setdefault(l.unit_id, []).append(l)
    return Response({'unidades': [unidade_dict(u, por_unidade.get(u.id, [])) for u in unidades]})


@api_view(['PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def unidade(request, unidade_id):
    u = unidade_do_professor(request, unidade_id)
    if request.method == 'DELETE':
        curso_id = u.course_id

        def apagar():
            u.delete()
            _compactar(PracticeUnit, {'course_id': curso_id})
            _tocar(curso_id)
            return Response(status=204)
        return _com_guarda(u.course, apagar)
    dados, erros, campos = _dados(request), {}, []
    if 'titulo' in dados:
        titulo = _titulo(dados.get('titulo'), erros)
        if titulo:
            u.title = titulo
            campos.append('title')
    if 'descricao' in dados:
        u.description = _descricao(dados.get('descricao'), erros)
        campos.append('description')
    if erros:
        return _validacao(erros)
    if campos:
        u.save(update_fields=campos + ['updated_at'])
        _tocar(u.course_id)
    return Response(unidade_dict(u))


# ---------------------------------------------------------------------------
# Lições
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes(PERMISSOES)
def criar_licao(request, unidade_id):
    u = unidade_do_professor(request, unidade_id)
    erros = {}
    titulo = _titulo(_dados(request).get('titulo'), erros)
    if erros:
        return _validacao(erros)
    with transaction.atomic():
        PracticeUnit.objects.select_for_update().filter(pk=u.pk).first()
        licao = PracticeLesson.objects.create(unit=u, title=titulo, order=_proxima(PracticeLesson, {'unit': u}))
        _tocar(u.course_id)
    return Response(licao_dict(licao), status=201)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def ordenar_licoes(request, unidade_id):
    u = unidade_do_professor(request, unidade_id)
    with transaction.atomic():
        erro = _ordenar(request, PracticeLesson, {'unit': u}, 'lições')
        if erro:
            return erro
        _tocar(u.course_id)
    return Response(unidade_dict(u))


@api_view(['PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def licao(request, licao_id):
    l = _licao_do_professor(request, licao_id)
    curso_id = l.unit.course_id
    curso = l.unit.course
    if request.method == 'DELETE':
        unidade_id = l.unit_id

        def apagar():
            l.delete()
            _compactar(PracticeLesson, {'unit_id': unidade_id})
            _tocar(curso_id)
            return Response(status=204)
        return _com_guarda(curso, apagar)

    dados, erros = _dados(request), {}
    titulo = _titulo(dados.get('titulo'), erros) if 'titulo' in dados else None
    destino = None
    if dados.get('unidade') not in (None, ''):
        destino_id = _ids([dados.get('unidade')]) if isinstance(dados.get('unidade'), str) else None
        destino = (PracticeUnit.objects.filter(id=destino_id[0], course_id=curso_id).first()
                   if destino_id else None)
        if destino is None:
            erros['unidade'] = ['Escolha uma unidade deste curso.']
    if erros:
        return _validacao(erros)

    def alterar():
        campos = []
        if titulo:
            l.title = titulo
            campos.append('title')
        if destino is not None and destino.id != l.unit_id:
            origem = l.unit_id
            PracticeUnit.objects.select_for_update().filter(pk=destino.pk).first()
            l.unit = destino
            l.order = _proxima(PracticeLesson, {'unit': destino})
            campos += ['unit', 'order']
            l.save(update_fields=campos + ['updated_at'])
            _compactar(PracticeLesson, {'unit_id': origem})
            campos = []
        if campos:
            l.save(update_fields=campos + ['updated_at'])
        _tocar(curso_id)
        return None
    erro = _com_guarda(curso, alterar)
    if erro is not None:
        return erro
    l.refresh_from_db()
    d = licao_dict(l)
    d['unidade'] = {'id': str(l.unit_id), 'titulo': l.unit.title, 'ordem': l.unit.order}
    return Response(d)


def criar_exercicios(licao, limpos, primeira_ordem):
    """Cria os exercícios (já validados) na lição, a partir de `primeira_ordem`."""
    criados = []
    for i, limpo in enumerate(limpos):
        ch = PracticeChallenge(lesson=licao, order=primeira_ordem + i)
        formato.guardar(ch, limpo)
        criados.append(ch)
    return criados


@api_view(['POST'])
@permission_classes(PERMISSOES)
def criar_licao_com_exercicios(request, unidade_id):
    """Cria a lição e todos os exercícios de uma vez (tudo ou nada). Usado depois de gerar com a IA."""
    u = unidade_do_professor(request, unidade_id)
    dados, erros = _dados(request), {}
    titulo = _titulo(dados.get('titulo'), erros)
    lista = dados.get('exercicios')
    limpos = []
    if not isinstance(lista, list) or not lista:
        erros['exercicios'] = ['Envie pelo menos um exercício.']
    elif len(lista) > MAX_EXERCICIOS_LICAO:
        erros['exercicios'] = [f'Uma lição pode ter no máximo {MAX_EXERCICIOS_LICAO} exercícios.']
    else:
        por_exercicio = {}
        for i, ex in enumerate(lista):
            limpo, e = formato.validar(ex)
            if e:
                por_exercicio[str(i)] = e
            else:
                limpos.append(limpo)
        if por_exercicio:
            n = min(int(k) for k in por_exercicio) + 1
            msgs = next(iter(por_exercicio[str(n - 1)].values()))
            return _erro(f'O exercício {n} tem um problema: {msgs[0]}', 'validation_error',
                         details={'exercicios': por_exercicio})
    if erros:
        return _validacao(erros)
    with transaction.atomic():
        PracticeUnit.objects.select_for_update().filter(pk=u.pk).first()
        licao_nova = PracticeLesson.objects.create(unit=u, title=titulo,
                                                   order=_proxima(PracticeLesson, {'unit': u}))
        criar_exercicios(licao_nova, limpos, 1)
        _tocar(u.course_id)
    exercicios_novos = _exercicios_da_licao(licao_nova)
    # sem_audio: escutas ainda sem áudio de referência; o editor deve pedir para o gerar (a lição só
    # aparece aos alunos de um curso publicado quando estiver completa).
    return Response({'licao': licao_dict(licao_nova), 'exercicios': exercicios_novos,
                     'sem_audio': sem_audio(exercicios_novos)}, status=201)


# ---------------------------------------------------------------------------
# Exercícios
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def exercicios(request, licao_id):
    l = _licao_do_professor(request, licao_id)
    curso = l.unit.course
    if request.method == 'GET':
        return Response({
            'licao': {'id': str(l.id), 'titulo': l.title,
                      'unidade': {'id': str(l.unit_id), 'titulo': l.unit.title, 'ordem': l.unit.order}},
            'curso': {'id': str(curso.id), 'titulo': curso.title},
            'exercicios': _exercicios_da_licao(l),
        })
    limpo, erros = formato.validar(_dados(request))
    if erros:
        return _validacao(erros)

    def criar():
        PracticeLesson.objects.select_for_update().filter(pk=l.pk).first()
        if PracticeChallenge.objects.filter(lesson=l).count() >= MAX_EXERCICIOS_LICAO:
            return _erro(f'Uma lição pode ter no máximo {MAX_EXERCICIOS_LICAO} exercícios.', 'limite_exercicios')
        ch = criar_exercicios(l, [limpo], _proxima(PracticeChallenge, {'lesson': l}))[0]
        if _protegido(curso):
            _audio_automatico(request, ch)
        _tocar(curso.pk)
        return Response(exercicio_dict(ch), status=201)
    return _com_guarda(curso, criar)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def ordenar_exercicios(request, licao_id):
    l = _licao_do_professor(request, licao_id)
    with transaction.atomic():
        erro = _ordenar(request, PracticeChallenge, {'lesson': l}, 'perguntas da lição')
        if erro:
            return erro
        _tocar(l.unit.course_id)
    return Response({'exercicios': _exercicios_da_licao(l)})


@api_view(['PUT', 'DELETE'])
@permission_classes(PERMISSOES)
def exercicio(request, exercicio_id):
    ch = _exercicio_do_professor(request, exercicio_id)
    curso_id = ch.lesson.unit.course_id
    curso = ch.lesson.unit.course
    if request.method == 'DELETE':
        licao_id = ch.lesson_id

        def apagar():
            ch.delete()
            _compactar(PracticeChallenge, {'lesson_id': licao_id})
            _tocar(curso_id)
            return Response(status=204)
        return _com_guarda(curso, apagar)
    limpo, erros = formato.validar(_dados(request))
    if erros:
        return _validacao(erros)

    def alterar():
        formato.guardar(ch, limpo)
        if _protegido(curso):
            _audio_automatico(request, ch)
        _tocar(curso_id)
        return Response(exercicio_dict(PracticeChallenge.objects.get(pk=ch.pk)))
    return _com_guarda(curso, alterar)


# ---------------------------------------------------------------------------
# Áudio de referência (TTS)
# ---------------------------------------------------------------------------

def _guardar_audio(request, ch, audio):
    """Guarda o mp3 (S3 em produção, MEDIA_ROOT em desenvolvimento) e devolve o URL público."""
    from .envios import _caminho_local, _s3, url_local, url_publico, usa_s3
    from django.conf import settings

    chave = f'reference-audio/{ch.id}/{uuid.uuid4().hex[:8]}.mp3'
    if usa_s3():
        _s3().put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=chave, Body=audio, ContentType='audio/mpeg')
        return url_publico(chave)
    caminho = _caminho_local(chave)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(audio)
    return url_local(request, chave)


def gerar_audio_tts(texto):
    """Bytes mp3 da frase, ou b'' se o serviço de voz falhar (sem chave, sem créditos, rede...)."""
    try:
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer
        return AIPronunciationAnalyzer().generate_reference_audio_sync(text=texto) or b''
    except Exception as e:  # o cliente OpenAI pode falhar logo ao criar
        logger.warning('pratica: TTS falhou: %s', e)
        return b''


@api_view(['POST'])
@permission_classes(PERMISSOES)
def audio(request, exercicio_id):
    ch = _exercicio_do_professor(request, exercicio_id)
    ex = formato.para_normalizado(ch)
    if ex['tipo'] not in ('escuta', 'pronuncia'):
        return _erro('Só os exercícios de escuta e de pronúncia têm áudio de referência.', 'tipo_invalido')
    frase = (ex['frase'] or '').strip()
    if not frase:
        return _erro('Escreva primeiro a frase do exercício.', 'validation_error',
                     details={'frase': ['Escreva a frase que vai ser lida.']})
    bytes_audio = gerar_audio_tts(frase[:500])
    if not bytes_audio:
        return _erro('Não foi possível gerar o áudio agora: o serviço de voz não está disponível. '
                     'Tente mais tarde ou indique o endereço de um áudio gravado por si.',
                     'audio_indisponivel', status_http=503)
    try:
        url = _guardar_audio(request, ch, bytes_audio)
    except Exception as e:
        logger.warning('pratica: não foi possível guardar o áudio de %s: %s', ch.id, e)
        return _erro('O áudio foi gerado mas não foi possível guardá-lo. Tente outra vez.',
                     'audio_indisponivel', status_http=503)
    PracticeChallenge.objects.filter(pk=ch.pk).update(reference_audio_url=url, updated_at=timezone.now())
    _tocar(ch.lesson.unit.course_id)
    return Response(exercicio_dict(PracticeChallenge.objects.get(pk=ch.pk)))
