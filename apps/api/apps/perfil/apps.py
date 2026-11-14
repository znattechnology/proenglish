from django.apps import AppConfig


class PerfilConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.perfil'
    label = 'perfil'
    verbose_name = 'Perfil de fala'

    def ready(self):
        from . import signals  # noqa: F401  (erros nas lições -> revisão)
