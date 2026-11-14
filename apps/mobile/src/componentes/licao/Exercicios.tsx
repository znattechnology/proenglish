/**
 * Os exercícios da lição (apps/web/components/pe/licao/Exercicios.tsx), com o visual das telas
 * LicaoEscolha, LicaoSelecionar, LicaoTraducao, LicaoEscuta, LicaoFala, LicaoPares, LicaoOrdem e LicaoVF.
 * A resposta vai para o servidor tal como na web; a correcção é sempre do servidor.
 */
import { Image } from "expo-image";
import { CheckCircle2 } from "lucide-react-native";
import { useMemo, useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import { urlAbsoluto } from "@/api/config";
import { ConversaCurta } from "@/componentes/conversa/ConversaCurta";
import type { DetalhePronuncia, Exercicio, Resposta, ResultadoResponder } from "@/dominios/laboratorio/api";
import type { Gravacao } from "@/dominios/laboratorio/gravacao";
import { cor, fonte, raio } from "@/tema";
import { Aviso, Texto } from "@/ui";
import { BotaoOuvir, BotaoOuvirTexto, OuvirGrande } from "./Audio";
import { BotaoGravar, useGravador } from "./Gravador";
import { AvisoAnaliseAproximada, BalaoEnunciado, corBorda, Dica, EmPortugues, Enunciado, estiloOpcao, PalavrasComNota, type Visual } from "./Partes";

export type RespostaExercicio = { tipo: "texto"; resposta: Resposta } | { tipo: "audio"; gravacao: Gravacao } | null;
export type ResultadoFala = { nota: number; palavras: string[]; mensagem?: string | null; detalhe?: DetalhePronuncia | null; fonte?: string | null };

type Props = {
  ex: Exercicio;
  bloqueado: boolean;
  visual: Visual;
  aoMudar: (r: RespostaExercicio) => void;
  fala?: ResultadoFala | null;
  avaliacao?: ResultadoResponder | null;
  /** Conversa curta: saltar a conversa (sem pontos nem vidas). */
  aoSaltar?: () => void;
};

const ESPACO = /_{2,}|\[\s*\]/g;

function NumeroOpcao({ n }: { n: number }) {
  return (
    <View style={{ width: 28, height: 28, alignItems: "center", justifyContent: "center", borderRadius: raio.sm, borderWidth: 1.5, borderColor: cor.linhaForte, backgroundColor: cor.fundo }}>
      <Texto v="legenda" forte suave>
        {n}
      </Texto>
    </View>
  );
}

/** Pílula de palavra (banco, ordenar). */
function Palavra({ texto, usada, onPress, disabled, marca, rotulo }: { texto: string; usada?: boolean; onPress: () => void; disabled?: boolean; marca?: boolean; rotulo?: string }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo ?? texto}
      accessibilityState={{ disabled: !!disabled || !!usada }}
      disabled={disabled || usada}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: 44,
        paddingHorizontal: 14,
        justifyContent: "center",
        borderRadius: raio.sm,
        borderWidth: marca ? 0 : 2,
        borderColor: usada ? cor.fundoForte : cor.linhaForte,
        backgroundColor: marca ? cor.azulMarca : usada ? cor.fundoForte : pressed ? cor.fundoSuave : cor.fundo,
        opacity: disabled && !usada && !marca ? 0.6 : 1,
      })}
    >
      <Texto forte cor={marca ? cor.sobreMarca : usada ? cor.fundoForte : cor.tinta} style={{ fontSize: 17, lineHeight: 22 }}>
        {texto}
      </Texto>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Escolha: SELECT, ASSIST, TRUE_FALSE e escolha em TRANSLATION/LISTENING */
/* ------------------------------------------------------------------ */
function Escolha({ ex, bloqueado, visual, aoMudar }: Props) {
  const [id, setId] = useState<string | null>(null);
  const opcoes = ex.opcoes ?? [];
  const comImagens = opcoes.some((o) => o.imagem);
  const vf = ex.tipo === "TRUE_FALSE";

  const escolher = (oid: string) => {
    if (bloqueado) return;
    setId(oid);
    const o = opcoes.find((x) => x.id === oid)!;
    // TRANSLATION valida o texto mesmo quando é de escolha.
    aoMudar({ tipo: "texto", resposta: ex.tipo === "TRANSLATION" ? { text_answer: o.texto } : { selected_option: oid } });
  };

  const titulo = vf ? ex.instrucao || "Verdadeiro ou falso?" : comImagens || ex.tipo === "ASSIST" ? ex.pergunta : ex.instrucao || "Escolha a melhor resposta";
  const mostraBalao = !(comImagens || ex.tipo === "ASSIST");

  return (
    <Enunciado titulo={titulo}>
      {mostraBalao ? <BalaoEnunciado depois={ex.audio ? <BotaoOuvir src={ex.audio} sobreMarca /> : null}>{ex.pergunta}</BalaoEnunciado> : null}
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções de resposta" style={comImagens || vf ? { flexDirection: "row", flexWrap: "wrap", gap: 12 } : { gap: 12 }}>
        {opcoes.map((o, i) => {
          const sel = id === o.id;
          const estilo = estiloOpcao(sel, visual);
          return (
            <Pressable
              key={o.id}
              accessibilityRole="radio"
              accessibilityState={{ selected: sel, disabled: bloqueado && !sel }}
              accessibilityLabel={o.texto}
              disabled={bloqueado}
              onPress={() => escolher(o.id)}
              style={({ pressed }) => [
                { borderRadius: comImagens ? raio.md : raio.sm, opacity: bloqueado && !sel ? 0.6 : 1 },
                comImagens
                  ? { width: "47.5%", flexGrow: 1, padding: 10, gap: 8 }
                  : vf
                    ? { width: "47.5%", flexGrow: 1, minHeight: 72, alignItems: "center", justifyContent: "center", paddingHorizontal: 12 }
                    : { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 8 },
                estilo,
                pressed && !sel && !bloqueado ? { backgroundColor: cor.fundoSuave } : null,
              ]}
            >
              {comImagens ? (
                o.imagem ? (
                  <Image source={{ uri: urlAbsoluto(o.imagem) ?? undefined }} contentFit="cover" accessibilityIgnoresInvertColors style={{ height: 120, width: "100%", borderRadius: raio.sm, backgroundColor: cor.fundoForte }} />
                ) : (
                  <View style={{ height: 120, borderRadius: raio.sm, backgroundColor: cor.fundoForte }} />
                )
              ) : vf ? null : (
                <NumeroOpcao n={i + 1} />
              )}
              <Texto
                forte={sel || vf}
                centro={comImagens || vf}
                style={{ flexShrink: 1, fontSize: vf ? 19 : comImagens ? 17 : 18, lineHeight: vf ? 26 : 24 }}
              >
                {o.texto}
              </Texto>
            </Pressable>
          );
        })}
      </View>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Banco de palavras: FILL_BLANK com alternativas                       */
/* ------------------------------------------------------------------ */
function Banco({ ex, bloqueado, visual, aoMudar }: Props) {
  const espacos = Math.max(1, ex.espacos ?? 1);
  // Um lugar por espaço (null = vazio): tirar uma palavra não puxa as seguintes.
  const [cheios, setCheios] = useState<(string | null)[]>(() => Array(espacos).fill(null));
  const opcoes = ex.opcoes ?? [];
  const textoDe = (id: string) => opcoes.find((o) => o.id === id)?.texto ?? "";
  const preenchidos = cheios.filter(Boolean).length;

  const actualizar = (novo: (string | null)[]) => {
    setCheios(novo);
    if (novo.every(Boolean)) {
      const textos = (novo as string[]).map(textoDe);
      aoMudar({ tipo: "texto", resposta: espacos > 1 ? { text_answers: textos } : { text_answer: textos[0] } });
    } else aoMudar(null);
  };
  const tirar = (i: number) => !bloqueado && actualizar(cheios.map((c, j) => (j === i ? null : c)));
  const por = (id: string) => {
    const livre = cheios.indexOf(null);
    if (livre < 0) return;
    actualizar(cheios.map((c, j) => (j === livre ? id : c)));
  };

  const partes = ex.pergunta.split(ESPACO);
  const fundoEspaco = visual === "certo" ? cor.certoSuave : visual === "errado" ? cor.erradoSuave : cor.realce;
  const corEspaco = visual === "certo" ? cor.certo : visual === "errado" ? cor.errado : cor.tinta;

  return (
    <Enunciado titulo={ex.instrucao || "Complete a frase"}>
      <BalaoEnunciado depois={ex.audio ? <BotaoOuvir src={ex.audio} sobreMarca /> : null}>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 34 }}>
          {partes.map((p, i) => (
            <Texto key={i} cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 34 }}>
              {p}
              {i < partes.length - 1 ? (
                cheios[i] ? (
                  <Texto
                    onPress={() => tirar(i)}
                    accessibilityRole="button"
                    accessibilityLabel={`Tirar ${textoDe(cheios[i]!)}`}
                    forte
                    cor={corEspaco}
                    style={{ fontSize: 20, lineHeight: 34, backgroundColor: fundoEspaco }}
                  >
                    {` ${textoDe(cheios[i]!)} `}
                  </Texto>
                ) : (
                  <Texto accessibilityLabel="espaço por preencher" style={{ fontSize: 20, lineHeight: 34, backgroundColor: cor.realce }}>
                    {" ".repeat(12)}
                  </Texto>
                )
              ) : null}
            </Texto>
          ))}
        </Texto>
      </BalaoEnunciado>
      {preenchidos ? (
        <Texto v="legenda" suave>
          Toque numa palavra da frase para a tirar.
        </Texto>
      ) : null}
      <View accessibilityLabel="Palavras" style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {opcoes.map((o) => (
          <Palavra key={o.id} texto={o.texto} usada={cheios.includes(o.id)} disabled={bloqueado || preenchidos >= espacos} onPress={() => por(o.id)} />
        ))}
      </View>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Escrever: TRANSLATION, ditado (LISTENING) e FILL_BLANK sem alternativas */
/* ------------------------------------------------------------------ */
function CampoResposta({ rotulo, valor, aoMudar, bloqueado, visual, linhas = 1, autoFocus, placeholder }: { rotulo: string; valor: string; aoMudar: (v: string) => void; bloqueado: boolean; visual: Visual; linhas?: number; autoFocus?: boolean; placeholder?: string }) {
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      <TextInput
        accessibilityLabel={rotulo}
        value={valor}
        onChangeText={aoMudar}
        editable={!bloqueado}
        multiline={linhas > 1}
        autoFocus={autoFocus}
        placeholder={placeholder}
        placeholderTextColor={cor.tintaSuave}
        autoCapitalize={linhas > 1 ? "sentences" : "none"}
        autoCorrect={false}
        spellCheck={false}
        onFocus={() => setFoco(true)}
        onBlur={() => setFoco(false)}
        style={{
          minHeight: linhas > 1 ? 28 * linhas + 24 : 52,
          paddingHorizontal: 14,
          paddingVertical: 12,
          textAlignVertical: linhas > 1 ? "top" : "center",
          fontFamily: fonte.texto,
          fontSize: 18,
          lineHeight: linhas > 1 ? 28 : undefined,
          color: cor.tinta,
          backgroundColor: cor.fundo,
          borderWidth: 2,
          borderRadius: raio.sm,
          borderColor: corBorda(visual, foco ? cor.azulMarca : cor.linhaForte),
        }}
      />
    </View>
  );
}

function Escrever({ ex, bloqueado, visual, aoMudar }: Props) {
  const n = Math.max(1, ex.espacos ?? 1);
  const [textos, setTextos] = useState<string[]>(() => Array(n).fill(""));

  const mudar = (i: number, v: string) => {
    const novo = textos.map((t, j) => (j === i ? v : t));
    setTextos(novo);
    const cheios = novo.every((t) => t.trim());
    aoMudar(cheios ? { tipo: "texto", resposta: n > 1 ? { text_answers: novo.map((t) => t.trim()) } : { text_answer: novo[0].trim() } } : null);
  };

  if (ex.tipo === "TRANSLATION") {
    return (
      <Enunciado titulo={ex.instrucao || "Escreva em inglês"}>
        <EmPortugues texto={ex.pergunta} />
        <CampoResposta rotulo="A sua tradução" valor={textos[0]} aoMudar={(v) => mudar(0, v)} bloqueado={bloqueado} visual={visual} linhas={3} />
      </Enunciado>
    );
  }

  if (ex.tipo === "LISTENING") {
    return (
      <Enunciado titulo={ex.pergunta || "Escreva o que ouve"}>
        {ex.audio ? <OuvirGrande src={ex.audio} /> : <Aviso tom="realce">O áudio deste exercício ainda não está disponível. Avise o professor do curso.</Aviso>}
        <CampoResposta rotulo="O que ouviu" valor={textos[0]} aoMudar={(v) => mudar(0, v)} bloqueado={bloqueado} visual={visual} linhas={2} placeholder="Escreva a frase em inglês" />
      </Enunciado>
    );
  }

  // FILL_BLANK sem alternativas: a frase com os espaços numerados e um campo por espaço.
  const partes = ex.pergunta.split(ESPACO);
  return (
    <Enunciado titulo={ex.instrucao || "Complete a frase"}>
      <BalaoEnunciado depois={ex.audio ? <BotaoOuvir src={ex.audio} sobreMarca /> : null}>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 34 }}>
          {partes.map((p, i) => (
            <Texto key={i} cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 34 }}>
              {p}
              {i < partes.length - 1 ? (
                <Texto forte style={{ fontSize: 20, lineHeight: 34, backgroundColor: cor.realce }}>
                  {textos[i]?.trim() ? ` ${textos[i].trim()} ` : n > 1 ? ` (${i + 1})    ` : " ".repeat(12)}
                </Texto>
              ) : null}
            </Texto>
          ))}
        </Texto>
      </BalaoEnunciado>
      {Array.from({ length: n }, (_, i) => (
        <CampoResposta key={i} rotulo={n > 1 ? `Espaço ${i + 1}` : "A palavra em falta"} valor={textos[i] ?? ""} aoMudar={(v) => mudar(i, v)} bloqueado={bloqueado} visual={visual} />
      ))}
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Ordenar a frase                                                      */
/* ------------------------------------------------------------------ */
function Ordenar({ ex, bloqueado, visual, aoMudar }: Props) {
  const palavras = ex.palavras ?? [];
  const [ordem, setOrdem] = useState<string[]>([]);
  const textoDe = (id: string) => palavras.find((p) => p.id === id)?.texto ?? "";
  const actualizar = (novo: string[]) => {
    setOrdem(novo);
    aoMudar(novo.length === palavras.length ? { tipo: "texto", resposta: { ordered_options: novo } } : null);
  };
  return (
    <Enunciado titulo={ex.instrucao || "Ponha as palavras por ordem"}>
      <EmPortugues texto={ex.pergunta} />
      <View style={{ gap: 8 }}>
        <Texto v="legenda" forte suave>
          A sua frase
        </Texto>
        <View
          accessibilityLabel="A sua frase"
          accessibilityLiveRegion="polite"
          style={{
            minHeight: 124,
            flexDirection: "row",
            flexWrap: "wrap",
            alignContent: "flex-start",
            gap: 8,
            padding: 12,
            borderWidth: 2,
            borderStyle: "dashed",
            borderRadius: raio.md,
            borderColor: corBorda(visual),
            backgroundColor: visual === "certo" ? cor.certoSuave : visual === "errado" ? cor.erradoSuave : cor.fundo,
          }}
        >
          {ordem.length === 0 ? (
            <Texto v="legenda" suave style={{ lineHeight: 44 }}>
              Toque nas palavras em baixo.
            </Texto>
          ) : null}
          {ordem.map((id, i) => (
            <Palavra key={id} marca texto={textoDe(id)} rotulo={`Tirar ${textoDe(id)}`} disabled={bloqueado} onPress={() => actualizar(ordem.filter((_, j) => j !== i))} />
          ))}
        </View>
      </View>
      <View style={{ gap: 8 }}>
        <Texto v="legenda" forte suave>
          Palavras
        </Texto>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {palavras.map((p) => (
            <Palavra key={p.id} texto={p.texto} usada={ordem.includes(p.id)} disabled={bloqueado} onPress={() => actualizar([...ordem, p.id])} />
          ))}
        </View>
      </View>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Ligar pares                                                          */
/* ------------------------------------------------------------------ */
function BotaoPar({ texto, ligado, escolhido, n, onPress, rotulo, bloqueado, visual }: { texto: string; ligado: boolean; escolhido: boolean; n: number; onPress: () => void; rotulo: string; bloqueado: boolean; visual: Visual }) {
  const corPar = visual === "certo" ? { borderColor: cor.certo, backgroundColor: cor.certoSuave } : visual === "errado" ? { borderColor: cor.errado, backgroundColor: cor.erradoSuave } : { borderColor: cor.certoSuave, backgroundColor: cor.certoSuave };
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      accessibilityState={{ selected: escolhido, disabled: bloqueado }}
      disabled={bloqueado}
      onPress={onPress}
      style={({ pressed }) => [
        { minHeight: 56, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 2, borderRadius: raio.sm, flexDirection: "row", alignItems: "center", gap: 6 },
        ligado ? corPar : escolhido ? { borderColor: cor.azulMarca, backgroundColor: cor.fundoSuave } : { borderColor: cor.linhaForte, backgroundColor: pressed ? cor.fundoSuave : cor.fundo },
      ]}
    >
      <Texto forte={ligado || escolhido} cor={ligado && visual === "livre" ? cor.certo : cor.tinta} style={{ flex: 1, fontSize: 17, lineHeight: 24 }}>
        {texto}
      </Texto>
      {ligado ? (
        <Texto v="legenda" suave numeros>
          {n}
        </Texto>
      ) : null}
    </Pressable>
  );
}

function Pares({ ex, bloqueado, visual, aoMudar }: Props) {
  const esquerda = ex.esquerda ?? [];
  const direita = ex.direita ?? [];
  const [pares, setPares] = useState<Record<string, string>>({});
  const [aberto, setAberto] = useState<string | null>(null);
  const usados = useMemo(() => new Set(Object.values(pares)), [pares]);

  const actualizar = (novo: Record<string, string>) => {
    setPares(novo);
    aoMudar(Object.keys(novo).length === esquerda.length ? { tipo: "texto", resposta: { paired_options: novo } } : null);
  };
  const tocarEsquerda = (id: string) => {
    if (bloqueado) return;
    if (pares[id]) {
      const resto = { ...pares };
      delete resto[id];
      actualizar(resto);
      return;
    }
    setAberto(aberto === id ? null : id);
  };
  const tocarDireita = (texto: string) => {
    if (bloqueado) return;
    const ligadoA = Object.entries(pares).find(([, v]) => v === texto)?.[0];
    if (ligadoA && !aberto) {
      // Tocar numa tradução já ligada desfaz o par.
      const resto = { ...pares };
      delete resto[ligadoA];
      actualizar(resto);
      return;
    }
    if (!aberto || usados.has(texto)) return;
    actualizar({ ...pares, [aberto]: texto });
    setAberto(null);
  };
  const numeroDoPar = (id: string) => Object.keys(pares).indexOf(id) + 1;
  const parDaDireita = (t: string) => Object.entries(pares).find(([, v]) => v === t)?.[0];
  const ligados = Object.keys(pares).length;
  return (
    <Enunciado titulo={ex.pergunta || "Ligue cada palavra à tradução"}>
      <Texto v="legenda" suave style={{ marginTop: -12, fontSize: 15, lineHeight: 22 }}>
        {ligados} de {esquerda.length} pares ligados. Toque numa palavra e depois na tradução.
      </Texto>
      <View style={{ flexDirection: "row", gap: 16 }}>
        <View style={{ flex: 1, gap: 12 }}>
          <Texto v="legenda" forte suave>
            Inglês
          </Texto>
          {esquerda.map((e) => (
            <BotaoPar
              key={e.id}
              bloqueado={bloqueado}
              visual={visual}
              texto={e.texto}
              ligado={!!pares[e.id]}
              escolhido={aberto === e.id}
              n={numeroDoPar(e.id)}
              onPress={() => tocarEsquerda(e.id)}
              rotulo={pares[e.id] ? `${e.texto}, ligado a ${pares[e.id]}. Tocar para desfazer` : e.texto}
            />
          ))}
        </View>
        <View style={{ flex: 1, gap: 12 }}>
          <Texto v="legenda" forte suave>
            Português
          </Texto>
          {direita.map((d) => {
            const lig = parDaDireita(d);
            return <BotaoPar key={d} bloqueado={bloqueado} visual={visual} texto={d} ligado={!!lig} escolhido={false} n={lig ? numeroDoPar(lig) : 0} onPress={() => tocarDireita(d)} rotulo={lig ? `${d}, ligado` : d} />;
          })}
        </View>
      </View>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Falar: grava a frase e envia para análise de pronúncia               */
/* ------------------------------------------------------------------ */
const soLetras = (t: string) => t.toLowerCase().replace(/[^a-z0-9']/g, "");

function ResultadoPronuncia({ frase, fala }: { frase: string; fala: ResultadoFala }) {
  const marcar = new Set(fala.palavras.flatMap((p) => p.split(/\s+/)).map(soLetras).filter(Boolean));
  const partes = frase.split(/\s+/).filter(Boolean);
  return (
    <View accessibilityLabel="Resultado da sua pronúncia" style={{ gap: 12, alignSelf: "stretch" }}>
      <View style={{ flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          O que percebemos
        </Texto>
        <Texto v="rotulo" numeros cor={fala.nota >= 70 ? cor.certo : cor.tinta}>
          {Math.round(fala.nota)} de 100
        </Texto>
      </View>
      <AvisoAnaliseAproximada fonte={fala.fonte} />
      {fala.detalhe ? (
        <PalavrasComNota detalhe={fala.detalhe} />
      ) : (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {partes.map((p, i) => {
            const mal = marcar.has(soLetras(p));
            return (
              <View key={`${p}-${i}`} accessible accessibilityLabel={mal ? `${p}, a treinar` : p} style={{ backgroundColor: mal ? cor.realceSuave : cor.certoSuave, paddingHorizontal: 10, paddingVertical: 2, borderRadius: raio.sm }}>
                <Texto forte={mal} style={{ fontSize: 19, lineHeight: 28, textDecorationLine: mal ? "underline" : "none", textDecorationStyle: "dotted" }}>
                  {p}
                </Texto>
              </View>
            );
          })}
        </View>
      )}
      {fala.mensagem ? <Dica texto={fala.mensagem} /> : null}
    </View>
  );
}

function Falar({ ex, bloqueado, aoMudar, fala }: Props) {
  const g = useGravador((gr) => aoMudar(gr ? { tipo: "audio", gravacao: gr } : null));
  const frase = ex.frase ?? ex.pergunta ?? "";
  return (
    <Enunciado titulo={ex.instrucao || "Diga esta frase em voz alta"}>
      <BalaoEnunciado
        style={{ alignSelf: "stretch" }}
        depois={ex.audio ? <BotaoOuvir src={ex.audio} rotulo="Ouvir o modelo" sobreMarca /> : frase ? <BotaoOuvirTexto texto={frase} rotulo="Ouvir o modelo" sobreMarca /> : null}
      >
        <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.voz, fontSize: 24, lineHeight: 34 }}>
          {frase}
        </Texto>
      </BalaoEnunciado>
      {fala ? <ResultadoPronuncia frase={frase} fala={fala} /> : null}
      <View style={{ paddingTop: 4 }}>
        <BotaoGravar g={g} bloqueado={bloqueado} />
      </View>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Responder: ouvir uma pergunta de trabalho e responder em voz alta    */
/* ------------------------------------------------------------------ */
const VEREDICTO = { sim: "Respondeu à pergunta", parcial: "Respondeu em parte", nao: "Ainda não respondeu à pergunta" } as const;

function AvaliacaoResposta({ a }: { a: ResultadoResponder }) {
  const linhas: [boolean, string][] = [
    [a.responde !== "nao", VEREDICTO[a.responde]],
    [a.usou_frase, a.usou_frase ? "Usou a frase" : "Ainda não usou a frase"],
  ];
  return (
    <View style={{ alignSelf: "stretch", gap: 12, backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 14 }}>
      <View style={{ gap: 2 }}>
        <Texto v="legenda" suave>
          Ouvimos
        </Texto>
        <Texto style={{ fontFamily: fonte.textoItalico, fontSize: 17, lineHeight: 26 }}>{a.transcricao}</Texto>
      </View>
      <View style={{ gap: 4 }}>
        {linhas.map(([ok, texto]) => (
          <View key={texto} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: ok ? cor.certo : cor.errado }} />
            <Texto forte style={{ fontSize: 15, lineHeight: 22 }}>
              {texto}
            </Texto>
          </View>
        ))}
      </View>
      {a.correccao ? (
        <View style={{ gap: 2 }}>
          <Texto style={{ lineHeight: 24 }}>
            <Texto suave style={{ textDecorationLine: "line-through" }}>
              {a.correccao.disse}
            </Texto>{" "}
            <Texto forte>{a.correccao.certo}</Texto>
          </Texto>
          <Texto v="legenda" suave>
            {a.correccao.porque}
          </Texto>
        </View>
      ) : null}
      {a.comentario ? <Texto style={{ fontSize: 15, lineHeight: 22 }}>{a.comentario}</Texto> : null}
      {a.exemplo ? (
        <View style={{ gap: 2, borderTopWidth: 1, borderColor: cor.linha, paddingTop: 10 }}>
          <Texto v="legenda" suave>
            Uma resposta possível
          </Texto>
          <Texto style={{ lineHeight: 24 }}>{a.exemplo}</Texto>
          <BotaoOuvirTexto texto={a.exemplo} rotulo="Ouvir" />
        </View>
      ) : null}
    </View>
  );
}

function Responder({ ex, bloqueado, aoMudar, avaliacao }: Props) {
  const g = useGravador((gr) => aoMudar(gr ? { tipo: "audio", gravacao: gr } : null));
  return (
    <Enunciado titulo="Responda em voz alta">
      {ex.contexto ? (
        <Texto suave style={{ marginTop: -8 }}>
          {ex.contexto}
        </Texto>
      ) : null}
      <BalaoEnunciado depois={<BotaoOuvirTexto texto={ex.pergunta} rotulo="Ouvir a pergunta" textoATocar="A ler a pergunta" sobreMarca />}>{ex.pergunta}</BalaoEnunciado>
      {ex.frase ? (
        <View style={{ borderLeftWidth: 4, borderColor: cor.realce, paddingLeft: 16, gap: 2 }}>
          <Texto v="legenda" suave>
            Use esta frase na resposta
          </Texto>
          <Texto style={{ fontFamily: fonte.tituloMedio, fontSize: 19, lineHeight: 28 }}>{ex.frase}</Texto>
        </View>
      ) : null}
      {avaliacao ? <AvaliacaoResposta a={avaliacao} /> : null}
      <BotaoGravar g={g} bloqueado={bloqueado} />
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Indisponíveis: o aluno salta sem perder nada.                        */
/* ------------------------------------------------------------------ */
function Indisponivel({ ex }: Props) {
  const textos = {
    conversa: ["Conversa com o tutor", "Esta conversa ainda não está pronta. Pode continuar: este exercício não conta pontos nem tira vidas."],
    incompleto: ["Responder em voz alta", "Este exercício ainda não está pronto. Pode continuar: não conta pontos nem tira vidas."],
    sem_audio: ["Exercício de escuta", "Este exercício de escuta ainda não tem áudio. Pode continuar: não conta pontos nem tira vidas."],
  } as const;
  const [titulo, texto] = textos[ex.motivo ?? "sem_audio"];
  return (
    <Enunciado titulo={titulo}>
      <View style={{ flexDirection: "row", gap: 10, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
        <CheckCircle2 size={22} color={cor.tintaSuave} />
        <Texto suave style={{ flex: 1 }}>
          {texto}
        </Texto>
      </View>
    </Enunciado>
  );
}

/** Exercícios que o aluno salta (sem pontos, sem vidas) em vez de responder. */
export function seSalta(ex: Exercicio) {
  return ex.modo === "indisponivel";
}

export function ExercicioUI(props: Props) {
  switch (props.ex.modo) {
    case "escolha":
      return <Escolha {...props} />;
    case "banco":
      return <Banco {...props} />;
    case "escrever":
      return <Escrever {...props} />;
    case "ordenar":
      return <Ordenar {...props} />;
    case "pares":
      return <Pares {...props} />;
    case "falar":
      return <Falar {...props} />;
    case "responder":
      return <Responder {...props} />;
    case "conversa":
      return (
        <ConversaCurta
          ex={{ id: props.ex.id, pergunta: props.ex.pergunta, frases: props.ex.frases }}
          bloqueado={props.bloqueado}
          aoMudar={props.aoMudar}
          aoSaltar={props.aoSaltar}
        />
      );
    default:
      return <Indisponivel {...props} />;
  }
}
