# A2.1 · Revisão 1 e exame oral

**Estado:** primeira versão escrita e revista aula a aula ([revisão n.º 1](revisao-1.md)); falta a leitura dos professores · **Plano:** [03-plano-A2.md](../../03-plano-A2.md), "Revisão 1 e exame oral do A2.1"

## Objectivo

No fim do A2.1, o aluno consegue manter uma conversa de 6 a 7 minutos sobre o trabalho, as pessoas com quem trabalha e o seu percurso, contar uma situação do passado até ao fim e resolver uma situação de trabalho: mudar uma reunião, convidar e combinar, comparar e recomendar, ou aconselhar um colega doente.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R1A "Review: my work, my story, my plans" (a conversa de fim de ano do Nuno com o Sr. Baptista, os cinco tempos lado a lado, os 10 erros mais comuns do A2.1); R1B "Getting ready for the A2.1 speaking exam" (as três partes, o que se avalia, duas estratégias novas, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 1–3 e 4–5), 25 exercícios, 4 respostas faladas | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Getting to know a new manager": ensaio do exame com o tutor (Jesse, nova chefia regional), com 6 critérios | Sim: campos do modelo `Situacao` |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U1 a U5), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do A2.1: o que verifica, as três partes, o guião do examinador, a escala do A2.1 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma: partes, perguntas, notas para o examinador, escala e o que não baixa a nota | Sim: validado com `exame.validar_guiao`; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3 (mudar uma reunião, convidar e combinar, comparar e recomendar, aconselhar um colega doente) | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A revisão junta os cinco tempos do A2.1 (dois presentes, dois passados e os três futuros) numa só conversa e ensina a escolhê-los pelas palavras de tempo.
- **Os 10 erros mais comuns do A2.1**, dois por unidade; dois deles são erros de sentido e não de gramática (*What does she like?* por *What's she like?*; *mustn't* por *don't have to*), e a aula diz isso.
- **Duas estratégias novas:** ganhar tempo (*That's a good question. Well…*) e confirmar uma pergunta (*Do you mean…?*). Não baixam a nota.
- **O exame do A2.1 pede mais do que o do A1:** respostas de duas ou três frases, uma história completa (o que aconteceu, o que estava a fazer, como acabou) e uma objecção do examinador na situação, a que o aluno tem de responder.
- **Quatro situações, uma por tipo de tarefa das unidades 3 a 5.** As unidades 1 e 2 verificam-se nas partes 1 e 2.
- **O exame de demonstração e o laboratório usam dados diferentes dos do exame** (projectores e portáteis, não as impressoras da situação C), para o aluno não decorar respostas.
- **Personagens conhecidas:** o Nuno (com o Sr. Baptista, como o estagiário do A1 com o Mateus) e a Lurdes (a aluna-modelo dos exames do A1), para o aluno ver o progresso.
- **Sem mudanças no código:** o guião, a escala e as situações carregam-se por curso, como no A1.

## O que falta

1. **Carregar o exame no curso A2.1** (exame.md, secção 4). Um curso A2 sem o guião carregado cai no exame geral da plataforma, pensado para o B1.
2. Leitura pelos professores.
3. Vídeos (vozes: o examinador, a Lurdes, o Nuno e o Sr. Baptista já existem), áudio do laboratório e carregamento na plataforma.
