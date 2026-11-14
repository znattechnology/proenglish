"""
Administração de utilizadores (/api/v1/admin/...).

- GET   painel/
- GET   utilizadores/?q=&papel=&plano=&estado=&pagina=
- GET   utilizadores/<id>/      PATCH utilizadores/<id>/      DELETE utilizadores/<id>/ (superutilizador)
- POST  utilizadores/<id>/suspender/ | reactivar/ | terminar-sessoes/ | obrigar-mudar-senha/
- POST  utilizadores/email/

Todas exigem EAdministrador. Cada alteração fica em RegistoAdmin.
"""
import logging
import math
import threading
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.permissions import EAdministrador

from ..models import (PROVINCIAS, ConviteProfessor, PerfilProfessor, SuspensaoConta, User, UserFeedback)
from . import servicos as sv

logger = logging.getLogger(__name__)

POR_PAGINA = 25
PROVINCIAS_DICT = dict(PROVINCIAS)
ESTADOS = ('activo', 'email_por_verificar', 'suspenso')
ESTADO_PAGAMENTO = {'pago': 'pago', 'pendente': 'pendente', 'recusado': 'falhou', 'expirado': 'expirado',
                    'cancelado': 'cancelado'}


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def utilizadores_base():
    """Todas as contas, menos as que o próprio utilizador apagou (anonimizadas)."""
    return User.objects.exclude(email__endswith='@apagado.invalid')


def q_plano_pago(agora, tipos=sv.PLANOS_PAGOS):
    return (Q(subscription__plan__plan_type__in=list(tipos)) & Q(subscription__expires_at__gt=agora)
            & ~Q(subscription__status='EXPIRED'))


def filtrar_plano(qs, plano, agora):
    qs = qs.filter(role='student')
    if plano == 'FREE':
        ids_pagos = User.objects.filter(q_plano_pago(agora)).values('id')
        return qs.exclude(id__in=ids_pagos)
    return qs.filter(q_plano_pago(agora, [plano]))


def filtrar_estado(qs, estado):
    if estado == 'suspenso':
        return qs.filter(is_active=False)
    if estado == 'email_por_verificar':
        return qs.filter(is_active=True, email_verified=False)
    return qs.filter(is_active=True, email_verified=True)


def convites_pendentes(agora):
    return ConviteProfessor.objects.filter(estado=ConviteProfessor.PENDENTE, expira_em__gt=agora)


def numeros_utilizadores(agora=None):
    agora = agora or timezone.now()
    base = utilizadores_base()
    por_verificar = base.filter(is_active=True, email_verified=False)
    return {
        'total': base.count(),
        'novos_mes': base.filter(date_joined__gte=sv.inicio_mes_luanda(agora)).count(),
        'estudantes': base.filter(role='student').count(),
        'pagantes': base.filter(role='student').filter(q_plano_pago(agora)).count(),
        'professores': base.filter(role='teacher').count(),
        'professores_por_activar': convites_pendentes(agora).count(),
        'email_por_verificar': por_verificar.count(),
        'email_por_verificar_3d': por_verificar.filter(date_joined__lte=agora - timedelta(days=3)).count(),
    }


def estado_de(user):
    if not user.is_active:
        return 'suspenso'
    return 'activo' if user.email_verified else 'email_por_verificar'


def iniciais(nome):
    partes = [p for p in (nome or '').split() if p]
    return ''.join(p[0].upper() for p in partes[:2]) or '?'


def ultima_entrada(user):
    datas = [d for d in (user.last_login, user.last_login_at) if d]
    return max(datas) if datas else None


def _inteiro(valor, defeito=1):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return defeito


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([EAdministrador])
def painel(request):
    # Números de subscrições/pagamentos: as mesmas definições do resumo de Subscrições
    # (apps/pagamentos/admin_api/metricas.py).
    from apps.pagamentos.admin_api import metricas as mt

    agora = timezone.now()
    mes = sv.inicio_mes_luanda(agora)
    n = numeros_utilizadores(agora)
    base = utilizadores_base()

    receita = mt.receita(mes, agora + timedelta(seconds=1))
    planos = mt.planos_em_vigor(agora)
    falhas = mt.falhados_em_aberto(agora)
    assinantes_pagos = len(mt.pagantes(planos))
    terminam = len(mt.terminam_em_breve(agora, planos, falhas))
    falhados_semana = len(mt.falhados_semana(agora, falhas))

    try:
        from apps.courses.models import Course
        em_revisao = Course.objects.filter(status='InReview').count()
    except Exception:
        em_revisao = 0

    por_plano = mt.por_plano(planos)

    recentes = [
        {'id': str(u.id), 'nome': u.name, 'email': u.email, 'papel': u.role, 'criado_em': sv.iso(u.date_joined)}
        for u in base.order_by('-date_joined')[:6]
    ]

    return Response({
        'numeros': {
            'utilizadores': n['total'],
            'novos_mes': n['novos_mes'],
            'estudantes': n['estudantes'],
            'pagantes': n['pagantes'],
            'professores': n['professores'],
            'professores_por_activar': n['professores_por_activar'],
            'email_por_verificar': n['email_por_verificar'],
            'email_por_verificar_3d': n['email_por_verificar_3d'],
            'assinantes_pagos': assinantes_pagos,
            'receita_mes_kz': int(receita),
        },
        'atencao': {
            'pagamentos_falhados_semana': falhados_semana,
            'terminam_3_dias': terminam,
            'opinioes_por_rever': UserFeedback.objects.filter(estado=UserFeedback.POR_REVER).count(),
            'cursos_em_revisao': em_revisao,
        },
        'por_plano': por_plano,
        'recentes': recentes,
    })


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([EAdministrador])
def lista(request):
    agora = timezone.now()
    p = request.query_params
    qs = utilizadores_base()
    erros = {}

    q = (p.get('q') or '').strip()
    if q:
        filtro = Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
        digitos = ''.join(c for c in q if c.isdigit())
        if len(digitos) >= 6:
            filtro |= Q(phone__icontains=digitos[-9:])
        qs = qs.filter(filtro)
    papel = p.get('papel') or ''
    if papel:
        if papel not in sv.PAPEIS:
            erros['papel'] = ['Use student, teacher ou admin.']
        else:
            qs = qs.filter(role=papel)
    plano = p.get('plano') or ''
    if plano:
        if plano not in sv.NOME_PLANO:
            erros['plano'] = ['Use FREE, PREMIUM ou PREMIUM_PLUS.']
        else:
            qs = filtrar_plano(qs, plano, agora)
    estado = p.get('estado') or ''
    if estado:
        if estado not in ESTADOS:
            erros['estado'] = ['Use activo, email_por_verificar ou suspenso.']
        else:
            qs = filtrar_estado(qs, estado)
    if erros:
        return sv.erro_validacao(erros)

    total = qs.count()
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(_inteiro(p.get('pagina')), paginas)
    inicio = (pagina - 1) * POR_PAGINA
    utilizadores = list(qs.select_related('subscription__plan').order_by('-date_joined', 'id')[inicio:inicio + POR_PAGINA])

    resultados = []
    for u in utilizadores:
        plano_nome = None
        if u.role == 'student':
            sub = getattr(u, 'subscription', None)
            plano_nome = sv.NOME_PLANO[sv.plano_em_vigor(sub, agora)]
        resultados.append({
            'id': str(u.id), 'nome': u.name, 'email': u.email, 'iniciais': iniciais(u.name),
            'papel': u.role, 'plano': plano_nome, 'estado': estado_de(u),
            'ultima_entrada': sv.iso(ultima_entrada(u)),
        })

    return Response({
        'numeros': numeros_utilizadores(agora),
        'total': total,
        'pagina': pagina,
        'paginas': paginas,
        'resultados': resultados,
    })


# ---------------------------------------------------------------------------
# Detalhe
# ---------------------------------------------------------------------------

def _fmt_kz(v):
    return f'{int(v):,}'.replace(',', ' ') + ' Kz'


def actividade(user, limite=15):
    """Últimos acontecimentos com significado, a partir dos dados que já existem."""
    eventos = []
    if user.date_joined:
        eventos.append((user.date_joined, 'Criou a conta.'))
    entrada = ultima_entrada(user)
    if entrada:
        eventos.append((entrada, 'Entrou na plataforma.'))
    try:
        from apps.practice.models import LessonCompletion, VapiSession
        for lc in LessonCompletion.objects.filter(user=user).select_related('lesson').order_by('-last_completed_at')[:limite]:
            eventos.append((lc.last_completed_at, f'Concluiu a lição «{lc.lesson.title}».'))
        for s in (VapiSession.objects.filter(user=user, status__in=VapiSession.STATUS_TERMINADAS)
                  .order_by('-created_at')[:limite]):
            minutos = round((s.duration_seconds or 0) / 60) or s.duration_minutes or 0
            quando = s.ended_at or s.started_at or getattr(s, 'created_at', None)
            if quando:
                txt = 'minuto' if minutos == 1 else 'minutos'
                eventos.append((quando, f'Conversou {minutos} {txt} com o tutor.'))
    except Exception:
        logger.exception('Actividade de prática indisponível (user=%s)', user.pk)
    try:
        from apps.courses.models import CourseCertificate, CourseEnrollment
        for e in CourseEnrollment.objects.filter(user=user).select_related('course').order_by('-enrollment_date')[:limite]:
            eventos.append((e.enrollment_date, f'Inscreveu-se no curso «{e.course.title}».'))
        for c in CourseCertificate.objects.filter(user=user).select_related('course').order_by('-created_at')[:limite]:
            eventos.append((c.created_at, f'Concluiu o curso «{c.course.title}» e recebeu o certificado.'))
    except Exception:
        logger.exception('Actividade de cursos indisponível (user=%s)', user.pk)
    from apps.pagamentos.models import Pagamento
    for pg in Pagamento.objects.filter(user=user).select_related('plan').order_by('-created_at')[:limite]:
        desc = f'{_fmt_kz(pg.total_kz)} ({pg.descricao})'
        if pg.estado == Pagamento.PAGO:
            eventos.append((pg.pago_em or pg.created_at, f'Pagou {desc}.'))
        elif pg.estado == Pagamento.RECUSADO:
            eventos.append((pg.created_at, f'O pagamento de {desc} falhou.'))
        elif pg.estado == Pagamento.PENDENTE:
            eventos.append((pg.created_at, f'Iniciou o pagamento de {desc}.'))
        elif pg.estado == Pagamento.EXPIRADO:
            eventos.append((pg.created_at, f'O pagamento de {desc} expirou sem ser confirmado.'))
        else:
            eventos.append((pg.created_at, f'Cancelou o pagamento de {desc}.'))
    for s in SuspensaoConta.objects.filter(user=user)[:limite]:
        eventos.append((s.desde, f'A conta foi suspensa ({s.get_motivo_display().lower()}).'))
        if s.terminada_em:
            eventos.append((s.terminada_em, 'A conta foi reactivada.'))
    eventos = [e for e in eventos if e[0]]
    eventos.sort(key=lambda e: e[0], reverse=True)
    return [{'quando': sv.iso(q), 'texto': t} for q, t in eventos[:limite]]


def _plano_detalhe(user, agora):
    if user.role != 'student':
        return None
    sub = sv.subscricao(user)
    tipo = sv.plano_em_vigor(sub, agora)
    if tipo == 'FREE':
        return {'tipo': 'FREE', 'nome': sv.NOME_PLANO['FREE'], 'periodo': None, 'renova_a': None, 'termina_a': None}
    from apps.pagamentos.models import Pagamento
    ultimo = (Pagamento.objects.filter(user=user, estado=Pagamento.PAGO, plan__plan_type=tipo)
              .order_by('-pago_em').first())
    periodo = ultimo.periodo if ultimo else None
    # Multicaixa Express não renova sozinho: "renova_a" só quando já há um pagamento pendente.
    pendente = Pagamento.objects.filter(user=user, estado=Pagamento.PENDENTE, expira_em__gt=agora).exists()
    cancelado = sub.status == 'CANCELED'
    return {
        'tipo': tipo,
        'nome': sv.NOME_PLANO[tipo],
        'periodo': periodo,
        'renova_a': sv.iso(sub.expires_at) if (pendente and not cancelado) else None,
        'termina_a': None if (pendente and not cancelado) else sv.iso(sub.expires_at),
    }


def detalhe_dict(user, actor=None):
    agora = timezone.now()
    prefs = user.preferences or {}
    from ..views import AREAS_PT
    suspensao = sv.suspensao_activa(user) if not user.is_active else None

    numeros = {'cursos': 0, 'concluidos': 0, 'pontos': 0, 'dias_seguidos': 0}
    try:
        from apps.courses.models import CourseCertificate, CourseEnrollment
        numeros['cursos'] = CourseEnrollment.objects.filter(user=user).count()
        numeros['concluidos'] = CourseCertificate.objects.filter(user=user).count()
    except Exception:
        pass
    try:
        from apps.practice.models import UserProgress, UserStreak
        numeros['pontos'] = UserProgress.objects.filter(user=user).values_list('points', flat=True).first() or 0
        numeros['dias_seguidos'] = UserStreak.objects.filter(user=user).values_list('current_streak', flat=True).first() or 0
    except Exception:
        pass

    from apps.pagamentos.models import Pagamento
    pagamentos = [{
        'id': str(pg.id),
        'data': sv.iso(pg.pago_em or pg.created_at),
        'descricao': pg.descricao,
        'valor_kz': pg.total_kz,
        'estado': ESTADO_PAGAMENTO.get(pg.estado, pg.estado),
        'numero_recibo': pg.numero_recibo,
    } for pg in Pagamento.objects.filter(user=user).select_related('plan').order_by('-created_at')[:30]]

    professor = None
    if user.role == 'teacher':
        perfil = PerfilProfessor.objects.filter(user=user).first()
        publicados, alunos = 0, 0
        try:
            from apps.courses.models import Course
            from apps.courses.api.teacher.cursos import _ids_alunos
            cursos = list(Course.objects.filter(teacher=user, status='Published').values_list('id', 'course_type'))
            publicados = len(cursos)
            if cursos:
                alunos = len(_ids_alunos([c for c, t in cursos if t != 'practice'],
                                         [c for c, t in cursos if t == 'practice']))
        except Exception:
            logger.exception('Números do professor indisponíveis (user=%s)', user.pk)
        professor = {'cursos_publicados': publicados, 'alunos': alunos,
                     'publica_sem_revisao': bool(perfil and perfil.publica_sem_revisao)}

    cidade = prefs.get('cidade') or ''
    if not cidade and user.role == 'teacher':
        cidade = PerfilProfessor.objects.filter(user=user).values_list('cidade', flat=True).first() or ''

    return {
        'utilizador': {
            'id': str(user.id),
            'nome': user.name,
            'email': user.email,
            'telefone': user.phone or None,
            'papel': user.role,
            'provincia': user.provincia or None,
            'provincia_nome': PROVINCIAS_DICT.get(user.provincia) if user.provincia else None,
            'profissao': AREAS_PT.get(prefs.get('area'), prefs.get('area')) or None,
            'cidade': cidade or None,
            'iniciais': iniciais(user.name),
            'avatar': user.avatar or None,
            'plano': _plano_detalhe(user, agora),
            'estado': estado_de(user),
            'suspensao': {
                'motivo': suspensao.motivo,
                'motivo_nome': suspensao.get_motivo_display(),
                'nota': suspensao.nota,
                'desde': sv.iso(suspensao.desde),
                'por': suspensao.por.name if suspensao.por else None,
            } if suspensao else None,
            'email_verificado': user.email_verified,
            # Email novo pedido pela administração, à espera de confirmação (o email acima
            # continua a ser o da conta até lá).
            'email_pendente': user.email_pendente or None,
            'verificado_em': _verificado_em(user),
            'entra_com_google': bool(user.google_id),
            'tem_senha': user.has_usable_password(),
            'deve_mudar_senha': user.deve_mudar_senha,
            'superutilizador': user.is_superuser,
            # O administrador que pede pode editar/suspender/terminar sessões desta conta.
            'pode_gerir': sv.pode_gerir(actor, user) if actor is not None else False,
            'criado_em': sv.iso(user.date_joined),
            'ultima_entrada': sv.iso(ultima_entrada(user)),
        },
        'numeros': numeros,
        'actividade': actividade(user),
        'pagamentos': pagamentos,
        'professor': professor,
    }


def _verificado_em(user):
    if not user.email_verified:
        return None
    from ..models import EmailVerification
    v = (EmailVerification.objects.filter(user=user, email__iexact=user.email, is_used=True,
                                          finalidade=EmailVerification.FINALIDADE_VERIFICAR)
         .order_by('-created_at').first())
    return sv.iso(v.updated_at if v else None)


def _obter(user_id):
    return utilizadores_base().filter(pk=user_id).first()


NAO_ENCONTRADO = ('Não encontrámos este utilizador.', 'not_found', 404)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([EAdministrador])
def detalhe(request, user_id):
    user = _obter(user_id)
    if user is None:
        return sv.erro(*NAO_ENCONTRADO)
    if request.method == 'GET':
        return Response(detalhe_dict(user, request.user))
    if request.method == 'DELETE':
        return sv.apagar_definitivamente(request, user)
    return _actualizar(request, user)


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------

CAMPOS_PATCH = ('nome', 'email', 'telefone', 'papel', 'plano', 'publica_sem_revisao', 'provincia')


def _validar_patch(request, user, dados):
    erros = {}
    limpos = {}
    actor = request.user
    if 'nome' in dados:
        nome = (dados.get('nome') or '').strip() if isinstance(dados.get('nome'), (str, type(None))) else ''
        if len(nome) < 2 or len(nome) > 255:
            erros['nome'] = ['Escreva o nome (2 a 255 caracteres).']
        else:
            limpos['nome'] = nome
    if 'email' in dados:
        email = (dados.get('email') or '').strip().lower() if isinstance(dados.get('email'), (str, type(None))) else ''
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            erros['email'] = ['Escreva um email válido.']
        else:
            if email != user.email.lower():
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    erros['email'] = ['Já existe outra conta com este email.']
                else:
                    limpos['email'] = email
    if 'telefone' in dados:
        tel = dados.get('telefone')
        if tel in (None, ''):
            limpos['telefone'] = None
        elif not isinstance(tel, str):
            erros['telefone'] = ['Número de telemóvel inválido.']
        else:
            from rest_framework import serializers as drf_serializers
            from ..serializers import UserProfileSerializer
            try:
                limpos['telefone'] = UserProfileSerializer().validate_phone(tel.strip())
            except drf_serializers.ValidationError as e:
                erros['telefone'] = [str(x) for x in (e.detail if isinstance(e.detail, list) else [e.detail])]
    if 'papel' in dados:
        papel = dados.get('papel')
        if papel not in sv.PAPEIS:
            erros['papel'] = ['Use student, teacher ou admin.']
        elif papel != user.role:
            limpos['papel'] = papel
    if 'plano' in dados:
        plano = dados.get('plano')
        papel_final = limpos.get('papel', user.role)
        if plano not in sv.NOME_PLANO:
            erros['plano'] = ['Use FREE, PREMIUM ou PREMIUM_PLUS.']
        elif papel_final != 'student':
            erros['plano'] = ['Só os estudantes têm plano.']
        else:
            limpos['plano'] = plano
    if 'publica_sem_revisao' in dados:
        v = dados.get('publica_sem_revisao')
        if not isinstance(v, bool):
            erros['publica_sem_revisao'] = ['Use true ou false.']
        elif limpos.get('papel', user.role) != 'teacher':
            erros['publica_sem_revisao'] = ['Só se aplica a professores.']
        else:
            limpos['publica_sem_revisao'] = v
    if 'provincia' in dados:
        prov = dados.get('provincia')
        if prov in (None, ''):
            limpos['provincia'] = ''
        elif prov not in PROVINCIAS_DICT:
            erros['provincia'] = ['Província desconhecida. Veja a lista em /api/v1/users/provincias/.']
        else:
            limpos['provincia'] = prov
    return limpos, erros


def _actualizar(request, user):
    dados = request.data if isinstance(request.data, dict) else {}
    desconhecidos = sorted(set(dados) - set(CAMPOS_PATCH))
    if desconhecidos:
        return sv.erro_validacao({c: ['Este campo não se pode alterar aqui.'] for c in desconhecidos})
    actor = request.user

    # Conta de outro administrador/superutilizador: qualquer alteração só por um superutilizador.
    recusa = sv.recusa_editar(actor, user)
    if recusa:
        return recusa

    # Papel: nunca o próprio; de/para administrador só um superutilizador.
    if 'papel' in dados and dados.get('papel') != user.role:
        if user.pk == actor.pk:
            return sv.erro('Não pode mudar o seu próprio papel.', 'propria_conta', 403)
        if (user.role == 'admin' or dados.get('papel') == 'admin' or user.is_superuser) and not actor.is_superuser:
            return sv.erro('Só um superutilizador pode dar ou tirar o papel de administrador.',
                           'alvo_administrador', 403)

    limpos, erros = _validar_patch(request, user, dados)
    if erros:
        return sv.erro_validacao(erros)
    if 'plano' in limpos and not user.is_active:
        return sv.erro('A conta está suspensa: o plano está em pausa. Reactive a conta antes de mudar o plano.',
                       'conta_suspensa', 409)

    mensagens = []
    with transaction.atomic():
        alterados = {}
        if 'nome' in limpos and limpos['nome'] != user.name:
            alterados['nome'] = [user.name, limpos['nome']]
            user.name = limpos['nome']
        if 'telefone' in limpos and limpos['telefone'] != user.phone:
            alterados['telefone'] = [user.phone, limpos['telefone']]
            user.phone = limpos['telefone']
        if 'provincia' in limpos and limpos['provincia'] != user.provincia:
            alterados['provincia'] = [user.provincia or None, limpos['provincia'] or None]
            user.provincia = limpos['provincia']
        novo_email = limpos.get('email')
        if novo_email:
            # Não muda já: fica pendente até ser confirmado (ver sv.pedir_mudanca_email).
            alterados['email_pendente'] = [user.email_pendente, novo_email]
        novo_papel = limpos.get('papel')
        if novo_papel:
            alterados['papel'] = [user.role, novo_papel]
            user.role = novo_papel
        if alterados:
            user.save()
            sv.registar(request, 'editar_utilizador', user, detalhes={'alterado': alterados})
        if novo_papel:
            sv.terminar_todas_sessoes(user)
            if novo_papel == 'teacher':
                sv.garantir_perfil_professor(user)
            mensagens.append('O papel mudou: as sessões abertas foram terminadas.')
        if 'publica_sem_revisao' in limpos:
            perfil = sv.garantir_perfil_professor(user)
            if perfil.publica_sem_revisao != limpos['publica_sem_revisao']:
                perfil.publica_sem_revisao = limpos['publica_sem_revisao']
                perfil.save(update_fields=['publica_sem_revisao', 'updated_at'])
                sv.registar(request, 'publica_sem_revisao', user,
                            detalhes={'publica_sem_revisao': perfil.publica_sem_revisao})
        if 'plano' in limpos:
            mudou, det = sv.atribuir_plano(user, limpos['plano'], actor, request)
            if mudou:
                sv.registar(request, 'atribuir_plano', user, detalhes=det)
                mensagens.append(f'Plano mudado para {sv.NOME_PLANO[limpos["plano"]]}, sem pagamento.')

    if novo_email:
        # Fora da transacção: o email sai mesmo que algo depois falhe, e não prende a BD.
        enviado, _ = sv.pedir_mudanca_email(user, novo_email, request)
        mensagens.append(
            f'Enviámos um código de confirmação para {novo_email}. O email da conta só muda quando '
            f'a pessoa o confirmar; até lá continua a entrar com {user.email}.' if enviado
            else f'Não conseguimos enviar o código de confirmação para {novo_email}. O email da conta '
                 f'não mudou; tente outra vez.')

    corpo = detalhe_dict(user, request.user)
    corpo['message'] = ' '.join(mensagens) or 'Utilizador actualizado.'
    return Response(corpo)


# ---------------------------------------------------------------------------
# Acções
# ---------------------------------------------------------------------------

MOTIVOS = dict(SuspensaoConta.MOTIVOS)


def _bool(v):
    return v is True or (isinstance(v, str) and v.strip().lower() in ('true', '1', 'sim'))


@api_view(['POST'])
@permission_classes([EAdministrador])
def suspender(request, user_id):
    user = _obter(user_id)
    if user is None:
        return sv.erro(*NAO_ENCONTRADO)
    recusa = sv.recusa_gerir(request.user, user)
    if recusa:
        return recusa
    motivo = request.data.get('motivo')
    nota = request.data.get('nota') or ''
    erros = {}
    if motivo not in MOTIVOS:
        erros['motivo'] = [f'Use um destes: {", ".join(MOTIVOS)}.']
    if not isinstance(nota, str) or len(nota) > 2000:
        erros['nota'] = ['A nota tem no máximo 2000 caracteres.']
    if erros:
        return sv.erro_validacao(erros)
    if not user.is_active:
        return sv.erro('Esta conta já está suspensa.', 'ja_suspensa', 409)
    sv.suspender(user, request.user, motivo, nota.strip(), _bool(request.data.get('avisar')), request)
    corpo = detalhe_dict(user, request.user)
    corpo['message'] = 'Conta suspensa. As sessões abertas foram terminadas.'
    return Response(corpo)


@api_view(['POST'])
@permission_classes([EAdministrador])
def reactivar(request, user_id):
    user = _obter(user_id)
    if user is None:
        return sv.erro(*NAO_ENCONTRADO)
    if user.is_active:
        return sv.erro('Esta conta não está suspensa.', 'nao_suspensa', 409)
    if sv.e_admin_alvo(user) and not request.user.is_superuser:
        return sv.erro('Só um superutilizador pode fazer isto a outro administrador.', 'alvo_administrador', 403)
    sv.reactivar(user, request.user, request)
    corpo = detalhe_dict(user, request.user)
    corpo['message'] = 'Conta reactivada.'
    return Response(corpo)


@api_view(['POST'])
@permission_classes([EAdministrador])
def terminar_sessoes(request, user_id):
    user = _obter(user_id)
    if user is None:
        return sv.erro(*NAO_ENCONTRADO)
    recusa = sv.recusa_gerir(request.user, user)
    if recusa:
        return recusa
    n = sv.terminar_todas_sessoes(user)
    sv.registar(request, 'terminar_sessoes', user, detalhes={'sessoes': n})
    corpo = detalhe_dict(user, request.user)
    corpo['message'] = 'As sessões abertas foram terminadas.'
    corpo['sessoes_terminadas'] = n
    return Response(corpo)


@api_view(['POST'])
@permission_classes([EAdministrador])
def obrigar_mudar_senha(request, user_id):
    user = _obter(user_id)
    if user is None:
        return sv.erro(*NAO_ENCONTRADO)
    recusa = sv.recusa_gerir(request.user, user)
    if recusa:
        return recusa
    user.deve_mudar_senha = True
    user.save(update_fields=['deve_mudar_senha'])
    sv.registar(request, 'obrigar_mudar_senha', user)
    corpo = detalhe_dict(user, request.user)
    corpo['message'] = 'Na próxima acção, a pessoa terá de mudar a palavra-passe.'
    return Response(corpo)


# ---------------------------------------------------------------------------
# Email a vários utilizadores
# ---------------------------------------------------------------------------

class EmailAdminThrottle(UserRateThrottle):
    scope = 'admin_email'
    rate = '10/hour'


MAX_IDS = 200


@api_view(['POST'])
@permission_classes([EAdministrador])
@throttle_classes([EmailAdminThrottle])
def email_varios(request):
    import uuid as _uuid
    ids = request.data.get('ids')
    assunto = request.data.get('assunto')
    mensagem = request.data.get('mensagem')
    erros = {}
    if not isinstance(ids, list) or not ids:
        erros['ids'] = ['Escolha pelo menos um utilizador.']
    elif len(ids) > MAX_IDS:
        erros['ids'] = [f'No máximo {MAX_IDS} utilizadores de cada vez.']
    else:
        try:
            ids = list({str(_uuid.UUID(str(i))) for i in ids})
        except (ValueError, TypeError, AttributeError):
            erros['ids'] = ['Há identificadores inválidos.']
    if not isinstance(assunto, str) or not (1 <= len(assunto.strip()) <= 150):
        erros['assunto'] = ['Escreva o assunto (até 150 caracteres).']
    elif '\r' in assunto or '\n' in assunto:
        erros['assunto'] = ['O assunto tem de ser uma só linha (sem mudanças de linha).']
    if not isinstance(mensagem, str) or not (1 <= len(mensagem.strip()) <= 5000):
        erros['mensagem'] = ['Escreva a mensagem (até 5000 caracteres).']
    if erros:
        return sv.erro_validacao(erros)

    assunto = assunto.strip()
    paragrafos = [p.strip() for p in mensagem.strip().split('\n\n') if p.strip()]
    utilizadores = list(utilizadores_base().filter(id__in=ids))
    nao_encontrados = len(ids) - len(utilizadores)
    registo = sv.registar(request, 'email_varios', None, alvo_tipo='utilizadores', detalhes={
        'ids': ids, 'assunto': assunto, 'a_enviar': len(utilizadores), 'nao_encontrados': nao_encontrados})
    lancar_envio(lambda: _enviar_varios(registo.pk, utilizadores, assunto, paragrafos, nao_encontrados))
    n = len(utilizadores)
    pessoas = 'pessoa' if n == 1 else 'pessoas'
    mensagem_resposta = f'A enviar o email a {n} {pessoas}. Pode continuar a trabalhar.'
    if nao_encontrados:
        mensagem_resposta += f' {nao_encontrados} não foram encontrados.'
    # `enviados` mantém-se por compatibilidade: são os emails postos a enviar (o envio corre em
    # segundo plano; o resultado final fica no RegistoAdmin desta acção).
    return Response({'a_enviar': n, 'enviados': n, 'falhados': nao_encontrados,
                     'em_segundo_plano': True, 'message': mensagem_resposta}, status=202)


def _enviar_varios(registo_id, utilizadores, assunto, paragrafos, nao_encontrados):
    """Envia os emails um a um (corre fora do pedido) e guarda o resultado no RegistoAdmin."""
    from django.db import connection
    from ..models import RegistoAdmin
    enviados, falhados = 0, 0
    try:
        for u in utilizadores:
            if sv.enviar_email(u, assunto, 'emails/admin_mensagem.html', {'paragrafos': paragrafos}):
                enviados += 1
            else:
                falhados += 1
        reg = RegistoAdmin.objects.filter(pk=registo_id).first()
        if reg is not None:
            reg.detalhes = {**(reg.detalhes or {}), 'enviados': enviados, 'falhados': falhados + nao_encontrados}
            reg.save(update_fields=['detalhes'])
        logger.info('Email a vários: %s enviados, %s falhados (registo %s)', enviados, falhados, registo_id)
    except Exception:
        logger.exception('Falha no envio do email a vários (registo %s)', registo_id)
    finally:
        if threading.current_thread() is not threading.main_thread():
            connection.close()  # a ligação à BD desta thread


def lancar_envio(funcao):
    """
    Corre `funcao` numa thread à parte, para o pedido não esperar por até 200 envios SMTP
    (cada um pode levar segundos). Sem fila de tarefas: se o processo reiniciar a meio, os
    envios que faltam perdem-se (o RegistoAdmin fica sem "enviados"). Os testes substituem
    esta função para correr o envio de imediato.
    """
    t = threading.Thread(target=funcao, name='admin-email-varios', daemon=True)
    t.start()
    return t
