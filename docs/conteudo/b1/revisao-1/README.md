# B1.1 · Revisão 1 e exame oral

**Estado:** primeira versão escrita; falta a revisão aula a aula e a leitura dos professores · **Plano:** [04-plano-B1.md](../../04-plano-B1.md), "Revisão 1 e exame oral do B1.1"

## Objectivo

No fim do B1.1, o aluno consegue manter uma conversa de 8 a 10 minutos sobre si, o seu trabalho e as mudanças na sua vida, falar sozinho cerca de um minuto sobre um processo, e conduzir uma situação de trabalho com opinião, desacordo e solução.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R1A "Review: connections, changes and opinions" (no avião do Namibe para Luanda, o Nuno conversa com o Chanda; o B1.1 unidade a unidade numa só conversa; os 10 erros mais comuns do B1.1); R1B "Getting ready for the B1.1 speaking exam" (as quatro partes, o que se avalia, duas estratégias, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 1–3 e 4–5 com o exame), 26 exercícios, 4 respostas faladas | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: a visiting consultant": ensaio do exame com o tutor (Quinn, consultor de Londres), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao`; 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U1 a U5), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do B1.1: o que verifica, as quatro partes, o guião do examinador, a escala do B1.1 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma | Sim: validado com `exame.validar_guiao`; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com a pergunta de discussão da parte 4 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R1A mostra, numa conversa com um desconhecido, uma estrutura de cada unidade, porque o B1 é escolher a estrutura certa para o que se quer dizer.
- **Os 10 erros mais comuns do B1.1**, dois por unidade. Os que mais custam a quem fala português: *I'm agree*, "trabalho aqui desde 2020" no presente, e *would* depois de *if*.
- **Duas estratégias:** organizar um turno longo (*There are two reasons. Firstly… Secondly… So, in short…*), que é nova; e reformular (*What I mean is… In other words…*), vista na 5F, agora como estratégia de exame. Nenhuma baixa a nota.
- **Quatro partes, como no plano:** a parte 2 é um turno longo de explicação (o exame é só de voz, sem fotografias, como no B1 Preliminary), e a parte 4 é uma discussão em que o examinador discorda de propósito.
- **Quatro situações, uma por tarefa das unidades 1, 3, 4 e 5,** sempre com uma dificuldade a meio. A unidade 2 verifica-se na parte 1.
- **O exame de demonstração, o laboratório e o tutor usam dados diferentes dos do exame** (uma impressora avariada, uma festa sem local, não os portáteis da situação C), para o aluno não decorar respostas.
- **Personagens:** o Nuno (o fim da instalação no Namibe) e um passageiro novo, o Chanda, cuja empresa não tem nome (o porto do Lobito é real; a empresa não). A Lurdes volta como aluna-modelo dos exames.
- **Sem mudanças no código:** o guião, a escala e as situações carregam-se por curso. A discussão vai dentro de cada situação, porque a plataforma põe sempre a situação no fim (ver [exame.md](exame.md), secção 4).

## O que falta

1. **Carregar o exame no curso B1.1** (exame.md, secção 4).
2. Revisão aula a aula e leitura pelos professores.
3. Vídeos (vozes: o examinador, a Lurdes, o Nuno e uma voz nova para o Chanda), áudio do laboratório e carregamento na plataforma.
