from django.apps import AppConfig


class PagamentosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pagamentos'
    verbose_name = 'Pagamentos'

    def ready(self):
        # Avisos ao aluno (Notification) ligados aos sinais de pagamentos/renovação
        from . import avisos  # noqa: F401
