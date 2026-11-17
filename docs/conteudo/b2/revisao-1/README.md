# B2.1 · Revisão 1 e exame oral

**Estado:** primeira versão escrita; falta a revisão aula a aula e a leitura dos professores · **Plano:** [05-plano-B2.md](../../05-plano-B2.md), "Revisão 1 e exame oral do B2.1"

## Objectivo

No fim do B2.1, o aluno consegue manter uma conversa de cerca de 12 minutos, comparar opções e escolher com razões, apresentar uma proposta, negociar, acalmar um cliente, especular sobre o futuro e chegar a uma decisão com outra pessoa.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R1A "Review: leading, presenting and negotiating" (a Elsa vai liderar a formação dos técnicos do Tômbwa e pede conselhos ao Nuno; o B2.1 unidade a unidade numa só conversa; os 10 erros mais comuns do B2.1); R1B "Getting ready for the B2.1 speaking exam" (as quatro partes, o que se avalia, duas estratégias novas, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 1–3 e 4–5 com o exame), 27 exercícios, 4 respostas faladas (duas de até 90 segundos) | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: the team retreat": ensaio do exame com o tutor (Casey, novo director de recursos humanos), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao`; 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U1 a U5), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do B2.1: o que verifica, as quatro partes, o guião do examinador, a escala do B2.1 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma (12 minutos) | Sim: validado com `exame.validar_guiao`, sem cortes; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com a pergunta de discussão e os dois contra-argumentos da parte 4 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R1A mostra, numa conversa entre o Nuno e a Elsa, uma estrutura de cada unidade do B2.1: a Elsa tem de apresentar a um cliente, negociar uma sala, resolver um erro e decidir sobre uma tecnologia — os temas das unidades 2 a 5 — e o Nuno dá-lhe os conselhos que aprendeu.
- **Os 10 erros mais comuns do B2.1**, dois por unidade. Os que mais custam a quem fala português: *what* em vez de *which* ("o que"), *until* em vez de *by* ("até") e "vou cortar o cabelo".
- **Duas estratégias novas, em blocos fixos:** comparar duas opções (*The first option… The second, on the other hand,… The main difference is… If I had to choose, I'd go for…*) e fechar uma decisão (*Shall we go for…? I could live with that. So, we've agreed on…*). O plano sugeria *Whereas the first…*; foi trocado, porque *whereas* só se ensina na unidade 7.
- **O exame segue o B2 First adaptado a uma conversa só de voz:** o turno longo compara duas opções descritas pelo examinador (em vez de fotografias), a tarefa colaborativa passa a ser uma decisão com o examinador, e a discussão tem dois contra-argumentos. Ocupa os 12 minutos que a plataforma agora permite.
- **Quatro situações, uma por tarefa das unidades 2, 3, 4 e 5,** sempre com uma dificuldade e uma decisão. A unidade 1 verifica-se na parte 1.
- **O exame de demonstração, o laboratório e o tutor usam dados e perguntas diferentes dos do exame:** a fila do banco, o carro ou o autocarro, o tipo de escritório (turnos longos); a sala de conferências de um hotel e o retiro da equipa (tarefas); salários públicos, teletrabalho e chefes escolhidos pela equipa (discussões). O exame usa a formação de novos funcionários, a cantina, os portáteis, os microfones e o reconhecimento facial.
- **A Lurdes volta como aluna-modelo** (contabilista num banco de Benguela desde 2014; aluna-modelo dos exames desde o A1), agora no seu primeiro exame do B2.
- **Sem mudanças no código:** o limite de 12 minutos já foi alterado (Novembro de 2026); o guião, a escala e as situações carregam-se por curso.

## O que falta

1. Revisão aula a aula.
2. **Carregar o exame no curso B2.1** (exame.md, secção 4): sem o guião, o curso usa o exame geral, que é do B1.
3. Leitura pelos professores.
4. Vídeos (vozes: o examinador, a Lurdes, o Nuno e a Elsa já existem), áudio do laboratório e carregamento na plataforma.
