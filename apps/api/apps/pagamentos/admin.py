from django.contrib import admin

from .models import Pagamento, SequenciaRecibo, LembreteRenovacao


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('numero_recibo', 'user', 'plan', 'periodo',
                    'valor_kz', 'desconto_kz', 'estado', 'provedor', 'created_at', 'pago_em')
    list_filter = ('estado', 'provedor', 'periodo', 'plan')
    search_fields = ('numero_recibo', 'referencia_externa', 'user__email', 'telefone')
    readonly_fields = [f.name for f in Pagamento._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(SequenciaRecibo)
class SequenciaReciboAdmin(admin.ModelAdmin):
    list_display = ('ano', 'ultimo')


@admin.register(LembreteRenovacao)
class LembreteRenovacaoAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'tipo', 'fim_periodo', 'enviado_em')
    list_filter = ('tipo',)
