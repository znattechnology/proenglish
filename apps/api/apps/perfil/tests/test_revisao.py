"""
Revisão de hoje: agenda (agenda.py), sessão e respostas (revisao.py), erros das lições (signals.py),
conversa e API (/api/v1/student/revisao/). O Claude é sempre simulado.

    ./venv/bin/python manage.py test apps.perfil.tests.test_revisao
"""
from datetime import datetime, timedelta, timezone as dt_tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.perfil import agenda, revisao, servico
from apps.perfil.models import ExerciciosPadrao, ItemBanco, PadraoErro, RespostaRevisao
from apps.practice.limite_licoes import hoje_luanda, inicio_do_dia
from apps.practice.models import (ChallengeAttempt, ChallengeOption, DailyStudyLog, PracticeChallenge,
                                  PracticeLesson, PracticeUnit, TentativaPronuncia, UserProgress, VapiSession)

User = get_user_model()
R = '/api/v1/student/revisao/'

CLAUDE_OK = {'exercicios': [
    {'tipo': 'escolher', 'instrucao': 'Escolha a forma certa', 'frase': 'She ___ the report every Monday.',
     'opcoes': ['send', 'sends', 'sending'], 'resposta': 'sends', 'traducao': 'Ela envia o relatório todas as segundas.',
     'explicacao': 'Com he/she/it o verbo leva -s.'},
    {'tipo': 'completar', 'instrucao': 'Complete a frase', 'frase': 'He ___ in the control room.', 'opcoes': [],
     'resposta': 'works', 'traducao': 'Ele trabalha na sala de controlo.', 'explicacao': 'Terceira pessoa: -s.'},
    {'tipo': 'dizer', 'instrucao': 'Diga em voz alta', 'frase': 'The pump needs a new valve.', 'opcoes': [],
     'resposta': 'x', 'traducao': 'A bomba precisa de uma válvula nova.', 'explicacao': 'needs, com -s.'},
    {'tipo': 'escolher', 'instrucao': 'Mau', 'frase': 'Sem espaço.', 'opcoes': ['a', 'b'], 'resposta': 'a',
     'traducao': '', 'explicacao': ''},
]}


def _aluno(email='f4a-aluno@example.com', role='student'):
    return User.objects.create_user(email=email, name='Ana Maria', password='x', role=role)


def _item(user, texto, traducao='', estado=ItemBanco.VISTA, **campos):
    item = servico.registar_item(user, texto, traducao)
    for k, v in dict(estado=estado, **campos).items():
        setattr(item, k, v)
    item.save()
    return item


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

class AgendaTests(TestCase):

    def test_primeira_revisao_por_nota(self):
        intervalos = [agenda.proximo_estado(None, None, n)[2] for n in agenda.NOTAS]
        self.assertEqual(intervalos, [1, 1, 3, 8])
        self.assertLess(agenda.proximo_estado(None, None, 'facil')[1], agenda.proximo_estado(None, None, 'errei')[1])

    def test_intervalos_crescem_com_acertos_e_caem_com_erro(self):
        s = d = None
        vistos = []
        for _ in range(5):
            s, d, i = agenda.proximo_estado(s, d, 'certo', s)
            vistos.append(i)
        self.assertEqual(vistos, sorted(vistos))
        self.assertGreater(vistos[-1], 20)
        s2, d2, i2 = agenda.proximo_estado(s, d, 'errei', s)
        self.assertEqual(i2, 1)
        self.assertAlmostEqual(s2, s * agenda.FACTOR_ERRO, places=3)
        self.assertGreater(d2, d)
        # facil > certo > dificil a partir do mesmo estado
        f, c, h = (agenda.proximo_estado(5.0, 5.0, n, 5.0)[0] for n in ('facil', 'certo', 'dificil'))
        self.assertGreater(f, c)
        self.assertGreater(c, h)
        self.assertGreater(h, 5.0)

    def test_retencao_e_limites(self):
        self.assertAlmostEqual(agenda.retencao(10, 10), 0.9)
        s, d = 300.0, 1.0
        for _ in range(5):
            s, d, i = agenda.proximo_estado(s, d, 'facil', s)
        self.assertLessEqual(i, agenda.INTERVALO_MAX)
        self.assertGreaterEqual(d, 1.0)
        s, d = 1.0, 10.0
        for _ in range(5):
            s, d, _ = agenda.proximo_estado(s, d, 'errei', s)
        self.assertLessEqual(d, 10.0)
        self.assertGreaterEqual(s, agenda.S_MIN)
        with self.assertRaises(ValueError):
            agenda.proximo_estado(None, None, 'talvez')

    def test_dia_e_o_de_luanda(self):
        # 23:30 UTC = 00:30 do dia seguinte em Luanda (UTC+1).
        agora = datetime(2026, 3, 10, 23, 30, tzinfo=dt_tz.utc)
        self.assertEqual(hoje_luanda(agora).isoformat(), '2026-03-11')
        self.assertEqual(agenda.para_o_dia(1, agora), inicio_do_dia(hoje_luanda(agora) + timedelta(days=1)))
        self.assertEqual(agenda.para_o_dia(1, agora).astimezone(dt_tz.utc), datetime(2026, 3, 11, 23, 0, tzinfo=dt_tz.utc))
        u = _aluno()
        i = _item(u, 'Check the valve.', proxima_revisao=datetime(2026, 3, 11, 22, 0, tzinfo=dt_tz.utc))
        self.assertTrue(agenda.esta_para_hoje(i, agora))  # 23:00 em Luanda, ainda dia 11
        i.proxima_revisao = datetime(2026, 3, 11, 23, 0, tzinfo=dt_tz.utc)
        self.assertFalse(agenda.esta_para_hoje(i, agora))

    def test_aplicar_marca_meia_noite_de_luanda(self):
        u = _aluno()
        i = _item(u, 'Check the valve.')
        agora = timezone.now()
        intervalo = agenda.aplicar(i, 'certo', agora)
        self.assertEqual(intervalo, 3)
        self.assertEqual(i.proxima_revisao, agenda.para_o_dia(3, agora))
        self.assertEqual((i.repeticoes, i.lapsos), (1, 0))
        agenda.aplicar(i, 'errei', agora)
        self.assertEqual((i.repeticoes, i.lapsos), (2, 1))
        self.assertEqual(i.proxima_revisao, agenda.para_o_dia(1, agora))


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------

class SessaoTests(TestCase):

    def setUp(self):
        cache.clear()
        self.u = _aluno()
        self.agora = timezone.now()

    def test_ordem_devidos_depois_novos_e_limites(self):
        ontem = agenda.para_o_dia(-1, self.agora)
        ha_tres = agenda.para_o_dia(-3, self.agora)
        recente = _item(self.u, 'Please send the invoice today.', 'Envie a fatura hoje.', proxima_revisao=ontem)
        antigo = _item(self.u, 'The meeting starts at nine.', 'A reunião começa às nove.', proxima_revisao=ha_tres)
        _item(self.u, 'Futuro distante.', proxima_revisao=agenda.para_o_dia(5, self.agora))
        novos = [_item(self.u, f'New phrase number {n} here.', f'Frase nova {n}.') for n in range(12)]
        s = revisao.sessao_de_hoje(self.u, self.agora, com_padroes=False)
        ids = [e['item_id'] for e in s['exercicios']]
        self.assertEqual(ids[:2], [antigo.pk, recente.pk])
        self.assertEqual(s['para_rever'], 2)
        self.assertEqual(s['novos'], revisao.NOVOS_POR_DIA)
        self.assertEqual(ids[2:], [n.pk for n in novos[:revisao.NOVOS_POR_DIA]])
        self.assertLessEqual(s['total'], revisao.MAX_ITENS)
        # Pelo menos metade falada.
        faladas = sum(1 for e in s['exercicios'] if e['forma'] == revisao.OUVIR)
        self.assertGreaterEqual(faladas, (s['total'] + 1) // 2)
        self.assertTrue(all(e['nova'] for e in s['exercicios'][2:]))

    def test_novos_por_dia_descontam_os_ja_introduzidos(self):
        for n in range(6):
            _item(self.u, f'Old phrase {n} was here.', introduzida_em=self.agora,
                  proxima_revisao=agenda.para_o_dia(2, self.agora))
        for n in range(5):
            _item(self.u, f'New phrase {n} is here.')
        devidos, novos = revisao.itens_para_hoje(self.u, self.agora)
        self.assertEqual((len(devidos), len(novos)), (0, revisao.NOVOS_POR_DIA - 6))

    def test_mais_devidos_que_o_limite(self):
        for n in range(15):
            _item(self.u, f'Due phrase {n} today.', proxima_revisao=agenda.para_o_dia(-n, self.agora))
        _item(self.u, 'Uma nova.')
        s = revisao.sessao_de_hoje(self.u, self.agora, com_padroes=False)
        self.assertEqual((s['total'], s['para_rever'], s['novos']), (revisao.MAX_ITENS, revisao.MAX_ITENS, 0))
        self.assertEqual(s['minutos'], 4)

    def test_formas_por_estado(self):
        vista = _item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        self.assertEqual(revisao.forma_para(vista), revisao.ESCOLHER)
        alta = _item(self.u, 'I will finish the report.', 'Vou acabar o relatório.', estado=ItemBanco.COM_AJUDA)
        self.assertEqual(revisao.forma_para(alta), revisao.TRADUZIR)
        alta.repeticoes = 1
        self.assertEqual(revisao.forma_para(alta), revisao.OUVIR)
        sem_traducao = _item(self.u, 'valve')
        self.assertEqual(revisao.formas_possiveis(sem_traducao), [revisao.OUVIR])
        self.assertEqual(revisao.forma_para(sem_traducao), revisao.OUVIR)

    def test_exercicios_construidos_sem_ia(self):
        a = _item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        _item(self.u, 'The truck is late.', 'O camião está atrasado.')
        dia = hoje_luanda(self.agora)
        c = revisao.exercicio_de_item(a, revisao.COMPLETAR, dia)
        self.assertEqual(c['frase_com_espaco'], 'Could you check the ____?')
        self.assertIsNone(c['texto_en'])
        e = revisao.exercicio_de_item(a, revisao.ESCOLHER, dia)
        self.assertEqual(len(e['opcoes']), 4)
        self.assertIn('Pode verificar a pressão?', e['opcoes'])
        self.assertIn('O camião está atrasado.', e['opcoes'])
        self.assertEqual(e['opcoes'], revisao.exercicio_de_item(a, revisao.ESCOLHER, dia)['opcoes'])  # estável no dia
        t = revisao.exercicio_de_item(a, revisao.TRADUZIR, dia)
        self.assertEqual((t['texto_en'], t['audio_texto'], t['traducao']), (None, None, 'Pode verificar a pressão?'))

    def test_padroes_no_fim_ate_dois(self):
        for chave in ('third_person_s', 'past_simple', 'articles'):
            PadraoErro.objects.create(user=self.u, chave=chave, descricao='Descrição', ocorrencias=2)
        _item(self.u, 'Please send the invoice today.', 'Envie a fatura hoje.')
        with mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', return_value=CLAUDE_OK) as m:
            s = revisao.sessao_de_hoje(self.u, self.agora)
        self.assertEqual(m.call_count, 2)
        self.assertEqual([e['origem'] for e in s['exercicios']], ['item', 'padrao', 'padrao'])
        self.assertLessEqual(s['total'], revisao.MAX_ITENS + revisao.MAX_PADROES)


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------

class RespostaTests(TestCase):

    def setUp(self):
        cache.clear()
        self.u = _aluno()

    def test_traducao_tolerante(self):
        certa = 'Could you send me the report by Friday?'
        for resposta, esperado in [('could you send me the report by friday', True),
                                   ('Could you send me the reprot by Friday?', True),
                                   ('Coud you send me the report by friday', True),
                                   ('The pump is broken.', False), ('', False)]:
            with self.subTest(resposta=resposta):
                self.assertEqual(revisao.validar(revisao.TRADUZIR, resposta, certa)[0], esperado)
        self.assertTrue(revisao.validar(revisao.TRADUZIR, "I'll have it ready.", 'I will have it ready.')[0])
        self.assertTrue(revisao.validar(revisao.COMPLETAR, 'Pressure', 'pressure')[0])
        self.assertFalse(revisao.validar(revisao.COMPLETAR, 'valve', 'pressure')[0])
        self.assertTrue(revisao.validar(revisao.ESCOLHER, 'pode verificar a pressão', 'Pode verificar a pressão?')[0])

    def test_nota_deduzida(self):
        n = revisao.nota_de
        self.assertEqual(n(revisao.TRADUZIR, False), 'errei')
        self.assertEqual(n(revisao.TRADUZIR, True, 8, 1.0), 'facil')
        self.assertEqual(n(revisao.TRADUZIR, True, 20, 1.0), 'certo')
        self.assertEqual(n(revisao.TRADUZIR, True, 8, 0.85), 'dificil')
        self.assertEqual(n(revisao.TRADUZIR, True, 8, 1.0, pistas=1), 'dificil')
        self.assertEqual(n(revisao.ESCOLHER, True, 3, 1.0), 'certo')
        self.assertEqual(n(revisao.ESCOLHER, True, 30, 1.0), 'dificil')
        self.assertEqual(n(revisao.OUVIR, True, nota_fala=95), 'facil')
        self.assertEqual(n(revisao.OUVIR, True, nota_fala=80), 'certo')
        self.assertEqual(n(revisao.OUVIR, True, nota_fala=60), 'dificil')

    def test_resposta_certa_sobe_agenda_pontos_e_minutos(self):
        i = _item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        r = revisao.responder(self.u, f'item:{i.pk}', revisao.ESCOLHER, 'Pode verificar a pressão?', segundos=6)
        self.assertTrue(r['correcta'])
        self.assertEqual((r['nota'], r['pontos'], r['estado_depois'], r['subiu']), ('certo', 2, 'reconhecida', True))
        i.refresh_from_db()
        self.assertEqual((i.estado, i.repeticoes), ('reconhecida', 1))
        self.assertIsNotNone(i.introduzida_em)
        self.assertEqual(i.proxima_revisao, agenda.para_o_dia(3))
        self.assertEqual(UserProgress.objects.get(user=self.u).points, 2)
        self.assertAlmostEqual(DailyStudyLog.objects.get(user=self.u).lesson_minutes, 0.1)
        # Segunda resposta ao mesmo exercício no mesmo dia: não conta.
        r2 = revisao.responder(self.u, f'item:{i.pk}', revisao.ESCOLHER, 'Pode verificar a pressão?', segundos=6)
        self.assertFalse(r2['contou'])
        self.assertEqual(r2['pontos'], 0)
        i.refresh_from_db()
        self.assertEqual(i.repeticoes, 1)
        self.assertEqual(UserProgress.objects.get(user=self.u).points, 2)

    def test_estado_nunca_desce_nem_chega_a_sozinho(self):
        i = _item(self.u, 'I will finish the report.', 'Vou acabar o relatório.', estado=ItemBanco.COM_AJUDA)
        r = revisao.responder(self.u, f'item:{i.pk}', revisao.ESCOLHER, 'Outra coisa', segundos=5)
        self.assertFalse(r['correcta'])
        self.assertEqual((r['nota'], r['estado_depois'], r['pontos']), ('errei', 'com_ajuda', 0))
        i.refresh_from_db()
        self.assertEqual(i.estado, 'com_ajuda')
        self.assertEqual(i.proxima_revisao, agenda.para_o_dia(1))
        j = _item(self.u, 'The valve is closed.', 'A válvula está fechada.', estado=ItemBanco.SOZINHO)
        revisao.responder(self.u, f'item:{j.pk}', revisao.TRADUZIR, 'The valve is closed.', segundos=5)
        j.refresh_from_db()
        self.assertEqual(j.estado, 'sozinho')
        k = _item(self.u, 'Send it now.', 'Envie agora.', estado=ItemBanco.RECONHECIDA)
        revisao.responder(self.u, f'item:{k.pk}', revisao.TRADUZIR, 'Send it now', segundos=5)
        k.refresh_from_db()
        self.assertEqual(k.estado, 'com_ajuda')  # o máximo na revisão

    def test_forma_impossivel_ou_item_de_outro(self):
        i = _item(self.u, 'valve')
        with self.assertRaises(revisao.ExercicioInvalido):
            revisao.responder(self.u, f'item:{i.pk}', revisao.TRADUZIR, 'valve')
        outro = _aluno('f4a-outro@example.com')
        with self.assertRaises(revisao.ExercicioInvalido):
            revisao.responder(outro, f'item:{i.pk}', revisao.OUVIR, 'valve')
        with self.assertRaises(revisao.ExercicioInvalido):
            revisao.responder(self.u, 'item:abc', revisao.ESCOLHER, 'x')

    def test_resumo_do_fim(self):
        a = _item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        b = _item(self.u, 'The truck is late.', 'O camião está atrasado.')
        _item(self.u, 'Due tomorrow phrase.', proxima_revisao=agenda.para_o_dia(1))
        inicio = timezone.now()
        revisao.responder(self.u, f'item:{a.pk}', revisao.ESCOLHER, 'Pode verificar a pressão?', segundos=10)
        revisao.responder(self.u, f'item:{b.pk}', revisao.ESCOLHER, 'Errado', segundos=10)
        t = revisao.terminar(self.u, inicio)
        self.assertEqual((t['respondidos'], t['acertos'], t['pontos']), (2, 1, 2))
        self.assertEqual([s['texto'] for s in t['subiram']], ['Could you check the pressure?'])
        # amanhã: b (errou) + o que já estava para amanhã
        self.assertEqual(t['amanha'], 2)
        self.assertIn('minutos_hoje', t['meta'])


# ---------------------------------------------------------------------------
# Padrões (Claude simulado)
# ---------------------------------------------------------------------------

class PadraoTests(TestCase):

    def setUp(self):
        cache.clear()
        self.u = _aluno()
        self.p = PadraoErro.objects.create(user=self.u, chave='third_person_s', descricao='Esquece o -s',
                                           exemplo_errado='He go to the site.', exemplo_certo='He goes to the site.')

    def test_gera_uma_vez_e_reutiliza_entre_alunos(self):
        with mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', return_value=CLAUDE_OK) as m:
            lista = revisao.exercicios_do_padrao(self.p)
            outro = _aluno('f4a-outro@example.com')
            p2 = PadraoErro.objects.create(user=outro, chave='third_person_s', descricao='Outra descrição')
            self.assertEqual(revisao.exercicios_do_padrao(p2), lista)
        self.assertEqual(m.call_count, 1)
        # Só a chave e a descrição vão para o Claude (nada do que o aluno disse).
        self.assertEqual(m.call_args.args, ('third_person_s', 'Esquece o -s'))
        self.assertEqual([e['tipo'] for e in lista], ['escolher', 'completar', 'dizer'])  # o inválido saiu
        self.assertEqual(lista[2]['resposta'], 'The pump needs a new valve.')
        self.assertTrue(ExerciciosPadrao.objects.filter(chave='third_person_s').exists())

    def test_falha_sem_exercicios_e_sem_repetir(self):
        with mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', side_effect=RuntimeError('rede')) as m:
            self.assertEqual(revisao.exercicios_do_padrao(self.p), [])
            self.assertEqual(revisao.exercicios_do_padrao(self.p), [])
            _item(self.u, 'Check the valve now.', 'Verifique a válvula.')
            s = revisao.sessao_de_hoje(self.u)
        self.assertEqual(m.call_count, 1)
        self.assertEqual([e['origem'] for e in s['exercicios']], ['item'])
        with mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', return_value={'exercicios': []}):
            cache.clear()
            self.assertEqual(revisao.exercicios_do_padrao(self.p), [])
        self.assertFalse(ExerciciosPadrao.objects.exists())

    def test_responder_exercicio_de_padrao(self):
        ExerciciosPadrao.objects.create(chave='third_person_s', exercicios=revisao.limpar_exercicios_padrao(CLAUDE_OK))
        r = revisao.responder(self.u, 'padrao:third_person_s:0', revisao.ESCOLHER, 'sends', segundos=5)
        self.assertTrue(r['correcta'])
        self.assertEqual(r['texto'], 'She sends the report every Monday.')
        self.assertEqual(r['pontos'], 2)
        self.assertFalse(revisao.responder(self.u, 'padrao:third_person_s:1', revisao.COMPLETAR, 'work')['correcta'])
        with self.assertRaises(revisao.ExercicioInvalido):
            revisao.responder(self.u, 'padrao:third_person_s:1', revisao.ESCOLHER, 'works')
        with self.assertRaises(revisao.ExercicioInvalido):
            revisao.responder(_aluno('f4a-x@example.com'), 'padrao:third_person_s:0', revisao.ESCOLHER, 'sends')
        # Já feito hoje: sai da sessão.
        s = revisao.sessao_de_hoje(self.u)
        self.assertNotIn('padrao:third_person_s:0', [e['id'] for e in s['exercicios']])


# ---------------------------------------------------------------------------
# Erros nas lições e conversas
# ---------------------------------------------------------------------------

class LicaoEConversaTests(TestCase):

    def setUp(self):
        self.u = _aluno()
        prof = _aluno('f4a-prof@example.com', role='teacher')
        self.curso = Course.objects.create(teacher=prof, teacherName='Prof', title='F4A curso', description='-',
                                           course_type='practice', status='Published')
        unidade = PracticeUnit.objects.create(course=self.curso, title='U', description='', order=1)
        self.licao = PracticeLesson.objects.create(unit=unidade, title='L', order=1)
        self.traduzir = PracticeChallenge.objects.create(lesson=self.licao, type='TRANSLATION', order=1,
                                                         question='O relatório está pronto.')
        ChallengeOption.objects.create(challenge=self.traduzir, text='The report is ready.', is_correct=True, order=1)
        self.completar = PracticeChallenge.objects.create(lesson=self.licao, type='FILL_BLANK', order=2,
                                                          question='Please ___ the valve.')
        ChallengeOption.objects.create(challenge=self.completar, text='close', is_correct=True, order=1)
        ChallengeOption.objects.create(challenge=self.completar, text='closes', is_correct=False, order=2)
        self.escolher = PracticeChallenge.objects.create(lesson=self.licao, type='SELECT', order=3, question='?')
        self.vazio = PracticeChallenge.objects.create(lesson=self.licao, type='TRANSLATION', order=4, question='Sem opções')

    def _errar(self, ch, certo=False):
        with self.captureOnCommitCallbacks(execute=True):
            ChallengeAttempt.objects.create(user=self.u, challenge=ch, is_correct=certo)

    def test_erro_na_licao_fica_para_amanha(self):
        self._errar(self.traduzir)
        item = ItemBanco.objects.get(user=self.u)
        self.assertEqual((item.texto, item.traducao, item.origem), ('The report is ready.', 'O relatório está pronto.', 'licao'))
        self.assertEqual((item.licao_id, item.curso_id), (self.licao.pk, self.curso.pk))
        self.assertEqual(item.proxima_revisao, agenda.para_o_dia(1))
        self.assertFalse(agenda.esta_para_hoje(item))
        self._errar(self.completar)
        self.assertTrue(ItemBanco.objects.filter(user=self.u, texto='Please close the valve.').exists())

    def test_erro_puxa_item_marcado_para_mais_tarde(self):
        item = _item(self.u, 'The report is ready.', estabilidade=20.0, dificuldade=5.0, repeticoes=3,
                     proxima_revisao=agenda.para_o_dia(20), estado=ItemBanco.COM_AJUDA)
        self._errar(self.traduzir)
        self._errar(self.traduzir)  # dois erros no mesmo dia contam uma vez
        item.refresh_from_db()
        self.assertEqual(item.proxima_revisao, agenda.para_o_dia(1))
        self.assertEqual((item.estado, item.lapsos), ('com_ajuda', 1))
        self.assertAlmostEqual(item.estabilidade, 6.0)

    def test_certos_e_exercicios_sem_texto_ignorados(self):
        self._errar(self.traduzir, certo=True)
        self._errar(self.escolher)
        self._errar(self.vazio)
        self.assertFalse(ItemBanco.objects.exists())

    def test_falha_no_registo_nao_parte_a_resposta(self):
        with mock.patch('apps.perfil.signals.registar_erro_licao', side_effect=RuntimeError('x')):
            self._errar(self.traduzir)
        self.assertEqual(ChallengeAttempt.objects.count(), 1)

    def test_dita_sozinha_na_conversa_conta_como_revisao_forte(self):
        frase = 'Could you send me the report by Friday?'
        s = VapiSession.objects.create(
            session_id='f4a-sessao-1', user=self.u, level='B1', domain='general', duration_minutes=5,
            status=VapiSession.STATUS_AVALIADA,
            full_session_data={'config': {'objectivos': [{'en': frase, 'pt': 'Pode enviar-me o relatório?'}]},
                               'transcricao': [{'quem': 'tutor', 'texto': 'Hello, how can I help?'},
                                               {'quem': 'aluno', 'texto': frase}]})
        servico.registar_conversa(s)
        item = ItemBanco.objects.get(user=self.u, chave=servico.normalizar(frase))
        self.assertEqual(item.estado, ItemBanco.SOZINHO)
        self.assertEqual(item.repeticoes, 1)
        self.assertEqual(item.estabilidade, agenda.S_INICIAL['facil'])
        self.assertEqual(item.proxima_revisao, agenda.para_o_dia(8))
        self.assertIsNone(item.introduzida_em)  # não gasta a quota de novos da revisão


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _audio():
    return SimpleUploadedFile('gravacao.webm', b'\x1a' * 4096, content_type='audio/webm')


class ApiTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.u = _aluno()
        self.item = _item(self.u, 'Could you check the pressure?', 'Pode verificar a pressão?')
        self.entrar(self.u)
        p = mock.patch('apps.perfil.revisao._pedir_exercicios_padrao', side_effect=RuntimeError('sem rede'))
        p.start()
        self.addCleanup(p.stop)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def test_so_alunos(self):
        self.client.credentials()
        self.assertEqual(self.client.get(f'{R}hoje/').status_code, 401)
        self.entrar(_aluno('f4a-prof@example.com', role='teacher'))
        self.assertEqual(self.client.get(f'{R}hoje/').status_code, 403)
        self.assertEqual(self.client.post(f'{R}responder/', {}, format='json').status_code, 403)

    def test_itens_de_outro_aluno_invisiveis(self):
        outro = _aluno('f4a-outro@example.com')
        self.entrar(outro)
        d = self.client.get(f'{R}hoje/').json()
        self.assertEqual(d['total'], 0)
        self.assertEqual(self.client.get(f'{R}resumo/').json()['para_rever'], 0)
        r = self.client.post(f'{R}responder/', {'exercicio_id': f'item:{self.item.pk}', 'forma': 'escolher',
                                                'resposta': 'Pode verificar a pressão?'}, format='json')
        self.assertEqual(r.status_code, 404)
        r = self.client.post(f'{R}falar/', {'exercicio_id': f'item:{self.item.pk}', 'audio': _audio()}, format='multipart')
        self.assertEqual(r.status_code, 404)

    def test_fluxo_completo(self):
        self.assertEqual(self.client.get(f'{R}resumo/').json(), {'para_rever': 1, 'minutos': 1, 'feitas_hoje': 0})
        d = self.client.get(f'{R}hoje/').json()
        ex = d['exercicios'][0]
        self.assertEqual((d['total'], ex['id'], ex['forma']), (1, f'item:{self.item.pk}', 'ouvir_repetir'))
        inicio = timezone.now().isoformat()
        r = self.client.post(f'{R}responder/', {'exercicio_id': ex['id'], 'forma': 'escolher',
                                                'resposta': 'Pode verificar a pressão?', 'segundos': 5}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['correcta'])
        self.assertEqual(self.client.get(f'{R}hoje/').json()['total'], 0)
        t = self.client.post(f'{R}terminar/', {'inicio': inicio}, format='json').json()
        self.assertEqual((t['respondidos'], t['acertos']), (1, 1))
        self.assertEqual(self.client.get(f'{R}resumo/').json()['feitas_hoje'], 1)

    @override_settings(PRONUNCIA_SIMULADA=True, DEBUG=True)
    def test_falar_guarda_tentativa_sem_exercicio(self):
        r = self.client.post(f'{R}falar/', {'exercicio_id': f'item:{self.item.pk}', 'audio': _audio(), 'segundos': 9},
                             format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertTrue(d['correcta'])
        self.assertEqual((d['analise']['nota'], d['nota'], d['estado_depois']), (82, 'certo', 'com_ajuda'))
        t = TentativaPronuncia.objects.get(user=self.u)
        self.assertIsNone(t.challenge_id)
        self.assertEqual(t.texto_esperado, 'Could you check the pressure?')
        self.assertFalse(ChallengeAttempt.objects.exists())
        self.assertEqual(self.client.post(f'{R}falar/', {'exercicio_id': f'item:{self.item.pk}'},
                                          format='multipart').status_code, 400)

    def test_falar_indisponivel_pode_saltar(self):
        with mock.patch('apps.perfil.views_revisao._analisar', side_effect=RuntimeError('openai')):
            r = self.client.post(f'{R}falar/', {'exercicio_id': f'item:{self.item.pk}', 'audio': _audio()},
                                 format='multipart')
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.json()['pode_saltar'])
        self.assertFalse(RespostaRevisao.objects.exists())
        self.item.refresh_from_db()
        self.assertIsNone(self.item.proxima_revisao)
