/**
 * Definições (canvas: Definicoes + PermissaoNotificacoes; web: user/settings/page.tsx,
 * components/pe/conta/MudarPalavraPasse.tsx, components/pe/avisos/Avisos.tsx).
 */
import { ExternalLink, LogOut } from "lucide-react-native";
import { type ReactNode, useState } from "react";
import { Pressable, View } from "react-native";
import { tokens } from "@/api/tokens";
import { mensagemErro } from "@/api/erros";
import { Avatar } from "@/componentes/perfil/Avatar";
import { SeccaoAvisos } from "@/componentes/perfil/Avisos";
import { Caixa, CampoTelefone, Escolha } from "@/componentes/perfil/Campos";
import { Folha } from "@/componentes/perfil/Folha";
import { abrirSite } from "@/dominios/perfil/abrir";
import { cancelarLembretes } from "@/dominios/perfil/lembrete";
import {
  AREAS,
  errosDoServidor,
  NIVEIS,
  normalizarNivel,
  usePerfilApagarContaMutation,
  usePerfilDadosQuery,
  usePerfilGuardarMutation,
  usePerfilMetaEstudoQuery,
  usePerfilMetaFalaQuery,
  usePerfilMudarMetaEstudoMutation,
  usePerfilMudarMetaFalaMutation,
  usePerfilMudarSenhaMutation,
  usePerfilProvinciasQuery,
  type Nivel,
  type Perfil,
} from "@/dominios/perfil/api";
import { dataPt, telefoneLegivel, useSubLembretesMutation, useSubMinhaQuery } from "@/dominios/subscricao/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { cor } from "@/tema";
import { ACarregar, Aviso, Botao, Cabecalho, Campo, Ecra, EstadoErro, Interruptor, Pilulas, Texto, Titulo } from "@/ui";

const METAS = [5, 10, 15, 20];

export default function EcraDefinicoes() {
  const perfil = usePerfilDadosQuery();
  const { data: sub } = useSubMinhaQuery();
  const p = perfil.data;

  if (perfil.isError && !p)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Definições" />}>
        <EstadoErro erro={perfil.error} titulo="Não conseguimos carregar os seus dados" aoTentar={() => perfil.refetch()} />
      </Ecra>
    );
  if (!p)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Definições" />}>
        <ACarregar linhas={4} altura={88} />
      </Ecra>
    );
  // Montado só com os dados: o formulário começa com os valores guardados.
  return <Definicoes key={p.id} p={p} pago={!!sub && sub.plan.plan_type !== "FREE" && !sub.em_teste} lembretes={!!sub?.lembretes_renovacao} plano={sub?.plan.name} />;
}

function Bloco({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <View style={{ gap: 12 }}>
      <Texto v="tituloXS" accessibilityRole="header" style={{ fontFamily: "Montserrat_600SemiBold", fontSize: 18, lineHeight: 24 }}>
        {titulo}
      </Texto>
      {children}
    </View>
  );
}

function Definicoes({ p, pago, lembretes, plano }: { p: Perfil; pago: boolean; lembretes: boolean; plano?: string }) {
  const { sair, actualizarUtilizador } = useSessao();
  const perfil = usePerfilDadosQuery();
  const [guardar, { isLoading: aGuardar }] = usePerfilGuardarMutation();
  const { data: provincias } = usePerfilProvinciasQuery();

  const estrangeiro = (p.phone ?? "").startsWith("+") && !(p.phone ?? "").startsWith("+244");
  const inicial = {
    nome: p.name,
    telefone: telefoneLegivel((p.phone ?? "").replace(/^\+244/, "")),
    cidade: p.preferences?.cidade ?? "",
    provincia: p.provincia ?? "",
    area: p.preferences?.area ?? "",
    nivel: (normalizarNivel(p.preferences?.nivel) ?? "") as Nivel | "",
  };
  const [f, setF] = useState(inicial);
  const [base, setBase] = useState(inicial);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<{ tom: "certo" | "erro"; texto: string } | null>(null);
  const sujo = JSON.stringify(f) !== JSON.stringify(base);
  const mudar = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => {
    setEstado(null);
    setF((x) => ({ ...x, [k]: v }));
  };

  const enviar = async () => {
    setEstado(null);
    const digitos = f.telefone.replace(/\D/g, "");
    const novos: Record<string, string> = {};
    if (f.nome.trim().length < 2) novos.name = "Escreva o seu nome.";
    if (!estrangeiro && digitos && !/^9\d{8}$/.test(digitos)) novos.phone = "Escreva os 9 dígitos do número, a começar por 9.";
    setErros(novos);
    if (Object.keys(novos).length) return;
    const r = await guardar({
      name: f.nome.trim(),
      phone: estrangeiro ? p.phone : digitos ? `+244${digitos}` : null,
      provincia: f.provincia || null,
      preferences: { ...p.preferences, cidade: f.cidade.trim(), area: f.area, nivel: f.nivel || undefined },
    });
    if ("error" in r && r.error) {
      const { campos, geral } = errosDoServidor(r.error);
      setErros(campos);
      setEstado(geral ? { tom: "erro", texto: geral } : null);
      return;
    }
    setBase(f);
    setEstado({ tom: "certo", texto: "Alterações guardadas." });
    void actualizarUtilizador();
  };

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Definições" />}
      aoActualizar={() => perfil.refetch()}
      aActualizar={perfil.isFetching}
      rodape={
        sujo ? (
          <Botao larguraTotal carregando={aGuardar} onPress={() => void enviar()}>
            {aGuardar ? "A guardar…" : "Guardar alterações"}
          </Botao>
        ) : undefined
      }
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
        <Avatar nome={p.name} foto={p.avatar} tamanho={64} />
        <View style={{ flex: 1 }}>
          <Titulo v="tituloS" numberOfLines={2}>
            {p.name}
          </Titulo>
          <Texto v="legenda" suave style={{ fontSize: 15 }}>
            Membro desde {dataPt(p.created_at, "mesAno")}
            {plano ? `, plano ${plano}` : ""}
          </Texto>
        </View>
      </View>

      <Bloco titulo="Os seus dados">
        <Campo rotulo="Nome completo" value={f.nome} onChangeText={(v) => mudar("nome", v)} autoComplete="name" textContentType="name" erro={erros.name} />
        <Campo rotulo="Email" value={p.email} editable={false} ajuda="O email não se pode mudar aqui." />
        {estrangeiro ? (
          <Campo rotulo="Telefone" value={p.phone ?? ""} editable={false} ajuda="Número estrangeiro." />
        ) : (
          <CampoTelefone rotulo="Telefone" valor={f.telefone} aoMudar={(v) => mudar("telefone", v)} erro={erros.phone} />
        )}
        <Campo rotulo="Cidade" value={f.cidade} onChangeText={(v) => mudar("cidade", v)} autoComplete="postal-address-locality" textContentType="addressCity" erro={erros.preferences} />
        <Escolha
          rotulo="Província (opcional)"
          ajuda="Ajuda-nos a perceber onde estão os nossos alunos."
          valor={f.provincia}
          opcoes={(provincias ?? []).map((x) => ({ valor: x.valor, nome: x.nome }))}
          aoMudar={(v) => mudar("provincia", v)}
          vazio="Prefiro não dizer"
        />
        <Escolha rotulo="Área profissional" ajuda="Usamos a área para lhe sugerir cursos." valor={f.area} opcoes={AREAS} aoMudar={(v) => mudar("area", v)} vazio="Escolha a sua área" />
        <Escolha
          rotulo="O seu nível de inglês"
          valor={f.nivel}
          opcoes={NIVEIS.map((n) => ({ valor: n.valor, nome: n.nome, descricao: n.descricao }))}
          aoMudar={(v) => mudar("nivel", v)}
          vazio="Não sei"
        />
        {estado ? <Aviso tom={estado.tom}>{estado.texto}</Aviso> : null}
      </Bloco>

      <EstudoERenovacao pago={pago} lembretes={lembretes} />

      <Bloco titulo="Avisos">
        <SeccaoAvisos />
      </Bloco>

      <Bloco titulo="Privacidade e gravações">
        <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
          Só gravamos o áudio do exame oral de um curso, e só quando o autoriza antes de começar. Ouvem-no você e o professor do curso, durante 12 meses. Pode apagar a gravação antes no resultado do exame.
        </Texto>
        <Pressable
          accessibilityRole="link"
          onPress={() => void abrirSite("/privacidade#gravacoes")}
          style={{ flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, alignSelf: "flex-start" }}
        >
          <Texto forte cor={cor.azulMarca} style={{ textDecorationLine: "underline" }}>
            Ler a política de privacidade
          </Texto>
          <ExternalLink size={18} color={cor.azulMarca} />
        </Pressable>
      </Bloco>

      <Seguranca temSenha={p.has_password !== false} />

      <Pressable
        accessibilityRole="button"
        onPress={() => {
          void cancelarLembretes();
          void sair();
        }}
        style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 48, alignSelf: "flex-start", opacity: pressed ? 0.7 : 1 })}
      >
        <LogOut size={20} color={cor.errado} />
        <Texto forte cor={cor.errado}>
          Sair da conta
        </Texto>
      </Pressable>
    </Ecra>
  );
}

/* ------------------------------------------------------------------ */
/* Estudo e renovação                                                   */
/* ------------------------------------------------------------------ */
function EstudoERenovacao({ pago, lembretes }: { pago: boolean; lembretes: boolean }) {
  const { data: meta } = usePerfilMetaEstudoQuery();
  const { data: fala } = usePerfilMetaFalaQuery();
  const [mudarMeta, { isLoading: aMeta }] = usePerfilMudarMetaEstudoMutation();
  const [mudarFala, { isLoading: aFala }] = usePerfilMudarMetaFalaMutation();
  const [mudarLembretes, { isLoading: aLembretes }] = useSubLembretesMutation();
  const [erro, setErro] = useState<string | null>(null);

  const tentar = async (p: Promise<{ error?: unknown }>, padrao: string) => {
    setErro(null);
    const r = await p;
    if (r.error) setErro(mensagemErro(r.error, padrao));
  };

  return (
    <Bloco titulo="Estudo e renovação">
      <View style={{ gap: 8 }}>
        <View>
          <Texto forte>Meta de estudo</Texto>
          <Texto v="legenda" suave>
            Minutos de prática por dia. Conta para os dias seguidos.
          </Texto>
        </View>
        <View pointerEvents={aMeta || !meta ? "none" : "auto"} style={{ opacity: aMeta ? 0.6 : 1 }}>
          <Pilulas
            rotulo="Meta de estudo"
            opcoes={METAS.map((m) => ({ valor: String(m), nome: `${m} min` }))}
            valor={String(meta?.daily_goal_minutes ?? "")}
            aoMudar={(v) => void tentar(mudarMeta(Number(v)), "Não foi possível mudar a meta.")}
          />
        </View>
      </View>
      <View style={{ gap: 8 }}>
        <View>
          <Texto forte>Meta de fala</Texto>
          <Texto v="legenda" suave>
            Minutos a falar inglês por dia (conversas, lições, revisão e aulas). Aparece em destaque no início.
          </Texto>
        </View>
        <View pointerEvents={aFala || !fala ? "none" : "auto"} style={{ opacity: aFala ? 0.6 : 1 }}>
          <Pilulas
            rotulo="Meta de fala"
            opcoes={(fala?.opcoes ?? [3, 5, 10, 15]).map((m) => ({ valor: String(m), nome: `${m} min` }))}
            valor={String(fala?.meta_fala_min ?? "")}
            aoMudar={(v) => void tentar(mudarFala(Number(v)), "Não foi possível mudar a meta.")}
          />
        </View>
      </View>
      {pago ? (
        <Interruptor
          rotulo="Lembretes de renovação"
          descricao="Avisamos 3 dias antes e no dia em que o plano termina."
          valor={lembretes}
          inactivo={aLembretes}
          aoMudar={(v) => void tentar(mudarLembretes(v), "Não foi possível guardar.")}
        />
      ) : null}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
    </Bloco>
  );
}

/* ------------------------------------------------------------------ */
/* Segurança: palavra-passe e apagar a conta                            */
/* ------------------------------------------------------------------ */
function Seguranca({ temSenha }: { temSenha: boolean }) {
  const [senha, setSenha] = useState(false);
  const [apagar, setApagar] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);
  return (
    <Bloco titulo="Segurança">
      {!temSenha ? (
        <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
          Entra com o Google. Se quiser, pode também criar uma palavra-passe para entrar com o email.
        </Texto>
      ) : null}
      <Botao tipo="secundario" larguraTotal onPress={() => setSenha(true)}>
        {temSenha ? "Mudar a palavra-passe" : "Criar uma palavra-passe"}
      </Botao>
      {feito ? <Aviso tom="certo">{feito}</Aviso> : null}
      <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
        Apagar a conta apaga o seu nome, email, telefone e fotografia, e deixa de poder entrar. Não se pode desfazer.
      </Texto>
      <Botao tipo="ligacao" onPress={() => setApagar(true)} style={{ minHeight: 44 }}>
        <Texto forte cor={cor.errado} style={{ textDecorationLine: "underline" }}>
          Apagar a conta
        </Texto>
      </Botao>
      {/* Montados só quando abrem: o formulário recomeça vazio de cada vez. */}
      {senha ? <MudarPalavraPasse temSenha={temSenha} aoFechar={() => setSenha(false)} aoMudada={setFeito} /> : null}
      {apagar ? <ApagarConta temSenha={temSenha} aoFechar={() => setApagar(false)} /> : null}
    </Bloco>
  );
}

function MudarPalavraPasse({ temSenha, aoFechar, aoMudada }: { temSenha: boolean; aoFechar: () => void; aoMudada: (m: string) => void }) {
  const { iniciar } = useSessao();
  const [mudar, { isLoading }] = usePerfilMudarSenhaMutation();
  const [actual, setActual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);

  const enviar = async () => {
    setGeral(null);
    const novos: Record<string, string> = {};
    if (temSenha && !actual) novos.current_password = "Escreva a palavra-passe actual.";
    if (nova.length < 8) novos.new_password = "Use pelo menos 8 caracteres.";
    if (nova !== confirmar) novos.new_password_confirm = "As duas palavras-passe novas não são iguais.";
    setErros(novos);
    if (Object.keys(novos).length) return;
    const r = await mudar({ actual, nova, confirmar, refresh: tokens.refresh });
    if ("error" in r && r.error) {
      const { campos, geral: g } = errosDoServidor(r.error);
      setErros(campos);
      setGeral(g);
      return;
    }
    // Os tokens de acesso antigos deixaram de valer: a resposta traz o novo.
    if (r.data.tokens?.access) await iniciar({ tokens: r.data.tokens }).catch(() => {});
    aoMudada(r.data.message);
    aoFechar();
  };

  return (
    <Folha
      aberto
      aoFechar={aoFechar}
      titulo={temSenha ? "Mudar a palavra-passe" : "Criar uma palavra-passe"}
      texto={temSenha ? "Depois de mudar, as sessões abertas noutros dispositivos terminam." : "Continua a poder entrar com o Google. A palavra-passe serve para entrar também com o email."}
    >
      {temSenha ? (
        <Campo rotulo="Palavra-passe actual" senha value={actual} onChangeText={setActual} autoComplete="current-password" textContentType="password" erro={erros.current_password} />
      ) : null}
      <Campo
        rotulo="Palavra-passe nova"
        senha
        value={nova}
        onChangeText={setNova}
        autoComplete="new-password"
        textContentType="newPassword"
        erro={erros.new_password}
        ajuda="Pelo menos 8 caracteres. Evite palavras comuns."
      />
      <Campo rotulo="Repita a palavra-passe nova" senha value={confirmar} onChangeText={setConfirmar} autoComplete="new-password" textContentType="newPassword" erro={erros.new_password_confirm} />
      {geral ? <Aviso tom="erro">{geral}</Aviso> : null}
      <Botao larguraTotal carregando={isLoading} onPress={() => void enviar()}>
        {isLoading ? "A guardar…" : temSenha ? "Mudar a palavra-passe" : "Criar a palavra-passe"}
      </Botao>
      <Botao tipo="ligacao" larguraTotal onPress={aoFechar}>
        Cancelar
      </Botao>
    </Folha>
  );
}

function ApagarConta({ temSenha, aoFechar }: { temSenha: boolean; aoFechar: () => void }) {
  const { sair } = useSessao();
  const [apagar, { isLoading }] = usePerfilApagarContaMutation();
  const [senha, setSenha] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const enviar = async () => {
    setErro(null);
    // Contas do Google não têm palavra-passe: confirma-se com a caixa.
    const r = await apagar(temSenha ? { password: senha } : { confirmar: true });
    if ("error" in r && r.error) {
      setErro(errosDoServidor(r.error).geral ?? "Não foi possível apagar a conta.");
      return;
    }
    // A sessão já terminou no servidor: limpa o telemóvel e volta à entrada.
    await cancelarLembretes();
    await sair();
  };

  const pontos = [
    "O seu nome, email, telefone e fotografia são apagados e deixa de poder entrar.",
    "O progresso, os pontos e os certificados deixam de estar ligados a si e não se recuperam.",
    "Se tem um plano pago, perde os dias que faltam. Não há reembolso automático.",
    "Os recibos dos pagamentos ficam guardados sem o seu nome, porque são registos fiscais.",
  ];

  return (
    <Folha aberto aoFechar={aoFechar} titulo="Apagar a conta?">
      <View style={{ gap: 8 }}>
        {pontos.map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
              •
            </Texto>
            <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
              {t}
            </Texto>
          </View>
        ))}
      </View>
      {temSenha ? (
        <Campo rotulo="Escreva a sua palavra-passe para confirmar" senha value={senha} onChangeText={setSenha} autoComplete="current-password" textContentType="password" />
      ) : (
        <Caixa marcada={confirmo} aoMudar={setConfirmo} corMarca={cor.errado}>
          Percebo que a conta é apagada para sempre.
        </Caixa>
      )}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <Botao larguraTotal onPress={aoFechar}>
        Manter a conta
      </Botao>
      <Botao tipo="perigo" larguraTotal carregando={isLoading} disabled={temSenha ? !senha : !confirmo} onPress={() => void enviar()}>
        {isLoading ? "A apagar…" : "Apagar a conta para sempre"}
      </Botao>
    </Folha>
  );
}
