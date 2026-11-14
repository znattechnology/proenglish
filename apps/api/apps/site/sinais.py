"""
O site público junta ao conteúdo publicado partes vivas (planos, áreas com cursos, testemunhos,
números automáticos). Quando estas mudam, a cache tem de ir embora, sobretudo quando um aluno
retira a autorização do testemunho ou a conta é suspensa ou apagada.
"""
from django.db.models.signals import post_delete, post_save


def _limpar(**kwargs):
    from django.db import transaction

    from .conteudo import limpar_cache
    # Depois do commit: antes disso, uma leitura pública ainda veria (e guardaria) os dados antigos.
    transaction.on_commit(limpar_cache)


def ligar():
    from apps.courses.models import Course
    from apps.subscriptions.models import SubscriptionPlan
    from apps.users.models import User, UserFeedback

    for modelo in (SubscriptionPlan, UserFeedback, Course, User):
        post_save.connect(_limpar, sender=modelo, dispatch_uid=f'site_cache_{modelo.__name__}_save')
        post_delete.connect(_limpar, sender=modelo, dispatch_uid=f'site_cache_{modelo.__name__}_delete')
