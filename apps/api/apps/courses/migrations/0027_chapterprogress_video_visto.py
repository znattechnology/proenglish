from django.db import migrations, models


def marcar_vistos(apps, schema_editor):
    # As aulas já concluídas foram vistas.
    ChapterProgress = apps.get_model('courses', 'ChapterProgress')
    ChapterProgress.objects.filter(completed=True).update(video_visto=True)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0026_moderacao_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='chapterprogress',
            name='video_visto',
            field=models.BooleanField(default=False, help_text='O aluno viu o vídeo (ou marcou a aula como vista)'),
        ),
        migrations.RunPython(marcar_vistos, migrations.RunPython.noop),
    ]
