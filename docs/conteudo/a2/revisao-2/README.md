# A2.2 · Revisão 2 e exame oral

**Estado:** primeira versão escrita, revista ([revisão n.º 1](revisao-1.md)); falta a leitura dos professores · **Plano:** [03-plano-A2.md](../../03-plano-A2.md), "Revisão 2 e exame oral do A2.2"

## Objectivo

No fim do A2.2, o aluno consegue manter uma conversa de 7 a 8 minutos sobre experiências, novidades e o seu trabalho, explicar como funciona uma coisa e o ponto de situação de um trabalho, e resolver um problema com outra pessoa: no hotel, no aeroporto, com o apoio técnico, a reclamar ou a atender um cliente.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R2A "Review: experiences, news and problems" (a Thandi liga ao Nuno quando sabe que ele ficou com o lugar; os tempos do A2.2 lado a lado; os 10 erros mais comuns do A2.2); R2B "Getting ready for the A2.2 speaking exam" (as três partes, o que se avalia, uma estratégia nova, um exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 6–8 e 9–10), 25 exercícios, 4 respostas faladas | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "A visitor from abroad": ensaio do exame com o tutor (Rowan, cliente de Nairobi de visita), com 6 critérios | Sim: campos do modelo `Situacao` |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U6 a U10), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do A2.2: o que verifica, as três partes, o guião do examinador, a escala do A2.2 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma | Sim: validado com `exame.validar_guiao`; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As cinco situações da parte 3 | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A revisão põe lado a lado o *present perfect* (novidade, já / ainda não, há quanto tempo, experiência) e o *past simple* (quando e como), e os futuros com o 1.º condicional.
- **Os 10 erros mais comuns do A2.2**, dois por unidade; os três primeiros (*present perfect* com uma data no passado, *ever went*, *I work here since*) são os que mais custam a quem fala português.
- **Uma estratégia nova:** corrigir-se (*Sorry, I mean…*). Não baixa a nota; é o uso legítimo da autocorrecção, com um erro do próprio nível.
- **A parte 2 do exame é explicar,** não descrever imagens: o exame é só de voz.
- **Cinco situações, uma por tarefa das unidades 6, 8 e 9,** sempre com uma dificuldade do examinador a meio. As unidades 7 e 10 verificam-se nas partes 1 e 2.
- **O exame de demonstração, o laboratório e o tutor usam dados diferentes dos do exame** (um cartão de banco, um portátil sem Wi-Fi, encomendas, não os telefones da situação E), para o aluno não decorar respostas.
- **Personagens conhecidas:** o Nuno e a Thandi (o fim da história do A2: o Nuno fica com o lugar na equipa conjunta) e a Lurdes (a aluna-modelo de todos os exames).
- **Sem mudanças no código:** o guião, a escala e as situações carregam-se por curso.

## O que falta

1. **Carregar o exame no curso A2.2** (exame.md, secção 4).
2. Leitura pelos professores.
3. Vídeos (vozes: o examinador, a Lurdes, o Nuno e a Thandi já existem), áudio do laboratório e carregamento na plataforma.
