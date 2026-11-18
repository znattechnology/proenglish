# C1.2 · Unidade 7 — Science and change (6 aulas)

**Estado:** primeira versão escrita; falta a revisão aula a aula e a leitura dos professores · **Plano:** [06-plano-C1.md](../../06-plano-C1.md), unidade 7

## Objectivos da unidade

No fim da unidade, o aluno consegue:

1. falar de planos e previsões do passado que se cumpriram ou não, com o futuro no passado (*We were going to… The facility was to have opened in June. I knew it would…*);
2. falar do que está prestes a acontecer com nuance (*be on the verge of, be set to, be due to, be about to*);
3. explicar uma ideia científica ou técnica complexa a um público não especializado, com analogias e exemplos;
4. especular sobre mudanças tecnológicas e ambientais e o seu impacto.

| Objectivo | Aulas | Laboratório | Tutor | Questionário |
|---|---|---|---|---|
| 1. O futuro no passado | 7A, 7E, 7F | 7A, 7F, 7R | Livre | 1, 2 |
| 2. O futuro próximo com nuance | 7B, 7E | 7B, 7R | — | 3, 4 |
| 3. Explicar a não especialistas | 7C, 7E, 7F | 7C, 7E, 7F | Guiada e livre | 5, 6 |
| 4. Tecnologia e mudança | 7B, 7D, 7E | 7B, 7D, 7E | Livre | 7 a 9 |

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | Os 6 guiões (7A a 7F), 12 a 14 minutos cada | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 7 lições (7A a 7F e 7R), 93 exercícios: 17 de escuta, 7 de pronúncia, 14 de resposta falada (duas por lição, uma delas até 90 segundos) | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | Conversa guiada (depois da 7C): "Explain it to me" (Robin, um vizinho que não percebe nada de tecnologia, só percebe quando ouve uma boa analogia); livre (no fim): "The worried resident" (Morgan, morador desconfiado de uma antena 5G junto à escola) | Sim: campos do modelo `Situacao` (nível C1); 10 minutos |
| [questionario.json](questionario.json) | 12 perguntas (9 da unidade e 3 de reciclagem das unidades 1, 5 e 6), aprovação a 70% | Sim: formato `quiz_data` |

## Vocabulário da unidade (cerca de 80 palavras e expressões)

- **O futuro no passado:** was / were going to, was about to, was to have + particípio, would, was supposed to.
- **O futuro próximo:** be due to, be set to, be about to, be on the verge of, be bound to, be (un)likely to.
- **Explicar:** Think of it as…, It works a bit like…, …except that…, Put simply, …, In other words, …, Basically, …, What it does is…, what engineers call…, Does that make sense?, Let me put it another way, analogy, jargon.
- **Energia e ciência:** storage, store / release energy, the grid, capacity, peak, charge / discharge, cycle, renewable energy, fossil fuels, emissions, the energy transition, carry out research, findings, a peer-reviewed study, a breakthrough, experiment, test, measure, suggest, prove, lithium, sodium.
- **A comunidade:** community meeting, resident, concern, rumour, power cuts, cooling fans, recycling, trainee, the regulator.
- **Fala ligada (para reconhecer):** gonna, wanna, didja, dunno.
- **Falsos amigos:** experience (experiência de vida; "experiência" científica = experiment), physician (médico; "físico" = physicist).

## Decisões pedagógicas desta unidade

- **O futuro no passado ao serviço da honestidade:** na 7A e na 7F, as formas novas servem para admitir o que falhou ("The facility was to have opened in June." "This meeting was going to happen in April. It should have."); na 7E, a cientista usa-as para admitir um erro de previsão ("I thought we'd be there by now. I was wrong.").
- **O futuro com precisão (7B):** *due to* (o calendário), *set to* (tudo aponta para lá), *about to* (iminente), *on the verge of* (perto de algo grande, que ainda não aconteceu) — com a gramática certa de cada uma.
- **Explicar sem jargão (7C):** a primeira tentativa do Nuno é correcta e inútil (catorze palavras técnicas antes do verbo); a segunda começa por uma imagem — um depósito de água no telhado — e mostra onde a analogia acaba ("except that…").
- **Ciência com cuidado (7D, 7E):** "the study suggests" em vez de "proves"; separar o que se descobriu do que ainda não se sabe; não esperar pela tecnologia perfeita.
- **Uma comunidade, não um público (7F):** o Nuno pede desculpa pela reunião que não se fez, valida cada receio ("That's a very reasonable question") em vez de dizer "não há nada a temer", é honesto sobre o preço da electricidade (que não controla), e deixa falar dois técnicos da aldeia, formados no centro de formação da Mopane.
- **Factos técnicos simplificados de forma correcta:** baterias LFP (das de lítio, as de menor risco de incêndio), contentores separados com sensores e extinção própria, armazenagem para o fim da tarde, reciclagem prevista no contrato; a descoberta das baterias de sódio é fictícia, mas o campo de investigação é real.
- **Mediação:** de um artigo técnico em português, os factos que respondem aos receios da sala — incluindo que os moradores de lá também desconfiavam ao princípio.

## A história

Agosto de 2030. A Marula Power está a construir uma instalação de baterias ao lado da sua central solar, perto da aldeia de Mokgalo, no Limpopo; a Mopane faz a monitorização e forma seis técnicos locais. A instalação devia ter aberto em Junho e está prevista para 15 de Outubro; a reunião com a comunidade, que devia ter sido em Abril, nunca se fez, e correm rumores. Na segunda, 5, a Thandi e o Nuno olham para o que estava planeado (7A); na quarta, 7, a Lindiwe fala-lhe do que aí vem — os preços das baterias a cair, o sódio (7B); na sexta, 9, ensina-o a explicar sem jargão, com o Rajesh a fazer de morador (7C); na segunda, 12, o Nuno ouve "The Science Slot" na rádio (7E); na quinta, 22, explica tudo a cerca de 80 moradores de Mokgalo com um balde de água, responde aos receios, admite o que não pode prometer, e dois técnicos da aldeia, o Karabo e a Dineo, falam do curso (7F).

## O que falta para publicar

Revisão aula a aula; leitura pelos professores; vídeos com o professor de IA; áudio (17 escutas, 7 pronúncias, a 7E com formas reduzidas na fala do apresentador); imagens (o calendário do projecto, os contentores, o artigo da "Energia & Rede"); carregamento na plataforma.

A seguir vem a **unidade 8, "On air"**.
