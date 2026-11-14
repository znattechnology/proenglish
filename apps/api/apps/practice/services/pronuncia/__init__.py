"""
Avaliação de pronúncia com fornecedores trocáveis (fase 3).

    avaliar(audio_bytes, mime, texto_esperado=None, idioma='en-US', modo='lido', user=None) -> ResultadoPronuncia

Escolha do fornecedor:
1. modo simulado (PRONUNCIA_SIMULADA com DEBUG) -> ProvedorSimulado;
2. avaliação detalhada (Azure Speech) quando PRONUNCIA_PROVEDOR é 'auto' ou 'azure', AZURE_SPEECH_KEY
   e AZURE_SPEECH_REGION (ou AZURE_SPEECH_ENDPOINT) estão definidas, há texto esperado e o aluno ainda
   tem avaliações detalhadas hoje (limite do plano: SubscriptionPlan.daily_detailed_pronunciation_limit,
   contado por dia de Luanda em AvaliacaoDetalhadaDia);
3. senão, ou se a detalhada falhar (rede, formato, resposta) -> avaliação pelo texto, sem aviso.

Outro fornecedor (SpeechAce, ELSA, um modelo nosso): uma classe Provedor nova e uma entrada em
DETALHADOS; os chamadores não mudam.
"""
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F

from .base import ErroProvedor, ResultadoPronuncia, credito_de  # noqa: F401
from .texto import ProvedorSimulado, ProvedorTexto, de_pronunciation_result  # noqa: F401

logger = logging.getLogger(__name__)


def modo_simulado():
    return bool(getattr(settings, 'PRONUNCIA_SIMULADA', False) and settings.DEBUG)


def _detalhado():
    """O fornecedor detalhado ligado (instância), ou None."""
    escolha = (getattr(settings, 'PRONUNCIA_PROVEDOR', 'auto') or 'auto').strip().lower()
    if escolha not in ('auto', 'azure'):
        return None
    from . import azure
    return azure.ProvedorAzure() if azure.configurado() else None


def detalhada_ligada():
    return _detalhado() is not None


# ---------------------------------------------------------------------------
# Limite diário do plano
# ---------------------------------------------------------------------------

def limite_detalhadas(user):
    """Avaliações detalhadas por dia no plano do aluno (sem assinatura activa: o do Gratuito)."""
    from apps.subscriptions.models import SubscriptionPlan, UserSubscription
    sub = UserSubscription.objects.select_related('plan').filter(user=user).first()
    if sub is not None and sub.is_active():
        return int(sub.plan.daily_detailed_pronunciation_limit or 0)
    gratuito = SubscriptionPlan.objects.filter(plan_type='FREE').values_list(
        'daily_detailed_pronunciation_limit', flat=True).first()
    return int(gratuito or 0)


def usadas_hoje(user, dia=None):
    from apps.practice.limite_licoes import hoje_luanda
    from apps.practice.models import AvaliacaoDetalhadaDia
    dia = dia or hoje_luanda()
    return AvaliacaoDetalhadaDia.objects.filter(user=user, dia=dia).values_list('usadas', flat=True).first() or 0


def reservar(user):
    """Gasta uma avaliação detalhada de hoje se ainda houver. True/False."""
    from apps.practice.limite_licoes import hoje_luanda
    from apps.practice.models import AvaliacaoDetalhadaDia
    limite = limite_detalhadas(user)
    if limite <= 0:
        return False
    dia = hoje_luanda()
    with transaction.atomic():
        try:
            with transaction.atomic():
                reg, _ = AvaliacaoDetalhadaDia.objects.get_or_create(user=user, dia=dia)
        except IntegrityError:
            reg = AvaliacaoDetalhadaDia.objects.get(user=user, dia=dia)
        n = AvaliacaoDetalhadaDia.objects.filter(pk=reg.pk, usadas__lt=limite).update(usadas=F('usadas') + 1)
    return n == 1


def devolver(user):
    """A detalhada falhou antes de haver resultado: não conta."""
    from apps.practice.limite_licoes import hoje_luanda
    from apps.practice.models import AvaliacaoDetalhadaDia
    AvaliacaoDetalhadaDia.objects.filter(user=user, dia=hoje_luanda(), usadas__gt=0).update(usadas=F('usadas') - 1)


def estado_detalhada(user):
    ligada = detalhada_ligada()
    limite = limite_detalhadas(user) if ligada else 0
    usadas = usadas_hoje(user) if ligada else 0
    return {'disponivel': ligada and limite > 0, 'limite': limite, 'usadas': usadas,
            'restantes': max(0, limite - usadas)}


# ---------------------------------------------------------------------------
# Avaliar
# ---------------------------------------------------------------------------

def avaliar(audio_bytes, mime='audio/webm', texto_esperado=None, idioma='en-US', modo='lido', user=None,
            nivel='intermediate', nome=None):
    """ResultadoPronuncia (ver o topo). Falhas técnicas da avaliação pelo texto vêm como indisponivel=True."""
    if hasattr(audio_bytes, 'getvalue'):
        nome = nome or getattr(audio_bytes, 'name', None)
        audio_bytes = audio_bytes.getvalue()
    if modo_simulado():
        return ProvedorSimulado().avaliar(audio_bytes, mime, texto_esperado, idioma, modo, nivel)
    detalhado = _detalhado() if (user is not None and modo == 'lido' and (texto_esperado or '').strip()) else None
    if detalhado is not None and reservar(user):
        try:
            return detalhado.avaliar(audio_bytes, mime, texto_esperado, idioma, modo, nivel)
        except ErroProvedor as e:
            logger.warning('pronúncia: avaliação detalhada (%s) indisponível: %s', detalhado.nome, e)
        except Exception as e:  # nunca parte a gravação do aluno
            logger.warning('pronúncia: avaliação detalhada (%s) falhou: %s', detalhado.nome, type(e).__name__)
        try:
            devolver(user)
        except Exception:
            logger.exception('pronúncia: falha a devolver a avaliação detalhada')
    return ProvedorTexto().avaliar(audio_bytes, mime, texto_esperado, idioma.split('-')[0] if idioma else 'en',
                                   modo, nivel, nome=nome)


# ---------------------------------------------------------------------------
# Para gravar e mostrar
# ---------------------------------------------------------------------------

def campos_tentativa(resultado):
    """Campos extra de TentativaPronuncia: métricas de fluência e, se houver, a avaliação detalhada."""
    from apps.practice.services.metricas_fala import metricas_de_transcricao
    tempos = getattr(resultado, 'tempos', None) or getattr(resultado, 'transcricao_fala', None)
    texto = getattr(resultado, 'transcricao', None)
    if texto is None:
        texto = getattr(resultado, 'transcribed_text', '') or ''
    campos = metricas_de_transcricao(tempos, texto)
    detalhada = bool(getattr(resultado, 'detalhada', False))
    campos['avaliacao'] = 'azure' if getattr(resultado, 'fonte', '') == 'azure' else 'texto'
    campos['nota_completude'] = getattr(resultado, 'completude', None) if detalhada else None
    campos['nota_prosodia'] = getattr(resultado, 'prosodia', None) if detalhada else None
    campos['palavras_detalhe'] = list(getattr(resultado, 'palavras', None) or []) if detalhada else None
    return campos


def detalhe_publico(resultado):
    """Para os painéis de resultado: notas por palavra (cor) e a dica do pior som. None sem detalhada."""
    if not getattr(resultado, 'detalhada', False):
        return None
    from .azure import dica_de
    palavras = [{'palavra': p['palavra'], 'nota': p['nota'], 'erro_tipo': p['erro_tipo']}
                for p in resultado.palavras]
    medidas = [p for p in resultado.palavras if p.get('nota') is not None and p.get('erro_tipo') != 'Omission']
    pior = min(medidas, key=lambda p: p['nota'], default=None)
    return {
        'palavras': palavras,
        'fluencia': resultado.fluencia, 'completude': resultado.completude, 'prosodia': resultado.prosodia,
        'dica': dica_de(pior) if pior else None,
        'fonte': resultado.fonte,
    }


def fala_publica(tentativa_ou_campos):
    """As métricas de fluência para o ecrã (sem os tempos de cada palavra), ou None."""
    from apps.practice.services.metricas_fala import CAMPOS, resumo_publico
    if tentativa_ou_campos is None:
        return None
    if isinstance(tentativa_ou_campos, dict):
        return resumo_publico(tentativa_ou_campos)
    return resumo_publico({k: getattr(tentativa_ou_campos, k, None) for k in CAMPOS})
