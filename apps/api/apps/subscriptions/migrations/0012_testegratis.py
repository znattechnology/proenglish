import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _normalizar_email(email):
    email = (email or '').strip().lower()
    if '@' not in email:
        return email
    local, dominio = email.rsplit('@', 1)
    local = local.split('+', 1)[0]
    if dominio in ('gmail.com', 'googlemail.com'):
        local = local.replace('.', '')
        dominio = 'gmail.com'
    return f'{local}@{dominio}'


def preencher(apps, schema_editor):
    """Regista os testes já feitos (sem número) e prende os códigos "meses" ao pagamento mensal."""
    Historico = apps.get_model('subscriptions', 'SubscriptionHistory')
    Teste = apps.get_model('subscriptions', 'TesteGratis')
    Codigo = apps.get_model('subscriptions', 'PromotionalCode')
    vistos = set()
    for h in (Historico.objects.filter(event_type='TRIAL_STARTED', new_plan__isnull=False)
              .select_related('subscription__user').order_by('created_at')):
        user = h.subscription.user
        email = _normalizar_email(user.email)
        if email in vistos:
            email = ''
        vistos.add(email)
        sub = h.subscription
        Teste.objects.create(user=user, plan_id=h.new_plan_id, telefone=None, email_normalizado=email,
                             iniciado_em=h.created_at,
                             termina_em=sub.trial_ends_at or sub.expires_at or h.created_at)
    # Duração "meses" só vale no pagamento mensal (um ano com N% era um erro)
    for c in Codigo.objects.filter(duracao='meses').exclude(periodo_aplicavel='mensal'):
        c.periodo_aplicavel = 'mensal'
        if c.description and 'só no pagamento' not in c.description and ' mensal' not in c.description:
            c.description = f'{c.description}, só no pagamento mensal'
        c.save(update_fields=['periodo_aplicavel', 'description'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('subscriptions', '0011_planos_codigos_testes'),
    ]

    operations = [
        migrations.CreateModel(
            name='TesteGratis',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('telefone', models.CharField(blank=True, max_length=9, null=True)),
                ('email_normalizado', models.CharField(blank=True, default='', max_length=254)),
                ('iniciado_em', models.DateTimeField(default=django.utils.timezone.now)),
                ('termina_em', models.DateTimeField()),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='testes_gratis',
                                           to='subscriptions.subscriptionplan')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='testes_gratis',
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-iniciado_em']},
        ),
        migrations.AddConstraint(
            model_name='testegratis',
            constraint=models.UniqueConstraint(condition=models.Q(('telefone__isnull', False)), fields=('telefone',),
                                               name='teste_gratis_um_por_telefone'),
        ),
        migrations.AddConstraint(
            model_name='testegratis',
            constraint=models.UniqueConstraint(condition=models.Q(('email_normalizado', ''), _negated=True),
                                               fields=('email_normalizado',), name='teste_gratis_um_por_email'),
        ),
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
