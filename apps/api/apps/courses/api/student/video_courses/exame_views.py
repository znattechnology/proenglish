"""
Exame oral de um curso em vídeo (fase 6). Montado em /api/v1/student/video-courses/.

  GET    <courseId>/exame/                 estado: disponível?, temas, frases, tentativas
  POST   <courseId>/exame/                 {consentimento: bool} -> começa o exame (sessão do tutor)
  GET    exames/<exameId>/                 resultado de uma tentativa (só o próprio aluno)
  DELETE exames/<exameId>/gravacao/        apagar a gravação (só o próprio aluno)

As regras de acesso do curso são as das aulas (inscrição activa, plano, curso aberto). O exame
termina-se com POST /practice/conversa/sessoes/<id>/terminar/, como as outras conversas.
Regras do exame em apps/practice/conversa/exame.py.
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses import ciclo
from apps.courses.models import Course, ExameOral

from .views import EnrollmentRequiredMixin

logger = logging.getLogger(__name__)


def _verdadeiro(valor):
    return valor is True or (isinstance(valor, str) and valor.strip().lower() in ('true', '1', 'sim'))


class ExameDoCurso(EnrollmentRequiredMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == 'POST':
            from apps.practice.conversa.views import LimiteSessoes
            return [LimiteSessoes()]
        return super().get_throttles()

    def curso(self):
        course = get_object_or_404(Course.objects.filter(ciclo.q_conteudo_aluno(), course_type='video'),
                                   id=self.kwargs['courseId'])
        self.check_enrollment(course)
        return course

    def get(self, request, courseId):
        from apps.practice.conversa import exame
        return Response(exame.estado(request.user, self.curso()))

    def post(self, request, courseId):
        from apps.practice.conversa import exame
        from apps.practice.conversa.servico import ErroConversa
        course = self.curso()
        corpo = request.data if isinstance(request.data, dict) else {}
        try:
            dados = exame.comecar(request.user, course, _verdadeiro(corpo.get('consentimento')))
        except ErroConversa as e:
            return Response({'codigo': e.codigo, 'mensagem': e.mensagem}, status=e.status)
        return Response(dados, status=status.HTTP_201_CREATED)


class _ExameDoAluno(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def exame(self):
        return get_object_or_404(ExameOral.objects.select_related('course', 'sessao', 'revisto_por'),
                                 pk=self.kwargs['exameId'], user=self.request.user)


class ExameDetalhe(_ExameDoAluno):
    def get(self, request, exameId):
        from apps.practice.conversa import exame as svc
        from apps.practice.conversa import servico
        from apps.practice.models import VapiSession
        e = self.exame()
        if e.sessao is not None and e.estado in (ExameOral.EM_CURSO, ExameOral.A_AVALIAR):
            if e.sessao.status == VapiSession.STATUS_A_AVALIAR:
                servico.avaliar_pendente(e.sessao.pk)  # o pedido de terminar caiu a meio
            elif e.sessao.status != VapiSession.STATUS_EM_CURSO:
                svc.depois_de_avaliar(e.sessao)
            e = self.exame()
        svc.buscar_gravacao(e)
        return Response(svc.exame_dict(e))


class ApagarGravacao(_ExameDoAluno):
    def delete(self, request, exameId):
        from apps.practice.conversa import exame as svc
        e = svc.apagar_gravacao(self.exame())
        return Response(svc.exame_dict(e))
