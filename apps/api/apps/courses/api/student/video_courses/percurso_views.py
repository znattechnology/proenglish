"""
Percurso de um curso em vídeo e passo seguinte do aluno. Montado em /api/v1/student/video-courses/.

  GET <courseId>/percurso/     as unidades, as aulas e os passos de cada aula (aula, questionário,
                               laboratório, conversa), com o estado de cada um e o passo seguinte
  GET percurso/proximo/        o passo seguinte do aluno em toda a plataforma (ou null);
                               ?licao=<id> ou ?situacao=<slug> diz o que o aluno acabou de fazer

As regras de acesso são as das aulas (inscrição activa, plano, curso aberto). O que conta como
feito e a ordem dos passos são decididos em apps/courses/percurso.py.
"""
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses import ciclo, percurso
from apps.courses.models import Course

from .views import EnrollmentRequiredMixin


class PercursoDoCurso(EnrollmentRequiredMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, courseId):
        course = get_object_or_404(Course.objects.filter(ciclo.q_conteudo_aluno(), course_type='video'),
                                   id=courseId)
        # parcial: num curso com unidades de amostra basta a amostra (os passos fechados vêm marcados).
        self.check_enrollment(course, parcial=True)
        return Response(percurso.percurso(request.user, course))


class ProximoPasso(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # ?licao=<id> ou ?situacao=<slug>: o que o aluno acabou de fazer (o "a seguir" fica nesse curso).
        return Response({'proximo': percurso.proximo_passo(
            request.user, licao_id=request.query_params.get('licao'),
            situacao=request.query_params.get('situacao'))})
