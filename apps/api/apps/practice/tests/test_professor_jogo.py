"""
Área do professor: situações da conversa, conquistas e competições (apps/practice/professor/).

    DATABASE_URL=... ./venv/bin/python manage.py test apps.practice.tests.test_professor_jogo
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course, CourseEnrollment
from apps.practice import competicoes
from apps.practice.achievement_utils import verificar_conquistas_professor
from apps.practice.limite_licoes import hoje_luanda
from apps.practice.models import (
    Achievement, Competition, CompetitionParticipant, LessonCompletion, PointsEntry, PracticeLesson, PracticeUnit,
    Situacao, UserAchievement, UserProgress, VapiSession,
)
from apps.subscriptions.models import SubscriptionPlan, UserSubscription
from apps.users.models import Notification

User = get_user_model()
T = '/api/v1/teacher/'
C = '/api/v1/practice/conversa/'


class Base(APITestCase):

    def setUp(self):
        cache.clear()
        self.prof_a = User.objects.create_user(email='prof-a-jogo@example.com', name='Ana Professora',
                                               password='x', role='teacher')
        self.prof_b = User.objects.create_user(email='prof-b-jogo@example.com', name='Bruno Professor',
                                               password='x', role='teacher')
        self.admin = User.objects.create_user(email='admin-jogo@example.com', name='Admin', password='x',
                                              role='admin', is_staff=True)
        self.aluno = User.objects.create_user(email='aluno1-jogo@example.com', name='Ana Maria Esteves',
                                              password='x', role='student')
        self.aluno2 = User.objects.create_user(email='aluno2-jogo@example.com', name='Carlos Dias',
                                               password='x', role='student')
        self.fora = User.objects.create_user(email='aluno3-jogo@example.com', name='Zé Fora',
                                             password='x', role='student')
        self.curso_a = Course.objects.create(teacher=self.prof_a, teacherName='Ana', title='Inglês Petróleo',
                                             description='x', course_type='video', status='Published')
        self.curso_a2 = Course.objects.create(teacher=self.prof_a, teacherName='Ana', title='Inglês Banca',
                                              description='x', course_type='video', status='Published')
        self.curso_b = Course.objects.create(teacher=self.prof_b, teacherName='Bruno', title='Curso do Bruno',
                                             description='x', course_type='video', status='Published')
        CourseEnrollment.objects.create(user=self.aluno, course=self.curso_a)
        CourseEnrollment.objects.create(user=self.aluno2, course=self.curso_a)
        CourseEnrollment.objects.create(user=self.fora, course=self.curso_b)
        self.client = APIClient()
        self.entrar(self.prof_a)

    def entrar(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def pontos(self, user, n, curso=None):
        p, _ = UserProgress.objects.get_or_create(user=user, defaults={'points': 0})
        p.add_points(n, reason='teste', curso_id=curso.id if curso else None)


# ---------------------------------------------------------------------------
# Situações
# ---------------------------------------------------------------------------

def _corpo_situacao(curso=None, **extra):
    return {'nome': 'Reunião com o fornecedor', 'descricao': 'O aluno negoceia o prazo de entrega de válvulas.',
            'papel_tutor': 'Um fornecedor apressado', 'frases': ['Could we agree on Friday?'],
            'curso': str(curso.id) if curso else None, 'nivel': 'B1', 'duracao_min': 5,
            'correccao': 'directa', 'estado': 'activo', **extra}


class SituacoesTests(Base):

    def test_migracao_cria_as_situacoes_da_plataforma(self):
        slugs = list(Situacao.objects.filter(criado_por__isnull=True).values_list('slug', flat=True))
        self.assertEqual(slugs, ['pedir_relatorio', 'reuniao_seguranca', 'atender_cliente', 'apresentar_equipa',
                                 'conversa_livre'])
        s = Situacao.objects.get(slug='pedir_relatorio')
        self.assertEqual(s.estado, 'activo')
        self.assertIn('brief', s.extras)

    def test_sessao_antiga_continua_a_abrir(self):
        VapiSession.objects.create(
            session_id='antiga-1', user=self.aluno, level='B1', domain='general', duration_minutes=3,
            status=VapiSession.STATUS_AVALIADA, situation='reuniao_seguranca', overall_score=70,
            full_session_data={'versao': 'conversa-1', 'transcricao': [], 'historico': []})
        self.entrar(self.aluno)
        r = self.client.get(f'{C}sessoes/antiga-1/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['situacao'], {'id': 'reuniao_seguranca', 'titulo': 'Reunião de segurança'})
        # Mesmo desligada continua a abrir.
        Situacao.objects.filter(slug='reuniao_seguranca').update(estado='rascunho')
        self.assertEqual(self.client.get(f'{C}sessoes/antiga-1/').data['situacao']['titulo'], 'Reunião de segurança')

    def test_criar_listar_e_ver(self):
        r = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['curso'], {'id': str(self.curso_a.id), 'titulo': 'Inglês Petróleo'})
        self.assertTrue(r.data['minha'])
        self.assertEqual(r.data['correccao'], 'directa')
        r = self.client.get(f'{T}situacoes/?tipo=conversa')
        self.assertEqual(r.status_code, 200)
        res = r.data['resultados']
        self.assertEqual(len(res), 6)
        self.assertTrue(res[0]['minha'])
        self.assertEqual(set(res[0]), {'id', 'nome', 'tipo', 'curso', 'nivel', 'estado', 'sessoes',
                                       'pontuacao_media', 'minha'})
        self.assertFalse(any(x['minha'] for x in res[1:]))

    def test_validacao(self):
        r = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_b, nivel='D1', duracao_min=7,
                                                                frases=['x' * 161], papel_tutor='p' * 201),
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'validation_error')
        self.assertEqual(set(r.data['details']), {'curso', 'nivel', 'duracao_min', 'frases', 'papel_tutor'})
        self.assertEqual(r.data['details']['curso'], ['Escolha um dos seus cursos.'])

    def test_permissoes(self):
        s = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a), format='json').data
        plataforma = Situacao.objects.get(slug='pedir_relatorio')
        # Outro professor: não existe.
        self.entrar(self.prof_b)
        self.assertEqual(self.client.get(f'{T}situacoes/{s["id"]}/').status_code, 404)
        self.assertEqual(self.client.patch(f'{T}situacoes/{s["id"]}/', {'nome': 'X y z'}, format='json').status_code,
                         404)
        self.assertEqual(len(self.client.get(f'{T}situacoes/').data['resultados']), 5)
        # Plataforma: só leitura.
        r = self.client.patch(f'{T}situacoes/{plataforma.pk}/', {'nome': 'Outro nome'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['code'], 'so_administrador')
        self.assertEqual(self.client.delete(f'{T}situacoes/{plataforma.pk}/').status_code, 403)
        # Aluno: 403.
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{T}situacoes/').status_code, 403)
        self.assertEqual(self.client.get(f'{T}situacoes/opcoes/').status_code, 403)

    def test_apagar_so_sem_sessoes(self):
        s = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a), format='json').data
        slug = Situacao.objects.get(pk=s['id']).slug
        VapiSession.objects.create(session_id='s-apagar', user=self.aluno, level='B1', domain='general',
                                   duration_minutes=2, status=VapiSession.STATUS_AVALIADA, situation=slug)
        r = self.client.delete(f'{T}situacoes/{s["id"]}/')
        self.assertEqual(r.status_code, 409)
        self.assertIn('desligue', r.data['message'])
        r = self.client.patch(f'{T}situacoes/{s["id"]}/', {'estado': 'rascunho'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['estado'], 'rascunho')
        VapiSession.objects.filter(session_id='s-apagar').delete()
        self.assertEqual(self.client.delete(f'{T}situacoes/{s["id"]}/').status_code, 204)

    def test_opcoes(self):
        r = self.client.get(f'{T}situacoes/opcoes/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual({c['titulo'] for c in r.data['cursos']}, {'Inglês Petróleo', 'Inglês Banca'})
        self.assertEqual(r.data['duracoes'], [3, 5, 10])
        self.assertEqual(r.data['niveis'][0]['valor'], 'A1')

    @override_settings(CONVERSA_SIMULADA=True, CONVERSA_MAX_MINUTOS_SESSAO=15)
    def test_aluno_ve_so_as_dos_seus_cursos(self):
        do_curso = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a), format='json').data
        rascunho = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a, estado='rascunho'),
                                    format='json').data
        slug = Situacao.objects.get(pk=do_curso['id']).slug
        slug_rascunho = Situacao.objects.get(pk=rascunho['id']).slug
        plano = SubscriptionPlan.objects.update_or_create(plan_type='PREMIUM_PLUS', defaults=dict(
            name='Premium Plus', description='-', monthly_price=Decimal('0'), daily_speaking_minutes=20,
            ai_tutor=True))[0]
        for u in (self.aluno, self.fora):
            UserSubscription.objects.update_or_create(user=u, defaults=dict(
                plan=plano, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30),
                last_reset_date=hoje_luanda()))

        self.entrar(self.aluno)
        ids = [s['id'] for s in self.client.get(f'{C}preparar/').data['situacoes']]
        self.assertIn(slug, ids)
        self.assertNotIn(slug_rascunho, ids)
        item = next(s for s in self.client.get(f'{C}preparar/').data['situacoes'] if s['id'] == slug)
        self.assertEqual(item['curso']['titulo'], 'Inglês Petróleo')
        self.assertEqual(item['correcao'], 'directa')
        r = self.client.post(f'{C}sessoes/', {'situacao': slug, 'nivel': 'B1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['situacao']['titulo'], 'Reunião com o fornecedor')
        self.assertEqual(r.data['frases'], [{'en': 'Could we agree on Friday?', 'pt': ''}])
        # Responder (simulado) funciona com o guião genérico.
        self.assertEqual(self.client.post(f'{C}sessoes/{r.data["id"]}/responder/',
                                          {'texto': 'Yes, Friday is fine for us.'}, format='json').status_code, 200)

        self.entrar(self.fora)
        ids = [s['id'] for s in self.client.get(f'{C}preparar/').data['situacoes']]
        self.assertNotIn(slug, ids)
        self.assertIn('pedir_relatorio', ids)
        r = self.client.post(f'{C}sessoes/', {'situacao': slug, 'nivel': 'B1', 'correcao': 'suave',
                                              'area': 'general'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_resultados_fala(self):
        s = self.client.post(f'{T}situacoes/', _corpo_situacao(self.curso_a), format='json').data
        slug = Situacao.objects.get(pk=s['id']).slug

        def sessao(sid, user, situacao, nota, minutos, status=VapiSession.STATUS_AVALIADA):
            VapiSession.objects.create(session_id=sid, user=user, level='B1', domain='general',
                                       duration_minutes=minutos, status=status, situation=situacao,
                                       overall_score=nota, fluency_score=nota, grammar_score=nota - 10,
                                       vocabulary_score=nota + 10, pronunciation_score=None)

        sessao('f1', self.aluno, slug, 80, 5)
        sessao('f2', self.aluno2, 'pedir_relatorio', 60, 3)            # aluno do professor, plataforma
        sessao('f3', self.fora, 'pedir_relatorio', 10, 9)               # não é aluno do professor: não conta
        sessao('f4', self.aluno, slug, 20, 2, VapiSession.STATUS_SEM_AVALIACAO)
        r = self.client.get(f'{T}resultados/fala/?periodo=30')
        self.assertEqual(r.status_code, 200)
        d = r.data
        self.assertEqual(d['sessoes'], 3)
        self.assertEqual(d['minutos'], 10)
        self.assertEqual(d['pontuacao_media'], 70)
        self.assertEqual(d['terminam_pct'], 67)
        self.assertIsNone(d['minutos_variacao_pct'])
        comp = {c['nome']: c['media'] for c in d['competencias']}
        self.assertEqual(comp, {'Fluência': 70, 'Gramática': 60, 'Vocabulário': 80})  # sem Pronúncia
        self.assertEqual(d['situacoes'][0], {'id': s['id'], 'nome': 'Reunião com o fornecedor', 'sessoes': 2,
                                             'media': 80})
        self.assertEqual(self.client.get(f'{T}resultados/fala/?periodo=12').status_code, 400)
        # A lista mostra as sessões e a média (só avaliadas).
        item = next(x for x in self.client.get(f'{T}situacoes/').data['resultados'] if x['id'] == s['id'])
        self.assertEqual((item['sessoes'], item['pontuacao_media']), (2, 80))


# ---------------------------------------------------------------------------
# Conquistas
# ---------------------------------------------------------------------------

def _corpo_conquista(curso=None, tipo='pontos', meta=20, **extra):
    return {'nome': 'Cem por cento', 'descricao': 'Ganhe pontos no curso.', 'icone': '★',
            'regra': {'tipo': tipo, 'meta': meta, 'curso': str(curso.id) if curso else None},
            'raridade': 'rara', 'pontos': 50, 'activa': True, **extra}


class ConquistasTests(Base):

    def test_criar_e_listar(self):
        r = self.client.post(f'{T}conquistas/', _corpo_conquista(self.curso_a, tipo='dias_seguidos', meta=7),
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['como_se_ganha'], 'Praticar 7 dias seguidos no curso «Inglês Petróleo»')
        self.assertEqual(r.data['regra'], {'tipo': 'dias_seguidos', 'meta': 7,
                                           'curso': {'id': str(self.curso_a.id), 'titulo': 'Inglês Petróleo'}})
        self.assertEqual(r.data['raridade'], 'rara')
        Achievement.objects.create(title='Plataforma', description='x', icon='P', category='milestone',
                                   points=10, requirement_type='points_earned', requirement_target=100)
        lista = self.client.get(f'{T}conquistas/?estado=activas').data['resultados']
        self.assertEqual([x['minha'] for x in lista], [True, False])
        self.assertEqual(lista[1]['regra']['tipo'], 'pontos')
        self.assertEqual(self.client.get(f'{T}conquistas/?estado=desligadas').data['resultados'], [])
        o = self.client.get(f'{T}conquistas/opcoes/').data
        self.assertEqual([t['valor'] for t in o['tipos']], ['conversas', 'licoes', 'dias_seguidos', 'pontos',
                                                            'palavras'])
        self.assertEqual(len(o['cursos']), 2)

    def test_validacao(self):
        r = self.client.post(f'{T}conquistas/', _corpo_conquista(self.curso_b, tipo='xp', meta=0, pontos=1,
                                                                 icone='ABCD', nome='X' * 41), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data['details']), {'nome', 'icone', 'regra.tipo', 'regra.meta', 'regra.curso',
                                                  'pontos'})

    def test_permissoes(self):
        a = self.client.post(f'{T}conquistas/', _corpo_conquista(self.curso_a), format='json').data
        plataforma = Achievement.objects.create(title='Plataforma', description='x', icon='P', category='milestone',
                                                points=10, requirement_type='points_earned', requirement_target=100)
        self.entrar(self.prof_b)
        self.assertEqual(self.client.patch(f'{T}conquistas/{a["id"]}/', {'nome': 'Outra'},
                                           format='json').status_code, 404)
        self.assertEqual(self.client.delete(f'{T}conquistas/{a["id"]}/').status_code, 404)
        r = self.client.patch(f'{T}conquistas/{plataforma.id}/', {'activa': False}, format='json')
        self.assertEqual(r.status_code, 403)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{T}conquistas/').status_code, 403)
        # As rotas antigas (practice/teacher/achievements) ficaram só para o administrador.
        self.entrar(self.prof_a)
        self.assertEqual(self.client.get('/api/v1/practice/teacher/achievements/').status_code, 403)
        self.entrar(self.admin)
        self.assertEqual(self.client.get('/api/v1/practice/teacher/achievements/').status_code, 200)
        self.assertEqual(self.client.patch(f'{T}conquistas/{plataforma.id}/', {'activa': False},
                                           format='json').status_code, 200)

    def test_atribuicao_so_conta_os_cursos_da_conquista(self):
        a = self.client.post(f'{T}conquistas/', _corpo_conquista(self.curso_a, tipo='pontos', meta=20),
                             format='json').data
        todos = self.client.post(f'{T}conquistas/', _corpo_conquista(None, tipo='pontos', meta=30, nome='Todos'),
                                 format='json').data
        plataforma = Achievement.objects.create(title='Plataforma', description='x', icon='P', category='milestone',
                                                points=5, requirement_type='points_earned', requirement_target=25)
        CourseEnrollment.objects.create(user=self.aluno, course=self.curso_b)
        CourseEnrollment.objects.create(user=self.aluno, course=self.curso_a2)

        def tem(conquista_id):
            return UserAchievement.objects.filter(user=self.aluno, achievement_id=conquista_id,
                                                  is_unlocked=True).exists()

        self.pontos(self.aluno, 25, self.curso_b)      # noutro professor: só conta para a plataforma
        self.assertFalse(tem(a['id']))
        self.assertFalse(tem(todos['id']))
        self.assertTrue(tem(plataforma.id))
        self.pontos(self.aluno, 15, self.curso_a2)     # outro curso da Ana: conta para "todos", não para curso_a
        self.assertFalse(tem(a['id']))
        self.assertFalse(tem(todos['id']))
        self.pontos(self.aluno, 20, self.curso_a)
        self.assertTrue(tem(a['id']))
        self.assertTrue(tem(todos['id']))
        self.assertTrue(Notification.objects.filter(user=self.aluno, dedupe_key=f'conquista:{a["id"]}').exists())
        # alunos_que_tem conta só os alunos dos cursos da Ana; apagar com quem a tenha: 409.
        item = next(x for x in self.client.get(f'{T}conquistas/').data['resultados'] if x['id'] == a['id'])
        self.assertEqual(item['alunos_que_tem'], 1)
        r = self.client.delete(f'{T}conquistas/{a["id"]}/')
        self.assertEqual(r.status_code, 409)
        self.assertIn('desligue', r.data['message'])

    def test_licoes_no_curso_e_ecra_do_aluno(self):
        pratica = Course.objects.create(teacher=self.prof_a, teacherName='Ana', title='Prática da Ana',
                                        description='x', course_type='practice', status='Published')
        outra = Course.objects.create(teacher=self.prof_b, teacherName='B', title='Prática do Bruno',
                                      description='x', course_type='practice', status='Published')
        CourseEnrollment.objects.create(user=self.aluno, course=pratica)
        l_a = PracticeLesson.objects.create(unit=PracticeUnit.objects.create(course=pratica, title='U', order=1),
                                            title='L', order=1)
        l_b = PracticeLesson.objects.create(unit=PracticeUnit.objects.create(course=outra, title='U', order=1),
                                            title='L', order=1)
        a = self.client.post(f'{T}conquistas/', _corpo_conquista(pratica, tipo='licoes', meta=1),
                             format='json').data
        LessonCompletion.objects.create(user=self.aluno, lesson=l_b, last_completed_at=timezone.now())
        verificar_conquistas_professor(self.aluno)
        self.assertFalse(UserAchievement.objects.filter(achievement_id=a['id'], is_unlocked=True).exists())

        self.entrar(self.aluno)
        lista = self.client.get('/api/v1/student/practice-courses/achievements/').data
        item = next(x for x in lista if x['id'] == a['id'])
        self.assertFalse(item['isUnlocked'])
        self.assertEqual(item['progress']['current'], 0)
        self.assertEqual(item['professor'], {'curso': {'id': str(pratica.id), 'titulo': 'Prática da Ana'}})

        LessonCompletion.objects.create(user=self.aluno, lesson=l_a, last_completed_at=timezone.now())
        lista = self.client.get('/api/v1/student/practice-courses/achievements/').data
        self.assertTrue(next(x for x in lista if x['id'] == a['id'])['isUnlocked'])
        # Quem não é aluno da Ana não vê a conquista.
        self.entrar(self.fora)
        lista = self.client.get('/api/v1/student/practice-courses/achievements/').data
        self.assertFalse(any(x['id'] == a['id'] for x in lista))


# ---------------------------------------------------------------------------
# Competições
# ---------------------------------------------------------------------------

class CompeticoesTests(Base):

    def corpo(self, **extra):
        hoje = timezone.localtime(timezone.now(), competicoes.FUSO).date()
        return {'nome': 'Maratona de Novembro', 'cursos': [str(self.curso_a.id)], 'conta': 'pontos',
                'inicio': hoje.isoformat(), 'fim': (hoje + timedelta(days=6)).isoformat(),
                'premio': 'certificado_merito', 'premio_lugares': 1, **extra}

    def criar(self, **extra):
        r = self.client.post(f'{T}competicoes/', self.corpo(**extra), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def recuar(self, cid, dias_inicio=2, dias_fim=None):
        agora = timezone.now()
        campos = {'start_date': agora - timedelta(days=dias_inicio)}
        if dias_fim is not None:
            campos['end_date'] = agora - timedelta(days=dias_fim)
        Competition.objects.filter(pk=cid).update(**campos)

    def test_premio_plano_so_admin_e_validacao(self):
        r = self.client.post(f'{T}competicoes/', self.corpo(premio='plano'), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('administrador', r.data['details']['premio'][0])
        hoje = timezone.localtime(timezone.now(), competicoes.FUSO).date()
        r = self.client.post(f'{T}competicoes/', self.corpo(
            inicio=(hoje - timedelta(days=1)).isoformat(), fim=(hoje + timedelta(days=40)).isoformat(),
            cursos=[str(self.curso_b.id)], premio_lugares=11), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data['details']), {'inicio', 'cursos', 'premio_lugares'})
        r = self.client.post(f'{T}competicoes/', self.corpo(fim=(hoje + timedelta(days=31)).isoformat()),
                             format='json')
        self.assertEqual(r.data['details']['fim'], ['Uma competição pode durar no máximo 31 dias.'])
        self.entrar(self.admin)
        self.assertEqual(self.client.post(f'{T}competicoes/', self.corpo(premio='plano', cursos=[]),
                                          format='json').status_code, 201)

    def test_lista_e_permissoes(self):
        c = self.criar(cursos=[])
        self.assertTrue(c['todos_os_cursos'])
        self.assertEqual({x['titulo'] for x in c['cursos']}, {'Inglês Petróleo', 'Inglês Banca'})
        self.assertEqual(c['estado'], 'activa')
        self.assertEqual(c['participantes'], 2)
        r = self.client.get(f'{T}competicoes/')
        self.assertEqual(r.data['numeros']['activas'], 1)
        self.assertEqual(r.data['numeros']['participantes'], 2)
        self.assertEqual(r.data['numeros']['pct_activos'], 0)
        self.assertEqual(set(r.data['resultados'][0]), {
            'id', 'nome', 'cursos', 'todos_os_cursos', 'estado', 'conta', 'inicio', 'fim', 'participantes',
            'premio', 'premio_lugares', 'tempo_decorrido', 'minha'})
        # Já começou: só nome e prémio; não se apaga.
        r = self.client.patch(f'{T}competicoes/{c["id"]}/', {'conta': 'licoes'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.client.patch(f'{T}competicoes/{c["id"]}/', {'nome': 'Maratona final'},
                                           format='json').data['nome'], 'Maratona final')
        self.recuar(c['id'])
        self.assertEqual(self.client.delete(f'{T}competicoes/{c["id"]}/').status_code, 409)
        self.entrar(self.prof_b)
        self.assertEqual(self.client.get(f'{T}competicoes/{c["id"]}/classificacao/').status_code, 404)
        self.assertEqual(self.client.patch(f'{T}competicoes/{c["id"]}/', {'nome': 'xyz'},
                                           format='json').status_code, 404)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(f'{T}competicoes/').status_code, 403)

    def test_agendada_altera_e_apaga(self):
        hoje = timezone.localtime(timezone.now(), competicoes.FUSO).date()
        c = self.criar(inicio=(hoje + timedelta(days=2)).isoformat(), fim=(hoje + timedelta(days=5)).isoformat())
        self.assertEqual(c['estado'], 'agendada')
        r = self.client.patch(f'{T}competicoes/{c["id"]}/', {'conta': 'licoes', 'fim': (hoje + timedelta(days=9))
                                                            .isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['conta'], r.data['fim']), ('licoes', (hoje + timedelta(days=9)).isoformat()))
        self.assertEqual(self.client.delete(f'{T}competicoes/{c["id"]}/').status_code, 204)

    def test_classificacao_fecho_e_premio(self):
        c = self.criar(premio_lugares=1)
        self.recuar(c['id'])
        self.pontos(self.aluno, 30, self.curso_a)
        self.pontos(self.aluno2, 10, self.curso_a)
        self.pontos(self.aluno2, 500, self.curso_b)   # noutro curso: não conta
        self.pontos(self.fora, 900, self.curso_b)      # não participa
        r = self.client.get(f'{T}competicoes/{c["id"]}/classificacao/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['conta'], 'pontos')
        self.assertEqual([(l['lugar'], l['nome'], l['valor']) for l in r.data['linhas']],
                         [(1, 'Ana E.', 30), (2, 'Carlos D.', 10)])
        # Ecrã do aluno: liga e lista de competições mostram a competição do curso.
        self.entrar(self.aluno)
        liga = self.client.get('/api/v1/student/practice-courses/liga/semana/').data
        self.assertEqual(liga['competicoes'][0]['meu_lugar'], 1)
        comps = self.client.get('/api/v1/practice/leaderboard/competitions/').data
        self.assertIn(c['id'], [x['id'] for x in comps])
        self.assertEqual(self.client.post(f'/api/v1/practice/leaderboard/competitions/{c["id"]}/join/')
                         .status_code, 400)
        self.entrar(self.fora)
        self.assertEqual(self.client.get('/api/v1/student/practice-courses/liga/semana/').data['competicoes'], [])

        # Início avisado uma vez; fecho atribui o prémio ao 1.º e avisa-o.
        competicoes.processar()
        self.assertEqual(Notification.objects.filter(dedupe_key=f'competicao:{c["id"]}:inicio').count(), 2)
        self.recuar(c['id'], dias_inicio=5, dias_fim=1)
        PointsEntry.objects.update(created_at=timezone.now() - timedelta(hours=36))
        self.pontos(self.aluno2, 100, self.curso_a)     # depois do fim: não conta
        self.assertEqual(competicoes.processar(), (0, 1))
        self.assertEqual(competicoes.processar(), (0, 0))
        p = CompetitionParticipant.objects.get(competition_id=c['id'], user=self.aluno)
        self.assertEqual((p.current_rank, p.valor, p.premio), (1, 30, 'certificado_merito'))
        self.assertEqual(CompetitionParticipant.objects.get(competition_id=c['id'], user=self.aluno2).premio, '')
        aviso = Notification.objects.get(user=self.aluno, dedupe_key=f'competicao:{c["id"]}:premio')
        self.assertIn('/certificado/', aviso.link)
        self.assertFalse(Notification.objects.filter(user=self.aluno2, dedupe_key__endswith=':premio').exists())
        self.entrar(self.aluno)
        r = self.client.get(f'/api/v1/practice/competicoes/{c["id"]}/certificado/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Certificado de mérito', r.content.decode())
        self.assertIn('Ana Maria Esteves', r.content.decode())
        self.entrar(self.aluno2)
        self.assertEqual(self.client.get(f'/api/v1/practice/competicoes/{c["id"]}/certificado/').status_code, 404)
        # Terminada: não se altera.
        self.entrar(self.prof_a)
        self.assertEqual(self.client.patch(f'{T}competicoes/{c["id"]}/', {'nome': 'Nova'},
                                           format='json').status_code, 409)

    def test_medalha_e_minutos_de_conversa(self):
        c = self.criar(conta='minutos_conversa', premio='medalha', premio_lugares=2)
        self.recuar(c['id'])
        VapiSession.objects.create(session_id='m1', user=self.aluno2, level='B1', domain='general',
                                   duration_minutes=7, status=VapiSession.STATUS_AVALIADA, situation='pedir_relatorio')
        VapiSession.objects.filter(session_id='m1').update(created_at=timezone.now() - timedelta(hours=36))
        linhas = self.client.get(f'{T}competicoes/{c["id"]}/classificacao/').data['linhas']
        self.assertEqual([(l['nome'], l['valor']) for l in linhas], [('Carlos D.', 7), ('Ana E.', 0)])
        self.recuar(c['id'], dias_inicio=5, dias_fim=1)
        competicoes.processar()
        # Só quem tem valor > 0 ganha, mesmo com 2 lugares premiados.
        self.assertEqual(list(CompetitionParticipant.objects.filter(competition_id=c['id'], premio='medalha')
                              .values_list('user__name', flat=True)), ['Carlos Dias'])
        self.assertTrue(Notification.objects.filter(user=self.aluno2, title__startswith='Ganhou uma medalha').exists())
