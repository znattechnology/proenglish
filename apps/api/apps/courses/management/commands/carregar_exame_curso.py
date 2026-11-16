"""
Carrega num curso o guião do exame oral e as situações só do exame (docs/conteudo/a1/revisao-N/).

    ./venv/bin/python manage.py carregar_exame_curso <id do curso> \
        --guiao docs/conteudo/a1/revisao-2/exame-guiao.json \
        --situacoes docs/conteudo/a1/revisao-2/exame-situacoes.json

O guião vai para CourseGradingConfig.exam_script (validado por exame.validar_guiao). As situações
ficam no curso, activas e com extras.exame = true: o aluno não as vê (só saem no exame).
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Course, CourseGradingConfig
from apps.practice.conversa import exame
from apps.practice.models import Situacao


class Command(BaseCommand):
    help = 'Carrega o guião do exame oral e as situações do exame num curso.'

    def add_arguments(self, parser):
        parser.add_argument('curso')
        parser.add_argument('--guiao')
        parser.add_argument('--situacoes')

    def handle(self, *args, **o):
        curso = Course.objects.filter(pk=o['curso']).first()
        if curso is None:
            raise CommandError('Curso não encontrado.')
        if not o['guiao'] and not o['situacoes']:
            raise CommandError('Indique --guiao, --situacoes ou ambos.')
        with transaction.atomic():
            if o['guiao']:
                with open(o['guiao'], encoding='utf-8') as f:
                    dados = json.load(f)
                dados.pop('formato', None)
                if exame.validar_guiao(dados) is None:
                    raise CommandError('Guião inválido (ver exame.validar_guiao).')
                config, _ = CourseGradingConfig.objects.get_or_create(course=curso)
                config.exam_script = dados
                config.save(update_fields=['exam_script', 'updated_at'])
                self.stdout.write(f'Guião do exame guardado ({len(dados["partes"])} partes).')
            if o['situacoes']:
                with open(o['situacoes'], encoding='utf-8') as f:
                    lista = json.load(f).get('situacoes') or []
                for s in lista:
                    outra = Situacao.objects.filter(slug=s['slug']).exclude(curso=curso).first()
                    if outra is not None:
                        raise CommandError(f'A situação {s["slug"]} já pertence a outro curso.')
                    extras = dict(s.get('extras') or {}, exame=True)
                    Situacao.objects.update_or_create(slug=s['slug'], defaults=dict(
                        nome=s['nome'][:80], descricao=s['descricao'], papel_tutor=s.get('papel_tutor', '')[:300],
                        frases=s.get('frases') or [], curso=curso, nivel=s.get('nivel', curso.level or 'A1')[:2],
                        duracao_min=s.get('duracao_min', 3), estado=Situacao.ACTIVO, criado_por=curso.teacher,
                        extras=extras))
                self.stdout.write(f'{len(lista)} situações do exame carregadas.')
