"""Corrige o conteúdo inicial: a página de verificação é /verify e o certificado exige nota final."""
from django.db import migrations

TEXTO_ANTIGO = ('Nos planos pagos, cada curso concluído dá um certificado que qualquer pessoa pode '
                'verificar online.')
TEXTO_NOVO = ('Nos planos pagos, ao concluir um curso com nota final suficiente recebe um certificado '
              'que qualquer pessoa pode verificar online.')
RESPOSTA_ANTIGA_FIM = 'empregador, em /certificados/verificar.'
RESPOSTA_NOVA_FIM = 'empregador, na página Verificar certificado, no fim do site.'


def _servico(d):
    if d.get('leva_a') == '/certificados/verificar':
        d['leva_a'] = '/verify'
    if d.get('texto') == TEXTO_ANTIGO:
        d['texto'] = TEXTO_NOVO


def _pergunta(d):
    if (d.get('resposta') or '').endswith(RESPOSTA_ANTIGA_FIM):
        d['resposta'] = d['resposta'][: -len(RESPOSTA_ANTIGA_FIM)] + RESPOSTA_NOVA_FIM


def _numero(d):
    if d.get('fonte') == 'utilizadores' and d.get('texto') == 'profissionais a aprender':
        d['texto'] = 'profissionais registados'


def corrigir(apps, schema_editor):
    Servico = apps.get_model('site', 'Servico')
    Pergunta = apps.get_model('site', 'Pergunta')
    Numero = apps.get_model('site', 'Numero')
    Config = apps.get_model('site', 'ConfiguracaoSite')
    for s in Servico.objects.all():
        d = {'leva_a': s.leva_a, 'texto': s.texto}
        _servico(d)
        if d != {'leva_a': s.leva_a, 'texto': s.texto}:
            s.leva_a, s.texto = d['leva_a'], d['texto']
            s.save(update_fields=['leva_a', 'texto'])
    for p in Pergunta.objects.all():
        d = {'resposta': p.resposta}
        _pergunta(d)
        if d['resposta'] != p.resposta:
            p.resposta = d['resposta']
            p.save(update_fields=['resposta'])
    for n in Numero.objects.all():
        d = {'fonte': n.fonte, 'texto': n.texto}
        _numero(d)
        if d['texto'] != n.texto:
            n.texto = d['texto']
            n.save(update_fields=['texto'])
    for cfg in Config.objects.all():
        pub = cfg.publicado or {}
        for s in pub.get('servicos', []):
            _servico(s)
        for p in pub.get('perguntas', []):
            _pergunta(p)
        for n in pub.get('numeros', []):
            _numero(n)
        cfg.publicado = pub
        cfg.save(update_fields=['publicado'])


class Migration(migrations.Migration):
    dependencies = [('site', '0002_conteudo_inicial')]
    operations = [migrations.RunPython(corrigir, migrations.RunPython.noop)]
