"""
Carrega num curso em vídeo as conversas com o tutor de uma ou mais unidades (docs/conteudo/<nível>/
unidade-NN/tutor.json) e liga cada uma à aula depois da qual o aluno a deve fazer.

    ./venv/bin/python manage.py carregar_conversas_curso <id do curso> \
        docs/conteudo/c1/unidade-01/tutor.json docs/conteudo/c1/unidade-02/tutor.json

Cada cenário do ficheiro traz "tipo" (guiada ou livre) e "depois_da_aula" (o código da aula, por
exemplo "1C"). A aula do curso é a que tem o título a começar por esse código ("1C — …", "1C: …"
ou "1C …"). Se não houver nenhuma, a conversa é carregada sem aula (aparece só na lista de
conversas) e o comando avisa; com --exigir-aulas, falha em vez de avisar.

As situações ficam no curso, activas, com o guião completo em extras (brief, primeira_fala, guiao,
frases com tradução, palavras, minutos_sugeridos e os critérios de sucesso). Correr outra vez
actualiza as mesmas situações (pelo slug).
"""
import json
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Chapter, Course
from apps.practice.models import Situacao

EXTRAS = ('brief', 'primeira_fala', 'primeira_fala_simples', 'guiao', 'frases', 'palavras', 'minutos_sugeridos')


def aula_do_codigo(aulas, codigo):
    """A aula cujo título começa pelo código ("1C — …"); None se não há ou se há mais de uma."""
    if not codigo:
        return None
    padrao = re.compile(r'^' + re.escape(str(codigo).strip()) + r'(\s|—|–|-|:|\.|$)', re.IGNORECASE)
    achadas = [a for a in aulas if padrao.match(a.title.strip())]
    return achadas[0] if len(achadas) == 1 else None


class Command(BaseCommand):
    help = 'Carrega as conversas com o tutor de uma ou mais unidades num curso, ligadas às aulas.'

    def add_arguments(self, parser):
        parser.add_argument('curso')
        parser.add_argument('ficheiros', nargs='+')
        parser.add_argument('--exigir-aulas', action='store_true',
                            help='Falha se alguma conversa não encontrar a sua aula.')

    def handle(self, *args, **o):
        curso = Course.objects.filter(pk=o['curso'], course_type='video').first()
        if curso is None:
            raise CommandError('Curso em vídeo não encontrado.')
        aulas = list(Chapter.objects.filter(section__course=curso))
        total, sem_aula = 0, []
        with transaction.atomic():
            for caminho in o['ficheiros']:
                with open(caminho, encoding='utf-8') as f:
                    cenarios = json.load(f).get('cenarios') or []
                for ordem, c in enumerate(cenarios, start=1):
                    outra = Situacao.objects.filter(slug=c['slug']).exclude(curso=curso).first()
                    if outra is not None:
                        raise CommandError(f'A situação {c["slug"]} já pertence a outro curso.')
                    tipo = c.get('tipo') or ''
                    if tipo not in ('', *Situacao.TIPOS_CONVERSA):
                        raise CommandError(f'{c["slug"]}: tipo inválido ({tipo}).')
                    if c.get('duracao_min', 5) not in Situacao.DURACOES:
                        raise CommandError(f'{c["slug"]}: duração inválida ({c.get("duracao_min")}).')
                    aula = aula_do_codigo(aulas, c.get('depois_da_aula'))
                    if aula is None:
                        sem_aula.append(f'{c["slug"]} (aula {c.get("depois_da_aula") or "?"})')
                    dados = c.get('extras') or {}
                    extras = {k: dados[k] for k in EXTRAS if dados.get(k) is not None}
                    if c.get('criterios'):
                        extras['criterios'] = c['criterios']
                    Situacao.objects.update_or_create(slug=c['slug'], defaults=dict(
                        nome=c['nome'][:80], descricao=c['descricao'], papel_tutor=(c.get('papel_tutor') or '')[:300],
                        frases=c.get('frases') or [], curso=curso, area=c.get('area') or 'general',
                        nivel=(c.get('nivel') or curso.level or 'A1')[:2], duracao_min=c.get('duracao_min', 5),
                        correccao=c.get('correccao') or 'suave', estado=Situacao.ACTIVO, criado_por=curso.teacher,
                        ordem=ordem, extras=extras, aula=aula, tipo_conversa=tipo))
                    total += 1
            if sem_aula and o['exigir_aulas']:
                raise CommandError('Conversas sem aula no curso: ' + ', '.join(sem_aula))
        self.stdout.write(f'{total} conversas carregadas.')
        if sem_aula:
            self.stdout.write(self.style.WARNING('Sem aula (aparecem só na lista de conversas): ' + ', '.join(sem_aula)))
