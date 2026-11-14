"""
Tests for the student study-tracking endpoints of the practice lab:
study-streak, study-goal, hearts-status, refill-hearts, course detail,
complete-lesson, review-words, notifications and student-analytics.

Run:
    ./venv/bin/python manage.py test apps.courses.api.tests.test_student_study_tracking \
        --settings=core.test_settings
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice.models import (
    Achievement,
    ChallengeAttempt,
    ChallengeOption,
    ChallengeProgress,
    DailyStudyLog,
    LessonCompletion,
    PracticeChallenge,
    PracticeLesson,
    PracticeUnit,
    UserProgress,
    UserStreak,
)
from apps.subscriptions.models import SubscriptionPlan, UserSubscription
from apps.users.models import Notification

User = get_user_model()

BASE = '/api/v1/student/practice-courses/'


class StudyTrackingTestBase(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(
            email='teacher-study@example.com', name='Teacher', password='password123', role='teacher'
        )
        self.student = User.objects.create_user(
            email='student-study@example.com', name='Student', password='password123', role='student'
        )
        self.other = User.objects.create_user(
            email='other-study@example.com', name='Other', password='password123', role='student'
        )
        self.course = Course.objects.create(
            teacher=self.teacher, teacherName=self.teacher.name, title='Inglês Prático',
            description='Curso de prática', course_type='practice', status='Published',
        )
        self.unit = PracticeUnit.objects.create(course=self.course, title='Unidade 1', description='', order=1)
        self.lesson = PracticeLesson.objects.create(unit=self.unit, title='Saudações', order=1)
        self.lesson2 = PracticeLesson.objects.create(unit=self.unit, title='Família', order=2)
        self.ch1 = self._challenge(self.lesson, 1, 'How do you say "Olá"?', 'Hello', 'Goodbye')
        self.ch2 = self._challenge(self.lesson, 2, 'How do you say "Obrigado"?', 'Thank you', 'Please')
        self.ch3 = self._challenge(self.lesson2, 1, 'Father of your father?', 'Grandfather', 'Uncle')

        self.subscription = UserSubscription.objects.select_related('plan').get(user=self.student)
        self.max_hearts = self.subscription.plan.hearts_limit
        self.authenticate(self.student)

    # -- helpers -------------------------------------------------------------

    def _challenge(self, lesson, order, question, right, wrong):
        ch = PracticeChallenge.objects.create(lesson=lesson, type='SELECT', question=question, order=order)
        ch.right = ChallengeOption.objects.create(challenge=ch, text=right, is_correct=True, order=1)
        ch.wrong = ChallengeOption.objects.create(challenge=ch, text=wrong, is_correct=False, order=2)
        return ch

    def authenticate(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def answer(self, challenge, correct=True):
        # Bypass the 2s duplicate-submission guard of ChallengeProgressView
        ChallengeProgress.objects.filter(user=self.student, challenge=challenge).update(
            updated_at=timezone.now() - timedelta(seconds=30)
        )
        option = challenge.right if correct else challenge.wrong
        resp = self.client.post(
            f'{BASE}challenge-progress/', {'challenge_id': str(challenge.id), 'selected_option': str(option.id)},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp

    def respondido_ha(self, minutos):
        """As respostas da lição foram dadas há `minutos`: o servidor só credita o tempo que viu passar."""
        ChallengeProgress.objects.filter(user=self.student).update(
            updated_at=timezone.now() - timedelta(minutes=minutos))

    def complete(self, lesson=None, duration=120):
        return self.client.post(
            f'{BASE}complete-lesson/',
            {'lesson_id': str((lesson or self.lesson).id), 'duration_seconds': duration},
            format='json',
        )

    def set_hearts(self, value):
        UserSubscription.objects.filter(user=self.student).update(
            current_hearts=value, last_heart_recharge=timezone.now()
        )

    def points(self):
        return UserProgress.objects.get(user=self.student).points

    def make_unlimited(self):
        plan = SubscriptionPlan.objects.get(plan_type='PREMIUM')
        self.assertEqual(plan.hearts_limit, 0)
        UserSubscription.objects.filter(user=self.student).update(
            plan=plan, status='ACTIVE', expires_at=timezone.now() + timedelta(days=30), current_hearts=999
        )


class AuthRequiredTests(StudyTrackingTestBase):

    def test_endpoints_require_authentication(self):
        self.client.credentials()
        notification = Notification.notify(self.student, 'system', 'Olá')
        cases = [
            ('get', 'study-streak/'), ('get', 'study-goal/'), ('patch', 'study-goal/'),
            ('get', 'hearts-status/'), ('get', f'courses/{self.course.id}/'),
            ('post', 'complete-lesson/'), ('get', 'review-words/'), ('get', 'notifications/'),
            ('post', f'notifications/{notification.id}/read/'), ('post', 'notifications/read-all/'),
            ('get', 'student-analytics/'),
        ]
        for method, path in cases:
            resp = getattr(self.client, method)(BASE + path, {}, format='json')
            self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED, f'{method} {path}')


class StudyGoalAndStreakTests(StudyTrackingTestBase):

    def test_goal_default_and_update(self):
        resp = self.client.get(f'{BASE}study-goal/')
        self.assertEqual(resp.json(), {'daily_goal_minutes': 10})
        resp = self.client.patch(f'{BASE}study-goal/', {'daily_goal_minutes': 15}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['daily_goal_minutes'], 15)
        self.assertEqual(UserStreak.objects.get(user=self.student).daily_goal_minutes, 15)

    def test_goal_validation(self):
        for bad in (7, 0, 30, 'abc', None):
            resp = self.client.patch(f'{BASE}study-goal/', {'daily_goal_minutes': bad}, format='json')
            self.assertEqual(resp.status_code, 400, bad)
            self.assertIn('message', resp.json())
        resp = self.client.patch(f'{BASE}study-goal/', {'daily_goal_minutes': 7}, format='json')
        self.assertIn('Meta diária inválida', resp.json()['message'])
        resp = self.client.patch(f'{BASE}study-goal/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_streak_empty_state(self):
        data = self.client.get(f'{BASE}study-streak/').json()
        self.assertEqual(data['current_streak'], 0)
        self.assertFalse(data['practiced_today'])
        self.assertEqual(data['minutes_today'], 0)
        self.assertFalse(data['goal_completed'])
        self.assertEqual(len(data['week']), 7)
        today = timezone.localdate()
        self.assertEqual(data['week'][0]['date'], (today - timedelta(days=6)).isoformat())
        self.assertEqual(data['week'][-1]['date'], today.isoformat())

    def test_goal_completed_transition_and_single_notification(self):
        self.client.patch(f'{BASE}study-goal/', {'daily_goal_minutes': 5}, format='json')
        r1 = DailyStudyLog.add_minutes(self.student, 'lesson', 3)
        self.assertFalse(r1['goal_completed'])
        data = self.client.get(f'{BASE}study-streak/').json()
        self.assertFalse(data['goal_completed'])
        self.assertEqual(data['current_streak'], 1)
        self.assertEqual(data['longest_streak'], 1)
        self.assertTrue(data['practiced_today'])

        r2 = DailyStudyLog.add_minutes(self.student, 'video', 2.5)
        self.assertTrue(r2['goal_just_completed'])
        r3 = DailyStudyLog.add_minutes(self.student, 'conversation', 5)
        self.assertTrue(r3['goal_completed'])
        self.assertFalse(r3['goal_just_completed'])

        data = self.client.get(f'{BASE}study-streak/').json()
        self.assertTrue(data['goal_completed'])
        self.assertEqual(data['minutes_today'], 10)
        self.assertTrue(data['week'][-1]['goal_met'])
        self.assertEqual(Notification.objects.filter(user=self.student, kind='streak').count(), 1)

    def test_broken_streak_reports_zero(self):
        UserStreak.objects.create(
            user=self.student, current_streak=4, longest_streak=6,
            last_practice_date=timezone.localdate() - timedelta(days=3),
        )
        data = self.client.get(f'{BASE}study-streak/').json()
        self.assertEqual(data['current_streak'], 0)
        self.assertEqual(data['longest_streak'], 6)


class HeartsTests(StudyTrackingTestBase):

    def test_hearts_status_full(self):
        data = self.client.get(f'{BASE}hearts-status/').json()
        self.assertEqual(data['current'], self.max_hearts)
        self.assertEqual(data['maximum'], self.max_hearts)
        self.assertFalse(data['unlimited'])
        self.assertIsNone(data['next_heart_at'])
        self.assertEqual(data['refill_cost_points'], 50)
        self.assertFalse(data['can_refill_with_points'])

    def test_hearts_status_below_max_with_points(self):
        self.set_hearts(1)
        UserProgress.objects.create(user=self.student, points=60)
        data = self.client.get(f'{BASE}hearts-status/').json()
        self.assertEqual(data['current'], 1)
        self.assertIsNotNone(data['next_heart_at'])
        self.assertTrue(data['can_refill_with_points'])

    def test_hearts_status_unlimited(self):
        self.make_unlimited()
        data = self.client.get(f'{BASE}hearts-status/').json()
        self.assertTrue(data['unlimited'])
        self.assertEqual(data['current'], 999)
        self.assertFalse(data['can_refill_with_points'])

    def test_refill_costs_50_points(self):
        self.set_hearts(1)
        UserProgress.objects.create(user=self.student, points=40)
        resp = self.client.post(f'{BASE}refill-hearts/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'insufficient_points')

        UserProgress.objects.filter(user=self.student).update(points=60)
        resp = self.client.post(f'{BASE}refill-hearts/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['hearts'], self.max_hearts)
        self.assertEqual(resp.json()['points'], 10)

        resp = self.client.post(f'{BASE}refill-hearts/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'hearts_full')


class CourseDetailTests(StudyTrackingTestBase):

    def test_course_detail_with_progress(self):
        self.answer(self.ch1)
        self.answer(self.ch2)
        resp = self.client.get(f'{BASE}courses/{self.course.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['units_count'], 1)
        self.assertEqual(data['lessons_count'], 2)
        self.assertEqual(data['challenges_count'], 3)
        self.assertFalse(data['is_active_course'])
        self.assertEqual(data['progress'], {'completed_lessons': 1, 'total_lessons': 2, 'percentage': 50})

    def test_active_course_flag(self):
        UserProgress.objects.create(user=self.student, active_course=self.course)
        data = self.client.get(f'{BASE}courses/{self.course.id}/').json()
        self.assertTrue(data['is_active_course'])

    def test_course_detail_404(self):
        draft = Course.objects.create(
            teacher=self.teacher, teacherName='T', title='Draft', description='d',
            course_type='practice', status='Draft',
        )
        video = Course.objects.create(
            teacher=self.teacher, teacherName='T', title='Video', description='d',
            course_type='video', status='Published',
        )
        for course in (draft, video):
            resp = self.client.get(f'{BASE}courses/{course.id}/')
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json()['message'], 'Curso de prática não encontrado.')


class CompleteLessonTests(StudyTrackingTestBase):

    def test_validation(self):
        resp = self.client.post(f'{BASE}complete-lesson/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(f'{BASE}complete-lesson/', {'lesson_id': 'nope'}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            f'{BASE}complete-lesson/', {'lesson_id': str(self.lesson.id), 'duration_seconds': -5}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        import uuid
        resp = self.client.post(f'{BASE}complete-lesson/', {'lesson_id': str(uuid.uuid4())}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_incomplete_lesson_rejected(self):
        self.answer(self.ch1)
        resp = self.complete()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'lesson_not_completed')
        self.assertIn('1/2', resp.json()['message'])
        self.assertFalse(LessonCompletion.objects.exists())

    def test_first_completion_bonus_is_idempotent(self):
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.assertEqual(self.points(), 20)
        self.respondido_ha(10)

        resp = self.complete(duration=180)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['first_completion'])
        self.assertEqual(data['points_awarded'], 10)
        self.assertEqual(data['total_points'], 30)
        self.assertEqual(data['streak'], 1)
        self.assertEqual(data['minutes_today'], 3)
        self.assertEqual(data['daily_goal_minutes'], 10)
        self.assertFalse(data['goal_completed'])

        # Same request again (double submit): nothing more is awarded or logged
        data = self.complete(duration=180).json()
        self.assertFalse(data['first_completion'])
        self.assertEqual(data['points_awarded'], 0)
        self.assertTrue(data['already_recorded'])
        self.assertEqual(data['total_points'], 30)
        self.assertEqual(data['minutes_today'], 3)
        self.assertEqual(LessonCompletion.objects.get(user=self.student).times_completed, 1)
        self.assertEqual(DailyStudyLog.objects.get(user=self.student).lessons_completed, 1)

    def test_time_spent_alias_and_duration_clamp(self):
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.respondido_ha(120)
        resp = self.client.post(
            f'{BASE}complete-lesson/', {'lesson_id': str(self.lesson.id), 'time_spent': 99999}, format='json'
        )
        data = resp.json()
        self.assertEqual(data['minutes_today'], 60)
        self.assertTrue(data['goal_completed'])
        self.assertTrue(data['goal_just_completed'])

    def test_cliente_nao_decide_se_acertou_nem_os_pontos(self):
        """Campos de correcção e pontos enviados pelo cliente são ignorados: o servidor corrige pela opção."""
        UserProgress.objects.get_or_create(user=self.student, defaults={'points': 0})
        antes = self.points()
        resp = self.client.post(f'{BASE}challenge-progress/', {
            'challenge_id': str(self.ch1.id), 'selected_option': str(self.ch1.wrong.id),
            'is_correct': True, 'correct': True, 'completed': True, 'points': 100, 'points_earned': 100,
            'score': 100, 'heartsUsed': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.points(), antes)
        self.assertFalse(ChallengeProgress.objects.filter(user=self.student, challenge=self.ch1, completed=True).exists())
        # E não se conclui a lição sem as respostas certas, diga o cliente o que disser.
        self.assertEqual(self.complete(duration=60).status_code, 400)

    def test_duracao_limitada_ao_tempo_que_o_servidor_viu(self):
        """O cliente diz 60 min, mas as respostas foram dadas há 1 min: credita no máximo 1 min + a folga."""
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.respondido_ha(1)
        data = self.complete(duration=3600).json()
        self.assertLessEqual(data['minutes_today'], 2.1)
        self.assertGreater(data['minutes_today'], 0)

    def test_duracao_sem_respostas_desta_volta_nao_credita(self):
        """Praticar de novo sem refazer os exercícios não regista nada, nem minutos."""
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.respondido_ha(10)
        self.complete(duration=120)
        data = self.complete(duration=3600).json()
        self.assertTrue(data['already_recorded'])
        self.assertEqual(data['minutes_today'], 2)

    def test_repeat_practice_awards_points_and_heart(self):
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.complete()
        LessonCompletion.objects.filter(user=self.student).update(
            last_completed_at=timezone.now() - timedelta(minutes=5)
        )
        self.set_hearts(2)
        ChallengeProgress.objects.filter(user=self.student).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        # Practising again: wrong answers never cost hearts
        self.answer(self.ch1, correct=False)
        self.assertEqual(UserSubscription.objects.get(user=self.student).current_hearts, 2)
        # Regra do produto: na prática repetida, os exercícios certos não dão pontos nem vidas;
        # a recompensa é só a da lição (+5 pontos e +1 vida no total).
        hearts_before = UserSubscription.objects.get(user=self.student).current_hearts
        points_before = self.points()
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.assertEqual(self.points(), points_before)
        self.assertEqual(UserSubscription.objects.get(user=self.student).current_hearts, hearts_before)

        data = self.complete().json()
        self.assertFalse(data['first_completion'])
        self.assertFalse(data['already_recorded'])
        self.assertEqual(data['points_awarded'], 5)
        self.assertEqual(data['hearts_awarded'], 1)
        self.assertEqual(data['total_points'], points_before + 5)
        self.assertEqual(data['hearts'], min(self.max_hearts, hearts_before + 1))
        self.assertEqual(LessonCompletion.objects.get(user=self.student).times_completed, 2)
        self.assertEqual(DailyStudyLog.objects.get(user=self.student).lessons_completed, 2)

    def test_repeat_practice_heart_capped_at_max(self):
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.complete()
        LessonCompletion.objects.filter(user=self.student).update(
            last_completed_at=timezone.now() - timedelta(minutes=5)
        )
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.set_hearts(self.max_hearts)
        data = self.complete().json()
        self.assertEqual(data['points_awarded'], 5)
        self.assertEqual(data['hearts'], self.max_hearts)

    def test_repeat_practice_unlimited_hearts_unchanged(self):
        self.make_unlimited()
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.complete()
        LessonCompletion.objects.filter(user=self.student).update(
            last_completed_at=timezone.now() - timedelta(minutes=5)
        )
        self.answer(self.ch1)
        self.answer(self.ch2)
        data = self.complete().json()
        self.assertEqual(data['points_awarded'], 5)
        self.assertEqual(data['hearts_awarded'], 0)
        self.assertEqual(data['hearts'], 999)


class ReviewWordsTests(StudyTrackingTestBase):

    def test_review_selection(self):
        # Lição 1 já feita antes (a lição 2 só abre depois dela); errar agora é revisão.
        for ch in (self.ch1, self.ch2):
            ChallengeProgress.objects.create(user=self.student, challenge=ch, completed=True)
        self.answer(self.ch1, correct=False)
        self.answer(self.ch3, correct=False)
        self.answer(self.ch2)  # only correct -> never in review

        data = self.client.get(f'{BASE}review-words/').json()
        self.assertEqual(data['count'], 2)
        ids = [i['challenge_id'] for i in data['items']]
        self.assertEqual(set(ids), {str(self.ch1.id), str(self.ch3.id)})
        item = next(i for i in data['items'] if i['challenge_id'] == str(self.ch1.id))
        self.assertEqual(item['answer'], 'Hello')
        self.assertEqual(item['prompt'], self.ch1.question)
        self.assertEqual(item['lesson_title'], 'Saudações')

        # Fixed afterwards -> leaves the review list
        self.answer(self.ch1)
        data = self.client.get(f'{BASE}review-words/').json()
        self.assertEqual([i['challenge_id'] for i in data['items']], [str(self.ch3.id)])

    def test_old_mistakes_and_other_users_excluded(self):
        ChallengeAttempt.objects.create(user=self.student, challenge=self.ch1, is_correct=False)
        ChallengeAttempt.objects.filter(user=self.student).update(created_at=timezone.now() - timedelta(days=20))
        ChallengeAttempt.objects.create(user=self.other, challenge=self.ch2, is_correct=False)
        data = self.client.get(f'{BASE}review-words/').json()
        self.assertEqual(data, {'count': 0, 'items': []})

    def test_most_recent_first(self):
        a = ChallengeAttempt.objects.create(user=self.student, challenge=self.ch1, is_correct=False)
        b = ChallengeAttempt.objects.create(user=self.student, challenge=self.ch2, is_correct=False)
        ChallengeAttempt.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=1))
        ChallengeAttempt.objects.filter(pk=b.pk).update(created_at=timezone.now() - timedelta(days=3))
        ids = [i['challenge_id'] for i in self.client.get(f'{BASE}review-words/').json()['items']]
        self.assertEqual(ids, [str(self.ch1.id), str(self.ch2.id)])


class NotificationTests(StudyTrackingTestBase):

    def test_list_read_and_read_all(self):
        n1 = Notification.notify(self.student, 'system', 'Um')
        Notification.notify(self.student, 'course', 'Dois')
        Notification.notify(self.student, 'certificate', 'Três')
        foreign = Notification.notify(self.other, 'system', 'Alheia')

        data = self.client.get(f'{BASE}notifications/').json()
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['unread_count'], 3)
        self.assertEqual(data['results'][0]['title'], 'Três')  # newest first

        resp = self.client.post(f'{BASE}notifications/{n1.id}/read/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['notification']['is_read'])
        self.assertEqual(resp.json()['unread_count'], 2)

        resp = self.client.post(f'{BASE}notifications/{foreign.id}/read/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['message'], 'Notificação não encontrada.')

        resp = self.client.post(f'{BASE}notifications/read-all/')
        self.assertEqual(resp.json(), {'marked_read': 2, 'unread': 0, 'unread_count': 0})
        foreign.refresh_from_db()
        self.assertIsNone(foreign.read_at)

    def test_pagination(self):
        for i in range(25):
            Notification.notify(self.student, 'system', f'N{i}')
        data = self.client.get(f'{BASE}notifications/').json()
        self.assertEqual(len(data['results']), 20)
        self.assertIsNotNone(data['next'])
        data = self.client.get(f'{BASE}notifications/?page=2').json()
        self.assertEqual(len(data['results']), 5)

    def test_achievement_unlock_creates_notification(self):
        Achievement.objects.create(
            title='Primeiros pontos', description='Ganha 10 pontos', icon='*', category='milestone',
            points=0, requirement_type='points_earned', requirement_target=10, requirement_unit='points',
        )
        self.answer(self.ch1)
        notes = Notification.objects.filter(user=self.student, kind='achievement')
        self.assertEqual(notes.count(), 1)
        self.assertIn('Primeiros pontos', notes.first().title)
        # Existing endpoint still works
        resp = self.client.get(f'{BASE}achievements/notifications/')
        self.assertEqual(resp.status_code, 200)


class AnalyticsAndHooksTests(StudyTrackingTestBase):

    def test_student_analytics(self):
        self.answer(self.ch1, correct=False)
        self.answer(self.ch1)
        self.answer(self.ch2)
        self.respondido_ha(10)
        self.complete(duration=300)
        data = self.client.get(f'{BASE}student-analytics/').json()
        ov = data['overview']
        self.assertEqual(ov['lessonsCompleted'], 1)
        self.assertEqual(ov['averageAccuracy'], 67)
        self.assertEqual(ov['totalStudyTime'], 5)
        self.assertEqual(ov['currentStreak'], 1)
        self.assertEqual(ov['totalPoints'], self.points())
        self.assertEqual(len(data['performance']['accuracyTrend']), 7)
        self.assertEqual(data['performance']['accuracyTrend'][-1]['accuracy'], 67)
        self.assertEqual(data['progress']['weekly'][-1], {
            'day': data['progress']['weekly'][-1]['day'], 'isoDate': timezone.localdate().isoformat(),
            'lessons': 1, 'timeSpent': 5,
        })
        self.assertEqual(len(data['progress']['monthly']), 4)
        self.assertEqual(data['progress']['comparison']['rankPosition'], 1)
        self.assertIn('recommendations', data)

    def test_video_progress_logs_minutes(self):
        from apps.courses.matriculas import matricular_em_curso
        url = f'/api/v1/student/video-courses/users/{self.student.id}/progress/{self.course.id}/update/'
        # Sem inscrição não se regista progresso.
        self.assertEqual(self.client.put(url, {'sections': [], 'watched_seconds': 60}, format='json').status_code, 403)
        matricular_em_curso(self.student, self.course)
        from apps.courses.models import Chapter, CourseSection
        cap = Chapter.objects.create(section=CourseSection.objects.create(course=self.course, sectionTitle='S', order=1),
                                     title='Vídeo', content='x', type='Video', order=1,
                                     video='https://cdn.exemplo.ao/videos/v.mp4')  # sem vídeo ficava escondida
        # O aluno abre a aula (o crédito não passa do tempo real desde a abertura).
        from datetime import timedelta as _td
        from apps.courses.tempo_video import _chave_aberta
        from django.core.cache import cache
        cache.set(_chave_aberta(self.student.pk, cap.pk), (timezone.now() - _td(minutes=10)).timestamp(), 3600)
        resp = self.client.put(url, {'sections': [], 'watched_seconds': 240, 'chapter_id': str(cap.id)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        log = DailyStudyLog.objects.get(user=self.student)
        self.assertEqual(log.video_minutes, 4)
        self.assertEqual(UserStreak.objects.get(user=self.student).current_streak, 1)
        # Backwards compatible: no watched_seconds -> no extra minutes
        resp = self.client.put(url, {'sections': []}, format='json')
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.video_minutes, 4)


class ChallengeHeartsRegressionTests(StudyTrackingTestBase):

    def test_correct_answer_does_not_cost_heart_and_wrong_costs_one(self):
        UserProgress.objects.create(user=self.student)
        self.set_hearts(3)
        self.answer(self.ch1)
        self.assertEqual(UserSubscription.objects.get(user=self.student).current_hearts, 3)
        self.answer(self.ch2, correct=False)
        self.assertEqual(UserSubscription.objects.get(user=self.student).current_hearts, 2)
        self.assertEqual(ChallengeAttempt.objects.filter(user=self.student).count(), 2)
