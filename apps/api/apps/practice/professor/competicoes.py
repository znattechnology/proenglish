"""
Área do professor: competições.

  GET    /api/v1/teacher/competicoes/
  POST   /api/v1/teacher/competicoes/
  GET    /api/v1/teacher/competicoes/<id>/
  PATCH  /api/v1/teacher/competicoes/<id>/
  DELETE /api/v1/teacher/competicoes/<id>/                 (só agendadas)
  GET    /api/v1/teacher/competicoes/<id>/classificacao/   (50 primeiros)

O professor cria competições para os cursos dele (cursos vazio = todos os cursos dele, também
os que criar depois). Prémios: certificado de mérito ou medalha; um mês de plano só o
administrador. Os alunos desses cursos participam automaticamente (ver apps/practice/competicoes.py).
Alterar: datas, métrica e cursos só enquanto agendada; depois de começar só nome e prémio;
terminada não se altera. Competições da plataforma: só leitura (minha=false).

numeros: sobre as competições activas do próprio professor (ver _numeros).
"""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.courses import ciclo
from apps.practice import actividade, competicoes as comp
from apps.practice.models import Competition

from .comum import (
    PERMISSOES, _erro, corpo, curso_api, cursos_do_professor, e_minha, erro_sem_permissao,
    erro_validacao, inteiro, ler_curso, obter_visivel, texto,
)

MAX_DIAS = 31


def _hoje():
    return timezone.localtime(timezone.now(), comp.FUSO).date()


def _ler_data(dados, campo, erros, rotulo):
    valor = dados.get(campo)
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        pass
    erros[campo] = f'Indique a data de {rotulo} no formato AAAA-MM-DD.'
    return None


def _cursos_item(c):
    if c.criado_por_id and c.todos_os_cursos:
        # Os cursos que contam agora (comp.cursos_ids): sem rascunhos nem cursos fechados.
        from apps.courses.models import Course
        return [curso_api(x) for x in Course.objects.filter(id__in=comp.cursos_ids(c)).order_by('title')]
    return [curso_api(x) for x in c.cursos.all()]


def _tempo_decorrido(c, agora):
    total = (c.end_date - c.start_date).total_seconds()
    if total <= 0 or agora <= c.start_date:
        return 0
    return min(100, round((agora - c.start_date).total_seconds() * 100 / total))


def _item(request, c, agora, participantes=None):
    if participantes is None:
        participantes = len(comp.participantes_ids(c))
    return {
        'id': str(c.id),
        'nome': c.title,
        'cursos': _cursos_item(c),
        'todos_os_cursos': bool(c.todos_os_cursos or (c.criado_por_id is None and not c.cursos.exists())),
        'estado': comp.estado(c, agora),
        'conta': c.conta,
        'inicio': comp.dia_inicio(c).isoformat(),
        'fim': comp.dia_fim(c).isoformat(),
        'participantes': participantes,
        'premio': c.premio,
        'premio_lugares': c.premio_lugares,
        'tempo_decorrido': _tempo_decorrido(c, agora),
        'minha': e_minha(request, c),
    }


def _numeros(activas, agora):
    """
    Números das competições activas do professor (cada aluno conta uma vez, mesmo que esteja
    em várias):
    - participantes: alunos que participam em pelo menos uma;
    - media_pontos: média de pontos por participante ganhos na semana actual (segunda a
      domingo, hora de Luanda), nos cursos dessas competições (participantes sem pontos contam 0);
    - pct_activos: % de participantes com actividade nesses cursos (pontos, respostas, vídeo)
      ou uma conversa com o tutor nos últimos 7 dias;
    - media_dias_seguidos: média, por participante, da maior sequência de dias seguidos com
      actividade nesses cursos desde o início da competição mais antiga.
    """
    from apps.practice.liga import limites_semana
    from apps.practice.models import VapiSession

    hoje = _hoje()
    domingo = hoje + timedelta(days=6 - hoje.weekday())
    participantes = set()
    cursos_todos = set()
    plataforma = False
    for c in activas:
        cursos = comp.cursos_ids(c)
        participantes |= comp.participantes_ids(c, cursos)
        if cursos is None:
            plataforma = True
        else:
            cursos_todos |= set(cursos)
    numeros = {
        'activas': len(activas),
        'terminam_esta_semana': sum(1 for c in activas if comp.dia_fim(c) <= domingo),
        'participantes': len(participantes),
        'pct_activos': None,
        'media_pontos': None,
        'media_dias_seguidos': None,
    }
    if not participantes:
        return numeros
    cursos = None if plataforma else cursos_todos
    n = len(participantes)
    inicio_semana, fim_semana = limites_semana(agora)
    pontos = actividade.valores('pontos', participantes, cursos, inicio_semana, min(fim_semana, agora))
    desde = agora - timedelta(days=7)
    activos = {u for u, dias in actividade.dias_activos(participantes, cursos, desde, agora).items() if dias}
    activos |= set(VapiSession.objects.filter(user_id__in=list(participantes), created_at__gte=desde,
                                              status__in=VapiSession.STATUS_TERMINADAS)
                   .values_list('user_id', flat=True))
    inicio = min(c.start_date for c in activas)
    dias = actividade.valores('dias_seguidos', participantes, cursos, inicio, agora)
    numeros.update({
        'pct_activos': round(len(activos & participantes) * 100 / n),
        'media_pontos': round(sum(pontos.values()) / n),
        'media_dias_seguidos': round(sum(dias.values()) / n, 1),
    })
    return numeros


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def lista(request):
    if request.method == 'POST':
        return _criar(request)
    agora = timezone.now()
    qs = (Competition.objects.filter(Q(criado_por=request.user) | Q(criado_por__isnull=True))
          .prefetch_related('cursos').order_by('-start_date'))
    competicoes = list(qs)
    minhas_activas = [c for c in competicoes if e_minha(request, c) and comp.estado(c, agora) == 'activa']
    ordem = {'activa': 0, 'agendada': 1, 'terminada': 2}
    competicoes.sort(key=lambda c: (ordem[comp.estado(c, agora)], not e_minha(request, c)))
    return Response({
        'numeros': _numeros(minhas_activas, agora),
        'resultados': [_item(request, c, agora) for c in competicoes],
    })


def _validar(request, dados, c, erros):
    """Valores finais (a competição `c` existente ou None) e o que mudou."""
    limpos = {}
    parcial = c is not None
    if not parcial or 'nome' in dados:
        limpos['title'] = texto(dados, 'nome', erros, 3, 60, 'o nome da competição')
    if not parcial or 'cursos' in dados:
        ids = dados.get('cursos', [])
        if ids is None:
            ids = []
        if not isinstance(ids, list):
            erros['cursos'] = 'Os cursos têm de ser uma lista (vazia = todos os seus cursos).'
        else:
            cursos = []
            for cid in ids:
                sub = {}
                curso = ler_curso(request, cid, sub)
                if sub or curso is None:
                    erros['cursos'] = sub.get('curso') or 'Escolha um dos seus cursos.'
                    break
                cursos.append(curso)
            if 'cursos' not in erros:
                if not cursos and not ciclo.e_staff(request.user) and not cursos_do_professor(request.user):
                    erros['cursos'] = 'Ainda não tem cursos: crie um curso antes de criar uma competição.'
                limpos['cursos'] = cursos
    if not parcial or 'conta' in dados:
        if dados.get('conta') not in comp.NOME_CONTA:
            erros['conta'] = 'Escolha o que conta: lições, pontos, minutos de conversa ou dias seguidos.'
        else:
            limpos['conta'] = dados['conta']
    if not parcial or 'premio' in dados:
        premio = dados.get('premio')
        if premio not in comp.NOME_PREMIO:
            erros['premio'] = 'Escolha o prémio: certificado de mérito ou medalha.'
        elif premio == Competition.PREMIO_PLANO and not ciclo.e_staff(request.user):
            erros['premio'] = 'O prémio «um mês de plano» só pode ser dado pelo administrador.'
        else:
            limpos['premio'] = premio
    if not parcial or 'premio_lugares' in dados:
        limpos['premio_lugares'] = inteiro(dados, 'premio_lugares', erros, 1, 10,
                                           'Os lugares premiados têm de ser um número de 1 a 10.')

    if not parcial or 'inicio' in dados or 'fim' in dados:
        inicio = _ler_data(dados, 'inicio', erros, 'início') if (not parcial or 'inicio' in dados) \
            else comp.dia_inicio(c)
        fim = _ler_data(dados, 'fim', erros, 'fim') if (not parcial or 'fim' in dados) else comp.dia_fim(c)
        if inicio is None and 'inicio' not in erros:
            erros['inicio'] = 'Indique a data de início.'
        if fim is None and 'fim' not in erros:
            erros['fim'] = 'Indique a data de fim.'
        if inicio and fim and 'inicio' not in erros and 'fim' not in erros:
            if inicio < _hoje():
                erros['inicio'] = 'A data de início não pode ser antes de hoje.'
            elif fim < inicio:
                erros['fim'] = 'A data de fim não pode ser antes da data de início.'
            elif (fim - inicio).days + 1 > MAX_DIAS:
                erros['fim'] = f'Uma competição pode durar no máximo {MAX_DIAS} dias.'
            else:
                limpos['start_date'] = comp.inicio_do_dia(inicio)
                limpos['end_date'] = comp.inicio_do_dia(fim + timedelta(days=1))
    return {k: v for k, v in limpos.items() if k not in erros and v is not None}


def _tipo(inicio, fim):
    dias = (fim - inicio).days
    return 'weekly' if dias <= 7 else 'monthly' if dias >= 28 else 'special'


def _gravar(c, limpos):
    cursos = limpos.pop('cursos', None)
    for campo, valor in limpos.items():
        setattr(c, campo, valor)
    c.type = _tipo(c.start_date, c.end_date)
    c.first_place_prize = comp.NOME_PREMIO[c.premio]
    c.second_place_prize = c.first_place_prize if c.premio_lugares >= 2 else ''
    c.third_place_prize = c.first_place_prize if c.premio_lugares >= 3 else ''
    if cursos is not None:
        # Professor sem cursos escolhidos = todos os dele; da plataforma sem cursos = toda a plataforma.
        c.todos_os_cursos = not cursos and c.criado_por_id is not None
    c.status = comp.status_modelo(comp.estado(c))
    c.save()
    if cursos is not None:
        c.cursos.set(cursos)
    return c


def _criar(request):
    dados = corpo(request)
    erros = {}
    limpos = _validar(request, dados, None, erros)
    if erros:
        return erro_validacao(erros)
    # O administrador sem cursos escolhidos cria uma competição da plataforma (todos os alunos).
    dono = None if ciclo.e_staff(request.user) and not limpos.get('cursos') else request.user
    with transaction.atomic():
        c = Competition(criado_por=dono, description='', status='upcoming')
        c = _gravar(c, limpos)
    return Response(_item(request, c, timezone.now()), status=201)


CAMPOS_DEPOIS_DE_COMECAR = {'nome', 'premio', 'premio_lugares'}


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def detalhe(request, competicao_id):
    c = obter_visivel(request, Competition.objects.prefetch_related('cursos'), competicao_id,
                      'Competição não encontrada.')
    agora = timezone.now()
    if request.method == 'GET':
        return Response(_item(request, c, agora))
    proibido = erro_sem_permissao(request, c)
    if proibido:
        return proibido
    est = comp.estado(c, agora)
    if request.method == 'DELETE':
        if est != 'agendada':
            return _erro('Só se pode apagar uma competição que ainda não começou.', 'ja_comecou', 409)
        c.delete()
        return Response(status=204)
    dados = corpo(request)
    if est == 'terminada' or c.fechada_em is not None:
        return _erro('Esta competição já terminou e não pode ser alterada.', 'terminada', 409)
    if est == 'activa':
        fora = sorted(set(dados) - CAMPOS_DEPOIS_DE_COMECAR)
        if fora:
            return _erro('A competição já começou: só pode mudar o nome e o prémio.', 'ja_comecou', 409,
                         details={'campos': fora})
    erros = {}
    limpos = _validar(request, dados, c, erros)
    if erros:
        return erro_validacao(erros)
    with transaction.atomic():
        c = _gravar(c, limpos)
    return Response(_item(request, c, agora))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def classificacao(request, competicao_id):
    c = obter_visivel(request, Competition.objects.prefetch_related('cursos'), competicao_id,
                      'Competição não encontrada.')
    return Response({'conta': c.conta, 'linhas': comp.classificacao(c)})
