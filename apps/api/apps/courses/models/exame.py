"""
Exame oral de um curso (fase 6).

Uma tentativa por linha: o aluno fala 8 a 10 minutos com o tutor no papel de examinador
(apps/practice/conversa/exame.py). A IA dá uma nota por competência, a nota final (0-100) e o
nível CEFR atingido; o professor do curso pode confirmar ou rever a nota (a revista ganha sempre).

Gravação: só com o consentimento do aluno (consentimento_gravacao). Sem consentimento o exame
faz-se na mesma, sem áudio guardado. O URL da gravação vem do end-of-call-report do Vapi e é
apagado ao fim de RETENCAO_GRAVACOES_DIAS (conversa/exame.py, comando apagar_gravacoes_exames).
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ExameOral(BaseModel):
    EM_CURSO = 'em_curso'
    A_AVALIAR = 'a_avaliar'
    AVALIADO = 'avaliado'
    INSUFICIENTE = 'insuficiente'   # ligou mas o aluno falou muito pouco: sem nota, não bloqueia
    ANULADO = 'anulado'             # a chamada nunca ligou
    ESTADOS = [(EM_CURSO, 'Em curso'), (A_AVALIAR, 'A avaliar'), (AVALIADO, 'Avaliado'),
               (INSUFICIENTE, 'Sem respostas suficientes'), (ANULADO, 'Não ligou')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exames_orais')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='exames_orais')
    sessao = models.ForeignKey('practice.VapiSession', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+')
    estado = models.CharField(max_length=14, choices=ESTADOS, default=EM_CURSO, db_index=True)

    # Notas da IA por competência (0-100). A pronúncia só existe com gravação consentida e o Azure
    # Speech configurado (conversa/exame.avaliar_pronuncia, em segundo plano); senão fica vazia.
    nota_fluencia = models.FloatField(null=True, blank=True)
    nota_gramatica = models.FloatField(null=True, blank=True)
    nota_vocabulario = models.FloatField(null=True, blank=True)
    nota_tarefa = models.FloatField(null=True, blank=True, help_text='Cumprimento das tarefas')
    nota_pronuncia = models.FloatField(null=True, blank=True)
    nota_final = models.FloatField(null=True, blank=True, help_text='Nota da IA (0-100)')
    nivel_cefr = models.CharField(max_length=2, blank=True, default='')
    nota_minima = models.FloatField(default=60.0, help_text='Nota para passar (no momento do exame)')
    aprovado = models.BooleanField(default=False)
    frases_usadas = models.JSONField(default=list, blank=True, help_text='Frases do curso ditas sozinho')
    frases_total = models.PositiveIntegerField(default=0)
    relatorio = models.TextField(blank=True, default='', help_text='Para o aluno (pt-PT)')
    a_treinar = models.JSONField(default=list, blank=True)
    fonte_avaliacao = models.CharField(max_length=10, blank=True, default='')

    consentimento_gravacao = models.BooleanField(default=False)
    consentimento_em = models.DateTimeField(null=True, blank=True)
    gravacao_url = models.URLField(max_length=1000, blank=True, default='')
    gravada_em = models.DateTimeField(null=True, blank=True)
    gravacao_apagada_em = models.DateTimeField(null=True, blank=True)

    revisto_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='exames_revistos')
    nota_revista = models.FloatField(null=True, blank=True)
    comentario_revisao = models.TextField(blank=True, default='')
    revisto_em = models.DateTimeField(null=True, blank=True)

    avaliado_em = models.DateTimeField(null=True, blank=True)
    pode_repetir_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'exames_orais'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'course', '-created_at']),
                   models.Index(fields=['course', 'estado'])]
        verbose_name = 'exame oral'
        verbose_name_plural = 'exames orais'

    def __str__(self):
        return f'{self.user_id} {self.course_id} {self.estado} {self.nota_efectiva}'

    @property
    def nota_efectiva(self):
        """A nota do professor, quando existe; senão a da IA."""
        return self.nota_revista if self.nota_revista is not None else self.nota_final

    def notas(self):
        return {'fluencia': self.nota_fluencia, 'gramatica': self.nota_gramatica,
                'vocabulario': self.nota_vocabulario, 'tarefa': self.nota_tarefa,
                'pronuncia': self.nota_pronuncia}
