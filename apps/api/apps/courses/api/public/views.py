"""
Verificação pública de certificados (sem autenticação).

GET /api/v1/certificados/verificar/<numero>/  (ex.: PE-C-2026-000001)

Devolve apenas campos não sensíveis: nome do aluno, curso, data de emissão, nota final
e estado (válido / revogado). Nunca devolve e-mail, ids nem o motivo da revogação.
"""
import logging
import re

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.courses.certificados import dados_verificacao_publica
from apps.courses.models import CourseCertificate

logger = logging.getLogger(__name__)

FORMATO_NUMERO = re.compile(r'^PE-C-\d{4}-\d{6}$')


class VerificacaoCertificadoThrottle(AnonRateThrottle):
    """Limita a enumeração de números sequenciais (por IP)."""
    scope = 'verificacao_certificado'
    rate = '20/minute'


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([VerificacaoCertificadoThrottle])
def verificar_certificado(request, numero):
    numero = (numero or '').strip().upper()
    if not FORMATO_NUMERO.match(numero):
        return Response({
            'valido': False,
            'estado': 'invalido',
            'mensagem': 'Número de certificado inválido. Formato: PE-C-AAAA-NNNNNN.',
        }, status=status.HTTP_400_BAD_REQUEST)

    cert = (CourseCertificate.objects.select_related('user', 'course')
            .filter(certificate_number=numero).first())
    if cert is None:
        logger.info('Verificação de certificado sem resultado: %s', numero)
        return Response({
            'valido': False,
            'estado': 'nao_encontrado',
            'numero': numero,
            'mensagem': 'Não existe nenhum certificado ProEnglish com este número.',
        }, status=status.HTTP_404_NOT_FOUND)

    return Response(dados_verificacao_publica(cert))
