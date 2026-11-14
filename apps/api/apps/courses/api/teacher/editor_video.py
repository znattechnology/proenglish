"""
Editor de cursos em vídeo da área do professor (base nova).

  GET    /api/v1/teacher/cursos/opcoes/[?tipo=video|pratica]   {areas:[{valor,nome}], niveis:[{valor,nome,descricao}]}
  POST   /api/v1/teacher/cursos/                               cria um curso (sempre rascunho)
  GET    /api/v1/teacher/cursos/<id>/estrutura/                {curso, seccoes:[{..., aulas:[...]}]}
  POST   /api/v1/teacher/cursos/<id>/seccoes/                  {titulo}
  POST   /api/v1/teacher/cursos/<id>/seccoes/ordem/            {ids:[...]}
  PATCH  /api/v1/teacher/seccoes/<id>/                         {titulo}
  DELETE /api/v1/teacher/seccoes/<id>/
  POST   /api/v1/teacher/seccoes/<id>/aulas/                   {titulo}
  POST   /api/v1/teacher/seccoes/<id>/aulas/ordem/             {ids:[...]}
  PATCH  /api/v1/teacher/aulas/<id>/                           {titulo, resumo, percentagem_vista, duracao_s, seccao,
                                                                licao_pratica: <id de lição> | null}
  GET    /api/v1/teacher/cursos/<id>/licoes-pratica/           lições dos cursos de prática do professor do curso
                                                               {cursos:[{id, titulo, estado, unidades:[{id, titulo, licoes:[{id, titulo}]}]}]}
  DELETE /api/v1/teacher/aulas/<id>/
  GET    /api/v1/teacher/aulas/<id>/questionario/
  PUT    /api/v1/teacher/aulas/<id>/questionario/              substitui o questionário inteiro
  DELETE /api/v1/teacher/materiais/<id>/

Só o professor dono do curso (ou um administrador); para os outros o recurso não existe (404).

Num curso publicado (ou em revisão) as alterações valem logo para os alunos, por isso as que o
deixariam a falhar a lista de verificação (apagar a última aula, um questionário activo com menos
de 3 perguntas, ...) são recusadas com 409 code "quebra_curso" (cursos.guardar_publicado).
Uma aula nova fica escondida dos alunos até ter vídeo.
Os envios de ficheiros (vídeo, materiais, capa) estão em envios.py.

O questionário de uma aula fica em Chapter.quiz_data (o formato que o aluno lê:
apps/courses/api/student/video_courses/conteudo.py) e o ChapterQuiz é sincronizado com
apps.courses.questionarios.sincronizar_questionario.
"""
import os
import uuid
from urllib.parse import unquote, urlparse

from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo, niveis
from apps.courses.models import Chapter, ChapterResource, Course, CourseSection
from apps.courses.tempo_video import duracao_do_video

from .cursos import ACESSO_API, PERMISSOES, _curso_do_professor, _erro, detalhe_curso, guardar_publicado

TITULO_CURSO_MAX = 60
TITULO_MAX = 200
NOTA_MINIMA_OMISSAO = 70
PONTOS_POR_PERGUNTA = 10
LETRAS = 'abcde'

ACESSO = {'todos': 'free', 'premium': 'premium'}

# Modelo visual dos cursos de prática a partir da área.
TEMPLATE_PRATICA = {
    'Oil & Gas': 'oil-gas', 'Banking': 'banking', 'Technology': 'technology',
    'Executive': 'executive', 'AI Enhanced': 'ai-personal', 'General': 'general',
}


# ---------------------------------------------------------------------------
# Ajudas
# ---------------------------------------------------------------------------

def _dados(request):
    return request.data if isinstance(request.data, dict) else {}


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else ''


def _validacao(erros):
    primeiro = next(iter(erros.values()))[0]
    return _erro(primeiro, 'validation_error', details=erros)


def _tocar(curso_id):
    """O curso mudou (estrutura ou conteúdo): actualiza a data, como no PATCH do curso."""
    Course.objects.filter(pk=curso_id).update(updated_at=timezone.now())


def _curso_video(request, curso_id):
    curso = _curso_do_professor(request, curso_id)
    if curso.course_type == 'practice':
        raise _TipoErrado()
    return curso


class _TipoErrado(Exception):
    pass


def _resposta_tipo_errado():
    return _erro('Esta acção só existe para cursos em vídeo.', 'tipo_invalido')


def _seccao_do_professor(request, seccao_id):
    seccao = CourseSection.objects.select_related('course').filter(id=seccao_id).first()
    if seccao is None or not ciclo.e_dono_ou_staff(request.user, seccao.course):
        raise NotFound('Secção não encontrada.')
    return seccao


def _aula_do_professor(request, aula_id):
    aula = Chapter.objects.select_related('section__course').filter(id=aula_id).first()
    if aula is None or not ciclo.e_dono_ou_staff(request.user, aula.section.course):
        raise NotFound('Aula não encontrada.')
    return aula


def _material_do_professor(request, material_id):
    material = ChapterResource.objects.select_related('chapter__section__course').filter(id=material_id).first()
    if material is None or not ciclo.e_dono_ou_staff(request.user, material.chapter.section.course):
        raise NotFound('Material não encontrado.')
    return material


def _ids(valor):
    if not isinstance(valor, list) or not all(isinstance(i, str) for i in valor):
        return None
    try:
        return [str(uuid.UUID(i)) for i in valor]
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Representações
# ---------------------------------------------------------------------------

TIPO_MATERIAL = {
    'PDF': 'pdf', 'AUDIO': 'audio', 'IMAGE': 'imagem', 'WORKSHEET': 'folha', 'LINK': 'ligacao',
    'VIDEO': 'video', 'CODE': 'documento',
}


def material_dict(m):
    url = m.external_url or (m.file.url if m.file else '')
    return {
        'id': str(m.id),
        'nome': m.title,
        'url': url,
        'tamanho_bytes': m.file_size,
        'tipo': TIPO_MATERIAL.get(m.resource_type, 'documento'),
    }


def _nome_do_url(url):
    caminho = urlparse(url).path if url else ''
    return unquote(os.path.basename(caminho)) or None


def perguntas_do_quiz(quiz_data):
    """quiz_data (formato do aluno) -> [{id, enunciado, opcoes, correcta, explicacao}]."""
    if not isinstance(quiz_data, dict):
        return []
    saida = []
    for q in quiz_data.get('questions') or []:
        if not isinstance(q, dict):
            continue
        opcoes = [o for o in q.get('options') or []]
        textos, correcta = [], 0
        for i, o in enumerate(opcoes):
            if isinstance(o, dict):
                textos.append(str(o.get('text') or ''))
                if o.get('isCorrect') or (q.get('correctOptionId') is not None
                                          and str(o.get('id')) == str(q.get('correctOptionId'))):
                    correcta = i
            else:
                textos.append(str(o))
        saida.append({
            'id': str(q.get('id') or ''),
            'enunciado': str(q.get('question') or q.get('text') or ''),
            'opcoes': textos,
            'correcta': correcta,
            'explicacao': str(q.get('explanation') or ''),
        })
    return saida


def _nota_minima(chapter):
    dados = chapter.quiz_data if isinstance(chapter.quiz_data, dict) else {}
    definicoes = dados.get('settings') if isinstance(dados.get('settings'), dict) else {}
    try:
        return int(definicoes.get('passingScore'))
    except (TypeError, ValueError):
        return NOTA_MINIMA_OMISSAO


def _quiz_activo(chapter):
    return bool(chapter.quiz_enabled or chapter.type == 'Quiz')


def resumo_questionario(chapter):
    from apps.courses.questionarios import perguntas_validas
    return {
        'activo': _quiz_activo(chapter),
        'perguntas': len(perguntas_validas(chapter.quiz_data)),
        'nota_minima': _nota_minima(chapter),
    }


def aula_dict(chapter, materiais=None):
    if materiais is None:
        materiais = list(chapter.resources.filter(is_active=True).order_by('order', 'created_at'))
    video = None
    if chapter.video:
        video = {
            'url': chapter.video,
            'nome': chapter.video_nome or _nome_do_url(chapter.video),
            'tamanho_bytes': chapter.video_tamanho,
        }
    return {
        'id': str(chapter.id),
        'titulo': chapter.title,
        'ordem': chapter.order,
        'tipo': chapter.type,
        'seccao': str(chapter.section_id),
        'video': video,
        # Uma aula sem vídeo fica escondida dos alunos até o vídeo ser carregado.
        'visivel_alunos': ciclo.aula_visivel(chapter),
        'duracao_s': chapter.duracao_s or duracao_do_video(chapter),
        'percentagem_vista': chapter.percentagem_vista,
        'resumo': chapter.content or '',
        'materiais': [material_dict(m) for m in materiais],
        'questionario': resumo_questionario(chapter),
        'licao_pratica': licao_pratica_dict(chapter.practice_lesson) if chapter.practice_lesson_id else None,
    }


def licao_pratica_dict(licao):
    """A "lição de prática a seguir a esta aula" (Chapter.practice_lesson)."""
    unidade = licao.unit
    curso = unidade.course
    return {
        'id': str(licao.id),
        'titulo': licao.title,
        'unidade': {'id': str(unidade.id), 'titulo': unidade.title},
        'curso': {'id': str(curso.id), 'titulo': curso.title, 'estado': ciclo.estado(curso)},
    }


def _licoes_pratica_do_professor(professor_id):
    from apps.practice.models import PracticeLesson
    return PracticeLesson.objects.filter(unit__course__course_type='practice',
                                         unit__course__teacher_id=professor_id)


def seccao_dict(seccao, aulas=None):
    if aulas is None:
        aulas = _aulas_com_materiais(Chapter.objects.filter(section=seccao))
    return {
        'id': str(seccao.id),
        'titulo': seccao.sectionTitle,
        'ordem': seccao.order,
        'aulas': [aula_dict(a, list(a.resources.all())) for a in aulas],
    }


def _aulas_com_materiais(qs):
    return list(qs.order_by('order', 'created_at').select_related(
        'practice_lesson__unit__course').prefetch_related(
        Prefetch('resources', queryset=ChapterResource.objects.filter(is_active=True).order_by('order', 'created_at'))))


def detalhe_com_acesso(curso):
    # detalhe_curso já inclui o acesso; mantido pelo nome usado noutros módulos.
    return detalhe_curso(curso)


# ---------------------------------------------------------------------------
# Opções e criação
# ---------------------------------------------------------------------------

def opcoes_areas(tipo='video'):
    """
    Áreas válidas para o tipo de curso, uma por valor guardado. Alguns valores antigos têm o mesmo
    rótulo de outro ('Technology English' e 'Technical English' são ambos "Tecnologia"): vêm
    marcados com legado=true, para o formulário os mostrar só quando são o valor actual do curso.
    """
    chaves = ciclo.AREAS_PRATICA if tipo == 'pratica' else ciclo.AREAS_VIDEO
    rotulos, saida = set(), []
    for chave in dict.fromkeys(chaves):
        nome = ciclo.AREAS[chave]
        item = {'valor': chave, 'nome': nome}
        if nome in rotulos:
            item['legado'] = True
        saida.append(item)
        rotulos.add(nome)
    return saida


@api_view(['GET'])
@permission_classes(PERMISSOES)
def opcoes(request):
    tipo = request.query_params.get('tipo') or 'video'
    if tipo not in ('video', 'pratica'):
        return _erro('Tipo inválido. Use "video" ou "pratica".', 'tipo_invalido', details={'tipo': tipo})
    return Response({
        'areas': opcoes_areas(tipo),
        'niveis': niveis.opcoes(),
    })


def _area_de_entrada(valor, course_type):
    """Valor guardado ou rótulo -> chave do tipo de curso; None se não for uma área conhecida."""
    valor = _texto(valor)
    if not valor:
        return None
    rotulo = ciclo.AREAS.get(valor, valor)
    chave = ciclo.categoria_de_entrada(rotulo, course_type)
    return chave if chave in ciclo.AREAS else None


def criar_curso(request):
    dados = _dados(request)
    erros = {}
    tipo = dados.get('tipo')
    if tipo not in ('video', 'pratica'):
        erros['tipo'] = ['Escolha o tipo de curso: "video" ou "pratica".']
    course_type = 'practice' if tipo == 'pratica' else 'video'

    titulo = _texto(dados.get('titulo'))
    if len(titulo) < 3 or len(titulo) > TITULO_CURSO_MAX:
        erros['titulo'] = [f'O título deve ter entre 3 e {TITULO_CURSO_MAX} caracteres.']
    descricao = _texto(dados.get('descricao'))
    area = _area_de_entrada(dados.get('area'), course_type)
    if not area:
        erros['area'] = ['Escolha a área do curso.']
    nivel = ciclo.nivel_de_entrada(_texto(dados.get('nivel')))
    if not nivel:
        erros['nivel'] = ['Nível inválido. Escolha um nível de A1 a C2.']
    acesso = dados.get('acesso', 'todos')
    if acesso not in ACESSO:
        erros['acesso'] = ['Escolha o acesso: "todos" ou "premium".']

    chave_lista = 'unidades' if course_type == 'practice' else 'seccoes'
    outra = 'seccoes' if course_type == 'practice' else 'unidades'
    lista = dados.get(chave_lista) or []
    if not isinstance(lista, list) or not all(isinstance(t, str) for t in lista):
        erros[chave_lista] = ['Envie uma lista de títulos.']
        lista = []
    titulos = [t.strip() for t in lista if t.strip()]
    if any(len(t) > TITULO_MAX for t in titulos):
        erros[chave_lista] = [f'Cada título pode ter até {TITULO_MAX} caracteres.']
    if dados.get(outra) and tipo in ('video', 'pratica'):
        erros[outra] = ['Os cursos em vídeo têm secções; os de prática têm unidades.']
    if erros:
        return _validacao(erros)

    with transaction.atomic():
        curso = Course.objects.create(
            teacher=request.user, teacherName=request.user.name or '', title=titulo, description=descricao,
            category=area, level=nivel, course_type=course_type, access_level=ACESSO[acesso],
            status=ciclo.RASCUNHO, is_featured=False,
            template=TEMPLATE_PRATICA.get(area, 'general') if course_type == 'practice' else 'general',
        )
        if course_type == 'practice':
            from apps.practice.models import PracticeUnit
            PracticeUnit.objects.bulk_create([
                PracticeUnit(course=curso, title=t, description='', order=i)
                for i, t in enumerate(titulos, start=1)])
        else:
            CourseSection.objects.bulk_create([
                CourseSection(course=curso, sectionTitle=t, order=i) for i, t in enumerate(titulos, start=1)])
    return Response(detalhe_com_acesso(curso), status=201)


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def estrutura(request, curso_id):
    try:
        curso = _curso_video(request, curso_id)
    except _TipoErrado:
        return _resposta_tipo_errado()
    seccoes = list(CourseSection.objects.filter(course=curso).order_by('order', 'created_at'))
    aulas = _aulas_com_materiais(Chapter.objects.filter(section__course=curso))
    por_seccao = {}
    for a in aulas:
        por_seccao.setdefault(a.section_id, []).append(a)
    return Response({
        'curso': detalhe_com_acesso(curso),
        'seccoes': [seccao_dict(s, por_seccao.get(s.id, [])) for s in seccoes],
    })


# ---------------------------------------------------------------------------
# Secções
# ---------------------------------------------------------------------------

def _titulo_valido(dados, erros, obrigatorio=True):
    if 'titulo' not in dados:
        if obrigatorio:
            erros['titulo'] = ['Indique o título.']
        return None
    titulo = _texto(dados.get('titulo'))
    if not titulo or len(titulo) > TITULO_MAX:
        erros['titulo'] = [f'O título deve ter entre 1 e {TITULO_MAX} caracteres.']
        return None
    return titulo


@api_view(['POST'])
@permission_classes(PERMISSOES)
def criar_seccao(request, curso_id):
    try:
        curso = _curso_video(request, curso_id)
    except _TipoErrado:
        return _resposta_tipo_errado()
    erros = {}
    titulo = _titulo_valido(_dados(request), erros)
    if erros:
        return _validacao(erros)
    with transaction.atomic():
        Course.objects.select_for_update().filter(pk=curso.pk).first()
        ultima = CourseSection.objects.filter(course=curso).aggregate(m=Max('order'))['m'] or 0
        seccao = CourseSection.objects.create(course=curso, sectionTitle=titulo, order=ultima + 1)
        _tocar(curso.pk)
    return Response(seccao_dict(seccao, []), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def seccao(request, seccao_id):
    seccao = _seccao_do_professor(request, seccao_id)
    if request.method == 'DELETE':
        from .envios import apagar_depois_do_commit, ficheiros_da_aula

        def _apagar():
            ficheiros = [u for a in Chapter.objects.filter(section=seccao) for u in ficheiros_da_aula(a)]
            seccao.delete()
            _tocar(seccao.course_id)
            apagar_depois_do_commit(ficheiros)
            return Response(status=204)
        return guardar_publicado(seccao.course, _apagar)
    erros = {}
    titulo = _titulo_valido(_dados(request), erros)
    if erros:
        return _validacao(erros)
    seccao.sectionTitle = titulo
    seccao.save(update_fields=['sectionTitle', 'updated_at'])
    _tocar(seccao.course_id)
    return Response(seccao_dict(seccao))


def _ordenar(objectos, ids, rotulo):
    """objectos: lista actual; ids: nova ordem. Devolve None ou a resposta de erro."""
    if ids is None:
        return _erro('Envie a lista completa de ids pela nova ordem.', 'validation_error',
                     details={'ids': ['Lista de ids inválida.']})
    actuais = {str(o.id) for o in objectos}
    if len(ids) != len(set(ids)) or set(ids) != actuais:
        return _erro(f'A lista tem de ter todas as {rotulo}, cada uma uma vez.', 'ordem_invalida',
                     details={'ids': [f'Envie exactamente as {rotulo} existentes.']})
    por_id = {str(o.id): o for o in objectos}
    mudados = []
    for i, oid in enumerate(ids, start=1):
        o = por_id[oid]
        if o.order != i:
            o.order = i
            mudados.append(o)
    if mudados:
        type(mudados[0]).objects.bulk_update(mudados, ['order'])
    return None


@api_view(['POST'])
@permission_classes(PERMISSOES)
def ordenar_seccoes(request, curso_id):
    try:
        curso = _curso_video(request, curso_id)
    except _TipoErrado:
        return _resposta_tipo_errado()
    with transaction.atomic():
        seccoes = list(CourseSection.objects.select_for_update().filter(course=curso))
        erro = _ordenar(seccoes, _ids(_dados(request).get('ids')), 'secções')
        if erro:
            return erro
        _tocar(curso.pk)
    seccoes.sort(key=lambda s: s.order)
    aulas = _aulas_com_materiais(Chapter.objects.filter(section__course=curso))
    por_seccao = {}
    for a in aulas:
        por_seccao.setdefault(a.section_id, []).append(a)
    return Response({'seccoes': [seccao_dict(s, por_seccao.get(s.id, [])) for s in seccoes]})


# ---------------------------------------------------------------------------
# Aulas
# ---------------------------------------------------------------------------

def _proxima_ordem(seccao):
    return (Chapter.objects.filter(section=seccao).aggregate(m=Max('order'))['m'] or 0) + 1


@api_view(['POST'])
@permission_classes(PERMISSOES)
def criar_aula(request, seccao_id):
    seccao = _seccao_do_professor(request, seccao_id)
    erros = {}
    titulo = _titulo_valido(_dados(request), erros)
    if erros:
        return _validacao(erros)
    with transaction.atomic():
        CourseSection.objects.select_for_update().filter(pk=seccao.pk).first()
        aula = Chapter.objects.create(section=seccao, title=titulo, content='', type='Video',
                                      order=_proxima_ordem(seccao))
        _tocar(seccao.course_id)
    return Response(aula_dict(aula, []), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def aula(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    curso_id = aula.section.course_id
    if request.method == 'DELETE':
        from .envios import apagar_depois_do_commit, ficheiros_da_aula

        def _apagar():
            ficheiros = ficheiros_da_aula(aula)
            aula.delete()
            _tocar(curso_id)
            apagar_depois_do_commit(ficheiros)
            return Response(status=204)
        return guardar_publicado(aula.section.course, _apagar)

    dados = _dados(request)
    erros, campos = {}, []
    titulo = _titulo_valido(dados, erros, obrigatorio=False)
    if titulo:
        aula.title = titulo
        campos.append('title')
    if 'resumo' in dados:
        if dados['resumo'] is not None and not isinstance(dados['resumo'], str):
            erros['resumo'] = ['O resumo tem de ser texto.']
        else:
            aula.content = (dados['resumo'] or '').strip()
            campos.append('content')
    if 'percentagem_vista' in dados:
        valor = dados['percentagem_vista']
        if isinstance(valor, bool) or valor not in (50, 80, 100):
            erros['percentagem_vista'] = ['Escolha 50, 80 ou 100.']
        else:
            aula.percentagem_vista = valor
            campos.append('percentagem_vista')
    if 'duracao_s' in dados:
        valor = dados['duracao_s']
        if valor is None:
            aula.duracao_s = None
            campos.append('duracao_s')
        elif isinstance(valor, bool) or not isinstance(valor, (int, float)) or not (1 <= valor <= 24 * 3600):
            erros['duracao_s'] = ['Indique a duração em segundos (entre 1 e 86400).']
        else:
            aula.duracao_s = int(round(valor))
            campos.append('duracao_s')
    destino = None
    if 'seccao' in dados:
        try:
            destino_id = uuid.UUID(str(dados['seccao']))
        except ValueError:
            destino_id = None
        destino = CourseSection.objects.filter(id=destino_id, course_id=curso_id).first() if destino_id else None
        if destino is None:
            erros['seccao'] = ['Escolha uma secção deste curso.']
    if 'licao_pratica' in dados:
        valor = dados['licao_pratica']
        if valor in (None, ''):
            aula.practice_lesson = None
            campos.append('practice_lesson')
        else:
            try:
                licao_id = uuid.UUID(str(valor))
            except ValueError:
                licao_id = None
            # Só lições de cursos de prática do mesmo professor (o dono do curso em vídeo).
            licao = (_licoes_pratica_do_professor(aula.section.course.teacher_id)
                     .select_related('unit__course').filter(id=licao_id).first() if licao_id else None)
            if licao is None:
                erros['licao_pratica'] = ['Escolha uma lição de um dos seus cursos de prática.']
            else:
                aula.practice_lesson = licao
                campos.append('practice_lesson')
    if erros:
        return _validacao(erros)

    curso = aula.section.course

    def _gravar():
        if destino is not None and destino.id != aula.section_id:
            CourseSection.objects.select_for_update().filter(pk=destino.pk).first()
            aula.section = destino
            aula.order = _proxima_ordem(destino)
            campos.extend(['section', 'order'])
        if campos:
            aula.save(update_fields=list(dict.fromkeys(campos)) + ['updated_at'])
            _tocar(curso_id)
        return Response(aula_dict(aula))
    return guardar_publicado(curso, _gravar)


@api_view(['GET'])
@permission_classes(PERMISSOES)
def licoes_pratica(request, curso_id):
    """Lições que se podem ligar às aulas deste curso: as dos cursos de prática do mesmo professor."""
    from apps.practice.models import PracticeLesson, PracticeUnit
    try:
        curso = _curso_video(request, curso_id)
    except _TipoErrado:
        return _resposta_tipo_errado()
    cursos = (Course.objects.filter(course_type='practice', teacher_id=curso.teacher_id)
              .order_by('title').prefetch_related(
                  Prefetch('practice_units', queryset=PracticeUnit.objects.order_by('order').prefetch_related(
                      Prefetch('lessons', queryset=PracticeLesson.objects.order_by('order'))))))
    return Response({'cursos': [{
        'id': str(c.id),
        'titulo': c.title,
        'estado': ciclo.estado(c),
        'unidades': [{
            'id': str(u.id),
            'titulo': u.title,
            'licoes': [{'id': str(l.id), 'titulo': l.title} for l in u.lessons.all()],
        } for u in c.practice_units.all()],
    } for c in cursos]})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def ordenar_aulas(request, seccao_id):
    seccao = _seccao_do_professor(request, seccao_id)
    with transaction.atomic():
        aulas = list(Chapter.objects.select_for_update().filter(section=seccao))
        erro = _ordenar(aulas, _ids(_dados(request).get('ids')), 'aulas da secção')
        if erro:
            return erro
        _tocar(seccao.course_id)
    return Response(seccao_dict(seccao))


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------

@api_view(['DELETE'])
@permission_classes(PERMISSOES)
def material(request, material_id):
    m = _material_do_professor(request, material_id)
    from .envios import apagar_depois_do_commit
    curso_id = m.chapter.section.course_id
    with transaction.atomic():
        url = m.external_url or (m.file.url if m.file else '')
        m.delete()
        _tocar(curso_id)
        apagar_depois_do_commit([url])
    return Response(status=204)


# ---------------------------------------------------------------------------
# Questionário
# ---------------------------------------------------------------------------

def questionario_dict(chapter):
    return {
        'activo': _quiz_activo(chapter),
        'nota_minima': _nota_minima(chapter),
        'perguntas': perguntas_do_quiz(chapter.quiz_data),
    }


def _validar_questionario(dados):
    erros = {}
    activo = dados.get('activo', True)
    if not isinstance(activo, bool):
        erros['activo'] = ['Indique verdadeiro ou falso.']
    nota = dados.get('nota_minima', NOTA_MINIMA_OMISSAO)
    if isinstance(nota, bool) or not isinstance(nota, int) or not (0 <= nota <= 100):
        erros['nota_minima'] = ['Indique uma nota mínima entre 0 e 100.']
    perguntas = dados.get('perguntas', [])
    if not isinstance(perguntas, list):
        erros['perguntas'] = ['Envie a lista de perguntas.']
        perguntas = []
    limpas, por_pergunta = [], {}
    for i, p in enumerate(perguntas):
        problemas = []
        if not isinstance(p, dict):
            por_pergunta[str(i)] = ['Pergunta inválida.']
            continue
        enunciado = _texto(p.get('enunciado'))
        if not enunciado:
            problemas.append('Escreva o enunciado.')
        opcoes = p.get('opcoes')
        if not isinstance(opcoes, list) or not all(isinstance(o, str) for o in opcoes):
            problemas.append('As opções têm de ser uma lista de textos.')
            opcoes = []
        opcoes = [o.strip() for o in opcoes]
        if not (2 <= len(opcoes) <= 5):
            problemas.append('Cada pergunta tem de ter entre 2 e 5 opções.')
        elif any(not o for o in opcoes):
            problemas.append('Nenhuma opção pode ficar vazia.')
        correcta = p.get('correcta')
        if isinstance(correcta, bool) or not isinstance(correcta, int) or not (0 <= correcta < max(len(opcoes), 1)):
            problemas.append('Escolha a opção correcta.')
        explicacao = p.get('explicacao') or ''
        if not isinstance(explicacao, str):
            problemas.append('A explicação tem de ser texto.')
            explicacao = ''
        if problemas:
            por_pergunta[str(i)] = problemas
            continue
        limpas.append({'id': _texto(p.get('id')) if isinstance(p.get('id'), str) else '',
                       'enunciado': enunciado, 'opcoes': opcoes, 'correcta': correcta,
                       'explicacao': explicacao.strip()})
    if por_pergunta:
        erros['perguntas'] = por_pergunta
    if not erros and activo and not limpas:
        erros['perguntas'] = ['Um questionário activo precisa de pelo menos uma pergunta.']
    return erros, activo, nota, limpas


def _primeira_mensagem(erros):
    valor = next(iter(erros.values()))
    if isinstance(valor, dict):
        n, msgs = next(iter(valor.items()))
        return f'Pergunta {int(n) + 1}: {msgs[0]}'
    return valor[0]


@api_view(['GET', 'PUT'])
@permission_classes(PERMISSOES)
def questionario(request, aula_id):
    chapter = _aula_do_professor(request, aula_id)
    if request.method == 'GET':
        return Response(questionario_dict(chapter))

    erros, activo, nota, perguntas = _validar_questionario(_dados(request))
    if erros:
        return _erro(_primeira_mensagem(erros), 'validation_error', details=erros)

    anterior = chapter.quiz_data if isinstance(chapter.quiz_data, dict) else {}
    pontos_antigos = {str(q.get('id')): q.get('points') for q in anterior.get('questions') or [] if isinstance(q, dict)}
    usados, questoes = set(), []
    for p in perguntas:
        qid = p['id'] if p['id'] and p['id'] not in usados else uuid.uuid4().hex[:12]
        usados.add(qid)
        opcoes = [{'id': LETRAS[i], 'text': t, 'isCorrect': i == p['correcta']} for i, t in enumerate(p['opcoes'])]
        questoes.append({
            'id': qid,
            'type': 'multiple-choice',
            'question': p['enunciado'],
            'options': opcoes,
            'correctOptionId': LETRAS[p['correcta']],
            'explanation': p['explicacao'],
            'points': pontos_antigos.get(qid) or PONTOS_POR_PERGUNTA,
        })
    definicoes = dict(anterior.get('settings') or {}) if isinstance(anterior.get('settings'), dict) else {}
    definicoes['passingScore'] = nota
    chapter.quiz_data = {**anterior, 'title': anterior.get('title') or chapter.title,
                         'settings': definicoes, 'questions': questoes}
    chapter.quiz_enabled = activo
    if not activo and chapter.type == 'Quiz':
        # Uma aula do tipo Quiz tem sempre o questionário ligado; desligar passa-a a aula normal.
        chapter.type = 'Video' if chapter.video else 'Text'
    from apps.courses.questionarios import sincronizar_questionario

    def _gravar():
        chapter.save(update_fields=['quiz_data', 'quiz_enabled', 'type', 'updated_at'])
        sincronizar_questionario(chapter)
        _tocar(chapter.section.course_id)
        return Response(questionario_dict(chapter))
    return guardar_publicado(chapter.section.course, _gravar)
