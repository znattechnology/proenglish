"""
Ganhos dos professores: bolo do mês, tempo dos alunos pagantes, fecho idempotente,
IBAN angolano, alteração da conta com código por email, permissões e CSV.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.courses.models import Chapter, Course, CourseSection, VideoWatchLog
from apps.practice.models import (
    ChallengeAttempt, PracticeChallenge, PracticeLesson, PracticeUnit,
)
from apps.subscriptions.services import FUSO_ANGOLA
from apps.users.models import EmailVerification, Notification

from apps.pagamentos import ganhos
from apps.pagamentos.models import (
    AlteracaoContaRecebimento, ContaRecebimento, GanhoMensal, Pagamento,
)

from .test_mcx import User, criar_planos

OUTUBRO = date(2026, 10, 1)
URL = '/api/v1/teacher/ganhos/'
URL_ADMIN = '/api/v1/admin/ganhos/'


def em(d, h=12):
    return datetime.combine(d, time(h), tzinfo=FUSO_ANGOLA)


def iban_valido(base='0040000012345678901'):
    for cd in range(100):
        try:
            return ganhos.normalizar_iban(f'AO06{base}{cd:02d}')
        except ganhos.IbanInvalido:
            continue
    raise AssertionError('sem IBAN válido')


class IbanTests(SimpleTestCase):
    def test_valido_com_espacos(self):
        iban = iban_valido()
        com_espacos = ' '.join(iban[i:i + 4] for i in range(0, 25, 4)).lower()
        self.assertEqual(ganhos.normalizar_iban(com_espacos), iban)
        self.assertEqual(len(iban), 25)

    def test_invalidos(self):
        iban = iban_valido()
        errado = iban[:-1] + str((int(iban[-1]) + 1) % 10)
        for entrada in ['', None, 'PT50000201231234567890154', 'AO07' + iban[4:], iban[:-1],
                        iban + '0', 'AO06' + 'A' * 21, errado]:
            with self.assertRaises(ganhos.IbanInvalido, msg=repr(entrada)):
                ganhos.normalizar_iban(entrada)

    def test_datas_de_pagamento(self):
        self.assertEqual(ganhos.data_pagamento(OUTUBRO), date(2026, 11, 5))
        self.assertEqual(ganhos.proximo_pagamento(date(2026, 11, 14)), (date(2026, 12, 5), date(2026, 11, 1)))
        self.assertEqual(ganhos.proximo_pagamento(date(2026, 11, 5)), (date(2026, 11, 5), OUTUBRO))
        self.assertEqual(ganhos.proximo_pagamento(date(2026, 12, 31)), (date(2027, 1, 5), date(2026, 12, 1)))
        self.assertEqual(ganhos.nome_mes(date(2026, 3, 1)), 'Março de 2026')

    def test_divisao_maior_resto(self):
        valores, quotas = ganhos.dividir(100, {'a': 1, 'b': 1, 'c': 1})
        self.assertEqual(sum(valores.values()), 100)
        self.assertEqual(sorted(valores.values()), [33, 33, 34])
        self.assertEqual(quotas['a'], Decimal('0.333333'))

    def test_mascara_email(self):
        self.assertEqual(ganhos.mascarar_email('prof.ana@exemplo.ao'), 'p***@exemplo.ao')


@override_settings(GANHOS_PERCENTAGEM_PROFESSORES=30, GANHOS_SEGUNDOS_POR_EXERCICIO=20,
                   GANHOS_DIA_PAGAMENTO=5, GANHOS_LIMITE_CODIGOS='1000/hour')
class BaseGanhos(APITestCase):
    def setUp(self):
        cache.clear()
        self.free, self.premium, self.plus = criar_planos()
        self.prof_a = User.objects.create_user(email='ana@example.com', name='Prof Ana',
                                               password='x' * 12, role='teacher')
        self.prof_b = User.objects.create_user(email='rui@example.com', name='Prof Rui',
                                               password='x' * 12, role='teacher')
        self.admin = User.objects.create_user(email='admin@example.com', name='Admin',
                                              password='x' * 12, role='admin')
        self.p1 = User.objects.create_user(email='p1@example.com', name='Pagante 1', password='x' * 12)
        self.p2 = User.objects.create_user(email='p2@example.com', name='Pagante 2', password='x' * 12)
        self.gratis = User.objects.create_user(email='gratis@example.com', name='Grátis', password='x' * 12)

        self.video = Course.objects.create(
            teacher=self.prof_a, teacherName='Prof Ana', title='Vídeo', description='x',
            course_type='video', status='Published')
        sec = CourseSection.objects.create(course=self.video, sectionTitle='S1', order=1)
        self.cap = Chapter.objects.create(section=sec, title='A1', content='x', type='Video', order=1)
        rascunho = Course.objects.create(
            teacher=self.prof_a, teacherName='Prof Ana', title='Rascunho', description='x',
            course_type='video', status='Draft')
        sec2 = CourseSection.objects.create(course=rascunho, sectionTitle='S1', order=1)
        self.cap_rascunho = Chapter.objects.create(section=sec2, title='R1', content='x', type='Video', order=1)

        self.pratica = Course.objects.create(
            teacher=self.prof_b, teacherName='Prof Rui', title='Prática', description='x',
            course_type='practice', status='Archived', modo_arquivo='manter')
        un = PracticeUnit.objects.create(course=self.pratica, title='U1', description='', order=1)
        li = PracticeLesson.objects.create(unit=un, title='L1', order=1)
        self.licao_b = li
        self.exs = PracticeChallenge.objects.bulk_create(
            [PracticeChallenge(lesson=li, type='SELECT', question=f'Q{i}', order=i) for i in range(1, 41)])
        self.ex = self.exs[0]

    # -- ajudantes --------------------------------------------------------
    def pagamento(self, user, plan, valor, pago_em, inicio, fim, **extra):
        return Pagamento.objects.create(
            user=user, plan=plan, periodo='mensal', valor_kz=valor, telefone='923456789',
            provedor='simulado', estado=Pagamento.PAGO, expira_em=pago_em, pago_em=pago_em,
            periodo_inicio=inicio, periodo_fim=fim, **extra)

    def ver(self, user, cap, dia, segundos):
        VideoWatchLog.objects.create(user=user, chapter=cap, date=dia, seconds=segundos)

    def responder(self, user, n, quando, exercicios=None, vezes=1):
        """Responde a ``n`` exercícios diferentes (``vezes`` cada um) no instante ``quando``."""
        ids = [ChallengeAttempt.objects.create(user=user, challenge=ch, is_correct=True).pk
               for ch in (exercicios or self.exs)[:n] for _ in range(vezes)]
        ChallengeAttempt.objects.filter(pk__in=ids).update(created_at=quando)

    def cenario_outubro(self):
        # Receita: 14 950 + 24 950 = 39 900 Kz -> bolo 30 % = 11 970 Kz
        self.pagamento(self.p1, self.premium, 14950, em(date(2026, 10, 1), 9),
                       em(date(2026, 10, 1), 9), em(date(2026, 10, 31), 9))
        self.pagamento(self.p2, self.plus, 24950, em(date(2026, 10, 10)),
                       em(date(2026, 10, 10)), em(date(2026, 11, 9)))
        # Fora do mês: não conta para o bolo
        self.pagamento(self.p2, self.premium, 14950, em(date(2026, 9, 2)),
                       em(date(2026, 9, 2)), em(date(2026, 9, 30)))
        # Prof. A (vídeo): p1 600 s + p2 300 s (depois de pagar) = 900 s
        self.ver(self.p1, self.cap, date(2026, 10, 5), 600)
        self.ver(self.p2, self.cap, date(2026, 10, 5), 1200)   # p2 ainda não pagava
        self.ver(self.p2, self.cap, date(2026, 10, 15), 300)
        self.ver(self.gratis, self.cap, date(2026, 10, 5), 3000)  # Gratuito: não conta
        self.ver(self.p1, self.cap_rascunho, date(2026, 10, 6), 5000)  # curso não publicado
        # Prof. B (prática): p1 30 respostas x 20 s = 600 s
        self.responder(self.p1, 30, em(date(2026, 10, 20)))
        self.responder(self.gratis, 40, em(date(2026, 10, 20)))
        self.responder(self.p1, 10, em(date(2026, 11, 2)))  # fora do mês


class CalculoTests(BaseGanhos):
    def test_bolo_dividido_pelo_tempo_dos_pagantes(self):
        self.cenario_outubro()
        c = ganhos.calcular(OUTUBRO)
        self.assertEqual(c.receita_kz, 39900)
        self.assertEqual(c.bolo_kz, 11970)
        self.assertEqual(c.professores[self.prof_a.pk].segundos, 900)
        self.assertEqual(c.professores[self.prof_a.pk].alunos, {self.p1.pk, self.p2.pk})
        self.assertEqual(c.professores[self.prof_b.pk].segundos, 600)
        self.assertEqual(c.valores[self.prof_a.pk], 7182)  # 11 970 x 900 / 1 500
        self.assertEqual(c.valores[self.prof_b.pk], 4788)
        self.assertEqual(c.quotas[self.prof_a.pk], Decimal('0.600000'))

    @override_settings(GANHOS_PERCENTAGEM_PROFESSORES=50)
    def test_percentagem_configuravel(self):
        self.cenario_outubro()
        self.assertEqual(ganhos.calcular(OUTUBRO).bolo_kz, 19950)

    def test_sem_pagantes_nao_ha_ganhos(self):
        self.ver(self.gratis, self.cap, date(2026, 10, 5), 3000)
        c = ganhos.calcular(OUTUBRO)
        self.assertEqual(c.professores, {})
        self.assertEqual(c.bolo_kz, 0)

    def test_fecho_idempotente_e_nao_mexe_no_pago(self):
        self.cenario_outubro()
        out = StringIO()
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=out)
        self.assertIn('bolo 30% = 11 970 Kz', out.getvalue())
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=StringIO())
        self.assertEqual(GanhoMensal.objects.filter(mes=OUTUBRO).count(), 2)
        self.assertEqual(Notification.objects.filter(user=self.prof_a, link='/teacher/billing').count(), 1)
        ga = GanhoMensal.objects.get(professor=self.prof_a, mes=OUTUBRO)
        self.assertEqual((ga.valor_kz, ga.alunos_pagantes, ga.segundos), (7182, 2, 900))

        GanhoMensal.objects.filter(pk=ga.pk).update(estado='pago', pago_em=date(2026, 11, 5), referencia='T1')
        self.responder(self.p1, 30, em(date(2026, 10, 21)))  # B passa a 1 200 s
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=StringIO())
        ga.refresh_from_db()
        self.assertEqual((ga.valor_kz, ga.estado, ga.referencia), (7182, 'pago', 'T1'))
        gb = GanhoMensal.objects.get(professor=self.prof_b, mes=OUTUBRO)
        self.assertEqual(gb.segundos, 1200)
        self.assertEqual(gb.valor_kz, 6840)  # 11 970 x 1 200 / 2 100

    def test_comando_recusa_mes_corrente(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('fechar_ganhos', '--mes', f'{ganhos.hoje():%Y-%m}', stdout=StringIO())

    def test_estimativa_do_mes_corrente(self):
        agora = timezone.now()
        hoje = ganhos.hoje()
        self.pagamento(self.p1, self.premium, 14950, agora - timedelta(minutes=1),
                       agora - timedelta(minutes=1), agora + timedelta(days=30))
        VideoWatchLog.objects.create(user=self.p1, chapter=self.cap, date=hoje, seconds=1200)
        self.client.force_authenticate(self.prof_a)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['este_mes'], {'valor_kz': 4485, 'ate': hoje.isoformat(),
                                              'alunos_pagantes': 1, 'minutos': 20})


class EndpointsTests(BaseGanhos):
    def test_resumo_e_csv(self):
        self.cenario_outubro()
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=StringIO())
        GanhoMensal.objects.create(professor=self.prof_a, mes=date(2026, 3, 1), alunos_pagantes=1,
                                   segundos=60, valor_kz=1000, estado='pago', pago_em=date(2026, 4, 5))
        self.client.force_authenticate(self.prof_a)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        d = r.data
        self.assertEqual(d['percentagem'], 30)
        self.assertEqual(d['dia_pagamento'], 5)
        self.assertEqual(d['total_recebido'], {'valor_kz': 1000, 'desde': 'Março de 2026'})
        self.assertEqual(d['meses'][0], {'mes': '2026-10', 'nome': 'Outubro de 2026', 'alunos': 2,
                                         'minutos': 15, 'valor_kz': 7182, 'pago_a': '2026-11-05',
                                         'pago_em': None, 'estado': 'a_processar'})
        self.assertEqual(d['meses'][1]['estado'], 'pago')
        self.assertEqual(d['meses'][1]['pago_em'], '2026-04-05')
        self.assertEqual(d['regras'], {'segundos_por_exercicio': 20, 'max_pratica_min_dia': 60,
                                       'max_video_min_dia': 240})
        self.assertIsNone(d['conta'])
        self.assertIsNone(d['alteracao_pendente'])
        self.assertIn('referente', d['proximo_pagamento'])

        r = self.client.get(URL + 'exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        texto = r.content.decode('utf-8')
        self.assertTrue(texto.startswith('﻿'))
        linhas = texto.lstrip('﻿').splitlines()
        self.assertEqual(linhas[0], 'Mês;Alunos;Minutos;Valor (Kz);Pago a;Estado')
        self.assertEqual(linhas[1], 'Outubro de 2026;2;15;7182;05/11/2026;A processar')
        self.assertEqual(linhas[2], 'Março de 2026;1;1;1000;05/04/2026;Pago')

    def test_outro_professor_so_ve_os_seus(self):
        self.cenario_outubro()
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=StringIO())
        self.client.force_authenticate(self.prof_b)
        meses = self.client.get(URL).data['meses']
        self.assertEqual([m['valor_kz'] for m in meses], [4788])

    def test_aluno_nao_entra(self):
        self.client.force_authenticate(self.p1)
        for url in [URL, URL + 'exportar/', URL + 'bancos/', URL_ADMIN]:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(URL + 'conta/', {}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_professor_nao_entra_no_admin(self):
        g = GanhoMensal.objects.create(professor=self.prof_a, mes=OUTUBRO, valor_kz=10)
        self.client.force_authenticate(self.prof_a)
        self.assertEqual(self.client.get(URL_ADMIN).status_code, 403)
        self.assertEqual(self.client.get(f'{URL_ADMIN}{g.pk}/iban/').status_code, 403)
        self.assertEqual(self.client.post(f'{URL_ADMIN}{g.pk}/pago/', {'referencia': 'x'}).status_code, 403)

    def test_bancos(self):
        self.client.force_authenticate(self.prof_a)
        r = self.client.get(URL + 'bancos/')
        self.assertIn({'valor': 'bai', 'nome': 'BAI'}, r.data)
        self.assertEqual(r.data[-1]['valor'], 'outro')

    def test_admin_lista_iban_e_pago(self):
        self.cenario_outubro()
        call_command('fechar_ganhos', '--mes', '2026-10', stdout=StringIO())
        iban = iban_valido()
        ContaRecebimento.objects.create(professor=self.prof_a, banco='bfa', iban=iban,
                                        titular='Ana Silva', confirmada_em=timezone.now())
        self.client.force_authenticate(self.admin)
        r = self.client.get(URL_ADMIN, {'mes': '2026-10'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['total_kz'], 11970)
        linha = r.data['linhas'][0]
        self.assertEqual(linha['professor']['nome'], 'Prof Ana')
        self.assertEqual(linha['conta']['terminada_em'], iban[-4:])
        self.assertNotIn(iban, str(r.data))
        self.assertIsNone(r.data['linhas'][1]['conta'])
        self.assertEqual(self.client.get(URL_ADMIN, {'mes': '2026-13'}).status_code, 400)

        with self.assertLogs('apps.pagamentos.views_ganhos', 'INFO') as logs:
            r = self.client.get(f"{URL_ADMIN}{linha['id']}/iban/")
        self.assertEqual(r.data['iban'], iban)
        self.assertIn('IBAN consultado', logs.output[0])

        gb = GanhoMensal.objects.get(professor=self.prof_b)
        r = self.client.post(f'{URL_ADMIN}{gb.pk}/pago/', {'referencia': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['code'], 'sem_conta')

        r = self.client.post(f"{URL_ADMIN}{linha['id']}/pago/", {'referencia': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado'], 'pago')
        self.assertTrue(Notification.objects.filter(user=self.prof_a, title__startswith='Pagámos').exists())
        r = self.client.post(f"{URL_ADMIN}{linha['id']}/pago/", {'referencia': 'TRF-1'}, format='json')
        self.assertEqual(r.status_code, 409)


class ContaTests(BaseGanhos):
    def setUp(self):
        super().setUp()
        self.iban = iban_valido()
        self.client.force_authenticate(self.prof_a)

    def pedir(self, **extra):
        corpo = {'banco': 'bai', 'iban': ' '.join([self.iban[:4], self.iban[4:]]), 'titular': ' Ana  Silva '}
        corpo.update(extra)
        return self.client.post(URL + 'conta/', corpo, format='json')

    def codigo(self):
        return AlteracaoContaRecebimento.objects.get(professor=self.prof_a).verificacao.code

    def test_fluxo_completo(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['alteracao_pendente']['terminada_em'], self.iban[-4:])
        self.assertEqual(r.data['alteracao_pendente']['titular'], 'Ana Silva')
        self.assertTrue(r.data['mensagem'].startswith('Enviámos um código para a***@example.com.'))
        self.assertEqual(len(mail.outbox), 1)
        codigo = self.codigo()
        self.assertIn(codigo, mail.outbox[0].alternatives[0][0])
        self.assertNotIn(self.iban, mail.outbox[0].body)
        v = AlteracaoContaRecebimento.objects.get().verificacao
        self.assertEqual(v.finalidade, 'conta_ganhos')
        self.assertAlmostEqual((v.expires_at - timezone.now()).total_seconds(), 900, delta=30)

        self.assertIsNotNone(self.client.get(URL).data['alteracao_pendente'])
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['conta']['banco'], 'bai')
        self.assertEqual(r.data['conta']['terminada_em'], self.iban[-4:])
        self.assertIsNone(r.data['alteracao_pendente'])
        self.assertNotIn(self.iban, str(r.data))
        self.assertEqual(ContaRecebimento.objects.get(professor=self.prof_a).iban, self.iban)
        # O código não volta a servir
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_validacao(self):
        r = self.pedir(banco='xpto', iban='AO06123', titular='')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'dados_invalidos')
        self.assertEqual(set(r.data['details']), {'banco', 'iban', 'titular'})
        for valor in r.data['details'].values():
            self.assertIsInstance(valor, list)
            self.assertTrue(all(isinstance(t, str) for t in valor))
        self.assertEqual(r.data['message'], r.data['details']['banco'][0])
        self.assertEqual(len(mail.outbox), 0)

    def test_codigo_expirado(self):
        self.pedir()
        codigo = self.codigo()
        EmailVerification.objects.filter(finalidade='conta_ganhos').update(
            expires_at=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(self.client.get(URL).data['alteracao_pendente'])
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'codigo_expirado')
        self.assertFalse(ContaRecebimento.objects.exists())

    def test_tentativas(self):
        self.pedir()
        codigo = self.codigo()
        errado = '000000' if codigo != '000000' else '111111'
        for restantes in [4, 3, 2, 1]:
            r = self.client.post(URL + 'conta/confirmar/', {'codigo': errado}, format='json')
            self.assertEqual(r.data['code'], 'codigo_invalido')
            self.assertEqual(r.data['tentativas_restantes'], restantes)
            self.assertIsInstance(r.data['details']['codigo'], list)
            self.assertIn(str(restantes), r.data['details']['codigo'][0])
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': errado}, format='json')
        self.assertEqual(r.data['code'], 'tentativas_esgotadas')
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.data['code'], 'tentativas_esgotadas')
        self.assertFalse(ContaRecebimento.objects.exists())
        # Um pedido novo gera um código novo e volta a dar 5 tentativas
        self.pedir()
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': self.codigo()}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_cancelar(self):
        self.pedir()
        codigo = self.codigo()
        self.assertEqual(self.client.delete(URL + 'conta/pendente/').status_code, 204)
        self.assertIsNone(self.client.get(URL).data['alteracao_pendente'])
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_codigo_de_outro_professor_nao_serve(self):
        self.pedir()
        codigo = self.codigo()
        self.client.force_authenticate(self.prof_b)
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 404)


class TempoQueContaTests(BaseGanhos):
    """Decisão do dono: cada exercício conta uma vez por aluno e dia; no máximo 60 min de prática
    (e 4 h de vídeo) por aluno e dia; períodos a 0 Kz não contam."""

    def setUp(self):
        super().setUp()
        self.pagamento(self.p1, self.premium, 14950, em(date(2026, 10, 1), 9),
                       em(date(2026, 10, 1), 9), em(date(2026, 10, 31), 9))
        # Curso de prática da Prof. Ana (para repartir o limite entre professores)
        self.pratica_a = Course.objects.create(
            teacher=self.prof_a, teacherName='Prof Ana', title='Prática A', description='x',
            course_type='practice', status='Published')
        un = PracticeUnit.objects.create(course=self.pratica_a, title='U1', description='', order=1)
        li = PracticeLesson.objects.create(unit=un, title='L1', order=1)
        self.exs_a = PracticeChallenge.objects.bulk_create(
            [PracticeChallenge(lesson=li, type='SELECT', question=f'A{i}', order=i) for i in range(1, 201)])

    def segundos(self):
        c = ganhos.calcular(OUTUBRO)
        return {k: t.segundos for k, t in c.professores.items()}

    def test_mesmo_exercicio_conta_uma_vez_por_dia(self):
        dia = date(2026, 10, 20)
        self.responder(self.p1, 1, em(dia, 10), vezes=50)       # 50 x o mesmo: 20 s
        self.responder(self.p1, 4, em(dia, 11))                 # mais 4 diferentes (inclui o 1.º): +60 s
        self.responder(self.p1, 1, em(date(2026, 10, 21), 10))  # outro dia: volta a contar, +20 s
        self.assertEqual(self.segundos(), {self.prof_b.pk: 100})

    def test_limite_de_60_min_por_dia_repartido_pelos_professores(self):
        dia = date(2026, 10, 20)
        self.responder(self.p1, 150, em(dia, 10), exercicios=self.exs_a)  # Ana: 3 000 s
        self.responder(self.p1, 40, em(dia, 11))                          # Rui: 800 s
        # 3 800 s > 3 600 s -> 3 600 x 3 000/3 800 = 2 842,1 e 3 600 x 800/3 800 = 757,9
        self.assertEqual(self.segundos(), {self.prof_a.pk: 2842, self.prof_b.pk: 758})

    def test_limite_por_dia_so_no_proprio_dia(self):
        self.responder(self.p1, 200, em(date(2026, 10, 20), 10), exercicios=self.exs_a)  # 4 000 -> 3 600
        self.responder(self.p1, 40, em(date(2026, 10, 21), 10))                         # 800 (sem limite)
        self.assertEqual(self.segundos(), {self.prof_a.pk: 3600, self.prof_b.pk: 800})

    @override_settings(GANHOS_MAX_PRATICA_SEGUNDOS_DIA=600)
    def test_limite_configuravel(self):
        self.responder(self.p1, 40, em(date(2026, 10, 20)))  # 800 -> 600
        self.assertEqual(self.segundos(), {self.prof_b.pk: 600})

    def test_video_limitado_a_4_horas_por_dia(self):
        sec = CourseSection.objects.create(course=self.video, sectionTitle='S2', order=2)
        dia = date(2026, 10, 20)
        for i in range(3):
            cap = Chapter.objects.create(section=sec, title=f'B{i}', content='x', type='Video', order=i + 2)
            self.ver(self.p1, cap, dia, 6000)  # 18 000 s no dia -> 14 400 s
        self.ver(self.p1, self.cap, date(2026, 10, 21), 600)
        self.assertEqual(self.segundos(), {self.prof_a.pk: 14400 + 600})

    def test_periodo_a_zero_kz_nao_conta(self):
        # p2: código de 100 % -> pagou 0 Kz; a actividade nesse período não conta.
        self.pagamento(self.p2, self.premium, 14950, em(date(2026, 10, 2)),
                       em(date(2026, 10, 2)), em(date(2026, 11, 1)), desconto_kz=14950)
        self.responder(self.p2, 10, em(date(2026, 10, 20)))
        self.ver(self.p2, self.cap, date(2026, 10, 20), 900)
        self.responder(self.p1, 5, em(date(2026, 10, 20)))
        c = ganhos.calcular(OUTUBRO)
        self.assertEqual(c.receita_kz, 14950)
        self.assertEqual({k: t.segundos for k, t in c.professores.items()}, {self.prof_b.pk: 100})
        self.assertEqual(c.professores[self.prof_b.pk].alunos, {self.p1.pk})
        # Crédito que cobre tudo também é 0 Kz
        Pagamento.objects.filter(user=self.p2).update(desconto_kz=0, credito_abatido_kz=14950)
        self.assertNotIn(self.prof_a.pk, ganhos.calcular(OUTUBRO).professores)


class LimiteCodigosTests(BaseGanhos):
    def setUp(self):
        super().setUp()
        self.iban = iban_valido()
        self.client.force_authenticate(self.prof_a)

    @override_settings(GANHOS_LIMITE_CODIGOS='2/hour')
    def test_so_conta_pedidos_que_enviam_codigo(self):
        for _ in range(5):
            r = self.client.post(URL + 'conta/', {'banco': 'xpto', 'iban': '1', 'titular': ''}, format='json')
            self.assertEqual(r.status_code, 400)
        valido = {'banco': 'bai', 'iban': self.iban, 'titular': 'Ana Silva'}
        for _ in range(2):
            self.assertEqual(self.client.post(URL + 'conta/', valido, format='json').status_code, 200)
        r = self.client.post(URL + 'conta/', valido, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(mail.outbox), 2)


class RegistoContaTests(BaseGanhos):
    def setUp(self):
        super().setUp()
        self.iban = iban_valido()
        self.client.force_authenticate(self.prof_a)

    def pedir(self):
        return self.client.post(URL + 'conta/', {'banco': 'bfa', 'iban': self.iban, 'titular': 'Ana Silva'},
                                format='json')

    def test_pedido_confirmacao_cancelamento_e_iban(self):
        from apps.pagamentos.models import RegistoContaRecebimento as R

        self.pedir()
        self.client.delete(URL + 'conta/pendente/')
        self.pedir()
        codigo = AlteracaoContaRecebimento.objects.get().verificacao.code
        r = self.client.post(URL + 'conta/confirmar/', {'codigo': codigo}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        accoes = list(R.objects.filter(professor=self.prof_a).order_by('criado_em', 'id')
                      .values_list('accao', 'autor_id', 'banco', 'terminada_em'))
        self.assertEqual(accoes, [
            ('pedido', self.prof_a.pk, 'bfa', self.iban[-4:]),
            ('cancelada', self.prof_a.pk, 'bfa', self.iban[-4:]),
            ('pedido', self.prof_a.pk, 'bfa', self.iban[-4:]),
            ('confirmada', self.prof_a.pk, 'bfa', self.iban[-4:]),
        ])
        # Email a avisar que a conta mudou (sem o IBAN completo)
        aviso = mail.outbox[-1]
        self.assertEqual(aviso.subject, 'A conta para receber os ganhos foi alterada - ProEnglish')
        self.assertEqual(aviso.to, ['ana@example.com'])
        self.assertIn(self.iban[-4:], aviso.body)
        self.assertIn('Se não foi você', aviso.body)
        self.assertNotIn(self.iban, aviso.body)

        g = GanhoMensal.objects.create(professor=self.prof_a, mes=OUTUBRO, valor_kz=10)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f'{URL_ADMIN}{g.pk}/iban/').status_code, 200)
        reg = R.objects.get(accao='iban_consultado')
        self.assertEqual((reg.professor_id, reg.autor_id, reg.ganho_id), (self.prof_a.pk, self.admin.pk, g.pk))
        self.assertNotIn(self.iban, str(list(R.objects.values())))

    def test_marcar_pago_details_em_lista(self):
        g = GanhoMensal.objects.create(professor=self.prof_a, mes=OUTUBRO, valor_kz=10)
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{URL_ADMIN}{g.pk}/pago/', {'referencia': ''}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['details'], {'referencia': ['Obrigatória (até 100 caracteres).']})
