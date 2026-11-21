"""
POST /api/v1/student/practice-courses/challenges/<uuid>/conversa/

Começa a conversa curta (1-2 min) de um exercício VAPI_CONVERSATION no fim de uma lição.
Usa o serviço normal da conversa com o tutor (apps/practice/conversa/servico.py): gasta os
minutos de conversa do dia do aluno. Termina-se com POST /practice/conversa/sessoes/<id>/terminar/
(como as outras conversas) e o exercício conta com POST challenge-progress/ {challenge_id, sessao_id}.

Respostas:
  201 {sessao: NovaSessao, modo: "vapi"|"simulado", chave_publica: str|null}
  403/409 {codigo, mensagem, pode_saltar: true}: sem minutos, plano sem tutor, exercício
     incompleto... o aluno pode saltar o exercício sem penalização (challenge-progress/ saltar).
"""
import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.practice.acesso_licoes import erro_acesso_licao
from apps.practice.conversa import licao as conversa_licao
from apps.practice.conversa import servico
from apps.practice.conversa.servico import ErroConversa
from apps.practice.conversa.situacoes import NIVEIS, preferencias_padrao
from apps.practice.conversa.views import LimiteSessoes
from apps.practice.models import PracticeChallenge

logger = logging.getLogger(__name__)


def _nao_disponivel(codigo, mensagem, estado=status.HTTP_409_CONFLICT):
    return Response({'codigo': codigo, 'mensagem': mensagem, 'pode_saltar': True}, status=estado)


def _preferencias(user):
    prefs = preferencias_padrao(user)
    try:
        from apps.perfil.servico import nivel_falar
        nivel = nivel_falar(user)
        if nivel in NIVEIS:
            prefs['nivel'] = nivel
    except Exception:
        logger.exception('conversa da lição: falha ao ler o nível de fala')
    return prefs


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LimiteSessoes])
def comecar_conversa_licao(request, challenge_id):
    try:
        ch = (PracticeChallenge.objects.select_related('lesson', 'lesson__unit', 'lesson__unit__course')
              .get(id=challenge_id, type='VAPI_CONVERSATION',
                   lesson__unit__course__status__in=('Published', 'Archived')))
    except (PracticeChallenge.DoesNotExist, ValueError, DjangoValidationError):
        return Response({'codigo': 'nao_encontrado', 'mensagem': 'Não encontrámos este exercício.'},
                        status=status.HTTP_404_NOT_FOUND)
    erro = erro_acesso_licao(request.user, ch.lesson)
    if erro:
        return Response(erro, status=status.HTTP_403_FORBIDDEN)

    frases = conversa_licao.frases_alvo(ch)
    if not (ch.question or '').strip() or not frases:
        return _nao_disponivel('conversa_incompleta', 'Esta conversa ainda não está pronta. Pode saltá-la.')

    try:
        sessao = servico.criar_sessao(
            request.user, _preferencias(request.user),
            situacao=conversa_licao.situacao_do_exercicio(ch),
            objectivos=[{'en': f, 'pt': ''} for f in frases],
            max_segundos=settings.CONVERSA_LICAO_MAX_SEGUNDOS,
            config_extra={'exercicio_id': str(ch.pk), 'licao_id': str(ch.lesson_id)},
        )
    except ErroConversa as e:
        return Response({'codigo': e.codigo, 'mensagem': e.mensagem, 'pode_saltar': True}, status=e.status)
    vapi = servico.config_vapi()
    return Response({'sessao': sessao, 'modo': servico.modo(), 'chave_publica': vapi['public_key'] if vapi else None},
                    status=status.HTTP_201_CREATED)
