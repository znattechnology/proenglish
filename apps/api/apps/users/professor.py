"""
Perfil público do professor.

- GET/PATCH /api/v1/teacher/perfil/      o próprio professor (nome, cidade, especialidade, experiência, sobre)
- DELETE    /api/v1/teacher/perfil/fotografia/   tira a fotografia (o envio passa por /teacher/perfil/fotografia/ POST)
- GET       /api/v1/professores/<id>/    público: o que os alunos vêem na página de cada curso

No perfil público os números (cursos publicados, alunos, "desde") contam só os cursos listados
(publicados e visíveis no catálogo). Ler o perfil nunca cria o PerfilProfessor (só o PATCH).
Quem não é professor, ou não tem cursos para mostrar, recebe o mesmo 404.
"""
from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.courses.api.teacher.cursos import PERMISSOES, _erro, _ids_alunos
from apps.courses.models import Course

from .models import PerfilProfessor

User = get_user_model()

MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro',
         'Outubro', 'Novembro', 'Dezembro']
LIMITES = {'nome': (2, 120), 'cidade': (0, 80), 'especialidade': (0, 120), 'experiencia': (0, 160), 'sobre': (0, 800)}


def iniciais(nome):
    partes = [p for p in (nome or '').split() if p]
    return ''.join(p[0].upper() for p in partes[:2]) or '?'


def _publicados(user):
    return Course.objects.filter(teacher=user, status='Published').order_by('-updated_at')


def _visiveis(user):
    return _publicados(user).filter(visivel_catalogo=True)


def perfil_dict(user, publico=False):
    # Leitura: sem get_or_create (um GET anónimo não deve escrever na base de dados).
    perfil = PerfilProfessor.objects.filter(user=user).first() or PerfilProfessor(user=user)
    cursos = list(_visiveis(user) if publico else _publicados(user))
    video = [c.id for c in cursos if c.course_type != 'practice']
    pratica = [c.id for c in cursos if c.course_type == 'practice']
    primeiro = min((c.aprovado_em or c.created_at for c in cursos), default=None)
    dados = {
        'id': str(user.id),
        'nome': user.name,
        'iniciais': iniciais(user.name),
        'fotografia': user.avatar or None,
        'cidade': perfil.cidade,
        'especialidade': perfil.especialidade,
        'experiencia': perfil.experiencia,
        'sobre': perfil.sobre,
        'desde': f'{MESES[primeiro.month - 1]} de {primeiro.year}' if primeiro else None,
        'cursos_publicados': len(cursos),
        'alunos': len(_ids_alunos(video, pratica)) if cursos else 0,
    }
    if publico:
        from apps.courses.ciclo import area_pt, nivel_pt
        dados['cursos'] = [
            {'id': str(c.id), 'titulo': c.title, 'tipo': 'pratica' if c.course_type == 'practice' else 'video',
             'area': area_pt(c.category), 'nivel': nivel_pt(c.level), 'imagem': c.image or None}
            for c in cursos
        ]
    return dados


@api_view(['GET', 'PATCH'])
@permission_classes(PERMISSOES)
def meu_perfil(request):
    user = request.user
    if request.method == 'GET':
        return Response(perfil_dict(user))

    dados = request.data if isinstance(request.data, dict) else {}
    erros, valores = {}, {}
    for campo, (minimo, maximo) in LIMITES.items():
        if campo not in dados:
            continue
        v = dados[campo]
        if not isinstance(v, str):
            erros[campo] = ['Escreva um texto.']
            continue
        v = ' '.join(v.split()) if campo != 'sobre' else v.strip()
        if len(v) < minimo:
            erros[campo] = ['Escreva o seu nome completo.' if campo == 'nome' else 'Campo obrigatório.']
        elif len(v) > maximo:
            erros[campo] = [f'No máximo {maximo} caracteres.']
        else:
            valores[campo] = v
    if erros:
        return _erro(next(iter(erros.values()))[0], 'dados_invalidos', details=erros)

    perfil, _ = PerfilProfessor.objects.get_or_create(user=user)
    if 'nome' in valores:
        user.name = valores.pop('nome')
        user.save(update_fields=['name', 'updated_at'])
    for campo, v in valores.items():
        setattr(perfil, campo, v)
    if valores:
        perfil.save()
    return Response(perfil_dict(user))


@api_view(['DELETE'])
@permission_classes(PERMISSOES)
def tirar_fotografia(request):
    from apps.courses.api.teacher.envios import apagar_ficheiro_local
    anterior = request.user.avatar
    request.user.avatar = None
    request.user.save(update_fields=['avatar', 'updated_at'])
    if anterior:
        apagar_ficheiro_local(anterior)
    return Response(perfil_dict(request.user))


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def perfil_publico(request, user_id):
    user = User.objects.filter(id=user_id, role='teacher', is_active=True).first()
    if user is None or not _visiveis(user).exists():
        return _erro('Professor não encontrado.', 'nao_encontrado', 404)
    return Response(perfil_dict(user, publico=True))
