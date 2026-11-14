"""
GET /api/v1/student/practice-courses/lessons/<uuid>/jogar/

A lição tal como o ecrã da lição precisa dela, SEM revelar respostas:
- nenhuma opção traz `is_correct`;
- as opções vêm baralhadas (a ordem guardada é a ordem certa em SENTENCE_ORDER);
- nos exercícios de escrever (FILL_BLANK, TRANSLATION, ditado em LISTENING) não vai o texto
  das respostas, só quantos espaços há para preencher;
- em MATCH_PAIRS as duas colunas vêm baralhadas em separado.

A validação continua no servidor (challenge-progress/ e analyze-ai-pronunciation/).
"""
import random
import re

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.practice import acesso_licoes, limite_licoes
from apps.practice.models import ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson

SEPARADORES_PAR = [" - ", " – ", " = ", " : "]
ESPACO = re.compile(r"_{2,}|\[\s*\]")


def _baralhar(itens, semente):
    """Baralha de forma estável por pessoa e exercício (recarregar a página não troca a ordem)."""
    itens = list(itens)
    random.Random(semente).shuffle(itens)
    return itens


def motivo_saltar(ch):
    """
    Porque é que este exercício é saltado sem ser feito, ou None:
    - "conversa": conversa curta (VAPI_CONVERSATION) sem situação ou sem frases-alvo;
    - "incompleto": responder (RESPONDER) sem pergunta ou sem frase-alvo;
    - "sem_audio": exercício de escuta sem áudio de referência.
    """
    if ch.type == "VAPI_CONVERSATION":
        from apps.practice.conversa.licao import frases_alvo
        return None if (ch.question or "").strip() and frases_alvo(ch) else "conversa"
    if ch.type == "RESPONDER":
        contexto = ch.conversation_context if isinstance(ch.conversation_context, dict) else {}
        return None if (ch.question or "").strip() and str(contexto.get("frase_alvo") or "").strip() else "incompleto"
    if ch.type == "LISTENING" and not (ch.reference_audio_url or "").strip():
        return "sem_audio"
    return None


def _opcao(o):
    return {"id": str(o.id), "texto": o.text, "imagem": o.image_url or None, "audio": o.audio_url or None}


def _exercicio(ch, user_id, feitos):
    opcoes = list(ch.options.all())
    certas = [o for o in opcoes if o.is_correct]
    erradas = [o for o in opcoes if not o.is_correct]
    semente = f"{user_id}:{ch.id}"
    base = {
        "id": str(ch.id),
        "tipo": ch.type,
        "pergunta": ch.question,
        "instrucao": ch.instruction or None,
        "audio": ch.reference_audio_url or None,
        "ordem": ch.order,
        "feito": ch.id in feitos,
    }

    motivo = motivo_saltar(ch)
    if motivo:
        # Exercício que o aluno não pode fazer: o ecrã mostra uma nota e salta-o (sem pontos e
        # sem perder vidas) com challenge-progress/ {saltar: true}. Nada da resposta vai.
        base["modo"] = "indisponivel"
        base["motivo"] = motivo
        base["pergunta"] = ""
        base["audio"] = None
        return base

    if ch.type in ("SELECT", "ASSIST", "TRUE_FALSE"):
        base["opcoes"] = [_opcao(o) for o in _baralhar(opcoes, semente)]
        base["modo"] = "escolha"

    elif ch.type in ("FILL_BLANK", "TRANSLATION", "LISTENING"):
        if erradas:
            # Há alternativas erradas: o exercício é de escolha (banco de palavras / opções).
            base["opcoes"] = [_opcao(o) for o in _baralhar(opcoes, semente)]
            base["modo"] = "escolha" if ch.type != "FILL_BLANK" else "banco"
            base["espacos"] = max(1, len(certas))
        else:
            base["modo"] = "escrever"
            if ch.type == "LISTENING":
                # Ditado: se o enunciado for a própria frase, não o mostrar (seria a resposta).
                normal = lambda x: " ".join((x or "").lower().split())
                if any(normal(o.text) == normal(ch.question) for o in certas):
                    base["pergunta"] = ch.instruction or "Escreva o que ouve."
            espacos = len(ESPACO.findall(ch.question or "")) if ch.type == "FILL_BLANK" else 0
            base["espacos"] = max(espacos, len(certas), 1) if ch.type != "TRANSLATION" else 1

    elif ch.type == "SENTENCE_ORDER":
        base["modo"] = "ordenar"
        base["palavras"] = [{"id": str(o.id), "texto": o.text} for o in _baralhar(opcoes, semente)]

    elif ch.type == "MATCH_PAIRS":
        esquerda, direita = [], []
        for o in opcoes:
            partes = None
            for sep in SEPARADORES_PAR:
                if sep in (o.text or ""):
                    partes = o.text.split(sep, 1)
                    break
            if partes:
                esquerda.append({"id": str(o.id), "texto": partes[0].strip()})
                direita.append(partes[1].strip())
        base["modo"] = "pares"
        base["esquerda"] = _baralhar(esquerda, semente + ":e")
        base["direita"] = _baralhar(direita, semente + ":d")

    elif ch.type == "SPEAKING":
        base["modo"] = "falar"
        # A frase a dizer é a pergunta (ou a 1.ª opção, em exercícios antigos).
        base["frase"] = ch.question if ch.question else (opcoes[0].text if opcoes else "")

    elif ch.type == "RESPONDER":
        # Pergunta de trabalho (ouvida e escrita) e a frase-alvo a usar; o exemplo de resposta só
        # aparece depois da avaliação (challenges/<id>/responder/).
        contexto = ch.conversation_context if isinstance(ch.conversation_context, dict) else {}
        base["modo"] = "responder"
        base["contexto"] = ch.instruction or None
        base["frase"] = str(contexto.get("frase_alvo") or "")

    elif ch.type == "VAPI_CONVERSATION":
        # Conversa curta (opcional) com o tutor: começa em challenges/<id>/conversa/.
        from apps.practice.conversa.licao import frases_alvo
        base["modo"] = "conversa"
        base["frases"] = frases_alvo(ch)

    return base


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def jogar_licao(request, lesson_id):
    licao = get_object_or_404(
        PracticeLesson.objects.select_related("unit", "unit__course").prefetch_related(
            Prefetch("challenges", queryset=PracticeChallenge.objects.order_by("order")),
            Prefetch("challenges__options", queryset=ChallengeOption.objects.order_by("order")),
        ),
        id=lesson_id,
    )
    # Ordem do trilho e plano do curso (antes qualquer lição bloqueada podia ser jogada).
    erro = acesso_licoes.erro_acesso_licao(request.user, licao)
    if erro:
        if erro.get("codigo") in ("curso_indisponivel", acesso_licoes.CODIGO_INDISPONIVEL):
            # rascunho / em revisão / lição ainda incompleta: não existe para o aluno
            from rest_framework.exceptions import NotFound
            raise NotFound("Lição não encontrada.")
        return Response(erro, status=403)
    erro = limite_licoes.erro_limite(request.user, licao)
    if erro:
        return Response(erro, status=403)
    exercicios = list(licao.challenges.all())
    feitos = set(
        ChallengeProgress.objects.filter(user=request.user, challenge__in=exercicios, completed=True).values_list(
            "challenge_id", flat=True
        )
    )
    return Response(
        {
            "id": str(licao.id),
            "titulo": licao.title,
            "unidade": {"id": str(licao.unit.id), "titulo": licao.unit.title},
            "curso": {"id": str(licao.unit.course.id), "titulo": licao.unit.course.title},
            # Repetição: a lição já foi toda feita antes; não custa vidas.
            "repeticao": bool(exercicios) and len(feitos) == len(exercicios),
            "exercicios": [_exercicio(ch, request.user.id, feitos) for ch in exercicios],
        }
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def trilho_curso(request, course_id):
    """
    GET /api/v1/student/practice-courses/courses/<uuid>/trilho/

    O caminho de unidades e lições com o estado de cada lição para esta pessoa:
    "feita" (todos os exercícios concluídos), "actual" (a primeira por fazer) ou "bloqueada".
    Sem exercícios nem opções: só o necessário para desenhar o trilho.
    """
    from apps.courses.models import Course
    from apps.practice.models import PracticeUnit

    curso = get_object_or_404(Course, id=course_id, course_type="practice")
    # Publicado, ou arquivado a manter para quem já fazia o curso (apps/courses/ciclo.py).
    from apps.courses.ciclo import bloqueio_pratica
    bloqueio = bloqueio_pratica(request.user, curso)
    if bloqueio:
        if bloqueio[0] == "curso_indisponivel":
            from rest_framework.exceptions import NotFound
            raise NotFound("Curso de prática não encontrado.")
        return Response({"codigo": bloqueio[0], "mensagem": bloqueio[1]}, status=403)
    # A mesma regra que bloqueia jogar/ e challenge-progress/ (apps.practice.acesso_licoes).
    licoes = acesso_licoes.estados_das_licoes(request.user, curso)
    unidades = {u.id: {"id": str(u.id), "titulo": u.title, "descricao": u.description, "ordem": u.order, "licoes": []}
                for u in PracticeUnit.objects.filter(course=curso).order_by("order")}
    feitas = 0
    for l, estado in licoes:
        if estado == "feita":
            feitas += 1
        unidades[l.unit_id]["licoes"].append(
            {"id": str(l.id), "titulo": l.title, "ordem": l.order, "estado": estado,
             "exercicios": l.total, "exercicios_feitos": min(l.feitos, l.total)}
        )
    total = len(licoes)
    return Response({
        "curso": {"id": str(curso.id), "titulo": curso.title, "categoria": curso.category, "nivel": curso.level},
        "licoes_feitas": feitas,
        "licoes_total": total,
        "percentagem": round(100 * feitas / total) if total else 0,
        # Unidades sem lições visíveis (só com lições ainda incompletas) não aparecem.
        "unidades": [u for u in unidades.values() if u["licoes"]],
    })
