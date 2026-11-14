"""
Perfil de fala do aluno (um por aluno).

- PerfilFala: nível CEFR por competência (com uma pontuação contínua para suavizar).
- ItemBanco: frases e palavras que o aluno está a aprender, com o estado
  vista < reconhecida < com_ajuda < sozinho (nunca desce). Os campos de repetição
  espaçada (proxima_revisao, estabilidade, ...) ficam prontos para a revisão (fase 4).
- PadraoErro: erros recorrentes (chave estável, p.ex. 'third_person_s').
"""
from django.conf import settings
from django.db import models

NIVEIS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
NIVEL_CHOICES = [(n, n) for n in NIVEIS]
COMPETENCIAS = ('falar', 'ouvir', 'vocabulario', 'gramatica')


class PerfilFala(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_fala')

    nivel_falar = models.CharField(max_length=2, choices=NIVEL_CHOICES, null=True, blank=True)
    nivel_ouvir = models.CharField(max_length=2, choices=NIVEL_CHOICES, null=True, blank=True)
    nivel_vocabulario = models.CharField(max_length=2, choices=NIVEL_CHOICES, null=True, blank=True)
    nivel_gramatica = models.CharField(max_length=2, choices=NIVEL_CHOICES, null=True, blank=True)
    # Pontuação contínua por competência: 0 = A1 ... 5 = C2 (média móvel das estimativas).
    pontos_falar = models.FloatField(null=True, blank=True)
    pontos_ouvir = models.FloatField(null=True, blank=True)
    pontos_vocabulario = models.FloatField(null=True, blank=True)
    pontos_gramatica = models.FloatField(null=True, blank=True)

    profissao = models.CharField(max_length=120, blank=True, default='')
    objectivo = models.CharField(max_length=200, blank=True, default='')
    conversas_avaliadas = models.PositiveIntegerField(default=0)

    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'perfil de fala'
        verbose_name_plural = 'perfis de fala'

    def __str__(self):
        return f'{self.user_id} ({self.nivel_falar or "-"})'

    def niveis(self):
        return {c: getattr(self, f'nivel_{c}') for c in COMPETENCIAS}


class ItemBanco(models.Model):
    TIPO_FRASE = 'frase'
    TIPO_PALAVRA = 'palavra'
    TIPOS = [(TIPO_FRASE, 'Frase'), (TIPO_PALAVRA, 'Palavra')]

    VISTA = 'vista'
    RECONHECIDA = 'reconhecida'
    COM_AJUDA = 'com_ajuda'
    SOZINHO = 'sozinho'
    ESTADOS = [VISTA, RECONHECIDA, COM_AJUDA, SOZINHO]  # por ordem: nunca desce
    ESTADO_CHOICES = [(VISTA, 'Vista'), (RECONHECIDA, 'Reconhecida'), (COM_AJUDA, 'Disse com ajuda'),
                      (SOZINHO, 'Disse sozinho')]

    ORIGENS = [('situacao', 'Situação'), ('aula', 'Aula em vídeo'), ('licao', 'Lição de prática'),
               ('conversa', 'Conversa'), ('professor', 'Professor')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='banco_frases')
    texto = models.CharField(max_length=300, help_text='Em inglês')
    traducao = models.CharField(max_length=300, blank=True, default='')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=TIPO_FRASE)
    chave = models.CharField(max_length=300, help_text='Texto normalizado (sem repetidos por aluno)')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=VISTA, db_index=True)
    vezes_sozinho = models.PositiveIntegerField(default=0)
    dias_sozinho = models.PositiveIntegerField(default=0, help_text='Dias diferentes em que a disse sozinho')
    ultima_vez_sozinho = models.DateTimeField(null=True, blank=True)

    origem = models.CharField(max_length=12, choices=ORIGENS, default='conversa')
    situacao = models.ForeignKey('practice.Situacao', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+')
    capitulo = models.ForeignKey('courses.Chapter', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+')
    licao = models.ForeignKey('practice.PracticeLesson', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+')
    curso = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+')
    sessao_origem = models.CharField(max_length=100, blank=True, default='',
                                     help_text='Conversa (VapiSession.session_id) onde apareceu')

    # Repetição espaçada (fase 4; por agora não usados).
    proxima_revisao = models.DateTimeField(null=True, blank=True)
    estabilidade = models.FloatField(null=True, blank=True)
    dificuldade = models.FloatField(null=True, blank=True)
    repeticoes = models.PositiveIntegerField(default=0)
    lapsos = models.PositiveIntegerField(default=0)

    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        constraints = [models.UniqueConstraint(fields=['user', 'chave'], name='perfil_item_unico_por_aluno')]
        indexes = [
            models.Index(fields=['user', 'estado']),
            models.Index(fields=['user', 'proxima_revisao']),
        ]
        verbose_name = 'item do banco'
        verbose_name_plural = 'banco de frases'

    def __str__(self):
        return f'{self.texto} ({self.estado})'

    @classmethod
    def ordem(cls, estado):
        return cls.ESTADOS.index(estado) if estado in cls.ESTADOS else -1


class PadraoErro(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='padroes_erro')
    chave = models.CharField(max_length=60, help_text="snake_case estável, p.ex. 'third_person_s'")
    descricao = models.CharField(max_length=160, help_text='Para o aluno (pt-PT, curta)')
    exemplo_errado = models.CharField(max_length=200, blank=True, default='')
    exemplo_certo = models.CharField(max_length=200, blank=True, default='')
    ocorrencias = models.PositiveIntegerField(default=0)
    sessoes_sem_ocorrer = models.PositiveIntegerField(default=0)
    ultima_ocorrencia = models.DateTimeField(null=True, blank=True)
    superado = models.BooleanField(default=False, db_index=True)
    superado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['superado', '-ocorrencias', '-ultima_ocorrencia']
        constraints = [models.UniqueConstraint(fields=['user', 'chave'], name='perfil_padrao_unico_por_aluno')]
        verbose_name = 'padrão de erro'
        verbose_name_plural = 'padrões de erro'

    def __str__(self):
        return f'{self.chave} x{self.ocorrencias}{" (superado)" if self.superado else ""}'
