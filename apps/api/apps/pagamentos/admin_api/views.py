"""
Administração: subscrições, pagamentos (incluindo falhados) e relatórios de receita.

Todas as vistas exigem ``EAdministrador`` (papel admin ou superutilizador; ``is_staff`` não chega).
Valores em kwanzas inteiros. Ver as definições das métricas em ``metricas.py``.
"""

import csv
import io
import logging
import math
import re
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador
from apps.subscriptions.services import FUSO_ANGOLA

from .. import services
from ..avisos import LINK_SUBSCRICAO, formatar_kz
from ..models import Pagamento
from . import metricas as m

logger = logging.getLogger(__name__)

PERMISSOES = [EAdministrador]
POR_PAGINA = 25
ESPERA_LEMBRETE = 24 * 3600  # 1 lembrete por pagamento por dia
ESPERA_NOVO_PEDIDO = 10 * 60  # 1 novo pedido por pagamento a cada 10 min
FILTROS_SUBSCRICOES = ('todas', 'activas', 'em_teste', 'a_expirar', 'falhou', 'canceladas')
FILTRO_PARA_ESTADO = {'activas': m.ACTIVA, 'em_teste': m.EM_TESTE, 'a_expirar': m.A_EXPIRAR,
                      'falhou': m.FALHOU, 'canceladas': m.CANCELADA}
PERIODOS_RELATORIO = {30: 1, 90: 3, 180: 6, 365: 12}  # dias -> meses


def _erro(mensagem, code, status_http=400, details=None, **extra):
    return Response(corpo_erro(mensagem, code, details or {}, **extra), status=status_http)


def _pagina(request):
    try:
        return max(1, int(request.query_params.get('pagina') or 1))
    except (TypeError, ValueError):
        return 1


def _paginar(itens, pagina, total=None):
    total = len(itens) if total is None else total
    paginas = max(1, math.ceil(total / POR_PAGINA))
    inicio = (pagina - 1) * POR_PAGINA
    return total, paginas, inicio


def _resolver_pendentes():
    """Pendentes fora de prazo passam a expirado/pago antes de contar (resolução lazy)."""
    try:
        services.resolver_pendentes_caducados()
    except Exception:
        logger.exception('Falha ao resolver pagamentos pendentes caducados')


def _hoje():
    return timezone.localtime(timezone.now(), FUSO_ANGOLA).date()


# ---------------------------------------------------------------------------
# 1. Resumo das subscrições
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def resumo(request):
    _resolver_pendentes()
    agora = timezone.now()
    # Definições partilhadas com o Painel (metricas.py): pago = período coberto por um pagamento > 0 Kz
    planos = m.planos_em_vigor(agora)
    pagos = [p for p in planos.values() if p.categoria == m.CAT_PAGO]
    premium = sum(1 for p in pagos if p.plan_type == 'PREMIUM')
    plus = sum(1 for p in pagos if p.plan_type == 'PREMIUM_PLUS')
    em_teste = sum(1 for p in planos.values() if p.categoria == m.CAT_TESTE)
    por_plano = m.por_plano(planos)

    # Últimos 8 pagamentos confirmados
    recentes_qs = list(Pagamento.objects.filter(estado=Pagamento.PAGO, pago_em__isnull=False)
                       .select_related('plan', 'user', 'historico').order_by('-pago_em')[:8])
    primeiros = m.primeiros_pagamentos({p.user_id for p in recentes_qs})
    recentes = [{
        'id': str(p.id),
        'utilizador': m.utilizador_repr(p.user),
        'descricao': m.descrever(p, primeiros.get(p.user_id)),
        'valor_kz': p.total_kz,
        'data': m.iso(p.pago_em),
    } for p in recentes_qs]

    # Atenção
    falhas = m.falhados_em_aberto(agora)
    semana = m.falhados_semana(agora, falhas)
    terminam = len(m.terminam_em_breve(agora, planos, falhas))

    intervalos = m.Intervalos()
    passam, cancelam = m.taxas_30_dias(agora, intervalos)
    mes = m.inicio_mes(agora)
    return Response({
        'assinantes_pagos': len(pagos),
        'premium': premium,
        'premium_plus': plus,
        'em_teste': em_teste,
        'receita_mes_kz': m.receita(mes, agora + timedelta(seconds=1)),
        'receita_ate': _hoje().isoformat(),
        'passam_a_pagar_pct': passam,
        'cancelam_pct': cancelam,
        'por_plano': por_plano,
        'recentes': recentes,
        'atencao': {
            'falhados_semana': len(semana),
            'falhados_semana_kz': sum(f.pagamento.total_kz for f in semana),
            'terminam_3_dias': terminam,
        },
    })


# ---------------------------------------------------------------------------
# 2. Lista de subscrições
# ---------------------------------------------------------------------------

def _periodo_linha(linha):
    if linha.estado == m.EM_TESTE:
        return m.PERIODO_TESTE
    ref = linha.pagamento_ref
    if ref is not None and ref.plan_id == linha.plano.pk:
        return ref.periodo
    if linha.sub is not None and linha.paga:
        try:
            return services.periodo_atual(linha.sub)['periodo'] or Pagamento.PERIODO_MENSAL
        except Exception:
            pass
    return ref.periodo if ref is not None else Pagamento.PERIODO_MENSAL


def _linha_subscricao(linha):
    tel = linha.ultimo_tel
    return {
        'id': str(linha.sub.pk) if linha.sub else str(linha.user.pk),
        'utilizador': m.utilizador_repr(linha.user),
        'plano': linha.plano.name,
        'plano_tipo': linha.plano.plan_type,
        'periodo': _periodo_linha(linha),
        'estado': linha.estado,
        'proxima_data': m.iso(linha.proxima_data),
        'pagamento': f'MCX {tel.telefone_mascarado}' if tel and tel.telefone_mascarado else None,
        'nota': linha.nota,
    }


@api_view(['GET'])
@permission_classes(PERMISSOES)
def subscricoes(request):
    estado = (request.query_params.get('estado') or 'todas').strip()
    if estado not in FILTROS_SUBSCRICOES:
        return _erro('Filtro de estado desconhecido.', 'estado_invalido',
                     details={'estado': [f'Use um de: {", ".join(FILTROS_SUBSCRICOES)}.']})
    dias = None
    bruto_dias = (request.query_params.get('dias') or '').strip()
    if bruto_dias:
        try:
            dias = int(bruto_dias)
        except ValueError:
            dias = 0
        if not 1 <= dias <= m.JANELA_A_EXPIRAR.days:
            return _erro('Número de dias inválido.', 'dias_invalido',
                         details={'dias': [f'Use um número de 1 a {m.JANELA_A_EXPIRAR.days}.']})
        if estado != 'a_expirar':
            return _erro('O filtro de dias só se usa com estado=a_expirar.', 'dias_invalido',
                         details={'dias': ['Use dias apenas com estado=a_expirar.']})
    _resolver_pendentes()
    agora = timezone.now()
    linhas = m.classificar_subscricoes(agora)

    contagens = {e: 0 for e in m.ESTADOS_SUBSCRICAO}
    for l in linhas:
        contagens[l.estado] += 1
    # Mesmas definições do resumo e do Painel (metricas.py)
    pagas = sum(1 for l in linhas if l.pago)
    em_teste = sum(1 for l in linhas if l.em_teste_conta)

    if estado != 'todas':
        linhas = [l for l in linhas if l.estado == FILTRO_PARA_ESTADO[estado]]
    if dias is not None:
        # Igual ao "terminam em 3 dias" do resumo/Painel: só assinantes pagos (não atribuídos)
        limite = agora + timedelta(days=dias)
        linhas = [l for l in linhas if l.pago and l.proxima_data and l.proxima_data <= limite]
    q = (request.query_params.get('q') or '').strip().lower()
    if q:
        linhas = [l for l in linhas if q in (l.user.name or '').lower() or q in (l.user.email or '').lower()]

    pagina = _pagina(request)
    total, paginas, inicio = _paginar(linhas, pagina)
    return Response({
        'total': total,
        'pagas': pagas,
        'em_teste': em_teste,
        'contagens': contagens,
        'pagina': pagina,
        'paginas': paginas,
        'resultados': [_linha_subscricao(l) for l in linhas[inicio:inicio + POR_PAGINA]],
    })


# ---------------------------------------------------------------------------
# 3. Lista de pagamentos
# ---------------------------------------------------------------------------

def _linha_pagamento(p, primeiro_pago_em):
    return {
        'id': str(p.id),
        'numero_recibo': p.numero_recibo,
        'utilizador': m.utilizador_repr(p.user),
        'descricao': m.descrever(p, primeiro_pago_em),
        'plano': p.plan.name,
        'periodo': p.periodo,
        'valor_kz': p.valor_kz,
        'desconto_kz': p.desconto_kz,
        'credito_kz': p.credito_abatido_kz,
        'total_kz': p.total_kz,
        'codigo_promocional': p.codigo_promocional or None,
        'metodo': p.metodo,
        'telefone_mascarado': p.telefone_mascarado or None,
        'estado': p.estado,
        'criado_em': m.iso(p.created_at),
        'pago_em': m.iso(p.pago_em),
        'motivo_falha': p.motivo_falha or None,
    }


@api_view(['GET'])
@permission_classes(PERMISSOES)
def pagamentos(request):
    estado = (request.query_params.get('estado') or '').strip()
    validos = dict(Pagamento.ESTADOS)
    if estado and estado not in validos and estado != 'todos':
        return _erro('Filtro de estado desconhecido.', 'estado_invalido',
                     details={'estado': [f'Use um de: {", ".join(validos)}.']})
    _resolver_pendentes()
    qs = Pagamento.objects.select_related('plan', 'user', 'historico').order_by('-created_at')
    if estado and estado != 'todos':
        qs = qs.filter(estado=estado)
    q = (request.query_params.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(user__name__icontains=q) | Q(user__email__icontains=q)
                       | Q(numero_recibo__icontains=q) | Q(codigo_promocional__iexact=q))
    pagina = _pagina(request)
    total, paginas, inicio = _paginar(None, pagina, total=qs.count())
    itens = list(qs[inicio:inicio + POR_PAGINA])
    primeiros = m.primeiros_pagamentos({p.user_id for p in itens})
    return Response({
        'total': total,
        'pagina': pagina,
        'paginas': paginas,
        'resultados': [_linha_pagamento(p, primeiros.get(p.user_id)) for p in itens],
    })


# ---------------------------------------------------------------------------
# 4. Pagamentos falhados, novo pedido e lembrete
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes(PERMISSOES)
def falhados(request):
    _resolver_pendentes()
    agora = timezone.now()
    falhas = sorted(m.falhados_em_aberto(agora).values(), key=lambda f: f.pagamento.updated_at, reverse=True)
    resultados = [{
        'id': str(f.pagamento.id),
        'utilizador': m.utilizador_repr(f.pagamento.user),
        'plano': f.pagamento.plan.name,
        'plano_tipo': f.pagamento.plan.plan_type,
        'periodo': f.pagamento.periodo,
        'valor_kz': f.pagamento.total_kz,
        'falhou_a': m.iso(f.pagamento.updated_at),
        'motivo': m.rotulo_motivo(f.pagamento),
        'motivo_detalhe': f.pagamento.motivo_falha or None,
        'estado': f.pagamento.estado,
        'telefone_mascarado': f.pagamento.telefone_mascarado or None,
        'pedidos': f.pedidos,
    } for f in falhas]
    return Response({
        'total_em_risco_kz': sum(f.pagamento.total_kz for f in falhas),
        'janela_dias': m.DIAS_JANELA_FALHAS,
        'resultados': resultados,
    })


def _pagamento_falhado(pk):
    p = Pagamento.objects.select_related('plan', 'user', 'historico').filter(pk=pk).first()
    if p is None:
        return None, _erro('Não encontrámos este pagamento.', 'nao_encontrado', 404)
    if p.estado not in m.FALHADOS:
        return None, _erro('Só é possível fazer isto com pagamentos recusados ou expirados.',
                           'estado_invalido', 409)
    return p, None


def _falha_em_aberto(p, agora=None):
    """A falha em aberto actual do aluno (``metricas.falhados_em_aberto``) é este pagamento?"""
    agora = agora or timezone.now()
    falha = m.falhados_em_aberto(agora, user_ids=[p.user_id]).get(p.user_id)
    return falha is not None and falha.pagamento.pk == p.pk


def _erro_ja_resolvido():
    return _erro('Esta falha já não está em aberto: o aluno pagou entretanto, tem um pedido em curso, '
                 'tentou outra vez mais tarde ou a falha tem mais de '
                 f'{m.DIAS_JANELA_FALHAS} dias.', 'ja_resolvido', 409)


def _espera(chave, segundos):
    """Limite simples por chave (cache.add). Devolve 0 se pode avançar, senão os segundos a esperar."""
    agora = timezone.now().timestamp()
    if cache.add(chave, agora, segundos):
        return 0
    enviado = cache.get(chave) or agora
    return max(1, int(enviado + segundos - agora))


@api_view(['POST'])
@permission_classes(PERMISSOES)
def novo_pedido(request, pk):
    from django.db import transaction
    from apps.subscriptions.models import UserSubscription

    p, erro = _pagamento_falhado(pk)
    if erro:
        return erro
    if p.metodo != Pagamento.METODO_MCX or not p.telefone:
        return _erro('Este pagamento não foi feito por Multicaixa Express.', 'sem_telefone', 409)
    if not p.user.is_active or (p.user.email or '').endswith('@apagado.invalid'):
        return _erro('A conta deste aluno está suspensa ou foi apagada. Não é possível pedir um novo '
                     'pagamento.', 'utilizador_inactivo', 409)
    services.resolver_pendentes(p.user)
    if Pagamento.objects.filter(user=p.user, estado=Pagamento.PENDENTE).exists():
        return _erro('Este aluno já tem um pedido de pagamento à espera de confirmação.',
                     'pedido_em_curso', 409)
    if Pagamento.objects.filter(user=p.user, estado=Pagamento.PAGO, pago_em__gt=p.created_at).exists():
        return _erro('O aluno já pagou depois desta falha. Não é preciso um novo pedido.', 'ja_pago', 409)

    chave = f'admin:novo-pedido:{p.pk}'
    espera = _espera(chave, ESPERA_NOVO_PEDIDO)
    if espera:
        minutos = max(1, math.ceil(espera / 60))
        return _erro(f'Já foi feito um novo pedido para este pagamento há pouco. Pode pedir outro daqui a '
                     f'{minutos} min.', 'novo_pedido_recente', 429, aguardar_segundos=espera)

    avisos = []
    try:
        with transaction.atomic():
            # Bloqueia a subscrição do aluno: dois pedidos em paralelo não passam os dois a verificação.
            if not UserSubscription.objects.select_for_update().filter(user=p.user).exists():
                type(p.user).objects.select_for_update().filter(pk=p.user_id).exists()
            if Pagamento.objects.filter(user=p.user, estado=Pagamento.PENDENTE).exists():
                cache.delete(chave)
                return _erro('Este aluno já tem um pedido de pagamento à espera de confirmação.',
                             'pedido_em_curso', 409)
            if not _falha_em_aberto(p):
                cache.delete(chave)
                return _erro_ja_resolvido()
            codigo = p.codigo_promocional if (p.codigo_promocional and p.desconto_kz) else None
            try:
                novo = services.criar_pagamento_mcx(p.user, telefone=p.telefone, plan_id=str(p.plan_id),
                                                    periodo=p.periodo, codigo_promocional=codigo)
            except services.ErroPagamento as e:
                if codigo and e.codigo == 'codigo_promocional':
                    avisos.append(f'O código {codigo} já não é válido para este aluno: o novo pedido é sem '
                                  'desconto.')
                    novo = services.criar_pagamento_mcx(p.user, telefone=p.telefone, plan_id=str(p.plan_id),
                                                        periodo=p.periodo, codigo_promocional=None)
                else:
                    raise
    except services.ErroPagamento as e:
        cache.delete(chave)
        if not p.plan.is_active and e.status == 404:
            return _erro(f'O plano {p.plan.name} já não está disponível, por isso não é possível pedir um novo '
                         'pagamento deste plano.', 'plano_indisponivel', 409)
        return _erro(e.mensagem, e.codigo or 'erro_pagamento', e.status)
    novo = Pagamento.objects.select_related('plan', 'user', 'historico').get(pk=novo.pk)
    if not p.plan.is_active:
        avisos.append(f'O plano {p.plan.name} já não está à venda; o pedido foi feito porque o aluno o tem.')
    if novo.total_kz != p.total_kz:
        avisos.append(f'O valor mudou de {formatar_kz(p.total_kz)} para {formatar_kz(novo.total_kz)}.')
    primeiros = m.primeiros_pagamentos({novo.user_id})
    dados = _linha_pagamento(novo, primeiros.get(novo.user_id))
    dados['expira_em'] = m.iso(novo.expira_em)
    dados['simulado'] = services._simulado(novo)
    dados['pedido_anterior'] = str(p.id)
    dados['aviso'] = ' '.join(avisos) or None
    return Response(dados, status=201)


def _textos_lembrete(p, agora):
    """
    Textos do lembrete conforme o caso: o aluno ainda tem o plano pago em vigor (renovação falhada:
    "manter o acesso") ou não tem (primeiro pagamento, ou plano já terminado: "activar o plano").
    """
    sub = getattr(p.user, 'subscription', None)
    tem_acesso = m.sub_paga(sub, agora)
    fim = (timezone.localtime(sub.expires_at, FUSO_ANGOLA).strftime('%d/%m/%Y') if tem_acesso else None)
    if tem_acesso:
        accao = f'para manter o acesso aos cursos depois de {fim}'
    else:
        accao = f'para activar o plano {p.plan.name}'
    return tem_acesso, fim, accao


def _enviar_lembrete(p, tem_acesso, fim, accao):
    from apps.users.email_service import _contexto_base, _enviar, _link
    ctx = {
        **_contexto_base(p.user, p.user.email),
        'plano': p.plan.name,
        'periodo': p.get_periodo_display().lower(),
        'valor': formatar_kz(p.total_kz),
        'link': _link(LINK_SUBSCRICAO),
        'tem_acesso': tem_acesso,
        'fim': fim,
        'accao': accao,
    }
    return _enviar(f'O pagamento do plano {p.plan.name} não foi concluído - ProEnglish',
                   'pagamentos/emails/lembrete_pagamento.html', ctx, p.user.email)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def lembrete(request, pk):
    p, erro = _pagamento_falhado(pk)
    if erro:
        return erro
    if not p.user.email:
        return _erro('Este aluno não tem email.', 'sem_email', 409)
    services.resolver_pendentes(p.user)
    agora_dt = timezone.now()
    if not _falha_em_aberto(p, agora_dt):
        return _erro_ja_resolvido()
    chave = f'admin:lembrete-pagamento:{p.pk}'
    espera = _espera(chave, ESPERA_LEMBRETE)
    if espera:
        horas = max(1, math.ceil(espera / 3600))
        return _erro(f'Já enviámos um lembrete deste pagamento hoje. Pode enviar outro daqui a {horas} h.',
                     'lembrete_ja_enviado', 429, aguardar_segundos=espera)
    tem_acesso, fim, accao = _textos_lembrete(p, agora_dt)
    if not _enviar_lembrete(p, tem_acesso, fim, accao):
        cache.delete(chave)
        return _erro('Não conseguimos enviar o email. Tente outra vez daqui a pouco.', 'email_falhou', 502)
    try:
        from apps.users.models import Notification
        Notification.notify(
            p.user, Notification.KIND_SUBSCRIPTION,
            title='O seu pagamento não foi concluído',
            body=(f'O pagamento do plano {p.plan.name} ({formatar_kz(p.total_kz)}) não foi concluído. '
                  f'Tente outra vez com Multicaixa Express {accao}.'),
            link=LINK_SUBSCRICAO,
            dedupe_key=f'lembrete-admin:{p.pk}:{_hoje().isoformat()}',
        )
    except Exception:
        logger.exception('Falha ao criar o aviso do lembrete (pagamento %s)', p.pk)
    return Response({'enviado': True})


# ---------------------------------------------------------------------------
# 5. Relatórios
# ---------------------------------------------------------------------------

def _periodo(request):
    bruto = request.query_params.get('periodo') or '30'
    try:
        dias = int(bruto)
    except (TypeError, ValueError):
        dias = None
    if dias not in PERIODOS_RELATORIO:
        return None
    return dias


def calcular_relatorio(dias, agora=None):
    """
    Relatório dos últimos ``dias`` dias:

    * ``periodo_receita_kz``: recebido nos últimos ``dias`` dias; ``periodo_anterior_receita_kz``: nos
      ``dias`` dias antes desses; ``receita_variacao_pct`` compara os dois.
    * ``receita_mes_kz`` / ``receita_mes_anterior_kz``: mês de calendário actual (até agora) e anterior.
    * ``receita_recorrente_mes_kz``: receita recorrente mensal dos assinantes pagos (o pagamento que
      cobre o período actual de cada um; os anuais a dividir por 12). ``receita_por_assinante_kz`` é
      esse valor a dividir pelo número de assinantes pagos.
    * ``receita_por_mes``: max(3, meses do período) meses de calendário, o último é o actual.
    """
    agora = agora or timezone.now()
    mes = m.inicio_mes(agora)
    fim_agora = agora + timedelta(seconds=1)
    receita_mes = m.receita(mes, fim_agora)
    anterior = m.receita(m.somar_meses(mes, -1), mes)
    janela = timedelta(days=dias)
    receita_periodo = m.receita(fim_agora - janela, fim_agora)
    receita_periodo_anterior = m.receita(fim_agora - 2 * janela, fim_agora - janela)

    intervalos = m.Intervalos()
    planos = m.planos_em_vigor(agora)
    ids_pagos = m.pagantes(planos)
    n_pagas = len(ids_pagos)
    recorrente, _ = m.receita_recorrente_mensal(agora)

    n_meses = max(3, PERIODOS_RELATORIO[dias])
    primeiro = m.somar_meses(mes, -(n_meses - 1))
    valores = {}
    for quando, total in (Pagamento.objects.filter(estado=Pagamento.PAGO, pago_em__gte=primeiro,
                                                   pago_em__lt=fim_agora)
                          .annotate(total=m.TOTAL_KZ).values_list('pago_em', 'total')):
        local = timezone.localtime(quando, FUSO_ANGOLA)
        chave = (local.year, local.month)
        valores[chave] = valores.get(chave, 0) + int(total or 0)
    por_mes = []
    for i in range(n_meses):
        inicio = m.somar_meses(primeiro, i)
        seguinte = m.somar_meses(inicio, 1)
        instante = min(agora, seguinte - timedelta(microseconds=1))
        por_mes.append({
            'mes': f'{inicio.year}-{inicio.month:02d}',
            'nome_curto': m.NOMES_MES_CURTOS[inicio.month - 1],
            'valor_kz': valores.get((inicio.year, inicio.month), 0),
            'assinantes': len(intervalos.pagantes_em(instante)),
        })

    # Províncias dos assinantes pagos
    nomes = m.nomes_provincias()
    contagem, sem = {}, 0
    if m.user_tem_provincia():
        for slug in m.User.objects.filter(pk__in=ids_pagos).values_list('provincia', flat=True):
            if slug:
                contagem[slug] = contagem.get(slug, 0) + 1
            else:
                sem += 1
    else:
        sem = n_pagas
    por_provincia = sorted(
        ({'provincia': s, 'nome': m.nome_provincia(s, nomes), 'assinantes': n} for s, n in contagem.items()),
        key=lambda x: (-x['assinantes'], x['nome']))

    retencao, coorte = m.retencao_3_meses(agora, dias, intervalos)
    conversao, testes = m.teste_para_pago(agora, dias)
    return {
        'periodo': dias,
        'periodo_receita_kz': receita_periodo,
        'periodo_anterior_receita_kz': receita_periodo_anterior,
        'receita_variacao_pct': m.pct(receita_periodo - receita_periodo_anterior, receita_periodo_anterior),
        'receita_mes_kz': receita_mes,
        'receita_mes_anterior_kz': anterior,
        'receita_mes_variacao_pct': m.pct(receita_mes - anterior, anterior),
        'receita_recorrente_mes_kz': recorrente,
        'receita_por_assinante_kz': round(recorrente / n_pagas) if n_pagas else None,
        'retencao_3_meses_pct': retencao,
        'retencao_coorte': coorte,
        'teste_para_pago_pct': conversao,
        'testes_terminados': testes,
        'receita_por_mes': por_mes,
        'por_provincia': por_provincia,
        'sem_provincia': sem,
        'assinantes_total': n_pagas,
        'gerado_em': m.iso(agora),
    }


@api_view(['GET'])
@permission_classes(PERMISSOES)
def relatorios(request):
    dias = _periodo(request)
    if dias is None:
        return _erro('Período inválido.', 'periodo_invalido',
                     details={'periodo': ['Use 30, 90, 180 ou 365 dias.']})
    _resolver_pendentes()
    return Response(calcular_relatorio(dias))


NUMERO_PT = re.compile(r'-?\d+(,\d+)?')


def celula(valor):
    """
    Evita fórmulas no Excel em células de texto (=, +, -, @, tab, CR). Números (e números em texto
    no formato pt-PT, como "-12,5") ficam como estão, para continuarem numéricos.
    """
    if valor is None:
        return ''
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return valor
    texto = str(valor)
    if NUMERO_PT.fullmatch(texto):
        return texto
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


def _num_pt(valor):
    return '' if valor is None else str(valor).replace('.', ',')


@api_view(['GET'])
@permission_classes(PERMISSOES)
def relatorios_exportar(request):
    dias = _periodo(request)
    if dias is None:
        return _erro('Período inválido.', 'periodo_invalido',
                     details={'periodo': ['Use 30, 90, 180 ou 365 dias.']})
    _resolver_pendentes()
    r = calcular_relatorio(dias)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';', lineterminator='\r\n')
    linha = lambda *vals: w.writerow([celula(v) for v in vals])  # noqa: E731

    linha('Relatório ProEnglish', f'Últimos {dias} dias', f'Gerado a {_hoje().strftime("%d/%m/%Y")}')
    linha()
    linha('Indicador', 'Valor')
    linha(f'Receita dos últimos {dias} dias (Kz)', r['periodo_receita_kz'])
    linha(f'Receita dos {dias} dias anteriores (Kz)', r['periodo_anterior_receita_kz'])
    linha('Variação face ao período anterior (%)', _num_pt(r['receita_variacao_pct']))
    linha('Receita deste mês (Kz)', r['receita_mes_kz'])
    linha('Receita do mês anterior (Kz)', r['receita_mes_anterior_kz'])
    linha('Receita recorrente mensal (Kz)', r['receita_recorrente_mes_kz'])
    linha('Receita recorrente mensal por assinante (Kz)', r['receita_por_assinante_kz'])
    linha('Retenção ao 3.º mês (%)', _num_pt(r['retencao_3_meses_pct']))
    linha('Testes que passaram a pago (%)', _num_pt(r['teste_para_pago_pct']))
    linha('Assinantes pagos', r['assinantes_total'])
    linha()
    linha('Mês', 'Receita (Kz)', 'Assinantes pagos')
    for item in r['receita_por_mes']:
        linha(f'{item["nome_curto"]} {item["mes"][:4]}', item['valor_kz'], item['assinantes'])
    linha()
    linha('Província', 'Assinantes pagos')
    for item in r['por_provincia']:
        linha(item['nome'], item['assinantes'])
    linha('Sem província indicada', r['sem_provincia'])

    resp = HttpResponse(('﻿' + buf.getvalue()).encode('utf-8'), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="relatorio-proenglish-{dias}-dias.csv"'
    return resp
