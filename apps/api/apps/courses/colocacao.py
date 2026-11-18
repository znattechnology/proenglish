"""
Colocação no curso geral (English Communication Skills): em que nível o aluno começa.

O aluno escolhe um nível de A1 a C1 (decisões de 18/11/2026):
- A1: entra logo;
- outro nível: faz UM teste escrito com perguntas de todos os níveis abaixo do escolhido (escolhe
  C1 -> A1, A2, B1 e B2; 30 perguntas repartidas pelos níveis, 30 minutos). Cada nível tem a sua nota
  (70% para passar). Entra no nível a seguir ao último aprovado sem falhar nenhum abaixo, a contar
  do A1, e nunca acima do que escolheu. Quem falha logo o A1 começa no A1.
  Exemplo: escolhe C1, passa A1 e A2, falha B1 -> entra no B1.
- Repetir o teste de colocação: 24 horas depois do último (só serve para subir).
- Testes de nível já feitos contam: quem já provou o A2 (p.ex. no teste do nível básico) pode
  escolher o B1 sem novo teste.

Quem decide é o servidor: o cliente só diz o nível que escolheu. A inscrição é no primeiro curso
em vídeo do curso geral desse nível (pelo título: "A2.1" antes de "A2.2"), e o laboratório ligado
a esse curso passa a ser o curso de prática activo. Se ainda não há curso publicado do nível, o
nível fica guardado e a inscrição faz-se quando o curso existir.

O motor dos testes (perguntas, anulação ao sair do ecrã, correcção) é o de teste_basico.py.
"""
from django.db import transaction
from django.utils import timezone

from apps.courses import niveis, teste_basico

NIVEIS_ESCOLHA = ('A1', 'A2', 'B1', 'B2', 'C1')


class ErroColocacao(Exception):
    def __init__(self, codigo, mensagem, status=400, **extra):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.status, self.extra = codigo, mensagem, status, extra


def _i(nivel):
    return NIVEIS_ESCOLHA.index(nivel) if nivel in NIVEIS_ESCOLHA else -1


def niveis_do_teste(escolhido):
    """Os níveis com perguntas no teste para este nível: todos os de baixo ([] para o A1)."""
    return list(NIVEIS_ESCOLHA[:_i(escolhido)]) if escolhido in NIVEIS_ESCOLHA else []


def seguinte(nivel):
    """O nível a seguir ao provado (A1 se nada está provado)."""
    if nivel is None:
        return 'A1'
    return NIVEIS_ESCOLHA[min(_i(nivel) + 1, len(NIVEIS_ESCOLHA) - 1)]


def _categorias_gerais():
    from apps.courses import ciclo
    return [valor for valor, rotulo in ciclo.AREAS.items() if rotulo in teste_basico.AREAS_GERAIS]


def curso_geral(nivel):
    """O primeiro curso em vídeo publicado do curso geral neste nível, ou None."""
    from apps.courses import ciclo
    from apps.courses.models import Course
    return (Course.objects.filter(course_type='video', level=nivel, category__in=_categorias_gerais(),
                                  status=ciclo.PUBLICADO)
            .order_by('title', 'created_at').first())


def _curso_pratica(curso):
    """O laboratório ligado às aulas do curso (Chapter.practice_lesson), se houver."""
    from apps.courses.models import Chapter
    aula = (Chapter.objects.filter(section__course=curso, practice_lesson__isnull=False)
            .select_related('practice_lesson__unit__course')
            .order_by('section__order', 'order').first())
    return aula.practice_lesson.unit.course if aula else None


def _curso_dict(c):
    return {'id': str(c.id), 'titulo': c.title} if c else None


def _proxima_tentativa(ultima, agora):
    if ultima is None or ultima.submetido_em is None:
        return None
    quando = ultima.created_at + teste_basico.ESPERA_REPETIR
    return quando if quando > agora else None


def pode_entrar(provado, nivel):
    """Entra sem (novo) teste: o A1, ou um nível cujo de baixo já está provado."""
    if _i(nivel) <= 0:
        return True
    anterior = NIVEIS_ESCOLHA[_i(nivel) - 1]
    return provado is not None and _i(provado) >= _i(anterior)


def estado(user):
    """Os níveis que se podem escolher, o que cada um pede, e o teste de colocação em curso ou o último."""
    agora = timezone.now()
    provado = teste_basico.nivel_provado_de(user)
    ultima = teste_basico.ultima_tentativa(user, None)
    em_curso = ultima if ultima and ultima.submetido_em is None else None
    proxima = _proxima_tentativa(ultima, agora)
    lista = []
    for nivel in NIVEIS_ESCOLHA:
        testados = niveis_do_teste(nivel)
        n = teste_basico.N_PERGUNTAS if testados else 0
        lista.append({
            'nivel': nivel,
            'nome': niveis.NOMES.get(nivel, nivel),
            'descricao': niveis.DESCRICOES.get(nivel, ''),
            'niveis_teste': testados,
            'perguntas': n,
            'minutos': n * teste_basico.MINUTOS_POR_PERGUNTA,
            'curso': _curso_dict(curso_geral(nivel)),
            'pode_entrar': pode_entrar(provado, nivel),
        })
    prefs = user.preferences if isinstance(user.preferences, dict) else {}
    return {
        'niveis': lista,
        'provado': provado,
        'em_curso': teste_basico._tentativa_dict(em_curso, com_perguntas=True) if em_curso else None,
        'ultima': teste_basico._tentativa_dict(ultima) if ultima and ultima.submetido_em else None,
        'proxima_tentativa_em': proxima.isoformat() if proxima else None,
        'colocacao': prefs.get('colocacao'),
        'regras': {k: v for k, v in teste_basico.regras().items() if k in ('aprovacao', 'espera_horas')},
    }


def _escolhido(valor):
    escolhido = str(valor or '').strip().upper()
    if escolhido not in NIVEIS_ESCOLHA:
        raise ErroColocacao('validation_error', 'Escolha um nível de A1 a C1.')
    return escolhido


def iniciar_teste(user, escolhido):
    """Abre o teste de colocação para o nível escolhido (ou devolve o que está em curso)."""
    from django.contrib.auth import get_user_model
    escolhido = _escolhido(escolhido)
    if escolhido == 'A1':
        raise ErroColocacao('sem_teste', 'O A1 não pede teste: pode começar logo.')
    with transaction.atomic():
        get_user_model().objects.select_for_update().filter(pk=user.pk).first()
        ultima = teste_basico.ultima_tentativa(user, None)
        if ultima is not None and ultima.submetido_em is None:
            if ultima.para == escolhido:
                return ultima
            raise ErroColocacao('teste_em_curso', f'Tem um teste para o {ultima.para} a meio: termine-o primeiro.',
                                409, para=ultima.para)
        if pode_entrar(teste_basico.nivel_provado_de(user), escolhido):
            raise ErroColocacao('ja_provado', f'Já pode começar no {escolhido} sem teste.')
        proxima = _proxima_tentativa(ultima, timezone.now())
        if proxima is not None:
            raise ErroColocacao('espera', 'Pode repetir o teste de colocação 24 horas depois do último.', 429,
                                proxima_tentativa_em=proxima.isoformat())
        try:
            return teste_basico.criar(user, niveis_do_teste(escolhido), para=escolhido)
        except teste_basico.ErroTeste as e:
            raise ErroColocacao(e.codigo, e.mensagem, e.status) from e


def nivel_final(user, escolhido):
    """O nível em que o aluno entra, pelas regras do topo. Lança ErroColocacao se falta o teste."""
    from apps.courses.models import TesteNivelBasico
    provado = teste_basico.nivel_provado_de(user)
    if pode_entrar(provado, escolhido):
        return escolhido
    # Há um teste de colocação entregue que cobre o nível abaixo do escolhido?
    anterior = NIVEIS_ESCOLHA[_i(escolhido) - 1]
    cobre = any(anterior in (t.niveis or []) for t in
                TesteNivelBasico.objects.filter(user=user, submetido_em__isnull=False).exclude(para=''))
    if cobre:
        final = seguinte(provado)
        return final if _i(final) <= _i(escolhido) else escolhido
    raise ErroColocacao('teste_necessario',
                        f'Para começar no {escolhido}, faça primeiro o teste de colocação '
                        f'({teste_basico.PERCENTAGEM_APROVACAO}% em cada nível para passar).', 409, teste=escolhido)


def colocar(user, escolhido):
    """Aplica a colocação: guarda o nível e inscreve no curso geral desse nível. Devolve o resultado."""
    from django.contrib.auth import get_user_model

    from apps.courses import ciclo
    from apps.courses.matriculas import matricular_em_curso
    from apps.practice.models import UserProgress

    escolhido = _escolhido(escolhido)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        final = nivel_final(user, escolhido)
        prefs = dict(user.preferences) if isinstance(user.preferences, dict) else {}
        prefs['nivel'] = final
        prefs['colocacao'] = {'nivel': final, 'escolhido': escolhido, 'em': timezone.now().isoformat()}
        prefs['acolhimento'] = 'concluido'   # a colocação é o fim da primeira entrada
        user.preferences = prefs
        user.save(update_fields=['preferences'])

        curso = curso_geral(final)
        inscrito, motivo, pratica = False, None, None
        if curso is not None:
            if not curso.user_has_access(user):
                motivo = 'plano'
            elif (bloqueio := ciclo.bloqueio_inscricao(user, curso)) is not None:
                motivo = bloqueio[0]
            else:
                matricular_em_curso(user, curso)
                inscrito = True
                pratica = _curso_pratica(curso)
                if pratica is not None:
                    progresso, _ = UserProgress.objects.get_or_create(user=user)
                    progresso.active_course = pratica
                    progresso.save(update_fields=['active_course'])
        else:
            motivo = 'sem_curso'
    return {'nivel': final, 'escolhido': escolhido, 'no_nivel_escolhido': final == escolhido,
            'provado': teste_basico.nivel_provado_de(user),
            'tem_nivel_basico': teste_basico.tem_nivel_basico(user),
            'curso': _curso_dict(curso), 'inscrito': inscrito, 'motivo': motivo,
            'curso_pratica': _curso_dict(pratica)}
