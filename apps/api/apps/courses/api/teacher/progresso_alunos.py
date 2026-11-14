"""
Progresso dos alunos visto pelo professor.

- GET /api/v1/practice/student-progress/?course=<uuid>
    Alunos de um curso de prática (laboratório) com lições concluídas, pontos,
    vidas, acerto e última actividade.
- GET /api/v1/teacher/video-courses/courses/<uuid>/enrollments/
    Inscritos num curso em vídeo com progresso, capítulos e tempo de estudo.

Só o professor dono do curso (ou um administrador) vê estes dados.
"""
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.courses.models import Chapter, Course, CourseEnrollment, CourseSection, UserCourseProgress
from apps.courses.models.enrollment import ChapterProgress
from apps.practice.models import (
    ChallengeAttempt,
    ChallengeProgress,
    LessonCompletion,
    PracticeLesson,
    UserProgress,
)


def _pode_ver(user, course):
    from apps.core.permissions import e_administrador
    if e_administrador(user):
        return True
    return getattr(user, "role", None) == "teacher" and course.teacher_id == user.id


def _negado():
    return Response(
        {"error": "Acesso negado", "message": "Só o professor deste curso pode ver o progresso dos alunos."},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def alunos_curso_pratica(request):
    course_id = request.query_params.get("course")
    if not course_id:
        return Response(
            {"error": "validation_error", "message": "Indique o curso com ?course=<id>."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    course = get_object_or_404(Course, id=course_id, course_type="practice")
    if not _pode_ver(request.user, course):
        return _negado()

    total_licoes = PracticeLesson.objects.filter(unit__course=course).count()

    # Alunos: quem tem o curso como activo ou já respondeu a algum exercício dele.
    ids_resposta = set(
        ChallengeProgress.objects.filter(challenge__lesson__unit__course=course).values_list("user_id", flat=True)
    )
    ids_activo = set(UserProgress.objects.filter(active_course=course).values_list("user_id", flat=True))
    ids = ids_resposta | ids_activo

    concluidas = dict(
        LessonCompletion.objects.filter(user_id__in=ids, lesson__unit__course=course)
        .values("user_id")
        .annotate(n=Count("id"))
        .values_list("user_id", "n")
    )
    acerto = {
        r["user_id"]: r
        for r in ChallengeAttempt.objects.filter(user_id__in=ids, challenge__lesson__unit__course=course)
        .values("user_id")
        .annotate(total=Count("id"), certas=Count("id", filter=Q(is_correct=True)), ultima=Max("created_at"))
    }
    ultima_resposta = dict(
        ChallengeProgress.objects.filter(user_id__in=ids, challenge__lesson__unit__course=course)
        .values("user_id")
        .annotate(u=Max("completed_at"))
        .values_list("user_id", "u")
    )
    progressos = {
        p.user_id: p for p in UserProgress.objects.filter(user_id__in=ids).select_related("user", "active_course")
    }

    from apps.subscriptions.models import UserSubscription

    vidas = dict(UserSubscription.objects.filter(user_id__in=ids).values_list("user_id", "current_hearts"))

    from django.contrib.auth import get_user_model

    resultado = []
    for u in get_user_model().objects.filter(id__in=ids).order_by("name"):
        p = progressos.get(u.id)
        a = acerto.get(u.id)
        feitas = concluidas.get(u.id, 0)
        datas = [d for d in (ultima_resposta.get(u.id), a and a["ultima"]) if d]
        resultado.append(
            {
                "id": str(u.id),
                "student_id": str(u.id),
                "student_name": u.name,
                "name": u.name,
                "email": u.email,
                "course_id": str(course.id),
                "course_name": course.title,
                "active_course": p.active_course.title if p and p.active_course else None,
                "progress_percentage": round(100 * feitas / total_licoes) if total_licoes else 0,
                "last_activity": max(datas).isoformat() if datas else None,
                "total_points": p.points if p else 0,
                "hearts": vidas.get(u.id),
                "completed_lessons": feitas,
                "total_lessons": total_licoes,
                "average_accuracy": round(100 * a["certas"] / a["total"]) if a and a["total"] else None,
            }
        )
    return Response(resultado)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def inscritos_curso_video(request, course_id):
    course = get_object_or_404(Course, id=course_id, course_type="video")
    if not _pode_ver(request.user, course):
        return _negado()

    total_seccoes = CourseSection.objects.filter(course=course).count()
    capitulos_por_seccao = dict(
        Chapter.objects.filter(section__course=course).values("section_id").annotate(n=Count("id")).values_list("section_id", "n")
    )
    total_capitulos = sum(capitulos_por_seccao.values())

    inscricoes = CourseEnrollment.objects.filter(course=course).select_related("user").order_by("-enrollment_date")
    ids = [i.user_id for i in inscricoes]
    progressos = {p.user_id: p for p in UserCourseProgress.objects.filter(course=course, user_id__in=ids)}

    feitos = {}
    for r in (
        ChapterProgress.objects.filter(user_progress__course=course, user_progress__user_id__in=ids, completed=True)
        .values("user_progress__user_id", "chapter__section_id")
        .annotate(n=Count("id"))
    ):
        feitos.setdefault(r["user_progress__user_id"], {})[r["chapter__section_id"]] = r["n"]

    resultado = []
    for i in inscricoes:
        p = progressos.get(i.user_id)
        por_seccao = feitos.get(i.user_id, {})
        seccoes_feitas = sum(1 for s, n in por_seccao.items() if n and n >= capitulos_por_seccao.get(s, 0) > 0)
        resultado.append(
            {
                "userId": str(i.user_id),
                "userName": i.user.name,
                "userEmail": i.user.email,
                "courseId": str(course.id),
                "enrolledAt": i.enrollment_date.isoformat() if i.enrollment_date else None,
                "progress": round(p.overallProgress) if p else 0,
                "lastAccessedAt": p.lastAccessedTimestamp.isoformat() if p and p.lastAccessedTimestamp else None,
                "completedSections": seccoes_feitas,
                "totalSections": total_seccoes,
                "completedChapters": sum(por_seccao.values()),
                "totalChapters": total_capitulos,
                "totalWatchTime": p.total_time_spent if p else 0,
                "averageScore": None,
            }
        )
    return Response(resultado)
