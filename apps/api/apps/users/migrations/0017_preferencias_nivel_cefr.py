from django.db import migrations

# preferences.nivel passa para a escala CEFR (a mesma de Course.level, ver apps/courses/niveis.py).
PARA_CEFR = {'Beginner': 'A2', 'Intermediate': 'B1', 'Advanced': 'B2'}
PARA_ANTIGO = {'A1': 'Beginner', 'A2': 'Beginner', 'B1': 'Intermediate',
               'B2': 'Advanced', 'C1': 'Advanced', 'C2': 'Advanced'}


def _converter(apps, mapa):
    User = apps.get_model('users', 'User')
    for user in User.objects.only('id', 'preferences').iterator():
        prefs = user.preferences if isinstance(user.preferences, dict) else None
        if not prefs or prefs.get('nivel') not in mapa:
            continue
        prefs['nivel'] = mapa[prefs['nivel']]
        User.objects.filter(pk=user.pk).update(preferences=prefs)


def para_cefr(apps, schema_editor):
    _converter(apps, PARA_CEFR)


def para_antigo(apps, schema_editor):
    _converter(apps, PARA_ANTIGO)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_email_pendente'),
    ]

    operations = [
        migrations.RunPython(para_cefr, para_antigo),
    ]
