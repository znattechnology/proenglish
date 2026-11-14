"""
Erros nas lições do laboratório -> revisão de amanhã.

Quando um ChallengeAttempt errado é gravado, a resposta certa do exercício (em inglês) entra no
banco do aluno (origem 'licao') e fica marcada para amanhã. Corre depois do commit e nunca parte
a resposta da lição: exercícios sem texto em inglês reconhecível são ignorados.
"""
import logging
import re

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.practice.models import ChallengeAttempt

logger = logging.getLogger(__name__)

ESPACO = re.compile(r'_{2,}|\[\s*\]')
MAX_PALAVRAS = 25


def _opcoes(ch):
    return sorted(ch.options.all(), key=lambda o: o.order)


def _ingles_provavel(texto):
    """Texto com letras sem acentos portugueses (as opções de SELECT podem estar em português)."""
    return bool(texto) and bool(re.search(r'[A-Za-z]', texto)) and not re.search(r'[ãõçáéíóúâêôà]', texto.lower())


def texto_certo(ch):
    """(inglês, português) da resposta certa do exercício, ou (None, None)."""
    tipo = ch.type
    pergunta = ' '.join((ch.question or '').split())
    certas = [o.text.strip() for o in _opcoes(ch) if o.is_correct and (o.text or '').strip()]
    if tipo == 'SPEAKING':
        from apps.practice.views_ai import frase_para_dizer
        return frase_para_dizer(ch) or None, None
    if tipo == 'TRANSLATION':
        return (certas[0], pergunta) if certas else (None, None)
    if tipo == 'SENTENCE_ORDER':
        texto = ' '.join(o.text.strip() for o in _opcoes(ch) if (o.text or '').strip())
        return texto or None, pergunta or None
    if tipo == 'FILL_BLANK':
        partes = ESPACO.split(pergunta)
        if len(partes) < 2 or len(certas) < len(partes) - 1:
            return None, None
        frase = partes[0]
        for i, p in enumerate(partes[1:]):
            frase += certas[i] + p
        return ' '.join(frase.split()), None
    if tipo == 'LISTENING':
        return (certas[0], None) if certas and _ingles_provavel(certas[0]) else (None, None)
    if tipo == 'RESPONDER':
        ctx = ch.conversation_context if isinstance(ch.conversation_context, dict) else {}
        alvo = ' '.join(str(ctx.get('frase_alvo') or ctx.get('exemplo') or '').split())
        return alvo or None, None
    return None, None  # SELECT, TRUE_FALSE, MATCH_PAIRS, ASSIST, conversa: sem frase certa clara


def registar_erro_licao(tentativa_id):
    from apps.perfil import agenda
    from apps.perfil.servico import registar_item

    t = (ChallengeAttempt.objects.select_related('challenge__lesson__unit', 'user')
         .filter(pk=tentativa_id).first())
    if t is None or t.is_correct or t.challenge is None:
        return None
    en, pt = texto_certo(t.challenge)
    if not en or len(en.split()) > MAX_PALAVRAS:
        return None
    licao = t.challenge.lesson
    curso_id = getattr(getattr(licao, 'unit', None), 'course_id', None)
    with transaction.atomic():
        item = registar_item(t.user, en, pt or '', origem='licao', licao_id=getattr(licao, 'pk', None),
                             curso_id=curso_id)
        if item is None:
            return None
        if agenda.marcar_para_amanha(item):
            item.save(update_fields=agenda.CAMPOS)
    return item


@receiver(post_save, sender=ChallengeAttempt, dispatch_uid='perfil_erro_licao_para_revisao')
def erro_na_licao(sender, instance, created, **kwargs):
    if not created or instance.is_correct:
        return
    pk = instance.pk

    def depois():
        try:
            registar_erro_licao(pk)
        except Exception:
            logger.exception('perfil: falha ao pôr o erro da lição na revisão')

    transaction.on_commit(depois)


# ---------------------------------------------------------------------------
# Fase 3: minutos a falar por dia e palavras difíceis (apps/perfil/fala.py)
# ---------------------------------------------------------------------------

def _ligar_sinais_fala():
    from apps.practice.models import TentativaPronuncia, VapiSession

    @receiver(post_save, sender=TentativaPronuncia, dispatch_uid='perfil_fala_tentativa')
    def tentativa_gravada(sender, instance, created, **kwargs):
        if not created:
            return
        pk = instance.pk

        def depois():
            from apps.perfil import fala
            t = TentativaPronuncia.objects.select_related('user').filter(pk=pk).first()
            if t is not None:
                fala.depois_da_tentativa(t)

        transaction.on_commit(depois)

    @receiver(post_save, sender=VapiSession, dispatch_uid='perfil_fala_sessao')
    def sessao_gravada(sender, instance, created, update_fields=None, **kwargs):
        if instance.segundos_aluno is None:
            return
        if update_fields is not None and not ({'segundos_aluno', 'status'} & set(update_fields)):
            return
        pk = instance.pk

        def depois():
            from apps.perfil import fala
            s = VapiSession.objects.select_related('user').filter(pk=pk).first()
            if s is not None:
                fala.depois_da_sessao(s)

        transaction.on_commit(depois)

    return tentativa_gravada, sessao_gravada


_SINAIS_FALA = _ligar_sinais_fala()
