"""
Quanto o aluno fala (fase 3): minutos a falar por dia, meta de fala, palavras difíceis,
resumo do painel e tendências da página de progresso.

Minutos a falar por dia (FalaDiaria), em dias de Luanda:
- conversas (VapiSession.segundos_aluno: só a parte do aluno), separadas em 'conversa', 'exame'
  (exame oral) e 'diagnostico' (teste de nível falado). Dia = dia_da_sessao (ligação/início).
- gravações (TentativaPronuncia.segundos_fala), por origem: 'licao', 'responder', 'revisao', 'aula'.
recalcular_dia() volta a somar tudo a partir das fontes: chamar duas vezes dá o mesmo resultado.
É chamado pelos sinais (apps/perfil/signals.py) quando se grava uma tentativa ou uma sessão com
tempo de fala; nunca parte o pedido que o chamou.

A sequência (dias seguidos) continua a usar a meta de ESTUDO (UserStreak); a meta de FALA
(PerfilFala.meta_fala_min) só se mostra, em destaque.
"""
import logging
import re
import statistics
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import FalaDiaria, ItemBanco, PadraoErro, PalavraDificil, PerfilFala

logger = logging.getLogger(__name__)

DIAS_SEMANA = 7
SEMANAS_PROGRESSO = 8
MAX_PALAVRAS_TREINAR = 12
ACERTOS_PARA_SAIR = 3          # gravações seguidas com a palavra bem dita: sai da lista
FALHAS_PARA_BANCO = 2          # à 2.ª falha a palavra entra no banco (revisão), como 'palavra'
NOTA_PALAVRA_OK = 60           # avaliação detalhada: abaixo disto a palavra falhou
_PALAVRA_OK = re.compile(r"^[a-z][a-z']{1,39}$")


def _hoje(agora=None):
    from apps.practice.limite_licoes import hoje_luanda
    return hoje_luanda(agora)


def _inicio(dia):
    from apps.practice.limite_licoes import inicio_do_dia
    return inicio_do_dia(dia)


# ---------------------------------------------------------------------------
# Minutos a falar por dia
# ---------------------------------------------------------------------------

def _fonte_sessao(situacao):
    s = situacao or ''
    if s.startswith('exame-'):
        return 'exame'
    if s.startswith('diagnostico-'):
        return 'diagnostico'
    return 'conversa'


def segundos_do_dia(user, dia):
    """{fonte: segundos} das fontes desse dia (Luanda)."""
    from apps.practice.models import TentativaPronuncia, VapiSession
    ini, fim = _inicio(dia), _inicio(dia + timedelta(days=1))
    fontes = {}
    for origem, s in (TentativaPronuncia.objects
                      .filter(user=user, criada_em__gte=ini, criada_em__lt=fim, segundos_fala__isnull=False)
                      .values_list('origem').annotate(s=Sum('segundos_fala'))):
        chave = origem or 'licao'
        fontes[chave] = fontes.get(chave, 0.0) + float(s or 0)
    sessoes = (VapiSession.objects.filter(user=user, segundos_aluno__isnull=False,
                                          status__in=VapiSession.STATUS_TERMINADAS)
               .annotate(quando=Coalesce('connected_at', 'started_at', 'created_at'))
               .filter(quando__gte=ini, quando__lt=fim).values_list('situation', 'segundos_aluno'))
    for situacao, s in sessoes:
        chave = _fonte_sessao(situacao)
        fontes[chave] = fontes.get(chave, 0.0) + float(s or 0)
    return {k: round(v, 1) for k, v in fontes.items() if v > 0}


def recalcular_dia(user, dia):
    """Volta a somar o dia a partir das fontes (idempotente). Devolve o FalaDiaria (ou None se vazio)."""
    fontes = segundos_do_dia(user, dia)
    total = round(sum(fontes.values()), 1)
    if not total:
        FalaDiaria.objects.filter(user=user, dia=dia).delete()
        return None
    try:
        with transaction.atomic():
            reg, _ = FalaDiaria.objects.update_or_create(user=user, dia=dia,
                                                         defaults={'segundos': total, 'fontes': fontes})
    except IntegrityError:  # dois pedidos ao mesmo tempo: o outro criou-o
        reg = FalaDiaria.objects.get(user=user, dia=dia)
        reg.segundos, reg.fontes = total, fontes
        reg.save(update_fields=['segundos', 'fontes', 'actualizado_em'])
    return reg


def depois_da_tentativa(tentativa):
    """Uma gravação nova: minutos do dia e palavras difíceis. Nunca levanta excepção."""
    try:
        with transaction.atomic():
            if tentativa.segundos_fala is not None:
                recalcular_dia(tentativa.user, _hoje(tentativa.criada_em))
    except Exception:
        logger.exception('fala: falha ao actualizar os minutos do dia (tentativa %s)', tentativa.pk)
    try:
        with transaction.atomic():
            registar_palavras(tentativa)
    except Exception:
        logger.exception('fala: falha ao registar as palavras difíceis (tentativa %s)', tentativa.pk)


def depois_da_sessao(sessao):
    if sessao.segundos_aluno is None:
        return
    try:
        from apps.practice.conversa.servico import dia_da_sessao
        with transaction.atomic():
            recalcular_dia(sessao.user, dia_da_sessao(sessao))
    except Exception:
        logger.exception('fala: falha ao actualizar os minutos do dia (sessão %s)', sessao.pk)


# ---------------------------------------------------------------------------
# Meta de fala
# ---------------------------------------------------------------------------

def metas_validas():
    return [v for v, _ in PerfilFala.META_FALA_CHOICES]


def meta_de(user):
    v = PerfilFala.objects.filter(user=user).values_list('meta_fala_min', flat=True).first()
    return v or PerfilFala.META_FALA_PADRAO


def definir_meta(user, valor):
    """Devolve a meta guardada; levanta ValueError com a mensagem para o aluno."""
    v = None
    if isinstance(valor, int) and not isinstance(valor, bool):
        v = valor
    elif isinstance(valor, str) and valor.strip().isdigit():
        v = int(valor.strip())
    if v not in metas_validas():
        raise ValueError('Escolha 3, 5, 10 ou 15 minutos por dia.')
    from .servico import obter_perfil
    perfil = obter_perfil(user)
    perfil.meta_fala_min = v
    perfil.save(update_fields=['meta_fala_min', 'actualizado_em'])
    return v


# ---------------------------------------------------------------------------
# Palavras difíceis
# ---------------------------------------------------------------------------

def _palavra(texto):
    p = str(texto or '').strip().lower().translate(str.maketrans({'’': "'", '‘': "'"}))
    p = re.sub(r"^[^a-z']+|[^a-z']+$", '', p)
    return p if _PALAVRA_OK.match(p) else None


def _palavras_do_texto(texto):
    out = []
    for t in re.findall(r"[A-Za-z']+", str(texto or '')):
        p = _palavra(t)
        if p and p not in out:
            out.append(p)
    return out


def _resultados_por_palavra(tentativa):
    """{palavra: (falhou, nota|None, fonema)} desta gravação."""
    out = {}
    detalhe = tentativa.palavras_detalhe if isinstance(tentativa.palavras_detalhe, list) else None
    if detalhe:
        for d in detalhe:
            if not isinstance(d, dict):
                continue
            p = _palavra(d.get('palavra'))
            nota = d.get('nota')
            if not p or not isinstance(nota, (int, float)):
                continue
            erro = d.get('erro_tipo') or 'None'
            falhou = nota < NOTA_PALAVRA_OK or erro in ('Mispronunciation', 'Omission')
            fonema = ''
            fonemas = [f for f in d.get('fonemas') or [] if isinstance(f, dict) and isinstance(f.get('nota'), (int, float))]
            if fonemas:
                fonema = str(min(fonemas, key=lambda f: f['nota']).get('fonema') or '')[:20]
            out[p] = (falhou, float(nota), fonema)
        return out
    # Avaliação pelo texto: as palavras a melhorar falharam; as outras do texto esperado saíram bem.
    problemas = {_palavra(w) for w in tentativa.palavras_problematicas or [] if isinstance(w, str)} - {None}
    for p in problemas:
        out[p] = (True, None, '')
    if tentativa.origem != 'responder':  # no Responder o texto esperado é só a frase-alvo
        for p in _palavras_do_texto(tentativa.texto_esperado):
            out.setdefault(p, (False, None, ''))
    return out


def registar_palavras(tentativa):
    """Actualiza PalavraDificil com uma gravação. Só cria linhas para palavras que falharam;
    as que saíram bem só contam se já lá estiverem. À FALHAS_PARA_BANCO.ª falha a palavra entra
    no banco do aluno (tipo 'palavra', origem 'pronuncia') e vai à revisão."""
    resultados = _resultados_por_palavra(tentativa)
    if not resultados:
        return []
    user, quando = tentativa.user, tentativa.criada_em or timezone.now()
    existentes = {p.palavra: p for p in PalavraDificil.objects.select_for_update()
                  .filter(user=user, palavra__in=list(resultados))}
    novas_no_banco = []
    for palavra, (falhou, nota, fonema) in resultados.items():
        reg = existentes.get(palavra)
        if reg is None:
            if not falhou:
                continue
            try:
                with transaction.atomic():
                    reg = PalavraDificil.objects.create(user=user, palavra=palavra)
            except IntegrityError:
                reg = PalavraDificil.objects.select_for_update().get(user=user, palavra=palavra)
        reg.tentativas += 1
        if falhou:
            reg.falhas += 1
            reg.acertos_seguidos = 0
            if fonema:
                reg.fonema = fonema
        else:
            reg.acertos_seguidos += 1
        if nota is not None:
            n = reg.avaliacoes_detalhadas
            reg.media = round(((reg.media or 0) * n + nota) / (n + 1), 1)
            reg.avaliacoes_detalhadas = n + 1
        reg.ultima = quando
        reg.save()
        if falhou and reg.falhas == FALHAS_PARA_BANCO:
            novas_no_banco.append(palavra)
    if novas_no_banco:
        from .servico import registar_item
        for palavra in novas_no_banco:
            registar_item(user, palavra, origem='pronuncia')
    return novas_no_banco


def palavras_a_treinar(user, limite=MAX_PALAVRAS_TREINAR):
    regs = (PalavraDificil.objects.filter(user=user, falhas__gt=0, acertos_seguidos__lt=ACERTOS_PARA_SAIR)
            .order_by('-falhas', '-ultima')[:limite])
    return [{'palavra': r.palavra, 'tentativas': r.tentativas, 'falhas': r.falhas,
             'media': r.media, 'fonema': r.fonema or None,
             'ultima': r.ultima.isoformat() if r.ultima else None} for r in regs]


# ---------------------------------------------------------------------------
# Leitura: painel e progresso
# ---------------------------------------------------------------------------

def _por_dia(user, inicio, fim):
    return {r.dia: r for r in FalaDiaria.objects.filter(user=user, dia__gte=inicio, dia__lte=fim)}


def duracao_texto(segundos):
    """'menos de 1 minuto' | '1 minuto' | '38 minutos' | '1 h 05 min'."""
    s = max(0, int(round(segundos or 0)))
    if s < 60:
        return 'menos de 1 minuto'
    m = int(round(s / 60.0))
    if m < 60:
        return '1 minuto' if m == 1 else f'{m} minutos'
    return f'{m // 60} h {m % 60:02d} min'


def frase_resumo(segundos_semana, frases_sozinho, padrao=None, meta_min=PerfilFala.META_FALA_PADRAO):
    """A frase do topo do painel, só com dados reais (sem IA). Ver os testes para os casos."""
    if not segundos_semana or segundos_semana < 1:
        return f'Ainda não falou esta semana. Comece por {meta_min} minutos com o tutor.'
    partes = [f'Nos últimos 7 dias falou {duracao_texto(segundos_semana)}']
    if frases_sozinho:
        partes.append(f' e disse sozinho {frases_sozinho} {"frase" if frases_sozinho == 1 else "frases"} numa conversa')
    texto = ''.join(partes) + '.'
    if padrao:
        d = ' '.join(str(padrao).split()).rstrip('.')
        if d:
            texto += f' Erro que ainda repete: {d}.'
    return texto


def resumo_painel(user, agora=None):
    """GET /student/fala/resumo/: frase, hoje vs meta e os últimos 7 dias."""
    hoje = _hoje(agora)
    inicio = hoje - timedelta(days=DIAS_SEMANA - 1)
    regs = _por_dia(user, inicio, hoje)
    dias = [{'dia': (inicio + timedelta(days=i)).isoformat(),
             'segundos': round(regs[inicio + timedelta(days=i)].segundos) if (inicio + timedelta(days=i)) in regs else 0,
             'hoje': i == DIAS_SEMANA - 1} for i in range(DIAS_SEMANA)]
    total = sum(d['segundos'] for d in dias)
    meta = meta_de(user)
    hoje_s = dias[-1]['segundos']
    sozinho = ItemBanco.objects.filter(user=user, estado=ItemBanco.SOZINHO,
                                       ultima_vez_sozinho__gte=_inicio(inicio)).count()
    padrao = (PadraoErro.objects.filter(user=user, superado=False)
              .order_by('-ocorrencias', '-ultima_ocorrencia').values_list('descricao', flat=True).first())
    return {
        'frase': frase_resumo(total, sozinho, padrao, meta),
        'hoje': {'segundos': hoje_s, 'meta_min': meta, 'cumprida': hoje_s >= meta * 60,
                 'percentagem': min(100, round(100 * hoje_s / (meta * 60))) if meta else 0},
        'semana': {'segundos': total, 'dias': dias, 'frases_sozinho': sozinho},
        'padrao': padrao or None,
        'metas_validas': metas_validas(),
    }


def _mediana(valores):
    v = [x for x in valores if isinstance(x, (int, float))]
    return round(statistics.median(v), 1) if v else None


def _media(valores):
    v = [x for x in valores if isinstance(x, (int, float))]
    return round(sum(v) / len(v), 1) if v else None


def progresso(user, agora=None, semanas=SEMANAS_PROGRESSO):
    """
    GET /student/fala/progresso/: as últimas `semanas` semanas (segunda a domingo, Luanda):
    minutos a falar, mediana das palavras por minuto (só medidas), palavras por resposta
    (Responder e média por turno nas conversas), pausas longas por minuto de fala (só medidas).
    """
    from apps.practice.models import TentativaPronuncia, VapiSession
    hoje = _hoje(agora)
    seg = hoje - timedelta(days=hoje.weekday())
    inicios = [seg - timedelta(weeks=semanas - 1 - i) for i in range(semanas)]
    regs = _por_dia(user, inicios[0], hoje)
    ini_dt = _inicio(inicios[0])
    tentativas = list(TentativaPronuncia.objects.filter(user=user, criada_em__gte=ini_dt)
                      .values('criada_em', 'origem', 'ppm', 'palavras_ditas', 'segundos_fala',
                              'pausas_longas', 'fonte_tempo'))
    sessoes = list(VapiSession.objects.filter(user=user, segundos_aluno__isnull=False,
                                              status__in=VapiSession.STATUS_TERMINADAS)
                   .annotate(quando=Coalesce('connected_at', 'started_at', 'created_at'))
                   .filter(quando__gte=ini_dt).values('quando', 'ppm_aluno', 'palavras_por_turno', 'fonte_tempo'))

    def semana_de(dt):
        d = _hoje(dt)
        return d - timedelta(days=d.weekday())

    linhas = []
    for ini in inicios:
        fim = ini + timedelta(days=6)
        segundos = sum(r.segundos for d, r in regs.items() if ini <= d <= fim)
        ts = [t for t in tentativas if semana_de(t['criada_em']) == ini]
        ss = [s for s in sessoes if semana_de(s['quando']) == ini]
        ppms = [t['ppm'] for t in ts if t['fonte_tempo'] == 'medido'] + \
               [s['ppm_aluno'] for s in ss if s['fonte_tempo'] == 'medido']
        respostas = [t['palavras_ditas'] for t in ts if t['origem'] == 'responder'] + \
                    [s['palavras_por_turno'] for s in ss]
        medidas = [t for t in ts if t['fonte_tempo'] == 'medido' and t['segundos_fala']]
        minutos_medidos = sum(t['segundos_fala'] for t in medidas) / 60.0
        pausas = (round(sum(t['pausas_longas'] or 0 for t in medidas) / minutos_medidos, 1)
                  if minutos_medidos >= 0.5 else None)
        linhas.append({'inicio': ini.isoformat(), 'segundos': round(segundos), 'ppm': _mediana(ppms),
                       'palavras_por_resposta': _media(respostas), 'pausas_por_minuto': pausas,
                       'actual': ini == seg})
    return {
        'semanas': linhas,
        'palavras_treinar': palavras_a_treinar(user),
        'meta_min': meta_de(user),
        'avaliacao_detalhada': _estado_detalhada(user),
    }


def _estado_detalhada(user):
    try:
        from apps.practice.services.pronuncia import estado_detalhada
        return estado_detalhada(user)
    except Exception:
        logger.exception('fala: falha ao ler o estado da avaliação detalhada')
        return {'disponivel': False, 'restantes': 0, 'limite': 0}


def resumo_professor(user, agora=None, semanas=SEMANAS_PROGRESSO):
    """Para a ficha do aluno (professor): minutos por semana, ppm e palavras a treinar."""
    p = progresso(user, agora, semanas)
    return {'semanas': [{k: s[k] for k in ('inicio', 'segundos', 'ppm', 'actual')} for s in p['semanas']],
            'palavras_treinar': p['palavras_treinar'][:8], 'meta_min': p['meta_min']}
