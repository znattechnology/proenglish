"""
Revisão de cursos pelo administrador (apps.core.permissions.EAdministrador; is_staff sozinho não chega).

  GET  /api/v1/admin/cursos/revisao/        cursos em revisão (mais antigos primeiro)
  POST /api/v1/admin/cursos/<id>/aprovar/   em_revisao -> publicado (+ aviso ao professor);
                                            400 verificacao_incompleta se a lista de verificação falhar
  POST /api/v1/admin/cursos/<id>/recusar/   {motivo} em_revisao -> estado anterior (rascunho, ou
                                            arquivado se o curso estava arquivado) + aviso com o motivo
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador
from apps.courses import ciclo
from apps.courses.models import Course

logger = logging.getLogger(__name__)

PERMISSOES = [EAdministrador]
LIGACAO_PROFESSOR = '/teacher/courses'


def _erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details, **extra), status=status_http)


def _curso(curso_id):
    return Course.objects.select_for_update().filter(id=curso_id).first()


def _item(c, com_verificacao=True):
    dados = {
        'id': str(c.id),
        'tipo': ciclo.tipo_api(c),
        'titulo': c.title,
        'descricao': c.description,
        'area': ciclo.area_pt(c.category),
        'nivel': ciclo.nivel_pt(c.level),
        'estado': ciclo.estado(c),
        'imagem': c.image or None,
        'professor': {'id': str(c.teacher_id), 'nome': c.teacherName or getattr(c.teacher, 'name', ''),
                      'email': c.teacher.email},
        'submetido_em': c.submetido_em.isoformat() if c.submetido_em else None,
        'aprovado_em': c.aprovado_em.isoformat() if c.aprovado_em else None,
        'motivo_recusa': c.motivo_recusa or None,
        'motivo_moderacao': c.motivo_moderacao or None,
        # 'arquivado' quando é a republicação de um curso arquivado (há alunos inscritos).
        'estado_antes_revisao': ciclo.ESTADO_API.get(c.estado_antes_revisao) if c.status == ciclo.EM_REVISAO else None,
    }
    if com_verificacao:
        dados['verificacao'] = ciclo.verificar(c)
    return dados


def chave_aviso(prefixo, curso):
    """Chave de dedupe única por decisão (duas decisões no mesmo segundo não colidem)."""
    return f'{prefixo}:{curso.pk}:{uuid.uuid4().hex}'


def _avisar(curso, titulo, corpo, chave):
    try:
        from apps.users.models import Notification
        Notification.notify(
            curso.teacher, Notification.KIND_COURSE, title=titulo, body=corpo,
            link=LIGACAO_PROFESSOR, dedupe_key=chave, respeitar_preferencias=False,
        )
    except Exception:  # o aviso nunca impede a decisão
        logger.exception('Falha ao avisar o professor do curso %s', curso.pk)


def registar_moderacao(curso, accao, motivo, admin):
    """Guarda a última decisão de moderação (recusar/arquivar) no curso, para o professor a ver."""
    curso.motivo_moderacao = motivo
    curso.moderacao_accao = accao
    curso.moderado_por = admin
    curso.moderado_em = timezone.now()
    curso.save(update_fields=['motivo_moderacao', 'moderacao_accao', 'moderado_por', 'moderado_em'])


@api_view(['GET'])
@permission_classes(PERMISSOES)
def lista_revisao(request):
    cursos = list(Course.objects.filter(status=ciclo.EM_REVISAO).select_related('teacher')
                  .order_by('submetido_em', 'updated_at'))
    return Response({'total': len(cursos), 'resultados': [_item(c) for c in cursos]})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def aprovar(request, curso_id):
    with transaction.atomic():
        curso = _curso(curso_id)
        if curso is None:
            return _erro('Curso não encontrado.', 'not_found', 404)
        if curso.status != ciclo.EM_REVISAO:
            return _erro('Só se aprovam cursos que estão em revisão.', 'nao_em_revisao')
        # O professor pode ter mudado o curso depois de o submeter: verifica outra vez.
        resultado = ciclo.verificar(curso)
        if not resultado['pode_submeter']:
            return _erro('O curso já não cumpre a lista de verificação e não pode ser publicado. '
                         'Recuse-o com o motivo para o professor corrigir.',
                         'verificacao_incompleta', details=resultado, verificacao=resultado, **resultado)
        agora = timezone.now()
        curso.status = ciclo.PUBLICADO
        curso.aprovado_em = agora
        curso.aprovado_por = request.user
        curso.motivo_recusa = ''
        curso.motivo_moderacao = ''
        curso.moderacao_accao = ''
        curso.modo_arquivo = ''
        curso.arquivado_em = None
        curso.estado_antes_revisao = ''
        curso.save(update_fields=['status', 'aprovado_em', 'aprovado_por', 'motivo_recusa',
                                  'motivo_moderacao', 'moderacao_accao',
                                  'modo_arquivo', 'arquivado_em', 'estado_antes_revisao', 'updated_at'])
    _avisar(curso, 'Curso aprovado',
            f'O seu curso "{curso.title}" foi aprovado e já está no catálogo.',
            chave_aviso('curso-aprovado', curso))
    return Response({'message': 'Curso aprovado e publicado.', 'curso': _item(curso, com_verificacao=False)})


@api_view(['POST'])
@permission_classes(PERMISSOES)
def recusar(request, curso_id):
    motivo = (request.data or {}).get('motivo') if isinstance(request.data, dict) else None
    motivo = motivo.strip() if isinstance(motivo, str) else ''
    if len(motivo) < 5:
        return _erro('Explique ao professor o que tem de mudar (pelo menos 5 caracteres).', 'motivo_obrigatorio',
                     details={'motivo': ['Indique o motivo da recusa.']})
    with transaction.atomic():
        curso = _curso(curso_id)
        if curso is None:
            return _erro('Curso não encontrado.', 'not_found', 404)
        if curso.status != ciclo.EM_REVISAO:
            return _erro('Só se recusam cursos que estão em revisão.', 'nao_em_revisao')
        from apps.courses.api.teacher.cursos import sair_da_revisao
        voltou = sair_da_revisao(curso, motivo=motivo[:2000])
        registar_moderacao(curso, 'recusar', motivo[:2000], request.user)
    onde = 'arquivado' if voltou == ciclo.ARQUIVADO else 'rascunho'
    _avisar(curso, 'Curso não aprovado',
            f'O seu curso "{curso.title}" voltou a {onde}. Motivo: {curso.motivo_recusa}',
            chave_aviso('curso-recusado', curso))
    return Response({'message': 'Curso recusado. O professor foi avisado.', 'curso': _item(curso, com_verificacao=False)})
