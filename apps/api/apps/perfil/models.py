"""
Perfil de fala do aluno (um por aluno).

- PerfilFala: nível CEFR por competência (com uma pontuação contínua para suavizar).
- ItemBanco: frases e palavras que o aluno está a aprender, com o estado
  vista < reconhecida < com_ajuda < sozinho. Só sobe, com uma excepção: uma frase 'sozinho'
  falhada em FALHAS_PARA_DESCER dias seguidos volta a 'com_ajuda' (servico.registar_falha). Os campos de repetição
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
    # Meta diária de minutos a FALAR (fase 3). A sequência continua a usar a meta de estudo.
    META_FALA_CHOICES = [(3, '3 minutos'), (5, '5 minutos'), (10, '10 minutos'), (15, '15 minutos')]
    META_FALA_PADRAO = 5
    meta_fala_min = models.PositiveSmallIntegerField(choices=META_FALA_CHOICES, default=META_FALA_PADRAO)

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
    ESTADOS = [VISTA, RECONHECIDA, COM_AJUDA, SOZINHO]  # por ordem (só 'sozinho' desce: servico.registar_falha)
    ESTADO_CHOICES = [(VISTA, 'Vista'), (RECONHECIDA, 'Reconhecida'), (COM_AJUDA, 'Disse com ajuda'),
                      (SOZINHO, 'Disse sozinho')]

    ORIGENS = [('situacao', 'Situação'), ('aula', 'Aula em vídeo'), ('licao', 'Lição de prática'),
               ('conversa', 'Conversa'), ('professor', 'Professor'), ('pronuncia', 'Palavra difícil')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='banco_frases')
    texto = models.CharField(max_length=300, help_text='Em inglês')
    traducao = models.CharField(max_length=300, blank=True, default='')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=TIPO_FRASE)
    chave = models.CharField(max_length=300, help_text='Texto normalizado (sem repetidos por aluno)')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=VISTA, db_index=True)
    vezes_sozinho = models.PositiveIntegerField(default=0)
    dias_sozinho = models.PositiveIntegerField(default=0, help_text='Dias diferentes em que a disse sozinho')
    ultima_vez_sozinho = models.DateTimeField(null=True, blank=True)
    # Falhas seguidas (no máximo uma por dia de Luanda): revisão, lição, correcção numa conversa.
    # Um acerto põe a zero. vezes_sozinho / dias_sozinho / ultima_vez_sozinho são histórico e
    # nunca se apagam, mesmo quando a frase volta a 'com_ajuda'.
    falhas_seguidas = models.PositiveSmallIntegerField(default=0)
    ultima_falha = models.DateTimeField(null=True, blank=True)

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

    # Repetição espaçada (revisão de hoje, apps/perfil/agenda.py). proxima_revisao vazia = item novo,
    # ainda fora da agenda; entra na revisão (no máximo N novos por dia).
    proxima_revisao = models.DateTimeField(null=True, blank=True)
    estabilidade = models.FloatField(null=True, blank=True, help_text='Dias até a memória cair para 90%')
    dificuldade = models.FloatField(null=True, blank=True, help_text='1 (fácil) a 10 (difícil)')
    repeticoes = models.PositiveIntegerField(default=0)
    lapsos = models.PositiveIntegerField(default=0)
    ultima_revisao = models.DateTimeField(null=True, blank=True)
    introduzida_em = models.DateTimeField(null=True, blank=True, help_text='Primeira vez na revisão')

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


class RespostaRevisao(models.Model):
    """
    Cada resposta na revisão de hoje. Só a primeira resposta a um exercício em cada dia (Luanda)
    conta (contou=True): mexe na agenda, dá pontos e minutos. Serve também o resumo do fim.
    """
    NOTAS = [('errei', 'Errei'), ('dificil', 'Difícil'), ('certo', 'Certo'), ('facil', 'Fácil')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='respostas_revisao')
    item = models.ForeignKey(ItemBanco, on_delete=models.CASCADE, null=True, blank=True, related_name='respostas')
    chave_exercicio = models.CharField(max_length=120, help_text="'item:<id>' ou 'padrao:<chave>:<n>'")
    forma = models.CharField(max_length=20)
    dia = models.DateField(help_text='Dia de Angola')
    correcta = models.BooleanField()
    nota = models.CharField(max_length=8, choices=NOTAS, blank=True, default='')
    contou = models.BooleanField(default=False)
    estado_antes = models.CharField(max_length=12, blank=True, default='')
    estado_depois = models.CharField(max_length=12, blank=True, default='')
    resposta = models.CharField(max_length=300, blank=True, default='')
    segundos = models.FloatField(default=0)
    pontos = models.PositiveSmallIntegerField(default=0)
    criada_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-criada_em']
        indexes = [models.Index(fields=['user', 'dia']), models.Index(fields=['user', 'chave_exercicio', 'dia'])]
        verbose_name = 'resposta da revisão'
        verbose_name_plural = 'respostas da revisão'

    def __str__(self):
        return f'{self.user_id} {self.chave_exercicio} {self.nota or "-"}'


class ExerciciosPadrao(models.Model):
    """
    Exercícios curtos gerados (Claude) para um padrão de erro, guardados por (chave, descrição).
    As chaves conhecidas (regras.CHAVES_REGRAS e as da lista curada em revisao.DESCRICOES_CANONICAS)
    usam sempre a nossa descrição: o mesmo registo serve todos os alunos. As outras chaves (escritas
    livremente pelo Claude) só partilham o registo com quem tiver exactamente a mesma descrição.
    Regenerados ao fim de revisao.VALIDADE_PADRAO_DIAS (criado_em = data da geração).
    """
    chave = models.CharField(max_length=60)
    descricao_hash = models.CharField(max_length=64, default='', help_text='sha256 da descrição normalizada')
    descricao = models.CharField(max_length=160, blank=True, default='')
    exercicios = models.JSONField(default=list)
    modelo = models.CharField(max_length=60, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chave', 'descricao_hash'], name='perfil_exercicios_padrao_unico')]
        verbose_name = 'exercícios de um padrão'
        verbose_name_plural = 'exercícios dos padrões'

    def __str__(self):
        return f'{self.chave} ({len(self.exercicios or [])})'


class FalaDiaria(models.Model):
    """
    Segundos que o aluno FALOU num dia de Luanda (fase 3): a sua parte das conversas com o tutor
    (incl. lição, aula, teste de nível e exame oral) e todas as gravações (lição, Responder, revisão,
    repetir frases da aula). Recalculada a partir das fontes (idempotente): ver apps/perfil/fala.py.
    fontes: {'conversa': s, 'exame': s, 'diagnostico': s, 'licao': s, 'responder': s, 'revisao': s, 'aula': s}
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fala_diaria')
    dia = models.DateField(help_text='Dia de Angola')
    segundos = models.FloatField(default=0)
    fontes = models.JSONField(default=dict, blank=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-dia']
        constraints = [models.UniqueConstraint(fields=['user', 'dia'], name='perfil_fala_diaria_unica')]
        verbose_name = 'fala diária'
        verbose_name_plural = 'fala diária'

    def __str__(self):
        return f'{self.user_id} {self.dia}: {self.segundos:.0f} s'


class PalavraDificil(models.Model):
    """
    Palavras que o aluno pronuncia mal (fase 3). Vêm das gravações: hoje as palavras a melhorar da
    avaliação pelo texto; com a avaliação detalhada, a nota de cada palavra (media).
    acertos_seguidos: gravações seguidas em que a palavra saiu bem (3 = deixa de aparecer).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='palavras_dificeis')
    palavra = models.CharField(max_length=40, help_text='Minúsculas')
    tentativas = models.PositiveIntegerField(default=0)
    falhas = models.PositiveIntegerField(default=0)
    acertos_seguidos = models.PositiveIntegerField(default=0)
    media = models.FloatField(null=True, blank=True, help_text='Nota média (0-100) das avaliações detalhadas')
    avaliacoes_detalhadas = models.PositiveIntegerField(default=0)
    fonema = models.CharField(max_length=20, blank=True, default='', help_text='O som mais difícil (detalhada)')
    ultima = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-falhas', '-ultima']
        constraints = [models.UniqueConstraint(fields=['user', 'palavra'], name='perfil_palavra_dificil_unica')]
        verbose_name = 'palavra difícil'
        verbose_name_plural = 'palavras difíceis'

    def __str__(self):
        return f'{self.palavra} ({self.falhas}/{self.tentativas})'


class SessaoRevisao(models.Model):
    """
    Os exercícios servidos a um aluno num dia de Luanda (revisão de hoje). A forma de cada item e o
    conteúdo de cada exercício de padrão ficam fixos para o dia: a resposta é corrigida contra o que
    foi mostrado (nunca contra a forma enviada pelo cliente) e um padrão regenerado não muda um
    exercício já servido. exercicios: {id: {'forma': ..., 'padrao': {...}, 'e': {...}, 'saltado': bool}}
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessoes_revisao')
    dia = models.DateField(help_text='Dia de Angola')
    exercicios = models.JSONField(default=dict, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    actualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-dia']
        constraints = [models.UniqueConstraint(fields=['user', 'dia'], name='perfil_sessao_revisao_unica')]
        verbose_name = 'sessão da revisão'
        verbose_name_plural = 'sessões da revisão'

    def __str__(self):
        return f'{self.user_id} {self.dia} ({len(self.exercicios or {})})'
