"""Contas com a palavra-passe vazia ('') passam a ter uma palavra-passe inutilizável.

Para o Django, '' conta como palavra-passe "utilizável" (has_usable_password() devolve True),
o que confundia, por exemplo, apagar-conta/ nas contas criadas pelo Google.
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations


def inutilizar(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for pk in User.objects.filter(password='').values_list('pk', flat=True):
        User.objects.filter(pk=pk).update(password=make_password(None))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_emailverification_finalidade'),
    ]

    operations = [
        migrations.RunPython(inutilizar, migrations.RunPython.noop),
    ]
