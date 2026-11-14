from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('perfil', '0004_revisao_sessao_e_padroes'),
    ]

    operations = [
        migrations.AddField(
            model_name='itembanco',
            name='falhas_seguidas',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='itembanco',
            name='ultima_falha',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
