"""
Administração de planos e códigos promocionais (montado em /api/v1/admin/).

Planos:
    GET   planos/              lista com limites, utilizadores e assinantes
    PATCH planos/<id>/         nome, descricao, preços, dias_teste, destaque, activo, limites, certificados
Códigos promocionais:
    GET   codigos/?estado=todos|activos|rascunhos|esgotados|expirados|desligados
    POST  codigos/             cria (rascunho por omissão); devolve também "exemplo"
    GET   codigos/<id>/        detalhe + utilizações
    PATCH codigos/<id>/        edita (desconto/aplica/duracao/codigo só enquanto não foi usado: 409);
                               "aplica" parcial mantém as chaves que faltam
    Cada código traz "bloqueado" (já usado: pago, confirmado ou reservado num pagamento pendente).
    Duração "meses" só com aplica.periodo "mensal" (400 em aplica.periodo).
    POST  codigos/<id>/activar/ | desligar/

Preços: quem já paga mantém o preço contratado (UserSubscription.preco_*_kz) nas
renovações; mudar o preço aqui só afecta subscrições novas.
Erros: {error, message, code, details: {campo: [mensagens]}}.
"""

import re
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.exceptions import corpo_erro
from apps.core.permissions import EAdministrador

from .models import PromoCodeUsage, PromotionalCode, SubscriptionPlan, UserSubscription
from .services import FUSO_ANGOLA, kz_inteiro

PERMISSOES = [EAdministrador]
TIPOS_PAGOS = ('PREMIUM', 'PREMIUM_PLUS')
MAX_DIAS_TESTE = 30
RE_CODIGO = re.compile(r'^[A-Z0-9]{3,20}$')


class ErroValidacao(Exception):
    def __init__(self, details, mensagem=None):
        self.details = details
        primeiro = next(iter(details.values()))[0] if details else 'Dados inválidos.'
        self.mensagem = mensagem or primeiro
        super().__init__(self.mensagem)


def _erro(mensagem, code, status_http=400, details=None):
    return Response(corpo_erro(mensagem, code, details), status=status_http)


def _erro_validacao(e):
    return _erro(e.mensagem, 'validacao', 400, e.details)


def _fmt_kz(valor):
    return f'{int(valor):,}'.replace(',', ' ') + ' Kz'


def _inteiro(valor, campo, erros, minimo=None, maximo=None, nulo=False):
    """Inteiro validado (ou None se ``nulo``); regista o erro em ``erros``."""
    if valor is None:
        if nulo:
            return None
        erros.setdefault(campo, []).append('Indique um número.')
        return None
    if isinstance(valor, bool):
        erros.setdefault(campo, []).append('Indique um número inteiro.')
        return None
    try:
        dec = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        erros.setdefault(campo, []).append('Indique um número inteiro.')
        return None
    if dec != dec.to_integral_value():
        erros.setdefault(campo, []).append('Indique um número inteiro.')
        return None
    n = int(dec)
    if minimo is not None and n < minimo:
        erros.setdefault(campo, []).append(f'Tem de ser pelo menos {minimo}.')
        return None
    if maximo is not None and n > maximo:
        erros.setdefault(campo, []).append(f'Tem de ser no máximo {maximo}.')
        return None
    return n


def _booleano(valor, campo, erros):
    if not isinstance(valor, bool):
        erros.setdefault(campo, []).append('Indique true ou false.')
        return None
    return valor


# ===========================================================================
# Planos
# ===========================================================================

def _contagens():
    """{plan_id: (utilizadores, assinantes)} com a mesma regra de "plano em vigor" da plataforma."""
    agora = timezone.now()
    em_vigor = Q(expires_at__gt=agora) & ~Q(status='EXPIRED')
    linhas = (UserSubscription.objects.values('plan_id', 'plan__plan_type')
              .annotate(
                  em_vigor=Count('id', filter=em_vigor),
                  pagantes=Count('id', filter=em_vigor & ~Q(status='TRIAL')),
                  caducadas=Count('id', filter=~em_vigor)))
    r = {}
    caducadas_pagas = 0
    gratuito_id = None
    for l in linhas:
        if l['plan__plan_type'] == 'FREE':
            gratuito_id = l['plan_id']
            r[l['plan_id']] = [l['em_vigor'] + l['caducadas'], 0]
        else:
            r[l['plan_id']] = [l['em_vigor'], l['pagantes']]
            caducadas_pagas += l['caducadas']
    # Um plano pago que terminou e ainda não foi passado ao Gratuito já é, na prática, Gratuito
    if gratuito_id is not None:
        r[gratuito_id][0] += caducadas_pagas
    return r


def _plano_repr(p, contagens=None):
    contagens = contagens if contagens is not None else _contagens()
    utilizadores, assinantes = contagens.get(p.id, (0, 0))
    return {
        'id': str(p.id),
        'tipo': p.plan_type,
        'nome': p.name,
        'descricao': p.description,
        'preco_mensal_kz': kz_inteiro(p.monthly_price or 0),
        'preco_anual_kz': 0 if p.plan_type == 'FREE' else (kz_inteiro(p.yearly_price) if p.yearly_price else None),
        'dias_teste': p.dias_teste,
        'destaque': p.destaque,
        'activo': p.is_active,
        'limites': {
            # null = ilimitado (no modelo: lições None/0 e vidas 0 são ilimitadas)
            'licoes_dia': p.daily_lessons_limit or None,
            'vidas': p.hearts_limit or None,
            'conversa_min_dia': p.daily_speaking_minutes,
            'conversa_min_mes': p.monthly_speaking_minutes,
            'teste_conversa_min_dia': p.trial_speaking_minutes,
            # Gratuito: dias depois do registo em que há tutor (com teste_conversa_min_dia por dia).
            'teste_conversa_dias': p.trial_days,
            'sessoes_nativo_mes': p.native_teacher_sessions,
            'protecoes_semana': p.streak_freeze,
            # Avaliações de pronúncia detalhadas (Azure) por dia; 0 = nenhuma.
            'pronuncia_detalhada_dia': p.daily_detailed_pronunciation_limit,
        },
        'certificados': p.certificates,
        'utilizadores': utilizadores,
        'assinantes': assinantes,
    }


@api_view(['GET'])
@permission_classes(PERMISSOES)
def planos(request):
    contagens = _contagens()
    return Response([_plano_repr(p, contagens) for p in SubscriptionPlan.objects.order_by('sort_order', 'monthly_price')])


def _validar_plano(p, d):
    """Aplica ``d`` (PATCH) a ``p`` em memória. Devolve (alterações extra a fazer, vidas novas)."""
    erros = {}
    gratuito = p.plan_type == 'FREE'
    conhecidos = {'nome', 'descricao', 'preco_mensal_kz', 'preco_anual_kz', 'dias_teste', 'destaque',
                  'activo', 'limites', 'certificados'}
    desconhecidos = sorted(set(d) - conhecidos)
    if desconhecidos:
        erros['campos'] = [f'Campo desconhecido: {", ".join(desconhecidos)}.']

    if 'nome' in d:
        nome = (d['nome'] or '').strip() if isinstance(d['nome'], str) else ''
        if not nome:
            erros['nome'] = ['Indique o nome do plano.']
        elif len(nome) > 100:
            erros['nome'] = ['O nome tem no máximo 100 caracteres.']
        else:
            p.name = nome
    if 'descricao' in d:
        if not isinstance(d['descricao'], str):
            erros['descricao'] = ['Indique um texto.']
        else:
            p.description = d['descricao'].strip()

    if 'preco_mensal_kz' in d:
        v = _inteiro(d['preco_mensal_kz'], 'preco_mensal_kz', erros, minimo=0, maximo=10_000_000)
        if v is not None:
            if gratuito and v != 0:
                erros['preco_mensal_kz'] = ['O plano Gratuito tem sempre o preço 0 Kz.']
            elif not gratuito and v <= 0:
                erros['preco_mensal_kz'] = ['O preço mensal de um plano pago tem de ser maior que 0 Kz.']
            else:
                p.monthly_price = Decimal(v)
    if 'preco_anual_kz' in d:
        v = _inteiro(d['preco_anual_kz'], 'preco_anual_kz', erros, minimo=0, maximo=100_000_000, nulo=True)
        if 'preco_anual_kz' not in erros:
            if gratuito and v:
                erros['preco_anual_kz'] = ['O plano Gratuito tem sempre o preço 0 Kz.']
            elif not gratuito and v is not None and v <= 0:
                erros['preco_anual_kz'] = ['O preço anual tem de ser maior que 0 Kz (ou vazio, sem plano anual).']
            else:
                p.yearly_price = Decimal(v) if v is not None else (Decimal('0') if gratuito else None)
    if not gratuito and 'preco_mensal_kz' not in erros and 'preco_anual_kz' not in erros and p.yearly_price:
        mensal = Decimal(p.monthly_price or 0)
        if Decimal(p.yearly_price) > mensal * 12:
            erros['preco_anual_kz'] = [f'O preço anual não pode ser maior que 12 meses ({_fmt_kz(mensal * 12)}).']
        elif Decimal(p.yearly_price) < mensal:
            erros['preco_anual_kz'] = [f'O preço anual não pode ser menor que um mês ({_fmt_kz(mensal)}).']

    if 'dias_teste' in d:
        v = _inteiro(d['dias_teste'], 'dias_teste', erros, minimo=0, maximo=MAX_DIAS_TESTE)
        if v is not None:
            if gratuito and v:
                erros['dias_teste'] = ['O plano Gratuito não tem período de teste.']
            else:
                p.dias_teste = v
    if 'destaque' in d:
        v = _booleano(d['destaque'], 'destaque', erros)
        if v is not None:
            p.destaque = v
    if 'activo' in d:
        v = _booleano(d['activo'], 'activo', erros)
        if v is not None:
            if gratuito and not v:
                erros['activo'] = ['O plano Gratuito não pode ser desactivado.']
            else:
                p.is_active = v
    if 'certificados' in d:
        v = _booleano(d['certificados'], 'certificados', erros)
        if v is not None:
            p.certificates = v

    vidas_novas = None
    if 'limites' in d:
        lim = d['limites']
        if not isinstance(lim, dict):
            erros['limites'] = ['Indique os limites como um objecto.']
        else:
            outros = sorted(set(lim) - {'licoes_dia', 'vidas', 'conversa_min_dia', 'conversa_min_mes',
                                        'teste_conversa_min_dia', 'teste_conversa_dias', 'sessoes_nativo_mes',
                                        'protecoes_semana', 'pronuncia_detalhada_dia'})
            if outros:
                erros['limites'] = [f'Limite desconhecido: {", ".join(outros)}.']
            if 'licoes_dia' in lim:
                v = _inteiro(lim['licoes_dia'], 'limites.licoes_dia', erros, minimo=1, maximo=1000, nulo=True)
                if 'limites.licoes_dia' not in erros:
                    p.daily_lessons_limit = v
            if 'vidas' in lim:
                v = _inteiro(lim['vidas'], 'limites.vidas', erros, minimo=1, maximo=100, nulo=True)
                if 'limites.vidas' not in erros:
                    p.hearts_limit = v or 0  # 0 = ilimitadas no modelo
                    vidas_novas = p.hearts_limit
            if 'conversa_min_dia' in lim:
                v = _inteiro(lim['conversa_min_dia'], 'limites.conversa_min_dia', erros, minimo=0, maximo=1440,
                             nulo=True)
                if 'limites.conversa_min_dia' not in erros:
                    p.daily_speaking_minutes = v
            if 'conversa_min_mes' in lim:
                v = _inteiro(lim['conversa_min_mes'], 'limites.conversa_min_mes', erros, minimo=0, maximo=44640,
                             nulo=True)
                if 'limites.conversa_min_mes' not in erros:
                    p.monthly_speaking_minutes = v
            if 'teste_conversa_min_dia' in lim:
                v = _inteiro(lim['teste_conversa_min_dia'], 'limites.teste_conversa_min_dia', erros, minimo=0, maximo=1440)
                if v is not None:
                    p.trial_speaking_minutes = v
            if 'teste_conversa_dias' in lim:
                v = _inteiro(lim['teste_conversa_dias'], 'limites.teste_conversa_dias', erros, minimo=0, maximo=60)
                if v is not None:
                    p.trial_days = v
            if 'sessoes_nativo_mes' in lim:
                v = _inteiro(lim['sessoes_nativo_mes'], 'limites.sessoes_nativo_mes', erros, minimo=0, maximo=100)
                if v is not None:
                    p.native_teacher_sessions = v
            if 'protecoes_semana' in lim:
                v = _inteiro(lim['protecoes_semana'], 'limites.protecoes_semana', erros, minimo=0, maximo=7)
                if v is not None:
                    p.streak_freeze = v
            if 'pronuncia_detalhada_dia' in lim:
                v = _inteiro(lim['pronuncia_detalhada_dia'], 'limites.pronuncia_detalhada_dia', erros, minimo=0,
                             maximo=500)
                if v is not None:
                    p.daily_detailed_pronunciation_limit = v
    if erros:
        raise ErroValidacao(erros)
    return vidas_novas


@api_view(['PATCH'])
@permission_classes(PERMISSOES)
def plano_detalhe(request, pk):
    d = request.data if isinstance(request.data, dict) else {}
    with transaction.atomic():
        p = SubscriptionPlan.objects.select_for_update().filter(pk=pk).first()
        if p is None:
            return _erro('Plano não encontrado.', 'nao_encontrado', 404)
        try:
            vidas = _validar_plano(p, d)
        except ErroValidacao as e:
            return _erro_validacao(e)
        if p.destaque:
            SubscriptionPlan.objects.exclude(pk=p.pk).filter(destaque=True).update(destaque=False)
        p.save()
        if vidas:
            # Ninguém fica com mais vidas do que o novo limite
            UserSubscription.objects.filter(plan=p, current_hearts__gt=vidas).update(current_hearts=vidas)
    return Response(_plano_repr(p))


# ===========================================================================
# Códigos promocionais
# ===========================================================================

TIPO_API = {'PERCENTAGE': 'percentagem', 'FIXED_AMOUNT': 'valor'}
TIPO_MODELO = {v: k for k, v in TIPO_API.items()}
NOMES_PLANOS = {'PREMIUM': 'Premium', 'PREMIUM_PLUS': 'Premium Plus'}
FILTROS = {
    'activos': 'activo', 'rascunhos': 'rascunho', 'esgotados': 'esgotado',
    'expirados': 'expirado', 'desligados': 'desligado',
}


def _numero(valor):
    v = Decimal(valor or 0)
    return int(v) if v == v.to_integral_value() else float(v)


def _data_fim(dt):
    return timezone.localtime(dt, FUSO_ANGOLA).date().isoformat() if dt else None


def _fim_do_dia(dia):
    return datetime.combine(dia, time.max, tzinfo=FUSO_ANGOLA)


def _planos_codigo(c):
    cache = getattr(c, '_prefetched_objects_cache', {}).get('applicable_plans')
    planos = list(cache) if cache is not None else list(c.applicable_plans.all())
    return sorted((p.plan_type for p in planos), key=lambda t: TIPOS_PAGOS.index(t) if t in TIPOS_PAGOS else 9)


def _desconto_txt(tipo, valor):
    return f'{_numero(valor)}%' if tipo == 'PERCENTAGE' else _fmt_kz(valor)


def descricao_codigo(tipo, valor, planos, periodo, duracao, meses, so_primeira):
    """Resumo pt-PT, ex.: "20% no 1.º mês", "5 000 Kz nos primeiros 3 meses, só no Premium"."""
    if duracao == PromotionalCode.DURACAO_MESES:
        quando = 'no 1.º mês' if meses == 1 else f'nos primeiros {meses} meses'
    elif duracao == PromotionalCode.DURACAO_SEMPRE:
        quando = 'em todos os pagamentos'
    else:
        quando = 'no 1.º mês' if periodo == 'mensal' else 'no 1.º pagamento'
    texto = f'{_desconto_txt(tipo, valor)} {quando}'
    nomes = ' e '.join(NOMES_PLANOS.get(t, t) for t in planos)
    per = {'mensal': 'mensal', 'anual': 'anual'}.get(periodo)
    if nomes and per:
        texto += f', só no {nomes} {per}'
    elif nomes:
        texto += f', só no {nomes}'
    elif per:
        texto += f', só no pagamento {per}'
    if so_primeira:
        texto += ', só na 1.ª compra'
    return texto


def exemplo_codigo(c):
    """
    Ex.: "o Premium anual passa de 149 500 Kz para 89 700 Kz no 1.º pagamento". Usa as mesmas
    regras do pagamento: "meses" só no mensal; "primeiro" e "sempre" também no anual.
    """
    from .services import desconto_do_codigo
    tipos = _planos_codigo(c) or ['PREMIUM']
    plano = SubscriptionPlan.objects.filter(plan_type__in=tipos).order_by('sort_order').first()
    if plano is None:
        return None
    if c.duracao == PromotionalCode.DURACAO_MESES or c.periodo_aplicavel == 'mensal':
        periodo = 'mensal'
    elif c.periodo_aplicavel == 'anual':
        periodo = 'anual'
    else:
        periodo = 'anual' if plano.yearly_price else 'mensal'
    if periodo == 'anual' and not plano.yearly_price:
        return f'o {plano.name} não tem pagamento anual: este código não se aplica a ele'
    base = Decimal(plano.yearly_price if periodo == 'anual' else plano.monthly_price)
    final = base - desconto_do_codigo(c, base)
    if c.duracao == PromotionalCode.DURACAO_SEMPRE:
        quando = 'em todos os pagamentos'
    elif c.duracao == PromotionalCode.DURACAO_MESES:
        quando = 'no 1.º mês' if (c.duracao_meses or 1) == 1 else f'nos primeiros {c.duracao_meses} meses'
    else:
        quando = 'no 1.º mês' if periodo == 'mensal' else 'no 1.º pagamento'
    return f'o {plano.name} {periodo} passa de {_fmt_kz(base)} para {_fmt_kz(kz_inteiro(final))} {quando}'


def _codigo_repr(c, agora=None, bloqueado=None):
    if bloqueado is None:
        bloqueado = _codigo_usado(c)
    return {
        'id': str(c.id),
        'codigo': c.code,
        'desconto': {'tipo': TIPO_API.get(c.discount_type, c.discount_type.lower()), 'valor': _numero(c.discount_value)},
        'aplica': {'planos': _planos_codigo(c), 'periodo': c.periodo_aplicavel},
        'duracao': {'tipo': c.duracao, 'meses': c.duracao_meses if c.duracao == PromotionalCode.DURACAO_MESES else None},
        'so_primeira_compra': c.first_time_users_only,
        'max_usos': c.max_uses,
        'usos': c.current_uses,
        'termina': _data_fim(c.valid_until),
        'estado': c.estado_actual(agora),
        'descricao': descricao_codigo(
            c.discount_type, c.discount_value, _planos_codigo(c), c.periodo_aplicavel, c.duracao,
            c.duracao_meses, c.first_time_users_only),
        'criado_em': c.created_at.isoformat() if c.created_at else None,
        # Já usado (pago, confirmado ou reservado num pagamento pendente): o código, o desconto,
        # a que se aplica e a duração já não se podem mudar.
        'bloqueado': bloqueado,
    }


def _inicio_mes(agora):
    local = timezone.localtime(agora, FUSO_ANGOLA)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _numeros(agora):
    from apps.pagamentos.models import Pagamento
    codigos = list(PromotionalCode.objects.all())
    estados = [c.estado_actual(agora) for c in codigos]
    inicio = _inicio_mes(agora)
    usos_mes = PromoCodeUsage.objects.filter(estado=PromoCodeUsage.CONFIRMADO, used_at__gte=inicio)
    desconto_mes = (Pagamento.objects
                    .filter(estado=Pagamento.PAGO, pago_em__gte=inicio, codigo_promocional__isnull=False)
                    .aggregate(t=Sum('desconto_kz'))['t'] or 0)

    # Dos que pagaram com um código e cujo período já terminou, quantos voltaram a pagar
    coorte = list(Pagamento.objects
                  .filter(estado=Pagamento.PAGO, promo_renovacao=False, codigo_promocional__isnull=False,
                          desconto_kz__gt=0, periodo_fim__lte=agora, pago_em__isnull=False)
                  .values('user_id', 'pago_em'))
    continuam = None
    if coorte:
        primeiro = {}
        for linha in coorte:
            if linha['user_id'] not in primeiro or linha['pago_em'] < primeiro[linha['user_id']]:
                primeiro[linha['user_id']] = linha['pago_em']
        voltaram = sum(
            1 for uid, quando in primeiro.items()
            if Pagamento.objects.filter(user_id=uid, estado=Pagamento.PAGO, pago_em__gt=quando).exists())
        continuam = round(100 * voltaram / len(primeiro))
    return {
        'activos': estados.count('activo'),
        'rascunhos': estados.count('rascunho'),
        'usados_mes': usos_mes.count(),
        'pessoas_mes': usos_mes.values('user_id').distinct().count(),
        'desconto_mes_kz': int(desconto_mes),
        'continuam_2_mes_pct': continuam,
    }


def _ler_codigo(d, c=None):
    """Valida o corpo (POST completo ou PATCH parcial). Devolve dict de campos do modelo + planos."""
    erros = {}
    novo = c is None
    campos = {}
    conhecidos = {'codigo', 'desconto', 'aplica', 'duracao', 'so_primeira_compra', 'max_usos', 'termina', 'estado'}
    desconhecidos = sorted(set(d) - conhecidos - {'id', 'usos', 'descricao', 'exemplo'})
    if desconhecidos:
        erros['campos'] = [f'Campo desconhecido: {", ".join(desconhecidos)}.']
    if 'usos' in d and c is not None and d['usos'] != c.current_uses:
        erros['usos'] = ['O número de utilizações não se pode alterar.']

    if novo or 'codigo' in d:
        codigo = d.get('codigo')
        codigo = codigo.strip().upper() if isinstance(codigo, str) else ''
        if not RE_CODIGO.match(codigo):
            erros['codigo'] = ['O código tem de 3 a 20 letras ou algarismos, sem espaços nem acentos.']
        elif PromotionalCode.objects.filter(code__iexact=codigo).exclude(pk=getattr(c, 'pk', None)).exists():
            erros['codigo'] = [f'Já existe um código {codigo}.']
        else:
            campos['code'] = codigo

    if novo or 'desconto' in d:
        desc = d.get('desconto')
        if not isinstance(desc, dict) or desc.get('tipo') not in TIPO_MODELO:
            erros['desconto.tipo'] = ['Escolha o tipo de desconto: "percentagem" ou "valor".']
        else:
            tipo = TIPO_MODELO[desc['tipo']]
            if tipo == 'PERCENTAGE':
                v = _inteiro(desc.get('valor'), 'desconto.valor', erros, minimo=1, maximo=100)
            else:
                v = _inteiro(desc.get('valor'), 'desconto.valor', erros, minimo=1, maximo=10_000_000)
            if v is not None:
                campos['discount_type'] = tipo
                campos['discount_value'] = Decimal(v)

    planos = None
    if novo or 'aplica' in d:
        aplica = d.get('aplica', {}) if novo else d.get('aplica')
        aplica = {} if aplica is None and novo else aplica
        if not isinstance(aplica, dict):
            erros['aplica'] = ['Indique a que planos e período o código se aplica.']
        else:
            # PATCH parcial: as chaves que faltam ficam como estavam
            if novo or 'planos' in aplica:
                lista = aplica.get('planos', [])
                if lista is None:
                    lista = []
                if not isinstance(lista, list) or any(t not in TIPOS_PAGOS for t in lista):
                    erros['aplica.planos'] = ['Os planos têm de ser "PREMIUM" e/ou "PREMIUM_PLUS" (vazio = todos os pagos).']
                else:
                    planos = sorted(set(lista), key=TIPOS_PAGOS.index)
            if novo or 'periodo' in aplica:
                periodo = aplica.get('periodo', 'todos')
                if periodo not in ('todos', 'mensal', 'anual'):
                    erros['aplica.periodo'] = ['O período tem de ser "todos", "mensal" ou "anual".']
                else:
                    campos['periodo_aplicavel'] = periodo

    if novo or 'duracao' in d:
        dur = d.get('duracao', {'tipo': 'primeiro'}) if novo else d.get('duracao')
        if dur is None and novo:
            dur = {'tipo': 'primeiro'}
        if not isinstance(dur, dict) or dur.get('tipo') not in ('primeiro', 'meses', 'sempre'):
            erros['duracao.tipo'] = ['A duração tem de ser "primeiro", "meses" ou "sempre".']
        else:
            campos['duracao'] = dur['tipo']
            if dur['tipo'] == 'meses':
                m = _inteiro(dur.get('meses'), 'duracao.meses', erros, minimo=2, maximo=24)
                if m is not None:
                    campos['duracao_meses'] = m
            else:
                campos['duracao_meses'] = None

    if 'so_primeira_compra' in d:
        v = _booleano(d['so_primeira_compra'], 'so_primeira_compra', erros)
        if v is not None:
            campos['first_time_users_only'] = v
    if 'max_usos' in d:
        v = _inteiro(d['max_usos'], 'max_usos', erros, minimo=1, maximo=1_000_000, nulo=True)
        if 'max_usos' not in erros:
            if c is not None and v is not None and v < c.current_uses:
                erros['max_usos'] = [f'Já foi usado {c.current_uses} vezes: o máximo não pode ser menor.']
            else:
                campos['max_uses'] = v
    elif novo:
        campos['max_uses'] = None
    if 'termina' in d:
        t = d['termina']
        if t in (None, ''):
            campos['valid_until'] = None
        else:
            try:
                dia = datetime.strptime(str(t)[:10], '%Y-%m-%d').date()
            except ValueError:
                erros['termina'] = ['Indique a data no formato AAAA-MM-DD.']
            else:
                hoje = timezone.localtime(timezone.now(), FUSO_ANGOLA).date()
                if dia < hoje:
                    erros['termina'] = ['A data de fim não pode ser no passado.']
                else:
                    campos['valid_until'] = _fim_do_dia(dia)
    if 'estado' in d:
        if not novo:
            erros['estado'] = ['Use activar/ ou desligar/ para mudar o estado.']
        elif d['estado'] not in ('rascunho', 'activo'):
            erros['estado'] = ['Um código novo começa em "rascunho" ou "activo".']
        else:
            campos['estado'] = d['estado']
    # "Os primeiros N meses" só vale em pagamentos mensais (num ano daria o desconto ao ano inteiro)
    duracao = campos.get('duracao', getattr(c, 'duracao', None))
    periodo = campos.get('periodo_aplicavel', getattr(c, 'periodo_aplicavel', 'todos'))
    if duracao == PromotionalCode.DURACAO_MESES and periodo != 'mensal' and 'duracao.tipo' not in erros \
            and 'aplica.periodo' not in erros:
        erros['aplica.periodo'] = ['Um código com desconto nos primeiros meses só vale no pagamento mensal: '
                                   'escolha o período "mensal".']
    if erros:
        raise ErroValidacao(erros)
    return campos, planos


def _usos_reais(codigos):
    """
    Códigos (ids) com utilizações que contam para os bloquear: pagamentos pagos, utilizações
    confirmadas (ex.: activação por um administrador) e reservas de pagamentos ainda pendentes
    e dentro do prazo. Pagamentos falhados, expirados ou cancelados não contam.
    """
    from apps.pagamentos.models import Pagamento
    codigos = list(codigos)
    if not codigos:
        return set()
    por_code = {c.code: c.pk for c in codigos}
    ids = {c.pk for c in codigos}
    usados = set(PromoCodeUsage.objects.filter(promo_code_id__in=ids, estado=PromoCodeUsage.CONFIRMADO)
                 .values_list('promo_code_id', flat=True))
    usados |= {por_code[code] for code in Pagamento.objects.filter(
        estado=Pagamento.PAGO, codigo_promocional__in=list(por_code)).values_list('codigo_promocional', flat=True)
        if code in por_code}
    usados |= set(PromoCodeUsage.objects.filter(
        promo_code_id__in=ids, estado=PromoCodeUsage.RESERVADO,
        pagamento__estado=Pagamento.PENDENTE, pagamento__expira_em__gt=timezone.now(),
    ).values_list('promo_code_id', flat=True))
    return usados


def _codigo_usado(c):
    return c.pk in _usos_reais([c])


def _guardar(c, campos, planos):
    for k, v in campos.items():
        setattr(c, k, v)
    if not c.valid_from:
        c.valid_from = timezone.now()
    tipos = planos if planos is not None else (_planos_codigo(c) if c.pk else [])
    c.description = descricao_codigo(c.discount_type, c.discount_value, tipos, c.periodo_aplicavel,
                                     c.duracao, c.duracao_meses, c.first_time_users_only)
    c.name = c.code
    if c.valid_until and c.valid_from and c.valid_until <= c.valid_from:
        c.valid_from = min(timezone.now(), c.valid_until - timedelta(seconds=1))
    c.save()
    if planos is not None:
        c.applicable_plans.set(SubscriptionPlan.objects.filter(plan_type__in=planos))
        if hasattr(c, '_prefetched_objects_cache'):
            c._prefetched_objects_cache.pop('applicable_plans', None)
    return c


@api_view(['GET', 'POST'])
@permission_classes(PERMISSOES)
def codigos(request):
    agora = timezone.now()
    if request.method == 'POST':
        d = request.data if isinstance(request.data, dict) else {}
        try:
            campos, planos = _ler_codigo(d)
        except ErroValidacao as e:
            return _erro_validacao(e)
        campos.setdefault('estado', PromotionalCode.RASCUNHO)
        with transaction.atomic():
            c = _guardar(PromotionalCode(), campos, planos or [])
        return Response({**_codigo_repr(c, agora, bloqueado=False), 'exemplo': exemplo_codigo(c)}, status=201)

    filtro = request.query_params.get('estado') or 'todos'
    if filtro != 'todos' and filtro not in FILTROS:
        return _erro('Filtro inválido: use todos, activos, rascunhos, esgotados, expirados ou desligados.',
                     'validacao', 400, {'estado': ['Filtro inválido.']})
    lista = list(PromotionalCode.objects.prefetch_related('applicable_plans').order_by('-created_at'))
    usados = _usos_reais(lista)
    resultados = []
    for c in lista:
        if filtro != 'todos' and c.estado_actual(agora) != FILTROS[filtro]:
            continue
        resultados.append(_codigo_repr(c, agora, bloqueado=c.pk in usados))
    return Response({'numeros': _numeros(agora), 'resultados': resultados})


def _obter_codigo(pk, bloquear=False):
    qs = PromotionalCode.objects.all()
    if bloquear:
        qs = qs.select_for_update()
    return qs.filter(pk=pk).first()


def _utilizacoes(c):
    from apps.pagamentos.models import Pagamento
    linhas = []
    pagamentos = (Pagamento.objects.filter(codigo_promocional=c.code, estado=Pagamento.PAGO)
                  .select_related('user', 'plan').order_by('-pago_em'))
    com_pagamento = set()
    for p in pagamentos:
        if p.uso_promo_id:
            com_pagamento.add(p.uso_promo_id)
        linhas.append({
            'utilizador': {'id': str(p.user_id), 'nome': _nome(p.user), 'email': p.user.email},
            'data': p.pago_em.isoformat() if p.pago_em else None,
            'valor_desconto_kz': p.desconto_kz,
            'plano': p.plan.plan_type,
            'periodo': p.periodo,
            'renovacao': p.promo_renovacao,
        })
    # Utilizações sem pagamento (ex.: activação por um administrador)
    for u in (PromoCodeUsage.objects.filter(promo_code=c, estado=PromoCodeUsage.CONFIRMADO)
              .exclude(pk__in=com_pagamento).select_related('user')):
        if Pagamento.objects.filter(uso_promo_id=u.pk).exists():
            continue
        linhas.append({
            'utilizador': {'id': str(u.user_id), 'nome': _nome(u.user), 'email': u.user.email},
            'data': u.used_at.isoformat(),
            'valor_desconto_kz': kz_inteiro(u.discount_applied),
            'plano': None,
            'periodo': None,
            'renovacao': False,
        })
    linhas.sort(key=lambda l: l['data'] or '', reverse=True)
    return linhas


def _nome(user):
    return (getattr(user, 'name', '') or '').strip() or user.get_full_name() or user.username


@api_view(['GET', 'PATCH'])
@permission_classes(PERMISSOES)
def codigo_detalhe(request, pk):
    agora = timezone.now()
    if request.method == 'GET':
        c = _obter_codigo(pk)
        if c is None:
            return _erro('Código não encontrado.', 'nao_encontrado', 404)
        return Response({**_codigo_repr(c, agora), 'exemplo': exemplo_codigo(c), 'utilizacoes': _utilizacoes(c)})

    d = request.data if isinstance(request.data, dict) else {}
    with transaction.atomic():
        c = _obter_codigo(pk, bloquear=True)
        if c is None:
            return _erro('Código não encontrado.', 'nao_encontrado', 404)
        try:
            campos, planos = _ler_codigo(d, c)
        except ErroValidacao as e:
            return _erro_validacao(e)
        bloqueados = []
        usado = _codigo_usado(c)
        if usado:
            if 'code' in campos and campos['code'] != c.code:
                bloqueados.append('codigo')
            if any(k in campos and campos[k] != getattr(c, k) for k in ('discount_type', 'discount_value')):
                bloqueados.append('desconto')
            if (planos is not None and planos != _planos_codigo(c)) or (
                    'periodo_aplicavel' in campos and campos['periodo_aplicavel'] != c.periodo_aplicavel):
                bloqueados.append('aplica')
            if any(k in campos and campos[k] != getattr(c, k) for k in ('duracao', 'duracao_meses')):
                bloqueados.append('duracao')
        if bloqueados:
            return _erro('Este código já foi usado: o código, o desconto, a que se aplica e a duração já não '
                         'se podem mudar. Crie um código novo.', 'codigo_em_uso', 409,
                         {k: ['Já não se pode mudar: o código foi usado.'] for k in bloqueados})
        _guardar(c, campos, planos)
    return Response({**_codigo_repr(c, agora, bloqueado=usado), 'exemplo': exemplo_codigo(c)})


def _mudar_estado(pk, novo):
    with transaction.atomic():
        c = _obter_codigo(pk, bloquear=True)
        if c is None:
            return _erro('Código não encontrado.', 'nao_encontrado', 404)
        if novo == PromotionalCode.ACTIVO and c.expirado():
            return _erro('Este código já expirou. Mude a data de fim antes de o activar.', 'codigo_expirado', 409,
                         {'termina': ['A data de fim já passou.']})
        if c.estado != novo:
            c.estado = novo
            c.save(update_fields=['estado', 'is_active', 'updated_at'])
    return Response(_codigo_repr(c))


@api_view(['POST'])
@permission_classes(PERMISSOES)
def codigo_activar(request, pk):
    return _mudar_estado(pk, PromotionalCode.ACTIVO)


@api_view(['POST'])
@permission_classes(PERMISSOES)
def codigo_desligar(request, pk):
    return _mudar_estado(pk, PromotionalCode.DESLIGADO)
