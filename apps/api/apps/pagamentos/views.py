"""
Endpoints de pagamentos (montados em /api/v1/pagamentos/).

GET  orcamento/?plan=&periodo=&codigo=   preço que vai ser cobrado (código + crédito do plano atual)
POST multicaixa/               cria pagamento pendente (push MCX)
POST sem-pagamento/            preço final 0 Kz: ativa já, sem Multicaixa (recibo de 0 Kz)
GET  <uuid:id>/                estado atual (resolução lazy no simulador)
POST <uuid:id>/cancelar/       cancela enquanto pendente
POST <uuid:id>/simular/        só com PAGAMENTOS_SIMULADOS=True
GET  recibos/<numero>/         recibo de um pagamento pago
POST teste/ {plano, telefone}  começa o teste grátis do plano (sem pagamento)
"""

from django.conf import settings
from django.http import Http404
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.exceptions import corpo_erro

from . import services
from .models import Pagamento
from .provedores import simulacao_permitida


class CriacaoPagamentoThrottle(UserRateThrottle):
    scope = 'pagamentos_criacao'

    def get_rate(self):
        return getattr(settings, 'PAGAMENTOS_LIMITE_CRIACAO', '10/min')


class CriarPagamentoSerializer(serializers.Serializer):
    # Só há subscrições: os cursos não se vendem à parte. "tipo" é opcional e só aceita "subscricao".
    tipo = serializers.ChoiceField(
        choices=[Pagamento.TIPO_SUBSCRICAO], required=False, default=Pagamento.TIPO_SUBSCRICAO,
        error_messages={'invalid_choice': 'Só é possível pagar subscrições: os cursos estão incluídos nos planos.'},
    )
    plan_id = serializers.UUIDField(required=False, allow_null=True,
                                    error_messages={'invalid': 'plan_id inválido.'})
    periodo = serializers.ChoiceField(
        choices=[Pagamento.PERIODO_MENSAL, Pagamento.PERIODO_ANUAL], required=False, allow_null=True,
        error_messages={'invalid_choice': 'Período inválido: use "mensal" ou "anual".'},
    )
    telefone = serializers.CharField(error_messages={'required': 'Indique o número de telemóvel.',
                                                     'blank': 'Indique o número de telemóvel.'})
    codigo_promocional = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                               max_length=50)


def _erro(e: services.ErroPagamento):
    return Response(corpo_erro(e.mensagem, e.codigo or 'erro_pagamento'), status=e.status)


def _pagamento_do_utilizador(request, pk):
    try:
        return Pagamento.objects.select_related('plan', 'user').get(pk=pk, user=request.user)
    except Pagamento.DoesNotExist:
        raise Http404


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([CriacaoPagamentoThrottle])
def criar_pagamento_multicaixa(request):
    ser = CriarPagamentoSerializer(data=request.data)
    if not ser.is_valid():
        primeiro = next(iter(ser.errors.values()))[0]
        return Response({'error': str(primeiro), 'detalhes': ser.errors},
                        status=status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    try:
        pagamento = services.criar_pagamento_mcx(
            request.user,
            telefone=d['telefone'],
            plan_id=d.get('plan_id'),
            periodo=d.get('periodo'),
            codigo_promocional=d.get('codigo_promocional'),
        )
    except services.ErroPagamento as e:
        return _erro(e)
    return Response(services.representar_pagamento(pagamento), status=status.HTTP_201_CREATED)


class AtivarSemPagamentoSerializer(serializers.Serializer):
    plan_id = serializers.CharField(error_messages={'required': 'Indique o plano (plan_id).'})
    periodo = serializers.ChoiceField(
        choices=[Pagamento.PERIODO_MENSAL, Pagamento.PERIODO_ANUAL],
        error_messages={'invalid_choice': 'Período inválido: use "mensal" ou "anual".',
                        'required': 'Indique o período: "mensal" ou "anual".'},
    )
    codigo_promocional = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                               max_length=50)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def orcamento(request):
    """?plan=<PREMIUM|PREMIUM_PLUS|uuid>&periodo=mensal|anual&codigo=<opcional>"""
    q = request.query_params
    plan = q.get('plan') or q.get('plan_id')
    if not plan:
        return Response({'error': 'Indique o plano (plan).'}, status=status.HTTP_400_BAD_REQUEST)
    periodo = q.get('periodo') or Pagamento.PERIODO_MENSAL
    try:
        return Response(services.orcamento(request.user, plan, periodo, q.get('codigo')))
    except services.ErroPagamento as e:
        return _erro(e)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([CriacaoPagamentoThrottle])
def ativar_sem_pagamento(request):
    ser = AtivarSemPagamentoSerializer(data=request.data)
    if not ser.is_valid():
        primeiro = next(iter(ser.errors.values()))[0]
        return Response({'error': str(primeiro), 'detalhes': ser.errors},
                        status=status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    try:
        pagamento = services.ativar_sem_pagamento(
            request.user, plan_id=d['plan_id'], periodo=d['periodo'],
            codigo_promocional=d.get('codigo_promocional'),
        )
    except services.ErroPagamento as e:
        return _erro(e)
    return Response(services.representar_pagamento(pagamento), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def detalhe_pagamento(request, pk):
    pagamento = _pagamento_do_utilizador(request, pk)
    try:
        services.atualizar_estado(pagamento)
    except services.ErroPagamento:
        # Cancelado/anulado em paralelo (ex.: durante o polling): devolver o estado atual
        pagamento.refresh_from_db()
    return Response(services.representar_pagamento(pagamento))


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancelar_pagamento(request, pk):
    pagamento = _pagamento_do_utilizador(request, pk)
    try:
        services.cancelar_pagamento(pagamento)
    except services.ErroPagamento as e:
        return _erro(e)
    return Response(services.representar_pagamento(pagamento))


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def simular_pagamento(request, pk):
    if not simulacao_permitida():
        raise Http404
    pagamento = _pagamento_do_utilizador(request, pk)
    resultado = request.data.get('resultado')
    if resultado not in ('aprovar', 'recusar', 'expirar'):
        return Response({'error': 'resultado deve ser "aprovar", "recusar" ou "expirar".'},
                        status=status.HTTP_400_BAD_REQUEST)

    services.atualizar_estado(pagamento)
    if pagamento.estado != Pagamento.PENDENTE:
        return Response({
            'error': f'O pagamento já não está pendente (estado: {pagamento.estado}).',
            'code': 'estado_invalido',
            'pagamento': services.representar_pagamento(pagamento),
        }, status=status.HTTP_409_CONFLICT)

    try:
        if resultado == 'aprovar':
            services.confirmar_pagamento(pagamento)
        elif resultado == 'recusar':
            from .provedores.simulado import MOTIVO_RECUSADO
            services.marcar_falha(pagamento, Pagamento.RECUSADO, MOTIVO_RECUSADO)
        else:
            services.marcar_falha(pagamento, Pagamento.EXPIRADO, services.MOTIVO_EXPIRADO)
    except services.ErroPagamento as e:
        return _erro(e)
    return Response(services.representar_pagamento(pagamento))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def recibo(request, numero):
    try:
        pagamento = Pagamento.objects.select_related('plan', 'user').get(
            numero_recibo=numero, user=request.user, estado=Pagamento.PAGO)
    except Pagamento.DoesNotExist:
        raise Http404
    return Response(services.representar_recibo(pagamento))


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([CriacaoPagamentoThrottle])
def iniciar_teste(request):
    """
    POST {plano: "PREMIUM"|"PREMIUM_PLUS"|<uuid>, telefone: "923456789"} -> 201 com o estado
    da subscrição em teste. Só alunos (403), um teste por pessoa: o número Multicaixa Express e
    a caixa de correio (normalizados) não podem ter sido usados noutro teste
    (409 telefone_ja_usado / teste_ja_usado). O plano tem de ter dias_teste > 0.
    """
    from .teste import SO_ALUNOS, ErroTeste, e_aluno, estado_teste, iniciar_teste as _iniciar

    if not e_aluno(request.user):
        e = ErroTeste(SO_ALUNOS)
        return Response(corpo_erro(e.mensagem, e.codigo), status=e.status)
    ref = request.data.get('plano') or request.data.get('plan') or request.data.get('plan_id')
    try:
        plano = services._resolver_plano(ref, request.user)
    except services.ErroPagamento as e:
        return _erro(e)
    telefone = request.data.get('telefone')
    if not isinstance(telefone, str) or not telefone.strip():
        msg = 'Indique o número de telemóvel com Multicaixa Express.'
        return Response(corpo_erro(msg, 'telefone_em_falta', {'telefone': [msg]}),
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        sub = _iniciar(request.user, plano, telefone=telefone)
    except ErroTeste as e:
        details = {'telefone': [e.mensagem]} if e.codigo.startswith('telefone') else None
        return Response(corpo_erro(e.mensagem, e.codigo, details), status=e.status)
    return Response({
        'plano': {'id': str(plano.id), 'nome': plano.name, 'tipo': plano.plan_type},
        'status': sub.status,
        **estado_teste(request.user, None, sub=sub),
        'mensagem': f'Começou o seu teste do {plano.name}. Não paga nada agora.',
    }, status=status.HTTP_201_CREATED)
