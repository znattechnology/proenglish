"""Testes do ecrã da lição: nada de respostas no que vai para o browser."""
import json

from apps.courses.api.tests.test_student_study_tracking import StudyTrackingTestBase
from apps.practice.models import ChallengeOption, PracticeChallenge


class JogarLicaoTests(StudyTrackingTestBase):
    def setUp(self):
        super().setUp()
        # A lição 1 já está feita: a lição 2 é a actual do trilho (as bloqueadas dão 403).
        from datetime import timedelta
        from django.utils import timezone
        from apps.practice.models import ChallengeProgress
        for ch in (self.ch1, self.ch2):
            ChallengeProgress.objects.create(user=self.student, challenge=ch, completed=True)
        ChallengeProgress.objects.filter(user=self.student).update(updated_at=timezone.now() - timedelta(minutes=1))
        self.ch1.hint = "Pense no cumprimento."
        self.ch1.explanation = "Hello é o cumprimento neutro."
        self.ch1.save()
        self.ordem = PracticeChallenge.objects.create(lesson=self.lesson2, type="SENTENCE_ORDER", question="Ordene", order=2)
        self.palavras = [
            ChallengeOption.objects.create(challenge=self.ordem, text=t, is_correct=True, order=i)
            for i, t in enumerate(["Send", "the", "report", "before", "the", "meeting"], start=1)
        ]
        self.pares = PracticeChallenge.objects.create(lesson=self.lesson2, type="MATCH_PAIRS", question="Ligue", order=3)
        for i, t in enumerate(["valve - válvula", "leak - fuga"], start=1):
            ChallengeOption.objects.create(challenge=self.pares, text=t, is_correct=True, order=i)
        self.escrever = PracticeChallenge.objects.create(lesson=self.lesson2, type="LISTENING", question="Shut down the pump", order=4,
                                                         reference_audio_url="https://exemplo.ao/pump.mp3")
        ChallengeOption.objects.create(challenge=self.escrever, text="Shut down the pump", is_correct=True, order=1)

    def jogar(self, licao):
        self.authenticate(self.student)
        r = self.client.get(f"/api/v1/student/practice-courses/lessons/{licao.id}/jogar/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_nao_revela_respostas(self):
        corpo = json.dumps(self.jogar(self.lesson2))
        self.assertNotIn("is_correct", corpo)
        # O ditado não mostra a frase a escrever.
        dados = self.jogar(self.lesson2)
        ditado = next(e for e in dados["exercicios"] if e["tipo"] == "LISTENING")
        self.assertEqual(ditado["modo"], "escrever")
        self.assertNotIn("Shut down the pump", json.dumps(ditado))
        # Pares: duas colunas separadas, sem o texto "a - b" original.
        pares = next(e for e in dados["exercicios"] if e["tipo"] == "MATCH_PAIRS")
        self.assertEqual(sorted(p["texto"] for p in pares["esquerda"]), ["leak", "valve"])
        self.assertEqual(sorted(pares["direita"]), ["fuga", "válvula"])
        self.assertNotIn("valve - válvula", json.dumps(pares))

    def test_ordem_estavel_por_pessoa(self):
        a = [p["id"] for p in next(e for e in self.jogar(self.lesson2)["exercicios"] if e["tipo"] == "SENTENCE_ORDER")["palavras"]]
        b = [p["id"] for p in next(e for e in self.jogar(self.lesson2)["exercicios"] if e["tipo"] == "SENTENCE_ORDER")["palavras"]]
        self.assertEqual(a, b)

    def test_ordenar_com_palavras_repetidas_compara_texto(self):
        self.authenticate(self.student)
        ids = [str(p.id) for p in self.palavras]
        # Troca os dois "the" de lugar: a frase fica igual e tem de contar como certa.
        trocado = [ids[0], ids[4], ids[2], ids[3], ids[1], ids[5]]
        r = self.client.post("/api/v1/student/practice-courses/challenge-progress/",
                             {"challenge_id": str(self.ordem.id), "ordered_options": trocado}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["correct"])

    def test_dica_ao_errar_e_explicacao_ao_acertar(self):
        self.authenticate(self.student)
        url = "/api/v1/student/practice-courses/challenge-progress/"
        errada = self.client.post(url, {"challenge_id": str(self.ch1.id), "selected_option": str(self.ch1.wrong.id)}, format="json").json()
        self.assertFalse(errada["correct"])
        self.assertEqual(errada["dica"], "Pense no cumprimento.")
        self.assertNotIn("explicacao", errada)
        certa = self.client.post(url, {"challenge_id": str(self.ch1.id), "selected_option": str(self.ch1.right.id)}, format="json").json()
        self.assertTrue(certa["correct"])
        self.assertEqual(certa["explicacao"], "Hello é o cumprimento neutro.")

    def test_sessao_obrigatoria(self):
        self.client.credentials()
        self.client.force_authenticate(user=None)
        r = self.client.get(f"/api/v1/student/practice-courses/lessons/{self.lesson2.id}/jogar/")
        self.assertEqual(r.status_code, 401)


class TrilhoTests(StudyTrackingTestBase):
    def test_estados_feita_actual_bloqueada(self):
        self.authenticate(self.student)
        self.answer(self.ch1)
        self.answer(self.ch2)
        r = self.client.get(f"/api/v1/student/practice-courses/courses/{self.course.id}/trilho/")
        self.assertEqual(r.status_code, 200)
        licoes = r.json()["unidades"][0]["licoes"]
        self.assertEqual([l["estado"] for l in licoes], ["feita", "actual"])
        self.assertEqual(r.json()["percentagem"], 50)
        self.assertNotIn("options", r.content.decode())


class PronunciaIndisponivelTests(StudyTrackingTestBase):
    """Se não foi possível ouvir a gravação, o aluno não perde vidas por isso."""

    def test_falha_tecnica_nao_tira_vidas(self):
        from unittest import mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from apps.practice.models import UserProgress
        from apps.practice.services.ai_pronunciation import AIPronunciationAnalyzer

        falar = PracticeChallenge.objects.create(lesson=self.lesson, type="SPEAKING", question="Please wear your safety glasses.", order=3)
        self.authenticate(self.student)
        antes = UserProgress.objects.get_or_create(user=self.student)[0].hearts

        async def falha(self_, audio_file, expected_text, difficulty_level="intermediate"):
            return self_._create_fallback_result(expected_text)

        audio = SimpleUploadedFile("gravacao.webm", b"\x00" * 4096, content_type="audio/webm")
        with override_settings(PRONUNCIA_SIMULADA=False), mock.patch.object(AIPronunciationAnalyzer, "__init__", lambda s: None), mock.patch.object(
            AIPronunciationAnalyzer, "analyze_pronunciation", falha
        ):
            r = self.client.post(
                "/api/v1/practice/analyze-ai-pronunciation/",
                {"audio": audio, "challenge_id": str(falar.id), "expected_text": falar.question},
                format="multipart",
            )
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"], "analysis_unavailable")
        self.assertEqual(UserProgress.objects.get(user=self.student).hearts, antes)
