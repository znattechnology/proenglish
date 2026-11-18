# Imagens do sistema: o que é preciso, onde se fazem e quanto custam

Análise de 18 de Novembro de 2026. Os números saem de uma contagem automática dos 60 conjuntos de ficheiros (A1 a C1) e do código da plataforma; são estimativas, e a lista exacta sai do manifesto descrito na secção 5.

## 1. Resumo

- **Personagens:** os guiões nomeiam cerca de 120 pessoas, mas só umas **30 aparecem em cena com frequência** (o Nuno em 207 indicações de ecrã; o Paulo em 59; a Thandi em 49; a Sílvia em 44). As outras são vozes ou aparecem uma vez. É preciso uma **bíblia de personagens** (já era uma falha apontada na análise geral) antes de gerar qualquer cena.
- **Vídeo-aulas:** 335 aulas e cerca de 2 960 indicações `[ECRÃ: …]`. A maior parte é texto (frases, tabelas, ✘/✔): faz-se com modelos de diapositivo, não com IA. Ficam **cerca de 600 imagens** de cena, fotografia e ilustração.
- **Laboratório:** a plataforma **já mostra** imagens nas opções de escolha múltipla (web e app), mas **o formato dos ficheiros não as aceita e nenhum dos 60 laboratórios as prevê**. Proponho cerca de 450 ilustrações de vocabulário no A1 e no A2.
- **Resto da plataforma:** capas de curso, conversas com o tutor, conquistas, site e estados vazios: cerca de 200 imagens.
- **Ferramenta:** sim, **Nano Banana**: o **Pro** para personagens e cenas (mantém as mesmas pessoas a partir de imagens de referência) e o **2.1** (mais barato) para as ilustrações simples do laboratório.
- **Custo previsto: cerca de US$ 320 a 490** em geração, ou **US$ 450 a 650 com margem** para refazer. O armazenamento é desprezável.

## 2. Onde é que o sistema precisa de imagens

| Parte | Onde aparece | Quantas (finais) | Como se faz |
|---|---|---|---|
| Personagens (bíblia) | Base de todas as cenas | 30 principais × 4 vistas + 40 secundárias = **160** | Nano Banana Pro, com aprovação sua |
| Lugares recorrentes | Escritório e copa da Kalandula Tech, recepção, escritório da Mopane em Sandton, a central do Tômbwa, a obra… | **15 × 2 = 30** | Nano Banana Pro |
| Cenas das vídeo-aulas | Abertura de cada aula e situações ("a copa da Kalandula Tech; o Paulo com o telemóvel…") | **~450** | Nano Banana Pro, com as referências das personagens e do lugar |
| Fotografias e ilustrações das aulas | Vocabulário (comida, objectos, transportes, sinais de segurança, caras), sobretudo A1–A2 | **~150** | Nano Banana 2.1 |
| Documentos e gráficos das aulas | E-mails, agendas, gráficos, tabelas, diapositivos, organogramas, cartas em português | ~90 | **Modelos de diapositivo (sem IA)**: os números e a ortografia têm de ser exactos |
| Texto no ecrã | Frases, tabelas, ✘/✔ | ~2 600 | Modelos de diapositivo (sem IA) |
| Laboratório | Opções com imagem ("Escolha a imagem: *a receipt*") | **~450** (banco de imagens por palavra, reutilizáveis) | Nano Banana 2.1, estilo único de ilustração |
| Conversas com o tutor | Um cartão com a cena e a pessoa que o tutor representa (110 conversas) | **110** | Nano Banana Pro |
| Capas de curso | 10 cursos em vídeo, 10 laboratórios, cursos por sector | **~25** | Nano Banana Pro |
| Conquistas | Hoje são emojis; medalhas próprias | **~30** | Nano Banana Pro |
| Site público e app | Imagem principal, secções, estados vazios, acolhimento | **~35** | Nano Banana Pro |
| Logótipos das empresas fictícias | Kalandula Tech, Mopane Systems, Mussulo Energy, Morro Azul Energia, Mussiro… | ~8 | Rascunho com IA, acabamento à mão |
| Professor de IA dos vídeos | O rosto do professor | 1 a 3 | Depende da ferramenta de vídeo, ainda por escolher |

**O que não se gera:**
- **testemunhos do site:** têm de ser de alunos reais; uma cara inventada seria um testemunho falso;
- **capturas para as lojas de aplicações:** são capturas reais;
- **certificados e imagens de partilha:** fazem-se com modelos;
- **exames:** são só de voz, sem fotografias, por decisão dos planos.

## 3. Personagens: a bíblia vem primeiro

Sem referências fixas, o Nuno da aula 1A do A1 não é o mesmo da 10G do C1. Proposta:

1. **Ficha escrita por personagem**, a partir dos guiões: idade em 2026, origem, aspecto, roupa de trabalho, empresa e cargo por nível, e as cenas onde aparece. A história vai de 2026 a 2031, por isso o Nuno precisa de duas versões (júnior em Luanda; Project Lead em Joanesburgo).
2. **Folha de referência com 4 vistas por personagem principal** (frente, três quartos, corpo inteiro, expressões), aprovada por si.
3. **Lugares recorrentes** com a mesma lógica.
4. **Estilo único** para todo o curso (ilustração editorial ou fotografia realista). É a primeira decisão a tomar, porque muda tudo o resto.

O elenco das 30 personagens principais, por número de cenas: Nuno, Paulo, Thandi, Sílvia, Lerato, Mateus, Elsa, Inês, Lindiwe, Rajesh, Sr. Baptista, Ana, Hannah, Bongani, Ingrid, Sr. Okafor, Sipho, Femi, Pieter, Rita, João, Arjun, Chanda, David Nkosi, Celeste, Dr Mthembu, Mei, Kagiso, Lúcia Tembe e Lurdes Cassoma (a aluna-modelo dos exames).

## 4. Laboratório

- O que existe: `ChallengeOption.image_url`; a web e a app já mostram a imagem em cada opção.
- O que falta:
  - o formato dos exercícios (`pratica_formato.validar`) e o comando de carregamento só aceitam `texto` e `certa` nas opções;
  - o editor do professor não tem onde pôr a imagem.
- Proposta: um campo `imagem` (opcional) nas opções, um **banco de imagens por palavra** (a mesma imagem de *receipt* serve em todas as lições) e exercícios novos de vocabulário com imagem no A1 e no A2.
- Contagem: cerca de 140 exercícios de escolha e de pares no A1–A2 têm opções curtas, mas só uma parte é desenhável (*a refund* sim; *Stop worrying!* não). Daí as ~450 imagens.
- Do B1 ao C1, as imagens no laboratório acrescentam pouco: os exercícios são de estrutura e de sentido.

## 5. Onde se fazem

| Via | Para quê | Prós | Contras |
|---|---|---|---|
| Aplicação Gemini / AI Studio, à mão | Bíblia de personagens e estilo | Rápido para experimentar; escolhe-se ao vivo | Não se repete a 1 500 imagens; não deixa registo |
| **Comando no projecto que chama a API do Gemini** | Tudo o resto | Reprodutível; usa as referências aprovadas; preço de lote (metade) | Precisa de chave da API com pagamento activo |

Recomendo as duas: a bíblia à mão (ou com o comando, em modo interactivo) e o resto pelo comando. O desenho:

1. **Manifesto por unidade** (`imagens.json`, ao lado dos guiões): id, tipo, descrição, personagens, lugar, formato (16:9 para vídeo, 1:1 para laboratório) e onde a imagem é usada.
2. **Comando** `gerar_imagens` que:
   - lê o manifesto e envia a descrição com as imagens de referência;
   - pede imagens **sem texto** (o texto vai por cima, na montagem);
   - guarda as variantes numa pasta de revisão.
3. **Revisão:** uma página simples para aprovar ou pedir outra variante.
4. **Publicação:**
   - as imagens aprovadas vão para o R2 (as chaves do R2 ainda estão pendentes);
   - as do laboratório, das conversas e das capas ficam ligadas na base de dados;
   - as das aulas seguem para a montagem dos vídeos.

## 6. Previsão de custo

Preços da API do Gemini em Novembro de 2026, segundo sítios agregadores (confirmar na página de preços da Google antes de gastar):
- **Nano Banana Pro:** US$ 0,134 por imagem a 1K ou 2K e US$ 0,24 a 4K; em lote, metade.
- **Nano Banana 2.1:** US$ 0,0336 a 1K e US$ 0,0504 a 2K.
- **Referências:** cada imagem de referência enviada custa cerca de US$ 0,001.
- **O Nano Banana original (2.5 Flash Image)** vai ser retirado. Não convém começar com ele.

Contei várias tentativas por imagem final: 4 nas personagens e na plataforma, 3 nas cenas e nas conversas, 2 nas ilustrações do laboratório.

| Bloco | Finais | Gerações | Modelo | Normal | Em lote |
|---|---|---|---|---|---|
| Personagens e lugares | 190 | 760 | Pro 2K | US$ 102 | (à mão, sem lote) US$ 102 |
| Cenas e ilustrações das aulas | 600 | 1 800 | Pro 2K | US$ 241 | US$ 121 |
| Laboratório | 450 | 900 | 2.1 1K | US$ 30 | US$ 15 |
| Conversas com o tutor | 110 | 330 | Pro 2K | US$ 44 | US$ 22 |
| Plataforma (capas, conquistas, site, logótipos) | 100 | 400 | Pro 2K | US$ 54 | US$ 54 |
| Imagens de referência enviadas | — | ~3 000 envios | — | ~US$ 20 | ~US$ 10 |
| **Total** | **~1 450** | **~4 200** | | **~US$ 490** | **~US$ 325** |

- **Com 30% de margem** (mudança de estilo, personagens refeitas, cenas acrescentadas): **US$ 450 a 650**.
- **Armazenamento no R2:** cerca de 1 GB em WebP, uns cêntimos por mês.
- **O que não está nesta conta:** a ferramenta de vídeo com o professor de IA (o maior custo de produção, a escolher à parte), as horas de revisão e a montagem dos diapositivos.

## 7. Riscos e regras

- **Texto dentro das imagens:** não. Os modelos erram a ortografia (sobretudo em português) e os números, que têm de bater certo com os guiões. O texto vai por cima, na montagem.
- **Pessoas reais, marcas reais e logótipos reais:** não. As empresas são fictícias e os lugares de Angola aparecem de forma genérica e reconhecível.
- **Representação:** profissionais angolanos e da África Austral, idades variadas, sem estereótipos. A revisão humana de cada imagem é obrigatória.
- **Consistência:** a Google anuncia que o Pro mantém até cerca de 5 pessoas numa imagem a partir das referências; cenas com mais gente pedem composição ou planos mais abertos. Confirmar no piloto.
- **Marca de água:** todas as imagens do Gemini levam a marca SynthID (invisível). Não atrapalha.

## 8. Próximo passo proposto

Um **piloto de cerca de US$ 10**:
1. o estilo (três propostas);
2. as folhas de referência de 6 personagens (Nuno, Paulo, Sílvia, Ana, Mateus, Sr. Baptista) e de 2 lugares (escritório e copa da Kalandula Tech);
3. as cenas da unidade 1 do A1;
4. 20 ilustrações de laboratório.

Com o piloto aprovado, faz-se a bíblia completa e o resto em lote.

Fontes dos preços: [benchlm.ai](https://benchlm.ai/media-pricing/nano-banana), [pixmind.io](https://www.pixmind.io/posts/nano-banana-pro-pricing-guide-2026), [whizi.io](https://whizi.io/resources/nano-banana-pricing/), [usagebox.com](https://usagebox.com/articles/nano-banana-pro-api-pricing-cost-per-image-2026), [blog da Google](https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/).
