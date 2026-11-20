# Sons das lições do laboratório

- **Toques** (`apps/web/public/sons/*.mp3`, `apps/mobile/assets/sons/`): marimba sintetizada com `sintetizar.py`, originais da ProEnglish. Para os refazer: `python sintetizar.py <pasta>` (precisa de numpy e ffmpeg).
- **Frases da Professora Luena** (`apps/web/public/sons/luena/*.mp3`): o texto está em `FRASES_LUENA` (`apps/web/components/pe/licao/sons.ts`). Cada frase é verificada com o whisper local (e, se houver dúvida, com o juiz do Gemini) antes de entrar.
- **Voz:** a voz oficial da Luena, clone ElevenLabs da aula de introdução do A1 (voz «Professora Luena (oficial)», `voice_id` `ifwDnT8c01WcGVCznB4B`, modelo `eleven_multilingual_v2`), desde 20/11/2026. Volume normalizado a −18 LUFS, mono, 96 kbps. A mesma voz serve do A1 ao C1; nunca se troca. Sempre que os ficheiros mudam, sobe-se `VERSAO` em `sons.ts` (agora `2`).
- **Quando tocam** (`somDoMomento`): toque em cada resposta; a Luena fala no início, nas sequências de 3 e 5 certos, no 1.º certo e depois de 4 em 4, no 1.º erro e depois de 3 em 3, sem vidas e no fim. Só depois da resposta do servidor; o aluno desliga os toques e a voz nas definições.
