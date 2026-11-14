/**
 * Notificações (canvas: Notificacoes; web: user/notifications/page.tsx).
 * As ligações da web (/user/...) abrem as rotas da app (src/lib/rotasWeb.ts).
 */
import { Award, Bell, BookOpen, CreditCard, Flame, Medal, Trophy } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { abrirLigacao } from "@/dominios/perfil/abrir";
import { quando, useMarcarLidaMutation, useMarcarTodasMutation, useNotificacoesQuery, type Notificacao, type TipoNotificacao } from "@/dominios/avisos/api";
import { balao, cor, raio } from "@/tema";
import { ACarregar, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Osso, Texto } from "@/ui";

const ICONE: Record<TipoNotificacao, typeof Bell> = {
  streak: Flame,
  achievement: Trophy,
  league: Medal,
  certificate: Award,
  course: BookOpen,
  subscription: CreditCard,
  system: Bell,
};

export default function EcraNotificacoes() {
  const [paginas, setPaginas] = useState(1);
  const primeira = useNotificacoesQuery(1);
  const [marcarTodas, { isLoading: aMarcar }] = useMarcarTodasMutation();
  const porLer = primeira.data?.unread ?? 0;

  return (
    <Ecra
      cabecalho={
        <Cabecalho
          titulo="Notificações"
          subtitulo={primeira.data ? (porLer ? `${porLer} por ler` : "Está tudo lido.") : undefined}
          direita={
            porLer ? (
              <Botao tipo="ligacao" tamanho="pequeno" disabled={aMarcar} onPress={() => void marcarTodas()} style={{ minHeight: 44 }}>
                Marcar como lidas
              </Botao>
            ) : undefined
          }
        />
      }
      aoActualizar={() => {
        setPaginas(1);
        primeira.refetch();
      }}
      aActualizar={primeira.isFetching && !!primeira.data}
      style={{ gap: 20, paddingTop: 12 }}
    >
      {primeira.isError && !primeira.data ? (
        <EstadoErro erro={primeira.error} titulo="Não conseguimos carregar as notificações" aoTentar={() => primeira.refetch()} />
      ) : !primeira.data ? (
        <ACarregar linhas={5} altura={76} rotulo="A carregar as notificações" />
      ) : !primeira.data.results.length ? (
        <EstadoVazio
          titulo="Ainda não há notificações"
          texto="Aqui aparecem os avisos da meta diária, da liga, dos certificados, das aulas novas e da subscrição."
          icone={<Bell size={26} color={cor.azulMarca} />}
          accao={
            <Botao tipo="secundario" href="/praticar" style={{ alignSelf: "flex-start" }}>
              Praticar agora
            </Botao>
          }
        />
      ) : (
        <View style={{ gap: 4, marginHorizontal: -8 }}>
          {Array.from({ length: paginas }, (_, i) => (
            <PaginaDeItens key={i} pagina={i + 1} ultima={i + 1 === paginas} aoVerMais={() => setPaginas((p) => p + 1)} />
          ))}
        </View>
      )}

      <Botao tipo="ligacao" tamanho="pequeno" href="/definicoes">
        Escolher que avisos recebe
      </Botao>
    </Ecra>
  );
}

function PaginaDeItens({ pagina, ultima, aoVerMais }: { pagina: number; ultima: boolean; aoVerMais: () => void }) {
  const { data, isFetching, isError, refetch } = useNotificacoesQuery(pagina);
  // Avisos novos empurram os antigos para a página seguinte: não repetir os que a anterior já mostra.
  const { data: anterior } = useNotificacoesQuery(pagina - 1, { skip: pagina === 1 });
  if (isError && !data)
    return (
      <View style={{ paddingHorizontal: 8, paddingTop: 8 }}>
        <Botao tipo="secundario" tamanho="pequeno" onPress={() => refetch()} style={{ alignSelf: "flex-start" }}>
          Tentar outra vez
        </Botao>
      </View>
    );
  if (!data) return <Osso altura={76} style={{ marginVertical: 4 }} />;
  const jaMostradas = new Set((anterior?.results ?? []).map((n) => n.id));
  return (
    <>
      {data.results
        .filter((n) => !jaMostradas.has(n.id))
        .map((n) => (
          <Item key={n.id} n={n} />
        ))}
      {ultima && data.next ? (
        <View style={{ paddingHorizontal: 8, paddingTop: 8 }}>
          <Botao tipo="ligacao" tamanho="pequeno" disabled={isFetching} onPress={aoVerMais}>
            Ver as mais antigas
          </Botao>
        </View>
      ) : null}
    </>
  );
}

function Item({ n }: { n: Notificacao }) {
  const [marcar] = useMarcarLidaMutation();
  const Icone = ICONE[n.kind] ?? Bell;
  return (
    <Pressable
      accessibilityRole={n.link ? "link" : "button"}
      accessibilityLabel={`${n.read ? "" : "Por ler: "}${n.title}. ${n.body}. ${quando(n.created_at)}`}
      onPress={() => {
        if (!n.read) void marcar(n.id);
        if (n.link) void abrirLigacao(n.link);
      }}
      style={({ pressed }) => ({
        flexDirection: "row",
        gap: 12,
        paddingVertical: 14,
        paddingHorizontal: 12,
        borderRadius: raio.md,
        backgroundColor: pressed ? cor.fundoForte : n.read ? cor.fundo : cor.fundoSuave,
      })}
    >
      <View style={[balao.pequeno, { width: 40, height: 40, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomRightRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: n.read ? cor.fundoForte : cor.azulMarca }]}>
        <Icone size={20} color={n.read ? cor.tintaSuave : cor.realce} />
      </View>
      <View style={{ flex: 1 }}>
        <Texto forte={!n.read} style={{ lineHeight: 22 }}>
          {n.title}
        </Texto>
        {n.body ? (
          <Texto v="legenda" suave>
            {n.body}
          </Texto>
        ) : null}
        <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
          {quando(n.created_at)}
        </Texto>
      </View>
      {n.read ? null : <View style={{ width: 10, height: 10, marginTop: 8, borderRadius: 5, backgroundColor: cor.azulVivo }} />}
    </Pressable>
  );
}
