"""
ChapterQuiz a partir do Chapter.quiz_data (o que o QuizBuilder do professor guarda).

As tentativas, o resumo e as notas usam o ChapterQuiz, mas o modal do professor só guarda o
quiz_data no capítulo: sem isto os questionários criados pelo professor davam 404 ao aluno.

- Capítulo do tipo Quiz com perguntas -> ChapterQuiz criado/actualizado (título, nota para
  passar, tentativas, tempo, pontos).
- Capítulo que deixou de ser Quiz, ou quiz do professor que ficou sem perguntas -> ChapterQuiz
  desactivado (as tentativas antigas ficam). Quizzes antigos ligados a uma lição de prática e
  sem quiz_data ficam como estão.
- Não mexe na lição de prática ligada (os quizzes semeados têm uma; os do professor não).

Chamado pelo signal post_save de Chapter (depois do commit) e pelo comando
`sincronizar_questionarios` (para os capítulos que já existiam).
"""
import logging

logger = logging.getLogger(__name__)


def _inteiro(valor, omissao, minimo=None, maximo=None):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return omissao
    if minimo is not None and n < minimo:
        return omissao
    if maximo is not None and n > maximo:
        n = maximo
    return n


def perguntas_validas(quiz_data):
    if not isinstance(quiz_data, dict):
        return []
    return [q for q in quiz_data.get('questions') or [] if isinstance(q, dict) and q.get('options')]


def sincronizar_questionario(chapter):
    """Cria, actualiza ou desactiva o ChapterQuiz do capítulo. Devolve o ChapterQuiz ou None."""
    from apps.courses.models import ChapterQuiz

    existente = ChapterQuiz.objects.filter(chapter=chapter).first()
    perguntas = perguntas_validas(chapter.quiz_data)
    deixou_de_ser_quiz = chapter.type != 'Quiz' and not chapter.quiz_enabled
    if deixou_de_ser_quiz or not perguntas:
        # Sem perguntas no quiz_data: os quizzes antigos ligados a uma lição de prática (semeados)
        # ficam como estão; os do professor ficam desactivados (não se podem fazer).
        desactivar = deixou_de_ser_quiz or (existente is not None and existente.practice_lesson_id is None)
        if existente and existente.is_active and desactivar:
            existente.is_active = False
            existente.save(update_fields=['is_active'])
        return existente

    dados = chapter.quiz_data or {}
    definicoes = dados.get('settings') if isinstance(dados.get('settings'), dict) else {}
    pontos = sum(_inteiro(q.get('points'), 1, minimo=0) for q in perguntas)
    tempo = _inteiro(definicoes.get('timeLimit'), None, minimo=1)
    valores = {
        'title': (dados.get('title') or chapter.title or 'Questionário')[:200],
        'description': dados.get('description') or '',
        'passing_score': _inteiro(definicoes.get('passingScore'), 70, minimo=0, maximo=100),
        'max_attempts': _inteiro(definicoes.get('maxAttempts'), 3, minimo=1, maximo=20),
        'hearts_cost': _inteiro(definicoes.get('heartsPerError'), 1, minimo=0, maximo=5),
        'time_limit': tempo,
        'points_reward': pontos or 15,
        'is_active': True,
    }

    if existente is None:
        professor = chapter.section.course.teacher
        quiz = ChapterQuiz.objects.create(chapter=chapter, created_by=professor, **valores)
        logger.info('ChapterQuiz criado para o capítulo %s', chapter.pk)
        return quiz

    mudou = [campo for campo, valor in valores.items() if getattr(existente, campo) != valor]
    if mudou:
        for campo in mudou:
            setattr(existente, campo, valores[campo])
        campos = {f.name for f in existente._meta.concrete_fields}
        existente.save(update_fields=mudou + (['updated_at'] if 'updated_at' in campos else []))
    return existente
