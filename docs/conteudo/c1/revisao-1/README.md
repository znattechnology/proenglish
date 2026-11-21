# C1.1 · Revisão 1 e exame oral

**Estado:** primeira versão escrita, com uma revisão aula a aula ([n.º 1](revisao-1.md)); falta a leitura dos professores · **Plano:** [06-plano-C1.md](../../06-plano-C1.md), "Revisão 1 e exame oral do C1.1"

## Objectivo

No fim do C1.1, o aluno consegue manter uma conversa de cerca de 12 minutos com fluência quase sem esforço, defender uma posição com ênfase e responder a contra-argumentos, atenuar e exprimir graus de certeza, formular hipóteses, mediar um conflito e sintetizar dados.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R1A "Review: persuasion, diplomacy and data" (a Inês vai apresentar a proposta da segunda fase à administração da Mussiro e pede conselhos ao Nuno; o C1.1 unidade a unidade numa só conversa; os 10 erros mais comuns do C1.1); R1B "Getting ready for the C1.1 speaking exam" (as quatro partes, o que se avalia, duas estratégias novas, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 1–3 e 4–5 com o exame), 28 exercícios, 4 respostas faladas (duas de até 90 segundos) | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: the budget": ensaio do exame com o tutor (Hayden, novo director de operações), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao` (nível C1); 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U1 a U5), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do C1.1: o que verifica, as quatro partes, o guião do examinador, a escala do C1.1 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma (12 minutos) | Sim: validado com `exame.validar_guiao`, sem cortes; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com a pergunta de discussão e os dois contra-argumentos da parte 4 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R1A mostra, numa conversa entre o Nuno e a Inês, uma estrutura de cada unidade do C1.1: a Inês tem de abrir com força, falar de um rumor, mostrar cenários, falar do conflito resolvido e dar números honestos — os temas das unidades 1 a 5. A ideia comum: honestidade com estrutura.
- **Os 10 erros mais comuns do C1.1**, dois por unidade, todos de forma ou de posição: *is* depois de uma clivada, o singular depois de *there seems*, o passado depois de *I'd be surprised if*, *Had we not* (não *Hadn't we*), o auxiliar antes do sujeito na inversão negativa e na oração principal com *only when*, e o sujeito certo depois de uma oração participial.
- **Duas estratégias novas, em blocos fixos:** escolher duas de três opções e especular (*Of the three, the two I'd like to talk about are… I'd leave aside… It could well be that…*) e matizar na discussão (*That's true up to a point, but… I'd go along with that, with one reservation… Where I come down is…*).
- **O exame segue o C1 Advanced adaptado a uma conversa só de voz:** três opções descritas pelo examinador (em vez de três fotografias), uma tarefa de decisão com o examinador (que, na mediação, faz de duas pessoas), e uma discussão com dois contra-argumentos. Ocupa os 12 minutos da plataforma.
- **Quatro situações, uma por tarefa das unidades 1, 3, 4 e 5,** sempre com uma dificuldade, um pedido a recusar ou atenuar (a unidade 2 verifica-se em todas) e uma decisão.
- **O exame de demonstração, o laboratório e o tutor usam dados e perguntas diferentes dos do exame:** o que as pessoas de fora não vêem no trabalho, uma escola (laboratório, inglês ou dias mais longos), uma cidade (luzes, centro desportivo ou autocarros nocturnos), uma vila (mercado, biblioteca ou centro de saúde) e o orçamento de formação (turnos longos); o director da escola, o corte de 10% (tarefas); as escolhas dos alunos, os exames e os prémios iguais (discussões). O exame usa a diferença no campo do aluno, um conselho recebido, os benefícios de uma empresa, a semana de quatro dias, as farmácias, a sala do sábado e o hotel de Benguela.
- **A Lurdes volta como aluna-modelo** (contabilista num banco de Benguela desde 2014), agora no seu primeiro exame do C1; corrige-se a si própria uma vez, para mostrar que não baixa a nota.
- **Sem mudanças no código:** o nível C1 já existe na plataforma, o limite de 12 minutos já foi alterado, e o guião, a escala e as situações carregam-se por curso.

## O que falta para publicar

Leitura pelos professores; vídeos com o professor de IA; áudio (4 escutas, 2 pronúncias; o exame de demonstração com duas vozes); criar o curso C1.1 na plataforma e carregar o exame com `carregar_exame_curso`.

A seguir vem o **C1.2, a começar pela unidade 6, "Compliance and ethics"**.
