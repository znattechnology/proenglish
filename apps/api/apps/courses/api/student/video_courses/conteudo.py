"""
O que um estudante pode ver de um curso em vídeo, e correcção dos questionários no servidor.

- O conteúdo dos capítulos (texto, vídeo, recursos, transcrição, questionário) só vai para
  quem está inscrito e tem o plano certo (ou é o professor do curso, ou administrador).
  Os outros vêem só a estrutura: títulos, tipos e ordem.
- As respostas certas e as explicações dos questionários nunca saem para o browser antes
  de o estudante responder: a correcção é feita aqui.
- Depois de uma tentativa, cada pergunta diz só se ficou certa e se foi respondida. As opções
  certas e as explicações só aparecem quando o estudante já passou no questionário ou já não
  tem tentativas (senão bastava uma tentativa em branco para ver tudo e acertar 100% a seguir).
"""

from django.utils import timezone

CAMPOS_DE_CONTEUDO = ('content', 'video', 'quiz_data', 'resources_data', 'transcript',
                      'practice_selection', 'practice_lesson')


def e_staff(user):
    from apps.core.permissions import e_administrador
    return e_administrador(user)


def pode_ver_conteudo(user, course):
    if not user or not user.is_authenticated:
        return False
    if course.teacher_id == user.id or e_staff(user):
        return True
    # Estado do curso: rascunho/em revisão ou arquivado a fechar -> sem conteúdo.
    from apps.courses.ciclo import bloqueio_conteudo
    if bloqueio_conteudo(user, course):
        return False
    from ....models import CourseEnrollment
    inscricao = CourseEnrollment.objects.filter(user=user, course=course, is_active=True).first()
    if not inscricao:
        return False
    if inscricao.expires_at and timezone.now() > inscricao.expires_at:
        return False
    return course.user_has_access(user)


def quiz_sem_respostas(quiz_data):
    """Cópia do quiz_data sem isCorrect, correctOptionId nem explicações."""
    if not isinstance(quiz_data, dict):
        return quiz_data
    perguntas = []
    for q in quiz_data.get('questions') or []:
        if not isinstance(q, dict):
            continue
        limpa = {k: v for k, v in q.items() if k not in ('correctOptionId', 'correctAnswer', 'explanation', 'isCorrect')}
        limpa['options'] = [
            {k: v for k, v in o.items() if k != 'isCorrect'} if isinstance(o, dict) else o
            for o in q.get('options') or []
        ]
        perguntas.append(limpa)
    return {**quiz_data, 'questions': perguntas}


def _certas(pergunta):
    ids = {str(o.get('id')) for o in pergunta.get('options') or [] if isinstance(o, dict) and o.get('isCorrect')}
    if not ids and pergunta.get('correctOptionId') is not None:
        ids = {str(pergunta['correctOptionId'])}
    return ids


def corrigir_quiz(quiz_data, respostas):
    """
    Corrige as respostas ({id_da_pergunta: id_da_opção ou [ids]}).
    Devolve (pontos, pontos_maximos, correccao_por_pergunta).
    """
    respostas = respostas if isinstance(respostas, dict) else {}
    pontos = maximo = 0
    correccao = []
    for q in (quiz_data or {}).get('questions') or []:
        if not isinstance(q, dict):
            continue
        valor = int(q.get('points') or 1)
        maximo += valor
        certas = _certas(q)
        dada = respostas.get(str(q.get('id')))
        escolhidas = {str(x) for x in dada} if isinstance(dada, (list, tuple)) else ({str(dada)} if dada not in (None, '') else set())
        certa = bool(certas) and escolhidas == certas
        if certa:
            pontos += valor
        correccao.append({
            'pergunta': str(q.get('id')),
            'certa': certa,
            'respondida': bool(escolhidas),
            'opcoes_certas': sorted(certas),
            'explicacao': q.get('explanation') or None,
        })
    return pontos, maximo, correccao


def pode_revelar_respostas(chapter_quiz, passou, tentativas_restantes):
    """Opções certas e explicações só depois de passar ou de esgotar as tentativas."""
    if chapter_quiz is not None and not getattr(chapter_quiz, 'show_correct_answers', True):
        return False
    return bool(passou) or tentativas_restantes <= 0


def correccao_para_aluno(correccao, revela):
    """A correcção completa (guardada na tentativa) filtrada segundo `revela`."""
    saida = []
    for item in correccao or []:
        if not isinstance(item, dict):
            continue
        linha = {'pergunta': item.get('pergunta'), 'certa': bool(item.get('certa')),
                 'respondida': bool(item.get('respondida'))}
        if revela:
            linha['opcoes_certas'] = item.get('opcoes_certas') or []
            linha['explicacao'] = item.get('explicacao')
        saida.append(linha)
    return saida


def respondidas(correccao):
    return sum(1 for item in correccao or [] if isinstance(item, dict) and item.get('respondida'))
