"""Conteúdo inicial do site (verdadeiro), já publicado para que GET /api/v1/site/ funcione logo."""
from django.db import migrations
from django.utils import timezone

TOPO = {
    'etiqueta': 'Novo: conversa com tutor de IA',
    'titulo': 'Fale inglês no seu trabalho',
    'texto': 'Cursos por área profissional, 15 minutos por dia e conversa com um tutor de IA.',
    'botao_principal': {'texto': 'Experimentar grátis', 'href': '/signup'},
    'botao_secundario': {'texto': 'Ver como funciona', 'href': '#como-funciona'},
    'mostrar_nota': True,
}

PRECOS = {
    'mostrar_anual': True,
    'planos': {
        'FREE': {'subtitulo': 'Para começar sem pagar', 'etiqueta': None, 'botao': 'Começar grátis',
                 'nota_angola': None},
        'PREMIUM': {'subtitulo': 'Para quem estuda todos os dias', 'etiqueta': None, 'botao': 'Escolher Premium',
                    'nota_angola': 'Pague em kwanzas por Multicaixa Express.'},
        'PREMIUM_PLUS': {'subtitulo': 'Todos os cursos, incluindo os Premium Plus', 'etiqueta': None,
                         'botao': 'Escolher Premium Plus',
                         'nota_angola': 'Pague em kwanzas por Multicaixa Express.'},
    },
}

DEFINICOES = {
    'titulo': 'ProEnglish: inglês para profissionais em Angola',
    'descricao': ('Cursos de inglês por área profissional, 15 minutos por dia e conversa com um tutor de IA. '
                  'Pague em kwanzas por Multicaixa Express.'),
    'palavras_chave': 'inglês, inglês profissional, cursos de inglês, Angola, Luanda, tutor de IA',
    'ga_id': None, 'pixel_id': None, 'email': None, 'telefone': None,
    'instagram': None, 'linkedin': None, 'facebook': None,
}

NUMEROS = [
    # (valor, texto, onde, fonte)
    ('', 'profissionais registados', 'topo', 'utilizadores'),
    ('', 'áreas profissionais', 'topo', 'areas'),
    ('15 min', 'por dia chegam', 'topo', 'manual'),
]

SERVICOS = [
    ('Cursos por área', 'Inglês para a sua área profissional, com as palavras e as situações do dia-a-dia '
                        'de trabalho.', 'livro', None),
    ('Laboratório de prática', 'Exercícios curtos de ouvir, falar, escrever e completar, para praticar '
                               '15 minutos por dia.', 'laboratorio', None),
    ('Tutor de IA', 'Converse em inglês, por voz, com um tutor de IA que corrige e ajuda a ganhar confiança.',
     'bot', None),
    ('Certificados', 'Nos planos pagos, ao concluir um curso com nota final suficiente recebe um certificado '
                     'que qualquer pessoa pode verificar online.',
     'certificado', '/verify'),
]

PERGUNTAS = [
    ('Preciso de cartão para começar?',
     'Não. O plano Gratuito não pede pagamento: basta criar a conta e começar a aprender.'),
    ('Como posso pagar um plano?',
     'Paga em kwanzas, por Multicaixa Express. Não precisa de cartão internacional.'),
    ('Como se verifica um certificado?',
     'Cada certificado tem um número único e pode ser verificado por qualquer pessoa, por exemplo um '
     'empregador, na página Verificar certificado, no fim do site.'),
    ('Funciona no telemóvel?',
     'Sim. Pode estudar no navegador do telemóvel e instalar a app pelo navegador, sem passar pela loja de '
     'aplicações.'),
    ('Como cancelo o meu plano?',
     'Não há renovações automáticas: o plano só renova quando paga o período seguinte. Se não pagar, '
     'passa para o plano Gratuito no fim do período.'),
]


def semear(apps, schema_editor):
    from apps.site.conteudo import foto

    Configuracao = apps.get_model('site', 'ConfiguracaoSite')
    Numero = apps.get_model('site', 'Numero')
    Empresa = apps.get_model('site', 'Empresa')
    Servico = apps.get_model('site', 'Servico')
    Pergunta = apps.get_model('site', 'Pergunta')

    if Configuracao.objects.filter(pk=1).exists():
        return
    cfg = Configuracao.objects.create(pk=1, topo=TOPO, precos=PRECOS, definicoes=DEFINICOES, alterado_em={})
    for i, (valor, texto, onde, fonte) in enumerate(NUMEROS, start=1):
        Numero.objects.create(valor=valor, texto=texto, onde=onde, fonte=fonte, mostrar=True, ordem=i)
    for i, (titulo, texto, icone, leva_a) in enumerate(SERVICOS, start=1):
        Servico.objects.create(titulo=titulo, texto=texto, icone=icone, leva_a=leva_a or '', ordem=i)
    for i, (pergunta, resposta) in enumerate(PERGUNTAS, start=1):
        Pergunta.objects.create(pergunta=pergunta, resposta=resposta, ordem=i)
    # Empresas parceiras: nenhuma (só se mostram as que tenham acordo assinado).
    cfg.publicado = foto(cfg, Numero, Empresa, Servico, Pergunta)
    cfg.publicado_em = timezone.now()
    cfg.save()


def desfazer(apps, schema_editor):
    for nome in ('Numero', 'Empresa', 'Servico', 'Pergunta', 'ConfiguracaoSite'):
        apps.get_model('site', nome).objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('site', '0001_initial')]
    operations = [migrations.RunPython(semear, desfazer)]
