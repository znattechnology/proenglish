"""Ajudas comuns às vistas do professor em apps/practice/professor/ (situações, conquistas, competições)."""
import re
import uuid

from rest_framework.exceptions import NotFound

from apps.courses import ciclo
from apps.courses.api.teacher.cursos import PERMISSOES, _erro  # noqa: F401 (reexportados)
from apps.courses.models import Course

MENSAGEM_PLATAFORMA = 'Este item é da plataforma: só o administrador o pode alterar.'


def cursos_do_professor(user):
    return list(Course.objects.filter(teacher=user).only('id', 'title').order_by('title'))


def curso_api(curso):
    return {'id': str(curso.id), 'titulo': curso.title} if curso is not None else None


def ler_curso(request, valor, erros, campo='curso'):
    """Curso do corpo do pedido: None (sem curso) ou um curso do professor. Guarda o erro em `erros`."""
    if valor in (None, ''):
        return None
    try:
        cid = uuid.UUID(str(valor))
    except (TypeError, ValueError):
        erros[campo] = 'Curso inválido.'
        return None
    curso = Course.objects.filter(id=cid).first()
    if curso is None or not ciclo.e_dono_ou_staff(request.user, curso):
        erros[campo] = 'Escolha um dos seus cursos.'
        return None
    return curso


def obter_visivel(request, qs, pk, mensagem):
    """Item do professor ou da plataforma (criado_por vazio); de outro professor: 404."""
    obj = qs.filter(pk=pk).first()
    if obj is None:
        raise NotFound(mensagem)
    if obj.criado_por_id not in (None, request.user.id) and not ciclo.e_staff(request.user):
        raise NotFound(mensagem)
    return obj


def erro_sem_permissao(request, obj):
    """Resposta 403 se o pedido não pode alterar o item; None se pode."""
    if obj.criado_por_id == request.user.id:
        return None
    if ciclo.e_staff(request.user):
        return None
    return _erro(MENSAGEM_PLATAFORMA, 'so_administrador', 403)


def e_minha(request, obj):
    return obj.criado_por_id == request.user.id


def corpo(request):
    return request.data if isinstance(request.data, dict) else {}


def erro_validacao(erros):
    """400 com details = {campo: [mensagens]} (listas, como os outros erros de validação da API)."""
    primeiro = next(iter(erros.values()))
    if isinstance(primeiro, list):
        primeiro = primeiro[0]
    detalhes = {k: (v if isinstance(v, list) else [v]) for k, v in erros.items()}
    return _erro(primeiro, 'validation_error', 400, details=detalhes)


def texto(dados, campo, erros, minimo, maximo, rotulo, obrigatorio=True):
    valor = dados.get(campo)
    if valor is None:
        if obrigatorio:
            erros[campo] = f'Indique {rotulo}.'
        return None
    if not isinstance(valor, str):
        erros[campo] = f'{rotulo[0].upper()}{rotulo[1:]} tem de ser texto.'
        return None
    # Sem caracteres de controlo (o PostgreSQL recusa NUL; os outros não servem para nada aqui).
    valor = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', valor)
    valor = ' '.join(valor.split()) if '\n' not in valor else valor.strip()
    if len(valor) < minimo:
        erros[campo] = (f'Indique {rotulo}.' if not valor
                        else f'{rotulo[0].upper()}{rotulo[1:]} tem de ter pelo menos {minimo} caracteres.')
        return None
    if len(valor) > maximo:
        erros[campo] = f'{rotulo[0].upper()}{rotulo[1:]} pode ter no máximo {maximo} caracteres.'
        return None
    return valor


def inteiro(dados, campo, erros, minimo, maximo, mensagem):
    valor = dados.get(campo)
    if isinstance(valor, bool):
        erros[campo] = mensagem
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        erros[campo] = mensagem
        return None
    if str(valor).strip() not in (str(n),) and not isinstance(valor, int):
        erros[campo] = mensagem
        return None
    if n < minimo or n > maximo:
        erros[campo] = mensagem
        return None
    return n
