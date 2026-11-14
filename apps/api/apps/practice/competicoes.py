"""
Competições: participantes, classificação, início e fecho (prémios e avisos).

Quem participa:
- competição com cursos (de um professor, ou da plataforma com cursos): os alunos desses
  cursos participam automaticamente, sem se inscreverem (actividade.alunos_dos_cursos);
- competição de professor com `todos_os_cursos`: os cursos dele no momento do cálculo;
- competição da plataforma sem cursos: todos os alunos com actividade no período, mais os
  que se inscreveram pelo endpoint antigo (join).

A classificação conta a métrica `conta` entre o início e o fim, só nos cursos da competição
(minutos_conversa: minutos com o tutor desses alunos no período). Desempate: pontos no período;
com o mesmo valor e os mesmos pontos partilham o lugar (1, 1, 3).

Datas: `inicio`/`fim` da API são dias (hora de Luanda); start_date = inicio às 00:00 e
end_date = dia seguinte ao fim às 00:00 (exclusivo).

Fecho (comando fechar_competicoes, de hora a hora):
- avisa os participantes quando a competição começa (Notification, uma vez);
- quando termina: grava a classificação final em CompetitionParticipant (valor, lugar),
  atribui o prémio a quem ficou nos primeiros `premio_lugares` lugares com valor > 0 (os
  empatados partilham o lugar e todos recebem o prémio) e avisa-os:
  medalha -> aviso "Medalha" (fica registada em CompetitionParticipant.premio);
  certificado_merito -> aviso com ligação (BACKEND_BASE_URL) para a página HTML imprimível
  /api/v1/practice/competicoes/<id>/certificado/ (só o próprio vencedor a abre);
  plano -> aviso; o mês de plano é activado à mão pelo administrador (sem integração).
"""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import actividade
from .liga import nome_publico
from .models import Competition, CompetitionParticipant

FUSO = actividade.FUSO
NOME_CONTA = dict(Competition.CONTA_CHOICES)
NOME_PREMIO = dict(Competition.PREMIO_CHOICES)
UNIDADE_CONTA = {'licoes': 'lições', 'pontos': 'pontos', 'minutos_conversa': 'minutos', 'dias_seguidos': 'dias'}
LIMITE_CLASSIFICACAO = 50


def inicio_do_dia(d):
    return datetime.combine(d, time.min, tzinfo=FUSO)


def dia_inicio(c):
    return timezone.localtime(c.start_date, FUSO).date()


def dia_fim(c):
    """Último dia da competição (end_date é exclusivo)."""
    return timezone.localtime(c.end_date - timedelta(microseconds=1), FUSO).date()


def estado(c, agora=None):
    agora = agora or timezone.now()
    if agora < c.start_date:
        return 'agendada'
    if agora < c.end_date:
        return 'activa'
    return 'terminada'


def status_modelo(est):
    return {'agendada': 'upcoming', 'activa': 'active', 'terminada': 'ended'}[est]


def cursos_ids(c):
    """
    Ids dos cursos da competição; None = toda a plataforma.
    "Todos os cursos" de um professor = os cursos dele cujo conteúdo os alunos podem abrir
    (publicados ou arquivados a manter); rascunhos, em revisão e fechados não contam.
    """
    if c.criado_por_id and c.todos_os_cursos:
        from apps.courses import ciclo
        from apps.courses.models import Course
        return list(Course.objects.filter(ciclo.q_conteudo_aluno(), teacher_id=c.criado_por_id)
                    .values_list('id', flat=True))
    ids = [x.id for x in c.cursos.all()]
    if ids:
        return ids
    return [] if c.criado_por_id else None


def participantes_ids(c, cursos=None):
    cursos = cursos_ids(c) if cursos is None else cursos
    if cursos is not None:
        return actividade.alunos_dos_cursos(cursos)
    User = get_user_model()
    ids = set(c.participants.values_list('user_id', flat=True))
    activos = actividade.valores(c.conta, User.objects.filter(role='student', is_active=True)
                                 .values_list('id', flat=True), None, c.start_date, c.end_date)
    return ids | {uid for uid, v in activos.items() if v > 0}


def classificacao(c, limite=LIMITE_CLASSIFICACAO, agora=None):
    """Lista ordenada [{lugar, aluno_id, nome, valor, pontos}] (todas as linhas se limite=None)."""
    agora = agora or timezone.now()
    cursos = cursos_ids(c)
    ids = participantes_ids(c, cursos)
    if not ids:
        return []
    fim = min(c.end_date, agora) if estado(c, agora) != 'agendada' else c.start_date
    valores = actividade.valores(c.conta, ids, cursos, c.start_date, fim)
    pontos = valores if c.conta == 'pontos' else actividade.valores('pontos', ids, cursos, c.start_date, fim)
    User = get_user_model()
    nomes = dict(User.objects.filter(id__in=ids).values_list('id', 'name'))
    linhas = sorted(ids, key=lambda u: (-valores[u], -pontos[u], (nomes.get(u) or '').lower(), str(u)))
    # Empates (mesmo valor e mesmos pontos) partilham o lugar: 1, 1, 3 ("standard competition ranking").
    out = []
    for i, u in enumerate(linhas, start=1):
        if out and (valores[u], pontos[u]) == (out[-1]['valor'], out[-1]['pontos']):
            lugar = out[-1]['lugar']
        else:
            lugar = i
        out.append({'lugar': lugar, 'aluno_id': str(u), 'nome': nome_publico(nomes.get(u)),
                    'valor': valores[u], 'pontos': pontos[u]})
    return out[:limite] if limite else out


def _notificar(user_id, titulo, corpo, link, chave):
    from apps.users.models import Notification
    User = get_user_model()
    user = User.objects.filter(id=user_id).first()
    if user is None:
        return
    Notification.notify(user, Notification.KIND_LEAGUE, title=titulo, body=corpo, link=link, dedupe_key=chave)


def link_aluno(c):
    return '/user/laboratory/achievements#liga'


def link_certificado(c):
    from django.conf import settings
    base = getattr(settings, 'BACKEND_BASE_URL', '').rstrip('/')
    return f'{base}/api/v1/practice/competicoes/{c.id}/certificado/'


def avisar_inicio(c):
    """Avisa os participantes de que a competição começou (uma vez)."""
    with transaction.atomic():
        c = Competition.objects.select_for_update().get(pk=c.pk)
        if c.inicio_notificado:
            return 0
        c.inicio_notificado = True
        c.status = 'active'
        c.save(update_fields=['inicio_notificado', 'status', 'updated_at'])
    ids = participantes_ids(c)
    corpo = (f'Conta: {NOME_CONTA[c.conta].lower()}, até {dia_fim(c).strftime("%d/%m")}. '
             f'Prémio para os {c.premio_lugares} primeiros: {NOME_PREMIO[c.premio].lower()}.')
    for uid in ids:
        _notificar(uid, f'Começou a competição «{c.title}»', corpo, link_aluno(c), f'competicao:{c.pk}:inicio')
    return len(ids)


def fechar(c, agora=None):
    """Grava a classificação final, atribui os prémios e avisa os vencedores. Idempotente."""
    agora = agora or timezone.now()
    with transaction.atomic():
        c = Competition.objects.select_for_update().get(pk=c.pk)
        if c.fechada_em is not None or agora < c.end_date:
            return []
        linhas = classificacao(c, limite=None, agora=c.end_date)
        vencedores = []
        for l in linhas:
            premio = ''
            if l['lugar'] <= c.premio_lugares and l['valor'] > 0:
                premio = c.premio
                vencedores.append(l)
            CompetitionParticipant.objects.update_or_create(
                competition=c, user_id=l['aluno_id'],
                defaults={'valor': l['valor'], 'points_earned': l['pontos'], 'current_rank': l['lugar'],
                          'best_rank': l['lugar'], 'premio': premio})
        c.fechada_em = agora
        c.status = 'ended'
        c.save(update_fields=['fechada_em', 'status', 'updated_at'])

    for l in vencedores:
        texto_lugar = f'{l["lugar"]}.º lugar'
        if c.premio == Competition.PREMIO_CERTIFICADO:
            titulo = f'Certificado de mérito: {texto_lugar} em «{c.title}»'
            corpo = 'Parabéns! Abra a ligação para ver e imprimir o seu certificado de mérito.'
            link = link_certificado(c)
        elif c.premio == Competition.PREMIO_MEDALHA:
            titulo = f'Ganhou uma medalha: {texto_lugar} em «{c.title}»'
            corpo = f'Parabéns! Ficou em {texto_lugar} com {l["valor"]} {UNIDADE_CONTA[c.conta]}.'
            link = link_aluno(c)
        else:
            titulo = f'Ganhou um mês de plano: {texto_lugar} em «{c.title}»'
            corpo = 'Parabéns! A equipa ProEnglish vai activar o seu mês de plano nos próximos dias.'
            link = link_aluno(c)
        _notificar(l['aluno_id'], titulo, corpo, link, f'competicao:{c.pk}:premio')
    return vencedores


def processar(agora=None):
    """Avisa as que começaram e fecha as que terminaram. Devolve (avisadas, fechadas)."""
    agora = agora or timezone.now()
    avisadas = fechadas = 0
    for c in Competition.objects.filter(inicio_notificado=False, start_date__lte=agora, end_date__gt=agora):
        avisar_inicio(c)
        avisadas += 1
    for c in Competition.objects.filter(fechada_em__isnull=True, end_date__lte=agora):
        fechar(c, agora)
        fechadas += 1
    return avisadas, fechadas


def competicoes_do_aluno(user, agora=None, incluir_agendadas=False):
    """Competições activas (com cursos) de que o aluno participa automaticamente
    (e as que vão começar, com incluir_agendadas)."""
    from django.db.models import Q
    agora = agora or timezone.now()
    cursos = actividade.cursos_do_aluno(user)
    if not cursos:
        return []
    from apps.courses.models import Course
    professores = list(Course.objects.filter(id__in=cursos).values_list('teacher_id', flat=True))
    qs = Competition.objects.filter(end_date__gt=agora)
    if not incluir_agendadas:
        qs = qs.filter(start_date__lte=agora)
    qs = (qs.order_by('start_date', 'end_date')
          .filter(Q(cursos__in=cursos) | Q(todos_os_cursos=True, criado_por_id__in=professores))
          .distinct().prefetch_related('cursos'))
    return [c for c in qs if user.id in participantes_ids(c)]


def _cursos_api(c, cursos):
    if cursos is None:
        return []
    from apps.courses.models import Course
    return [{'id': str(x.id), 'titulo': x.title}
            for x in Course.objects.filter(id__in=cursos).only('id', 'title').order_by('title')]


def resumo_aluno(c, user, agora=None):
    """Item de competição (activa ou agendada) para o aluno, com o lugar dele."""
    agora = agora or timezone.now()
    linhas = classificacao(c, limite=None, agora=agora)
    minha = next((l for l in linhas if l['aluno_id'] == str(user.id)), None)
    est = estado(c, agora)
    hoje = timezone.localtime(agora, FUSO).date()
    return {
        'id': str(c.id),
        'nome': c.title,
        'estado': est,
        'cursos': _cursos_api(c, cursos_ids(c)),
        'conta': c.conta,
        'conta_nome': NOME_CONTA[c.conta],
        'unidade': UNIDADE_CONTA[c.conta],
        'inicio': dia_inicio(c).isoformat(),
        'fim': dia_fim(c).isoformat(),
        # Dias até ao fim, contando hoje (último dia = 1).
        'dias_restantes': max(0, (dia_fim(c) - hoje).days + 1) if est != 'terminada' else 0,
        'premio': c.premio,
        'premio_nome': NOME_PREMIO[c.premio],
        'premio_lugares': c.premio_lugares,
        'participantes': len(linhas),
        'meu_lugar': minha['lugar'] if minha else None,
        'meu_valor': minha['valor'] if minha else 0,
        'topo': [{'lugar': l['lugar'], 'nome': l['nome'], 'valor': l['valor'],
                  'sou_eu': l['aluno_id'] == str(user.id)} for l in linhas[:3]],
    }


def terminadas_do_aluno(user, limite=10):
    """
    Competições fechadas em que o aluno ficou classificado (CompetitionParticipant gravado no
    fecho), das mais recentes para as mais antigas, com o resultado e o prémio dele.
    """
    participacoes = (CompetitionParticipant.objects
                     .filter(user=user, competition__fechada_em__isnull=False, current_rank__isnull=False)
                     .select_related('competition').order_by('-competition__end_date')[:limite])
    out = []
    for p in participacoes:
        c = p.competition
        topo = (CompetitionParticipant.objects.filter(competition=c, current_rank__isnull=False)
                .select_related('user').order_by('current_rank', 'user__name')[:3])
        out.append({
            'id': str(c.id),
            'nome': c.title,
            'estado': 'terminada',
            'conta': c.conta,
            'conta_nome': NOME_CONTA[c.conta],
            'unidade': UNIDADE_CONTA[c.conta],
            'inicio': dia_inicio(c).isoformat(),
            'fim': dia_fim(c).isoformat(),
            'premio': c.premio,
            'premio_nome': NOME_PREMIO[c.premio],
            'premio_lugares': c.premio_lugares,
            'participantes': CompetitionParticipant.objects.filter(competition=c).count(),
            'meu_lugar': p.current_rank,
            'meu_valor': p.valor,
            # Prémio que o aluno ganhou ('' = nenhum) e, no certificado, a página para o abrir.
            'meu_premio': p.premio or None,
            'certificado_url': (link_certificado(c) if p.premio == Competition.PREMIO_CERTIFICADO else None),
            'topo': [{'lugar': t.current_rank, 'nome': nome_publico(t.user.name), 'valor': t.valor,
                      'sou_eu': t.user_id == user.id} for t in topo],
        })
    return out


def premios_do_aluno(user):
    """Prémios ganhos em competições (medalhas, certificados de mérito, meses de plano)."""
    out = []
    for p in (CompetitionParticipant.objects.filter(user=user).exclude(premio='')
              .select_related('competition').order_by('-competition__end_date')):
        c = p.competition
        out.append({
            'competicao_id': str(c.id),
            'competicao': c.title,
            'premio': p.premio,
            'premio_nome': NOME_PREMIO.get(p.premio, p.premio),
            'lugar': p.current_rank,
            'valor': p.valor,
            'unidade': UNIDADE_CONTA[c.conta],
            'fim': dia_fim(c).isoformat(),
            'certificado_url': link_certificado(c) if p.premio == Competition.PREMIO_CERTIFICADO else None,
        })
    return out
