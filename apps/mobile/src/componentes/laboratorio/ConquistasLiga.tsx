/**
 * Liga semanal, competições e conquistas (tela ConquistasMovel; web user/laboratory/achievements).
 * Duas abas: Liga e Conquistas. /liga abre na Liga, /conquistas nas Conquistas.
 */
import { Award, ChevronDown, ChevronUp, Lock, Medal } from "lucide-react-native";
import { useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { useLabConquistasQuery, useLabLigaQuery, type Competicao, type Conquista, type Liga, type PremioGanho } from "@/dominios/conquistas/api";
import { fmt } from "@/dominios/laboratorio/api";
import { voltarAoTrilho } from "@/componentes/licao/Jogador";
import { balao, cor, fonte, raio } from "@/tema";
import { ACarregar, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Etiqueta, Texto } from "@/ui";

type Aba = "liga" | "conquistas";

export function ConquistasLiga({ abaInicial }: { abaInicial: Aba }) {
  const [aba, setAba] = useState<Aba>(abaInicial);
  const conquistas = useLabConquistasQuery();
  const liga = useLabLigaQuery();
  const q = aba === "liga" ? liga : conquistas;

  return (
    <Ecra
      cabecalho={
        <View style={{ borderBottomWidth: 1, borderColor: cor.linha }}>
          <Cabecalho titulo="Liga e conquistas" linha={false} />
          <View accessibilityRole="tablist" style={{ flexDirection: "row", paddingHorizontal: 16 }}>
            {(
              [
                ["liga", "Liga"],
                ["conquistas", "Conquistas"],
              ] as const
            ).map(([valor, nome]) => {
              const activa = aba === valor;
              return (
                <Pressable
                  key={valor}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: activa }}
                  onPress={() => setAba(valor)}
                  style={{ flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center", borderBottomWidth: 3, borderColor: activa ? cor.azulMarca : "transparent" }}
                >
                  <Texto forte={activa} cor={activa ? cor.azulMarca : cor.tintaSuave}>
                    {nome}
                  </Texto>
                </Pressable>
              );
            })}
          </View>
        </View>
      }
      aoActualizar={() => void q.refetch()}
      aActualizar={q.isFetching && !q.isLoading}
      style={{ gap: 14 }}
    >
      {aba === "liga" ? (
        liga.isError ? (
          <EstadoErro erro={liga.error} titulo="Não conseguimos carregar a liga" aoTentar={() => void liga.refetch()} />
        ) : !liga.data ? (
          <ACarregar linhas={6} altura={56} />
        ) : (
          <TabelaLiga l={liga.data} />
        )
      ) : conquistas.isError ? (
        <EstadoErro erro={conquistas.error} titulo="Não conseguimos carregar as conquistas" aoTentar={() => void conquistas.refetch()} />
      ) : !conquistas.data ? (
        <ACarregar linhas={5} altura={72} />
      ) : conquistas.data.length === 0 ? (
        <EstadoVazio titulo="Ainda não há conquistas" texto="Faça lições e converse com o tutor: as conquistas aparecem aqui." accao={<Botao onPress={voltarAoTrilho}>Praticar uma lição</Botao>} />
      ) : (
        <ListaConquistas lista={conquistas.data} />
      )}
    </Ecra>
  );
}

function iniciais(nome: string) {
  const p = nome.replace(/\(.*\)/, "").trim().split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? (p[p.length - 1][0] ?? "") : "")).toUpperCase();
}

function TabelaLiga({ l }: { l: Liga }) {
  const dias = Math.floor(l.semana.segundos_ate_fim / 86_400);
  const horas = Math.floor((l.semana.segundos_ate_fim % 86_400) / 3_600);
  const termina = dias ? `termina daqui a ${dias} ${dias === 1 ? "dia" : "dias"}` : `termina daqui a ${horas} h`;
  const falta = l.eu.pontos_para_lugar_acima ? `Faltam-lhe ${fmt(l.eu.pontos_para_lugar_acima)} pontos para subir um lugar.` : l.eu.posicao === 1 ? "Está em 1.º lugar esta semana." : "";
  const temCompeticoes = !!(l.competicoes?.length || l.competicoes_terminadas?.length || l.premios?.length);
  return (
    <>
      <View style={[balao.grande, { borderTopLeftRadius: 24, borderTopRightRadius: 24, borderBottomRightRadius: 24, backgroundColor: cor.azulMarca, paddingHorizontal: 20, paddingVertical: 18, gap: 4 }]}>
        <Texto accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 20, lineHeight: 26 }}>
          {l.liga.nome}
        </Texto>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          {`Está em ${l.eu.posicao}.º lugar. ${falta} ${l.regra_promocao.descricao}`.replace(/\s+/g, " ").trim()}
        </Texto>
      </View>
      <Texto v="legenda" suave>
        Pontos desta semana, que {termina}.
      </Texto>
      <View>
        {l.ranking.map((j) => (
          <View
            key={`${j.posicao}-${j.nome}`}
            accessible
            accessibilityLabel={`${j.posicao}.º lugar, ${j.sou_eu ? "você" : j.nome}, ${fmt(j.pontos_semana)} pontos`}
            style={{ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 56, paddingHorizontal: 8, paddingVertical: 4, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: j.sou_eu ? cor.realceSuave : undefined, borderRadius: j.sou_eu ? raio.sm : 0 }}
          >
            <Texto forte numeros centro style={{ width: 32 }}>
              {j.posicao}.º
            </Texto>
            <View style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte, borderTopLeftRadius: 12, borderTopRightRadius: 12, borderBottomRightRadius: 12 }}>
              <Texto v="mini" forte>
                {iniciais(j.nome)}
              </Texto>
            </View>
            <Texto forte={j.sou_eu} numberOfLines={1} style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
              {j.sou_eu ? `${j.nome} (você)` : j.nome}
            </Texto>
            <Texto forte numeros style={{ fontSize: 15, lineHeight: 22 }}>
              {fmt(j.pontos_semana)}
            </Texto>
          </View>
        ))}
      </View>
      {l.regra_promocao.proxima_liga && l.regra_promocao.pontos_em_falta !== null ? (
        <View style={{ gap: 6 }}>
          <Texto v="legenda" suave>
            {`Faltam ${fmt(l.regra_promocao.pontos_em_falta)} pontos para a ${l.regra_promocao.proxima_liga.nome}.`}
          </Texto>
          <BarraProgresso
            valor={(100 * (l.eu.pontos_totais - l.liga.pontos_minimos)) / Math.max(1, l.regra_promocao.proxima_liga.pontos_minimos - l.liga.pontos_minimos)}
            rotulo={`Pontos até à ${l.regra_promocao.proxima_liga.nome}`}
            corBarra={cor.realce}
          />
        </View>
      ) : null}
      <View style={{ gap: 10, paddingTop: 4 }}>
        <Botao larguraTotal tamanho="medio" onPress={voltarAoTrilho}>
          Praticar uma lição
        </Botao>
        <Botao larguraTotal tamanho="medio" tipo="secundario" href="/conversa">
          Conversar com o tutor
        </Botao>
      </View>
      {temCompeticoes ? <Competicoes actuais={l.competicoes ?? []} terminadas={l.competicoes_terminadas ?? []} premios={l.premios ?? []} /> : null}
    </>
  );
}

function ListaConquistas({ lista }: { lista: Conquista[] }) {
  const ganhas = lista.filter((c) => c.isUnlocked).length;
  const ordenadas = [...lista].sort((a, b) => Number(b.isUnlocked) - Number(a.isUnlocked) || (b.progress?.percentage ?? 0) - (a.progress?.percentage ?? 0));
  return (
    <View style={{ gap: 10 }}>
      <Texto suave style={{ fontSize: 15 }}>
        {ganhas} de {lista.length} conquistas
      </Texto>
      {ordenadas.map((c) => {
        const sigla = c.icon && !/^[\p{L}\p{N}]/u.test(c.icon) ? c.icon : c.title.slice(0, 2);
        return (
          <View
            key={c.id}
            accessible
            accessibilityLabel={`${c.title}. ${c.description}. ${c.isUnlocked ? "Conquistada" : c.progress ? `${fmt(c.progress.current)} de ${fmt(c.progress.target)}` : "Por conquistar"}`}
            style={{ flexDirection: "row", gap: 12, padding: 12, borderRadius: raio.md, borderWidth: 1, borderColor: c.isUnlocked ? cor.linha : cor.fundoSuave, backgroundColor: c.isUnlocked ? cor.fundo : cor.fundoSuave }}
          >
            <View style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center", borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomRightRadius: 14, backgroundColor: c.isUnlocked ? cor.azulMarca : cor.fundoForte }}>
              {c.isUnlocked ? (
                <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 15, lineHeight: 20 }}>
                  {sigla}
                </Texto>
              ) : (
                <Lock size={20} color={cor.tintaSuave} />
              )}
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <Texto forte style={{ lineHeight: 22 }}>
                {c.title}
              </Texto>
              <Texto v="legenda" suave>
                {c.description}
              </Texto>
              {c.isUnlocked ? (
                <Texto v="legenda" forte cor={cor.certo}>
                  {`Conquistada ${c.unlockedAt ?? ""}`.trim()}
                </Texto>
              ) : c.progress ? (
                <View style={{ gap: 6, paddingTop: 4 }}>
                  <Texto v="legenda" forte numeros>
                    {fmt(c.progress.current)} de {fmt(c.progress.target)}
                    {c.progress.unit ? ` ${c.progress.unit}` : ""}
                  </Texto>
                  <BarraProgresso valor={c.progress.percentage} rotulo={`Progresso em ${c.title}`} />
                </View>
              ) : (
                <Texto v="legenda" forte>
                  Por conquistar
                </Texto>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Competições (apps/web/components/pe/estatisticas/Competicoes.tsx)   */
/* ------------------------------------------------------------------ */
const dia = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
};
const PREMIO_CURTO: Record<string, string> = { certificado_merito: "um certificado de mérito", medalha: "uma medalha", plano: "um mês de plano" };
function unidade(c: { unidade: string }, n: number) {
  if (n !== 1) return c.unidade;
  return ({ lições: "lição", pontos: "ponto", minutos: "minuto", dias: "dia" } as Record<string, string>)[c.unidade] ?? c.unidade;
}
function listaCursos(cursos: { titulo: string }[]) {
  const t = cursos.map((c) => `«${c.titulo}»`);
  return t.length <= 1 ? t.join("") : `${t.slice(0, -1).join(", ")} e ${t[t.length - 1]}`;
}
function quando(c: Competicao) {
  if (c.estado === "agendada") return `Começa a ${dia(c.inicio)}`;
  const n = c.dias_restantes ?? 0;
  return n <= 1 ? "Termina hoje" : `Faltam ${n} dias`;
}

function Competicoes({ actuais, terminadas, premios }: { actuais: Competicao[]; terminadas: Competicao[]; premios: PremioGanho[] }) {
  const [verTerminadas, setVerTerminadas] = useState(false);
  return (
    <View style={{ gap: 14, borderTopWidth: 1, borderColor: cor.linha, paddingTop: 20, marginTop: 6 }}>
      <View style={{ gap: 2 }}>
        <Texto v="tituloS" accessibilityRole="header">
          Competições
        </Texto>
        <Texto v="legenda" suave>
          Participa automaticamente nas competições dos seus cursos.
        </Texto>
      </View>
      {actuais.map((c) => (
        <View key={c.id} style={{ gap: 10, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 16 }}>
          <View style={{ gap: 6 }}>
            <Texto forte style={{ fontSize: 17, lineHeight: 24 }}>
              {c.nome}
            </Texto>
            <Etiqueta tom={c.estado === "activa" && (c.dias_restantes ?? 0) <= 1 ? "realce" : "neutro"}>{quando(c)}</Etiqueta>
          </View>
          <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
            {`Conta ${c.conta_nome.toLowerCase()}, de ${dia(c.inicio)} a ${dia(c.fim)}${c.cursos?.length ? `, no${c.cursos.length > 1 ? "s cursos" : " curso"} ${listaCursos(c.cursos)}` : ""}. Prémio para ${c.premio_lugares === 1 ? "o 1.º lugar" : `os ${c.premio_lugares} primeiros`}: ${PREMIO_CURTO[c.premio] ?? c.premio_nome.toLowerCase()}.`}
          </Texto>
          {c.estado === "activa" ? (
            c.meu_lugar ? (
              <Texto style={{ fontSize: 15, lineHeight: 22 }}>
                <Texto numeros style={{ fontFamily: fonte.titulo, fontSize: 22, lineHeight: 30 }}>
                  {c.meu_lugar}.º lugar{" "}
                </Texto>
                <Texto suave style={{ fontSize: 15, lineHeight: 22 }}>
                  {`com ${fmt(c.meu_valor)} ${unidade(c, c.meu_valor)}, entre ${c.participantes} ${c.participantes === 1 ? "participante" : "participantes"}`}
                </Texto>
              </Texto>
            ) : (
              <Texto style={{ fontSize: 15, lineHeight: 22 }}>Ainda não tem lugar nesta competição.</Texto>
            )
          ) : null}
          {c.estado === "activa" && c.topo.length ? (
            <View style={{ gap: 4 }}>
              {c.topo.map((t, i) => (
                <View key={`${t.lugar}-${t.nome}-${i}`} style={{ flexDirection: "row", gap: 12, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: t.sou_eu ? cor.realceSuave : cor.fundoSuave }}>
                  <Texto numeros forte={t.sou_eu} style={{ width: 32, fontSize: 15 }}>
                    {t.lugar}.º
                  </Texto>
                  <Texto forte={t.sou_eu} numberOfLines={1} style={{ flex: 1, fontSize: 15 }}>
                    {t.sou_eu ? `${t.nome} (você)` : t.nome}
                  </Texto>
                  <Texto numeros forte={t.sou_eu} style={{ fontSize: 15 }}>
                    {fmt(t.valor)}
                  </Texto>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ))}

      {premios.length ? (
        <View style={{ gap: 8 }}>
          <Texto forte style={{ fontSize: 17 }}>
            Os seus prémios
          </Texto>
          {premios.map((p) => {
            const Icone = p.premio === "medalha" ? Medal : Award;
            return (
              <Pressable
                key={`${p.competicao_id}-${p.premio}`}
                disabled={!p.certificado_url}
                accessibilityRole={p.certificado_url ? "link" : undefined}
                onPress={() => p.certificado_url && void Linking.openURL(p.certificado_url)}
                style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingHorizontal: 12, paddingVertical: 8 }}
              >
                <View style={{ width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }}>
                  <Icone size={20} color={cor.sobreMarca} />
                </View>
                <View style={{ flex: 1 }}>
                  <Texto forte style={{ fontSize: 15, lineHeight: 20 }}>
                    {`${p.premio_nome}${p.lugar ? `, ${p.lugar}.º lugar` : ""}`}
                  </Texto>
                  <Texto v="legenda" suave numberOfLines={1} style={p.certificado_url ? { textDecorationLine: "underline" } : undefined}>
                    {p.competicao}
                  </Texto>
                </View>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {terminadas.length ? (
        <View style={{ borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md }}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: verTerminadas }}
            onPress={() => setVerTerminadas((v) => !v)}
            style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48, paddingHorizontal: 16 }}
          >
            <Texto forte>Competições terminadas ({terminadas.length})</Texto>
            {verTerminadas ? <ChevronUp size={20} color={cor.tintaSuave} /> : <ChevronDown size={20} color={cor.tintaSuave} />}
          </Pressable>
          {verTerminadas
            ? terminadas.map((c) => (
                <View key={c.id} style={{ gap: 6, borderTopWidth: 1, borderColor: cor.linha, paddingHorizontal: 16, paddingVertical: 12 }}>
                  <Texto forte style={{ lineHeight: 22 }}>
                    {c.nome}
                  </Texto>
                  {c.meu_premio ? <Etiqueta tom="certo">{`Ganhou ${PREMIO_CURTO[c.meu_premio] ?? "um prémio"}`}</Etiqueta> : null}
                  <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                    {`Terminou a ${dia(c.fim)}. ${c.meu_lugar ? `Ficou em ${c.meu_lugar}.º lugar com ${fmt(c.meu_valor)} ${unidade(c, c.meu_valor)}, entre ${c.participantes} participantes.` : "Não ficou classificado."}${c.topo.length ? ` Primeiros: ${c.topo.map((t) => `${t.lugar}.º ${t.sou_eu ? "você" : t.nome}`).join(", ")}.` : ""}`}
                  </Texto>
                  {c.certificado_url ? (
                    <Botao tipo="ligacao" tamanho="pequeno" onPress={() => void Linking.openURL(c.certificado_url!)}>
                      Abrir o certificado de mérito
                    </Botao>
                  ) : null}
                </View>
              ))
            : null}
        </View>
      ) : null}
    </View>
  );
}
