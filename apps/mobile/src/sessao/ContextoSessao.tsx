/**
 * Sessão da pessoa na app: carrega o refresh do cofre ao abrir, entra, sai e termina quando a API
 * recusa a renovação. Só estudantes usam a app; professores e administradores vêem um aviso.
 */
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, aoPedirMudarSenha, aoTerminarSessao, pedir, renovarSessao } from "@/api/base";
import { tokens } from "@/api/tokens";
import { store } from "@/lib/store";

export type Utilizador = {
  id: string;
  email: string;
  name: string;
  role: "student" | "teacher" | "admin";
  avatar?: string | null;
  phone?: string | null;
  provincia?: string | null;
  email_verified: boolean;
  has_password?: boolean;
  deve_mudar_senha?: boolean;
  preferences?: Record<string, unknown>;
  created_at?: string;
};

export type RespostaSessao = { user?: Utilizador; tokens?: { access: string; refresh: string | null } };

type Estado = "a-carregar" | "sem-sessao" | "com-sessao";

type Contexto = {
  estado: Estado;
  utilizador: Utilizador | null;
  /** A sessão terminou sozinha (refresh expirado): o ecrã de entrada mostra o aviso "Sessão terminada". */
  terminouSozinha: boolean;
  /** Guarda a sessão devolvida por login, verificação de email, Google, etc. */
  iniciar: (r: RespostaSessao) => Promise<void>;
  entrar: (email: string, senha: string) => Promise<{ ok: true } | { ok: false; erro: unknown; status: number }>;
  sair: () => Promise<void>;
  actualizarUtilizador: () => Promise<void>;
};

const Ctx = createContext<Contexto | null>(null);

export function SessaoProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>("a-carregar");
  const [utilizador, setUtilizador] = useState<Utilizador | null>(null);
  const [terminouSozinha, setTerminouSozinha] = useState(false);

  const limparTudo = useCallback(async () => {
    await tokens.limpar();
    store.dispatch(api.util.resetApiState());
    setUtilizador(null);
    setEstado("sem-sessao");
  }, []);

  const carregarPerfil = useCallback(async () => {
    const r = await pedir<Utilizador>("/users/profile/");
    if (r.ok && r.data) {
      setUtilizador(r.data);
      return r.data;
    }
    return null;
  }, []);

  // Ao abrir: há refresh no cofre? Renova e carrega o perfil.
  useEffect(() => {
    (async () => {
      const refresh = await tokens.carregar();
      if (!refresh) return setEstado("sem-sessao");
      const ok = await renovarSessao();
      if (!ok && !tokens.refresh) return setEstado("sem-sessao");
      const u = await carregarPerfil();
      // Sem rede: mantém a sessão (o refresh continua válido) e tenta outra vez mais tarde.
      setEstado(u || tokens.refresh ? "com-sessao" : "sem-sessao");
    })();
  }, [carregarPerfil]);

  useEffect(() => {
    const parar = aoTerminarSessao(() => {
      setTerminouSozinha(true);
      void limparTudo();
    });
    return () => {
      parar();
    };
  }, [limparTudo]);

  // A meio da sessão: 403 mudar_senha → recarregar o perfil (deve_mudar_senha) para mostrar o ecrã obrigatório.
  useEffect(() => {
    const parar = aoPedirMudarSenha(() => void carregarPerfil());
    return () => {
      parar();
    };
  }, [carregarPerfil]);

  const iniciar = useCallback(
    async (r: RespostaSessao) => {
      if (!r.tokens?.access) throw new Error("Resposta sem sessão");
      await tokens.definir({ access: r.tokens.access, refresh: r.tokens.refresh });
      setTerminouSozinha(false);
      // O `user` do login/Google não traz as preferências: carregar sempre o perfil completo
      // (a primeira entrada e outras decisões dependem delas). O `user` só serve se o perfil falhar.
      const perfil = await carregarPerfil();
      if (!perfil && r.user) setUtilizador(r.user);
      setEstado("com-sessao");
    },
    [carregarPerfil]
  );

  const entrar = useCallback<Contexto["entrar"]>(
    async (email, senha) => {
      const r = await pedir<RespostaSessao>("/users/login/", { method: "POST", body: JSON.stringify({ email: email.trim().toLowerCase(), password: senha }) });
      if (!r.ok) return { ok: false, erro: { status: r.status, data: r.data }, status: r.status };
      await iniciar(r.data);
      return { ok: true };
    },
    [iniciar]
  );

  const sair = useCallback(async () => {
    const refresh = tokens.refresh;
    if (refresh) await pedir("/users/logout/", { method: "POST", body: JSON.stringify({ refresh }) }).catch(() => {});
    setTerminouSozinha(false);
    await limparTudo();
  }, [limparTudo]);

  const actualizarUtilizador = useCallback(async () => {
    await carregarPerfil();
  }, [carregarPerfil]);

  const valor = useMemo(() => ({ estado, utilizador, terminouSozinha, iniciar, entrar, sair, actualizarUtilizador }), [estado, utilizador, terminouSozinha, iniciar, entrar, sair, actualizarUtilizador]);
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

export function useSessao() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSessao fora do SessaoProvider");
  return c;
}

/** Primeiro nome para saudações ("Bom dia, Maria"). */
export function primeiroNome(nome?: string | null) {
  return (nome ?? "").trim().split(/\s+/)[0] ?? "";
}
