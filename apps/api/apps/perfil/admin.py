from django.contrib import admin

from .models import ExerciciosPadrao, ItemBanco, PadraoErro, PerfilFala, RespostaRevisao


@admin.register(PerfilFala)
class PerfilFalaAdmin(admin.ModelAdmin):
    list_display = ('user', 'nivel_falar', 'nivel_ouvir', 'nivel_vocabulario', 'nivel_gramatica',
                    'conversas_avaliadas', 'actualizado_em')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)


@admin.register(ItemBanco)
class ItemBancoAdmin(admin.ModelAdmin):
    list_display = ('texto', 'user', 'estado', 'origem', 'proxima_revisao', 'repeticoes', 'criado_em')
    list_filter = ('estado', 'origem', 'tipo')
    search_fields = ('texto', 'user__email')
    raw_id_fields = ('user', 'situacao', 'capitulo', 'licao', 'curso')


@admin.register(PadraoErro)
class PadraoErroAdmin(admin.ModelAdmin):
    list_display = ('chave', 'user', 'ocorrencias', 'sessoes_sem_ocorrer', 'superado', 'ultima_ocorrencia')
    list_filter = ('superado',)
    search_fields = ('chave', 'user__email')
    raw_id_fields = ('user',)


@admin.register(RespostaRevisao)
class RespostaRevisaoAdmin(admin.ModelAdmin):
    list_display = ('chave_exercicio', 'user', 'forma', 'dia', 'correcta', 'nota', 'contou')
    list_filter = ('forma', 'nota', 'contou')
    search_fields = ('user__email', 'chave_exercicio')
    raw_id_fields = ('user', 'item')


@admin.register(ExerciciosPadrao)
class ExerciciosPadraoAdmin(admin.ModelAdmin):
    list_display = ('chave', 'modelo', 'criado_em')
    search_fields = ('chave',)
