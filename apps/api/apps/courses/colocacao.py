"""
Colocação no curso geral (English Communication Skills): em que nível o aluno começa.

O aluno escolhe um nível de A1 a C1 (decisão de 18/11/2026):
- A1: inscreve-se logo;
- outro nível: tem de passar (70%) no teste escrito do nível anterior (teste_basico.py, por nível):
  escolhe B1 -> teste do A2. Aprovado: entra no nível escolhido. Reprovado: entra no nível testado
  (o A2, no exemplo) e pode repetir o teste ao fim de 24 horas para subir.

Quem decide é o servidor: o cliente só diz o nível que escolheu. A inscrição é no primeiro curso
em vídeo do curso geral desse nível (pelo título: "A2.1" antes de "A2.2"), e o laboratório ligado
a esse curso passa a ser o curso de prática activo. Se ainda não há curso publicado do nível, o
nível fica guardado e a inscrição faz-se quando o curso existir.
"""
from django.db import transaction
from django.utils import timezone

from apps.courses import niveis, teste_basico

NIVEIS_ESCOLHA = ('A1', 'A2', 'B1', 'B2', 'C1')


class ErroColocacao(Exception):
    def __init__(self, codigo, mensagem, status=400, **extra):
        super().__init__(mensagem)
        self.codigo, self.mensagem, self.status, self.extra = codigo, mensagem, status, extra


def nivel_do_teste(escolhido):
    """O teste que dá acesso ao nível escolhido: o do nível anterior (None para o A1)."""
    i = NIVEIS_ESCOLHA.index(escolhido)
    return NIVEIS_ESCOLHA[i - 1] if i > 0 else None


def _categorias_gerais():
    from apps.courses import ciclo
    return [valor for valor, rotulo in ciclo.AREAS.items() if rotulo in teste_basico.AREAS_GERAIS]


def curso_geral(nivel):
    """O primeiro curso em vídeo publicado do curso geral neste nível, ou None."""
    from apps.courses import ciclo
    from apps.courses.models import Course
    candidatos = (Course.objects.filter(course_type='video', level=nivel, category__in=_categorias_gerais(),
                                        status=ciclo.PUBLICADO)
                  .order_by('title', 'created_at'))
    return candidatos.first()


def _curso_pratica(curso):
    """O laboratório ligado às aulas do curso (Chapter.practice_lesson), se houver."""
    from apps.courses.models import Chapter
    aula = (Chapter.objects.filter(section__course=curso, practice_lesson__isnull=False)
            .select_related('practice_lesson__unit__course')
            .order_by('section__order', 'order').first())
    return aula.practice_lesson.unit.course if aula else None


def _curso_dict(c):
    return {'id': str(c.id), 'titulo': c.title} if c else None


def estado(user):
    """Os níveis que se podem escolher e, para cada um, o que falta para lá entrar."""
    lista = []
    for nivel in NIVEIS_ESCOLHA:
        teste = nivel_do_teste(nivel)
        item = {
            'nivel': nivel,
            'nome': niveis.NOMES.get(nivel, nivel),
            'descricao': niveis.DESCRICOES.get(nivel, ''),
            'teste': teste,
            'curso': _curso_dict(curso_geral(nivel)),
        }
        if teste:
            e = teste_basico.estado(user, teste)
            item.update({
                'pode_entrar': e['aprovado_no_nivel'],
                'teste_em_curso': bool(e['em_curso']),
                'teste_reprovado': bool(e['ultima'] and e['ultima']['aprovado'] is False),
                'proxima_tentativa_em': e['proxima_tentativa_em'],
            })
        else:
            item.update({'pode_entrar': True, 'teste_em_curso': False, 'teste_reprovado': False,
                         'proxima_tentativa_em': None})
        lista.append(item)
    prefs = user.preferences if isinstance(user.preferences, dict) else {}
    return {'niveis': lista, 'colocacao': prefs.get('colocacao'),
            'regras': {'aprovacao': teste_basico.PERCENTAGEM_APROVACAO, 'perguntas': teste_basico.N_PERGUNTAS,
                       'minutos': int(teste_basico.DURACAO.total_seconds() // 60)}}


def nivel_final(user, escolhido):
    """O nível em que o aluno entra, pelas regras do topo. Lança ErroColocacao se falta o teste."""
    teste = nivel_do_teste(escolhido)
    if teste is None or teste_basico.aprovado_no_nivel(user, teste):
        return escolhido
    ultima = teste_basico.ultima_tentativa(user, teste)
    if ultima is not None and ultima.submetido_em is not None and not ultima.aprovado:
        return teste
    raise ErroColocacao('teste_necessario',
                        f'Para começar no {escolhido}, faça primeiro o teste do nível {teste} '
                        f'({teste_basico.PERCENTAGEM_APROVACAO}% para passar).', 409, teste=teste)


def colocar(user, escolhido):
    """Aplica a colocação: guarda o nível e inscreve no curso geral desse nível. Devolve o resultado."""
    from django.contrib.auth import get_user_model

    from apps.courses import ciclo
    from apps.courses.matriculas import matricular_em_curso
    from apps.practice.models import UserProgress

    escolhido = str(escolhido or '').strip().upper()
    if escolhido not in NIVEIS_ESCOLHA:
        raise ErroColocacao('validation_error', 'Escolha um nível de A1 a C1.')
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        final = nivel_final(user, escolhido)
        prefs = dict(user.preferences) if isinstance(user.preferences, dict) else {}
        prefs['nivel'] = final
        prefs['colocacao'] = {'nivel': final, 'escolhido': escolhido, 'em': timezone.now().isoformat()}
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
            'curso': _curso_dict(curso), 'inscrito': inscrito, 'motivo': motivo,
            'curso_pratica': _curso_dict(pratica)}
