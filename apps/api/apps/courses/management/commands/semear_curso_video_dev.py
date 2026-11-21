"""
Cria (ou actualiza) cursos de vídeo de desenvolvimento para testar as páginas do aluno:
detalhe do curso, leitor de capítulos (vídeo, texto, recursos, quiz), progresso e notas.
Só corre com DEBUG ligado. Pode correr várias vezes: actualiza em vez de duplicar e
repõe o estado do aluno de teste (2 capítulos concluídos, sem tentativas de quiz).

    python manage.py semear_curso_video_dev
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.courses.matriculas import matricular_em_curso
from apps.courses.models import (
    Chapter, ChapterProgress, ChapterQuiz, ChapterResource, Course, CourseEnrollment,
    CourseSection, StudentQuizAttempt, UserCourseProgress,
)
from apps.practice.models import ChallengeOption, PracticeChallenge, PracticeLesson, PracticeUnit

TITULO_PREMIUM = "[DEV] Inglês para reuniões de segurança"
TITULO_GRATUITO = "[DEV] Primeiros passos: o briefing da manhã"

PROFESSOR_EMAIL = "professor@local.test"
ALUNO_EMAIL = "aluno@local.test"
GRATUITO_EMAIL = "gratuito@local.test"
GRATUITO_PASSWORD = "gratuito123"
PROFESSOR_PASSWORD = "professor123"  # só desenvolvimento, para entrar na área do professor
ADMIN_EMAIL = "admin@local.test"
ADMIN_PASSWORD = "admin123"  # só desenvolvimento, para entrar na área da administração

# Vídeos curtos e públicos (MDN CC0, 5 s; test-videos.co.uk, 10 s). O campo Chapter.video
# guarda um URL absoluto (em produção vem do S3).
VIDEO_A = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
VIDEO_B = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"


def _transcricao(*linhas):
    """Transcrição em JSON (texto), como descreve Chapter.transcript."""
    import json
    return json.dumps(
        [{"start": i * 2, "end": i * 2 + 2, "text": t} for i, t in enumerate(linhas)],
        ensure_ascii=False,
    )


# O conteúdo dos capítulos é Markdown (o editor do professor, RichTextEditor, usa markdownToHtml).
TEXTO_VOCABULARIO = """## Vocabulário essencial da reunião de segurança

Antes de cada turno, a equipa faz um **toolbox talk** (conversa curta de segurança). Estas são as palavras que vai ouvir todos os dias:

| Inglês | Português |
|---|---|
| hazard | perigo |
| near miss | quase-acidente |
| PPE (personal protective equipment) | EPI |
| permit to work | autorização de trabalho |
| muster point | ponto de encontro |
| hot work | trabalho a quente |

### Frases que vai usar

- *Is everyone wearing their PPE?* — Estão todos com o EPI?
- *We had a near miss on the drill floor yesterday.* — Tivemos um quase-acidente na plataforma de perfuração ontem.
- *Nobody starts hot work without a permit.* — Ninguém começa trabalho a quente sem autorização.

> **Dica:** "near miss" é sempre contável: *one near miss, two near misses*.
"""

TEXTO_REPORTAR = """## Como reportar um incidente em inglês

Quando relata um incidente, siga a ordem **o quê → onde → quando → acção tomada**.

1. **What happened?** *A valve was leaking.*
2. **Where?** *On the separator, level two.*
3. **When?** *At about 6:15 this morning.*
4. **What did you do?** *I isolated the line and informed the supervisor.*

### Passado simples para relatar

Use o *past simple* para factos concluídos: *I **saw** the leak, I **called** the control room.*

Evite o presente: diga *"The alarm **went** off"*, e não *"The alarm goes off"*.

> **Atenção:** nunca adivinhe. Se não sabe, diga *"I'm not sure, I'll check and report back."*
"""

TEXTO_GRATUITO = """## O briefing da manhã

Todas as manhãs o supervisor faz um briefing curto. Ouça três coisas: **o trabalho do dia**, **os perigos** e **quem faz o quê**.

- *Today we are replacing the pump seal.* — Hoje vamos substituir o vedante da bomba.
- *The main hazard is pressure.* — O principal perigo é a pressão.
- *João, you are the fire watch.* — João, és o vigilante de incêndio.
"""

QUIZ_PERGUNTAS = [
    {
        "id": "q1",
        "question": 'O que quer dizer "near miss"?',
        "options": [("a", "Um acidente grave", False), ("b", "Um quase-acidente", True),
                    ("c", "Uma falha de energia", False), ("d", "Uma reunião curta", False)],
        "explanation": '"Near miss" é um quase-acidente: algo que podia ter causado dano mas não causou.',
    },
    {
        "id": "q2",
        "question": "Complete: Nobody starts hot work without a ___.",
        "options": [("a", "permit", True), ("b", "hazard", False), ("c", "muster", False)],
        "explanation": 'Trabalho a quente exige sempre um "permit to work".',
    },
    {
        "id": "q3",
        "question": "Qual é a forma correcta para relatar um facto concluído?",
        "options": [("a", "The alarm goes off at six.", False), ("b", "The alarm went off at six.", True),
                    ("c", "The alarm going off at six.", False)],
        "explanation": "Para factos concluídos usa-se o past simple: went.",
    },
    {
        "id": "q4",
        "question": 'Para onde vai a equipa quando ouve o alarme geral? To the ___ point.',
        "options": [("a", "meeting", False), ("b", "muster", True), ("c", "starting", False)],
        "explanation": '"Muster point" é o ponto de encontro em caso de emergência.',
    },
]
QUIZ_TITULO = "Quiz: reuniões de segurança"
QUIZ_APROVACAO = 70
QUIZ_TENTATIVAS = 3


def _quiz_data():
    """Formato do QuizBuilder do professor (Chapter.quiz_data)."""
    return {
        "title": QUIZ_TITULO,
        "description": "Quatro perguntas sobre o vocabulário e as frases das reuniões de segurança.",
        "questions": [
            {
                "id": q["id"],
                "question": q["question"],
                "options": [{"id": oid, "text": txt, "isCorrect": ok} for oid, txt, ok in q["options"]],
                "correctOptionId": next(oid for oid, _, ok in q["options"] if ok),
                "explanation": q["explanation"],
                "points": 10,
            }
            for q in QUIZ_PERGUNTAS
        ],
        "settings": {
            "pointsPerQuestion": 10, "heartsPerError": 1, "timeLimit": None,
            "passingScore": QUIZ_APROVACAO, "maxAttempts": QUIZ_TENTATIVAS,
        },
    }


def _recursos_json(recursos):
    """Chapter.resources_data (JSON servido junto com o capítulo)."""
    return [
        {"id": f"r{i}", "title": t, "type": tipo.lower(), "url": url, "description": d,
         "downloadable": tipo == "PDF"}
        for i, (t, tipo, url, d) in enumerate(recursos, start=1)
    ]


# Recursos: (título, tipo ChapterResource, URL, descrição)
REC_VOCAB = [
    ("Glossário de segurança (PDF)", "PDF",
     "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
     "Lista de termos para imprimir e levar para o turno."),
    ("IOGP: Life-Saving Rules", "LINK", "https://www.iogp.org/life-savingrules/",
     "As regras que salvam vidas, em inglês."),
]
REC_REPORTAR = [
    ("Modelo de relatório de incidente", "WORKSHEET",
     "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
     "Preencha em inglês depois do capítulo."),
]

# Estrutura: secções -> capítulos (tipo, título, conteúdo, vídeo, transcrição, recursos, quiz?)
PREMIUM = [
    ("Antes do turno", "Vocabulário e rotina da conversa de segurança.", [
        ("Video", "Boas-vindas: porque o inglês salva vidas",
         "Neste vídeo apresentamos o curso e o que vai conseguir fazer no fim: conduzir e participar numa reunião de segurança em inglês.",
         VIDEO_A, _transcricao("Welcome to the course.", "Safety comes first, every shift."), [], False),
        ("Text", "Vocabulário essencial", TEXTO_VOCABULARIO, "", "", REC_VOCAB, False),
        ("Video", "O toolbox talk passo a passo",
         "Veja um toolbox talk completo e repare na ordem: trabalho do dia, perigos, EPI, autorizações.",
         VIDEO_B, _transcricao("Good morning, team.", "Today's job is the pump seal.", "Main hazard: pressure."), [], False),
    ]),
    ("Durante a reunião", "Fazer perguntas, confirmar e reportar.", [
        ("Text", "Reportar um incidente", TEXTO_REPORTAR, "", "", REC_REPORTAR, False),
        ("Video", "Confirmar que todos perceberam",
         "Frases para confirmar compreensão: *Does everyone understand? Any questions? Can you repeat that, please?*",
         VIDEO_A, _transcricao("Does everyone understand?", "Any questions before we start?"), [], False),
        ("Quiz", QUIZ_TITULO, "Responda às quatro perguntas. Precisa de 70% para passar.", "", "", [], True),
    ]),
    ("Emergências", "O que dizer quando algo corre mal.", [
        ("Video", "Alarme geral e ponto de encontro",
         "Ouça os anúncios de emergência mais comuns e o que cada um pede que faça.",
         VIDEO_B, _transcricao("This is not a drill.", "Proceed to your muster point."), [], False),
        ("Text", "Resumo do curso",
         "## Resumo\n\nJá sabe **abrir** uma reunião de segurança, **confirmar** que todos perceberam e **reportar** um incidente.\n\n- Use o *past simple* para relatar.\n- Peça sempre para repetir quando não percebe: *Sorry, can you say that again?*",
         "", "", [], False),
    ]),
]

GRATUITO = [
    ("Introdução", "Um primeiro contacto com o inglês do terreno.", [
        ("Video", "Bem-vindo ao briefing",
         "Um vídeo curto com o primeiro briefing do dia.",
         VIDEO_A, _transcricao("Good morning, everyone.", "Let's start the briefing."), [], False),
        ("Text", "O briefing da manhã", TEXTO_GRATUITO, "", "", [], False),
    ]),
]


class Command(BaseCommand):
    help = "Cria/actualiza os cursos de vídeo [DEV] e o estado do aluno de teste."

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Só para desenvolvimento (DEBUG=True).")
        User = get_user_model()
        professor = (User.objects.filter(email=PROFESSOR_EMAIL).first()
                     or User.objects.filter(role="teacher").order_by("created_at").first())
        if not professor:
            raise CommandError("Crie primeiro um utilizador com papel de professor.")
        admin = User.objects.filter(email=ADMIN_EMAIL, role="admin").first()
        if admin and not admin.check_password(ADMIN_PASSWORD):
            admin.set_password(ADMIN_PASSWORD)
            admin.save(update_fields=["password"])
        if professor.email == PROFESSOR_EMAIL and not professor.check_password(PROFESSOR_PASSWORD):
            professor.set_password(PROFESSOR_PASSWORD)
            professor.email_verified = True
            professor.save(update_fields=["password", "email_verified"])

        with transaction.atomic():
            premium = self._curso(professor, TITULO_PREMIUM, "premium",
                                  "Aprenda a conduzir e a participar em reuniões de segurança em inglês, "
                                  "com o vocabulário do petróleo e gás: perigos, EPI, autorizações e emergências.",
                                  PREMIUM)
            gratuito = self._curso(professor, TITULO_GRATUITO, "free",
                                   "Curso curto e gratuito: perceber o briefing da manhã em inglês.",
                                   GRATUITO)
            self._estado_aluno(User, premium, gratuito)
            self._utilizador_gratuito(User)

        for curso in (premium, gratuito):
            self.stdout.write(self.style.SUCCESS(f"{curso.title} ({curso.access_level}): {curso.id}"))
            for s in curso.sections.order_by("order"):
                self.stdout.write(f"  secção {s.order} {s.id} {s.sectionTitle}")
                for c in s.chapters.order_by("order"):
                    extra = f" quiz={c.quiz.id}" if hasattr(c, "quiz") else ""
                    self.stdout.write(f"    cap {c.order} {c.id} [{c.type}] {c.title}{extra}")

    # ------------------------------------------------------------------ cursos
    def _curso(self, professor, titulo, acesso, descricao, estrutura):
        curso, _ = Course.objects.update_or_create(
            title=titulo, course_type="video",
            defaults=dict(
                teacher=professor, teacherName=professor.name, description=descricao,
                category="Industry English", level="B1", status="Published",
                template="technology", access_level=acesso,
            ),
        )
        ordens_seccao = []
        for s_ordem, (s_titulo, s_desc, capitulos) in enumerate(estrutura, start=1):
            seccao, _ = CourseSection.objects.update_or_create(
                course=curso, order=s_ordem,
                defaults=dict(sectionTitle=s_titulo, sectionDescription=s_desc),
            )
            ordens_seccao.append(s_ordem)
            ordens_cap = []
            for c_ordem, (tipo, titulo_c, conteudo, video, transcr, recursos, quiz) in enumerate(capitulos, start=1):
                cap, _ = Chapter.objects.update_or_create(
                    section=seccao, order=c_ordem,
                    defaults=dict(
                        title=titulo_c, content=conteudo, type=tipo, video=video, transcript=transcr,
                        quiz_enabled=quiz, quiz_data=_quiz_data() if quiz else None,
                        resources_data=_recursos_json(recursos),
                    ),
                )
                ordens_cap.append(c_ordem)
                self._recursos(cap, recursos, professor)
                if quiz:
                    self._quiz(curso, cap, professor)
            seccao.chapters.exclude(order__in=ordens_cap).delete()
        curso.sections.exclude(order__in=ordens_seccao).delete()
        return curso

    @staticmethod
    def _recursos(cap, recursos, professor):
        titulos = []
        for ordem, (titulo, tipo, url, desc) in enumerate(recursos, start=1):
            ChapterResource.objects.update_or_create(
                chapter=cap, title=titulo,
                defaults=dict(resource_type=tipo, external_url=url, description=desc, order=ordem,
                              created_by=professor, is_featured=ordem == 1),
            )
            titulos.append(titulo)
        ChapterResource.objects.filter(chapter=cap).exclude(title__in=titulos).delete()

    @staticmethod
    def _quiz(curso, cap, professor):
        """ChapterQuiz (usado por /quiz/, tentativas, resumo e notas) ligado a uma lição de prática
        com as mesmas perguntas. A unidade fica no próprio curso de vídeo para ser apagada com ele."""
        unidade, _ = PracticeUnit.objects.update_or_create(
            course=curso, order=1,
            defaults=dict(title="Quizzes do curso", description="Lições usadas pelos quizzes dos capítulos."),
        )
        licao, _ = PracticeLesson.objects.update_or_create(unit=unidade, order=1, defaults=dict(title=QUIZ_TITULO))
        licao.challenges.all().delete()
        for ordem, q in enumerate(QUIZ_PERGUNTAS, start=1):
            ch = PracticeChallenge.objects.create(lesson=licao, type="SELECT", question=q["question"],
                                                  explanation=q["explanation"], order=ordem)
            for o, (_, txt, ok) in enumerate(q["options"], start=1):
                ChallengeOption.objects.create(challenge=ch, text=txt, is_correct=ok, order=o)
        ChapterQuiz.objects.update_or_create(
            chapter=cap,
            defaults=dict(
                practice_lesson=licao, title=QUIZ_TITULO,
                description="Quatro perguntas sobre as reuniões de segurança.",
                passing_score=QUIZ_APROVACAO, max_attempts=QUIZ_TENTATIVAS, points_reward=40,
                hearts_cost=1, is_active=True, created_by=professor,
                total_attempts=0, total_completions=0, average_score=0,
            ),
        )

    # ------------------------------------------------------------------ utilizadores
    def _estado_aluno(self, User, premium, gratuito):
        aluno = User.objects.filter(email=ALUNO_EMAIL).first()
        if not aluno:
            self.stdout.write(self.style.WARNING(f"{ALUNO_EMAIL} não existe: estado do aluno não criado."))
            return
        # Curso gratuito: deixa o aluno sem inscrição.
        CourseEnrollment.objects.filter(user=aluno, course=gratuito).delete()
        UserCourseProgress.objects.filter(user=aluno, course=gratuito).delete()

        # Curso premium: inscrito, 2 primeiros capítulos concluídos, terceiro em curso.
        matricular_em_curso(aluno, premium)
        progresso = UserCourseProgress.objects.get(user=aluno, course=premium)
        StudentQuizAttempt.objects.filter(student=aluno, chapter_quiz__chapter__section__course=premium).delete()
        capitulos = list(Chapter.objects.filter(section__course=premium).order_by("section__order", "order"))
        progresso.chapter_progress.exclude(chapter__in=capitulos).delete()
        agora = timezone.now()
        for i, cap in enumerate(capitulos):
            ChapterProgress.objects.update_or_create(
                user_progress=progresso, chapter=cap,
                defaults=dict(completed=i < 2, completed_at=agora if i < 2 else None,
                              time_spent=[3, 6, 2][i] if i < 3 else 0),
            )
        progresso.current_chapter = capitulos[2]
        progresso.total_time_spent = 11
        progresso.save(update_fields=["current_chapter", "total_time_spent", "lastAccessedTimestamp"])
        progresso.update_overall_progress()

    def _utilizador_gratuito(self, User):
        """Aluno no plano Gratuito para testar o bloqueio dos cursos premium."""
        from apps.subscriptions.models import SubscriptionPlan, UserSubscription
        user = User.objects.filter(email=GRATUITO_EMAIL).first()
        if not user:
            user = User.objects.create_user(email=GRATUITO_EMAIL, name="Aluno Gratuito",
                                            password=GRATUITO_PASSWORD, role="student")
        plano = SubscriptionPlan.objects.filter(plan_type="FREE").first()
        if plano:
            UserSubscription.objects.update_or_create(
                user=user,
                defaults=dict(plan=plano, status="ACTIVE", expires_at=timezone.now() + timedelta(days=365)),
            )
        self.stdout.write(f"Utilizador gratuito: {GRATUITO_EMAIL} / {GRATUITO_PASSWORD} ({user.id})")
