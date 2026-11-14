"""
Conversa curta no fim de uma lição de prática (exercício VAPI_CONVERSATION).

Usa o serviço normal da conversa (servico.criar_sessao / terminar): a mesma quota diária de
minutos, o mesmo Vapi (ou o modo simulado) e a mesma avaliação. O que muda:
- a "situação" vem do exercício (texto do professor como DADOS, ver situacoes.bloco_cena);
- os objectivos são as 2-3 frases da lição que o professor escolheu (não as do banco do aluno);
- dura no máximo CONVERSA_LICAO_MAX_SEGUNDOS (120 s por omissão).

A sessão guarda situation = "licao-<hex do exercício>" (cabe nos 40 caracteres do campo) e
config.exercicio_id; o exercício conta como feito quando a conversa terminou com pelo menos
2 falas do aluno (challenge-progress/ {challenge_id, sessao_id}).
"""
import uuid

from .situacoes import GUIAO_GENERICO, PALAVRA_FRASE, _limpar_prompt, bloco_cena

PREFIXO = 'licao-'
MIN_FALAS_ALUNO = 2


def slug_do_exercicio(challenge):
    return PREFIXO + uuid.UUID(str(challenge.pk)).hex


def exercicio_do_slug(slug):
    """O PracticeChallenge de uma situação "licao-<hex>", ou None."""
    from apps.practice.models import PracticeChallenge
    if not isinstance(slug, str) or not slug.startswith(PREFIXO):
        return None
    try:
        pk = uuid.UUID(slug[len(PREFIXO):])
    except ValueError:
        return None
    return (PracticeChallenge.objects.select_related('lesson', 'lesson__unit', 'lesson__unit__course')
            .filter(pk=pk, type='VAPI_CONVERSATION').first())


def frases_alvo(challenge):
    from apps.courses.api.teacher.pratica_formato import frases_da_conversa
    return frases_da_conversa(challenge.conversation_context)


def situacao_do_exercicio(challenge):
    """O dicionário de situação (o mesmo formato de situacoes.situacao_dict) de um exercício de conversa."""
    frases = frases_alvo(challenge)
    licao = challenge.lesson
    curso = licao.unit.course if licao and licao.unit_id else None
    titulo = _limpar_prompt(f'Conversa curta: {licao.title}' if licao else 'Conversa curta', 80)
    brief = ("Short role-play at the end of a practice lesson (about two minutes). The scene was set by the "
             "student's teacher (the description may be in Portuguese; always speak English).\n"
             + bloco_cena('a work colleague in the scene', challenge.question, frases) + '\n'
             'Play your role in the scene, start the conversation right away and keep it to three or four short '
             'exchanges. Give the student natural chances to use the target phrases.')
    return {
        'id': slug_do_exercicio(challenge),
        'pk': None,
        'titulo': titulo,
        'descricao': ' '.join(str(challenge.question or '').split())[:600],
        'minutos_sugeridos': 2,
        'brief': brief,
        'primeira_fala': "Hi {nome}! Let's use what you learned in this lesson. How would you start?",
        'primeira_fala_simples': "Hi {nome}! Let's practise. How would you start?",
        'frases': [{'en': f, 'pt': ''} for f in frases],
        'palavras': sorted({p.lower() for f in frases for p in PALAVRA_FRASE.findall(f)}),
        'guiao': GUIAO_GENERICO,
        'nivel': None,
        'area': None,
        'correcao': None,
        'curso_id': curso.pk if curso else None,
        'criado_por_id': curso.teacher_id if curso else None,
    }


def situacao_por_slug(slug):
    ch = exercicio_do_slug(slug)
    return situacao_do_exercicio(ch) if ch is not None else None


def falas_do_aluno(sessao):
    from .analise import textos_aluno, limpar_transcricao
    dados = sessao.full_session_data if isinstance(sessao.full_session_data, dict) else {}
    transcricao = dados.get('transcricao') or limpar_transcricao(dados.get('historico') or [])
    return len(textos_aluno(transcricao))


def conversa_concluida(user, challenge, sessao_id):
    """
    (ok, motivo): a conversa `sessao_id` é deste aluno e deste exercício, já terminou e teve pelo
    menos MIN_FALAS_ALUNO falas do aluno.
    """
    from apps.practice.models import VapiSession
    if not sessao_id:
        return False, 'sem_sessao'
    sessao = VapiSession.objects.filter(user=user, session_id=str(sessao_id)[:100]).first()
    if sessao is None:
        return False, 'sem_sessao'
    cfg = (sessao.full_session_data or {}).get('config') if isinstance(sessao.full_session_data, dict) else None
    if not isinstance(cfg, dict) or cfg.get('exercicio_id') != str(challenge.pk):
        return False, 'sem_sessao'
    if sessao.status not in VapiSession.STATUS_TERMINADAS:
        return False, 'nao_terminada'
    if falas_do_aluno(sessao) < MIN_FALAS_ALUNO:
        return False, 'poucas_falas'
    return True, ''
