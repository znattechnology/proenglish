"""
Teste do nível básico: o requisito para entrar num curso de sector sem ter feito o curso geral
(apps/courses/teste_basico.py tem o banco de perguntas e as regras).

Uma tentativa por linha. As perguntas sorteadas e a ordem das opções ficam aqui, no servidor:
o cliente nunca recebe as respostas certas e não escolhe as perguntas.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TesteNivelBasico(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='testes_basico')
    # [{"id": "<pergunta>", "ordem": [índices das opções pela ordem mostrada]}]
    perguntas = models.JSONField(default=list)
    expira_em = models.DateTimeField()
    submetido_em = models.DateTimeField(null=True, blank=True)
    certas = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)
    aprovado = models.BooleanField(default=False)

    class Meta:
        db_table = 'testes_nivel_basico'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]

    def __str__(self):
        return f'{self.user_id} {self.certas}/{self.total} {"aprovado" if self.aprovado else ""}'
