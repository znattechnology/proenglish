# Videoclipe do hino — guião plano a plano (rascunho 1)

Música: maquete `hino-pop-r2c` (2:50, cerca de 103 BPM), em `apps/api/media/hino/hino-oficial-maquete.mp3`. Letra em [hino.md](hino.md). Decidido a 19/11/2026.

## Ideia

**Um dia na Kalandula Tech, do medo à voz.** O clipe abre com o Paulo no primeiro dia, calado na reunião, e fecha com toda a equipa a cantar no terraço, ao pôr do sol sobre Luanda.

- **Quem canta:**
  - O **Paulo** dá a voz masculina, nas estrofes.
  - A **Ana** dá a voz feminina, nos pré-refrões e refrões.
  - A **equipa toda** faz o coro.
- **A Professora Luena** aparece no seu estúdio de aula, nos dois «Repete comigo!». Não entra nas cenas da empresa, porque não faz parte da história.

## Regras de produção

- **Ferramenta:** Gemini Omni Flash (`gemini-omni-1.2-flash`), como na aula do A1, com 16:9 a 720p.
  - Cada plano parte de uma **imagem inicial** feita a partir das fichas aprovadas, para as caras serem sempre as mesmas.
  - Geram-se planos de 8 s, que se cortam na montagem.
- **O som de cada plano deita-se fora;** a banda sonora é só a música.
- **Lábios:** o Omni não aceita a música como entrada (testado a 19/11/2026).
  - Nos planos marcados **«grito»**, as personagens dizem a palavra no plano gerado («ProEnglish!», «Hello!»). Na montagem alinha-se a boca com a música.
  - Nos planos marcados **«canto»**, o Paulo ou a Ana cantam a frase com o som do Omni e alinha-se pelo início da frase. Se a diferença se notar, estes são os candidatos a uma ferramenta de sincronização de lábios.
  - Nos restantes planos não se vê ninguém a cantar.
- **Sem texto gerado pela IA dentro da imagem.** Os ecrãs aparecem desfocados ou de lado, e não há logótipos nem marcas reais. As legendas da ponte e o cartão final da marca põem-se na montagem.
- **Cores da marca nas roupas e nos cenários,** sem exagero: azul-marinho (#000066) e amarelo (#ffc72c).
- **Tempos:** vêm do mapa da música feito pelo Gemini. Confirmam-se a ouvir antes da montagem.

## Planos

| # | Tempo | Secção | Quem | Cena e acção | Câmara | Imagem inicial | Lábios |
|---|---|---|---|---|---|---|---|
| 1 | 0:00–0:06 | Intro | — | Luanda ao amanhecer: a baía, a Marginal e os prédios de Talatona ao longe; o sol nasce. | Drone lento a avançar | **nova** `clip-luanda-amanhecer` | — |
| 2 | 0:06–0:14 | Intro | Equipa | A porta de vidro da Kalandula Tech abre-se. A equipa, em fila, vira-se para a câmara e grita «This is ProEnglish!» de braços no ar. | Plano geral, câmara entra pela porta | **nova** `clip-equipa-entrada` | grito |
| 3 | 0:14–0:22 | Estrofe 1 | Paulo | Em casa, em Viana, de manhã: abotoa a camisa branca acabada de passar e olha-se ao espelho, nervoso. | Plano médio, depois grande plano no espelho | **nova** `clip-paulo-casa` | canto |
| 4 | 0:22–0:32 | Estrofe 1 | Paulo, Thandi, Sr. Baptista | Reunião: a Thandi fala e o Sr. Baptista acena. O Paulo abre a boca para responder, não sai nada, e baixa os olhos. | Plano médio sobre a mesa, depois grande plano do Paulo | `site-cena-reuniao` | — |
| 5 | 0:32–0:39 | Pré-refrão | Paulo | À noite, em casa, com auscultadores e o portátil: repete frases em voz alta e sorri pela primeira vez. | Grande plano, luz quente do ecrã | `site-cena-escuta` | canto |
| 6 | 0:39–0:46 | Pré-refrão | Professora Luena | No estúdio de aula, sorri, aponta para a câmara e diz «Repete comigo!», acompanhando o ritmo com a mão. | Plano médio, ligeiro avanço | `professora-enquadramento` | — |
| 7 | 0:46–0:48 | Pré-refrão | Paulo e Ana | Corte rápido: os dois, lado a lado na recepção, gritam «ProEnglish!» para a câmara. | Grande plano, ligeiro tremor de entusiasmo | **nova** `clip-ana-recepcao` | grito |
| 8 | 0:48–0:55 | Refrão | Ana | A Ana sai de trás do balcão a cantar «Hello, world — here I am!», e os colegas aparecem atrás dela. | Câmara recua à frente dela (travelling) | `clip-ana-recepcao` | canto |
| 9 | 0:55–1:00 | Refrão | Equipa | No terraço do prédio em Talatona, a equipa dança em grupo, com a cidade ao fundo. | Plano geral, câmara à volta do grupo | **nova** `clip-terraco-equipa` | — |
| 10 | 1:00–1:04 | Refrão | Sílvia, Mateus, Nuno | Três grandes planos seguidos, cada um a gritar «ProEnglish!». | Grandes planos | `clip-terraco-equipa` | grito |
| 11 | 1:04–1:09 | Estrofe 2 | Mateus | Na plataforma ao largo de Cabinda, de capacete, fala ao rádio com à-vontade; o mar ao fundo. | Plano médio, vento | **nova** `clip-mateus-plataforma` | — |
| 12 | 1:09–1:13 | Estrofe 2 | Sílvia | No escritório de Benguela, recebe um cliente estrangeiro e estende-lhe a mão com um sorriso. | Plano médio | **nova** `clip-silvia-cliente` | — |
| 13 | 1:13–1:18 | Estrofe 2 | Profissionais (sem personagens) | Três planos rápidos: uma médica num corredor de hospital, um mineiro junto ao camião, um técnico na torre de controlo. | Planos curtos, cerca de 1,5 s cada | capas `capa-sector-saude`, `-minas`, `-aviacao` | — |
| 14 | 1:18–1:29 | Estrofe 2 e pré-refrão | Paulo, Thandi, Sr. Baptista | A mesma sala do plano 4, agora o Paulo de pé, a apresentar com confiança. A Thandi sorri e o Sr. Baptista bate-lhe no ombro. | Plano médio, depois contracampo | **nova** `clip-paulo-apresenta` | canto |
| 15 | 1:29–1:36 | Pré-refrão | Professora Luena | De novo «Repete comigo!», mais perto. Faz o gesto de «agora você» e sorri com as covinhas. | Grande plano | `professora-enquadramento` | — |
| 16 | 1:36–1:38 | Pré-refrão | Equipa | No terraço, todos gritam «ProEnglish!». | Plano geral picado | `clip-terraco-equipa` | grito |
| 17 | 1:38–1:46 | Refrão | Ana, Paulo | Na Marginal de Luanda, ao fim da tarde, a Ana e o Paulo caminham a cantar; os colegas juntam-se pelo caminho. | Travelling à frente deles | **nova** `clip-marginal` | canto |
| 18 | 1:46–1:54 | Refrão | Elenco | Na Marginal, o elenco todo em linha, com a baía atrás, canta o refrão; no «ProEnglish!» saltam todos. | Plano geral, câmara sobe | `clip-marginal` | grito |
| 19 | 1:54–2:04 | Pausa instrumental | Equipa | Dança no terraço: o Nuno tenta um passo e falha, todos se riem, e o Sr. Baptista entra na dança. | Planos soltos ao ritmo | `clip-terraco-equipa` | — |
| 20 | 2:04–2:16 | Ponte | As 7 personagens | Sete planos de cerca de 1,7 s. Cada personagem, no seu sítio, olha para a câmara e acena. A frase aparece escrita no ecrã. | Grandes planos fixos | ver a tabela da ponte | — |
| 21 | 2:16–2:18 | Ponte | Elenco | No terraço, todos juntos: «This is ProEnglish!» | Plano geral | `clip-terraco-equipa` | grito |
| 22 | 2:18–2:30 | Refrão final | Elenco | Terraço ao pôr do sol: todos cantam e dançam, e a Ana e o Paulo vêm à frente. | Câmara à volta do grupo | `clip-terraco-equipa` | canto |
| 23 | 2:30–2:37 | Refrão final | Professora Luena | No estúdio, canta junto o «Say it with me» e bate palmas. | Plano médio | `professora-enquadramento` | — |
| 24 | 2:37–2:44 | Final | Elenco | O drone afasta-se do terraço e mostra Luanda iluminada ao anoitecer. | Drone a recuar e a subir | `clip-terraco-equipa` | — |
| 25 | 2:44–2:50 | Final | — | Cartão final, feito na montagem: logótipo ProEnglish, «From Angola to the world» e o endereço do site. | — | — | — |

### Ponte (plano 20)

| Tempo | Personagem | Onde | Legenda no ecrã |
|---|---|---|---|
| 2:04 | Ana | Recepção | *I'm Ana. What's your name?* |
| 2:06 | Paulo | Secretária dele | *Good morning! It's my first day.* |
| 2:08 | Mateus | Plataforma | *I'm from Huambo — and you?* |
| 2:10 | Sílvia | Escritório | *Nice to meet you, too!* |
| 2:11 | Thandi | Sala de reuniões | *I have a meeting at two.* |
| 2:13 | Sr. Baptista | Gabinete | *Welcome to the team!* |
| 2:14 | Nuno | Rua de Luanda, de mochila | *I'm new here... but I have a dream!* |

Na ponte não se vê ninguém a cantar, porque as vozes da maquete nem sempre batem com as personagens (a frase do Nuno é cantada por uma mulher).

## O que é preciso gerar

**Imagens iniciais novas:** 9, em 16:9, com as fichas como referência. Custam cerca de US$ 1,20.

| Imagem | Referências |
|---|---|
| `clip-luanda-amanhecer` | `estilo-foto` |
| `clip-equipa-entrada` | as 7 fichas, sem a Luena |
| `clip-paulo-casa` | `ficha-paulo` |
| `clip-ana-recepcao` | `ficha-ana`, `ficha-paulo` |
| `clip-terraco-equipa` | as 7 fichas |
| `clip-mateus-plataforma` | `ficha-mateus` |
| `clip-silvia-cliente` | `ficha-silvia` |
| `clip-paulo-apresenta` | `ficha-paulo`, `ficha-thandi`, `ficha-baptista` |
| `clip-marginal` | as 7 fichas |

A imagem do Nuno na rua e as restantes da ponte saem destas ou das fichas.

**Vídeo:** cerca de 30 planos de 8 s no Omni Flash (os 24 planos, mais os 7 da ponte, menos os repetidos). Na estimativa alta de US$ 0,10 por segundo, são cerca de US$ 24; com repetições, até US$ 35.

**Montagem:** com o mesmo pipeline da aula (`montar.py`). Música por baixo, cortes ao ritmo, legendas da ponte e cartão final.

## Depois, para espalhar a marca

- **Versões verticais (9:16)** de 15 a 30 s, só com o refrão, para TikTok, Instagram e WhatsApp. Os planos do refrão e dos gritos geram-se também em 9:16; cortar o 16:9 perde demasiado.
- **Desafio do refrão:** as pessoas cantam «Hello, world — here I am!» e dizem o seu nome em inglês.
