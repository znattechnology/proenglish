# B2.2 · Revisão 2 e exame oral

**Estado:** primeira versão escrita; falta a revisão aula a aula e a leitura dos professores · **Plano:** [05-plano-B2.md](../../05-plano-B2.md), "Revisão 2 e exame oral do B2.2"

## Objectivo

No fim do B2.2 — e do nível B2 —, o aluno consegue manter uma discussão de cerca de 12 minutos sobre temas concretos e abstractos, desenvolver um argumento com prós e contras, especular sobre o passado, mediar informação, falar de escolhas e arrependimentos, e conceder num debate sem abandonar a sua posição.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R2A "Review: risks, arguments and choices" (o Paulo e a Elsa levam o Nuno a jantar; o B2.2 unidade a unidade numa só conversa; os 10 erros mais comuns do B2.2); R2B "Getting ready for the B2.2 speaking exam" (as quatro partes, o que se avalia, uma estratégia nova para o debate, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 6–8 e 9–10 com o exame), 26 exercícios, 4 respostas faladas (duas de até 90 segundos) | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: the safety audit": ensaio do exame com o tutor (Quinn, auditor externo), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao`; 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U6 a U10), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do B2.2: o que verifica, as quatro partes, o guião do examinador, a escala do B2.2 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma (12 minutos) | Sim: validado com `exame.validar_guiao`, sem cortes; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com a pergunta de discussão e os dois contra-argumentos da parte 4 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R2A mostra, num jantar de despedida antecipada, uma estrutura de cada unidade do B2.2, e cada frase lembra um momento do semestre: o contentor caído (6), o miniautocarro do condomínio (7), a zona solar do festival (8), o atraso da Kuvango (9) e a decisão do Nuno (10).
- **Os 10 erros mais comuns do B2.2**, dois por unidade. Os que mais custam a quem fala português: *suggested us to* ("sugeriu-nos que"), *very fantastic* ("muito fantástico") e *I wish I know* ("quem me dera saber").
- **Uma estratégia nova, em blocos fixos: conceder num debate** (*That may be true, but… To some extent, yes. I see where you're coming from. Even so…*). Junta o *admittedly / even so* da unidade 7 ao debate da parte 4, onde o examinador discorda duas vezes.
- **O exame segue o do B2.1** (12 minutos, quatro partes, decisão e dois contra-argumentos), com as tarefas das unidades 6 a 9 e perguntas de discussão mais abstractas. A unidade 10 verifica-se na entrevista.
- **Dados e perguntas diferentes entre o exame e o resto:** o exame usa o plástico, a baliza, o horário de trabalho, o torneio solidário e o armazém; a demonstração usa o orçamento de formação de um banco e a abertura de uma agência; o ensaio usa as férias e o micro-ondas da cozinha; o laboratório, uma aptidão nova. As perguntas de discussão também são todas diferentes (reforma, redes sociais para menores e trabalho nocturno na preparação; segurança, viver fora das cidades, patrocínios e tradução automática no exame), e não repetem as perguntas de opinião das unidades 6 a 10.
- **A Lurdes volta como aluna-modelo** (contabilista num banco de Benguela desde 2014), no seu último exame do B2.
- **Sem mudanças no código:** o guião, a escala e as situações carregam-se por curso, com o limite de 12 minutos.

## O que falta

1. Revisão aula a aula.
2. **Carregar o exame no curso B2.2** (exame.md, secção 4) — e o do B2.1 ([revisao-1/exame.md](../revisao-1/exame.md)): sem os guiões, os cursos usam o exame geral, que é do B1.
3. Leitura pelos professores.
4. Vídeos (vozes: o examinador, a Lurdes, o Nuno, o Paulo e a Elsa já existem), áudio do laboratório e carregamento na plataforma.
