"""
Certificados do aluno (montado em /api/v1/student/video-courses/):

- GET  certificados/                     os meus certificados + cursos inscritos ainda sem
                                         certificado (nota, requisitos em falta)
- POST <courseId>/certificado/           emitir (idempotente)
- GET  certificados/<certificadoId>/pdf/ descarregar o PDF (só o dono)

A verificação pública está em apps/courses/api/public (sem autenticação).
Regras em apps.courses.certificados.
"""
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses import certificados as svc
from apps.courses.models import (
    Course, CourseCertificate, CourseEnrollment,
)
from apps.courses.services.grade_calculator import GradeCalculatorService


def _curso(course):
    return {'id': str(course.id), 'titulo': course.title, 'imagem': course.image or None}


def _certificado(cert, request):
    return {
        'id': str(cert.id),
        'numero': cert.certificate_number,
        'curso': _curso(cert.course),
        'emitido_em': timezone.localtime(cert.issued_at, svc.FUSO_ANGOLA).isoformat(),
        'nota_final': round(cert.final_grade, 1) if cert.final_grade is not None else None,
        'nota_letra': cert.final_grade_letter or None,
        'estado': 'revogado' if cert.is_revoked else 'valido',
        'ligacao_verificacao': svc.ligacao_verificacao(cert),
        'pdf_url': request.build_absolute_uri(f'/api/v1/student/video-courses/certificados/{cert.id}/pdf/'),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_certificados(request):
    user = request.user
    plano_ok = svc.plano_inclui_certificados(user)
    certificados_ids = set(CourseCertificate.objects.filter(user=user).values_list('course_id', flat=True))

    em_curso = []
    from apps.courses.ciclo import q_conteudo_aluno
    inscricoes = (CourseEnrollment.objects.filter(q_conteudo_aluno('course__'), user=user,
                                                  course__course_type='video')
                  .exclude(course_id__in=certificados_ids)
                  .select_related('course').order_by('-enrollment_date'))
    for insc in inscricoes:
        course = insc.course
        # Só leitura: a nota é calculada em memória (um GET não escreve notas nem histórico).
        # A emissão automática acontece nos signals (quiz, progresso) ou no POST .../certificado/.
        grade = GradeCalculatorService(user, course).calcular_sem_guardar()
        prog = svc.progresso_actual(user, course)
        estado = svc.estado_certificado(user, course, grade, progresso=prog, plano_ok=plano_ok)
        em_curso.append({
            'curso': _curso(course),
            'progresso': round(prog, 1),
            'nota_final': round(grade.final_grade_percentage, 1),
            'nota_letra': grade.final_grade_letter,
            'nota_minima': estado['nota_minima'],
            'pode_emitir': estado['pode_emitir'],
            'em_falta': estado['em_falta'],
        })

    certs = CourseCertificate.objects.filter(user=user).select_related('course').order_by('-issued_at')
    return Response({
        'plano_inclui_certificados': plano_ok,
        'certificados': [_certificado(c, request) for c in certs],
        'em_curso': em_curso,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emitir_certificado(request, courseId):
    course = Course.objects.filter(id=courseId).first()
    if course is None:
        return Response({'codigo': 'CURSO_NAO_ENCONTRADO', 'mensagem': 'Curso não encontrado.'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        cert, criado = svc.emitir_certificado(request.user, course)
    except svc.CertificadoIndisponivel as e:
        return Response({'codigo': e.codigo, 'mensagem': e.mensagem, **e.detalhes}, status=e.status)
    return Response(
        {'criado': criado, 'certificado': _certificado(cert, request)},
        status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def descarregar_pdf(request, certificadoId):
    cert = (CourseCertificate.objects.select_related('course', 'user')
            .filter(id=certificadoId, user=request.user).first())
    if cert is None:
        return Response({'codigo': 'NAO_ENCONTRADO', 'mensagem': 'Certificado não encontrado.'},
                        status=status.HTTP_404_NOT_FOUND)
    if cert.is_revoked:
        return Response({'codigo': 'REVOGADO', 'mensagem': 'Este certificado foi revogado.'},
                        status=status.HTTP_409_CONFLICT)
    pdf, nome = svc.gerar_pdf(cert)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{nome}"'
    resp['Cache-Control'] = 'private, no-store'
    return resp
