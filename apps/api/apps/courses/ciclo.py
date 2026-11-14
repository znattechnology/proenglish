"""
Ciclo de vida de um curso (vídeo ou prática) e regras de acesso que dependem dele.

Estados (Course.status -> nome na API):
- Draft     -> rascunho    (o professor está a construir)
- InReview  -> em_revisao  (submetido; espera pela aprovação do administrador)
- Published -> publicado   (aprovado; está no catálogo)
- Archived  -> arquivado   (fora do catálogo; sem inscrições novas)

Arquivar tem um modo:
- manter: quem já está inscrito continua a ter acesso, progresso e certificados;
- fechar: os inscritos perdem o acesso às aulas; os certificados emitidos continuam válidos.

Transições:
  rascunho --submeter--> em_revisao --aprovar--> publicado --arquivar--> arquivado
  em_revisao --recusar(motivo)/cancelar-revisao--> estado anterior (rascunho, ou arquivado
                                                    no mesmo modo se veio de arquivado)
  arquivado --submeter--> em_revisao (republicar passa sempre pela revisão; enquanto espera,
                          um curso que estava arquivado a manter continua aberto aos inscritos)
  rascunho --arquivar--> arquivado

Só o administrador publica, com uma excepção: um professor marcado pelo administrador como
"pode publicar sem revisão" (PerfilProfessor.publica_sem_revisao) publica ao submeter, se a lista
de verificação passar.
"""
from django.db.models import Count, Q

from apps.courses import niveis

RASCUNHO = 'Draft'
EM_REVISAO = 'InReview'
PUBLICADO = 'Published'
ARQUIVADO = 'Archived'

ESTADO_API = {
    RASCUNHO: 'rascunho',
    EM_REVISAO: 'em_revisao',
    PUBLICADO: 'publicado',
    ARQUIVADO: 'arquivado',
}
API_ESTADO = {v: k for k, v in ESTADO_API.items()}

MANTER = 'manter'
FECHAR = 'fechar'
MODOS_ARQUIVO = (MANTER, FECHAR)

# Cursos cujo conteúdo um aluno já inscrito pode ainda abrir (o modo "fechar" é filtrado
# por bloqueio_conteudo, porque depende de quem pede).
ESTADOS_CONTEUDO_ALUNO = (PUBLICADO, ARQUIVADO)

# Definições guardadas em Course.definicoes (JSON). As que o servidor tem de consultar com
# filtros (visivel_catalogo, inscricao_livre, maximo_alunos) são colunas próprias.
DEFINICOES_OMISSAO = {
    'pode_repetir': True,
    'mostrar_progresso': True,
    'resumo_semanal': False,
    'tempo_limite_questionario_min': None,
    'certificado_automatico': True,
}

# Rótulos em pt-PT, iguais aos que o estudante vê (apps/web/src/domains/student/inicio/api.ts).
AREAS = {
    # Cursos de vídeo
    'Industry English': 'Petróleo e Gás',
    'Financial English': 'Banca',
    'Technical English': 'Tecnologia',
    'Business English': 'Negócios',
    'General English': 'Geral',
    'Medical English': 'Saúde',
    'Legal English': 'Direito',
    'Technology English': 'Tecnologia',
    'Inglês Geral': 'Geral',
    # Cursos de prática (laboratório)
    'Oil & Gas': 'Petróleo e Gás',
    'General': 'Geral',
    'Banking': 'Banca',
    'Technology': 'Tecnologia',
    'Executive': 'Executivo',
    'AI Enhanced': 'Inglês com IA',
}
AREAS_SEM_VALOR = {'', 'Sem categoria'}

# Níveis: escala CEFR única (ver apps/courses/niveis.py). Valor -> nome curto para selects.
NIVEIS = {c: f'{c} ({niveis.NOMES[c]})' for c in niveis.CEFR}

TITULOS_POR_OMISSAO = {'', 'Curso sem título', 'Novo Curso'}

TIPOS_EXERCICIO = {
    'SELECT': 'Escolha múltipla',
    'ASSIST': 'Escolha assistida',
    'FILL_BLANK': 'Completar',
    'TRANSLATION': 'Tradução',
    'MATCH_PAIRS': 'Pares',
    'SENTENCE_ORDER': 'Ordenar a frase',
    'TRUE_FALSE': 'Verdadeiro ou falso',
    'LISTENING': 'Ouvir',
    'SPEAKING': 'Falar',
    'RESPONDER': 'Responder',
    'VAPI_CONVERSATION': 'Conversa curta',
}


# ---------------------------------------------------------------------------
# Quem é quem
# ---------------------------------------------------------------------------

def e_staff(user):
    """
    Administrador da plataforma (conta activa com papel admin, ou superutilizador): pode agir como
    professor em qualquer curso e abrir qualquer conteúdo. `is_staff` sozinho não chega.
    Nome antigo mantido por compatibilidade; a regra é a de apps.core.permissions.e_administrador.
    """
    from apps.core.permissions import e_administrador
    return e_administrador(user)


def e_professor(user):
    return bool(user and user.is_authenticated and getattr(user, 'role', None) == 'teacher')


def e_dono_ou_staff(user, course):
    if not user or not user.is_authenticated:
        return False
    return course.teacher_id == user.id or e_staff(user)


# ---------------------------------------------------------------------------
# Estado e rótulos
# ---------------------------------------------------------------------------

def estado(course):
    return ESTADO_API.get(course.status, 'rascunho')


def area_pt(categoria):
    if not categoria or categoria in AREAS_SEM_VALOR:
        return None
    return AREAS.get(categoria, categoria)


AREAS_VIDEO = ('Industry English', 'Financial English', 'Technical English', 'Business English',
               'General English', 'Medical English', 'Legal English', 'Technology English', 'Inglês Geral')
AREAS_PRATICA = ('Oil & Gas', 'General', 'Banking', 'Technology', 'Executive', 'AI Enhanced')


def categoria_de_entrada(valor, course_type='video'):
    """
    Aceita o valor guardado ('Industry English') ou o rótulo ('Petróleo e Gás'); o rótulo é
    convertido no valor do tipo de curso (os cursos de prática usam 'Oil & Gas', ...).
    """
    valor = (valor or '').strip()
    if valor in AREAS:
        return valor
    preferidas = AREAS_PRATICA if course_type == 'practice' else AREAS_VIDEO
    candidatas = [c for c, rotulo in AREAS.items() if rotulo.lower() == valor.lower()]
    for chave in candidatas:
        if chave in preferidas:
            return chave
    return candidatas[0] if candidatas else valor


def nivel_pt(nivel):
    """'Nível B1' (aceita valores antigos guardados); None sem nível."""
    return niveis.rotulo(nivel)


def nivel_de_entrada(valor):
    """Só códigos CEFR (A1..C2, qualquer caixa); os nomes antigos são recusados."""
    return niveis.cefr_de_entrada(valor)


def definicoes(course):
    guardadas = course.definicoes if isinstance(course.definicoes, dict) else {}
    return {**DEFINICOES_OMISSAO, **{k: v for k, v in guardadas.items() if k in DEFINICOES_OMISSAO}}


def definicao(course, chave):
    return definicoes(course).get(chave)


def tipo_api(course):
    return 'pratica' if course.course_type == 'practice' else 'video'


# ---------------------------------------------------------------------------
# Filtros para o lado do estudante
# ---------------------------------------------------------------------------

def q_catalogo(prefixo=''):
    """Cursos que aparecem no catálogo (listas, destaques, pesquisa)."""
    return Q(**{f'{prefixo}status': PUBLICADO, f'{prefixo}visivel_catalogo': True})


def q_conteudo_aluno(prefixo=''):
    """
    Cursos cujo conteúdo um inscrito ainda pode abrir: publicados, arquivados a manter e os que
    estavam arquivados a manter e foram submetidos de novo (em revisão).
    """
    return (Q(**{f'{prefixo}status': PUBLICADO})
            | Q(**{f'{prefixo}status': ARQUIVADO, f'{prefixo}modo_arquivo': MANTER})
            | Q(**{f'{prefixo}status': EM_REVISAO, f'{prefixo}estado_antes_revisao': ARQUIVADO,
                   f'{prefixo}modo_arquivo': MANTER}))


def arquivado_efectivo(course):
    """Arquivado, ou em revisão depois de ter estado arquivado (os inscritos contam como num arquivado)."""
    return course.status == ARQUIVADO or (
        course.status == EM_REVISAO and getattr(course, 'estado_antes_revisao', '') == ARQUIVADO)


def q_aula_visivel(prefixo=''):
    """
    Aulas que os alunos vêem: uma aula de vídeo sem vídeo ainda não está pronta e fica escondida
    (não aparece, não conta para o progresso nem para o certificado).
    """
    return ~Q(**{f'{prefixo}type': 'Video', f'{prefixo}video': ''})


def aula_visivel(chapter):
    return not (chapter.type == 'Video' and not chapter.video)


MENSAGEM_FECHADO = ('Este curso foi fechado pelo professor. '
                    'Os certificados já emitidos continuam válidos.')
MENSAGEM_INDISPONIVEL = 'Este curso não está disponível.'


def participou_pratica(user, course):
    """Num curso de prática não há matrícula: conta quem já fez exercícios ou o tem activo."""
    from apps.practice.models import ChallengeProgress, UserProgress
    if ChallengeProgress.objects.filter(user=user, challenge__lesson__unit__course=course).exists():
        return True
    return UserProgress.objects.filter(user=user, active_course=course).exists()


def bloqueio_conteudo(user, course):
    """
    None se a pessoa pode abrir o conteúdo do curso no estado actual; senão (codigo, mensagem).
    Não verifica a matrícula nem o plano (isso fica nos sítios que já o faziam), só o estado:
    - publicado: sim;
    - arquivado a manter: sim (a matrícula/participação continua a ser exigida à parte);
    - arquivado a fechar: não;
    - rascunho / em revisão: não.
    O professor do curso e os administradores podem sempre.
    """
    if e_dono_ou_staff(user, course):
        return None
    if course.status == PUBLICADO:
        return None
    if arquivado_efectivo(course):
        if course.modo_arquivo == FECHAR:
            return ('curso_fechado', MENSAGEM_FECHADO)
        return None
    return ('curso_indisponivel', MENSAGEM_INDISPONIVEL)


def bloqueio_pratica(user, course):
    """
    Regras de estado e definições para jogar um curso de prática:
    estado (bloqueio_conteudo), arquivado a manter só para quem já participava,
    e o máximo de alunos para quem ainda não participava.
    """
    erro = bloqueio_conteudo(user, course)
    if erro:
        return erro
    if e_dono_ou_staff(user, course):
        return None
    if arquivado_efectivo(course):
        if not participou_pratica(user, course):
            return ('curso_arquivado', 'Este curso foi arquivado e já não aceita alunos novos.')
        return None
    if course.maximo_alunos and not participou_pratica(user, course):
        if alunos_pratica(course) >= course.maximo_alunos:
            return ('curso_cheio', 'Este curso já atingiu o número máximo de alunos.')
    return None


def alunos_pratica(course):
    from apps.practice.models import ChallengeProgress
    return (ChallengeProgress.objects.filter(challenge__lesson__unit__course=course)
            .values('user_id').distinct().count())


def bloqueio_inscricao(user, course):
    """
    None se a pessoa se pode inscrever agora; senão (codigo, mensagem, status_http).
    Quem já está inscrito não é bloqueado (a inscrição é idempotente).
    """
    from apps.courses.models import CourseEnrollment

    if e_dono_ou_staff(user, course):
        return None
    if CourseEnrollment.objects.filter(user=user, course=course).exists():
        return None
    if course.status == ARQUIVADO:
        return ('curso_arquivado', 'Este curso foi arquivado e já não aceita inscrições.', 400)
    if course.status != PUBLICADO:
        return ('curso_indisponivel', MENSAGEM_INDISPONIVEL, 404)
    if not course.inscricao_livre:
        return ('inscricoes_fechadas', 'As inscrições neste curso estão fechadas.', 400)
    if course.maximo_alunos:
        inscritos = CourseEnrollment.objects.filter(course=course, is_active=True).count()
        if inscritos >= course.maximo_alunos:
            return ('curso_cheio', 'Este curso já atingiu o número máximo de alunos.', 400)
    return None


# ---------------------------------------------------------------------------
# Verificação antes de submeter
# ---------------------------------------------------------------------------

def _plural(n, singular, plural):
    return f'{n} {singular if n == 1 else plural}'


def _lista_titulos(titulos):
    titulos = [f'"{t}"' for t in titulos]
    if len(titulos) <= 1:
        return ''.join(titulos)
    return ', '.join(titulos[:-1]) + ' e ' + titulos[-1]


def _agrupar(onde_titulos, rotulo, limite=6):
    """[(n_grupo, titulo)] -> 'Secção 3, "A" e "B"; Secção 5, "C"' (corta depois de `limite`)."""
    grupos = {}
    for n, titulo in onde_titulos[:limite]:
        grupos.setdefault(n, []).append(titulo or 'sem título')
    texto = '; '.join(f'{rotulo} {n}, {_lista_titulos(t)}' for n, t in grupos.items())
    resto = len(onde_titulos) - limite
    if resto > 0:
        texto += f' e mais {resto}'
    return texto


def _item(chave, titulo, ok, detalhe):
    return {'chave': chave, 'titulo': titulo, 'ok': bool(ok), 'detalhe': detalhe}


def _item_dados(course):
    falta = []
    if (course.title or '').strip() in TITULOS_POR_OMISSAO:
        falta.append('título')
    if (course.category or '').strip() in AREAS_SEM_VALOR:
        falta.append('área')
    if not course.level:
        falta.append('nível')
    if falta:
        detalhe = 'Falta preencher: ' + ', '.join(falta) + '.'
    else:
        detalhe = f'{area_pt(course.category)}, nível {niveis.normalizar(course.level) or course.level}.'
    return _item('dados', 'Título, área e nível preenchidos', not falta, detalhe)


def _perguntas_quiz(chapter, perguntas_licao):
    from apps.courses.questionarios import perguntas_validas
    n = len(perguntas_validas(chapter.quiz_data))
    if n == 0 and chapter.practice_lesson_id:
        n = perguntas_licao.get(chapter.practice_lesson_id, 0)
    return n


def verificar_video(course, so_visiveis=False):
    """
    so_visiveis: ignora as aulas escondidas (vídeo ainda por carregar). Usado para proteger um curso
    publicado: uma aula nova sem vídeo não o torna incompleto, porque os alunos não a vêem.
    """
    from apps.courses.models import CourseSection, Chapter
    from apps.practice.models import PracticeChallenge

    itens = [_item_dados(course)]
    itens.append(_item(
        'capa', 'Imagem de capa', bool(course.image),
        'Imagem de capa carregada.' if course.image else 'Carregue uma imagem de capa para o catálogo.'))

    seccoes = list(CourseSection.objects.filter(course=course).order_by('order', 'created_at'))
    numero = {s.id: i for i, s in enumerate(seccoes, start=1)}
    aulas_qs = Chapter.objects.filter(section__course=course)
    if so_visiveis:
        aulas_qs = aulas_qs.filter(q_aula_visivel())
    aulas = list(aulas_qs
                 .order_by('section__order', 'section__created_at', 'order', 'created_at')
                 .only('id', 'title', 'type', 'video', 'quiz_enabled', 'quiz_data',
                       'practice_lesson_id', 'section_id'))
    com_aulas = {a.section_id for a in aulas}
    ok_estrutura = bool(com_aulas)
    if ok_estrutura:
        detalhe = f'{_plural(len(seccoes), "secção", "secções")}, {_plural(len(aulas), "aula", "aulas")}.'
    elif seccoes:
        detalhe = 'As secções ainda não têm aulas.'
    else:
        detalhe = 'Crie pelo menos uma secção com uma aula.'
    itens.append(_item('estrutura', 'Pelo menos uma secção com uma aula', ok_estrutura, detalhe))

    sem_video = [(numero.get(a.section_id), a.title) for a in aulas if a.type == 'Video' and not a.video]
    if sem_video:
        detalhe = (f'{_plural(len(sem_video), "aula sem vídeo", "aulas sem vídeo")}: '
                   f'{_agrupar(sem_video, "Secção")}.')
    elif any(a.type == 'Video' for a in aulas):
        detalhe = 'Todas as aulas de vídeo têm vídeo.'
    else:
        detalhe = 'Não há aulas de vídeo.'
    itens.append(_item('videos', 'Todas as aulas têm vídeo', not sem_video and ok_estrutura, detalhe))

    licoes_ligadas = {a.practice_lesson_id for a in aulas if a.practice_lesson_id}
    perguntas_licao = dict(
        PracticeChallenge.objects.filter(lesson_id__in=licoes_ligadas)
        .values_list('lesson_id').annotate(n=Count('id'))
    ) if licoes_ligadas else {}
    com_quiz = [a for a in aulas if a.quiz_enabled or a.type == 'Quiz']
    curtos = [(numero.get(a.section_id), a.title) for a in com_quiz if _perguntas_quiz(a, perguntas_licao) < 3]
    if curtos:
        detalhe = (f'{_plural(len(curtos), "questionário com menos de 3 perguntas", "questionários com menos de 3 perguntas")}: '
                   f'{_agrupar(curtos, "Secção")}.')
    elif com_quiz:
        detalhe = f'{_plural(len(com_quiz), "questionário", "questionários")} com 3 ou mais perguntas.'
    else:
        detalhe = 'Sem questionários.'
    itens.append(_item('questionarios', 'Questionários com pelo menos 3 perguntas', not curtos, detalhe))
    return itens


def exercicio_valido(challenge, opcoes):
    """opcoes: lista de ChallengeOption do exercício. Devolve (ok, motivo)."""
    certas = [o for o in opcoes if o.is_correct]
    tipo = challenge.type
    contexto = challenge.conversation_context if isinstance(challenge.conversation_context, dict) else {}
    if tipo == 'VAPI_CONVERSATION':
        # Conversa curta no fim da lição: situação e 2 a 3 frases-alvo.
        from apps.courses.api.teacher.pratica_formato import MIN_FRASES_CONVERSA, frases_da_conversa
        if not (challenge.question or '').strip():
            return False, 'sem situação'
        if len(frases_da_conversa(contexto)) < MIN_FRASES_CONVERSA:
            return False, f'menos de {MIN_FRASES_CONVERSA} frases para o aluno usar'
        return True, ''
    if tipo == 'RESPONDER':
        if not (challenge.question or '').strip():
            return False, 'sem pergunta'
        if not str(contexto.get('frase_alvo') or '').strip():
            return False, 'sem frase-alvo'
        return True, ''
    if not (challenge.question or '').strip() and tipo != 'SPEAKING':
        return False, 'sem enunciado'
    if tipo == 'LISTENING' and not (challenge.reference_audio_url or '').strip():
        return False, 'sem áudio'
    if tipo in ('SELECT', 'ASSIST', 'TRUE_FALSE'):
        if len(opcoes) < 2:
            return False, 'menos de 2 opções'
        if not certas:
            return False, 'sem resposta certa'
    elif tipo in ('FILL_BLANK', 'TRANSLATION', 'LISTENING'):
        if not certas:
            return False, 'sem resposta certa'
    elif tipo == 'SENTENCE_ORDER':
        if len(opcoes) < 2:
            return False, 'menos de 2 palavras'
    elif tipo == 'MATCH_PAIRS':
        from apps.courses.api.student.practice_courses.jogar import SEPARADORES_PAR
        pares = [o for o in opcoes if any(s in (o.text or '') for s in SEPARADORES_PAR)]
        if len(pares) < 2:
            return False, 'menos de 2 pares'
    elif tipo == 'SPEAKING':
        if not (challenge.question or '').strip() and not opcoes:
            return False, 'sem frase para dizer'
    return True, ''


def verificar_pratica(course):
    from django.db.models import Prefetch
    from apps.practice.models import PracticeUnit, PracticeLesson, PracticeChallenge, ChallengeOption

    itens = [_item_dados(course)]
    unidades = list(PracticeUnit.objects.filter(course=course).order_by('order'))
    numero = {u.id: i for i, u in enumerate(unidades, start=1)}
    licoes = list(
        PracticeLesson.objects.filter(unit__course=course)
        .order_by('unit__order', 'order')
        .prefetch_related(
            Prefetch('challenges', queryset=PracticeChallenge.objects.order_by('order')),
            Prefetch('challenges__options', queryset=ChallengeOption.objects.order_by('order')),
        )
    )
    exercicios = [(l, ch) for l in licoes for ch in l.challenges.all()]
    ok_estrutura = bool(licoes)
    if ok_estrutura:
        detalhe = (f'{_plural(len(unidades), "unidade", "unidades")}, {_plural(len(licoes), "lição", "lições")}, '
                   f'{_plural(len(exercicios), "exercício", "exercícios")}.')
    elif unidades:
        detalhe = 'As unidades ainda não têm lições.'
    else:
        detalhe = 'Crie pelo menos uma unidade com uma lição.'
    itens.append(_item('estrutura', 'Pelo menos uma unidade com uma lição', ok_estrutura, detalhe))

    curtas = [(numero.get(l.unit_id), l.title) for l in licoes if len(l.challenges.all()) < 3]
    if curtas:
        detalhe = (f'{_plural(len(curtas), "lição com menos de 3 exercícios", "lições com menos de 3 exercícios")}: '
                   f'{_agrupar(curtas, "Unidade")}.')
    elif licoes:
        detalhe = 'Todas as lições têm 3 ou mais exercícios.'
    else:
        detalhe = 'Ainda não há lições.'
    itens.append(_item('exercicios', 'Cada lição tem pelo menos 3 exercícios', not curtas and ok_estrutura, detalhe))

    invalidos = []
    for licao, ch in exercicios:
        ok, motivo = exercicio_valido(ch, list(ch.options.all()))
        if not ok:
            frase = (ch.question or '').strip() or TIPOS_EXERCICIO.get(ch.type, ch.type)
            invalidos.append((numero.get(licao.unit_id), f'{frase[:60]}" ({motivo})'.rstrip()))
    if invalidos:
        # _agrupar põe aspas à volta; o motivo vai a seguir ao fecho das aspas.
        grupos = {}
        for n, texto in invalidos[:6]:
            grupos.setdefault(n, []).append('"' + texto)
        partes = '; '.join(f'Unidade {n}, ' + ', '.join(t) for n, t in grupos.items())
        resto = len(invalidos) - 6
        if resto > 0:
            partes += f' e mais {resto}'
        detalhe = f'{_plural(len(invalidos), "exercício incompleto", "exercícios incompletos")}: {partes}.'
    elif exercicios:
        detalhe = 'Todos os exercícios estão completos.'
    else:
        detalhe = 'Ainda não há exercícios.'
    itens.append(_item('respostas', 'Todos os exercícios têm resposta certa', not invalidos and bool(exercicios), detalhe))
    return itens


def verificar(course, so_visiveis=False):
    itens = verificar_pratica(course) if course.course_type == 'practice' else verificar_video(course, so_visiveis)
    return {'itens': itens, 'pode_submeter': all(i['ok'] for i in itens)}


# ---------------------------------------------------------------------------
# Serializers antigos de criação/edição (teacher/video-courses/ e courses/)
# ---------------------------------------------------------------------------

def limpar_criacao(validated_data):
    """Um curso novo é sempre rascunho e sem destaque (o pedido não decide)."""
    validated_data['status'] = RASCUNHO
    validated_data['is_featured'] = False
    return validated_data


def limpar_edicao(instance, validated_data):
    """
    Na edição, o estado e o destaque não mudam por aqui: enviar o mesmo valor é aceite
    (os ecrãs antigos mandam o formulário inteiro), mudá-lo dá 400.
    """
    from rest_framework.exceptions import ValidationError

    erros = {}
    if 'status' in validated_data:
        if validated_data.pop('status') != instance.status:
            erros['status'] = ['O estado do curso muda-se ao submeter para revisão ou ao arquivar.']
    if 'is_featured' in validated_data:
        if bool(validated_data.pop('is_featured')) != bool(instance.is_featured):
            erros['is_featured'] = ['Só o administrador pode destacar cursos.']
    if erros:
        raise ValidationError(erros)
    return validated_data
