"""
Integration tests for Teacher Practice Courses APIs.

Tests teacher access to practice course management including:
- Course CRUD operations (via practice app)
- Authentication and permissions
- Practice-specific features
- Gamification management
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course
from apps.practice.models import PracticeUnit, PracticeLesson, PracticeChallenge
from tests.factories import TeacherFactory, StudentFactory, PracticeCourseFactory

# A gestão de cursos de prática do professor é a da app practice, montada em dois prefixos.
# As raízes (/api/v1/practice/ e /api/v1/teacher/practice-courses/) não têm vista: a lista
# está em courses/, a criação em courses/create/ e publicar/apagar em courses/<id>/.
PRATICA_PROF = '/api/v1/teacher/practice-courses/courses/'
PRATICA_APP = '/api/v1/practice/courses/'


class TeacherPracticeCoursesAPITest(APITestCase):
    """Test teacher practice course API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.teacher = TeacherFactory()
        self.other_teacher = TeacherFactory()
        self.student = StudentFactory()
        
        # Create practice courses
        self.teacher_practice_course = PracticeCourseFactory(teacher=self.teacher, status='Published')
        self.teacher_draft_practice_course = PracticeCourseFactory(teacher=self.teacher, status='Draft')
        self.other_teacher_practice_course = PracticeCourseFactory(teacher=self.other_teacher, status='Published')
    
    def get_jwt_token(self, user):
        """Get JWT token for user authentication."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def authenticate_as_teacher(self):
        """Authenticate client as teacher."""
        token = self.get_jwt_token(self.teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def authenticate_as_student(self):
        """Authenticate client as student."""
        token = self.get_jwt_token(self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def test_teacher_practice_endpoints_redirect_to_practice_app(self):
        """teacher/practice-courses/ é a mesma app practice: as duas listas dão os mesmos cursos."""
        self.authenticate_as_teacher()

        listas = {}
        for url in (PRATICA_PROF, PRATICA_APP):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                listas[url] = {c['courseId'] for c in response.json()}
        self.assertEqual(listas[PRATICA_PROF], listas[PRATICA_APP])
        self.assertEqual(listas[PRATICA_PROF], {
            str(self.teacher_practice_course.id), str(self.teacher_draft_practice_course.id)
        })

    def test_teacher_authentication_required_for_practice_management(self):
        """Test that practice course management requires authentication."""
        # Test without authentication
        response = self.client.get(PRATICA_PROF)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(f'{PRATICA_PROF}create/', {'title': 'Sem sessão'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.delete(f'{PRATICA_PROF}{self.teacher_draft_practice_course.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Course.objects.filter(id=self.teacher_draft_practice_course.id).exists())

    def test_student_cannot_access_teacher_practice_endpoints(self):
        """O aluno só vê o catálogo (nada de rascunhos) e não cria, publica nem apaga cursos."""
        self.authenticate_as_student()

        response = self.client.get(PRATICA_PROF)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {c['courseId'] for c in response.json()}
        self.assertNotIn(str(self.teacher_draft_practice_course.id), ids)
        self.assertEqual(
            set(Course.objects.filter(id__in=ids).values_list('status', flat=True)) - {'Published'}, set()
        )

        dados = {'title': 'Curso do aluno', 'description': 'Não devia ser criado', 'category': 'General'}
        response = self.client.post(f'{PRATICA_PROF}create/', dados, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Course.objects.filter(title='Curso do aluno').exists())

        url = f'{PRATICA_PROF}{self.teacher_draft_practice_course.id}/'
        self.assertEqual(self.client.put(url, {'action': 'publish'}, format='json').status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Course.objects.filter(id=self.teacher_draft_practice_course.id).exists())

    def test_practice_course_type_separation(self):
        """Test that practice courses are properly separated from video courses."""
        self.authenticate_as_teacher()
        
        # Create a video course for comparison
        video_course = Course.objects.create(
            teacher=self.teacher,
            teacherName=self.teacher.name,
            title="Video Course",
            description="A video course",
            course_type='video',
            status='Published'
        )
        
        # Verify course types are different
        self.assertEqual(self.teacher_practice_course.course_type, 'practice')
        self.assertEqual(video_course.course_type, 'video')
        
        # Verify they are stored correctly
        practice_courses = Course.objects.filter(course_type='practice', teacher=self.teacher)
        video_courses = Course.objects.filter(course_type='video', teacher=self.teacher)
        
        self.assertIn(self.teacher_practice_course, practice_courses)
        self.assertNotIn(video_course, practice_courses)
        self.assertIn(video_course, video_courses)
        self.assertNotIn(self.teacher_practice_course, video_courses)


@pytest.mark.django_db
class TeacherPracticeCoursesPermissionsTest(APITestCase):
    """Test permissions and access control for teacher practice courses."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.teacher = TeacherFactory()
        self.student = StudentFactory()
    
    def get_jwt_token(self, user):
        """Get JWT token for user authentication."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_role_based_access_to_practice_management(self):
        """Test that only teachers can access practice course management."""
        dados = {'title': 'Curso novo', 'description': 'Um curso de prática novo', 'category': 'General'}

        # Test with student credentials
        student_token = self.get_jwt_token(self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_token}')
        response = self.client.post(f'{PRATICA_PROF}create/', dados, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Course.objects.filter(title='Curso novo').exists())

        # Test with teacher credentials
        teacher_token = self.get_jwt_token(self.teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_token}')
        self.assertEqual(self.client.get(PRATICA_PROF).status_code, status.HTTP_200_OK)
        response = self.client.post(f'{PRATICA_PROF}create/', dados, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        curso = Course.objects.get(title='Curso novo')
        self.assertEqual((curso.teacher, curso.course_type), (self.teacher, 'practice'))

@pytest.mark.django_db
class PracticeAppIntegrationTest(APITestCase):
    """Test integration between courses app and practice app."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.teacher = TeacherFactory()
        self.student = StudentFactory()
        
        # Create a practice course
        self.practice_course = Course.objects.create(
            teacher=self.teacher,
            teacherName=self.teacher.name,
            title="Practice Course",
            description="A practice course",
            course_type='practice',
            status='Published'
        )
    
    def get_jwt_token(self, user):
        """Get JWT token for user authentication."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_practice_course_exists_in_database(self):
        """Test that practice courses are properly stored."""
        # Verify course exists and has correct type
        self.assertTrue(Course.objects.filter(
            id=self.practice_course.id,
            course_type='practice'
        ).exists())
        
        # Verify course is accessible
        course = Course.objects.get(id=self.practice_course.id)
        self.assertEqual(course.course_type, 'practice')
        self.assertEqual(course.teacher, self.teacher)
    
    def test_practice_units_can_be_created(self):
        """Test that practice units can be created for practice courses."""
        # Create a practice unit
        practice_unit = PracticeUnit.objects.create(
            course=self.practice_course,
            title="Basic Unit",
            description="Basic practice unit",
            order=1
        )
        
        # Verify unit was created correctly
        self.assertEqual(practice_unit.course, self.practice_course)
        self.assertEqual(practice_unit.title, "Basic Unit")
        
        # Verify relationship works
        self.assertIn(practice_unit, self.practice_course.practice_units.all())
    
    def test_practice_lessons_can_be_created(self):
        """Test that practice lessons can be created for practice units."""
        # Create unit first
        practice_unit = PracticeUnit.objects.create(
            course=self.practice_course,
            title="Basic Unit",
            description="Basic practice unit",
            order=1
        )
        
        # Create lesson
        practice_lesson = PracticeLesson.objects.create(
            unit=practice_unit,
            title="Basic Lesson",
            order=1
        )
        
        # Verify lesson was created correctly
        self.assertEqual(practice_lesson.unit, practice_unit)
        self.assertEqual(practice_lesson.title, "Basic Lesson")
        
        # Verify relationship works
        self.assertIn(practice_lesson, practice_unit.lessons.all())
    
    def test_practice_challenges_can_be_created(self):
        """Test that practice challenges can be created for practice lessons."""
        # Create unit and lesson first
        practice_unit = PracticeUnit.objects.create(
            course=self.practice_course,
            title="Basic Unit",
            description="Basic practice unit",
            order=1
        )
        
        practice_lesson = PracticeLesson.objects.create(
            unit=practice_unit,
            title="Basic Lesson",
            order=1
        )
        
        # Create challenge
        practice_challenge = PracticeChallenge.objects.create(
            lesson=practice_lesson,
            type="SELECT",
            question="What is the correct answer?",
            order=1
        )
        
        # Verify challenge was created correctly
        self.assertEqual(practice_challenge.lesson, practice_lesson)
        self.assertEqual(practice_challenge.type, "SELECT")
        
        # Verify relationship works
        self.assertIn(practice_challenge, practice_lesson.challenges.all())


@pytest.mark.django_db
class PracticeCoursesEndpointsTest(APITestCase):
    """Test that practice course endpoints exist and are accessible."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.teacher = TeacherFactory()
    
    def get_jwt_token(self, user):
        """Get JWT token for user authentication."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_practice_app_endpoints_exist(self):
        """Test that practice app endpoints exist."""
        token = self.get_jwt_token(self.teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        for url in (PRATICA_APP, PRATICA_PROF):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_practice_course_management_flow(self):
        """Criar, ver na lista, tentar publicar (vai para revisão só se estiver pronto) e apagar."""
        token = self.get_jwt_token(self.teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.post(f'{PRATICA_PROF}create/', {
            'title': 'Test Practice Course', 'description': 'A test practice course',
            'category': 'General', 'level': 'B1', 'status': 'Published',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        practice_course = Course.objects.get(id=response.json()['courseId'])
        self.assertEqual((practice_course.course_type, practice_course.teacher), ('practice', self.teacher))
        # O pedido não publica: um curso novo é rascunho.
        self.assertEqual(practice_course.status, 'Draft')

        ids = {c['courseId'] for c in self.client.get(PRATICA_PROF).json()}
        self.assertIn(str(practice_course.id), ids)

        # Publicar um curso vazio não passa da lista de verificação.
        url = f'{PRATICA_PROF}{practice_course.id}/'
        response = self.client.put(url, {'action': 'publish'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        practice_course.refresh_from_db()
        self.assertEqual(practice_course.status, 'Draft')

        # Um rascunho apaga-se.
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Course.objects.filter(id=practice_course.id).exists())
