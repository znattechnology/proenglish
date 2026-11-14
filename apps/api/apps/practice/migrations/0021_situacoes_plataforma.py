"""
Dados: as 5 situações da conversa que estavam no código passam para a tabela Situacao,
como situações da plataforma, com os mesmos slugs (as sessões antigas guardam o slug em
VapiSession.situation e continuam a apontar para elas).

As competições que já tinham terminado ficam marcadas como avisadas e fechadas (sem prémios);
as activas e as agendadas ficam abertas e o fecho automático (fechar_competicoes) trata delas.
"""
from django.db import migrations
from django.utils import timezone

# Cópia fixa (a migração não deve depender do código que muda).
AREAS = {
    'pedir_relatorio': ('business', 5),
    'reuniao_seguranca': ('petroleum', 5),
    'atender_cliente': ('business', 5),
    'apresentar_equipa': ('general', 3),
    'conversa_livre': ('general', 5),
}
# Cópia fixa de conversa.situacoes.SITUACOES no momento da migração.
SITUACOES = [{'id': 'pedir_relatorio',
  'titulo': 'Pedir um relatório',
  'descricao': 'Pedir e combinar a entrega de um relatório.',
  'minutos_sugeridos': 5,
  'brief': "Role-play: you are the student's manager. You need a report from them. Agree on what the report "
           'must include, the format and the deadline. Ask follow-up questions about dates and content, and '
           'confirm the agreement at the end.',
  'primeira_fala': 'Hi {nome}! I need the monthly report from your team. When can you send it to me?',
  'primeira_fala_simples': 'Hi {nome}! I need a report. When can you send it?',
  'frases': [{'en': 'Could you send me the report by Friday?',
              'pt': 'Pode enviar-me o relatório até sexta-feira?'},
             {'en': 'When is the deadline?', 'pt': 'Qual é o prazo?'},
             {'en': "I'll have it ready on Thursday.", 'pt': 'Vou tê-lo pronto na quinta-feira.'},
             {'en': 'Does it include the figures for last month?',
              'pt': 'Inclui os números do mês passado?'}],
  'palavras': ['report',
               'deadline',
               'send',
               'ready',
               'include',
               'includes',
               'figures',
               'data',
               'monthly',
               'summary',
               'draft',
               'monday',
               'tuesday',
               'wednesday',
               'thursday',
               'friday'],
  'guiao': ['Okay, thank you. What will the report include?',
            'Great. Do you need anything from me to finish it?',
            'Perfect. Could you also send a short summary to the team?',
            "Thanks. Let's confirm: what is the final deadline?",
            'Excellent, that is very clear. Thank you, {nome}. Good job today!']},
 {'id': 'reuniao_seguranca',
  'titulo': 'Reunião de segurança',
  'descricao': 'Explicar um incidente à equipa.',
  'minutos_sugeridos': 6,
  'brief': 'Role-play: you lead a safety meeting (toolbox talk). The student must explain to the team an '
           'incident that happened at work: what happened, where, when, whether anyone was hurt, what was '
           'done immediately and how to prevent it. Ask clear follow-up questions.',
  'primeira_fala': 'Hello {nome}, thanks for joining the safety meeting. Can you tell the team what happened '
                   'during the incident yesterday?',
  'primeira_fala_simples': 'Hello {nome}. Welcome to the safety meeting. What happened yesterday?',
  'frases': [{'en': 'There was an incident on site yesterday.', 'pt': 'Houve um incidente no local ontem.'},
             {'en': 'Nobody was injured.', 'pt': 'Ninguém ficou ferido.'},
             {'en': 'We stopped the work immediately.', 'pt': 'Parámos o trabalho imediatamente.'},
             {'en': 'We need to wear our PPE at all times.', 'pt': 'Temos de usar sempre o EPI.'}],
  'palavras': ['incident',
               'injured',
               'safety',
               'hazard',
               'ppe',
               'helmet',
               'gloves',
               'immediately',
               'stopped',
               'report',
               'procedure',
               'risk',
               'site',
               'supervisor',
               'emergency',
               'leak'],
  'guiao': ['Thank you. Where exactly did it happen?',
            'I see. Was anyone injured?',
            'What did you do immediately after the incident?',
            'Good. What can we do to prevent this in the future?',
            'Thank you, {nome}. That was a clear report. Stay safe!']},
 {'id': 'atender_cliente',
  'titulo': 'Atender um cliente',
  'descricao': 'Responder a uma reclamação.',
  'minutos_sugeridos': 6,
  'brief': 'Role-play: you are an unhappy customer. Your order arrived late and some items are missing. The '
           'student works in customer service and must apologise, ask for details, explain what they will do '
           'and agree on a solution. Be polite but insistent; calm down if the student handles it well.',
  'primeira_fala': "Good morning. I'm calling because my order arrived late and some items are missing. I'm "
                   'not happy. What can you do?',
  'primeira_fala_simples': 'Good morning. My order is late and some items are missing. Can you help me?',
  'frases': [{'en': "I'm sorry for the inconvenience.", 'pt': 'Peço desculpa pelo incómodo.'},
             {'en': 'Could you give me your order number?', 'pt': 'Pode dar-me o número da encomenda?'},
             {'en': "I'll look into it right away.", 'pt': 'Vou verificar isso imediatamente.'},
             {'en': 'We will send the missing items tomorrow.',
              'pt': 'Vamos enviar os artigos em falta amanhã.'}],
  'palavras': ['sorry',
               'apologise',
               'apologize',
               'inconvenience',
               'order',
               'number',
               'delivery',
               'missing',
               'refund',
               'replace',
               'tomorrow',
               'immediately',
               'customer',
               'solution',
               'check'],
  'guiao': ["It's order number 4521. Why was it so late?",
            'And what about the missing items?',
            'When will I receive them?',
            'Can I get a discount for the trouble?',
            'Okay, thank you for your help. That solves my problem.']},
 {'id': 'apresentar_equipa',
  'titulo': 'Apresentar-se à equipa',
  'descricao': 'Diga quem é, o que faz e onde trabalhou.',
  'minutos_sugeridos': 4,
  'brief': "Role-play: it is the student's first day in a new team and you are a friendly colleague. Ask "
           'them to introduce themselves: name, role, experience, previous jobs and what they like about '
           'their work. Show interest and ask natural follow-up questions.',
  'primeira_fala': 'Hi {nome}, welcome to the team! Could you introduce yourself? Tell us about your role '
                   'and where you worked before.',
  'primeira_fala_simples': 'Hi {nome}, welcome to the team! Can you tell us about you?',
  'frases': [{'en': 'My name is ... and I work as ...', 'pt': 'Chamo-me ... e trabalho como ...'},
             {'en': "I'm responsible for ...", 'pt': 'Sou responsável por ...'},
             {'en': 'Before this, I worked at ...', 'pt': 'Antes disto, trabalhei na ...'},
             {'en': "I'm looking forward to working with you.",
              'pt': 'Tenho muito gosto em trabalhar convosco.'}],
  'palavras': ['responsible',
               'experience',
               'role',
               'team',
               'engineer',
               'manager',
               'technician',
               'worked',
               'company',
               'years',
               'project',
               'looking',
               'forward',
               'department'],
  'guiao': ['Nice to meet you! What will you be responsible for here?',
            'Interesting. Where did you work before?',
            'How many years of experience do you have?',
            'What do you enjoy most about your work?',
            'Great to have you here, {nome}. Welcome aboard!']},
 {'id': 'conversa_livre',
  'titulo': 'Conversa livre',
  'descricao': 'Fale do que quiser.',
  'minutos_sugeridos': 5,
  'brief': 'Free conversation: let the student choose the topic. Keep the conversation going with open '
           'questions related to what they say, ideally connected to their work.',
  'primeira_fala': 'Hi {nome}! What would you like to talk about today?',
  'primeira_fala_simples': 'Hi {nome}! What do you want to talk about?',
  'frases': [{'en': 'Could you say that again, please?', 'pt': 'Pode repetir, por favor?'},
             {'en': 'What do you mean by ...?', 'pt': 'O que quer dizer com ...?'},
             {'en': 'In my opinion, ...', 'pt': 'Na minha opinião, ...'},
             {'en': 'Let me think for a second.', 'pt': 'Deixe-me pensar um segundo.'}],
  'palavras': ['opinion',
               'think',
               'because',
               'however',
               'example',
               'usually',
               'weekend',
               'family',
               'work',
               'favourite',
               'favorite',
               'interesting',
               'actually'],
  'guiao': ['That sounds interesting. Can you tell me more?',
            'Why is that important to you?',
            'How does that connect with your work?',
            'What would you like to improve in your English?',
            'Thank you for the chat, {nome}. You did well today!']}]

PAPEIS = {
    'pedir_relatorio': 'O seu chefe, que precisa de um relatório.',
    'reuniao_seguranca': 'O responsável pela reunião de segurança.',
    'atender_cliente': 'Um cliente insatisfeito.',
    'apresentar_equipa': 'Um colega simpático da nova equipa.',
    'conversa_livre': 'Um tutor que segue o tema escolhido pelo aluno.',
}


def criar(apps, schema_editor):
    Situacao = apps.get_model('practice', 'Situacao')
    for ordem, s in enumerate(SITUACOES):
        area, duracao = AREAS.get(s['id'], ('general', 5))
        Situacao.objects.update_or_create(slug=s['id'], defaults={
            'nome': s['titulo'],
            'descricao': s['descricao'],
            'papel_tutor': PAPEIS.get(s['id'], ''),
            'frases': [f['en'] for f in s['frases']],
            'curso': None,
            'area': area,
            'nivel': 'B1',
            'duracao_min': duracao,
            'correccao': 'suave',
            'estado': 'activo',
            'criado_por': None,
            'ordem': ordem,
            'extras': {
                'brief': s['brief'],
                'primeira_fala': s['primeira_fala'],
                'primeira_fala_simples': s['primeira_fala_simples'],
                'frases': s['frases'],
                'palavras': s['palavras'],
                'guiao': s['guiao'],
                'minutos_sugeridos': s['minutos_sugeridos'],
            },
        })

    # Só as competições que já terminaram ficam fechadas sem prémios; as activas e as
    # agendadas continuam abertas (o fecho automático trata delas).
    Competition = apps.get_model('practice', 'Competition')
    agora = timezone.now()
    Competition.objects.filter(end_date__lt=agora, fechada_em__isnull=True).update(
        inicio_notificado=True, fechada_em=agora)


def desfazer(apps, schema_editor):
    Situacao = apps.get_model('practice', 'Situacao')
    Situacao.objects.filter(criado_por__isnull=True, slug__in=list(AREAS)).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('practice', '0020_professor_situacoes_conquistas_competicoes'),
    ]

    operations = [migrations.RunPython(criar, desfazer)]
