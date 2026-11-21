"""Área do professor: alunos e resultados (só leitura). Ver alunos.py."""
from django.urls import path

from . import alunos, exames, tentativas

app_name = 'teacher_alunos'

urlpatterns = [
    path('alunos/', alunos.lista_alunos, name='alunos'),
    path('alunos/exportar/', alunos.exportar_alunos, name='alunos-exportar'),
    path('alunos/<uuid:aluno_id>/', alunos.detalhe_aluno, name='aluno'),
    path('alunos/<uuid:aluno_id>/fala/', exames.fala_aluno, name='aluno-fala'),
    path('alunos/<uuid:aluno_id>/questionarios/', tentativas.questionarios_do_aluno, name='aluno-questionarios'),
    path('alunos/<uuid:aluno_id>/questionarios/<uuid:quiz_id>/tentativas/', tentativas.dar_tentativas,
         name='aluno-questionario-tentativas'),
    path('exames/', exames.exames_dos_cursos, name='exames'),
    path('exames/<uuid:exame_id>/', exames.exame_detalhe, name='exame-detalhe'),
    path('exames/<uuid:exame_id>/rever/', exames.rever_exame, name='exame-rever'),
    path('resultados/', alunos.resultados, name='resultados'),
    path('resultados/exportar/', alunos.exportar_resultados, name='resultados-exportar'),
]
