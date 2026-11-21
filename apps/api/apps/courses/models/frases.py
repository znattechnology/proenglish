"""
Frases da aula (aulas em vídeo).

Frases e palavras úteis no trabalho que aparecem no vídeo de uma aula. O Claude propõe-nas a partir
da transcrição (apps/courses/frases_aula.py); o professor aprova, edita, apaga ou acrescenta. Só as
aprovadas chegam aos alunos: entram no banco de frases quando o aluno vê o vídeo, servem para o
"Repetir em voz alta" e são os objectivos da conversa no fim da aula.
"""
from django.db import models


class FraseAula(models.Model):
    TIPO_FRASE = 'frase'
    TIPO_PALAVRA = 'palavra'
    TIPOS = [(TIPO_FRASE, 'Frase'), (TIPO_PALAVRA, 'Palavra')]

    PROPOSTA = 'proposta'
    APROVADA = 'aprovada'
    ESTADOS = [(PROPOSTA, 'Proposta'), (APROVADA, 'Aprovada')]

    chapter = models.ForeignKey('courses.Chapter', on_delete=models.CASCADE, related_name='frases_aula')
    texto = models.CharField(max_length=300, help_text='Em inglês')
    traducao = models.CharField(max_length=300, blank=True, default='', help_text='Em português (pt-PT)')
    inicio = models.FloatField(null=True, blank=True, help_text='Segundo do vídeo onde a frase começa')
    fim = models.FloatField(null=True, blank=True, help_text='Segundo do vídeo onde a frase acaba')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=TIPO_FRASE)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PROPOSTA, db_index=True)
    ordem = models.PositiveIntegerField(default=0)
    criada_por_ia = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    actualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'frases_aula'
        ordering = ['ordem', 'id']
        indexes = [models.Index(fields=['chapter', 'estado'])]
        verbose_name = 'frase da aula'
        verbose_name_plural = 'frases das aulas'

    def __str__(self):
        return f'{self.texto} ({self.estado})'
