"""
Plano Gratuito mais apertado, para empurrar para a assinatura:
2 lições novas por dia (era 3), 3 análises de pronúncia por IA (eram 5) e 3 minutos de conversa
com o tutor (eram 5, também nos primeiros dias). Só muda o valor que ainda estiver no antigo:
um valor que o administrador já mudou no painel fica como está.
"""
from django.db import migrations

MUDANCAS = (
    # campo, antigo, novo
    ('daily_lessons_limit', 3, 2),
    ('daily_ai_analyses_limit', 5, 3),
    ('daily_speaking_minutes', 5, 3),
    ('trial_speaking_minutes', 5, 3),
)


def apertar(apps, schema_editor):
    Plano = apps.get_model('subscriptions', 'SubscriptionPlan')
    for campo, antigo, novo in MUDANCAS:
        Plano.objects.filter(plan_type='FREE', **{campo: antigo}).update(**{campo: novo})


def desapertar(apps, schema_editor):
    Plano = apps.get_model('subscriptions', 'SubscriptionPlan')
    for campo, antigo, novo in MUDANCAS:
        Plano.objects.filter(plan_type='FREE', **{campo: novo}).update(**{campo: antigo})


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0013_pronuncia_detalhada'),
    ]

    operations = [
        migrations.RunPython(apertar, desapertar),
    ]
