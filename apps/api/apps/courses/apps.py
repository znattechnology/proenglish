from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courses'

    def ready(self):
        # Notas recalculadas após quizzes e emissão automática de certificados.
        # Antes não eram importados em lado nenhum, por isso nunca corriam.
        from . import signals  # noqa: F401
