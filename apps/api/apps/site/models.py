"""
Conteúdo do site público (página inicial).

A administração edita um RASCUNHO (ConfiguracaoSite.topo/precos/definicoes e as listas Numero,
Empresa, Servico, Pergunta). "Publicar alterações" copia o rascunho para
ConfiguracaoSite.publicado (uma fotografia em JSON) e é só essa fotografia que o site lê.
O modo de manutenção não passa pelo rascunho: aplica-se logo.
"""
from django.conf import settings
from django.db import models


class ConfiguracaoSite(models.Model):
    """Linha única (pk=1)."""

    # Rascunho das secções simples
    topo = models.JSONField(default=dict, blank=True)
    precos = models.JSONField(default=dict, blank=True)
    definicoes = models.JSONField(default=dict, blank=True)
    # {secção: ISO} da última alteração do rascunho em cada secção
    alterado_em = models.JSONField(default=dict, blank=True)

    # Versão publicada (o que o site mostra)
    publicado = models.JSONField(default=dict, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)
    publicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name='+')

    # Manutenção (imediata, fora do rascunho)
    manutencao_activa = models.BooleanField(default=False)
    manutencao_mensagem = models.CharField(max_length=300, blank=True, default='')
    manutencao_volta_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Configuração do site'
        verbose_name_plural = 'Configuração do site'

    def __str__(self):
        return 'Configuração do site'

    @classmethod
    def obter(cls, bloquear=False):
        qs = cls.objects.select_for_update() if bloquear else cls.objects
        obj = qs.filter(pk=1).first()
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Numero(models.Model):
    FONTES = [
        ('manual', 'Escrito à mão'),
        ('utilizadores', 'Alunos registados'),
        ('alunos_activos_semana', 'Alunos activos nos últimos 7 dias'),
        ('areas', 'Áreas profissionais com cursos'),
        ('cursos', 'Cursos publicados'),
    ]
    ONDE = [('topo', 'Topo'), ('sobre', 'Sobre'), ('rodape', 'Rodapé')]

    valor = models.CharField(max_length=20, blank=True, default='')  # só para fonte manual
    texto = models.CharField(max_length=60)
    onde = models.CharField(max_length=10, choices=ONDE, default='topo')
    fonte = models.CharField(max_length=30, choices=FONTES, default='manual')
    mostrar = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'id']


class Empresa(models.Model):
    nome = models.CharField(max_length=80)
    area = models.CharField(max_length=60, blank=True, default='')
    logo_url = models.CharField(max_length=500, blank=True, default='')
    no_topo = models.BooleanField(default=False)
    na_faixa = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'id']


class Servico(models.Model):
    ICONES = [
        ('bot', 'Robô'), ('microfone', 'Microfone'), ('balao', 'Balão de conversa'),
        ('livro', 'Livro'), ('certificado', 'Certificado'), ('laboratorio', 'Laboratório'),
    ]

    titulo = models.CharField(max_length=60)
    texto = models.CharField(max_length=300)
    icone = models.CharField(max_length=20, choices=ICONES, default='livro')
    leva_a = models.CharField(max_length=200, blank=True, default='')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'id']


class Pergunta(models.Model):
    pergunta = models.CharField(max_length=200)
    resposta = models.TextField(max_length=1000)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'id']
