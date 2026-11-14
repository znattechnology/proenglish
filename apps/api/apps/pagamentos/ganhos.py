"""
Ganhos dos professores.

Regra do dono: uma percentagem (``GANHOS_PERCENTAGEM_PROFESSORES``, 30 % por omissão) da
receita de subscrições do mês é dividida pelos professores segundo o tempo que os alunos
com plano pago passaram nos cursos de cada um; paga-se no dia ``GANHOS_DIA_PAGAMENTO``
(5) do mês seguinte. Os meses são meses de calendário em Africa/Luanda.

Receita do mês (o "bolo")
    Soma do que foi efectivamente cobrado (``Pagamento.total_kz``: preço menos desconto do
    código promocional menos crédito abatido) nos pagamentos de subscrição em estado
    ``pago`` cujo ``pago_em`` cai no mês. Critério de caixa: uma anuidade conta toda no mês
    em que foi paga. Ainda não há reembolsos no sistema; quando houver, um pagamento
    reembolsado deixa de estar ``pago`` e sai do bolo ao recalcular (os meses já pagos
    nunca mudam). Bolo = floor(receita × percentagem / 100).

Tempo que conta
    Só alunos com um plano pago (Premium ou Premium Plus) no momento da actividade, isto é,
    com um ``Pagamento`` pago desse plano, com ``total_kz`` maior que 0, cujo período
    [periodo_inicio, periodo_fim) cobre a actividade. Os períodos a 0 Kz (código de 100 % ou
    crédito que cobre tudo) não contam: nesse período o aluno não pagou nada. Alunos no
    Gratuito, ou com o plano dado à mão sem pagamento, não contam. O próprio professor nunca
    conta nos seus cursos.

    * Vídeo: segundos creditados em ``VideoWatchLog`` (já limitados no servidor por aluno,
      capítulo e dia). Conta se o plano pago cobrir alguma parte desse dia. Por aluno e dia,
      somando todos os professores, conta no máximo ``GANHOS_MAX_VIDEO_SEGUNDOS_DIA``
      (4 h); acima disso o limite é repartido pelos professores em proporção ao tempo de cada um.
    * Prática: não existe tempo medido por exercício nem por sessão de lição
      (``DailyStudyLog`` é por aluno e dia, sem curso). Estimativa: cada exercício respondido
      (``ChallengeAttempt``, certo ou errado) vale ``GANHOS_SEGUNDOS_POR_EXERCICIO`` (20 s),
      uma vez por aluno e por dia (hora de Luanda): repetir o mesmo exercício no mesmo dia não
      soma. Conta se o plano pago cobrir o instante da resposta. Por aluno e dia, somando todos
      os professores, conta no máximo ``GANHOS_MAX_PRATICA_SEGUNDOS_DIA`` (60 min); acima disso
      o limite é repartido pelos professores em proporção ao tempo de cada um.

    Só cursos de professores (``teacher.role == 'teacher'``) publicados, ou arquivados com
    ``modo_arquivo == 'manter'`` (estado no momento do cálculo).

Divisão
    quota = segundos do professor / segundos de todos os professores; valor = bolo × quota,
    arredondado ao kwanza pelo método do maior resto (a soma dá exactamente o bolo).
"""

import calendar
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.subscriptions.services import FUSO_ANGOLA

from .models import GanhoMensal, Pagamento

PLANOS_PAGOS = ('PREMIUM', 'PREMIUM_PLUS')

MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
         'Setembro', 'Outubro', 'Novembro', 'Dezembro']

BANCOS = [
    ('bai', 'BAI'),
    ('bfa', 'BFA'),
    ('bic', 'BIC'),
    ('bpc', 'BPC'),
    ('atlantico', 'Millennium Atlântico'),
    ('standard', 'Standard Bank'),
    ('economico', 'Banco Económico'),
    ('sol', 'Banco Sol'),
    ('keve', 'Banco Keve'),
    ('bci', 'BCI'),
    ('finibanco', 'Finibanco'),
    ('outro', 'Outro banco'),
]
NOME_BANCO = dict(BANCOS)


# ---------------------------------------------------------------------------
# Configuração e datas
# ---------------------------------------------------------------------------

def percentagem():
    return int(getattr(settings, 'GANHOS_PERCENTAGEM_PROFESSORES', 30))


def dia_pagamento():
    return int(getattr(settings, 'GANHOS_DIA_PAGAMENTO', 5))


def segundos_por_exercicio():
    return int(getattr(settings, 'GANHOS_SEGUNDOS_POR_EXERCICIO', 20))


def max_pratica_dia():
    return int(getattr(settings, 'GANHOS_MAX_PRATICA_SEGUNDOS_DIA', 3600))


def max_video_dia():
    return int(getattr(settings, 'GANHOS_MAX_VIDEO_SEGUNDOS_DIA', 4 * 3600))


def hoje():
    return timezone.localtime(timezone.now(), FUSO_ANGOLA).date()


def primeiro_dia(d):
    return d.replace(day=1)


def mes_seguinte(mes):
    return (mes.replace(day=28) + timedelta(days=4)).replace(day=1)


def mes_anterior(mes):
    return (mes.replace(day=1) - timedelta(days=1)).replace(day=1)


def nome_mes(mes):
    return f'{MESES[mes.month - 1]} de {mes.year}'


def chave_mes(mes):
    return f'{mes:%Y-%m}'


PRIMEIRO_MES = date(2020, 1, 1)


def ler_mes(texto):
    """
    '2026-10' -> date(2026, 10, 1). Só meses fechados: de Janeiro de 2020 ao mês anterior ao actual
    (hora de Luanda). ValueError (mensagem pt-PT) se inválido ou fora desses limites.
    """
    m = re.fullmatch(r'(\d{4})-(\d{2})', (texto or '').strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError('Mês inválido: use o formato AAAA-MM (por exemplo, 2026-10).')
    mes = date(int(m.group(1)), int(m.group(2)), 1)
    ultimo = mes_anterior(hoje())
    if mes < PRIMEIRO_MES or mes > ultimo:
        raise ValueError(f'Escolha um mês entre {nome_mes(PRIMEIRO_MES)} e {nome_mes(ultimo)}: '
                         'só os meses já terminados têm ganhos fechados.')
    return mes


def data_pagamento(mes):
    """Dia em que se pagam os ganhos de ``mes`` (o dia X do mês seguinte)."""
    seguinte = mes_seguinte(mes)
    ultimo = calendar.monthrange(seguinte.year, seguinte.month)[1]
    return seguinte.replace(day=min(dia_pagamento(), ultimo))


def proximo_pagamento(d=None):
    """(data, mês a que se refere) do próximo dia de pagamento a partir de ``d`` (inclusive)."""
    d = d or hoje()
    mes_ref = mes_anterior(d)
    if data_pagamento(mes_ref) < d:
        mes_ref = primeiro_dia(d)
    return data_pagamento(mes_ref), mes_ref


def _instante(d):
    return datetime.combine(d, time.min, tzinfo=FUSO_ANGOLA)


def limites_mes(mes):
    return _instante(mes), _instante(mes_seguinte(mes))


# ---------------------------------------------------------------------------
# IBAN angolano
# ---------------------------------------------------------------------------

class IbanInvalido(ValueError):
    pass


def normalizar_iban(texto):
    """'AO06 0040 ...' -> 'AO060040...'. Aceita espaços; exige AO06 + 21 dígitos e mod-97."""
    iban = re.sub(r'\s+', '', str(texto or '')).upper()
    if not iban:
        raise IbanInvalido('Indique o IBAN.')
    if not re.fullmatch(r'AO06\d{21}', iban):
        raise IbanInvalido('O IBAN angolano tem 25 caracteres: AO06 seguido de 21 dígitos.')
    rearranjado = iban[4:] + iban[:4]
    numero = ''.join(str(int(c, 36)) for c in rearranjado)
    if int(numero) % 97 != 1:
        raise IbanInvalido('O IBAN não é válido: confirme os dígitos.')
    return iban


def ultimos4(iban):
    return (iban or '')[-4:]


def mascarar_email(email):
    local, _, dominio = (email or '').partition('@')
    if not local:
        return email or ''
    return f'{local[0]}***@{dominio}'


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

@dataclass
class TempoProfessor:
    segundos: int = 0
    alunos: set = field(default_factory=set)


@dataclass
class Calculo:
    mes: date
    receita_kz: int
    bolo_kz: int
    professores: dict  # professor_id -> TempoProfessor
    valores: dict  # professor_id -> int (kz)
    quotas: dict  # professor_id -> Decimal

    @property
    def segundos_total(self):
        return sum(t.segundos for t in self.professores.values())


def receita_mes(inicio, fim):
    pagos = Pagamento.objects.filter(
        estado=Pagamento.PAGO, tipo=Pagamento.TIPO_SUBSCRICAO, pago_em__gte=inicio, pago_em__lt=fim,
    ).only('valor_kz', 'desconto_kz', 'credito_abatido_kz')
    return sum(p.total_kz for p in pagos)


def _periodos_pagos(inicio, fim):
    """aluno_id -> lista de (inicio, fim) dos períodos pagos (total > 0 Kz) que tocam [inicio, fim)."""
    periodos = {}
    qs = (Pagamento.objects
          .filter(estado=Pagamento.PAGO, plan__plan_type__in=PLANOS_PAGOS,
                  periodo_inicio__isnull=False, periodo_fim__isnull=False,
                  periodo_inicio__lt=fim, periodo_fim__gt=inicio)
          .annotate(total=F('valor_kz') - F('desconto_kz') - F('credito_abatido_kz'))
          .filter(total__gt=0)
          .values_list('user_id', 'periodo_inicio', 'periodo_fim'))
    for uid, a, b in qs:
        periodos.setdefault(uid, []).append((a, b))
    return periodos


def _coberto(lista, a, b=None):
    """Algum período de ``lista`` cobre o instante ``a`` (b None) ou intersecta [a, b)?"""
    if b is None:
        return any(ini <= a < fim for ini, fim in lista)
    return any(ini < b and fim > a for ini, fim in lista)


def cursos_que_contam():
    from apps.courses.models import Course
    return (Course.objects
            .filter(teacher__role='teacher')
            .filter(Q(status='Published') | Q(status='Archived', modo_arquivo='manter')))


def _limitar(por_professor, limite):
    """Segundos de um aluno num dia por professor, com o total limitado a ``limite``
    (repartido em proporção, maior resto)."""
    if sum(por_professor.values()) <= limite:
        return dict(por_professor)
    return dividir(limite, por_professor)[0]


def tempo_por_professor(inicio, fim):
    """professor_id -> TempoProfessor no intervalo [inicio, fim) (instantes)."""
    from apps.courses.models import VideoWatchLog
    from apps.practice.models import ChallengeAttempt

    periodos = _periodos_pagos(inicio, fim)
    resultado = {}
    if not periodos:
        return resultado
    cursos = cursos_que_contam()
    alunos = list(periodos)

    # (aluno, dia) -> {professor: segundos}
    video_dia = defaultdict(lambda: defaultdict(int))
    d_ini = timezone.localtime(inicio, FUSO_ANGOLA).date()
    d_fim = timezone.localtime(fim - timedelta(microseconds=1), FUSO_ANGOLA).date()
    video = (VideoWatchLog.objects
             .filter(date__gte=d_ini, date__lte=d_fim, user_id__in=alunos, seconds__gt=0,
                     chapter__section__course__in=cursos)
             .values_list('user_id', 'date', 'seconds', 'chapter__section__course__teacher_id')
             .order_by())
    for uid, dia, seg, prof in video.iterator():
        if uid == prof:
            continue
        a, b = max(_instante(dia), inicio), min(_instante(dia + timedelta(days=1)), fim)
        if _coberto(periodos[uid], a, b):
            video_dia[(uid, dia)][prof] += seg

    pratica_dia = defaultdict(lambda: defaultdict(int))
    por_exercicio = segundos_por_exercicio()
    vistos = set()  # (aluno, exercício, dia): cada exercício conta uma vez por dia
    respostas = (ChallengeAttempt.objects
                 .filter(created_at__gte=inicio, created_at__lt=fim, user_id__in=alunos,
                         challenge__lesson__unit__course__in=cursos)
                 .values_list('user_id', 'challenge_id', 'created_at',
                              'challenge__lesson__unit__course__teacher_id')
                 .order_by())
    for uid, ch, quando, prof in respostas.iterator():
        if uid == prof or not _coberto(periodos[uid], quando):
            continue
        dia = timezone.localtime(quando, FUSO_ANGOLA).date()
        if (uid, ch, dia) in vistos:
            continue
        vistos.add((uid, ch, dia))
        pratica_dia[(uid, dia)][prof] += por_exercicio

    for por_dia, limite in ((video_dia, max_video_dia()), (pratica_dia, max_pratica_dia())):
        for (uid, _dia), por_professor in por_dia.items():
            for prof, seg in _limitar(por_professor, limite).items():
                if seg <= 0:
                    continue
                t = resultado.setdefault(prof, TempoProfessor())
                t.segundos += seg
                t.alunos.add(uid)
    return resultado


def dividir(bolo, segundos):
    """Divide ``bolo`` kz proporcionalmente (maior resto). -> (valores, quotas)."""
    total = sum(segundos.values())
    if not total:
        return {k: 0 for k in segundos}, {k: Decimal(0) for k in segundos}
    valores, restos = {}, []
    for k, s in segundos.items():
        q, r = divmod(bolo * s, total)
        valores[k] = q
        restos.append((r, s, str(k), k))
    sobra = bolo - sum(valores.values())
    for _, _, _, k in sorted(restos, reverse=True)[:sobra]:
        valores[k] += 1
    quotas = {k: (Decimal(s) / Decimal(total)).quantize(Decimal('0.000001'), ROUND_HALF_UP)
              for k, s in segundos.items()}
    return valores, quotas


def calcular(mes, ate=None):
    """Cálculo do mês ``mes`` (até ``ate``, para a estimativa do mês corrente)."""
    inicio, fim = limites_mes(mes)
    if ate is not None:
        fim = min(fim, ate)
    receita = receita_mes(inicio, fim)
    bolo = receita * percentagem() // 100
    tempos = tempo_por_professor(inicio, fim)
    valores, quotas = dividir(bolo, {k: t.segundos for k, t in tempos.items()})
    return Calculo(mes=mes, receita_kz=receita, bolo_kz=bolo, professores=tempos,
                   valores=valores, quotas=quotas)


def estimativa_mes_corrente():
    """Estimativa do mês corrente até agora (cache de 10 min, partilhada por todos)."""
    mes = primeiro_dia(hoje())
    chave = f'ganhos:estimativa:{chave_mes(mes)}'
    dados = cache.get(chave)
    if dados is None:
        c = calcular(mes, ate=timezone.now())
        dados = {str(k): {'valor_kz': c.valores[k], 'alunos': len(t.alunos), 'segundos': t.segundos}
                 for k, t in c.professores.items()}
        cache.set(chave, dados, 600)
    return dados


# ---------------------------------------------------------------------------
# Fecho do mês
# ---------------------------------------------------------------------------

@dataclass
class ResultadoFecho:
    calculo: Calculo
    criados: int = 0
    actualizados: int = 0
    removidos: int = 0
    ja_pagos: int = 0
    notificados: int = 0


def fechar_mes(mes, notificar=True):
    """
    Cria/actualiza os GanhoMensal de ``mes`` (idempotente). Linhas já "pago" nunca mudam;
    linhas "a_processar" de professores que deixaram de ter tempo, ou cujo valor dá 0 Kz (não há
    nada a transferir), são apagadas / não são criadas.
    """
    from apps.users.models import Notification, User

    mes = primeiro_dia(mes)
    calculo = calcular(mes)
    res = ResultadoFecho(calculo=calculo)
    with transaction.atomic():
        existentes = {g.professor_id: g for g in GanhoMensal.objects.select_for_update().filter(mes=mes)}
        for prof_id, tempo in calculo.professores.items():
            if calculo.valores[prof_id] <= 0:
                continue  # 0 Kz: sem linha (fica em "existentes" e é apagada se estiver a processar)
            g = existentes.pop(prof_id, None)
            campos = dict(alunos_pagantes=len(tempo.alunos), segundos=tempo.segundos,
                          quota=calculo.quotas[prof_id], valor_kz=calculo.valores[prof_id])
            if g is None:
                GanhoMensal.objects.create(professor_id=prof_id, mes=mes, **campos)
                res.criados += 1
            elif g.estado == GanhoMensal.PAGO:
                res.ja_pagos += 1
            else:
                for k, v in campos.items():
                    setattr(g, k, v)
                g.save()
                res.actualizados += 1
        for g in existentes.values():
            if g.estado == GanhoMensal.PAGO:
                res.ja_pagos += 1
            else:
                g.delete()
                res.removidos += 1

    if notificar:
        quando = data_pagamento(mes)
        for g in GanhoMensal.objects.filter(mes=mes, estado=GanhoMensal.A_PROCESSAR).select_related('professor'):
            n = Notification.notify(
                g.professor, Notification.KIND_SYSTEM,
                f'Ganhos de {nome_mes(mes)}: {formatar_kz(g.valor_kz)}',
                body=(f'Os seus alunos com plano pago estudaram {g.segundos // 60} minutos nos seus cursos. '
                      f'O pagamento é feito a {quando:%d/%m/%Y}.'),
                link='/teacher/billing', dedupe_key=f'ganhos:{chave_mes(mes)}',
            )
            if n is not None:
                res.notificados += 1
    return res


def formatar_kz(valor):
    return f'{valor:,}'.replace(',', ' ') + ' Kz'


# ---------------------------------------------------------------------------
# Representação (área do professor)
# ---------------------------------------------------------------------------

def _repr_conta(banco, iban, titular):
    return {'banco': banco, 'banco_nome': NOME_BANCO.get(banco, banco),
            'terminada_em': ultimos4(iban), 'titular': titular}


def repr_conta(conta):
    if conta is None:
        return None
    return {**_repr_conta(conta.banco, conta.iban, conta.titular),
            'confirmada_em': conta.confirmada_em.isoformat()}


def alteracao_valida(alt):
    if alt is None:
        return False
    v = alt.verificacao
    return not v.is_used and not v.is_expired() and v.attempts < v.max_attempts


def repr_alteracao(alt):
    if not alteracao_valida(alt):
        return None
    return {**_repr_conta(alt.banco, alt.iban, alt.titular),
            'expira_em': alt.verificacao.expires_at.isoformat()}


def repr_mes(g):
    return {
        'mes': chave_mes(g.mes),
        'nome': nome_mes(g.mes),
        'alunos': g.alunos_pagantes,
        'minutos': round(g.segundos / 60),
        'valor_kz': g.valor_kz,
        'pago_a': data_pagamento(g.mes).isoformat(),
        'pago_em': g.pago_em.isoformat() if g.pago_em else None,
        'estado': g.estado,
    }


def resumo_professor(user):
    from .models import AlteracaoContaRecebimento, ContaRecebimento

    d = hoje()
    estimativa = estimativa_mes_corrente().get(str(user.pk), {})
    data, referente = proximo_pagamento(d)
    ganhos = GanhoMensal.objects.filter(professor=user)
    pagos = ganhos.filter(estado=GanhoMensal.PAGO).order_by('mes')
    primeiro = pagos.first()
    conta = ContaRecebimento.objects.filter(professor=user).first()
    alt = AlteracaoContaRecebimento.objects.filter(professor=user).select_related('verificacao').first()
    return {
        'percentagem': percentagem(),
        'dia_pagamento': dia_pagamento(),
        'regras': {
            'segundos_por_exercicio': segundos_por_exercicio(),
            'max_pratica_min_dia': max_pratica_dia() // 60,
            'max_video_min_dia': max_video_dia() // 60,
        },
        'este_mes': {
            'valor_kz': estimativa.get('valor_kz', 0),
            'ate': d.isoformat(),
            'alunos_pagantes': estimativa.get('alunos', 0),
            'minutos': round(estimativa.get('segundos', 0) / 60),
        },
        'proximo_pagamento': {'data': data.isoformat(), 'referente': nome_mes(referente)},
        'total_recebido': {
            'valor_kz': sum(g.valor_kz for g in pagos),
            'desde': nome_mes(primeiro.mes) if primeiro else None,
        },
        'meses': [repr_mes(g) for g in ganhos.order_by('-mes')[:24]],
        'conta': repr_conta(conta),
        'alteracao_pendente': repr_alteracao(alt),
    }
