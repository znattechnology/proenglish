"""
Regras comuns das gravações dos alunos (exercício de pronúncia, Responder, revisão, repetir frases
da aula): tamanho máximo e as respostas 413/422 que pedem para gravar outra vez.

- Gravação maior do que MAX_BYTES (o ecrã grava no máximo 90 s, menos de 1 MB; 5 MB chega e sobra) -> 413
  'gravacao_grande', antes de a ler para a memória ou de a enviar a um fornecedor.
- Sem fala (transcrição vazia: silêncio, só ruído) -> 422 'sem_fala'. Não chama o Claude, não
  tira vidas e não gasta análises.
- Gravação que o fornecedor recusa (formato, ficheiro estragado, demasiado grande: HTTP 400/413)
  -> 422 'gravacao_invalida'. É um problema da gravação, não do serviço: grava-se outra vez.
Só falhas do serviço (rede, timeout, 5xx, 401/429, chave em falta) são "indisponível" (503).
"""
from rest_framework import status
from rest_framework.response import Response

MAX_BYTES = 5 * 1024 * 1024
MAX_SEGUNDOS = 90

MENSAGEM_SEM_FALA = 'Não ouvimos nada na gravação. Grave outra vez, mais perto do microfone.'
MENSAGEM_INVALIDA = 'Não conseguimos ler esta gravação. Grave outra vez.'
MENSAGEM_GRANDE = f'A gravação é demasiado longa. Grave outra vez (no máximo {MAX_SEGUNDOS} segundos).'


def demasiado_grande(ficheiro):
    tamanho = getattr(ficheiro, 'size', None)
    return tamanho is not None and tamanho > MAX_BYTES


def resposta_grande():
    return Response({'codigo': 'gravacao_grande', 'error': 'audio_too_large', 'mensagem': MENSAGEM_GRANDE,
                     'message': MENSAGEM_GRANDE}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


def resposta_sem_fala():
    return Response({'codigo': 'sem_fala', 'error': 'no_speech', 'mensagem': MENSAGEM_SEM_FALA,
                     'message': MENSAGEM_SEM_FALA}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


def resposta_invalida():
    return Response({'codigo': 'gravacao_invalida', 'error': 'invalid_audio', 'mensagem': MENSAGEM_INVALIDA,
                     'message': MENSAGEM_INVALIDA}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


def resposta_do_resultado(resultado):
    """422 para um resultado sem fala ou com a gravação recusada; None se houve avaliação."""
    if getattr(resultado, 'audio_invalido', False):
        return resposta_invalida()
    if getattr(resultado, 'sem_fala', False):
        return resposta_sem_fala()
    return None
