"""
Conversa de 3 minutos no fim de uma aula em vídeo ("Usar isto numa conversa").

Como a conversa curta das lições (conversa/licao.py), usa o serviço normal da conversa: a mesma
quota diária de minutos, o mesmo Vapi (ou o modo simulado) e a mesma avaliação. O que muda:
- a "situação" vem da aula: título e resumo do professor (como DADOS, situacoes.bloco_cena) e as
  frases aprovadas da aula (FraseAula) como frases-alvo;
- os objectivos são as frases aprovadas que o aluno ainda não diz sozinho (até 4);
- dura no máximo CONVERSA_AULA_MAX_SEGUNDOS (180 s por omissão);
- curso_id = o curso da aula, para a conversa contar para a nota do curso (fase 1).

A sessão guarda situation = "aula-<hex da aula>" (cabe nos 40 caracteres) e config.capitulo_id.
"""
import uuid

from .situacoes import GUIAO_GENERICO, PALAVRA_FRASE, _limpar_prompt, bloco_cena

PREFIXO = 'aula-'
MAX_OBJECTIVOS = 4


def slug_da_aula(chapter):
    return PREFIXO + uuid.UUID(str(chapter.pk)).hex


def aula_do_slug(slug):
    from apps.courses.models import Chapter
    if not isinstance(slug, str) or not slug.startswith(PREFIXO):
        return None
    try:
        pk = uuid.UUID(slug[len(PREFIXO):])
    except ValueError:
        return None
    return Chapter.objects.select_related('section__course').filter(pk=pk).first()


def frases_da_aula(chapter):
    """As frases aprovadas da aula (só as frases; as palavras ficam de fora): [{en, pt}]."""
    from apps.courses.frases_aula import aprovadas
    return [{'en': f.texto, 'pt': f.traducao} for f in aprovadas(chapter) if f.tipo == 'frase']


def situacao_da_aula(chapter):
    """O dicionário de situação (formato de situacoes.situacao_dict) de uma aula em vídeo."""
    frases = frases_da_aula(chapter)
    curso = chapter.section.course
    titulo = _limpar_prompt(f'Conversa: {chapter.title}', 80)
    descricao = f'{chapter.title}. {chapter.content or ""}'.strip()
    brief = ("Short role-play after a video lesson (about three minutes). The student has just watched a video "
             "lesson; its title and the teacher's summary are below (the summary may be in Portuguese; always "
             "speak English).\n"
             + bloco_cena('a work colleague in a situation like the one in the lesson', descricao,
                          [f['en'] for f in frases]) + '\n'
             'Set up a realistic workplace situation based on the lesson, start the conversation right away and '
             'keep each turn short. Give the student natural chances to use the target phrases, but never say a '
             'target phrase yourself before the student has tried it.')
    return {
        'id': slug_da_aula(chapter),
        'pk': None,
        'titulo': titulo,
        'descricao': ' '.join(str(chapter.content or '').split())[:600],
        'minutos_sugeridos': 3,
        'brief': brief,
        'primeira_fala': "Hi {nome}! Let's use what you saw in the video. Imagine we're at work. How would you start?",
        'primeira_fala_simples': "Hi {nome}! Let's practise the video. How would you start?",
        'frases': frases,
        'palavras': sorted({p.lower() for f in frases for p in PALAVRA_FRASE.findall(f['en'])}),
        'guiao': GUIAO_GENERICO,
        'nivel': None,
        'area': None,
        'correcao': None,
        'curso_id': curso.pk,
        'criado_por_id': curso.teacher_id,
    }


def situacao_por_slug(slug):
    ch = aula_do_slug(slug)
    return situacao_da_aula(ch) if ch is not None else None


def objectivos(user, chapter, frases=None):
    """Até MAX_OBJECTIVOS frases da aula, primeiro as que o aluno ainda não diz sozinho."""
    from apps.perfil.models import ItemBanco
    from apps.perfil.servico import normalizar
    frases = frases if frases is not None else frases_da_aula(chapter)
    estados = dict(ItemBanco.objects.filter(user=user, chave__in=[normalizar(f['en']) for f in frases])
                   .values_list('chave', 'estado'))
    ordenadas = sorted(frases, key=lambda f: 1 if estados.get(normalizar(f['en'])) == ItemBanco.SOZINHO else 0)
    return ordenadas[:MAX_OBJECTIVOS]
