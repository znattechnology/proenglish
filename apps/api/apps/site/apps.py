from django.apps import AppConfig


class SiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site'
    label = 'site'
    verbose_name = 'Conteúdo do site público'

    def ready(self):
        from . import sinais
        sinais.ligar()
