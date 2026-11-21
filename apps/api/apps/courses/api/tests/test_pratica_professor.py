"""
Editor de cursos de prática da área do professor (/api/v1/teacher/pratica/): estrutura, unidades,
lições, exercícios no formato normalizado (todos os tipos), áudio, geração com o Claude (simulado)
e ligação ao ecrã da lição do aluno e à lista de verificação do curso.
"""
import json
import shutil
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice.models import (
    ChallengeAttempt, ChallengeOption, ChallengeProgress, PracticeChallenge, PracticeLesson, PracticeUnit,
)
from apps.users.models import User

P = '/api/v1/teacher/pratica/'
PROF = '/api/v1/teacher/'
ALUNO = '/api/v1/student/practice-courses/'

EXEMPLOS = {
    'escolher': {'tipo': 'escolher', 'enunciado': 'What do you say before a shift handover?',
                 'opcoes': [{'texto': 'Let me brief you.', 'certa': True}, {'texto': 'Goodbye forever.', 'certa': False},
                            {'texto': 'I am hungry.', 'certa': False}],
                 'explicacao': '"Let me brief you" é a forma habitual de começar a passagem de turno.'},
    'assistir': {'tipo': 'assistir', 'enunciado': 'Qual destes é o "hard hat"?',
                 'opcoes': [{'texto': 'capacete', 'certa': True}, {'texto': 'luvas', 'certa': False}]},
    'completar': {'tipo': 'completar', 'frase': 'Please [check] the pressure before you start.',
                  'opcoes': [{'texto': 'check', 'certa': True}, {'texto': 'checks', 'certa': False},
                             {'texto': 'checking', 'certa': False}]},
    'traduzir': {'tipo': 'traduzir', 'enunciado': 'A bomba está desligada.', 'resposta': 'The pump is off.',
                 'opcoes': [{'texto': 'The pump is switched off.', 'certa': True}]},
    'ordenar': {'tipo': 'ordenar', 'enunciado': 'Envie o relatório antes da reunião.',
                'resposta': 'Send the report before the meeting'},
    'pares': {'tipo': 'pares', 'pares': [{'a': 'valve', 'b': 'válvula'}, {'a': 'leak', 'b': 'fuga'},
                                         {'a': 'pump', 'b': 'bomba'}]},
    'verdadeiro_falso': {'tipo': 'verdadeiro_falso', 'enunciado': '"Shut down" quer dizer "desligar".',
                         'resposta': 'verdadeiro'},
    'escuta': {'tipo': 'escuta', 'frase': 'The pressure test is at two.', 'enunciado': 'A que horas é o teste?',
               'opcoes': [{'texto': 'Às duas', 'certa': True}, {'texto': 'Às dez', 'certa': False}],
               'audio_url': 'https://exemplo.ao/a.mp3'},
    'pronuncia': {'tipo': 'pronuncia', 'frase': 'Please wear your safety glasses.'},
}
# Conversa curta no fim da lição: a situação e 2 a 3 frases da lição para o aluno usar.
CONVERSA = {'tipo': 'conversa', 'enunciado': 'Passagem de turno com o supervisor.',
            'frases_alvo': ['Let me brief you.', 'Pump 3 is still pending inspection.']}
# Responder em voz alta: pergunta, frase-alvo e exemplo de resposta (que usa a frase-alvo).
RESPONDER = {'tipo': 'responder', 'enunciado': 'When can you send me the shift report?',
             'contexto': 'O supervisor pergunta pelo relatório.', 'frase': "I'll have it ready by",
             'resposta': "I'll have it ready by five o'clock."}
MODOS = {
    'escolher': 'escolha', 'assistir': 'escolha', 'completar': 'banco', 'traduzir': 'escrever', 'ordenar': 'ordenar',
    'pares': 'pares', 'verdadeiro_falso': 'escolha', 'escuta': 'escolha', 'pronuncia': 'falar',
}


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.prof = User.objects.create_user(email='prof-pratica@example.com', name='Prof', password='x12345678',
                                             role='teacher')
        self.outro = User.objects.create_user(email='outro-pratica@example.com', name='Outro', password='x12345678',
                                              role='teacher')
        self.aluno = User.objects.create_user(email='aluno-pratica@example.com', name='Aluno', password='x12345678',
                                              role='student')
        self.admin = User.objects.create_user(email='admin-pratica@example.com', name='Admin', password='x12345678',
                                              role='admin')
        self.curso = Course.objects.create(teacher=self.prof, teacherName='Prof', title='Inglês no Terminal',
                                           description='Curso de prática', category='Oil & Gas', level='B1',
                                           course_type='practice', status='Draft')
        # O curso é de sector: o aluno destes testes já tem o nível básico (regra testada em
        # apps/courses/test_teste_basico.py).
        from django.utils import timezone
        from apps.courses.models import TesteNivelBasico
        TesteNivelBasico.objects.create(user=self.aluno, perguntas=[], expira_em=timezone.now(),
                                        submetido_em=timezone.now(), certas=20, total=20, aprovado=True)
        self.entrar(self.prof)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def nova_unidade(self, titulo='Segurança', curso=None):
        r = self.client.post(f'{P}{(curso or self.curso).id}/unidades/', {'titulo': titulo}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def nova_licao(self, unidade_id, titulo='Passagem de turno'):
        r = self.client.post(f'{P}unidades/{unidade_id}/licoes/', {'titulo': titulo}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def novo_exercicio(self, licao_id, dados):
        r = self.client.post(f'{P}licoes/{licao_id}/exercicios/', dados, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()


class EstruturaUnidadesLicoesTests(Base):
    def test_criar_ordenar_e_apagar_unidades(self):
        a, b, c = self.nova_unidade('Aa'), self.nova_unidade('Bb'), self.nova_unidade('Cc')
        self.assertEqual([a['ordem'], b['ordem'], c['ordem']], [1, 2, 3])
        r = self.client.post(f'{P}{self.curso.id}/unidades/ordem/', {'ids': [c['id'], a['id'], b['id']]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([u['titulo'] for u in r.json()['unidades']], ['Cc', 'Aa', 'Bb'])
        r = self.client.post(f'{P}{self.curso.id}/unidades/ordem/', {'ids': [c['id'], a['id']]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'ordem_invalida')
        r = self.client.patch(f'{P}unidades/{a["id"]}/', {'titulo': 'Aa2', 'descricao': 'Nova'}, format='json')
        self.assertEqual(r.json()['titulo'], 'Aa2')
        self.assertEqual(r.json()['descricao'], 'Nova')
        self.assertEqual(self.client.delete(f'{P}unidades/{c["id"]}/').status_code, 204)
        self.assertEqual(list(PracticeUnit.objects.filter(course=self.curso).order_by('order')
                              .values_list('title', 'order')), [('Aa2', 1), ('Bb', 2)])

    def test_titulo_obrigatorio(self):
        r = self.client.post(f'{P}{self.curso.id}/unidades/', {'titulo': ' '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('titulo', r.json()['details'])

    def test_licoes_criar_mover_ordenar(self):
        u1, u2 = self.nova_unidade('U1'), self.nova_unidade('U2')
        l1, l2, l3 = (self.nova_licao(u1['id'], t) for t in ('L1', 'L2', 'L3'))
        r = self.client.post(f'{P}unidades/{u1["id"]}/licoes/ordem/', {'ids': [l3['id'], l1['id'], l2['id']]},
                             format='json')
        self.assertEqual([l['titulo'] for l in r.json()['licoes']], ['L3', 'L1', 'L2'])
        self.nova_licao(u2['id'], 'M1')
        r = self.client.patch(f'{P}licoes/{l3["id"]}/', {'unidade': u2['id'], 'titulo': 'L3 movida'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['ordem'], 2)
        self.assertEqual(r.json()['unidade']['id'], u2['id'])
        self.assertEqual(list(PracticeLesson.objects.filter(unit_id=u1['id']).order_by('order')
                              .values_list('title', 'order')), [('L1', 1), ('L2', 2)])
        outro_curso = Course.objects.create(teacher=self.prof, title='Outro', course_type='practice')
        u3 = PracticeUnit.objects.create(course=outro_curso, title='X', description='', order=1)
        r = self.client.patch(f'{P}licoes/{l1["id"]}/', {'unidade': str(u3.id)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('unidade', r.json()['details'])
        self.assertEqual(self.client.delete(f'{P}licoes/{l1["id"]}/').status_code, 204)
        self.assertEqual(PracticeLesson.objects.get(id=l2['id']).order, 1)

    def test_estrutura_tipos_e_acerto(self):
        u = self.nova_unidade()
        l = self.nova_licao(u['id'])
        e1 = self.novo_exercicio(l['id'], EXEMPLOS['completar'])
        self.novo_exercicio(l['id'], EXEMPLOS['escolher'])
        self.novo_exercicio(l['id'], EXEMPLOS['completar'])
        for certa in (True, True, True, False):
            ChallengeAttempt.objects.create(user=self.aluno, challenge_id=e1['id'], is_correct=certa)
        r = self.client.get(f'{P}{self.curso.id}/estrutura/')
        self.assertEqual(r.status_code, 200)
        dados = r.json()
        self.assertEqual(dados['curso']['id'], str(self.curso.id))
        self.assertIn('definicoes', dados['curso'])
        licao = dados['unidades'][0]['licoes'][0]
        self.assertEqual(licao['exercicios'], 3)
        self.assertEqual(licao['tipos'], ['Completar', 'Escolher'])
        self.assertEqual(licao['acerto'], 75)
        self.assertEqual(licao['tentativas'], 4)
        ex = self.client.get(f'{P}licoes/{l["id"]}/exercicios/').json()
        self.assertEqual(ex['exercicios'][0]['acerto'], 75)
        self.assertIsNone(ex['exercicios'][1]['acerto'])
        self.assertEqual(ex['exercicios'][1]['tentativas'], 0)
        self.assertEqual(ex['licao']['unidade']['titulo'], 'Segurança')
        self.assertEqual(ex['curso']['titulo'], 'Inglês no Terminal')


class PermissoesTests(Base):
    def test_outro_professor_404_aluno_403_admin_ok(self):
        u = self.nova_unidade()
        l = self.nova_licao(u['id'])
        e = self.novo_exercicio(l['id'], EXEMPLOS['escolher'])
        self.entrar(self.outro)
        for metodo, url in (('get', f'{P}{self.curso.id}/estrutura/'), ('patch', f'{P}unidades/{u["id"]}/'),
                            ('patch', f'{P}licoes/{l["id"]}/'), ('get', f'{P}licoes/{l["id"]}/exercicios/'),
                            ('put', f'{P}exercicios/{e["id"]}/'), ('delete', f'{P}exercicios/{e["id"]}/'),
                            ('post', f'{P}{self.curso.id}/gerar-licao/')):
            self.assertEqual(getattr(self.client, metodo)(url, {}, format='json').status_code, 404, url)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{P}{self.curso.id}/estrutura/').status_code, 403)
        self.entrar(self.admin)
        self.assertEqual(self.client.get(f'{P}{self.curso.id}/estrutura/').status_code, 200)

    def test_curso_video_nao_tem_editor_de_pratica(self):
        video = Course.objects.create(teacher=self.prof, title='Vídeo', course_type='video')
        r = self.client.get(f'{P}{video.id}/estrutura/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'tipo_invalido')


class ExerciciosTests(Base):
    def setUp(self):
        super().setUp()
        self.u = self.nova_unidade()
        self.l = self.nova_licao(self.u['id'])

    def test_todos_os_tipos_ida_e_volta(self):
        for tipo, dados in EXEMPLOS.items():
            ex = self.novo_exercicio(self.l['id'], dados)
            self.assertEqual(ex['tipo'], tipo)
            for chave in ('id', 'ordem', 'enunciado', 'frase', 'opcoes', 'pares', 'resposta', 'explicacao',
                          'audio_url', 'acerto', 'tentativas'):
                self.assertIn(chave, ex)
            for chave in ('enunciado', 'frase', 'resposta'):
                if dados.get(chave):
                    self.assertEqual(ex[chave], dados[chave], f'{tipo}.{chave}')
            if tipo == 'pares':
                self.assertEqual(ex['pares'], dados['pares'])
            # PUT com o que veio de volta não muda nada
            r = self.client.put(f'{P}exercicios/{ex["id"]}/', ex, format='json')
            self.assertEqual(r.status_code, 200, (tipo, r.content))
            novo = r.json()
            for chave in ('tipo', 'enunciado', 'frase', 'resposta', 'pares', 'audio_url', 'explicacao'):
                self.assertEqual(novo[chave], ex[chave], f'{tipo}.{chave}')
            self.assertEqual([(o['texto'], o['certa']) for o in novo['opcoes']],
                             [(o['texto'], o['certa']) for o in ex['opcoes']], tipo)

    def test_mapeamento_no_modelo(self):
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['completar'])
        ch = PracticeChallenge.objects.get(id=ex['id'])
        self.assertEqual(ch.type, 'FILL_BLANK')
        self.assertEqual(ch.question, 'Please ___ the pressure before you start.')
        self.assertEqual([(o.text, o.is_correct) for o in ch.options.order_by('order')],
                         [('check', True), ('checks', False), ('checking', False)])
        self.assertEqual(ex['frase'], 'Please [check] the pressure before you start.')
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['ordenar'])
        ch = PracticeChallenge.objects.get(id=ex['id'])
        self.assertEqual([o.text for o in ch.options.order_by('order')],
                         ['Send', 'the', 'report', 'before', 'the', 'meeting'])
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['pares'])
        self.assertEqual(PracticeChallenge.objects.get(id=ex['id']).options.first().text, 'valve - válvula')
        ex = self.novo_exercicio(self.l['id'], {'tipo': 'escuta', 'frase': 'Shut down the pump.'})
        ch = PracticeChallenge.objects.get(id=ex['id'])
        self.assertEqual(ch.question, 'Escreva o que ouve.')
        self.assertEqual([o.text for o in ch.options.all()], ['Shut down the pump.'])
        self.assertEqual(ex['frase'], 'Shut down the pump.')
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['pronuncia'])
        ch = PracticeChallenge.objects.get(id=ex['id'])
        self.assertEqual(ch.type, 'SPEAKING')
        # Campos não usados vazios
        self.assertEqual((ex['opcoes'], ex['pares'], ex['resposta'], ex['audio_url']), ([], [], '', None))

    def test_validacoes(self):
        casos = [
            ({'tipo': 'completar', 'frase': 'Please check the pressure.'}, 'frase',
             'Ponha entre parênteses rectos a palavra que o aluno tem de escolher.'),
            ({'tipo': 'completar', 'frase': 'Please [check] the [ ].'}, 'frase', None),
            ({'tipo': 'escolher', 'enunciado': 'X?', 'opcoes': [{'texto': 'a', 'certa': True},
                                                              {'texto': 'b', 'certa': True}]},
             'opcoes', 'Marque exactamente uma opção certa.'),
            ({'tipo': 'escolher', 'enunciado': 'X?', 'opcoes': [{'texto': 'a', 'certa': True}]},
             'opcoes', 'Indique pelo menos 2 opções.'),
            ({'tipo': 'pares', 'pares': [{'a': 'x', 'b': 'y'}, {'a': 'z', 'b': 'w'}]}, 'pares',
             'Indique pelo menos 3 pares.'),
            ({'tipo': 'ordenar', 'enunciado': 'Olá', 'resposta': 'Hello'}, 'resposta', None),
            ({'tipo': 'traduzir', 'enunciado': 'Olá'}, 'resposta', None),
            ({'tipo': 'verdadeiro_falso', 'enunciado': 'X'}, 'resposta', None),
            ({'tipo': 'pronuncia'}, 'frase', None),
            ({'tipo': 'conversa', 'enunciado': 'X', 'frase': 'Y'}, 'frases_alvo',
             'Indique entre 2 e 3 frases da lição para o aluno usar.'),
            ({**CONVERSA, 'frases_alvo': ['Check it.', 'check  it.', 'C']}, 'frases_alvo', 'Há frases repetidas.'),
            ({**CONVERSA, 'enunciado': ''}, 'enunciado', 'Descreva a situação da conversa.'),
            ({**RESPONDER, 'frase': ''}, 'frase', 'Indique a frase ou estrutura que a resposta deve usar.'),
            ({**RESPONDER, 'resposta': 'Tomorrow morning.'}, 'resposta',
             'O exemplo de resposta tem de usar a frase-alvo.'),
            ({**RESPONDER, 'enunciado': ''}, 'enunciado', None),
            ({'tipo': 'escuta', 'frase': 'Hi', 'audio_url': 'nao-e-url'}, 'audio_url', None),
            ({'tipo': 'xpto'}, 'tipo', None),
        ]
        for dados, campo, mensagem in casos:
            r = self.client.post(f'{P}licoes/{self.l["id"]}/exercicios/', dados, format='json')
            self.assertEqual(r.status_code, 400, dados)
            corpo = r.json()
            self.assertEqual(corpo['code'], 'validation_error')
            self.assertIn(campo, corpo['details'], dados)
            if mensagem:
                self.assertEqual(corpo['details'][campo][0], mensagem)
                self.assertEqual(corpo['message'], mensagem)
        self.assertEqual(PracticeChallenge.objects.filter(lesson_id=self.l['id']).count(), 0)

    def test_ordenar_e_apagar_exercicios(self):
        a = self.novo_exercicio(self.l['id'], EXEMPLOS['escolher'])
        b = self.novo_exercicio(self.l['id'], EXEMPLOS['traduzir'])
        c = self.novo_exercicio(self.l['id'], EXEMPLOS['pares'])
        r = self.client.post(f'{P}licoes/{self.l["id"]}/exercicios/ordem/', {'ids': [c['id'], a['id'], b['id']]},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([e['tipo'] for e in r.json()['exercicios']], ['pares', 'escolher', 'traduzir'])
        self.assertEqual(self.client.delete(f'{P}exercicios/{c["id"]}/').status_code, 204)
        self.assertEqual(list(PracticeChallenge.objects.filter(lesson_id=self.l['id']).order_by('order')
                              .values_list('order', flat=True)), [1, 2])

    def test_put_troca_o_tipo(self):
        a = self.novo_exercicio(self.l['id'], EXEMPLOS['escolher'])
        r = self.client.put(f'{P}exercicios/{a["id"]}/', EXEMPLOS['ordenar'], format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['tipo'], 'ordenar')
        self.assertEqual(r.json()['id'], a['id'])
        self.assertEqual(r.json()['ordem'], 1)


class AudioTests(Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        u = self.nova_unidade()
        self.l = self.nova_licao(u['id'])

    def test_tts_indisponivel_503(self):
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['pronuncia'])
        with mock.patch('apps.courses.api.teacher.pratica.gerar_audio_tts', return_value=b''):
            r = self.client.post(f'{P}exercicios/{ex["id"]}/audio/')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['code'], 'audio_indisponivel')

    def test_tts_sem_chave_nao_rebenta(self):
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['pronuncia'])
        with mock.patch('apps.practice.services.ai_pronunciation.AIPronunciationAnalyzer',
                        side_effect=RuntimeError('sem chave')):
            r = self.client.post(f'{P}exercicios/{ex["id"]}/audio/')
        self.assertEqual(r.status_code, 503)

    def test_gera_e_guarda(self):
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['pronuncia'])
        with override_settings(MEDIA_ROOT=self.media, USE_S3=False), \
                mock.patch('apps.courses.api.teacher.pratica.gerar_audio_tts', return_value=b'ID3audio') as tts:
            r = self.client.post(f'{P}exercicios/{ex["id"]}/audio/')
        self.assertEqual(r.status_code, 200, r.content)
        tts.assert_called_once_with('Please wear your safety glasses.')
        self.assertIn('/reference-audio/', r.json()['audio_url'])
        self.assertEqual(PracticeChallenge.objects.get(id=ex['id']).reference_audio_url, r.json()['audio_url'])

    def test_so_escuta_e_pronuncia(self):
        ex = self.novo_exercicio(self.l['id'], EXEMPLOS['escolher'])
        self.assertEqual(self.client.post(f'{P}exercicios/{ex["id"]}/audio/').status_code, 400)


class JogadorDoAlunoTests(Base):
    """Exercícios criados por esta API têm de ser jogáveis no ecrã da lição do aluno."""

    def setUp(self):
        super().setUp()
        Course.objects.filter(pk=self.curso.pk).update(status='Published')
        u = self.nova_unidade()
        self.l = self.nova_licao(u['id'])
        self.ex = {tipo: self.novo_exercicio(self.l['id'], dados) for tipo, dados in EXEMPLOS.items()}
        self.ditado = self.novo_exercicio(self.l['id'], {'tipo': 'escuta', 'frase': 'Shut down the pump.',
                                                         'audio_url': 'https://exemplo.ao/pump.mp3'})
        self.entrar(self.aluno)
        r = self.client.get(f'{ALUNO}lessons/{self.l["id"]}/jogar/')
        self.assertEqual(r.status_code, 200, r.content)
        self.jogo = {e['id']: e for e in r.json()['exercicios']}

    def responder(self, ex_id, corpo):
        ChallengeProgress.objects.filter(user=self.aluno).update(updated_at=timezone.now() - timedelta(seconds=30))
        r = self.client.post(f'{ALUNO}challenge-progress/', {'challenge_id': ex_id, **corpo}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['correct']

    def test_cada_tipo_tem_o_que_o_jogador_precisa(self):
        self.assertNotIn('is_correct', json.dumps(self.jogo))
        for tipo, ex in self.ex.items():
            j = self.jogo[ex['id']]
            self.assertEqual(j['modo'], MODOS[tipo], tipo)
            if j['modo'] == 'escolha':
                self.assertGreaterEqual(len(j['opcoes']), 2, tipo)
                self.assertTrue(j['pergunta'], tipo)
        self.assertEqual(self.jogo[self.ex['completar']['id']]['pergunta'],
                         'Please ___ the pressure before you start.')
        self.assertEqual(self.jogo[self.ex['completar']['id']]['espacos'], 1)
        self.assertEqual(self.jogo[self.ex['traduzir']['id']]['pergunta'], 'A bomba está desligada.')
        self.assertEqual(len(self.jogo[self.ex['ordenar']['id']]['palavras']), 6)
        self.assertEqual(sorted(p['texto'] for p in self.jogo[self.ex['pares']['id']]['esquerda']),
                         ['leak', 'pump', 'valve'])
        self.assertEqual(self.jogo[self.ex['pronuncia']['id']]['frase'], 'Please wear your safety glasses.')
        self.assertEqual(self.jogo[self.ex['escuta']['id']]['audio'], 'https://exemplo.ao/a.mp3')
        ditado = self.jogo[self.ditado['id']]
        self.assertEqual(ditado['modo'], 'escrever')
        self.assertNotIn('Shut down the pump', json.dumps(ditado))

    def test_respostas_certas_contam(self):
        def opcao(tipo, texto):
            return next(o['id'] for o in self.jogo[self.ex[tipo]['id']]['opcoes'] if o['texto'] == texto)

        self.assertTrue(self.responder(self.ex['escolher']['id'], {'selected_option': opcao('escolher', 'Let me brief you.')}))
        self.assertTrue(self.responder(self.ex['verdadeiro_falso']['id'],
                                       {'selected_option': opcao('verdadeiro_falso', 'Verdadeiro')}))
        self.assertTrue(self.responder(self.ex['completar']['id'], {'text_answer': 'check'}))
        self.assertFalse(self.responder(self.ex['completar']['id'], {'text_answer': 'checking'}))
        self.assertTrue(self.responder(self.ex['traduzir']['id'], {'text_answer': 'The pump is switched off.'}))
        self.assertTrue(self.responder(self.ditado['id'], {'text_answer': 'Shut down the pump'}))
        ordem = PracticeChallenge.objects.get(id=self.ex['ordenar']['id']).options.order_by('order')
        self.assertTrue(self.responder(self.ex['ordenar']['id'], {'ordered_options': [str(o.id) for o in ordem]}))
        pares = self.jogo[self.ex['pares']['id']]
        traducao = {'valve': 'válvula', 'leak': 'fuga', 'pump': 'bomba'}
        self.assertTrue(self.responder(self.ex['pares']['id'],
                                       {'paired_options': {p['id']: traducao[p['texto']] for p in pares['esquerda']}}))


class VerificacaoTests(Base):
    def test_curso_feito_pela_api_passa_a_verificacao_e_submete(self):
        u = self.nova_unidade()
        l = self.nova_licao(u['id'])
        r = self.client.get(f'{PROF}cursos/{self.curso.id}/verificacao/').json()
        self.assertFalse(r['pode_submeter'])
        for tipo in ('completar', 'pares', 'escuta', 'pronuncia', 'verdadeiro_falso', 'ordenar',
                     'traduzir', 'assistir'):
            self.novo_exercicio(l['id'], EXEMPLOS[tipo])
        self.novo_exercicio(l['id'], {'tipo': 'pares', 'enunciado': '',
                                      'pares': EXEMPLOS['pares']['pares']})
        r = self.client.get(f'{PROF}cursos/{self.curso.id}/verificacao/').json()
        self.assertTrue(r['pode_submeter'], r)
        r = self.client.post(f'{PROF}cursos/{self.curso.id}/submeter/')
        self.assertEqual(r.status_code, 200, r.content)


def _resposta_claude(dados, stop='end_turn'):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type='text', text=json.dumps(dados))])


GERADO = {
    'titulo_sugerido': 'Passar o turno com segurança',
    'exercicios': [
        {**{'enunciado': '', 'frase': '', 'opcoes': [], 'pares': [], 'resposta': '', 'explicacao': 'Porque sim.'},
         **{k: v for k, v in EXEMPLOS[t].items() if k != 'audio_url'}}
        for t in ('pares', 'escolher', 'completar', 'traduzir', 'pronuncia')
    ] + [
        {'tipo': 'pronuncia', 'enunciado': '', 'frase': 'The pump is off.', 'opcoes': [], 'pares': [],
         'resposta': '', 'explicacao': ''},
        {**{'opcoes': [], 'pares': [], 'explicacao': ''}, **RESPONDER},
        {**{'opcoes': [], 'pares': [], 'explicacao': ''}, **RESPONDER,
         'enunciado': 'Is pump 3 ready?', 'frase': 'still pending', 'resposta': 'No, it is still pending inspection.'},
    ] + [
        {'tipo': 'completar', 'enunciado': '', 'frase': 'Sem parênteses aqui.', 'opcoes': [], 'pares': [],
         'resposta': '', 'explicacao': ''},
        {'tipo': 'conversa', 'enunciado': 'X', 'frase': 'Y', 'opcoes': [], 'pares': [], 'resposta': '',
         'explicacao': ''},
    ],
}


class GerarLicaoTests(Base):
    def setUp(self):
        super().setUp()
        self.u = self.nova_unidade('Turnos')
        self.nova_licao(self.u['id'], 'Cumprimentos no turno')
        self.url = f'{P}{self.curso.id}/gerar-licao/'
        self.pedido = {'unidade': self.u['id'], 'objectivo': 'Passar o turno ao colega',
                       'palavras': ['handover', 'pressure'], 'quantos': 8}

    def _cliente(self, resposta=None, erro=None):
        cliente = mock.MagicMock()
        if erro:
            cliente.beta.messages.create.side_effect = erro
        else:
            cliente.beta.messages.create.return_value = resposta
        return mock.patch('apps.courses.api.teacher.gerar_licao._cliente', return_value=cliente), cliente

    def test_gera_valida_e_descarta(self):
        patch, cliente = self._cliente(_resposta_claude(GERADO))
        with patch, override_settings(PRATICA_CLAUDE_MODELO='claude-opus-5-5'):
            r = self.client.post(self.url, self.pedido, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        dados = r.json()
        self.assertEqual(dados['titulo_sugerido'], 'Passar o turno com segurança')
        self.assertEqual(len(dados['exercicios']), 8)
        self.assertEqual(dados['descartados'], 2)
        self.assertNotIn('conversa', [e['tipo'] for e in dados['exercicios']])
        for ex in dados['exercicios']:
            self.assertNotIn('id', ex)
            self.assertIsNone(ex['acerto'])
            self.assertIsNone(ex['tentativas'])
        kwargs = cliente.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'claude-opus-5-5')
        self.assertEqual(kwargs['output_config']['format']['type'], 'json_schema')
        contexto = kwargs['messages'][0]['content']
        for pedaco in ('Turnos', 'Cumprimentos no turno', 'handover', 'Passar o turno ao colega', 'B1'):
            self.assertIn(pedaco, contexto)
        self.assertFalse(PracticeLesson.objects.filter(title='Passar o turno com segurança').exists())

        # Gravar a lição gerada: tudo de uma vez
        r = self.client.post(f'{P}unidades/{self.u["id"]}/licoes/com-exercicios/',
                             {'titulo': dados['titulo_sugerido'], 'exercicios': dados['exercicios']}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['licao']['exercicios'], 8)
        self.assertEqual(r.json()['licao']['ordem'], 2)
        self.assertEqual(len(r.json()['exercicios']), 8)
        self.assertTrue(all(e['id'] for e in r.json()['exercicios']))

    def test_com_exercicios_e_atomico(self):
        exercicios = [EXEMPLOS['escolher'], {'tipo': 'completar', 'frase': 'sem nada'}]
        r = self.client.post(f'{P}unidades/{self.u["id"]}/licoes/com-exercicios/',
                             {'titulo': 'Nova', 'exercicios': exercicios}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('1', r.json()['details']['exercicios'])
        self.assertIn('frase', r.json()['details']['exercicios']['1'])
        self.assertFalse(PracticeLesson.objects.filter(title='Nova').exists())

    def test_erro_da_anthropic_503(self):
        import anthropic
        import httpx2
        erro = anthropic.APIConnectionError(request=httpx2.Request('POST', 'https://api.anthropic.com'))
        patch, _ = self._cliente(erro=erro)
        with patch:
            r = self.client.post(self.url, self.pedido, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['code'], 'ia_indisponivel')

    def test_recusa_ou_corte_503(self):
        patch, _ = self._cliente(_resposta_claude(GERADO, stop='refusal'))
        with patch:
            self.assertEqual(self.client.post(self.url, self.pedido, format='json').status_code, 503)

    def test_sem_chave_503(self):
        with override_settings(ANTHROPIC_API_KEY=''):
            r = self.client.post(self.url, self.pedido, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['code'], 'ia_indisponivel')

    def test_validacao_do_pedido(self):
        r = self.client.post(self.url, {'unidade': 'x', 'objectivo': '', 'quantos': 7}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['details']), {'unidade', 'objectivo', 'quantos'})

    def test_limite_diario_429(self):
        patch, _ = self._cliente(_resposta_claude(GERADO))
        with patch, override_settings(PRATICA_GERAR_LIMITE_DIA=2):
            self.assertEqual(self.client.post(self.url, self.pedido, format='json').status_code, 200)
            self.assertEqual(self.client.post(self.url, self.pedido, format='json').status_code, 200)
            r = self.client.post(self.url, self.pedido, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()['code'], 'limite_geracao')

    def test_so_professores(self):
        self.entrar(self.aluno)
        self.assertEqual(self.client.post(self.url, self.pedido, format='json').status_code, 403)
