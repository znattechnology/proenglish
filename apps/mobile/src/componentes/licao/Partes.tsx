/**
 * Peças do ecrã da lição e da revisão (apps/web/components/pe/licao/Partes.tsx), com o visual das telas
 * Licao*.dc.html: cabeçalho com sair/progresso/vidas, enunciado, balão, e o rodapé verificar/certo/errado.
 */
import { CheckCircle2, X, XCircle } from "lucide-react-native";
import type { ReactNode } from "react";
import { View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { DetalhePronuncia } from "@/dominios/laboratorio/api";
import { balao, cor, fonte, raio } from "@/tema";
import { BarraProgresso, Botao, BotaoIcone, Texto, Titulo, Vidas } from "@/ui";

export type Visual = "livre" | "certo" | "errado";

/** Cabeçalho: X para sair, barra de progresso e vidas (null = não mostra). */
export function CabecalhoLicao({ feitos, total, vidas, ilimitadas, aoSair, rotuloSair = "Sair da lição", contador }: { feitos: number; total: number; vidas: number | null; ilimitadas?: boolean; aoSair: () => void; rotuloSair?: string; contador?: boolean }) {
  const pct = total ? (100 * feitos) / total : 0;
  const n = Math.min(feitos + 1, total);
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12 }}>
      <BotaoIcone rotulo={rotuloSair} onPress={aoSair}>
        <X size={26} color={cor.tinta} />
      </BotaoIcone>
      <View style={{ flex: 1 }}>
        <BarraProgresso valor={pct} rotulo={`Exercício ${n} de ${total}`} altura={10} />
      </View>
      {contador ? (
        <Texto v="legenda" suave numeros>
          {n} de {total}
        </Texto>
      ) : null}
      {vidas !== null ? <Vidas quantas={vidas} ilimitadas={ilimitadas} /> : null}
    </View>
  );
}

/** Título do exercício e o conteúdo por baixo. */
export function Enunciado({ titulo, children, antes }: { titulo: string; children?: ReactNode; antes?: ReactNode }) {
  return (
    <View style={{ gap: 20 }}>
      <View style={{ gap: 4 }}>
        {antes}
        <Titulo v="tituloM">{titulo}</Titulo>
      </View>
      {children}
    </View>
  );
}

/** O balão azul-marca com a frase (e, por baixo, ouvir). */
export function BalaoEnunciado({ autor, children, depois, style }: { autor?: string | null; children: ReactNode; depois?: ReactNode; style?: ViewStyle }) {
  return (
    <View style={[balao.grande, { alignSelf: "flex-start", maxWidth: "100%", backgroundColor: cor.azulMarca, paddingVertical: 18, paddingHorizontal: 22, gap: 6 }, style]}>
      {autor ? (
        <Texto v="legenda" forte cor={cor.sobreMarca}>
          {autor}
        </Texto>
      ) : null}
      {typeof children === "string" ? (
        <Texto cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 30 }}>
          {children}
        </Texto>
      ) : (
        children
      )}
      {depois}
    </View>
  );
}

/** Caixa "Em português" (tradução, ordenar). */
export function EmPortugues({ texto, rotulo = "Em português" }: { texto: string; rotulo?: string }) {
  return (
    <View style={{ backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingVertical: 16, paddingHorizontal: 20, gap: 4 }}>
      <Texto v="legenda" forte suave>
        {rotulo}
      </Texto>
      <Texto style={{ fontSize: 19, lineHeight: 28 }}>{texto}</Texto>
    </View>
  );
}

/** Estilo de uma opção conforme esteja escolhida, certa ou errada (cores do canvas). */
export function estiloOpcao(escolhida: boolean, visual: Visual): ViewStyle {
  if (escolhida && visual === "certo") return { borderWidth: 2, borderColor: cor.certo, backgroundColor: cor.certoSuave };
  if (escolhida && visual === "errado") return { borderWidth: 2, borderColor: cor.errado, backgroundColor: cor.erradoSuave };
  if (escolhida) return { borderWidth: 2, borderColor: cor.azulMarca, backgroundColor: cor.fundoSuave };
  return { borderWidth: 2, borderColor: cor.linhaForte, backgroundColor: cor.fundo };
}

export function corBorda(visual: Visual, normal: string = cor.linhaForte) {
  return visual === "certo" ? cor.certo : visual === "errado" ? cor.errado : normal;
}

/** A frase com cada palavra pela sua nota: verde (bem), amarelo (quase), vermelho (a treinar). */
export function PalavrasComNota({ detalhe }: { detalhe: DetalhePronuncia }) {
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {detalhe.palavras.map((p, i) => {
          const omitida = p.erro_tipo === "Omission";
          const n = p.nota;
          const f = omitida || (n !== null && n < 60) ? cor.erradoSuave : n !== null && n < 80 ? cor.realceSuave : n !== null ? cor.certoSuave : cor.fundoSuave;
          const texto = omitida ? "não se ouviu" : n === null ? "" : n >= 80 ? `${n} de 100, bem` : n >= 60 ? `${n} de 100, quase` : `${n} de 100, a treinar`;
          return (
            <View key={`${p.palavra}-${i}`} accessible accessibilityLabel={texto ? `${p.palavra}, ${texto}` : p.palavra} style={{ backgroundColor: f, paddingHorizontal: 10, paddingVertical: 2, borderRadius: raio.sm }}>
              <Texto
                style={{ fontSize: 19, lineHeight: 28, textDecorationLine: omitida ? "line-through" : n !== null && n < 80 ? "underline" : "none" }}
                forte={n !== null && n < 80}
              >
                {p.palavra}
              </Texto>
            </View>
          );
        })}
      </View>
      <Texto v="mini" suave importantForAccessibility="no">
        Verde: bem. Amarelo: quase. Vermelho: a treinar.
      </Texto>
      {detalhe.dica ? <Dica texto={detalhe.dica} /> : null}
    </View>
  );
}

/** Caixa amarela de dica (tela LicaoFala). */
export function Dica({ texto }: { texto: string }) {
  return (
    <View style={{ backgroundColor: cor.realceSuave, borderRadius: raio.md, paddingVertical: 12, paddingHorizontal: 16 }}>
      <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
        {texto}
      </Texto>
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Rodapé: verificar, ou o resultado (certo/errado) e continuar.       */
/* ------------------------------------------------------------------ */
export type EstadoRodape =
  | { tipo: "verificar"; pronto: boolean; aVerificar: boolean }
  | { tipo: "certo"; explicacao?: string | null }
  | { tipo: "errado"; dica?: string | null; perdeuVida: boolean; solucao?: string | null; explicacao?: string | null; repetir?: boolean; falado?: boolean };

export function RodapeLicao({
  estado,
  aoVerificar,
  aoContinuar,
  aoTentarOutraVez,
  textoContinuar = "Continuar",
  textoVerificar = "Verificar",
  textoPorResponder,
}: {
  estado: EstadoRodape;
  aoVerificar: () => void;
  aoContinuar: () => void;
  aoTentarOutraVez: () => void;
  textoContinuar?: string;
  textoVerificar?: string;
  /** Texto do botão desactivado antes de haver resposta (ex.: "Ligue todos os pares"). */
  textoPorResponder?: string;
}) {
  const certo = estado.tipo === "certo";
  const errado = estado.tipo === "errado";
  return (
    <Rodape tom={certo ? "certo" : errado ? "errado" : null}>
      {estado.tipo === "certo" || estado.tipo === "errado" ? (
        <Resultado
          certo={certo}
          titulo={certo ? "Certo" : estado.tipo === "errado" && estado.perdeuVida ? "Ainda não. Perdeu uma vida" : "Ainda não"}
        >
          {certo && estado.explicacao ? <Linha>{estado.explicacao}</Linha> : null}
          {estado.tipo === "errado" ? (
            <>
              {estado.solucao ? (
                <Texto style={{ fontSize: 15, lineHeight: 22 }}>
                  Resposta certa: <Texto forte style={{ fontSize: 15, lineHeight: 22 }}>{estado.solucao}</Texto>
                </Texto>
              ) : null}
              {estado.explicacao ? <Linha>{estado.explicacao}</Linha> : null}
              {estado.dica && !estado.solucao ? <Linha>{estado.dica}</Linha> : null}
              {!estado.repetir ? (
                <Texto v="legenda" suave>
                  {estado.falado ? "A falar não perde vidas. Este exercício volta no fim da lição e entra na sua revisão." : "Este exercício volta no fim da lição."}
                </Texto>
              ) : null}
            </>
          ) : null}
        </Resultado>
      ) : null}
      {estado.tipo === "verificar" ? (
        <Botao larguraTotal disabled={!estado.pronto || estado.aVerificar} carregando={estado.aVerificar} onPress={aoVerificar}>
          {estado.aVerificar ? "A verificar…" : !estado.pronto && textoPorResponder ? textoPorResponder : textoVerificar}
        </Botao>
      ) : certo || (estado.tipo === "errado" && !estado.repetir) ? (
        <Botao larguraTotal onPress={aoContinuar}>
          {textoContinuar}
        </Botao>
      ) : (
        <Botao larguraTotal onPress={aoTentarOutraVez}>
          Tentar outra vez
        </Botao>
      )}
    </Rodape>
  );
}

export function Linha({ children }: { children: ReactNode }) {
  return <Texto style={{ fontSize: 15, lineHeight: 22 }}>{children}</Texto>;
}

/** A faixa colorida do resultado (verde/vermelha) com o ícone e o título. */
export function Resultado({ certo, titulo, children }: { certo: boolean; titulo: string; children?: ReactNode }) {
  const c = certo ? cor.certo : cor.errado;
  return (
    <View accessibilityRole="alert" accessibilityLiveRegion="assertive" style={{ flexDirection: "row", gap: 10 }}>
      {certo ? <CheckCircle2 size={26} color={c} /> : <XCircle size={26} color={c} />}
      <View style={{ flex: 1, gap: 4 }}>
        <Texto cor={c} style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 24 }}>
          {titulo}
        </Texto>
        {children}
      </View>
    </View>
  );
}

/** Rodapé fixo da lição: branco com linha, verde depois de acertar, vermelho depois de errar. */
export function Rodape({ tom, children }: { tom: "certo" | "errado" | null; children: ReactNode }) {
  const ins = useSafeAreaInsets();
  return (
    <View
      style={{
        backgroundColor: tom === "certo" ? cor.certoSuave : tom === "errado" ? cor.erradoSuave : cor.fundo,
        borderTopWidth: tom ? 0 : 1,
        borderColor: cor.linha,
        paddingHorizontal: 20,
        paddingTop: tom ? 16 : 12,
        paddingBottom: Math.max(ins.bottom, 16),
        gap: 14,
      }}
    >
      {children}
    </View>
  );
}
