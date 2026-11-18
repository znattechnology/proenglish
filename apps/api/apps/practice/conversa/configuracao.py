"""
Configuração do tutor de conversa, editável no admin (apps.practice.models.ConfiguracaoTutor).

GET   /api/v1/admin/tutor/   {provedor, modelo, max_minutos_sessao, alterado_em, sugestoes}
PATCH /api/v1/admin/tutor/   {provedor?, modelo?, max_minutos_sessao?}
"""
import re

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador

MODELO_VALIDO = re.compile(r'^[a-z0-9][a-z0-9.\-]{1,78}$')
# Modelos que o Vapi aceita para o tutor (o admin pode escrever outro: o Vapi é que decide).
SUGESTOES = {
    'anthropic': ['claude-haiku-5-5', 'claude-sonnet-5', 'claude-haiku-4-5-20251001'],
    'openai': ['gpt-4.1-mini', 'gpt-4o-mini', 'gpt-4.1'],
}


def actual():
    """{provedor, modelo, max_minutos_sessao}: a linha do admin, ou as definições do servidor."""
    from apps.practice.models import ConfiguracaoTutor
    c = ConfiguracaoTutor.objects.order_by('pk').first()
    if c is None:
        return {'provedor': settings.CONVERSA_VAPI_PROVEDOR, 'modelo': settings.CONVERSA_VAPI_MODELO,
                'max_minutos_sessao': settings.CONVERSA_MAX_MINUTOS_SESSAO, 'alterado_em': None}
    return {'provedor': c.provedor, 'modelo': c.modelo, 'max_minutos_sessao': c.max_minutos_sessao,
            'alterado_em': c.alterado_em.isoformat()}


@api_view(['GET', 'PATCH'])
@permission_classes([EAdministrador])
def tutor(request):
    from apps.practice.models import ConfiguracaoTutor
    if request.method == 'PATCH':
        dados, erros = request.data if isinstance(request.data, dict) else {}, {}
        atual = actual()
        provedor = dados.get('provedor', atual['provedor'])
        modelo = str(dados.get('modelo', atual['modelo']) or '').strip()
        minutos = dados.get('max_minutos_sessao', atual['max_minutos_sessao'])
        if provedor not in dict(ConfiguracaoTutor.PROVEDORES):
            erros['provedor'] = ['Escolha Anthropic ou OpenAI.']
        if not MODELO_VALIDO.match(modelo):
            erros['modelo'] = ['Indique o nome do modelo (letras minúsculas, números, pontos e hífenes).']
        if isinstance(minutos, bool) or not isinstance(minutos, int) or not 1 <= minutos <= 60:
            erros['max_minutos_sessao'] = ['Indique entre 1 e 60 minutos.']
        if erros:
            return Response(corpo_erro('Corrija os campos assinalados.', 'validation_error', erros), status=400)
        c = ConfiguracaoTutor.objects.order_by('pk').first() or ConfiguracaoTutor()
        c.provedor, c.modelo, c.max_minutos_sessao, c.alterado_por = provedor, modelo, minutos, request.user
        c.save()
    return Response({**actual(), 'sugestoes': SUGESTOES})
