# B1.2 · Revisão 2 e exame oral

**Estado:** primeira versão escrita, com uma revisão aula a aula ([n.º 1](revisao-1.md)); falta a leitura dos professores · **Plano:** [04-plano-B1.md](../../04-plano-B1.md), "Revisão 2 e exame oral do B1.2"

## Objectivo

No fim do B1.2, o aluno consegue manter uma conversa de 9 a 10 minutos, contar um acontecimento e as suas causas, relatar o que outros disseram, resumir e comentar um tema, e discutir uma situação com hipóteses sobre o passado e o futuro.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R2A "Review: stories, reports and opinions" (a Mei e o Nuno, um ano depois de Joanesburgo; o B1.2 unidade a unidade numa só conversa; os 10 erros mais comuns do B1.2); R2B "Getting ready for the B1.2 speaking exam" (as quatro partes, o que se avalia, uma estratégia nova, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 6–8 e 9–10 com o exame), 26 exercícios, 4 respostas faladas | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: a visiting auditor": ensaio do exame com o tutor (Skyler, auditor de Nairobi), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao`; 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U6 a U10), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do B1.2: o que verifica, as quatro partes, o guião do examinador, a escala do B1.2 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma | Sim: validado com `exame.validar_guiao`; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com a pergunta de discussão da parte 4 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R2A mostra, numa videochamada entre o Nuno e a Mei, uma estrutura de cada unidade do B1.2.
- **Os 10 erros mais comuns do B1.2**, dois por unidade. Os que mais custam a quem fala português: *She said me*, *for to* e *would* depois de *if*.
- **Uma estratégia nova:** ganhar tempo e organizar a opinião (*That's an interesting question. It depends. On the one hand… On the other hand… So, overall…*). *On the one hand* apareceu na 9E; aqui torna-se uma estratégia de exame.
- **O turno longo passa a ser uma história** (um problema que o aluno viveu), com as perguntas do examinador a pedir o 3.º condicional e o *should have*.
- **Quatro situações, uma por tarefa das unidades 7, 8, 9 e 10,** sempre com uma dificuldade a meio. A unidade 6 verifica-se na parte 2.
- **O exame de demonstração, o laboratório e o tutor usam dados diferentes dos do exame** (um corte de internet num banco, cadeiras de escritório, uma festa de fim de ano, não o hotel, a formação nem as notícias das situações), para o aluno não decorar respostas.
- **O fim da história do B1:** a Mei (unidades 1 e 6) liga ao Nuno quase um ano depois de Joanesburgo; ela é agora chefe de equipa, ele quer liderar o projecto do Tômbwa e fazer o exame B2. A Lurdes volta como aluna-modelo.
- **Sem mudanças no código:** o guião, a escala e as situações carregam-se por curso; a discussão vai dentro de cada situação, como no B1.1.

## O que falta

1. **Carregar o exame no curso B1.2** (exame.md, secção 4) — e o do B1.1 ([revisao-1/exame.md](../revisao-1/exame.md)).
2. Leitura pelos professores.
3. Vídeos (vozes: o examinador, a Lurdes, o Nuno e a Mei já existem), áudio do laboratório e carregamento na plataforma.
