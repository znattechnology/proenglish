"""
Integration tests for Teacher API endpoints.

Tests teacher access to both video courses and practice courses APIs,
including CRUD operations, authentication, permissions, and ownership validation.
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course, CourseSection, Chapter
from tests.factories import (
    TeacherFactory, StudentFactory, 
    PublishedVideoCourseFactory, VideoCourseFactory,
    PublishedPracticeCourseFactory, PracticeCourseFactory,
    CourseSectionFactory, ChapterFactory
)


class BaseTeacherAPITest(APITestCase):
    """Base class for teacher API tests."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.teacher = TeacherFactory()
        self.other_teacher = TeacherFactory()
        self.student = StudentFactory()
        
        # Create courses for main teacher
        self.teacher_video_course = PublishedVideoCourseFactory(teacher=self.teacher)
        self.teacher_practice_course = PublishedPracticeCourseFactory(teacher=self.teacher)
        self.teacher_draft_video = VideoCourseFactory(teacher=self.teacher, status='Draft')
        
        # Create courses for other teacher
        self.other_video_course = PublishedVideoCourseFactory(teacher=self.other_teacher)
        self.other_practice_course = PublishedPracticeCourseFactory(teacher=self.other_teacher)
        
        # Create course structure
        self.video_section = CourseSection.objects.create(
            course=self.teacher_video_course,
            sectionTitle='Video Section',
            order=1
        )
        self.video_chapter = Chapter.objects.create(
            section=self.video_section,
            title='Video Chapter',
            content='Video content',
            type='Video',
            video='https://example.com/video.mp4',
            order=1
        )
    
    def get_jwt_token(self, user):
        """Get JWT token for user authentication."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def authenticate_as_teacher(self):
        """Authenticate client as main teacher."""
        token = self.get_jwt_token(self.teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def authenticate_as_other_teacher(self):
        """Authenticate client as other teacher."""
        token = self.get_jwt_token(self.other_teacher)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def authenticate_as_student(self):
        """Authenticate client as student."""
        token = self.get_jwt_token(self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def video_list(self, response):
        """A lista do professor vem em {message, data: [...]}."""
        body = response.json()
        self.assertIn('message', body)
        return body['data']


# Os cursos de prática do professor vivem em /api/v1/teacher/practice-courses/courses/ (lista,
# criação em courses/create/, publicar/apagar em courses/<id>/). A raiz deixou de responder.
PRATICA = '/api/v1/teacher/practice-courses/courses/'


@pytest.mark.django_db
class TestTeacherVideoCourseAPI(BaseTeacherAPITest):
    """Test teacher video course API endpoints."""

    def test_teacher_list_own_video_courses(self):
        """Test teacher can list their own video courses."""
        self.authenticate_as_teacher()

        url = '/api/v1/teacher/video-courses/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.video_list(response)

        # Should see own video courses but not other teacher's
        course_ids = [course['courseId'] for course in data]
        self.assertIn(str(self.teacher_video_course.id), course_ids)
        self.assertIn(str(self.teacher_draft_video.id), course_ids)
        self.assertNotIn(str(self.other_video_course.id), course_ids)

        # Should not see practice courses in video endpoint
        self.assertNotIn(str(self.teacher_practice_course.id), course_ids)
        self.assertEqual({c['course_type'] for c in data}, {'video'})

    def test_teacher_create_video_course(self):
        """Test teacher can create new video courses."""
        self.authenticate_as_teacher()

        course_data = {
            'title': 'New Video Course',
            'description': 'A new course for testing',
            'category': 'Grammar',
            'level': 'A2',
            'status': 'Draft'
        }

        url = '/api/v1/teacher/video-courses/'
        response = self.client.post(url, course_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['data']

        self.assertEqual(data['title'], course_data['title'])
        self.assertEqual(data['teacherName'], self.teacher.name)

        # Verify in database
        course = Course.objects.get(id=data['courseId'])
        self.assertEqual(course.teacher, self.teacher)
        self.assertEqual(course.course_type, 'video')

    def test_teacher_update_own_video_course(self):
        """A edição antiga foi retirada (410): o curso edita-se em /api/v1/teacher/cursos/<id>/."""
        self.authenticate_as_teacher()
        url = f'/api/v1/teacher/video-courses/{self.teacher_draft_video.id}/'
        response = self.client.patch(url, {'title': 'Updated Video Course'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.teacher_draft_video.refresh_from_db()
        self.assertNotEqual(self.teacher_draft_video.title, 'Updated Video Course')

    def test_teacher_delete_own_video_course(self):
        """Um rascunho sem alunos apaga-se; um curso publicado não (409)."""
        self.authenticate_as_teacher()
        url = f'/api/v1/teacher/video-courses/{self.teacher_draft_video.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Course.objects.filter(id=self.teacher_draft_video.id).exists())

    def test_teacher_cannot_access_other_teacher_video_course(self):
        """O professor não vê nem altera cursos de outro professor (403, sem dados)."""
        self.authenticate_as_teacher()
        titulo = self.other_video_course.title

        url = f'/api/v1/teacher/video-courses/{self.other_video_course.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('data', response.json())

        # A edição pela rota antiga já não existe (410) para ninguém; o curso fica igual.
        response = self.client.patch(url, {'title': 'Hacked Title'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_410_GONE])
        self.other_video_course.refresh_from_db()
        self.assertEqual(self.other_video_course.title, titulo)

        # Apagar o curso de outro professor também não.
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Course.objects.filter(id=self.other_video_course.id).exists())

    def test_teacher_create_section_in_video_course(self):
        """Criar secções pela rota antiga foi retirado (410): usa-se o editor novo."""
        self.authenticate_as_teacher()
        url = f'/api/v1/teacher/video-courses/{self.teacher_video_course.id}/sections/'
        response = self.client.post(url, {'sectionTitle': 'New Video Section', 'order': 2}, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertFalse(CourseSection.objects.filter(sectionTitle='New Video Section').exists())

    def test_teacher_create_video_chapter(self):
        """Criar capítulos pela rota antiga foi retirado (410): usa-se o editor novo."""
        self.authenticate_as_teacher()
        url = f'/api/v1/teacher/video-courses/sections/{self.video_section.id}/chapters/'
        response = self.client.post(url, {'title': 'New Video Chapter', 'type': 'Video',
                                          'video': 'https://example.com/new-video.mp4'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)


@pytest.mark.django_db
class TestTeacherPracticeCourseAPI(BaseTeacherAPITest):
    """Test teacher practice course API endpoints.

    Os capítulos de exercício/questionário em cursos de prática deram lugar a unidades, lições e
    exercícios do editor novo (/api/v1/teacher/pratica/), testados em test_pratica_professor.
    """

    def test_teacher_list_own_practice_courses(self):
        """Test teacher can list their own practice courses."""
        self.authenticate_as_teacher()

        response = self.client.get(PRATICA)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should see own practice courses but not other teacher's
        course_ids = [course['courseId'] for course in data]
        self.assertIn(str(self.teacher_practice_course.id), course_ids)
        self.assertNotIn(str(self.other_practice_course.id), course_ids)

        # Should not see video courses in practice endpoint
        self.assertNotIn(str(self.teacher_video_course.id), course_ids)

    def test_teacher_create_practice_course(self):
        """Test teacher can create new practice courses."""
        self.authenticate_as_teacher()

        course_data = {
            'title': 'New Practice Course',
            'description': 'A new practice laboratory course',
            'category': 'General',  # Must be one of the valid categories
            'level': 'B1',
            'status': 'Draft'
        }

        url = '/api/v1/practice/courses/create/'
        response = self.client.post(url, course_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data['title'], course_data['title'])
        self.assertEqual(data['course_type'], 'practice')  # Auto-set to practice
        # teacherName uses email as fallback when name is not available
        self.assertIn(data['teacherName'], [self.teacher.name, self.teacher.email])

        # Verify in database using correct field name
        course = Course.objects.get(id=data['courseId'])
        self.assertEqual(course.teacher, self.teacher)
        self.assertEqual(course.course_type, 'practice')


@pytest.mark.django_db
class TestTeacherAPIAuthentication(BaseTeacherAPITest):
    """Test teacher API authentication requirements."""

    def test_teacher_endpoints_require_authentication(self):
        """Test that teacher endpoints require authentication."""
        # Video courses
        response = self.client.get('/api/v1/teacher/video-courses/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post('/api/v1/teacher/video-courses/', {'title': 'Test Course'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Practice courses
        response = self.client.get(PRATICA)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Course creation
        course_data = {'title': 'Test Course'}
        response = self.client.post(f'{PRATICA}create/', course_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Course.objects.filter(title='Test Course').exists())

    def test_students_cannot_access_teacher_endpoints(self):
        """Test that students cannot access teacher endpoints."""
        self.authenticate_as_student()

        # Try to access teacher video courses
        url = '/api/v1/teacher/video-courses/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try to create course as student (vídeo e prática)
        course_data = {'title': 'Student Course', 'description': 'Should not be created'}
        response = self.client.post(url, course_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post('/api/v1/courses/', course_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post(f'{PRATICA}create/', course_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Course.objects.filter(title='Student Course').exists())

        # Nem publicar ou apagar um curso de prática
        url = f'{PRATICA}{self.teacher_practice_course.id}/'
        self.assertEqual(self.client.put(url, {'action': 'unpublish'}, format='json').status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Course.objects.filter(id=self.teacher_practice_course.id).exists())

    def test_teacher_role_validation(self):
        """Test that only users with teacher role can access teacher endpoints."""
        # Create a user with student role but try to access teacher endpoints
        student_user = StudentFactory()
        token = self.get_jwt_token(student_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = '/api/v1/teacher/video-courses/'
        response = self.client.get(url)

        # Should not see any courses or be forbidden
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            self.assertEqual(len(data), 0)
        else:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
class TestTeacherAPICourseOwnership(BaseTeacherAPITest):
    """Test course ownership and isolation between teachers."""

    def test_teacher_course_isolation(self):
        """Test that teachers can only see their own courses."""
        self.authenticate_as_teacher()

        # Video courses
        response = self.client.get('/api/v1/teacher/video-courses/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course_ids = [course['courseId'] for course in self.video_list(response)]
        self.assertIn(str(self.teacher_video_course.id), course_ids)
        self.assertNotIn(str(self.other_video_course.id), course_ids)

        # Practice courses
        response = self.client.get(PRATICA)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course_ids = [course['courseId'] for course in response.json()]
        self.assertIn(str(self.teacher_practice_course.id), course_ids)
        self.assertNotIn(str(self.other_practice_course.id), course_ids)

    def test_cross_teacher_access_prevention(self):
        """Test that teachers cannot access other teachers' courses."""
        self.authenticate_as_teacher()

        # Try to access other teacher's video course
        url = f'/api/v1/teacher/video-courses/{self.other_video_course.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try to publish/unpublish or delete other teacher's practice course
        url = f'{PRATICA}{self.other_practice_course.id}/'
        response = self.client.put(url, {'action': 'unpublish'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.other_practice_course.refresh_from_db()
        self.assertEqual(self.other_practice_course.status, 'Published')

        # Try to modify other teacher's course
        titulo = self.other_video_course.title
        url = f'/api/v1/teacher/video-courses/{self.other_video_course.id}/'
        response = self.client.patch(url, {'title': 'Hacked Title'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_410_GONE])
        self.other_video_course.refresh_from_db()
        self.assertEqual(self.other_video_course.title, titulo)

    def test_teacher_can_manage_all_course_types(self):
        """Test that a teacher can manage both video and practice courses."""
        self.authenticate_as_teacher()

        # Teacher should have access to both video and practice courses
        response = self.client.get('/api/v1/teacher/video-courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(PRATICA)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should be able to create both types
        video_data = {'title': 'New Video Course', 'description': 'Video course'}
        response = self.client.post('/api/v1/teacher/video-courses/', video_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        practice_data = {'title': 'New Practice Course', 'description': 'Practice course',
                         'category': 'General', 'level': 'B1'}
        response = self.client.post(f'{PRATICA}create/', practice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        self.assertEqual(Course.objects.get(title='New Video Course').course_type, 'video')
        self.assertEqual(Course.objects.get(title='New Practice Course').course_type, 'practice')


@pytest.mark.django_db
class TestTeacherAPIValidation(BaseTeacherAPITest):
    """Test teacher API data validation and error handling."""

    def test_create_course_validation(self):
        """Test course creation validation."""
        self.authenticate_as_teacher()
        url = '/api/v1/teacher/video-courses/'

        # Sem título cria-se um rascunho "Novo Curso" (o professor muda-o no editor).
        response = self.client.post(url, {'description': 'Missing title'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['data']['title'], 'Novo Curso')

        # Invalid level
        invalid_data = {
            'title': 'Test Course',
            'level': 'InvalidLevel'
        }
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Course.objects.filter(title='Test Course').exists())

        # O pedido não decide o estado nem o destaque: um curso novo é sempre rascunho.
        response = self.client.post(url, {'title': 'Quer publicar', 'status': 'Published',
                                          'is_featured': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course = Course.objects.get(title='Quer publicar')
        self.assertEqual(course.status, 'Draft')
        self.assertFalse(course.is_featured)

        # Prática: título obrigatório (3 letras no mínimo)
        response = self.client.post(f'{PRATICA}create/', {'title': 'X'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_course_type_is_enforced(self):
        """Test that course_type is automatically set correctly."""
        self.authenticate_as_teacher()

        # Video course should have course_type='video', mesmo que o pedido diga outra coisa
        video_data = {'title': 'Video Course', 'description': 'Test', 'course_type': 'practice'}
        url = '/api/v1/teacher/video-courses/'
        response = self.client.post(url, video_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course = Course.objects.get(id=response.json()['data']['courseId'])
        self.assertEqual(course.course_type, 'video')

        # Practice course should have course_type='practice'
        practice_data = {'title': 'Practice Course', 'description': 'Practice course description',
                         'category': 'General', 'level': 'B1', 'course_type': 'video'}
        response = self.client.post(f'{PRATICA}create/', practice_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['course_type'], 'practice')
        self.assertEqual(Course.objects.get(id=data['courseId']).course_type, 'practice')
