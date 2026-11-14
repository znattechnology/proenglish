"""
Opiniões dos alunos e testemunhos do site (/api/v1/admin/...).

- GET   opinioes/?estado=por_rever|aprovada|recusada|todas&pagina=
- PATCH opinioes/<id>/          {estado, nota_interna}
- GET   testemunhos/            aprovadas e com autorização pública
- PATCH testemunhos/<id>/       {mostrar}
- POST  testemunhos/ordem/      {ids}  (ordem no site)

No site (GET /api/v1/users/feedback/testimonials/) aparecem só as aprovadas, públicas e com
mostrar=True, pela `ordem`.
"""
import math
import uuid

from django.db import transaction
from django.db.models import Avg
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import EAdministrador

from ..models import UserFeedback
from . import servicos as sv

POR_PAGINA = 25

MOMENTOS = {
    'primeira_licao': 'Depois da primeira lição',
    'curso_concluido': 'Ao concluir o primeiro curso',
    'licoes_5': 'Depois de 5 lições',
    'conversas_5': 'Depois de 5 conversas com o tutor',
    'dias_7': 'Depois de 7 dias de estudo',
    'licoes_25': 'Depois de 25 lições',
    'dias_30': 'Depois de um mês de estudo',
}
MOMENTOS_TRIGGER = {
    'first_lesson': 'Depois da primeira lição',
    'milestone_lessons': 'Depois de várias lições',
    'course_complete': 'Ao concluir um curso',
    'ai_sessions': 'Depois de conversas com o tutor',
    'days_active': 'Depois de vários dias de estudo',
    'manual': 'Por iniciativa própria',
    'prompt': 'A pedido da plataforma',
}


def momento(f):
    chave = (f.context_data or {}).get('chave') if isinstance(f.context_data, dict) else None
    return MOMENTOS.get(chave) or MOMENTOS_TRIGGER.get(f.trigger) or 'Por iniciativa própria'


def area_de(user):
    from ..views import AREAS_PT
    area = (user.preferences or {}).get('area')
    return AREAS_PT.get(area)  # só áreas da lista: o texto livre não vai para o site


NOTA_INTERNA_MAX = 2000


def nome_curto(nome):
    """
    Nome que aparece no site e na pré-visualização da administração (a mesma função nos dois):
    'João Pedro Silva' -> 'João S.'; um só nome fica como está ('João', nunca 'J.').
    """
    partes = [p for p in (nome or '').split() if p]
    if not partes:
        return 'Aluno ProEnglish'
    if len(partes) == 1:
        return partes[0]
    return f'{partes[0]} {partes[-1][0].upper()}.'


def no_site_qs():
    """
    Testemunhos que aparecem no site (GET /api/v1/users/feedback/testimonials/): aprovados,
    autorizados pelo aluno, marcados para mostrar e de contas activas (nunca de contas
    suspensas ou apagadas).
    """
    return (UserFeedback.objects.filter(estado=UserFeedback.APROVADA, allow_public=True, mostrar=True,
                                        user__is_active=True)
            .exclude(comment='').exclude(user__email__endswith='@apagado.invalid'))


def proxima_ordem():
    """Ordem para uma opinião acabada de aprovar: depois de todas as outras (fica em último)."""
    from django.db.models import Max
    m = UserFeedback.objects.filter(estado=UserFeedback.APROVADA).aggregate(m=Max('ordem'))['m']
    return (m or 0) + 1


def aprovar(f):
    """Marca como aprovada (sem gravar) e põe-na no fim da ordem dos testemunhos."""
    f.estado = UserFeedback.APROVADA
    f.ordem = proxima_ordem()


def _plano(user, agora):
    if user.role != 'student':
        return None
    return sv.NOME_PLANO[sv.plano_em_vigor(getattr(user, 'subscription', None), agora)]


def opiniao_dict(f, agora):
    return {
        'id': str(f.id),
        'nome': f.user.name,
        'area': area_de(f.user),
        'plano': _plano(f.user, agora),
        'nota': f.rating,
        'comentario': f.comment,
        'momento': momento(f),
        'estado': f.estado,
        'permite_publico': f.allow_public,
        'permite_contacto': f.allow_contact,
        'contacto': f.user.email if f.allow_contact else None,
        'criada_em': sv.iso(f.created_at),
        'nota_interna': f.admin_notes,
    }


ESTADOS_FILTRO = ('por_rever', 'aprovada', 'recusada', 'todas')


@api_view(['GET'])
@permission_classes([EAdministrador])
def opinioes(request):
    agora = timezone.now()
    estado = request.query_params.get('estado') or 'por_rever'
    if estado not in ESTADOS_FILTRO:
        return sv.erro_validacao({'estado': ['Use por_rever, aprovada, recusada ou todas.']})
    todas = UserFeedback.objects.all()
    por_rever = todas.filter(estado=UserFeedback.POR_REVER)
    media = todas.filter(rating__isnull=False).aggregate(m=Avg('rating'))['m']
    numeros = {
        'total': todas.count(),
        'novas_mes': todas.filter(created_at__gte=sv.inicio_mes_luanda(agora)).count(),
        'media': round(float(media), 1) if media is not None else None,
        'por_rever': por_rever.count(),
        'por_rever_publicas': por_rever.filter(allow_public=True).count(),
        'no_site': no_site_qs().count(),
    }
    qs = todas if estado == 'todas' else todas.filter(estado=estado)
    total = qs.count()
    paginas = max(1, math.ceil(total / POR_PAGINA))
    try:
        pagina = min(max(1, int(request.query_params.get('pagina') or 1)), paginas)
    except ValueError:
        pagina = 1
    inicio = (pagina - 1) * POR_PAGINA
    itens = qs.select_related('user', 'user__subscription__plan').order_by('-created_at')[inicio:inicio + POR_PAGINA]
    return Response({
        'numeros': numeros, 'total': total, 'pagina': pagina, 'paginas': paginas,
        'resultados': [opiniao_dict(f, agora) for f in itens],
    })


def _uuid_ou_none(valor):
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


@api_view(['PATCH'])
@permission_classes([EAdministrador])
def opiniao(request, opiniao_id):
    f = UserFeedback.objects.select_related('user').filter(pk=opiniao_id).first()
    if f is None:
        return sv.erro('Não encontrámos esta opinião.', 'not_found', 404)
    d = request.data if isinstance(request.data, dict) else {}
    erros = {}
    validos = dict(UserFeedback.ESTADOS)
    if 'estado' in d and d.get('estado') not in validos:
        erros['estado'] = ['Use por_rever, aprovada ou recusada.']
    if 'nota_interna' in d and (not isinstance(d.get('nota_interna'), (str, type(None)))
                                or len(d.get('nota_interna') or '') > NOTA_INTERNA_MAX):
        erros['nota_interna'] = [f'A nota interna tem no máximo {NOTA_INTERNA_MAX} caracteres.']
    if erros:
        return sv.erro_validacao(erros)
    alterado = {}
    if 'estado' in d and d['estado'] != f.estado:
        alterado['estado'] = [f.estado, d['estado']]
        if d['estado'] == UserFeedback.APROVADA:
            aprovar(f)
        else:
            f.estado = d['estado']
        f.is_reviewed = f.estado != UserFeedback.POR_REVER
    if 'nota_interna' in d and (d.get('nota_interna') or '') != f.admin_notes:
        alterado['nota_interna'] = True
        f.admin_notes = d.get('nota_interna') or ''
    if alterado:
        f.save()
        sv.registar(request, 'opiniao', f, alvo_tipo='opiniao', detalhes=alterado)
    corpo = opiniao_dict(f, timezone.now())
    corpo['no_site'] = no_site_qs().filter(pk=f.pk).exists()
    return Response(corpo)


# ---------------------------------------------------------------------------
# Testemunhos
# ---------------------------------------------------------------------------

def elegiveis():
    return (UserFeedback.objects.filter(estado=UserFeedback.APROVADA, allow_public=True)
            .exclude(comment='').select_related('user'))


def testemunho_dict(f):
    return {
        'id': str(f.id),
        'nome_curto': nome_curto(f.user.name),
        'area': area_de(f.user),
        'texto': f.comment,
        'nota': f.rating,
        'mostrar': f.mostrar,
        'ordem': f.ordem,
        # Conta suspensa ou apagada: o testemunho não aparece no site.
        'conta_activa': bool(f.user.is_active and not f.user.email.endswith('@apagado.invalid')),
    }


@api_view(['GET'])
@permission_classes([EAdministrador])
def testemunhos(request):
    return Response([testemunho_dict(f) for f in elegiveis().order_by('ordem', '-created_at')])


@api_view(['PATCH'])
@permission_classes([EAdministrador])
def testemunho(request, opiniao_id):
    f = elegiveis().filter(pk=opiniao_id).first()
    if f is None:
        return sv.erro('Não encontrámos este testemunho.', 'not_found', 404)
    mostrar = request.data.get('mostrar') if isinstance(request.data, dict) else None
    if not isinstance(mostrar, bool):
        return sv.erro_validacao({'mostrar': ['Use true ou false.']})
    if f.mostrar != mostrar:
        f.mostrar = mostrar
        f.save(update_fields=['mostrar', 'updated_at'])
        sv.registar(request, 'testemunho_mostrar', f, alvo_tipo='opiniao', detalhes={'mostrar': mostrar})
    return Response(testemunho_dict(f))


@api_view(['POST'])
@permission_classes([EAdministrador])
def ordem(request):
    ids = request.data.get('ids') if isinstance(request.data, dict) else None
    if not isinstance(ids, list) or not ids or len(ids) > 500:
        return sv.erro_validacao({'ids': ['Envie a lista de testemunhos pela ordem pretendida.']})
    uuids = [_uuid_ou_none(i) for i in ids]
    if any(u is None for u in uuids) or len(set(uuids)) != len(uuids):
        return sv.erro_validacao({'ids': ['Há identificadores inválidos ou repetidos.']})
    existentes = set(elegiveis().filter(pk__in=uuids).values_list('pk', flat=True))
    em_falta = [str(u) for u in uuids if u not in existentes]
    if em_falta:
        return sv.erro_validacao({'ids': [f'Não são testemunhos: {", ".join(em_falta)}.']})
    with transaction.atomic():
        for posicao, u in enumerate(uuids, start=1):
            UserFeedback.objects.filter(pk=u).update(ordem=posicao)
    from apps.site.conteudo import limpar_cache
    limpar_cache()  # update() não dispara os sinais que limpam a cache do site
    sv.registar(request, 'testemunhos_ordem', None, alvo_tipo='opiniao', detalhes={'ids': [str(u) for u in uuids]})
    return Response([testemunho_dict(f) for f in elegiveis().order_by('ordem', '-created_at')])
