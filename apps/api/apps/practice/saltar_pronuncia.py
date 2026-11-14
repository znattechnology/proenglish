"""
Saltar um exercício de pronúncia (SPEAKING) quando a análise está indisponível.

Quando a análise falha (OpenAI sem crédito, Whisper em baixo, ...), analyze-ai-pronunciation/
responde 503 {"codigo": "analise_indisponivel", "pode_saltar": true, "token_saltar": "..."}.
O ecrã pode então enviar:

    POST /api/v1/student/practice-courses/challenge-progress/
    {"challenge_id": "<id>", "saltar": true, "token_saltar": "<token do 503>"}

O exercício fica concluído (`skipped=True`) para a lição poder ser terminada: sem pontos e sem
perder vidas. O token é assinado (pessoa + exercício) e vale 1 hora, para não se poder saltar
exercícios de pronúncia com a análise a funcionar. Sem chave da OpenAI configurada (e sem
análise simulada) também se pode saltar sem token.
"""
from django.conf import settings
from django.core import signing

SAL = 'proenglish.saltar-pronuncia'
VALIDADE_SEGUNDOS = 60 * 60


def gerar_token(user, challenge):
    return signing.dumps({'u': str(user.id), 'c': str(challenge.id)}, salt=SAL)


def token_valido(token, user, challenge):
    if not token:
        return False
    try:
        dados = signing.loads(token, salt=SAL, max_age=VALIDADE_SEGUNDOS)
    except signing.BadSignature:
        return False
    return dados.get('u') == str(user.id) and dados.get('c') == str(challenge.id)


def analise_configurada():
    if getattr(settings, 'PRONUNCIA_SIMULADA', False) and settings.DEBUG:
        return True
    return bool(getattr(settings, 'OPENAI_API_KEY', ''))


def pode_saltar(token, user, challenge):
    return token_valido(token, user, challenge) or not analise_configurada()
