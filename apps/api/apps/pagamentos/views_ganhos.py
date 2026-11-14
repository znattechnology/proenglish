"""
Ganhos dos professores (regras em apps/pagamentos/ganhos.py).

Professor (ou staff), em /api/v1/teacher/ganhos/:
    GET    ''                 resumo (estimativa do mês, próximos pagamentos, meses, conta)
    GET    exportar/          CSV (UTF-8 com BOM, separador ";")
    GET    bancos/            lista de bancos
    POST   conta/             {banco, iban, titular} -> guarda pendente e envia código por email
                              (o limite de códigos só conta pedidos válidos que enviam um código)
    POST   conta/confirmar/   {codigo} -> aplica a alteração, avisa por email; devolve o resumo
    DELETE conta/pendente/    cancela a alteração pendente

Pedidos, confirmações e cancelamentos da conta, e cada consulta do IBAN completo, ficam em
RegistoContaRecebimento (sem o IBAN completo).

Administração (role admin ou staff), em /api/v1/admin/ganhos/:
    GET  ?mes=AAAA-MM         linhas do mês (por omissão o mês anterior)
    GET  <id>/iban/           IBAN completo (fica registado em RegistoContaRecebimento)
    POST <id>/pago/           {referencia} marca como pago e avisa o professor
"""

import csv
import io
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador
from apps.core.ip import ip_do_cliente
from apps.courses.api.teacher.cursos import PERMISSOES

from . import ganhos
from .models import AlteracaoContaRecebimento, ContaRecebimento, GanhoMensal, RegistoContaRecebimento

logger = logging.getLogger(__name__)

FINALIDADE_CONTA = 'conta_ganhos'
VALIDADE_CODIGO = timedelta(minutes=15)
MAX_TENTATIVAS = 5


def _erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details, **extra), status=status_http)


def _registar(request, professor_id, accao, banco='', iban='', ganho=None):
    RegistoContaRecebimento.objects.create(
        professor_id=professor_id, autor=request.user, accao=accao, banco=banco or '',
        terminada_em=ganhos.ultimos4(iban), ganho=ganho, ip=(ip_do_cliente(request) or '')[:45])


class CodigoContaThrottle(UserRateThrottle):
    scope = 'ganhos_conta'

    def get_rate(self):
        return getattr(settings, 'GANHOS_LIMITE_CODIGOS', '5/hour')


# Administração: só administradores (papel admin ou superutilizador); is_staff não chega.
PERMISSOES_ADMIN = [permissions.IsAuthenticated, EAdministrador]


# ---------------------------------------------------------------------------
# Professor
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def resumo(request):
    return Response(ganhos.resumo_professor(request.user))


@api_view(['GET'])
@permission_classes(PERMISSOES)
def bancos(request):
    return Response([{'valor': v, 'nome': n} for v, n in ganhos.BANCOS])


@api_view(['GET'])
@permission_classes(PERMISSOES)
def exportar(request):
    buf = io.StringIO()
    buf.write('﻿')
    w = csv.writer(buf, delimiter=';', lineterminator='\r\n')
    w.writerow(['Mês', 'Alunos', 'Minutos', 'Valor (Kz)', 'Pago a', 'Estado'])
    estados = dict(GanhoMensal.ESTADOS)
    for g in GanhoMensal.objects.filter(professor=request.user).order_by('-mes'):
        w.writerow([ganhos.nome_mes(g.mes), g.alunos_pagantes, round(g.segundos / 60), g.valor_kz,
                    ganhos.data_pagamento(g.mes).strftime('%d/%m/%Y'), estados[g.estado]])
    resp = HttpResponse(buf.getvalue().encode('utf-8'), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="ganhos-proenglish.csv"'
    return resp


def _enviar_codigo(user, alt):
    from apps.users.email_service import _contexto_base, _enviar
    ctx = {**_contexto_base(user, user.email), 'codigo': alt.verificacao.code,
           'banco': ganhos.NOME_BANCO.get(alt.banco, alt.banco),
           'terminada_em': ganhos.ultimos4(alt.iban), 'titular': alt.titular}
    return _enviar('Confirme a conta para receber os ganhos - ProEnglish',
                   'emails/conta_ganhos_codigo.html', ctx, user.email)


def _enviar_aviso_alteracao(user, conta):
    from apps.users.email_service import _contexto_base, _enviar
    ctx = {**_contexto_base(user, user.email), 'banco': ganhos.NOME_BANCO.get(conta.banco, conta.banco),
           'terminada_em': ganhos.ultimos4(conta.iban), 'titular': conta.titular,
           'quando': timezone.localtime(conta.confirmada_em, ganhos.FUSO_ANGOLA).strftime('%d/%m/%Y às %H:%M')}
    return _enviar('A conta para receber os ganhos foi alterada - ProEnglish',
                   'emails/conta_ganhos_alterada.html', ctx, user.email)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def alterar_conta(request):
    from apps.users.models import EmailVerification
    from apps.users.email_service import EmailVerificationService

    dados = request.data if isinstance(request.data, dict) else {}
    erros = {}
    banco = str(dados.get('banco') or '').strip().lower()
    if banco not in ganhos.NOME_BANCO:
        erros['banco'] = ['Escolha o banco da lista.']
    try:
        iban = ganhos.normalizar_iban(dados.get('iban'))
    except ganhos.IbanInvalido as e:
        erros['iban'] = [str(e)]
    titular = ' '.join(str(dados.get('titular') or '').split())
    if len(titular) < 3 or len(titular) > 120:
        erros['titular'] = ['Indique o nome do titular da conta, como aparece no banco.']
    if erros:
        return _erro(next(iter(erros.values()))[0], 'dados_invalidos', details=erros)
    if not request.user.email:
        return _erro('A sua conta não tem email para receber o código.', 'sem_email')
    # O limite conta só os pedidos que enviam mesmo um código (não os que falham na validação).
    limite = CodigoContaThrottle()
    if not limite.allow_request(request, None):
        raise Throttled(wait=limite.wait())

    user = request.user
    with transaction.atomic():
        AlteracaoContaRecebimento.objects.filter(professor=user).delete()
        # O finalidade "conta_ganhos" não está nas choices de EmailVerification (só valida em
        # full_clean); isola estes códigos dos de confirmar email/recuperar palavra-passe.
        v = EmailVerificationService.create_verification_code(user, user.email, finalidade=FINALIDADE_CONTA)
        v.expires_at = timezone.now() + VALIDADE_CODIGO
        v.max_attempts = MAX_TENTATIVAS
        v.save(update_fields=['expires_at', 'max_attempts'])
        alt = AlteracaoContaRecebimento.objects.create(
            professor=user, banco=banco, iban=iban, titular=titular, verificacao=v)
        _registar(request, user.pk, RegistoContaRecebimento.PEDIDO, banco, iban)
    if not _enviar_codigo(user, alt):
        alt.delete()
        EmailVerification.objects.filter(pk=v.pk).update(is_used=True)
        return _erro('Não conseguimos enviar o email com o código. Tente outra vez daqui a pouco.',
                     'email_falhou', status_http=503)
    return Response({
        'alteracao_pendente': ganhos.repr_alteracao(alt),
        'mensagem': (f'Enviámos um código para {ganhos.mascarar_email(user.email)}. '
                     'Introduza-o para confirmar a conta; é válido durante 15 minutos.'),
    })


@api_view(['POST'])
@permission_classes(PERMISSOES)
def confirmar_conta(request):
    codigo = str((request.data or {}).get('codigo') or '').strip()
    with transaction.atomic():
        alt = (AlteracaoContaRecebimento.objects.select_for_update()
               .select_related('verificacao').filter(professor=request.user).first())
        if alt is None:
            return _erro('Não há nenhuma alteração da conta à espera de confirmação.', 'sem_alteracao', 404)
        v = alt.verificacao
        if v.is_used or v.is_expired():
            return _erro('O código expirou. Peça um código novo.', 'codigo_expirado')
        if v.attempts >= v.max_attempts:
            return _erro('Esgotou as tentativas. Peça um código novo.', 'tentativas_esgotadas')
        if not codigo or not secrets.compare_digest(codigo, v.code):
            v.increment_attempts()
            restantes = max(v.max_attempts - v.attempts, 0)
            if restantes == 0:
                return _erro('Esgotou as tentativas. Peça um código novo.', 'tentativas_esgotadas')
            texto = (f'O código não está certo. Resta {restantes} tentativa.' if restantes == 1
                     else f'O código não está certo. Restam {restantes} tentativas.')
            return _erro('O código não está certo.', 'codigo_invalido',
                         details={'codigo': [texto]}, tentativas_restantes=restantes)
        v.is_used = True
        v.save(update_fields=['is_used'])
        conta, _ = ContaRecebimento.objects.update_or_create(
            professor=request.user,
            defaults={'banco': alt.banco, 'iban': alt.iban, 'titular': alt.titular,
                      'confirmada_em': timezone.now()})
        alt.delete()
        _registar(request, request.user.pk, RegistoContaRecebimento.CONFIRMADA, conta.banco, conta.iban)
    logger.info('Conta de recebimento confirmada pelo professor %s', request.user.pk)
    if request.user.email:
        _enviar_aviso_alteracao(request.user, conta)
    return Response(ganhos.resumo_professor(request.user))


@api_view(['DELETE'])
@permission_classes(PERMISSOES)
def cancelar_alteracao(request):
    alt = AlteracaoContaRecebimento.objects.filter(professor=request.user).select_related('verificacao').first()
    if alt is not None:
        v = alt.verificacao
        _registar(request, request.user.pk, RegistoContaRecebimento.CANCELADA, alt.banco, alt.iban)
        alt.delete()
        v.is_used = True
        v.save(update_fields=['is_used'])
    return Response(status=204)


# ---------------------------------------------------------------------------
# Administração
# ---------------------------------------------------------------------------

def _linha_admin(g, conta):
    p = g.professor
    return {
        'id': g.pk,
        'professor': {'id': str(p.pk), 'nome': (getattr(p, 'name', '') or '').strip() or p.email,
                      'email': p.email},
        'mes': ganhos.chave_mes(g.mes),
        'alunos': g.alunos_pagantes,
        'minutos': round(g.segundos / 60),
        'quota': float(g.quota),
        'valor_kz': g.valor_kz,
        'conta': (None if conta is None else {
            'banco': conta.banco, 'banco_nome': ganhos.NOME_BANCO.get(conta.banco, conta.banco),
            'terminada_em': ganhos.ultimos4(conta.iban), 'titular': conta.titular,
            'confirmada_em': conta.confirmada_em.isoformat()}),
        'estado': g.estado,
        'pago_em': g.pago_em.isoformat() if g.pago_em else None,
        'referencia': g.referencia,
    }


@api_view(['GET'])
@permission_classes(PERMISSOES_ADMIN)
def admin_lista(request):
    texto = request.query_params.get('mes')
    try:
        mes = ganhos.ler_mes(texto) if texto else ganhos.mes_anterior(ganhos.hoje())
    except ValueError as e:
        return _erro(str(e), 'mes_invalido')
    linhas = list(GanhoMensal.objects.filter(mes=mes).select_related('professor').order_by('-valor_kz'))
    contas = {c.professor_id: c for c in
              ContaRecebimento.objects.filter(professor_id__in=[g.professor_id for g in linhas])}
    return Response({
        'mes': ganhos.chave_mes(mes),
        'nome': ganhos.nome_mes(mes),
        'pago_a': ganhos.data_pagamento(mes).isoformat(),
        'percentagem': ganhos.percentagem(),
        'total_kz': sum(g.valor_kz for g in linhas),
        'por_pagar_kz': sum(g.valor_kz for g in linhas if g.estado == GanhoMensal.A_PROCESSAR),
        'linhas': [_linha_admin(g, contas.get(g.professor_id)) for g in linhas],
    })


@api_view(['GET'])
@permission_classes(PERMISSOES_ADMIN)
def admin_iban(request, pk):
    g = get_object_or_404(GanhoMensal.objects.select_related('professor'), pk=pk)
    conta = ContaRecebimento.objects.filter(professor_id=g.professor_id).first()
    if conta is None:
        return _erro('O professor ainda não tem uma conta confirmada.', 'sem_conta', 404)
    logger.info('IBAN consultado: admin=%s professor=%s ganho=%s', request.user.pk, g.professor_id, g.pk)
    _registar(request, g.professor_id, RegistoContaRecebimento.IBAN_CONSULTADO, conta.banco, conta.iban, ganho=g)
    return Response({'iban': conta.iban, 'banco': conta.banco,
                     'banco_nome': ganhos.NOME_BANCO.get(conta.banco, conta.banco),
                     'titular': conta.titular})


@api_view(['POST'])
@permission_classes(PERMISSOES_ADMIN)
def admin_marcar_pago(request, pk):
    from apps.users.models import Notification

    referencia = str((request.data or {}).get('referencia') or '').strip()
    if not referencia or len(referencia) > 100:
        return _erro('Indique a referência da transferência.', 'dados_invalidos',
                     details={'referencia': ['Obrigatória (até 100 caracteres).']})
    with transaction.atomic():
        g = get_object_or_404(GanhoMensal.objects.select_for_update().select_related('professor'), pk=pk)
        if g.estado == GanhoMensal.PAGO:
            return _erro('Este mês já está marcado como pago.', 'ja_pago', 409)
        if g.valor_kz <= 0:
            return _erro('Este mês não tem valor a pagar (0 Kz).', 'sem_valor', 409)
        conta = ContaRecebimento.objects.filter(professor_id=g.professor_id).first()
        if conta is None:
            return _erro('O professor ainda não tem uma conta confirmada.', 'sem_conta', 409)
        g.estado = GanhoMensal.PAGO
        g.pago_em = ganhos.hoje()
        g.referencia = referencia
        g.save(update_fields=['estado', 'pago_em', 'referencia', 'atualizado_em'])
        # Auditoria: quem marcou, para que conta (banco e últimos 4 dígitos, nunca o IBAN completo)
        _registar(request, g.professor_id, RegistoContaRecebimento.PAGO, conta.banco, conta.iban, ganho=g)
    logger.info('Ganho %s marcado como pago por %s (ref. %s)', g.pk, request.user.pk, referencia)
    try:
        Notification.notify(
            g.professor, Notification.KIND_SYSTEM,
            f'Pagámos os seus ganhos de {ganhos.nome_mes(g.mes)}',
            body=f'Transferimos {ganhos.formatar_kz(g.valor_kz)} para a sua conta (referência {referencia}).',
            link='/teacher/billing', dedupe_key=f'ganhos-pago:{g.pk}',
        )
    except Exception:
        logger.exception('Falha ao avisar o professor do pagamento do ganho %s', g.pk)
    return Response(_linha_admin(g, conta))
