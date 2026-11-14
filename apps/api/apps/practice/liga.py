"""
Liga semanal: ranking dos alunos da mesma liga pelos pontos ganhos nesta semana.

- A liga de cada aluno vem dos pontos totais (UserLeague.get_league_for_points:
  Bronze 0-999, Prata 1000-1999, Ouro 2000-2999, Diamante 3000+). Esta é a única regra
  de subida que existe no sistema; não há promoção "top N da semana".
- Os pontos da semana somam PointsEntry (registado em UserProgress.add_points).
- A semana vai de segunda 00:00 a domingo 23:59 na hora de Angola (Africa/Luanda).
- Privacidade: os outros alunos aparecem só com nome público ("Ana M."), sem ids,
  e-mails nem nome completo.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q, Sum
from django.utils import timezone

from apps.practice.models import PointsEntry, UserLeague, UserProgress

FUSO_ANGOLA = ZoneInfo('Africa/Luanda')
ORDEM_LIGAS = [codigo for codigo, _ in UserLeague.LEAGUE_CHOICES]  # bronze → diamond
LIMITE_LISTA_COMPLETA = 30
JANELA = 5  # lugares acima/abaixo do aluno quando a liga é grande
TOPO = 3


def nome_publico(nome):
    """Primeiro nome + inicial do último apelido ("Ana Martins Silva" -> "Ana S.")."""
    partes = (nome or '').split()
    if not partes:
        return 'Aluno'
    if len(partes) == 1:
        return partes[0]
    return f'{partes[0]} {partes[-1][0].upper()}.'


def limites_semana(agora=None):
    agora = timezone.localtime(agora or timezone.now(), FUSO_ANGOLA)
    segunda = agora.date() - timedelta(days=agora.weekday())
    inicio = datetime.combine(segunda, time.min, tzinfo=FUSO_ANGOLA)
    return inicio, inicio + timedelta(days=7)


def _info_liga(codigo):
    info = UserLeague.get_league_info(codigo)
    return {'id': codigo, 'nome': info['name'], 'icone': info['icon'],
            'pontos_minimos': info['min_points'], 'pontos_maximos': info['max_points']}


def _competicoes(user):
    """(a decorrer e agendadas, terminadas com o resultado do aluno, prémios ganhos)."""
    try:
        from apps.practice.competicoes import (
            competicoes_do_aluno, premios_do_aluno, resumo_aluno, terminadas_do_aluno,
        )
        agora = timezone.now()
        actuais = [resumo_aluno(c, user, agora) for c in competicoes_do_aluno(user, agora, incluir_agendadas=True)]
        return actuais, terminadas_do_aluno(user), premios_do_aluno(user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('liga: falha ao calcular as competições de %s', user.pk)
        return [], [], []


def construir_liga_semanal(user, agora=None):
    inicio, fim = limites_semana(agora)
    progresso = UserProgress.objects.filter(user=user).first()
    meus_pontos_totais = progresso.points if progresso else 0
    liga = UserLeague.get_league_for_points(meus_pontos_totais)
    info = _info_liga(liga)

    filtro_liga = Q(practice_progress__points__gte=info['pontos_minimos'])
    if info['pontos_maximos'] is not None:
        filtro_liga &= Q(practice_progress__points__lte=info['pontos_maximos'])

    from django.contrib.auth import get_user_model
    User = get_user_model()
    participantes = (
        User.objects.filter(filtro_liga, is_active=True, role='student')
        .annotate(pontos_semana=Sum(
            'points_entries__points',
            filter=Q(points_entries__created_at__gte=inicio, points_entries__created_at__lt=fim),
        ))
        .values('id', 'name', 'pontos_semana', 'practice_progress__points')
    )
    linhas = [
        {'id': p['id'], 'name': p['name'], 'semana': p['pontos_semana'] or 0,
         'total': p['practice_progress__points'] or 0}
        for p in participantes
    ]
    if not any(l['id'] == user.id for l in linhas):  # ex.: professor/admin ou sem progresso
        linhas.append({'id': user.id, 'name': user.name, 'total': meus_pontos_totais,
                       'semana': PointsEntry.objects.filter(user=user, created_at__gte=inicio,
                                                            created_at__lt=fim)
                       .aggregate(s=Sum('points'))['s'] or 0})
    linhas.sort(key=lambda l: (-l['semana'], -l['total'], (l['name'] or '').lower(), str(l['id'])))

    minha_pos = next(i for i, l in enumerate(linhas, start=1) if l['id'] == user.id)
    meus_semana = linhas[minha_pos - 1]['semana']
    if len(linhas) <= LIMITE_LISTA_COMPLETA:
        visiveis = set(range(1, len(linhas) + 1))
    else:
        visiveis = set(range(1, TOPO + 1)) | set(range(max(1, minha_pos - JANELA), minha_pos + JANELA + 1))

    ranking = [{
        'posicao': pos,
        'nome': nome_publico(l['name']),
        'pontos_semana': l['semana'],
        'sou_eu': l['id'] == user.id,
    } for pos, l in enumerate(linhas, start=1) if pos in visiveis]

    acima = linhas[minha_pos - 2] if minha_pos > 1 else None
    idx = ORDEM_LIGAS.index(liga)
    proxima = _info_liga(ORDEM_LIGAS[idx + 1]) if idx + 1 < len(ORDEM_LIGAS) else None

    competicoes, terminadas, premios = _competicoes(user)
    return {
        # Competições dos cursos do aluno a decorrer ou agendadas (participação automática),
        # com o lugar dele; as terminadas com o resultado; os prémios ganhos (medalhas...).
        'competicoes': competicoes,
        'competicoes_terminadas': terminadas,
        'premios': premios,
        'semana': {
            'inicio': inicio.isoformat(),
            'fim': fim.isoformat(),
            'fuso_horario': 'Africa/Luanda',
            'segundos_ate_fim': max(0, int((fim - timezone.now()).total_seconds())),
        },
        'liga': info,
        'eu': {
            'posicao': minha_pos,
            'nome': nome_publico(user.name),
            'pontos_semana': meus_semana,
            'pontos_totais': meus_pontos_totais,
            'pontos_para_lugar_acima': (acima['semana'] - meus_semana + 1) if acima else None,
        },
        'participantes': len(linhas),
        'ranking': ranking,
        'regra_promocao': {
            'tipo': 'pontos_totais',
            'descricao': (
                f"Sobe para a {proxima['nome']} ao chegar a {proxima['pontos_minimos']} pontos no total."
                if proxima else 'Está na liga mais alta.'
            ),
            'proxima_liga': proxima,
            'pontos_em_falta': max(0, proxima['pontos_minimos'] - meus_pontos_totais) if proxima else None,
        },
    }
