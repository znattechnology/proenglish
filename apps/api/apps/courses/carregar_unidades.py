"""
Carrega num curso as unidades escritas em docs/conteudo/<nível>/unidade-NN (ou revisao-N).

Cada pasta tem quatro ficheiros que se carregam:

  guioes.md          as aulas da unidade ("## 1A — título", com "Objectivo da aula" e "Duração");
  questionario.json  o questionário da unidade, no formato quiz_data;
  laboratorio.json   as lições de laboratório (formato de apps/courses/api/teacher/pratica_formato.py),
                     cada uma com o código da aula a que pertence;
  tutor.json         as conversas com o tutor (ver o comando carregar_conversas_curso).

O que fica no curso em vídeo: uma secção por pasta, uma aula por guião (sem vídeo: o vídeo é
enviado depois, na área do professor) e, no fim da secção, uma aula de questionário.
O que fica no curso de laboratório: uma unidade por pasta e uma lição por código; cada aula fica
ligada à sua lição (Chapter.practice_lesson) e a lição de reciclagem (sem aula) fica ligada à aula
de questionário, para aparecer no percurso.

Pode correr várias vezes: procura o que já existe pelo código da aula ("1A") e actualiza. O que os
alunos já fizeram não se estraga: uma lição com respostas de alunos, ou um questionário com
tentativas, não é substituído (o comando avisa), a não ser com forcar=True.
"""
import json
import os
import re

from django.db.models import Max

from apps.courses.api.teacher import pratica_formato as formato
from apps.courses.models import Chapter, ChapterQuiz, CourseSection, StudentQuizAttempt
from apps.courses.questionarios import perguntas_validas, sincronizar_questionario
from apps.practice.models import ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit

AULA = re.compile(r'^## (\S+) — (.+?)\s*$', re.MULTILINE)
OBJECTIVO = re.compile(r'^Objectivo da aula:\s*(.+?)(?=^\S[^\n:]*:|\Z)', re.MULTILINE | re.DOTALL)
DURACAO = re.compile(r'^Duração:\s*(\d+)\s*min', re.MULTILINE)
MAX_EXERCICIOS = 30


class ErroDeConteudo(Exception):
    """Um ficheiro da pasta não está no formato esperado."""


def comeca_pelo_codigo(titulo, codigo):
    return bool(re.match(r'^' + re.escape(str(codigo).strip()) + r'(\s|—|–|-|:|\.|$)', (titulo or '').strip(), re.IGNORECASE))


def _json(pasta, nome):
    caminho = os.path.join(pasta, nome)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def titulo_da_seccao(primeira_linha):
    """'# C1.1 · Unidade 1 — Making the case · Guiões das vídeo-aulas' -> 'Unidade 1 — Making the case'."""
    partes = [p.strip() for p in primeira_linha.lstrip('#').split('·')]
    if len(partes) < 2:
        raise ErroDeConteudo(f'Título dos guiões inesperado: {primeira_linha!r}')
    return re.sub(r'\s*\(\d+ aulas\)\s*$', '', partes[1])


def ler_pasta(pasta):
    """
    Lê e valida os ficheiros de uma pasta. Devolve
    {titulo, aulas: [{codigo, titulo, objectivo, minutos}], questionario, licoes: [{codigo, titulo, aula, exercicios}], tutor}
    com os exercícios já normalizados. Levanta ErroDeConteudo com o primeiro problema.
    """
    caminho = os.path.join(pasta, 'guioes.md')
    if not os.path.exists(caminho):
        raise ErroDeConteudo(f'{pasta}: falta guioes.md')
    with open(caminho, encoding='utf-8') as f:
        texto = f.read()
    titulo = titulo_da_seccao(texto.split('\n', 1)[0])
    marcas = list(AULA.finditer(texto))
    if not marcas:
        raise ErroDeConteudo(f'{pasta}: os guiões não têm aulas ("## 1A — título").')
    aulas = []
    for i, m in enumerate(marcas):
        bloco = texto[m.end():marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)]
        objectivo = OBJECTIVO.search(bloco)
        duracao = DURACAO.search(bloco)
        aulas.append({
            'codigo': m.group(1), 'titulo': m.group(2),
            'objectivo': ' '.join(objectivo.group(1).split()) if objectivo else '',
            'minutos': int(duracao.group(1)) if duracao else None,
        })
    codigos = [a['codigo'] for a in aulas]
    if len(set(codigos)) != len(codigos):
        raise ErroDeConteudo(f'{pasta}: há códigos de aula repetidos nos guiões.')

    questionario = _json(pasta, 'questionario.json')
    if questionario is not None and not perguntas_validas(questionario):
        raise ErroDeConteudo(f'{pasta}: questionario.json não tem perguntas válidas.')

    licoes = []
    for licao in (_json(pasta, 'laboratorio.json') or {}).get('licoes') or []:
        codigo = licao.get('codigo')
        if licao.get('aula') and licao['aula'] not in codigos:
            raise ErroDeConteudo(f'{pasta}: a lição {codigo} aponta para a aula {licao["aula"]}, que não existe.')
        exercicios = licao.get('exercicios') or []
        if not exercicios or len(exercicios) > MAX_EXERCICIOS:
            raise ErroDeConteudo(f'{pasta}: a lição {codigo} tem {len(exercicios)} exercícios (1 a {MAX_EXERCICIOS}).')
        limpos = []
        for n, exercicio in enumerate(exercicios, start=1):
            limpo, erros = formato.validar(exercicio)
            if erros:
                raise ErroDeConteudo(f'{pasta}: lição {codigo}, exercício {n}: {next(iter(erros.values()))[0]}')
            limpos.append(limpo)
        licoes.append({'codigo': codigo, 'titulo': licao.get('titulo') or '', 'aula': licao.get('aula'), 'exercicios': limpos})
    if len({l['codigo'] for l in licoes}) != len(licoes):
        raise ErroDeConteudo(f'{pasta}: há códigos de lição repetidos no laboratório.')

    tutor = os.path.join(pasta, 'tutor.json')
    return {'titulo': titulo, 'aulas': aulas, 'questionario': questionario, 'licoes': licoes,
            'tutor': tutor if os.path.exists(tutor) else None}


def _seguinte(queryset):
    return (queryset.aggregate(m=Max('order'))['m'] or 0) + 1


def _um(candidatos, descricao):
    if len(candidatos) > 1:
        raise ErroDeConteudo(f'Há mais de um resultado para {descricao}; corrija os títulos antes de carregar.')
    return candidatos[0] if candidatos else None


def carregar_video(curso, dados, forcar=False):
    """Secção, aulas e questionário no curso em vídeo. Devolve ({código: aula}, aula do questionário, avisos)."""
    avisos = []
    seccao = CourseSection.objects.filter(course=curso, sectionTitle=dados['titulo']).first()
    if seccao is None:
        seccao = CourseSection.objects.create(course=curso, sectionTitle=dados['titulo'],
                                              order=_seguinte(CourseSection.objects.filter(course=curso)))
    do_curso = list(Chapter.objects.filter(section__course=curso))
    por_codigo = {}
    for ordem, a in enumerate(dados['aulas'], start=1):
        titulo = f"{a['codigo']} — {a['titulo']}"
        aula = _um([c for c in do_curso if c.type != 'Quiz' and comeca_pelo_codigo(c.title, a['codigo'])],
                   f'a aula {a["codigo"]}')
        if aula is None:
            aula = Chapter(section=seccao, type='Video')
        elif aula.section_id != seccao.id:
            raise ErroDeConteudo(f'A aula {a["codigo"]} já existe noutra secção do curso ({aula.section.sectionTitle}).')
        aula.title, aula.content, aula.order = titulo, a['objectivo'], ordem
        # Sem vídeo ainda: a duração do guião serve de estimativa (o envio do vídeo põe a verdadeira).
        if not aula.video and a['minutos']:
            aula.duracao_s = a['minutos'] * 60
        aula.save()
        por_codigo[a['codigo']] = aula

    aula_quiz = None
    q = dados['questionario']
    if q is not None:
        aula_quiz = Chapter.objects.filter(section=seccao, type='Quiz').first()
        com_tentativas = aula_quiz is not None and StudentQuizAttempt.objects.filter(chapter_quiz__chapter=aula_quiz).exists()
        if aula_quiz is None:
            aula_quiz = Chapter(section=seccao, type='Quiz')
        if com_tentativas and aula_quiz.quiz_data != q and not forcar:
            avisos.append(f'{dados["titulo"]}: o questionário já tem tentativas de alunos e ficou como estava.')
        else:
            aula_quiz.title = q.get('title') or 'Questionário'
            aula_quiz.content = q.get('description') or ''
            aula_quiz.quiz_data, aula_quiz.quiz_enabled = q, True
        aula_quiz.order = len(dados['aulas']) + 1
        aula_quiz.save()
        sincronizar_questionario(aula_quiz)
        if not ChapterQuiz.objects.filter(chapter=aula_quiz, is_active=True).exists():
            raise ErroDeConteudo(f'{dados["titulo"]}: o questionário não ficou activo.')
    return por_codigo, aula_quiz, avisos


def carregar_laboratorio(laboratorio, dados, aulas, aula_quiz, forcar=False):
    """Unidade, lições e exercícios no curso de laboratório; liga cada aula à sua lição. Devolve (n.º de exercícios, sem áudio, avisos)."""
    avisos, total, sem_audio = [], 0, 0
    if not dados['licoes']:
        return total, sem_audio, avisos
    unidade = PracticeUnit.objects.filter(course=laboratorio, title=dados['titulo']).first()
    if unidade is None:
        unidade = PracticeUnit.objects.create(course=laboratorio, title=dados['titulo'], description='',
                                              order=_seguinte(PracticeUnit.objects.filter(course=laboratorio)))
    existentes = list(PracticeLesson.objects.filter(unit=unidade))
    for l in dados['licoes']:
        titulo = f"{l['codigo']} — {l['titulo']}" if l['titulo'] else l['codigo']
        licao = _um([e for e in existentes if comeca_pelo_codigo(e.title, l['codigo'])], f'a lição {l["codigo"]}')
        if licao is None:
            licao = PracticeLesson.objects.create(unit=unidade, title=titulo,
                                                  order=_seguinte(PracticeLesson.objects.filter(unit=unidade)))
        elif licao.title != titulo:
            licao.title = titulo
            licao.save(update_fields=['title', 'updated_at'])
        antigos = PracticeChallenge.objects.filter(lesson=licao)
        # Iguais ao que já lá está? Compara-se no formato normalizado (o mesmo dos ficheiros).
        iguais = [formato.validar(formato.para_normalizado(c))[0] for c in antigos.order_by('order')] == l['exercicios']
        if antigos.exists() and not iguais and not forcar and ChallengeProgress.objects.filter(challenge__lesson=licao).exists():
            avisos.append(f'{dados["titulo"]}: a lição {l["codigo"]} já tem respostas de alunos e ficou como estava.')
        elif not iguais:
            antigos.delete()
            for ordem, limpo in enumerate(l['exercicios'], start=1):
                formato.guardar(PracticeChallenge(lesson=licao, order=ordem), limpo)
        total += len(l['exercicios'])
        sem_audio += sum(1 for e in l['exercicios'] if e['tipo'] in ('escuta', 'pronuncia') and not e.get('audio_url'))
        # A lição de reciclagem (sem aula) fica no fim da unidade: liga-se à aula do questionário.
        aula = aulas.get(l['aula']) if l['aula'] else aula_quiz
        if aula is not None and aula.practice_lesson_id != licao.id:
            aula.practice_lesson = licao
            aula.save(update_fields=['practice_lesson'])
    return total, sem_audio, avisos
