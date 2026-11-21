/**
 * Separador Perfil (canvas: Perfil; web: app/(estudante)/user/profile/page.tsx).
 */
import { Bell, BarChart3, ClipboardList, CreditCard, LogOut, Medal, MessageSquareHeart, Receipt, Settings, Trophy } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { Avatar } from "@/componentes/perfil/Avatar";
import { usePermissaoNotificacoes, useSincronizarLembrete } from "@/componentes/perfil/Avisos";
import { usePorLer } from "@/dominios/avisos/api";
import { nomeArea, usePerfilCertificadosQuery, usePerfilDadosQuery, usePerfilSequenciaQuery, usePerfilVidasQuery } from "@/dominios/perfil/api";
import { dataPt, milhares, useSubMinhaQuery } from "@/dominios/subscricao/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { cor, raio } from "@/tema";
import { Botao, Dialogo, Ecra, Etiqueta, EstadoErro, LinhaLista, MarcaIcone, Osso, Texto, Titulo } from "@/ui";

export default function EcraPerfil() {
  const { sair } = useSessao();
  const perfil = usePerfilDadosQuery();
  const sub = useSubMinhaQuery();
  const sequencia = usePerfilSequenciaQuery();
  const vidas = usePerfilVidasQuery();
  const certificados = usePerfilCertificadosQuery();
  const porLer = usePorLer();
  const [confirmarSair, setConfirmarSair] = useState(false);
  const [aSair, setASair] = useState(false);
  // Ao abrir o perfil, os lembretes locais acertam-se com o que a API sabe.
  const { estado: permissao } = usePermissaoNotificacoes();
  useSincronizarLembrete(permissao);

  const p = perfil.data;
  const s = sub.data;
  const gratuito = !s || s.plan.plan_type === "FREE";
  const subtitulo = [nomeArea(p?.preferences?.area), p?.preferences?.cidade].filter(Boolean).join(", ");
  const nCert = certificados.data?.certificados.filter((c) => c.estado === "valido").length;
  const aActualizar = perfil.isFetching && !perfil.isLoading;

  const actualizar = () => {
    perfil.refetch();
    sub.refetch();
    sequencia.refetch();
    vidas.refetch();
    certificados.refetch();
  };

  const numeros: [string, string][] = [
    [sequencia.data ? String(sequencia.data.current_streak) : "–", sequencia.data?.current_streak === 1 ? "dia seguido" : "dias seguidos"],
    [vidas.data ? milhares(vidas.data.points) : "–", "pontos"],
    [nCert === undefined ? "–" : String(nCert), nCert === 1 ? "certificado" : "certificados"],
  ];

  const ic = (I: typeof Bell) => (
    <MarcaIcone>
      <I size={20} color={cor.tinta} />
    </MarcaIcone>
  );
  const itens = [
    { href: "/estatisticas", titulo: "Estatísticas", texto: "Tempo, lições e respostas certas", icone: ic(BarChart3) },
    { href: "/notas", titulo: "Notas dos cursos", texto: "As notas dos questionários e exames", icone: ic(ClipboardList) },
    { href: "/certificados", titulo: "Certificados", texto: "Os certificados dos cursos que concluiu", icone: ic(Medal) },
    { href: "/conquistas", titulo: "Conquistas e liga", texto: "Medalhas e a sua posição", icone: ic(Trophy) },
    {
      href: "/subscricao",
      titulo: "Subscrição",
      texto: s ? (gratuito ? "Plano Gratuito" : s.em_teste ? `${s.plan.name} em teste até ${dataPt(s.teste_termina_em ?? s.termina_em, "diaMes")}` : `${s.plan.name}, válido até ${dataPt(s.termina_em ?? s.expires_at, "diaMes")}`) : "O seu plano",
      icone: ic(CreditCard),
    },
    { href: "/recibos", titulo: "Pagamentos e recibos", texto: "Os recibos dos seus pagamentos", icone: ic(Receipt) },
    { href: "/definicoes", titulo: "Definições", texto: "Dados, metas, avisos e palavra-passe", icone: ic(Settings) },
    { href: "/notificacoes", titulo: "Notificações", texto: porLer ? `${porLer} por ler` : "Os avisos que recebeu", icone: ic(Bell) },
    { href: "/opiniao", titulo: "Dar a sua opinião", texto: "Diga-nos o que está a correr bem e o que mudar", icone: ic(MessageSquareHeart) },
  ];

  return (
    <Ecra aoActualizar={actualizar} aActualizar={aActualizar} style={{ gap: 22, paddingTop: 24 }}>
      {perfil.isError && !p ? (
        <EstadoErro erro={perfil.error} titulo="Não conseguimos carregar o seu perfil" aoTentar={actualizar} />
      ) : (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
          {p ? <Avatar nome={p.name} foto={p.avatar} /> : <Osso altura={72} largura={72} />}
          <View style={{ flex: 1, gap: 2 }}>
            {p ? (
              <Titulo v="tituloM" numberOfLines={2} style={{ fontSize: 24, lineHeight: 30 }}>
                {p.name}
              </Titulo>
            ) : (
              <Osso altura={28} largura="70%" />
            )}
            {subtitulo ? (
              <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                {subtitulo}
              </Texto>
            ) : null}
            {s ? (
              <View style={{ marginTop: 4 }}>
                <Etiqueta tom={gratuito ? "neutro" : "realce"}>{s.plan.name}</Etiqueta>
              </View>
            ) : null}
          </View>
        </View>
      )}

      <View style={{ flexDirection: "row", gap: 8 }}>
        {numeros.map(([n, r]) => (
          <View key={r} accessible accessibilityLabel={`${n} ${r}`} style={{ flex: 1, alignItems: "center", paddingVertical: 12, paddingHorizontal: 8, backgroundColor: cor.fundoSuave, borderRadius: raio.md }}>
            <Texto v="tituloM" numeros>
              {n}
            </Texto>
            <Texto v="mini" suave centro style={{ fontSize: 13, lineHeight: 18 }}>
              {r}
            </Texto>
          </View>
        ))}
      </View>

      <View accessibilityLabel="Conta">
        {itens.map((i) => (
          <LinhaLista key={i.href} href={i.href} titulo={i.titulo} descricao={i.texto} icone={i.icone} suave={false} />
        ))}
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={() => setConfirmarSair(true)}
        style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 48, alignSelf: "flex-start", opacity: pressed ? 0.7 : 1 })}
      >
        <LogOut size={20} color={cor.errado} />
        <Texto forte cor={cor.errado}>
          Sair da conta
        </Texto>
      </Pressable>

      <Dialogo aberto={confirmarSair} aoFechar={() => setConfirmarSair(false)} titulo="Sair da conta?" texto="Para voltar, tem de entrar outra vez neste telemóvel.">
        <Botao larguraTotal onPress={() => setConfirmarSair(false)}>
          Ficar
        </Botao>
        <Botao
          larguraTotal
          tipo="perigo"
          carregando={aSair}
          onPress={async () => {
            setASair(true);
            await sair();
          }}
        >
          Sair da conta
        </Botao>
      </Dialogo>
    </Ecra>
  );
}
