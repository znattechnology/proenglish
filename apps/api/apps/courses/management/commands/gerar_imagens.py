"""
Gera, aprova e publica as imagens de um manifesto (ver apps/courses/imagens_ia.py).

    ./venv/bin/python manage.py gerar_imagens docs/conteudo/imagens/piloto.json --simular
    ./venv/bin/python manage.py gerar_imagens docs/conteudo/imagens/piloto.json --ids estilo-a,estilo-b --variantes 2 --limite-usd 1
    ./venv/bin/python manage.py gerar_imagens docs/conteudo/imagens/piloto.json --aprovar estilo-a=2
    ./venv/bin/python manage.py gerar_imagens docs/conteudo/imagens/piloto.json --publicar estilo-a
    ./venv/bin/python manage.py gerar_imagens docs/conteudo/imagens/piloto.json --custos

A chave da API vem de GEMINI_API_KEY (no .env), nunca da linha de comandos. As imagens geradas ficam
em media/imagens-ia (fora do git); o registo do custo fica em docs/conteudo/imagens/custos.csv.
"""
import os

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.courses import imagens_ia as ia

RAIZ = os.path.normpath(os.path.join(settings.BASE_DIR, '..', '..'))


class Command(BaseCommand):
    help = 'Gera com o Nano Banana as imagens de um manifesto, com registo e limite de custo.'

    def add_arguments(self, parser):
        parser.add_argument('manifesto')
        parser.add_argument('--ids', help='Só estas imagens (separadas por vírgulas).')
        parser.add_argument('--variantes', type=int, default=1)
        parser.add_argument('--limite-usd', type=float, default=2.0, help='Gasto máximo desta execução.')
        parser.add_argument('--simular', action='store_true', help='Mostra o que geraria e o custo, sem pedir nada.')
        parser.add_argument('--api', choices=['interacoes', 'generate'], default='interacoes')
        parser.add_argument('--aprovar', help='id=variante: a imagem escolhida (serve de referência às outras).')
        parser.add_argument('--publicar', help='Ids aprovados a enviar para o bucket (R2), separados por vírgulas.')
        parser.add_argument('--custos', action='store_true', help='Total gasto até agora.')
        parser.add_argument('--saida', default=os.path.join(settings.BASE_DIR, 'media', 'imagens-ia'))
        parser.add_argument('--registo', default=os.path.join(RAIZ, 'docs', 'conteudo', 'imagens', 'custos.csv'))

    def handle(self, *args, **o):
        try:
            self._handle(o)
        except ia.ErroImagens as e:
            raise CommandError(str(e))

    def _handle(self, o):
        if o['custos']:
            total, n = ia.total_gasto(o['registo'])
            self.stdout.write(f'{n} imagens geradas, cerca de US$ {total:.2f}.')
            return
        if o['aprovar']:
            ident, _, variante = o['aprovar'].partition('=')
            destino = ia.aprovar(o['saida'], ident, variante)
            self.stdout.write(self.style.SUCCESS(f'Aprovada: {destino}'))
            return
        if o['publicar']:
            for ident in o['publicar'].split(','):
                self.stdout.write(self.style.SUCCESS(f'{ident}: {ia.publicar(o["saida"], ident.strip())}'))
            return

        manifesto = ia.ler_manifesto(o['manifesto'])
        itens = manifesto['imagens']
        if o['ids']:
            pedidos = [i.strip() for i in o['ids'].split(',')]
            desconhecidos = set(pedidos) - {i['id'] for i in itens}
            if desconhecidos:
                raise CommandError('Ids que não estão no manifesto: ' + ', '.join(sorted(desconhecidos)))
            itens = [i for i in itens if i['id'] in pedidos]
        previsto = sum(ia.custo_previsto(i) for i in itens) * o['variantes']
        if o['simular']:
            for i in itens:
                self.stdout.write(f'{i["id"]}: {i.get("modelo", "pro")} {i.get("tamanho", "1K")} {i.get("proporcao", "1:1")}, '
                                  f'{len(i.get("referencias") or [])} referências, US$ {ia.custo_previsto(i):.4f} cada')
            self.stdout.write(f'{len(itens)} imagens × {o["variantes"]} variantes: cerca de US$ {previsto:.2f}. Nada foi pedido.')
            return
        chave = config('GEMINI_API_KEY', default='')
        if not chave:
            raise CommandError('Falta GEMINI_API_KEY no .env da API.')
        gasto = ia.gerar(manifesto, itens, o['saida'], o['registo'], chave, variantes=o['variantes'],
                         limite_usd=o['limite_usd'], api=o['api'], escrever=self.stdout.write)
        total, _ = ia.total_gasto(o['registo'])
        self.stdout.write(self.style.SUCCESS(f'Gasto nesta execução: cerca de US$ {gasto:.2f}. Total até agora: US$ {total:.2f}.'))
