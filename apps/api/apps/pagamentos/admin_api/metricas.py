"""
Contas da administração: estado de cada subscrição, pagamentos falhados e métricas de receita.

Estas definições são as mesmas no Painel (apps.users.admin_api.utilizadores.painel) e em Subscrições;
os dois usam as funções deste módulo. Datas em hora de Luanda quando se fala de "mês".

* **Universo**: alunos (``role='student'``), sem as contas apagadas (anonimizadas). Contas suspensas
  contam (continuam a ter o plano que pagaram).
* **Plano em vigor**: subscrição de um plano que não é o Gratuito, estado ACTIVE ou CANCELED e
  ``expires_at`` no futuro; ou estado TRIAL com o teste a decorrer (``trial_ends_at``, ou
  ``expires_at`` se não houver, no futuro).
* **Pago** (assinante pago): plano em vigor (não TRIAL) cujo instante actual está coberto por um
  ``Pagamento`` confirmado (``pago``) desse mesmo plano com valor maior que 0 Kz, isto é,
  ``periodo_inicio <= agora < min(periodo_fim, creditado_em)`` e ``total_kz + credito_kz > 0``.
  Um período a 0 Kz por um código de 100 % não é "pago" (o aluno não pagou nada); um período a 0 Kz
  pago só com crédito de um plano anterior (que foi pago) é. Ver ``valor_pago``.
* **Em teste**: subscrição TRIAL com o teste a decorrer.
* **Atribuído**: plano em vigor (não TRIAL) sem pagamento que o cubra (dado por um administrador,
  ou período a 0 Kz com um código de 100 %).
* **A pagar num instante T** (para comparar com o passado): há um pagamento ``pago`` com valor > 0
  cujo período ``[periodo_inicio, fim)`` contém T, com ``fim = min(periodo_fim, creditado_em)``.
* **Falhado em aberto**: a última tentativa de pagamento do utilizador (ignorando as canceladas) está
  ``recusado`` ou ``expirado``, foi criada nos últimos ``JANELA_FALHAS`` (30) dias e o utilizador não
  tem nenhum pagamento pendente (um pendente é uma nova tentativa em curso).
* **Falhados da semana**: falhados em aberto cuja falha foi nos últimos 7 dias.
* **Terminam em 3 dias**: assinantes pagos (não em teste, não atribuídos) cujo plano termina em 3 dias
  ou menos, sem pagamento pendente e sem falhado em aberto (esses já contam nos falhados). É o mesmo
  conjunto que a lista de subscrições mostra com ``estado=a_expirar&dias=3``.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.subscriptions.models import SubscriptionHistory, UserSubscription
from apps.subscriptions.services import FUSO_ANGOLA

from ..models import Pagamento

User = get_user_model()

DIAS_JANELA_FALHAS = 30
JANELA_FALHAS = timedelta(days=DIAS_JANELA_FALHAS)
JANELA_A_EXPIRAR = timedelta(days=7)
DIAS_TERMINAM = timedelta(days=3)
JANELA_FALHADOS_SEMANA = timedelta(days=7)

TOTAL_KZ = F('valor_kz') - F('desconto_kz') - F('credito_abatido_kz')
# Valor do período: o que foi pago mais o crédito (pago) trazido do plano anterior
VALOR_PERIODO_KZ = TOTAL_KZ + F('credito_kz')

# Categorias de um plano em vigor
CAT_PAGO = 'pago'
CAT_TESTE = 'em_teste'
CAT_ATRIBUIDO = 'atribuido'
FALHADOS = (Pagamento.RECUSADO, Pagamento.EXPIRADO)

NOMES_MES_CURTOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

ACTIVA = 'activa'
EM_TESTE = 'em_teste'
A_EXPIRAR = 'a_expirar'
FALHOU = 'falhou'
CANCELADA = 'cancelada'
ESTADOS_SUBSCRICAO = (ACTIVA, EM_TESTE, A_EXPIRAR, FALHOU, CANCELADA)

NOTA_SEM_PAGAMENTO = 'Ainda sem pagamento'
NOTA_CANCELOU = 'Cancelou a renovação'
NOTA_LEMBRETES = 'Lembretes desligados'
NOTA_ATRIBUIDO = 'Plano atribuído sem pagamento'
PERIODO_TESTE = 'teste'

# Províncias de Angola (divisão de 2024, 21 províncias). Cópia local de reserva: a lista oficial é
# apps.users.models.PROVINCIAS (choices de User.provincia) e tem prioridade.
_PROVINCIAS_LOCAIS = [
    ('bengo', 'Bengo'), ('benguela', 'Benguela'), ('bie', 'Bié'), ('cabinda', 'Cabinda'),
    ('cuando', 'Cuando'), ('cubango', 'Cubango'), ('cuanza-norte', 'Cuanza Norte'),
    ('cuanza-sul', 'Cuanza Sul'), ('cunene', 'Cunene'), ('huambo', 'Huambo'), ('huila', 'Huíla'),
    ('icolo-e-bengo', 'Icolo e Bengo'), ('luanda', 'Luanda'), ('lunda-norte', 'Lunda Norte'),
    ('lunda-sul', 'Lunda Sul'), ('malanje', 'Malanje'), ('moxico', 'Moxico'),
    ('moxico-leste', 'Moxico Leste'), ('namibe', 'Namibe'), ('uige', 'Uíge'), ('zaire', 'Zaire'),
    ('cuando-cubango', 'Cuando Cubango'),
]


def nomes_provincias():
    nomes = {}
    try:
        from apps.users import models as mod  # lista oficial (choices de User.provincia)
        lista = getattr(mod, 'PROVINCIAS', None) or []
        itens = lista.items() if isinstance(lista, dict) else lista
        for item in itens:
            if isinstance(item, dict):
                slug, nome = item.get('slug') or item.get('id') or item.get('valor'), item.get('nome')
            else:
                slug, nome = item[0], item[1]
            if slug and nome:
                nomes[str(slug)] = str(nome)
    except Exception:
        pass
    for slug, nome in _PROVINCIAS_LOCAIS:
        nomes.setdefault(slug, nome)
    return nomes


def nome_provincia(slug, nomes=None):
    nomes = nomes if nomes is not None else nomes_provincias()
    if slug in nomes:
        return nomes[slug]
    alt = str(slug).replace('_', '-').lower()
    return nomes.get(alt) or str(slug).replace('-', ' ').replace('_', ' ').title()


def user_tem_provincia():
    try:
        User._meta.get_field('provincia')
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def iso(dt):
    return dt.isoformat() if dt else None


def iniciais(nome, email=''):
    partes = [p for p in (nome or '').split() if p]
    if partes:
        return ''.join(p[0].upper() for p in partes[:2])
    return (email or '?')[:1].upper()


def utilizador_repr(u):
    return {'id': str(u.pk), 'nome': (u.name or '').strip() or u.email, 'email': u.email,
            'iniciais': iniciais(u.name, u.email)}


def pct(numerador, denominador):
    if not denominador:
        return None
    return round(numerador * 100 / denominador, 1)


def inicio_mes(dt):
    """Primeiro instante do mês de ``dt`` em Luanda (aware)."""
    local = timezone.localtime(dt, FUSO_ANGOLA)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def somar_meses(inicio, n):
    """Início do mês ``n`` meses depois (n pode ser negativo) de um início de mês em Luanda."""
    ano, mes = divmod(inicio.year * 12 + (inicio.month - 1) + n, 12)
    return datetime(ano, mes + 1, 1, tzinfo=FUSO_ANGOLA)


def receita(desde, ate):
    """Total recebido (kz) em pagamentos confirmados com ``desde <= pago_em < ate``."""
    v = (Pagamento.objects.filter(estado=Pagamento.PAGO, pago_em__gte=desde, pago_em__lt=ate)
         .aggregate(t=Sum(TOTAL_KZ))['t'])
    return int(v or 0)


# ---------------------------------------------------------------------------
# Quem está a pagar
# ---------------------------------------------------------------------------

def subs_pagas(agora):
    return (UserSubscription.objects
            .filter(expires_at__gt=agora, status__in=('ACTIVE', 'CANCELED'))
            .exclude(plan__plan_type='FREE'))


def subs_em_teste(agora):
    return UserSubscription.objects.filter(status='TRIAL').filter(
        Q(trial_ends_at__gt=agora) | Q(trial_ends_at__isnull=True, expires_at__gt=agora))


def sub_paga(sub, agora):
    return bool(sub and sub.plan.plan_type != 'FREE' and sub.status in ('ACTIVE', 'CANCELED')
                and sub.expires_at and sub.expires_at > agora)


def sub_em_teste(sub, agora):
    if not sub or sub.status != 'TRIAL':
        return False
    fim = sub.trial_ends_at or sub.expires_at
    return bool(fim and fim > agora)


def fim_teste(sub):
    return sub.trial_ends_at or sub.expires_at


def alunos():
    """Universo das contagens de planos: alunos, sem as contas apagadas (anonimizadas)."""
    return User.objects.filter(role='student').exclude(email__endswith='@apagado.invalid')


def pagamentos_que_cobrem(agora):
    """Pagamentos confirmados com valor > 0 cujo período cobre ``agora`` (ver "Pago" no topo)."""
    return (Pagamento.objects
            .filter(estado=Pagamento.PAGO, periodo_inicio__lte=agora, periodo_fim__gt=agora)
            .filter(Q(creditado_em__isnull=True) | Q(creditado_em__gt=agora))
            .annotate(_valor=VALOR_PERIODO_KZ).filter(_valor__gt=0))


@dataclass
class PlanoEmVigor:
    categoria: str  # CAT_PAGO | CAT_TESTE | CAT_ATRIBUIDO
    plan_id: object
    plan_type: str
    expires_at: Optional[datetime]


def planos_em_vigor(agora):
    """{user_id: PlanoEmVigor} dos alunos com plano pago em vigor ou em teste (definições no topo)."""
    cobertos = set(pagamentos_que_cobrem(agora).values_list('user_id', 'plan_id'))
    res = {}
    subs = (UserSubscription.objects.filter(user__in=alunos()).exclude(plan__plan_type='FREE')
            .values_list('user_id', 'plan_id', 'plan__plan_type', 'status', 'trial_ends_at', 'expires_at'))
    for uid, plan_id, tipo, status, fim_teste_, expira in subs:
        if status == 'TRIAL':
            fim = fim_teste_ or expira
            if fim and fim > agora:
                res[uid] = PlanoEmVigor(CAT_TESTE, plan_id, tipo, fim)
        elif status in ('ACTIVE', 'CANCELED') and expira and expira > agora:
            cat = CAT_PAGO if (uid, plan_id) in cobertos else CAT_ATRIBUIDO
            res[uid] = PlanoEmVigor(cat, plan_id, tipo, expira)
    return res


def pagantes(planos):
    return {uid for uid, p in planos.items() if p.categoria == CAT_PAGO}


def por_plano(planos, n_alunos=None):
    """
    Alunos por plano: ``[{plano, nome, utilizadores, pagos, em_teste, atribuidos}]``. Nos planos pagos,
    ``utilizadores = pagos + em_teste + atribuidos``; no Gratuito, ``utilizadores`` são os restantes
    alunos (os outros campos ficam a 0).
    """
    from apps.subscriptions.models import SubscriptionPlan
    n_alunos = alunos().count() if n_alunos is None else n_alunos
    contagem = defaultdict(lambda: {CAT_PAGO: 0, CAT_TESTE: 0, CAT_ATRIBUIDO: 0})
    for p in planos.values():
        contagem[p.plan_id][p.categoria] += 1
    linhas = []
    for plano in SubscriptionPlan.objects.all().order_by('sort_order', 'monthly_price'):
        if plano.plan_type == 'FREE':
            linha = {'utilizadores': max(0, n_alunos - len(planos)), 'pagos': 0, 'em_teste': 0, 'atribuidos': 0}
        else:
            c = contagem.get(plano.pk)
            if c is None and not plano.is_active:
                continue  # plano desactivado sem ninguém
            c = c or {CAT_PAGO: 0, CAT_TESTE: 0, CAT_ATRIBUIDO: 0}
            linha = {'utilizadores': sum(c.values()), 'pagos': c[CAT_PAGO], 'em_teste': c[CAT_TESTE],
                     'atribuidos': c[CAT_ATRIBUIDO]}
        linhas.append({'plano': plano.plan_type, 'nome': plano.name, **linha})
    return linhas


def com_pendente(agora):
    """Utilizadores com um pagamento pendente ainda dentro do prazo (nova tentativa em curso)."""
    return set(Pagamento.objects.filter(estado=Pagamento.PENDENTE, expira_em__gt=agora)
               .values_list('user_id', flat=True))


def terminam_em_breve(agora, planos, falhas=None, dias=DIAS_TERMINAM):
    """Assinantes pagos cujo plano termina em ``dias`` ou menos, sem pendente nem falhado em aberto."""
    falhas = falhados_em_aberto(agora) if falhas is None else falhas
    pendentes = com_pendente(agora)
    limite = agora + dias
    return {uid for uid, p in planos.items()
            if p.categoria == CAT_PAGO and p.expires_at <= limite
            and uid not in pendentes and uid not in falhas}


def falhados_semana(agora, falhas=None):
    """Falhados em aberto cuja falha (``updated_at``) foi nos últimos 7 dias."""
    falhas = falhados_em_aberto(agora) if falhas is None else falhas
    desde = agora - JANELA_FALHADOS_SEMANA
    return [f for f in falhas.values() if f.pagamento.updated_at >= desde]


def receita_recorrente_mensal(agora):
    """
    (receita recorrente mensal em kz, n.º de assinantes pagos): para cada assinante pago, o pagamento
    que cobre o período actual, a dividir por 12 se for anual. Usa o valor efectivamente cobrado
    (``total_kz``) mais o crédito trazido, como em ``valor_pago``.
    """
    planos = planos_em_vigor(agora)
    ids = pagantes(planos)
    por_user = {}
    for uid, plan_id, periodo, valor in (pagamentos_que_cobrem(agora).filter(user_id__in=ids)
                                         .values_list('user_id', 'plan_id', 'periodo', '_valor')
                                         .order_by('user_id', '-periodo_inicio')):
        if uid in por_user or planos[uid].plan_id != plan_id:
            continue
        por_user[uid] = int(valor or 0) / (12 if periodo == Pagamento.PERIODO_ANUAL else 1)
    return int(round(sum(por_user.values()))), len(ids)


class Intervalos:
    """Períodos pagos por utilizador (de pagamentos confirmados), para saber quem pagava em T."""

    def __init__(self, user_ids=None):
        qs = (Pagamento.objects.filter(estado=Pagamento.PAGO, periodo_inicio__isnull=False,
                                       periodo_fim__isnull=False)
              .annotate(_valor=VALOR_PERIODO_KZ).filter(_valor__gt=0))
        if user_ids is not None:
            qs = qs.filter(user_id__in=user_ids)
        self.por_user = defaultdict(list)
        self.primeiro_inicio = {}
        for uid, ini, fim, cred in qs.values_list('user_id', 'periodo_inicio', 'periodo_fim', 'creditado_em'):
            fim_ef = min(fim, cred) if cred else fim
            self.por_user[uid].append((ini, fim_ef))
            if uid not in self.primeiro_inicio or ini < self.primeiro_inicio[uid]:
                self.primeiro_inicio[uid] = ini

    def paga_em(self, uid, t):
        return any(ini <= t < fim for ini, fim in self.por_user.get(uid, ()))

    def pagantes_em(self, t):
        return {uid for uid in self.por_user if self.paga_em(uid, t)}


# ---------------------------------------------------------------------------
# Falhados em aberto
# ---------------------------------------------------------------------------

@dataclass
class Falha:
    pagamento: Pagamento
    pedidos: int


def falhados_em_aberto(agora, user_ids=None):
    """{user_id: Falha} com a tentativa falhada mais recente de cada utilizador ainda por resolver."""
    desde = agora - JANELA_FALHAS
    candidatos = Pagamento.objects.filter(estado__in=FALHADOS, created_at__gte=desde)
    if user_ids is not None:
        candidatos = candidatos.filter(user_id__in=user_ids)
    uids = set(candidatos.values_list('user_id', flat=True))
    if not uids:
        return {}
    recentes = (Pagamento.objects.filter(user_id__in=uids, created_at__gte=desde)
                .select_related('plan', 'user').order_by('user_id', '-created_at'))
    ultimo_pago = {}
    for uid, quando in (Pagamento.objects.filter(user_id__in=uids, estado=Pagamento.PAGO)
                        .values_list('user_id', 'pago_em')):
        if quando and (uid not in ultimo_pago or quando > ultimo_pago[uid]):
            ultimo_pago[uid] = quando

    por_user = defaultdict(list)
    for p in recentes:
        por_user[p.user_id].append(p)

    resultado = {}
    for uid, lista in por_user.items():
        if any(p.estado == Pagamento.PENDENTE for p in lista):
            continue  # nova tentativa em curso
        tentativas = [p for p in lista if p.estado != Pagamento.CANCELADO]
        if not tentativas or tentativas[0].estado not in FALHADOS:
            continue
        falha = tentativas[0]
        # Pedidos deste período: tentativas do mesmo plano depois do último pagamento confirmado
        corte = ultimo_pago.get(uid)
        pedidos = sum(1 for p in tentativas
                      if p.plan_id == falha.plan_id and p.estado in FALHADOS
                      and (corte is None or p.created_at > corte))
        resultado[uid] = Falha(falha, max(1, pedidos))
    return resultado


def rotulo_motivo(p):
    """Motivo da falha em pt-PT curto, para a lista da administração."""
    texto = (p.motivo_falha or '').lower()
    if 'saldo' in texto:
        return 'Saldo insuficiente'
    if p.estado == Pagamento.EXPIRADO or 'expirou' in texto:
        return 'Expirou sem confirmação'
    if 'contactar' in texto or 'indispon' in texto:
        return 'Multicaixa Express indisponível'
    if 'limite' in texto:
        return 'Limite do Multicaixa Express excedido'
    if 'telem' in texto or 'recusad' in texto:
        return 'Recusado no telemóvel'
    return 'Pagamento recusado'


# ---------------------------------------------------------------------------
# Descrição de um pagamento ("Premium, 1.º mês com BEMVINDO")
# ---------------------------------------------------------------------------

def primeiros_pagamentos(user_ids):
    """{user_id: pago_em do primeiro pagamento confirmado}."""
    res = {}
    for uid, quando in (Pagamento.objects.filter(user_id__in=user_ids, estado=Pagamento.PAGO)
                        .values_list('user_id', 'pago_em')):
        if quando and (uid not in res or quando < res[uid]):
            res[uid] = quando
    return res


def descrever(p, primeiro_pago_em):
    renovacao = bool(p.historico_id and getattr(p.historico, 'event_type', '') == 'RENEWED')
    quando = p.pago_em if p.estado == Pagamento.PAGO else p.created_at
    primeiro = not renovacao and (primeiro_pago_em is None or (quando and quando <= primeiro_pago_em))
    if p.periodo == Pagamento.PERIODO_ANUAL:
        texto = 'renovação anual' if renovacao else 'anual'
    elif primeiro:
        texto = '1.º mês'
    else:
        texto = 'renovação mensal' if renovacao else 'mensal'
    if p.codigo_promocional and p.desconto_kz:
        texto += f' com {p.codigo_promocional}'
    return f'{p.plan.name}, {texto}'


# ---------------------------------------------------------------------------
# Estado de cada subscrição (lista da administração)
# ---------------------------------------------------------------------------

@dataclass
class LinhaSubscricao:
    user: object
    sub: Optional[UserSubscription]
    estado: str
    plano: object  # SubscriptionPlan
    proxima_data: Optional[datetime]
    nota: Optional[str]
    ultimo_tel: Optional[Pagamento] = None
    pagamento_ref: Optional[Pagamento] = None  # pagamento que dá o período (falha ou último pago)
    paga: bool = False  # plano pago em vigor (com ou sem pagamento)
    teste: bool = False
    pago: bool = False  # assinante pago (ver definições): conta para o rodapé "pagas"
    em_teste_conta: bool = False  # em teste, no universo das contagens
    extras: dict = field(default_factory=dict)


ORDEM_ESTADO = {FALHOU: 0, A_EXPIRAR: 1, EM_TESTE: 2, ACTIVA: 3, CANCELADA: 4}


def classificar_subscricoes(agora):
    """
    Uma linha por utilizador com subscrição "de interesse" (plano pago, teste, ou algum pagamento):

    * ``falhou``: tem um falhado em aberto (ver ``falhados_em_aberto``). Tem prioridade.
    * ``em_teste``: subscrição TRIAL com o teste a decorrer.
    * ``a_expirar``: plano pago em vigor que termina em ``JANELA_A_EXPIRAR`` (7 dias) ou menos, sem
      pagamento pendente (não há débito automático: sem novo pagamento, o plano acaba).
    * ``activa``: restante plano pago em vigor.
    * ``cancelada``: já pagou (ou teve teste) e agora não tem plano pago em vigor.
    Utilizadores no Gratuito que nunca pagaram nem tiveram teste (só tentativas canceladas) ficam de fora.
    """
    falhas = falhados_em_aberto(agora)
    planos = planos_em_vigor(agora)
    ids_pagamentos = set(Pagamento.objects.values_list('user_id', flat=True).distinct())
    subs = {s.user_id: s for s in UserSubscription.objects.select_related('plan', 'user').filter(
        Q(user_id__in=ids_pagamentos) | ~Q(plan__plan_type='FREE') | Q(status='TRIAL')
        | Q(trial_ends_at__isnull=False))}
    uids = set(subs) | ids_pagamentos
    users = {u.pk: u for u in User.objects.filter(pk__in=uids)}

    ultimo_pago, ultimo_tel, pendentes = {}, {}, set()
    for p in (Pagamento.objects.filter(user_id__in=uids).select_related('plan')
              .only('id', 'user_id', 'plan', 'periodo', 'estado', 'telefone', 'pago_em', 'created_at',
                    'periodo_fim', 'metodo').order_by('-created_at')):
        if p.estado == Pagamento.PENDENTE:
            pendentes.add(p.user_id)
        if p.telefone and p.user_id not in ultimo_tel:
            ultimo_tel[p.user_id] = p
        if p.estado == Pagamento.PAGO and p.user_id not in ultimo_pago:
            ultimo_pago[p.user_id] = p

    linhas = []
    for uid in uids:
        user = users.get(uid)
        if user is None:
            continue
        sub = subs.get(uid)
        paga = sub_paga(sub, agora)
        teste = sub_em_teste(sub, agora)
        ja_pagou = uid in ultimo_pago
        cancelou = bool(sub and sub.status == 'CANCELED')
        sem_lembretes = bool(sub and not sub.lembretes_renovacao)
        categoria = planos[uid].categoria if uid in planos else None
        falha = falhas.get(uid)
        nota = None
        if falha:
            estado = FALHOU
            plano = falha.pagamento.plan
            proxima = sub.expires_at if paga else None
            ref = falha.pagamento
            nota = None if ja_pagou else NOTA_SEM_PAGAMENTO
        elif teste:
            estado = EM_TESTE
            plano, proxima, ref = sub.plan, fim_teste(sub), None
            nota = None if ja_pagou else NOTA_SEM_PAGAMENTO
        elif paga:
            termina_breve = sub.expires_at <= agora + JANELA_A_EXPIRAR
            estado = A_EXPIRAR if (termina_breve and uid not in pendentes) else ACTIVA
            plano, proxima, ref = sub.plan, sub.expires_at, ultimo_pago.get(uid)
            if cancelou:
                nota = NOTA_CANCELOU
            elif categoria == CAT_ATRIBUIDO:
                nota = NOTA_ATRIBUIDO
            elif not ja_pagou:
                nota = NOTA_SEM_PAGAMENTO
            elif sem_lembretes:
                nota = NOTA_LEMBRETES
        elif ja_pagou or (sub and sub.trial_ends_at):
            estado = CANCELADA
            ref = ultimo_pago.get(uid)
            plano = ref.plan if ref else sub.plan
            proxima = None
            nota = NOTA_CANCELOU if (sub and sub.status == 'CANCELED') else (
                None if ja_pagou else NOTA_SEM_PAGAMENTO)
        else:
            continue
        linhas.append(LinhaSubscricao(
            user=user, sub=sub, estado=estado, plano=plano, proxima_data=proxima, nota=nota,
            ultimo_tel=ultimo_tel.get(uid), pagamento_ref=ref, paga=paga, teste=teste,
            pago=categoria == CAT_PAGO, em_teste_conta=categoria == CAT_TESTE))

    longe = datetime.max.replace(tzinfo=FUSO_ANGOLA)
    linhas.sort(key=lambda l: (ORDEM_ESTADO[l.estado], l.proxima_data or longe,
                               (l.user.name or l.user.email or '').lower()))
    return linhas


# ---------------------------------------------------------------------------
# Taxas
# ---------------------------------------------------------------------------

def utilizadores_base():
    """Universo dos alunos (para "passam a pagar")."""
    return User.objects.filter(role='student', is_active=True)


def taxas_30_dias(agora, intervalos=None):
    """(passam_a_pagar_pct, cancelam_pct) com base nos períodos pagos."""
    intervalos = intervalos or Intervalos()
    antes = agora - timedelta(days=30)
    pagavam_antes = intervalos.pagantes_em(antes)
    pagam_agora = intervalos.pagantes_em(agora)

    criados_antes = set(utilizadores_base().filter(created_at__lte=antes).values_list('pk', flat=True))
    gratuitos_antes = criados_antes - pagavam_antes
    passam = pct(len(gratuitos_antes & pagam_agora), len(gratuitos_antes))
    cancelam = pct(len(pagavam_antes - pagam_agora), len(pagavam_antes))
    return passam, cancelam


def retencao_3_meses(agora, dias_periodo, intervalos=None):
    """
    Coorte: utilizadores cujo 1.º período pago começou entre ``agora - 90 dias - período`` e
    ``agora - 90 dias``. Retidos: ainda a pagar no 3.º mês (61 dias depois do início do 1.º período).
    """
    intervalos = intervalos or Intervalos()
    fim = agora - timedelta(days=90)
    ini = fim - timedelta(days=dias_periodo)
    coorte = [uid for uid, primeiro in intervalos.primeiro_inicio.items() if ini <= primeiro < fim]
    retidos = [uid for uid in coorte
               if intervalos.paga_em(uid, intervalos.primeiro_inicio[uid] + timedelta(days=61))]
    return pct(len(retidos), len(coorte)), len(coorte)


def teste_para_pago(agora, dias_periodo):
    """
    Testes que terminaram no período (``trial_ends_at`` da subscrição, ou evento TRIAL_ENDED) e que
    passaram a pago: há um pagamento confirmado com valor > 0 depois do início do teste (evento
    TRIAL_STARTED, ou 31 dias antes do fim se não houver registo).
    """
    desde = agora - timedelta(days=dias_periodo)
    fins = {}
    for uid, fim in (UserSubscription.objects.filter(trial_ends_at__gt=desde, trial_ends_at__lte=agora)
                     .values_list('user_id', 'trial_ends_at')):
        fins[uid] = fim
    for uid, quando in (SubscriptionHistory.objects
                        .filter(event_type='TRIAL_ENDED', created_at__gt=desde, created_at__lte=agora)
                        .values_list('subscription__user_id', 'created_at')):
        fins.setdefault(uid, quando)
    if not fins:
        return None, 0
    inicios = {}
    for uid, quando in (SubscriptionHistory.objects
                        .filter(event_type='TRIAL_STARTED', subscription__user_id__in=fins)
                        .values_list('subscription__user_id', 'created_at')):
        if quando <= fins[uid] and (uid not in inicios or quando > inicios[uid]):
            inicios[uid] = quando
    pagos = defaultdict(list)
    for uid, quando in (Pagamento.objects
                        .filter(user_id__in=fins, estado=Pagamento.PAGO)
                        .annotate(total=TOTAL_KZ).filter(total__gt=0)
                        .values_list('user_id', 'pago_em')):
        pagos[uid].append(quando)
    convertidos = 0
    for uid, fim in fins.items():
        inicio = inicios.get(uid) or (fim - timedelta(days=31))
        if any(q and q >= inicio for q in pagos.get(uid, ())):
            convertidos += 1
    return pct(convertidos, len(fins)), len(fins)
