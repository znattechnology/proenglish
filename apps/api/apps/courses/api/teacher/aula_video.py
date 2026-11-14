"""
Transcrição e frases de uma aula em vídeo (editor do professor, fase 5).

  GET    /api/v1/teacher/aulas/<id>/transcricao/            {estado, erro, origem, em, video_mudou, linhas:[{start,end,text}]}
  PUT    /api/v1/teacher/aulas/<id>/transcricao/            {linhas:[...]}  o professor escreve/edita -> 'manual'
  POST   /api/v1/teacher/aulas/<id>/transcricao/            {forcar?}  transcrever (outra vez); uma transcrição
                                                            manual só é substituída com forcar=true (senão 409)
  GET    /api/v1/teacher/aulas/<id>/frases/                 {aula:{...}, frases:[...], ia:{estado, erro}}
  POST   /api/v1/teacher/aulas/<id>/frases/                 {texto, traducao, tipo, inicio?, fim?}  (fica aprovada)
  POST   /api/v1/teacher/aulas/<id>/frases/propor/          o Claude propõe (substitui as propostas da IA por aprovar)
  POST   /api/v1/teacher/aulas/<id>/frases/aprovar-todas/
  PATCH  /api/v1/teacher/frases/<id>/                       {texto?, traducao?, tipo?, inicio?, fim?, estado?}
  DELETE /api/v1/teacher/frases/<id>/

Só o professor dono do curso (ou um administrador). As frases aprovadas valem logo para os alunos
(como o resto de um curso publicado). Propor frases gasta do mesmo limite diário da geração de
lições (PRATICA_GERAR_LIMITE_DIA).
"""
import math

from django.db import transaction
from django.db.models import Max
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo, frases_aula, transcricao
from apps.courses.models import FraseAula

from .cursos import PERMISSOES, _erro
from .editor_video import _aula_do_professor, _dados, _validacao

MAX_FRASES_AULA = 30


def _transcricao_dict(aula):
    return {**transcricao.estado_para_ecra(aula), 'linhas': transcricao.linhas(aula)}


@api_view(['GET', 'PUT', 'POST'])
@permission_classes(PERMISSOES)
def transcricao_aula(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    if request.method == 'GET':
        return Response(_transcricao_dict(aula))
    dados = _dados(request)
    if request.method == 'PUT':
        linhas, erro = transcricao.limpar_linhas(dados.get('linhas'))
        if erro:
            return _validacao({'linhas': [erro]})
        transcricao.guardar_manual(aula, linhas)
        return Response(_transcricao_dict(aula))
    if not aula.video:
        return _erro('Esta aula ainda não tem vídeo.', 'sem_video')
    forcar = dados.get('forcar') is True
    actual = transcricao.estado_de(aula)
    if actual.get('estado') == transcricao.MANUAL and not forcar:
        return _erro('Esta transcrição foi escrita à mão. Confirme que a quer substituir pela automática.',
                     'transcricao_manual', 409)
    if actual.get('estado') == transcricao.A_PROCESSAR and not forcar:
        return Response(_transcricao_dict(aula), status=202)
    with transaction.atomic():
        transcricao.agendar(aula, forcar=forcar, origem_pedido='professor')
    aula.refresh_from_db()
    return Response(_transcricao_dict(aula), status=202)


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------

def _frase_do_professor(request, frase_id):
    frase = FraseAula.objects.select_related('chapter__section__course').filter(pk=frase_id).first()
    if frase is None or not ciclo.e_dono_ou_staff(request.user, frase.chapter.section.course):
        raise NotFound('Frase não encontrada.')
    return frase


def _frases_dict(aula):
    curso = aula.section.course
    ia = frases_aula.estado_ia(aula)
    return {
        'aula': {'id': str(aula.pk), 'titulo': aula.title, 'resumo': aula.content or '',
                 'curso': {'id': str(curso.pk), 'titulo': curso.title},
                 'tem_transcricao': bool(transcricao.linhas(aula))},
        'frases': [frases_aula.frase_dict(f) for f in aula.frases_aula.all().order_by('ordem', 'id')],
        'ia': {'estado': ia.get('estado') or None, 'erro': ia.get('erro') or None},
    }


def _tempo(valor, rotulo, erros):
    if valor in (None, ''):
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) \
            or not (0 <= valor <= 24 * 3600):
        erros[rotulo] = ['Indique o tempo em segundos.']
        return None
    return round(float(valor), 2)


def _validar_frase(dados, parcial=False):
    """Devolve (campos, erros)."""
    erros, campos = {}, {}
    if 'texto' in dados or not parcial:
        texto = ' '.join(str(dados.get('texto') or '').split()) if isinstance(dados.get('texto'), str) else ''
        if not texto:
            erros['texto'] = ['Escreva a frase em inglês.']
        elif len(texto) > 300:
            erros['texto'] = ['A frase pode ter no máximo 300 caracteres.']
        campos['texto'] = texto
    if 'traducao' in dados or not parcial:
        traducao = dados.get('traducao')
        if traducao is not None and not isinstance(traducao, str):
            erros['traducao'] = ['A tradução tem de ser texto.']
        else:
            campos['traducao'] = ' '.join((traducao or '').split())[:300]
    if 'tipo' in dados or not parcial:
        tipo = dados.get('tipo') or FraseAula.TIPO_FRASE
        if tipo not in (FraseAula.TIPO_FRASE, FraseAula.TIPO_PALAVRA):
            erros['tipo'] = ['Escolha "frase" ou "palavra".']
        campos['tipo'] = tipo
    for nome in ('inicio', 'fim'):
        if nome in dados:
            campos[nome] = _tempo(dados.get(nome), nome, erros)
    if 'estado' in dados:
        if dados['estado'] not in (FraseAula.PROPOSTA, FraseAula.APROVADA):
            erros['estado'] = ['Estado inválido.']
        else:
            campos['estado'] = dados['estado']
    ini, fim = campos.get('inicio'), campos.get('fim')
    if ini is not None and fim is not None and fim <= ini:
        erros['fim'] = ['O fim tem de ser depois do início.']
    return campos, erros


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def frases(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    if request.method == 'GET':
        return Response(_frases_dict(aula))
    campos, erros = _validar_frase(_dados(request))
    if erros:
        return _validacao(erros)
    if aula.frases_aula.count() >= MAX_FRASES_AULA:
        return _erro(f'Uma aula pode ter no máximo {MAX_FRASES_AULA} frases.', 'limite_frases')
    if 'inicio' not in campos:
        campos['inicio'], campos['fim'] = frases_aula.localizar(campos['texto'], transcricao.linhas(aula))
    ordem = (aula.frases_aula.aggregate(m=Max('ordem'))['m'] or 0) + 1
    f = FraseAula.objects.create(chapter=aula, ordem=ordem, criada_por_ia=False,
                                 estado=campos.pop('estado', FraseAula.APROVADA), **campos)
    return Response(frases_aula.frase_dict(f), status=201)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def propor_frases(request, aula_id):
    from .gerar_licao import devolver_geracao, gastar_geracao
    aula = _aula_do_professor(request, aula_id)
    if not transcricao.linhas(aula):
        return _erro('A aula ainda não tem transcrição. Transcreva o vídeo primeiro.', 'sem_transcricao')
    if not gastar_geracao(request.user):
        return _erro('Já usou a IA o número máximo de vezes hoje. Pode voltar a pedir amanhã.',
                     'limite_geracao', status_http=429)
    criadas = frases_aula.propor_e_registar(aula)
    if not criadas and frases_aula.estado_ia(aula).get('estado') == 'erro':
        devolver_geracao(request.user)
        return _erro('A IA não conseguiu propor frases agora. Tente daqui a alguns minutos ou escreva-as à mão.',
                     'ia_indisponivel', status_http=503)
    return Response(_frases_dict(aula))


@api_view(['POST'])
@permission_classes(PERMISSOES)
def aprovar_todas(request, aula_id):
    aula = _aula_do_professor(request, aula_id)
    aula.frases_aula.filter(estado=FraseAula.PROPOSTA).update(estado=FraseAula.APROVADA)
    return Response(_frases_dict(aula))


@api_view(['PATCH', 'DELETE'])
@permission_classes(PERMISSOES)
def frase(request, frase_id):
    f = _frase_do_professor(request, frase_id)
    if request.method == 'DELETE':
        f.delete()
        return Response(status=204)
    campos, erros = _validar_frase(_dados(request), parcial=True)
    if erros:
        return _validacao(erros)
    ini = campos.get('inicio', f.inicio)
    fim = campos.get('fim', f.fim)
    if ini is not None and fim is not None and fim <= ini:
        return _validacao({'fim': ['O fim tem de ser depois do início.']})
    for k, v in campos.items():
        setattr(f, k, v)
    f.save()
    return Response(frases_aula.frase_dict(f))
