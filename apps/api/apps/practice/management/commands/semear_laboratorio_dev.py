"""
Cria (ou recria) um curso de prática de desenvolvimento com os 9 tipos de exercício,
para testar o ecrã da lição. Só corre com DEBUG ligado.

    python manage.py semear_laboratorio_dev
"""
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Course
from apps.practice.models import ChallengeOption, PracticeChallenge, PracticeLesson, PracticeUnit

TITULO = "[DEV] Laboratório: Reuniões de segurança"

# (tipo, pergunta, instrução, dica, explicação, [(texto, certa)])
EXERCICIOS = [
    ("FILL_BLANK", "Could you ___ me the drilling report by Friday?", "Complete o pedido",
     'Depois de "could you" vem o verbo sem "to".', 'Depois de "could you" o verbo fica na forma base: send.',
     [("send", True), ("to send", False), ("sending", False), ("sent", False)]),
    ("SELECT", "Is the pressure test done?", "O supervisor pergunta. Escolha a melhor resposta",
     "A pergunta é se o teste está feito. Procure a resposta que fala do teste.", '"Not yet" responde à pergunta e diz logo quando fica pronto.',
     [("Yes, I am fine, thank you.", False), ("Not yet. We will finish it at two.", True), ("The meeting is on Friday.", False)]),
    ("ASSIST", "Qual destes é o hard hat?", None,
     "Hard hat protege a cabeça.", "Hard hat é o capacete de obra.",
     [("luvas", False), ("capacete", True), ("botas", False), ("óculos", False)]),
    ("TRANSLATION", "A equipa da noite deixou três tarefas por fazer.", "Escreva em inglês",
     'Turno da noite diz-se "night shift".', '"Unfinished" vai no fim: left three tasks unfinished.',
     [("The night shift left three tasks unfinished.", True)]),
    ("LISTENING", "The pressure test is scheduled for two.", "Escreva o que ouve",
     "Ouça outra vez com atenção ao número.", '"Scheduled for two" quer dizer marcado para as duas.',
     [("The pressure test is scheduled for two.", True)]),
    ("SPEAKING", "Please wear your safety glasses.", "Diga esta frase em voz alta",
     'Em "glasses", o fim soa a "iz".', "Muito bem. Repare no som final de glasses.", []),
    ("MATCH_PAIRS", "Ligue cada palavra à tradução", None,
     "Comece pelas que tem a certeza.", "Vocabulário de segurança completo.",
     [("hard hat - capacete", True), ("gloves - luvas", True), ("shift - turno", True), ("valve - válvula", True), ("leak - fuga", True)]),
    ("SENTENCE_ORDER", "Envie o relatório antes da reunião.", "Ponha as palavras por ordem",
     "Comece pelo verbo.", "Em inglês, o pedido começa pelo verbo: Send the report...",
     [("Send", True), ("the", True), ("report", True), ("before", True), ("the", True), ("meeting", True)]),
    ("TRUE_FALSE", '"Not yet" quer dizer que já está feito.', "Verdadeiro ou falso?",
     '"Yet" fala de algo que ainda vai acontecer.', '"Not yet" quer dizer "ainda não".',
     [("Verdadeiro", False), ("Falso", True)]),
]

LICOES_SIMPLES = [
    ("Perguntar se está feito", [("SELECT", "Has the inspection finished?", None, None, None,
                                  [("Yes, it finished an hour ago.", True), ("I like inspections.", False)])]),
    ("Dar instruções", [("TRUE_FALSE", '"Shut down the pump" quer dizer "desligue a bomba".', None, None, None,
                         [("Verdadeiro", True), ("Falso", False)])]),
]


class Command(BaseCommand):
    help = "Cria um curso de prática de desenvolvimento com os 9 tipos de exercício."

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Só para desenvolvimento (DEBUG=True).")
        User = get_user_model()
        professor = User.objects.filter(role="teacher").order_by("created_at").first()
        if not professor:
            raise CommandError("Crie primeiro um utilizador com papel de professor.")

        with transaction.atomic():
            Course.objects.filter(title=TITULO).delete()
            curso = Course.objects.create(
                teacher=professor, teacherName=professor.name, title=TITULO,
                description="Curso de desenvolvimento com os 9 tipos de exercício.",
                category="Industry English", level="Intermediate",
                course_type="practice", status="Published",
            )
            u1 = PracticeUnit.objects.create(course=curso, title="Reuniões de segurança", description="Pedir, confirmar e relatar.", order=1)
            u2 = PracticeUnit.objects.create(course=curso, title="Passagem de turno", description="Entregar e receber o turno.", order=2)

            licao = PracticeLesson.objects.create(unit=u1, title="Pedir um relatório", order=1)
            self._exercicios(licao, EXERCICIOS)
            for i, (titulo, exs) in enumerate(LICOES_SIMPLES, start=2):
                self._exercicios(PracticeLesson.objects.create(unit=u1, title=titulo, order=i), exs)
            self._exercicios(
                PracticeLesson.objects.create(unit=u2, title="Tarefas por fazer", order=1),
                [("SELECT", "Which task is still open?", None, None, None, [("The valve check.", True), ("Yesterday.", False)])],
            )
        self.stdout.write(self.style.SUCCESS(f"Criado: {TITULO} ({curso.id})"))

    @staticmethod
    def _audio(frase):
        """Gera áudio de referência com a voz do macOS (só desenvolvimento). Devolve o URL ou ''."""
        if not (shutil.which("say") and shutil.which("afconvert")):
            return ""
        pasta = Path(settings.MEDIA_ROOT) / "dev-audio"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = re.sub(r"[^a-z0-9]+", "-", frase.lower()).strip("-")[:60]
        aiff, m4a = pasta / f"{nome}.aiff", pasta / f"{nome}.m4a"
        if not m4a.exists():
            subprocess.run(["say", "-v", "Daniel", "-o", str(aiff), frase], check=False)
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(m4a)], check=False)
            aiff.unlink(missing_ok=True)
        return f"http://localhost:8000{settings.MEDIA_URL}dev-audio/{m4a.name}" if m4a.exists() else ""

    @classmethod
    def _exercicios(cls, licao, exercicios):
        for ordem, (tipo, pergunta, instrucao, dica, explicacao, opcoes) in enumerate(exercicios, start=1):
            frase_audio = {"LISTENING": opcoes[0][0] if opcoes else "", "SPEAKING": pergunta}.get(tipo, "")
            ch = PracticeChallenge.objects.create(
                lesson=licao, type=tipo,
                # Na escuta o enunciado não pode ser a frase a ouvir (seria a resposta à vista).
                question=pergunta if tipo != "LISTENING" else "Escreva o que ouve.",
                instruction=instrucao or "",
                hint=dica or "", explanation=explicacao or "", order=ordem,
                reference_audio_url=cls._audio(frase_audio) if frase_audio else None,
            )
            for o, (texto, certa) in enumerate(opcoes, start=1):
                ChallengeOption.objects.create(challenge=ch, text=texto, is_correct=certa, order=o)
