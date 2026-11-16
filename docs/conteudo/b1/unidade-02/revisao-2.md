# B1.1 · Unidade 2 — Revisão pedagógica n.º 2 (aula a aula)

**Data:** 16 de Novembro de 2026 · **Âmbito:** releitura completa depois da [revisão n.º 1](revisao-1.md): os seis guiões linha a linha (falas, ecrãs e fichas), cada exercício do laboratório, o questionário e as falas do tutor contra qualquer resposta do aluno · **Critérios:** os 7 do [plano do A2, secção 10](../../03-plano-A2.md#revisão-de-cada-aula), com as regras do B1 · **Resultado:** 6 problemas, corrigidos em 10 sítios; nenhum erro de inglês nos modelos que o aluno repete.

## O que se encontrou e o que se fez

| # | Onde | Critério | Problema | Correcção |
|---|---|---|---|---|
| 1 | 2C, prática | 2 | **Ficou uma oração relativa sem pronome** que a revisão n.º 1 não apanhou: "Tell me one thing you've been doing for a long time, and two things you've finished or done." | "Talk about your year: one long activity, with 'I've been…', and two results, with numbers." |
| 2 | 2C (ficha, ecrã do quadro, pronúncia) | 6 | A revisão n.º 1 mudou o diálogo para "since lunch", mas a ficha ("all morning"), o quadro e a fala de pronúncia ("all afternoon") ficaram com a frase antiga. | "since lunch" nos três sítios. |
| 3 | 2C, explicação | 6 | "twice, three reports, four projects": o diálogo corrigido fala agora de dois projectos. | "two projects". |
| 4 | 2E, terceira escuta | 4 | "Each person has… before, with 'used to'": depois da revisão n.º 1, a Esperança fala do passado com o *past simple* e não usa *used to*. | "before, with 'used to' or the past simple". |
| 5 | 2F | 1, 6 | "your evaluation from last year": a avaliação vai de Outubro de 2026 a Junho de 2027, e "last year" (2026) não bate certo. | "his evaluation of your work until June". |
| 6 | 2B (ecrã, fala e ficha) | 6, 4 | O exemplo dos verbos de estado dizia "since February", mas o diálogo corrigido diz "since January". A ficha listava *lately* e *all morning*, que a aula não usa. | "since January" no ecrã e na fala; palavras-alvo trocadas pelas que a aula usa (*a bit*, *It shows*). |

**Verificado sem alterações:**
- **Escutas:** as 12 do laboratório, cada uma lida só com a frase ouvida. Têm a resposta e o nome de quem fala.
- **Respostas faladas:** as 14 cabem em 45 segundos e contêm a frase-alvo.
- **Opções erradas:** nenhuma pode estar certa noutro contexto, com uma excepção já explicada na revisão n.º 1: *used to live… for twenty years*.
- **Tutor:** o Chris e o Robin funcionam com respostas curtas e com "não". O Robin não fala de marido nem de mulher.
- **Questionário:** as 12 perguntas e as explicações estão certas. **Problema encontrado e por resolver:** a resposta certa está sempre em primeiro lugar e tem sempre o identificador terminado em `o0`. A plataforma não baralha as opções (`quiz_sem_respostas`, em `apps/courses/api/student/video_courses/conteudo.py`), por isso o aluno pode adivinhar a resposta pela posição ou pelo identificador. O mesmo acontece nos questionários do A1 e do A2. Fica para decisão da direcção (ver a nota no fim).
- **Língua:** nenhuma estrutura das unidades seguintes, em nova procura automática e leitura.

## Nota para decisão

Os questionários de todos os níveis (A1, A2 e B1) põem a resposta certa em primeiro lugar e com o identificador `…o0`. Há duas soluções:

- **Na plataforma (recomendada):** a API passa a baralhar as opções de cada pergunta e a enviar identificadores que não revelam a resposta. Assim ficam corrigidos todos os questionários, os já escritos e os que os professores criarem.
- **Nos ficheiros:** baralhar as opções e trocar os identificadores em todos os `questionario.json`. Isto não protege os questionários que os professores criarem.
