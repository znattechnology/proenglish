/**
 * Avisos na app (web: components/pe/avisos/Avisos.tsx): preferências guardadas na API
 * (/users/avisos/) e o lembrete diário como notificação local (ver src/dominios/perfil/lembrete.ts).
 */
import { BellRing } from "lucide-react-native";
import { useCallback, useEffect, useState } from "react";
import { AppState, Linking, Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAvisosQuery, useMudarAvisosMutation, type MudancaAvisos } from "@/dominios/avisos/api";
import { usePerfilSequenciaQuery } from "@/dominios/perfil/api";
import { estadoPermissao, pedirPermissao, sincronizarLembrete, type EstadoPermissao } from "@/dominios/perfil/lembrete";
import { balao, cor, raio } from "@/tema";
import { Aviso, Botao, Interruptor, Osso, Pilulas, Texto, Titulo } from "@/ui";

const HORAS = ["07:00", "12:30", "19:00", "21:00"];

/** Estado da autorização do sistema, actualizado ao voltar à app (a pessoa pode tê-la mudado). */
export function usePermissaoNotificacoes() {
  const [estado, setEstado] = useState<EstadoPermissao | null>(null);
  const ler = useCallback(() => {
    void estadoPermissao().then(setEstado);
  }, []);
  useEffect(() => {
    ler();
    const s = AppState.addEventListener("change", (e) => e === "active" && ler());
    return () => s.remove();
  }, [ler]);
  return { estado, ler };
}

/** Mantém os avisos locais agendados de acordo com a API (lembrete, hora, se já praticou hoje). */
export function useSincronizarLembrete(permissao: EstadoPermissao | null) {
  const { data: a } = useAvisosQuery();
  const { data: s } = usePerfilSequenciaQuery();
  const ligado = a?.lembrete.ligado;
  const hora = a?.lembrete.hora;
  const praticou = s ? s.goal_completed || s.practiced_today : undefined;
  useEffect(() => {
    if (ligado === undefined || !hora || permissao === null) return;
    void sincronizarLembrete({ ligado, hora, praticouHoje: praticou, metaMinutos: s?.daily_goal_minutes, minutosHoje: s?.minutes_today });
  }, [ligado, hora, praticou, permissao, s?.daily_goal_minutes, s?.minutes_today]);
}

/**
 * Folha "Quer um lembrete para não perder os dias seguidos?" (tela PermissaoNotificacoes).
 * Explica antes de o sistema pedir autorização. Pode ser aberta no fim de uma lição (3 dias seguidos)
 * ou nas definições, ao ligar o lembrete.
 */
export function PedirLembrete({ aberto, aoFechar, nota }: { aberto: boolean; aoFechar: (ligado: boolean) => void; nota?: string }) {
  const ins = useSafeAreaInsets();
  const { data: a } = useAvisosQuery();
  const [mudar, { isLoading }] = useMudarAvisosMutation();
  const [hora, setHora] = useState("19:00");
  const [aLigar, setALigar] = useState(false);
  const horas = Array.from(new Set([...HORAS, a?.lembrete.hora ?? "19:00"])).sort();

  const ligar = async () => {
    setALigar(true);
    try {
      await mudar({ lembrete: { ligado: true, hora } }).unwrap().catch(() => null);
      const ok = await pedirPermissao();
      if (ok) await sincronizarLembrete({ ligado: true, hora });
      aoFechar(true);
    } finally {
      setALigar(false);
    }
  };

  return (
    <Modal visible={aberto} transparent animationType="slide" onRequestClose={() => aoFechar(false)} statusBarTranslucent>
      <View style={{ flex: 1, justifyContent: "flex-end" }}>
        <Pressable accessibilityLabel="Fechar" onPress={() => aoFechar(false)} style={{ position: "absolute", inset: 0, backgroundColor: "rgba(20,20,63,0.55)" }} />
        <View accessibilityViewIsModal style={{ backgroundColor: cor.fundo, borderTopLeftRadius: raio.md, borderTopRightRadius: raio.md, paddingHorizontal: 20, paddingTop: 24, paddingBottom: Math.max(ins.bottom, 24), gap: 18 }}>
          <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.realce }]}>
            <BellRing size={28} color={cor.tinta} />
          </View>
          <View style={{ gap: 8 }}>
            <Titulo v="tituloM">Quer um lembrete para não perder os dias seguidos?</Titulo>
            <Texto suave>Um aviso por dia, à hora que escolher, só se ainda não tiver praticado.</Texto>
          </View>
          <View style={{ gap: 8 }}>
            <Texto v="rotulo">Hora do lembrete</Texto>
            <Pilulas rotulo="Hora do lembrete" opcoes={horas.map((h) => ({ valor: h, nome: h }))} valor={hora} aoMudar={setHora} />
          </View>
          <View style={{ gap: 10 }}>
            <Botao larguraTotal carregando={aLigar || isLoading} onPress={() => void ligar()}>
              Ligar o lembrete
            </Botao>
            <Botao tipo="ligacao" larguraTotal onPress={() => aoFechar(false)}>
              Agora não
            </Botao>
          </View>
          {nota ? (
            <Texto v="mini" suave centro style={{ fontSize: 13, lineHeight: 18 }}>
              {nota}
            </Texto>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

/** Secção "Avisos" das definições. */
export function SeccaoAvisos() {
  const { data: a, isError, refetch } = useAvisosQuery();
  const [mudar, { isLoading }] = useMudarAvisosMutation();
  const { estado: permissao, ler } = usePermissaoNotificacoes();
  useSincronizarLembrete(permissao);
  const [pedir, setPedir] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const guardar = async (m: MudancaAvisos) => {
    setErro(null);
    try {
      await mudar(m).unwrap();
    } catch {
      setErro("Não foi possível guardar. Tente outra vez.");
    }
  };

  if (isError)
    return (
      <Aviso tom="erro" titulo="Não conseguimos carregar os avisos." accao={<Botao tamanho="pequeno" onPress={() => refetch()} style={{ alignSelf: "flex-start" }}>Tentar outra vez</Botao>} />
    );
  if (!a) return <Osso altura={220} />;

  return (
    <View style={{ gap: 12 }}>
      <View>
        <Interruptor
          rotulo="Lembrete da meta diária"
          descricao="Um aviso por dia, à hora que escolher, só se ainda não tiver praticado."
          valor={a.lembrete.ligado}
          inactivo={isLoading}
          aoMudar={async (v) => {
            setAviso(null);
            if (v && permissao === "pode-pedir") return setPedir(true);
            await guardar({ lembrete: { ligado: v } });
            if (v && permissao === "negada") setAviso("O telemóvel está a bloquear as notificações do ProEnglish. Sem autorização, o lembrete não aparece.");
          }}
        />
        {a.lembrete.ligado ? (
          <View style={{ gap: 8, paddingBottom: 8 }}>
            <Texto v="rotulo">Hora do lembrete</Texto>
            <Pilulas
              rotulo="Hora do lembrete"
              opcoes={Array.from(new Set([...HORAS, a.lembrete.hora])).sort().map((h) => ({ valor: h, nome: h }))}
              valor={a.lembrete.hora}
              aoMudar={(h) => void guardar({ lembrete: { hora: h } })}
            />
            <Texto v="legenda" suave>
              Hora de Angola.
            </Texto>
          </View>
        ) : null}
      </View>

      <View>
        <Texto forte style={{ paddingTop: 4 }}>
          O que quer receber
        </Texto>
        <Interruptor rotulo="Meta diária e dias seguidos" valor={a.tipos.meta} inactivo={isLoading} aoMudar={(v) => void guardar({ tipos: { meta: v } })} />
        <Interruptor rotulo="Liga semanal e conquistas" valor={a.tipos.liga} inactivo={isLoading} aoMudar={(v) => void guardar({ tipos: { liga: v } })} />
        <Interruptor rotulo="Certificados" valor={a.tipos.certificados} inactivo={isLoading} aoMudar={(v) => void guardar({ tipos: { certificados: v } })} />
        <Interruptor rotulo="Aulas novas nos seus cursos" valor={a.tipos.cursos} inactivo={isLoading} aoMudar={(v) => void guardar({ tipos: { cursos: v } })} />
        <Interruptor rotulo="Subscrição e recibos" descricao="Pagamentos e fim do plano. Não se podem desligar." valor inactivo aoMudar={() => {}} />
      </View>

      <View style={{ gap: 8, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <BellRing size={20} color={cor.azulMarca} />
          <Texto forte>Notificações neste telemóvel</Texto>
        </View>
        {permissao === "concedida" ? (
          <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
            Autorizadas. O lembrete da meta chega à hora escolhida. Os outros avisos aparecem em Notificações.
          </Texto>
        ) : permissao === "negada" ? (
          <>
            <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
              O telemóvel está a bloquear as notificações do ProEnglish. Pode autorizar nas definições do telemóvel.
            </Texto>
            <Botao tipo="ligacao" tamanho="pequeno" onPress={() => void Linking.openSettings()}>
              Abrir as definições do telemóvel
            </Botao>
          </>
        ) : permissao === "pode-pedir" ? (
          <>
            <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
              Autorize para receber o lembrete da meta mesmo com a app fechada.
            </Texto>
            <Botao
              tamanho="pequeno"
              style={{ alignSelf: "flex-start" }}
              onPress={async () => {
                const ok = await pedirPermissao();
                ler();
                setAviso(ok ? "Notificações autorizadas neste telemóvel." : "Sem autorização, os avisos ficam só em Notificações.");
              }}
            >
              Autorizar notificações
            </Botao>
          </>
        ) : (
          <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
            Este aparelho não recebe notificações. Os avisos aparecem em Notificações.
          </Texto>
        )}
      </View>
      {aviso ? <Aviso tom="info">{aviso}</Aviso> : null}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}

      <PedirLembrete
        aberto={pedir}
        aoFechar={(ligado) => {
          setPedir(false);
          ler();
          if (ligado) setAviso(null);
        }}
      />
    </View>
  );
}
