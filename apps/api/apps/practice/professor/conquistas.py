"""
Área do professor: conquistas.

  GET    /api/v1/teacher/conquistas/?estado=todas|activas|desligadas
  POST   /api/v1/teacher/conquistas/
  GET    /api/v1/teacher/conquistas/opcoes/
  GET    /api/v1/teacher/conquistas/<id>/
  PATCH  /api/v1/teacher/conquistas/<id>/
  DELETE /api/v1/teacher/conquistas/<id>/      (só se ninguém a tem; senão 409: desligue-a)

Cada professor cria e altera só as suas conquistas, sempre no âmbito dos cursos dele
(regra.curso = um curso dele, ou null = todos os cursos dele). As da plataforma aparecem só
para leitura (minha=false; alterar: 403, só o administrador). As de outros professores: 404.
Uma conquista de professor só conta a actividade nos cursos dela (achievement_utils).
alunos_que_tem conta só os alunos dos cursos do professor.
"""
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.practice.achievement_utils import TIPOS_PROFESSOR
from apps.practice.actividade import alunos_dos_cursos
from apps.practice.models import Achievement, UserAchievement

from .comum import (
    PERMISSOES, _erro, corpo, curso_api, cursos_do_professor, e_minha, erro_sem_permissao,
    erro_validacao, inteiro, ler_curso, obter_visivel, texto,
)

RARIDADES = [('comum', 'Comum', 'common'), ('rara', 'Rara', 'rare'),
             ('epica', 'Épica', 'epic'), ('lendaria', 'Lendária', 'legendary')]
RARIDADE_API = {modelo: api for api, _, modelo in RARIDADES}
RARIDADE_MODELO = {api: modelo for api, _, modelo in RARIDADES}
# Tipos das conquistas da plataforma -> tipo da API (os outros passam como estão).
TIPO_PLATAFORMA = {'lessons_completed': 'licoes', 'streak_days': 'dias_seguidos', 'points_earned': 'pontos'}
FRASES = {
    'conversas': ('Terminar 1 conversa avaliada com o tutor', 'Terminar {n} conversas avaliadas com o tutor'),
    'licoes': ('Concluir 1 lição', 'Concluir {n} lições'),
    'dias_seguidos': ('Praticar 1 dia', 'Praticar {n} dias seguidos'),
    'pontos': ('Ganhar 1 ponto', 'Ganhar {n} pontos'),
    'palavras': ('Dizer 1 palavra nas conversas com o tutor', 'Dizer {n} palavras nas conversas com o tutor'),
    'challenges_completed': ('Completar 1 exercício', 'Completar {n} exercícios'),
}
# As conversas não pertencem a um curso: contam as situações da plataforma e as do professor
# (achievement_utils.ambito_conquista).
TIPOS_CONVERSA = ('conversas', 'palavras')


def como_se_ganha(tipo, meta, curso=None, do_professor=True):
    frases = FRASES.get(tipo)
    if frases is None:
        base = f'Chegar a {meta}'
    else:
        base = (frases[0] if meta == 1 else frases[1]).format(n=meta)
    if tipo in TIPOS_CONVERSA and do_professor:
        if curso is not None:
            return (f'{base}, nas situações da plataforma, nas gerais do professor e nas do curso '
                    f'«{curso.title}» (conta quem é aluno deste curso)')
        return f'{base}, nas situações da plataforma e nas do professor (conta quem é aluno dos cursos dele)'
    return f'{base} no curso «{curso.title}»' if curso is not None else base


def _tipo_api(a):
    return TIPO_PLATAFORMA.get(a.requirement_type, a.requirement_type) if a.criado_por_id is None \
        else a.requirement_type


def _visiveis(request):
    return Achievement.objects.filter(Q(criado_por__isnull=True) | Q(criado_por=request.user))


def _alunos(request):
    return alunos_dos_cursos([c.id for c in cursos_do_professor(request.user)])


def _contagens(conquistas, alunos):
    return {r['achievement_id']: r['n'] for r in UserAchievement.objects.filter(
        achievement__in=conquistas, is_unlocked=True, user_id__in=list(alunos))
        .values('achievement_id').annotate(n=Count('id'))}


def _item(request, a, contagens):
    tipo = _tipo_api(a)
    return {
        'id': str(a.id),
        'nome': a.title,
        'descricao': a.description,
        'icone': a.icon,
        'regra': {'tipo': tipo, 'meta': a.requirement_target, 'curso': curso_api(a.curso)},
        'como_se_ganha': como_se_ganha(tipo, a.requirement_target, a.curso, a.criado_por_id is not None),
        'raridade': RARIDADE_API.get(a.rarity, 'comum'),
        'pontos': a.points,
        'alunos_que_tem': contagens.get(a.id, 0),
        'activa': a.is_active,
        'minha': e_minha(request, a),
    }


def _validar(request, dados, parcial, erros):
    limpos = {}

    def quer(campo):
        return not parcial or campo in dados

    if quer('nome'):
        limpos['title'] = texto(dados, 'nome', erros, 3, 40, 'o nome da conquista')
    if quer('descricao'):
        limpos['description'] = texto(dados, 'descricao', erros, 3, 120, 'a descrição')
    if quer('icone'):
        icone = dados.get('icone')
        if not isinstance(icone, str) or not icone.strip():
            erros['icone'] = 'Indique o ícone (até 3 caracteres, por exemplo "7" ou "★").'
        elif len(icone.strip()) > 3:
            erros['icone'] = 'O ícone pode ter no máximo 3 caracteres.'
        else:
            limpos['icon'] = icone.strip()
    if quer('regra'):
        regra = dados.get('regra')
        if not isinstance(regra, dict):
            erros['regra'] = 'Indique a regra: tipo, meta e curso.'
        else:
            tipo = regra.get('tipo')
            if tipo not in TIPOS_PROFESSOR:
                erros['regra.tipo'] = 'Escolha o tipo: conversas, lições, dias seguidos, pontos ou palavras.'
            meta = inteiro(regra, 'meta', erros, 1, 10000, 'A meta tem de ser um número inteiro de 1 a 10 000.')
            if 'meta' in erros:
                erros['regra.meta'] = erros.pop('meta')
            sub = {}
            curso = ler_curso(request, regra.get('curso'), sub)
            if sub:
                erros['regra.curso'] = sub['curso']
            if not any(k.startswith('regra') for k in erros):
                nome, unidade, categoria = TIPOS_PROFESSOR[tipo]
                limpos.update({'requirement_type': tipo, 'requirement_target': meta, 'curso': curso,
                               'requirement_unit': unidade, 'category': categoria})
    if quer('raridade'):
        valor = dados.get('raridade', 'comum' if not parcial else None)
        if valor not in RARIDADE_MODELO:
            erros['raridade'] = 'Escolha a raridade: comum, rara, épica ou lendária.'
        else:
            limpos['rarity'] = RARIDADE_MODELO[valor]
    if quer('pontos'):
        limpos['points'] = inteiro(dados, 'pontos', erros, 5, 500, 'Os pontos têm de ser um número de 5 a 500.')
    if 'activa' in dados or not parcial:
        valor = dados.get('activa', True)
        if not isinstance(valor, bool):
            erros['activa'] = 'Indique se a conquista está activa (true ou false).'
        else:
            limpos['is_active'] = valor
    if not parcial and 'raridade' not in dados:
        limpos['rarity'] = 'common'
        erros.pop('raridade', None)
    return {k: v for k, v in limpos.items() if v is not None or k == 'curso'}


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def lista(request):
    if request.method == 'POST':
        return _criar(request)
    estado = request.query_params.get('estado') or 'todas'
    if estado not in ('todas', 'activas', 'desligadas'):
        return _erro('Estado inválido. Use todas, activas ou desligadas.', 'estado_invalido',
                     details={'estado': estado})
    qs = _visiveis(request).select_related('curso')
    if estado == 'activas':
        qs = qs.filter(is_active=True)
    elif estado == 'desligadas':
        qs = qs.filter(is_active=False)
    conquistas = list(qs)
    conquistas.sort(key=lambda a: (a.criado_por_id is None, -a.created_at.timestamp() if a.criado_por_id else a.order))
    contagens = _contagens(conquistas, _alunos(request))
    return Response({'resultados': [_item(request, a, contagens) for a in conquistas]})


def _criar(request):
    dados = corpo(request)
    erros = {}
    limpos = _validar(request, dados, False, erros)
    if erros:
        return erro_validacao(erros)
    a = Achievement.objects.create(criado_por=request.user, **limpos)
    return Response(_item(request, a, {}), status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def detalhe(request, conquista_id):
    a = obter_visivel(request, Achievement.objects.select_related('curso'), conquista_id, 'Conquista não encontrada.')
    if request.method == 'GET':
        return Response(_item(request, a, _contagens([a], _alunos(request))))
    proibido = erro_sem_permissao(request, a)
    if proibido:
        return proibido
    if request.method == 'DELETE':
        if UserAchievement.objects.filter(achievement=a, is_unlocked=True).exists():
            return _erro('Há alunos que já ganharam esta conquista, por isso não pode ser apagada. '
                         'Para deixar de a atribuir, desligue-a.', 'tem_alunos', 409)
        a.delete()
        return Response(status=204)
    dados = corpo(request)
    if a.criado_por_id is None and 'regra' in dados:
        return _erro('A regra das conquistas da plataforma não se muda aqui.', 'regra_plataforma', 400)
    erros = {}
    limpos = _validar(request, dados, True, erros)
    if erros:
        return erro_validacao(erros)
    for campo, valor in limpos.items():
        setattr(a, campo, valor)
    a.save()
    return Response(_item(request, a, _contagens([a], _alunos(request))))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def opcoes(request):
    return Response({
        'tipos': [{'valor': v, 'nome': nome, 'unidade': unidade} for v, (nome, unidade, _) in TIPOS_PROFESSOR.items()],
        'raridades': [{'valor': api, 'nome': nome} for api, nome, _ in RARIDADES],
        'cursos': [curso_api(c) for c in cursos_do_professor(request.user)],
    })
