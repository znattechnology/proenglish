# Sons das lições do laboratório

- **Toques** (`apps/web/public/sons/*.mp3`, `apps/mobile/assets/sons/`): marimba sintetizada com `sintetizar.py`, originais da ProEnglish. Para os refazer: `python sintetizar.py <pasta>` (precisa de numpy e ffmpeg).
- **Frases da Professora Luena** (`apps/web/public/sons/luena/*.mp3`): o texto está em `FRASES_LUENA` (`apps/web/components/pe/licao/sons.ts`). Cada frase é verificada com o juiz do Gemini e o whisper local antes de entrar.
- **Voz:** provisoriamente a Aoede (Gemini TTS). A voz oficial será o clone da Luena das vídeo-aulas (ElevenLabs); ao trocar, sobe-se `VERSAO` em `sons.ts`.
- **Quando tocam** (`somDoMomento`): toque em cada resposta; a Luena fala no início, nas sequências de 3 e 5 certos, no 1.º certo e depois de 4 em 4, no 1.º erro e depois de 3 em 3, sem vidas e no fim. Só depois da resposta do servidor; o aluno desliga os toques e a voz nas definições.
