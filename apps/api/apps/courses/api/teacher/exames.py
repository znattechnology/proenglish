"""
Área do professor: perfil de fala e exames orais dos alunos (fase 6).

  GET  /api/v1/teacher/alunos/<id>/fala/      perfil de fala (níveis por competência, erros
                                              frequentes, frases ditas sozinho), minutos a falar
                                              por semana e palavras a treinar, e exames orais
                                              do aluno nos cursos do professor
  GET  /api/v1/teacher/exames/?curso=<id>     exames orais avaliados de um curso (ou de todos),
                                              primeiro os que pedem confirmação (revisao_recomendada)
  GET  /api/v1/teacher/exames/<id>/           um exame (pede a gravação ao Vapi, se ainda não chegou)
  POST /api/v1/teacher/exames/<id>/rever/     {"confirmar": true} ou {"nota": 0-100, "comentario"}

As listas nunca falam com o Vapi (usam o URL guardado); só a vista de um exame o faz.

Só o professor do curso (ou a administração) vê e revê os exames desse curso; para os outros os
exames não existem (404). A nota revista ganha à da IA e a nota do curso é recalculada.
Sem transcrições: o professor ouve a gravação, quando o aluno a autorizou.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.courses import ciclo
from apps.courses.api.teacher.cursos import PERMISSOES, _erro
from apps.courses.models import ExameOral

from .alunos import _cursos_visiveis, _nome, _pares


def _exame_professor(e, buscar=False):
    from apps.practice.conversa.exame import buscar_gravacao, exame_dict, revisao_recomendada
    if buscar:
        buscar_gravacao(e)  # nunca levanta
    d = exame_dict(e)
    return {**d, 'aluno': {'id': str(e.user_id), 'nome': _nome(e.user.name)},
            'revisao_recomendada': revisao_recomendada(e, minima=d['nota_minima'])}


def _exame_visivel(request, exame_id):
    e = ExameOral.objects.select_related('course', 'user', 'sessao', 'revisto_por').filter(pk=exame_id).first()
    if e is None or not ciclo.e_dono_ou_staff(request.user, e.course):
        raise NotFound('Exame não encontrado.')
    return e


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exame_detalhe(request, exame_id):
    return Response(_exame_professor(_exame_visivel(request, exame_id), buscar=True))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def fala_aluno(request, aluno_id):
    from apps.perfil.models import ItemBanco, PadraoErro, PerfilFala
    cursos = _cursos_visiveis(request)
    pares = {cid for (uid, cid) in _pares(cursos, user_ids=[aluno_id]) if uid == aluno_id}
    if not pares:
        raise NotFound('Aluno não encontrado.')
    perfil = PerfilFala.objects.filter(user_id=aluno_id).first()
    padroes = list(PadraoErro.objects.filter(user_id=aluno_id, superado=False)
                   .order_by('-ocorrencias', '-ultima_ocorrencia')[:5])
    sozinho = ItemBanco.objects.filter(user_id=aluno_id, estado=ItemBanco.SOZINHO)
    exames = (ExameOral.objects.filter(user_id=aluno_id, course_id__in=list(pares))
              .exclude(estado__in=[ExameOral.ANULADO, ExameOral.EM_CURSO])
              .select_related('course', 'user', 'sessao', 'revisto_por').order_by('-created_at')[:20])
    return Response({
        'perfil': {
            'niveis': perfil.niveis() if perfil else {'falar': None, 'ouvir': None, 'vocabulario': None,
                                                     'gramatica': None},
            'conversas_avaliadas': perfil.conversas_avaliadas if perfil else 0,
            'padroes': [{'chave': p.chave, 'descricao': p.descricao, 'errado': p.exemplo_errado,
                         'certo': p.exemplo_certo, 'ocorrencias': p.ocorrencias} for p in padroes],
            'frases_sozinho': sozinho.count(),
            'frases_sozinho_cursos': sozinho.filter(curso_id__in=list(pares)).count(),
        },
        'fala': _fala(aluno_id),
        'exames': [_exame_professor(e) for e in exames],
    })


def _fala(aluno_id):
    """Fase 3: minutos a falar por semana, palavras por minuto e palavras a treinar."""
    from apps.perfil import fala
    from apps.users.models import User
    aluno = User.objects.filter(pk=aluno_id).first()
    return fala.resumo_professor(aluno) if aluno is not None else None


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exames_dos_cursos(request):
    cursos = _cursos_visiveis(request)
    ids = [c.id for c in cursos]
    curso = (request.query_params.get('curso') or '').strip()
    if curso:
        if curso not in {str(i) for i in ids}:
            raise NotFound('Curso não encontrado.')
        ids = [i for i in ids if str(i) == curso]
    exames = (ExameOral.objects.filter(course_id__in=ids, estado=ExameOral.AVALIADO)
              .select_related('course', 'user', 'sessao', 'revisto_por').order_by('-created_at')[:100])
    lista = [_exame_professor(e) for e in exames]
    # Primeiro os que pedem a confirmação do professor (perto da nota mínima, avaliados por regras).
    lista.sort(key=lambda d: d['revisao_recomendada'] is None)
    return Response({'exames': lista, 'por_rever': sum(1 for d in lista if d['revisao_recomendada'])})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def rever_exame(request, exame_id):
    from apps.practice.conversa import exame as svc
    e = _exame_visivel(request, exame_id)
    if e.estado != ExameOral.AVALIADO:
        return _erro('Este exame ainda não tem nota da IA.', 'exame_sem_nota', status_http=409)
    corpo = request.data if isinstance(request.data, dict) else {}
    comentario = corpo.get('comentario') or ''
    if not isinstance(comentario, str):
        return _erro('Comentário inválido.', 'dados_invalidos', details={'comentario': ['Texto inválido.']})
    if corpo.get('confirmar') is True:
        nota = e.nota_final
    else:
        try:
            nota = float(corpo.get('nota'))
        except (TypeError, ValueError):
            nota = None
        if nota is None or not 0 <= nota <= 100:
            return _erro('A nota tem de ser um número de 0 a 100.', 'dados_invalidos',
                         details={'nota': ['Use um número de 0 a 100.']})
    if nota is None:
        return _erro('Este exame ainda não tem nota da IA.', 'exame_sem_nota', status_http=409)
    e = svc.rever(e, request.user, nota, comentario)
    e = ExameOral.objects.select_related('course', 'user', 'sessao', 'revisto_por').get(pk=e.pk)
    return Response(_exame_professor(e))

