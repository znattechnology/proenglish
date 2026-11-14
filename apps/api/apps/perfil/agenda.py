"""
Agenda da revisão espaçada (itens do banco de frases).

Algoritmo: uma versão simplificada do FSRS (Free Spaced Repetition Scheduler).
Cada item guarda:
- estabilidade S (dias): o tempo até a probabilidade de se lembrar cair para 90%;
- dificuldade D (1 a 10).

Probabilidade de se lembrar t dias depois da última revisão (curva do FSRS):
    R(t) = 1 / (1 + t / (9 * S))          -> R(S) = 0.9
Por isso o intervalo até à próxima revisão é S dias (retenção-alvo de 90%), arredondado,
com um mínimo de 1 dia e um máximo de INTERVALO_MAX.

Notas (por revisão): errei < dificil < certo < facil.
- Primeira revisão: S = S_INICIAL[nota], D = D_INICIAL[nota].
- Acerto (dificil/certo/facil):
      S' = S * (1 + CRESCIMENTO * (11 - D)/10 * S^-0.15 * (e^(1.2 * (1 - R)) - 0.4) * BONUS[nota])
  Cresce mais quando o item é fácil (D baixo), quando S ainda é pequeno e quando foi revisto
  já meio esquecido (R baixo).
      D' = D + PASSO_D[nota], puxado 10% para 5 (não fica preso nos extremos).
- Erro: S' = max(S_MIN, S * 0.3), D' = D + 1.5, lapsos + 1, volta amanhã.

Os dias são os de Angola (Africa/Luanda): uma revisão "para dia X" fica marcada para a
meia-noite de X em Luanda, e "para hoje" é tudo o que está marcado antes da meia-noite de amanhã.
"""
import math
from datetime import timedelta

from django.utils import timezone

from apps.practice.limite_licoes import hoje_luanda, inicio_do_dia

ERREI, DIFICIL, CERTO, FACIL = 'errei', 'dificil', 'certo', 'facil'
NOTAS = (ERREI, DIFICIL, CERTO, FACIL)

S_INICIAL = {ERREI: 0.4, DIFICIL: 1.2, CERTO: 3.0, FACIL: 8.0}
D_INICIAL = {ERREI: 7.0, DIFICIL: 6.0, CERTO: 5.0, FACIL: 3.5}
PASSO_D = {DIFICIL: 0.6, CERTO: 0.0, FACIL: -0.6}
BONUS = {DIFICIL: 0.6, CERTO: 1.0, FACIL: 1.6}
CRESCIMENTO = 2.2
FACTOR_ERRO = 0.3
S_MIN = 0.3
D_MEDIA = 5.0
REVERSAO_D = 0.1
INTERVALO_MAX = 365


def _limitar(v, lo, hi):
    return max(lo, min(hi, v))


def retencao(dias, estabilidade):
    """Probabilidade (0..1) de se lembrar `dias` depois da última revisão."""
    if not estabilidade or estabilidade <= 0:
        return 0.0
    return 1.0 / (1.0 + max(0.0, dias) / (9.0 * estabilidade))


def proximo_estado(estabilidade, dificuldade, nota, dias_desde_ultima=None):
    """
    Função pura: (S, D) depois de uma revisão com `nota`. estabilidade None = primeira revisão.
    Devolve (S', D', intervalo_em_dias).
    """
    if nota not in NOTAS:
        raise ValueError(f'nota desconhecida: {nota}')
    if estabilidade is None or dificuldade is None:
        s, d = S_INICIAL[nota], D_INICIAL[nota]
    elif nota == ERREI:
        s = max(S_MIN, estabilidade * FACTOR_ERRO)
        d = dificuldade + 1.5
    else:
        dias = estabilidade if dias_desde_ultima is None else dias_desde_ultima
        r = retencao(dias, estabilidade)
        crescimento = (CRESCIMENTO * (11 - dificuldade) / 10 * estabilidade ** -0.15
                       * (math.exp(1.2 * (1 - r)) - 0.4) * BONUS[nota])
        s = estabilidade * (1 + max(0.05, crescimento))
        d = dificuldade + PASSO_D[nota]
    d = _limitar(d + REVERSAO_D * (D_MEDIA - d), 1.0, 10.0)
    s = _limitar(s, S_MIN, float(INTERVALO_MAX))
    intervalo = 1 if nota == ERREI else int(_limitar(round(s), 1, INTERVALO_MAX))
    return round(s, 4), round(d, 4), intervalo


def para_o_dia(dias_a_partir_de_hoje, agora=None):
    """Meia-noite (Luanda) do dia daqui a N dias."""
    return inicio_do_dia(hoje_luanda(agora) + timedelta(days=dias_a_partir_de_hoje))


def fim_de_hoje(agora=None):
    return para_o_dia(1, agora)


def esta_para_hoje(item, agora=None):
    return item.proxima_revisao is not None and item.proxima_revisao < fim_de_hoje(agora)


def revisto_hoje(item, agora=None):
    return item.ultima_revisao is not None and hoje_luanda(item.ultima_revisao) == hoje_luanda(agora)


def aplicar(item, nota, agora=None):
    """Aplica uma revisão ao item (sem gravar). Devolve o intervalo em dias."""
    agora = agora or timezone.now()
    dias = None
    if item.ultima_revisao is not None:
        dias = max(0.0, (agora - item.ultima_revisao).total_seconds() / 86400.0)
    s, d, intervalo = proximo_estado(item.estabilidade, item.dificuldade, nota, dias)
    if nota == ERREI and item.repeticoes:
        item.lapsos += 1
    item.estabilidade, item.dificuldade = s, d
    item.repeticoes += 1
    item.ultima_revisao = agora
    item.proxima_revisao = para_o_dia(intervalo, agora)
    return intervalo


def rever_por_conversa(item, agora=None):
    """Disse a frase sozinho numa conversa: conta como uma revisão forte (fácil)."""
    return aplicar(item, FACIL, agora)


CAMPOS = ['estabilidade', 'dificuldade', 'repeticoes', 'lapsos', 'ultima_revisao', 'proxima_revisao',
          'introduzida_em', 'actualizado_em']


def marcar_para_amanha(item, agora=None):
    """Erro numa lição: o item volta amanhã (ou mais cedo, se já estava marcado antes)."""
    amanha = para_o_dia(1, agora)
    if item.proxima_revisao is not None and item.proxima_revisao <= amanha:
        return False  # já volta amanhã (ou hoje): vários erros no mesmo dia contam uma vez
    if item.repeticoes and item.estabilidade:
        item.estabilidade = max(S_MIN, item.estabilidade * FACTOR_ERRO)
        item.lapsos += 1
    item.proxima_revisao = amanha
    return True
