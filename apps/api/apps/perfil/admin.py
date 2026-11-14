from django.contrib import admin

from .models import ItemBanco, PadraoErro, PerfilFala


@admin.register(PerfilFala)
class PerfilFalaAdmin(admin.ModelAdmin):
    list_display = ('user', 'nivel_falar', 'nivel_ouvir', 'nivel_vocabulario', 'nivel_gramatica',
                    'conversas_avaliadas', 'actualizado_em')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)


@admin.register(ItemBanco)
class ItemBancoAdmin(admin.ModelAdmin):
    list_display = ('texto', 'user', 'estado', 'origem', 'vezes_sozinho', 'dias_sozinho', 'criado_em')
    list_filter = ('estado', 'origem', 'tipo')
    search_fields = ('texto', 'user__email')
    raw_id_fields = ('user', 'situacao', 'capitulo', 'licao', 'curso')


@admin.register(PadraoErro)
class PadraoErroAdmin(admin.ModelAdmin):
    list_display = ('chave', 'user', 'ocorrencias', 'sessoes_sem_ocorrer', 'superado', 'ultima_ocorrencia')
    list_filter = ('superado',)
    search_fields = ('chave', 'user__email')
    raw_id_fields = ('user',)
