"""
Gera os bancos de perguntas dos testes de colocação (apps/courses/bancos_colocacao.json) a partir
dos questionários das unidades em docs/conteudo/<nível>/*/questionario.json.

    python manage.py gerar_bancos_colocacao [--conteudo ../../docs/conteudo]

Só entram perguntas de escolha múltipla com exactamente uma opção certa. O prefixo "U3. " do
enunciado (a unidade, útil no questionário da revisão) sai. Os testes do A1, A2, B1 e B2 usam
estes bancos; o do A2 junta-lhes o banco do teste do nível básico (teste_basico.BANCO).
"""
import json
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

NIVEIS = ('A1', 'A2', 'B1', 'B2')
PREFIXO = re.compile(r'^U\d+\.\s*')
SAIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bancos_colocacao.json')


def ler_nivel(pasta_nivel, nivel):
    banco = []
    for pasta in sorted(os.listdir(pasta_nivel)):
        caminho = os.path.join(pasta_nivel, pasta, 'questionario.json')
        if not os.path.exists(caminho):
            continue
        with open(caminho, encoding='utf-8') as f:
            perguntas = json.load(f).get('questions') or []
        for q in perguntas:
            opcoes = q.get('options') or []
            certas = [o for o in opcoes if o.get('isCorrect')]
            if len(certas) != 1 or len(opcoes) < 2:
                continue
            textos = [certas[0]['text']] + [o['text'] for o in opcoes if not o.get('isCorrect')]
            enunciado = PREFIXO.sub('', (q.get('question') or '').strip())
            if not enunciado or any(not (t or '').strip() for t in textos):
                continue
            banco.append([f'{nivel.lower()}-{pasta}-{q["id"]}', enunciado, textos])
    return banco


class Command(BaseCommand):
    help = 'Gera apps/courses/bancos_colocacao.json a partir dos questionários das unidades.'

    def add_arguments(self, parser):
        parser.add_argument('--conteudo', default=os.path.join(settings.BASE_DIR, '..', '..', 'docs', 'conteudo'))

    def handle(self, *args, conteudo, **opts):
        bancos = {}
        for nivel in NIVEIS:
            pasta = os.path.join(conteudo, nivel.lower())
            if not os.path.isdir(pasta):
                raise CommandError(f'Não existe {pasta}.')
            bancos[nivel] = ler_nivel(pasta, nivel)
            self.stdout.write(f'{nivel}: {len(bancos[nivel])} perguntas')
        with open(SAIDA, 'w', encoding='utf-8') as f:
            json.dump(bancos, f, ensure_ascii=False, indent=0)
        self.stdout.write(f'Escrito {SAIDA}')
