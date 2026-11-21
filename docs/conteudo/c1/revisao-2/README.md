# C1.2 · Revisão 2 e exame oral

**Estado:** primeira versão escrita, com uma revisão aula a aula ([n.º 1](revisao-1.md)); falta a leitura dos professores · **Plano:** [06-plano-C1.md](../../06-plano-C1.md), "Revisão 2 e exame oral do C1.2" · É o fim do curso.

## Objectivo

No fim do C1.2, o aluno consegue manter uma discussão de cerca de 12 minutos com fluência quase sem esforço sobre temas técnicos, éticos e abstractos, explicar ideias complexas, ser entrevistado, mudar de registo e conduzir uma negociação até um acordo.

## O que está nesta pasta

| Ficheiro | Conteúdo | Pronto a carregar? |
|---|---|---|
| [guioes.md](guioes.md) | R2A "Review: ethics, science, media and deals" (a Lindiwe tem uma renegociação com a Marula e uma entrevista de rádio no mesmo dia, e recebeu uma garrafa de uísque do cliente; o Nuno aconselha-a; os 10 erros mais comuns do C1.2); R2B "Getting ready for the C1.2 speaking exam" (as quatro partes, o que se avalia, duas estratégias novas, o último exame de demonstração da Lurdes) | Para o professor de IA |
| [laboratorio.json](laboratorio.json) | 2 lições de revisão (unidades 6–8 e 9–10 com o exame), 28 exercícios, 4 respostas faladas (duas de até 90 segundos) | Sim: validado com `pratica_formato.validar` (0 erros) |
| [tutor.json](tutor.json) | "Exam rehearsal: the office lease": ensaio do exame com o tutor (Rory, consultor, que na parte 3 faz de senhorio formal), em quatro partes, com 6 critérios | Sim: campos do modelo `Situacao` (nível C1); 10 minutos |
| [questionario.json](questionario.json) | 15 perguntas, três por unidade (U6 a U10), aprovação a 70% | Sim: formato `quiz_data` |
| [exame.md](exame.md) | O exame oral do C1.2: o que verifica, as quatro partes, o guião do examinador, a escala do C1.2 e como carregar na plataforma | Documento de referência |
| [exame-guiao.json](exame-guiao.json) | O guião do exame para a plataforma (12 minutos) | Sim: validado com `exame.validar_guiao`, sem cortes; `manage.py carregar_exame_curso` |
| [exame-situacoes.json](exame-situacoes.json) | As quatro situações da parte 3, cada uma com o registo da personagem, a pergunta de discussão e os dois contra-argumentos | Sim: `manage.py carregar_exame_curso` |

## Decisões pedagógicas

- **Sem gramática nova.** A R2A junta as cinco unidades num só dia da Lindiwe: uma oferta antes de uma negociação (ética e negociação), uma entrevista sobre baterias (ciência e media), e o registo em tudo.
- **Os 10 erros mais comuns do C1.2**, dois por unidade: ordem das palavras (*So can I*, *This I can promise*, *turn it down*, *Difficult as it was*) e falsos amigos (*pretensions*).
- **Duas estratégias novas, em blocos fixos:** responder com estrutura a uma pergunta abstracta (*There are two ways of looking at this… Much depends on… Where I come down is…*) e acompanhar o registo da personagem da parte 3.
- **O exame avalia o registo (unidade 9) em todas as situações:** cada personagem tem um registo indicado na descrição, que o examinador mantém desde a primeira frase.
- **Quatro situações, uma por tarefa das unidades 6, 7, 8 e 10**, cada uma com uma dificuldade e uma decisão.
- **O exame de demonstração, o laboratório e o tutor usam dados e perguntas diferentes dos do exame:** uma decisão do banco, o trânsito, uma aplicação bancária, as agências e a tecnologia e a liberdade (demonstração); o hospital e a honestidade nos negócios (laboratório); a pegada de carbono, o arrendamento do escritório e a negociação na escola (ensaio). O exame usa as pessoas com quem o aluno fala, o que se esperava no seu campo, as notícias, as contas da electricidade, o fornecedor simpático, os processos electrónicos, a carreira de autocarros e a cantina da universidade.
- **A Lurdes faz o seu último exame** e lembra o caminho do curso: do "My name is Lurdes" do A1 a discutir política bancária em inglês.
- **Sem mudanças no código:** o nível C1 já existe na plataforma, e o guião, a escala e as situações carregam-se por curso.

## O que falta para publicar

Leitura pelos professores; vídeos com o professor de IA; áudio (4 escutas, 2 pronúncias; o exame de demonstração com duas vozes); criar o curso C1.2 na plataforma e carregar o exame com `carregar_exame_curso`.

**Com esta pasta, o curso English Communication Skills fica escrito do A1 ao C1.**
