# Análise geral do curso (A1 a C1) e da plataforma

**Data:** 18 de Novembro de 2026 · **Âmbito:** os cinco planos, as 50 unidades, as 10 revisões e os 10 exames, cruzados com as fontes ([01-fontes-do-curso.md](01-fontes-do-curso.md) e [notas-fontes/](notas-fontes/)); e o código da plataforma (API, web e app) no que toca à ligação entre vídeo, laboratório e tutor e à retenção dos alunos.

**Como foi feita:** leitura das fontes e dos mapas dos planos; verificações automáticas a todos os ficheiros (validador do laboratório, tipos de exercício, explicações, duração das conversas, palavras-alvo); e leitura do código da plataforma. Onde um número é uma estimativa ou vem de memória, está dito.

## 1. Veredicto

O conteúdo é sólido, coerente e original, e segue a espinha dorsal certa (Core Inventory). **O ponto fraco não está nas aulas: está no pouco tempo em que o aluno fala de facto, e no facto de a plataforma ainda não saber em que ponto do curso cada conversa e cada lição de laboratório encaixam.** O curso foi escrito como um percurso (aula → laboratório → conversa guiada → conversa livre), mas a plataforma mostra três listas separadas. É aí que os alunos se perdem e desistem.

## 2. O que está bem (e deve manter-se)

- **Cobertura do Core Inventory:** a gramática e as funções de cada nível estão quase todas nas unidades certas (excepções na secção 3).
- **Mediação português → inglês em todas as unidades**, do B1 ao C1: é o que o CEFR Companion Volume 2020 acrescentou e o que nenhum manual comercial dá a um aluno angolano.
- **Falsos amigos como fio condutor desde o A2**, sem repetições entre níveis — como as fontes recomendam para falantes de português.
- **Conteúdo 100% original**, com contexto angolano e da África Austral: o risco de direitos de autor é baixo.
- **Laboratório tecnicamente limpo:** 385 lições e 4 659 exercícios, todos aceites pelo validador da plataforma (0 erros).
- **A ordem das opções não denuncia a resposta:** nos ficheiros, a opção certa está sempre em primeiro lugar, mas a plataforma baralha-as no servidor (no questionário e no laboratório) — confirmado no código.
- **A plataforma já tem as peças de um sistema inteligente:** perfil de fala, banco de frases com repetição espaçada, padrões de erro, memória do tutor, sequências (*streaks*) e meta diária alimentadas pelas três peças.

## 3. Cruzamento com as fontes: erros e inconsistências

| # | Gravidade | O que as fontes dizem | O que temos | O que fazer |
|---|---|---|---|---|
| 1 | **Alta** | Um nível CEFR pede muito mais horas do que as nossas: o próprio plano do A1 cita 100–120 h por nível (OUP); a referência habitual da Cambridge é de cerca de 700–800 h acumuladas até ao C1 (de memória — a confirmar). | 55 + 60 + 70 + 75 + 80 = **340 h** do A1 ao C1. | Não prometer "chega ao nível C1"; certificar "concluiu o curso C1.2 e passou o exame oral". E aumentar o volume de prática (secção 6) — sobretudo a fala. |
| 2 | **Alta** | O curso é "focado na fala". | As conversas com o tutor somam **1,6 h no A1, 2,2 h no A2 e cerca de 3,2 h em cada nível do B1 ao C1** — cerca de 13 h em 340 (4%). No laboratório, a fala (resposta falada e pronúncia) é 22–25% dos exercícios. | Conversa curta diária com o tutor fora do guião; repetição das conversas com variação; mais exercícios de fala no laboratório (secção 6). |
| 3 | Média | Core Inventory C1, temas: **artes, livros e literatura, cinema**. | O plano do C1 (secção 9) diz que estão nas unidades 8 e 9 — **não estão**. O C1 é todo profissional. | Corrigir a tabela do plano; acrescentar o tema em duas aulas "Real English" (por exemplo, uma crítica de um filme e uma conversa sobre um livro) ou numa unidade opcional. |
| 4 | Média | Core Inventory C1, gramática: **modais no passado** e ***wish / if only* para arrependimentos**. | Só aparecem em perguntas de reciclagem (uma ou duas vezes); o plano dá-os como "revistos". | Uma aula de língua ou meia aula na unidade 3 (estratégia: *we should have…, we needn't have…, if only we had…*). |
| 5 | Média | Core Inventory A1: superlativos e *could / couldn't*. | Ficam para o A2 (unidades 4 e 9). | Aceitável (é o que fazem os manuais), mas deve constar da tabela de cobertura do A1 como decisão. |
| 6 | Média | As fontes pedem um **inventário de vocabulário próprio por nível** e a regra "95% das palavras dentro do nível", validada automaticamente. | **O inventário não existe como ficheiro**; a regra nunca foi verificada. "Fechar o inventário" está nos próximos passos de todos os planos. | Criar o inventário (base NGSL, aferida com Oxford 3000/5000) e um verificador automático dos guiões. É o que falta para garantir que o A1 é mesmo A1. |
| 7 | Média | CEFR Companion Volume: descritores de oralidade, mediação e pronúncia. | Continuam marcados **[NV — não verificado]** em todos os planos (16 marcas nos planos e 14 no estudo das fontes). | Descarregar o PDF à mão e confirmar os descritores de cada nível; é uma tarde de trabalho de um professor. |
| 8 | Baixa | Recursos abertos (VOA, Common Voice, Tatoeba, CMUdict) para alimentar a escuta e o laboratório. | Não foram usados: tudo é escrito de raiz e dito por voz sintética. | Decisão válida. Mas a escuta fica pobre em sotaques reais — ver o ponto 10. |
| 9 | Baixa | Formatos das provas orais da Cambridge (não verificados nas notas). | Os nossos exames seguem-nos correctamente (entrevista, turno longo, tarefa, discussão; três opções no C1). | Só confirmar as durações oficiais antes de as citar em público. |

## 4. Inconsistências dentro do conteúdo (verificações automáticas)

| # | Gravidade | Problema | Números | O que fazer |
|---|---|---|---|---|
| 10 | **Alta** | **A escuta do laboratório não cresce com o nível.** O limite de 300 caracteres faz com que o C1 ouça frases de 18 palavras em média — as mesmas do B1 (17). E a resposta está sempre literalmente na frase. | A1: 9 palavras; A2: 15; B1: 17; B2: 18; C1: 18. | Do B2 em diante, escutas de 30–60 segundos com perguntas de inferência ("o que quer ela dizer?"). Pede uma alteração ao formato do laboratório. |
| 11 | **Alta** | **Quase nenhum exercício explica o erro.** Quando o aluno falha, vê a resposta certa, mas não o porquê. | Com explicação: A1 24%; A2 8%; B1 9%; B2 4%; C1 3%. | Acrescentar uma explicação curta em português a todos os exercícios de escolha e de completar. Pode ser gerada e revista em lote. |
| 12 | Média | **A resposta-modelo não corresponde ao que se pede.** No B2 e no C1 pede-se uma resposta "até 90 segundos" (cerca de 200 palavras), mas o modelo tem 38–42 palavras (15–20 segundos), por causa do limite de 300 caracteres. | Modelo médio: B1 38; B2 42; C1 38 palavras. | Subir o limite do modelo ou mostrá-lo como "esqueleto" (os pontos a cobrir), e dizer ao aluno o tempo esperado. |
| 13 | Média | **A avaliação da pronúncia só ouve os primeiros 30 segundos** de uma gravação que pode ter 90. | Limite do serviço (Azure). | Dizer ao aluno o que é avaliado em quê; nas respostas longas, avaliar o conteúdo e a língua (texto) e só uma amostra da pronúncia. |
| 14 | Média | **Palavras-alvo anunciadas que não aparecem na aula.** No C1 foi corrigido com um verificador automático; o A1, o A2 e o B1 nunca passaram por ele. | Estimativa grosseira (com falsos positivos): 14–18% das palavras-alvo do A1 ao B1; 8% no B2; 3% no C1. | Correr o verificador nos três primeiros níveis e corrigir as fichas ou os diálogos. |
| 15 | Média | **Não há uma "bíblia" de personagens e de cronologia.** Só no C1 apanhei três colisões por acaso (o director financeiro da Mopane, o apelido da Thandi, a empresa da Lerato). | — | Um ficheiro único com todas as personagens (nome, empresa, cargo, onde aparecem) e a linha do tempo de 2026 a 2030. |
| 16 | Baixa | **Um só protagonista (o Nuno, homem, tecnologia e energia) durante cinco níveis.** A Lurdes (contabilista) só aparece nos exames. | — | Nos cursos de sector (banca, petróleo, aviação), protagonistas diferentes; no curso geral, dar mais aulas "Work & Life" à Inês, à Lindiwe e à Lurdes. |
| 17 | Baixa | **O laboratório é sobretudo de reconhecimento** (escolher e completar são mais de metade), com três opções em que as erradas são agramaticais — fácil para um aluno de C1. | Escolher + completar: 54% no C1. | No B2 e no C1, trocar parte por transformação falada ("diga isto de forma mais diplomática") — o formato `responder` já existe. |

## 5. A ligação entre vídeo, laboratório e tutor

**O que o conteúdo pressupõe:** cada unidade é um percurso — três aulas de língua → conversa guiada → aulas D, E e F → conversa livre → questionário; cada aula tem a sua lição de laboratório. Os ficheiros `tutor.json` dizem `tipo: guiada / livre` e `depois_da_aula: 1C`.

**O que a plataforma faz hoje (confirmado no código):**

| Ligação | Estado | Consequência |
|---|---|---|
| Aula de vídeo → lição de laboratório | Existe (um campo opcional na aula). A página da aula mostra sempre "Praticar no laboratório". | Funciona, se alguém preencher o campo em cada uma das 335 aulas. Nada leva o aluno lá quando acaba o vídeo. |
| Lição de laboratório → aula de vídeo | **Não existe.** | Quem entra pelo laboratório não sabe que aula ver primeiro. |
| Conversa do tutor → unidade ou aula | **Não existe.** A situação só se liga ao curso. **O campo `depois_da_aula` e a distinção guiada / livre não existem na plataforma.** | As 22 conversas de cada nível aparecem numa lista corrida, "Do curso X". O aluno não sabe qual fazer nem quando. **É a maior quebra entre o que escrevemos e o que o aluno vê.** |
| O tutor sabe o que o aluno estudou? | Em parte: recebe o nível, a área, os três padrões de erro, oito frases em aprendizagem e a última conversa. **Não recebe as aulas concluídas nem as palavras e os sons difíceis.** | O tutor pode usar língua que o aluno ainda não aprendeu, e não insiste nos sons em que o aluno falha. |
| Erros → reforço | Os erros do laboratório e das conversas entram no banco de frases e na revisão diária. Não geram exercícios novos nas lições. | Bom. É o motor certo; falta mostrá-lo ao aluno ("isto está aqui porque falhou ontem"). |
| Frases do vídeo → revisão | As frases aprovadas de cada aula entram na repetição espaçada quando a aula é concluída. | Bom. |
| "O que faço a seguir?" | **Não existe um passo seguinte único.** O painel tem "Continuar curso" (vai para a página do curso, não para a aula) e três atalhos fixos. | O aluno tem de decidir sozinho, todos os dias, entre vídeo, laboratório, revisão e tutor. |
| Pontos | O laboratório, a revisão e as conversas dão pontos; **o questionário do vídeo não** (os pontos não chegam à liga nem às conquistas). | Quem estuda pelo vídeo sente que "não conta". |

## 6. Como tornar a plataforma mais inteligente e reduzir o abandono

Por ordem de efeito esperado sobre a retenção.

1. **Um único "passo seguinte".** No painel e no fim de cada actividade: "A seguir: laboratório 3B (8 min)". O percurso da unidade passa a ser uma só linha — aula, laboratório, conversa guiada, conversa livre, questionário — com o que está feito e o que falta. Para isto, a situação do tutor precisa de dois campos (a aula depois da qual aparece e o tipo), que o nosso conteúdo já traz.
2. **Falar todos os dias, logo no primeiro dia.** Uma conversa de 3 minutos com o tutor no fim de cada aula (a "conversa da aula" já existe no código — torná-la o passo por omissão) e a meta diária medida em **minutos de fala**, não só em minutos de estudo. É o que duplica o tempo de fala sem escrever conteúdo novo.
3. **O tutor a conhecer o aluno.** Dar-lhe a lista das aulas concluídas (para só usar língua já ensinada) e os sons e palavras difíceis; e fazê-lo abrir cada conversa com uma frase do tipo "Na semana passada custou-lhe o *th*. Vamos tentar outra vez?". Um tutor que se lembra é a razão mais forte para voltar.
4. **Recuperar quem pára.** Hoje só há o lembrete da meta diária. Faltam: notificações *push* reais na app (hoje são só locais); uma mensagem ao 3.º, 7.º e 14.º dia sem actividade, por WhatsApp ou SMS (em Angola, mais eficaz do que o *e-mail*); "a sua sequência acaba hoje"; e "o exame está pronto". E um plano de regresso: depois de uma pausa, a plataforma propõe 5 minutos de revisão, não a aula seguinte.
5. **Ver onde os alunos desistem.** Não existe um funil por aula. Sem isso, não sabemos se o problema é a aula 1C do A1 ou o primeiro exame. Um quadro para a direcção e os professores: quantos começam e quantos acabam cada aula, cada lição e cada conversa. O estado "em risco" (10 dias sem actividade) só existe para o professor; deve existir também para a direcção.
6. **Perguntar "porquê" no primeiro dia.** O acolhimento pergunta a área e os minutos por dia, mas não a razão ("uma entrevista em Março", "falar com clientes"). Sem razão, não há como lembrar o aluno do seu objectivo quando esmorece. O campo já existe no perfil; falta a pergunta.
7. **Mostrar progresso que se sente.** "Este mês falou 42 minutos em inglês"; "há três semanas não conseguia dizer isto" (com a gravação antiga ao lado da nova, quando o aluno a autorizou). O progresso na fala é invisível para o próprio — é preciso mostrá-lo.
8. **Vitórias pequenas no início.** A primeira semana decide quase tudo: a primeira conversa com o tutor deve acontecer no primeiro dia, durar 2 minutos e acabar com um elogio concreto. O primeiro exame só aparece ao fim de cinco unidades — é tarde; acrescentar um "mini-desafio de fala" no fim de cada unidade, com certificado partilhável.
9. **Dar pontos ao questionário do vídeo**, para que as três peças contem para a liga e as conquistas.
10. **Explicar os erros** (ponto 11 da secção 4): um aluno que falha sem perceber porquê desiste mais depressa do que um que falha e aprende.

## 7. Prioridades

| Ordem | O quê | Tipo | Esforço |
|---|---|---|---|
| 1 | Ligar as conversas do tutor às aulas e mostrar o percurso da unidade com um "passo seguinte" | Plataforma | Médio |
| 2 | Carregar os cursos B2 e C1 e os quatro exames, com a ligação aula → laboratório preenchida | Plataforma | Baixo |
| 3 | Explicações em todos os exercícios de escolha e de completar | Conteúdo | Médio (em lote) |
| 4 | Conversa da aula por omissão e meta em minutos de fala | Plataforma | Baixo |
| 5 | Notificações de regresso (*push*, WhatsApp ou SMS) e funil de abandono | Plataforma | Médio |
| 6 | Tutor com as aulas concluídas e os sons difíceis | Plataforma | Baixo |
| 7 | Inventário de vocabulário e verificador automático; palavras-alvo do A1 ao B1 | Conteúdo | Médio |
| 8 | Escuta mais longa e com inferência no B2 e no C1 | Conteúdo e formato | Médio |
| 9 | Lacunas do C1 face ao Core Inventory (artes, modais no passado, *wish*) e correcção da tabela de cobertura | Conteúdo | Baixo |
| 10 | Bíblia de personagens; confirmação dos descritores do CEFR | Conteúdo | Baixo |

**O que não foi verificado nesta análise:** o estado do que está carregado na base de dados de produção; a qualidade dos vídeos e do áudio (ainda não existem); e o comportamento real dos alunos (não há dados de utilização). As conclusões sobre o abandono são de experiência de ensino e da leitura do código, não de medições.
