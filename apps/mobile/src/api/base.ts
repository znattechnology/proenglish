/**
 * Base de todos os pedidos à API: Authorization: Bearer, X-Cliente: app (a API devolve a sessão no
 * corpo em vez de cookies) e renovação automática do access quando chega um 401.
 *
 * Os domínios (src/dominios/...) acrescentam endpoints com
 *   api.enhanceEndpoints({ addTagTypes: [...] }).injectEndpoints({ endpoints: (b) => ({...}) })
 * para haver um só reducer no store.
 */
import { type BaseQueryFn, createApi, type FetchArgs, fetchBaseQuery, type FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import { API_URL } from "./config";
import { tokens } from "./tokens";

const ouvintesFim = new Set<() => void>();
/** Chamado quando a sessão termina sem remédio (refresh inválido). O ContextoSessao ouve isto. */
export function aoTerminarSessao(f: () => void) {
  ouvintesFim.add(f);
  return () => ouvintesFim.delete(f);
}

const ouvintesMudarSenha = new Set<() => void>();
/** Chamado quando a API responde 403 `mudar_senha` (a administração pediu uma palavra-passe nova a meio da sessão). */
export function aoPedirMudarSenha(f: () => void) {
  ouvintesMudarSenha.add(f);
  return () => ouvintesMudarSenha.delete(f);
}

const cru = fetchBaseQuery({
  baseUrl: API_URL,
  timeout: 75_000,
  prepareHeaders: (h) => {
    h.set("X-Cliente", "app");
    h.set("Accept", "application/json");
    if (tokens.access && !h.has("Authorization")) h.set("Authorization", `Bearer ${tokens.access}`);
    return h;
  },
});

let renovacao: Promise<boolean> | null = null;

/** Renova o access com o refresh do cofre. Um só pedido de cada vez (os outros esperam por ele). */
export function renovarSessao(): Promise<boolean> {
  if (renovacao) return renovacao;
  renovacao = (async () => {
    const refresh = tokens.refresh ?? (await tokens.carregar());
    if (!refresh) return false;
    try {
      const r = await fetch(`${API_URL}/users/refresh-token/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Cliente": "app", Accept: "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!r.ok) {
        // 401/400: refresh expirado ou na lista negra. Outros (5xx) não terminam a sessão.
        if (r.status === 401 || r.status === 400) await tokens.limpar();
        return false;
      }
      const d = (await r.json()) as { tokens?: { access: string; refresh?: string | null } };
      if (!d.tokens?.access) return false;
      await tokens.definir({ access: d.tokens.access, refresh: d.tokens.refresh ?? null });
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    renovacao = null;
  });
  return renovacao;
}

export const baseQuery: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (args, api, extra) => {
  if (!tokens.access && tokens.refresh) await renovarSessao();
  let r = await cru(args, api, extra);
  if (r.error?.status === 401 && tokens.refresh) {
    const ok = await renovarSessao();
    if (ok) r = await cru(args, api, extra);
    else if (!tokens.refresh) ouvintesFim.forEach((f) => f());
  }
  if (r.error?.status === 403 && (r.error.data as { code?: string } | undefined)?.code === "mudar_senha") ouvintesMudarSenha.forEach((f) => f());
  return r;
};

export const api = createApi({
  reducerPath: "api",
  baseQuery,
  tagTypes: ["Perfil"],
  refetchOnReconnect: true,
  refetchOnFocus: true,
  endpoints: () => ({}),
});

/**
 * Pedido fora do RTK Query (envio de gravações em multipart, por exemplo), com a mesma
 * autenticação e renovação. Devolve {ok, status, data}.
 */
export async function pedir<T = unknown>(caminho: string, init: RequestInit = {}): Promise<{ ok: boolean; status: number; data: T }> {
  const fazer = () =>
    fetch(`${API_URL}${caminho}`, {
      ...init,
      headers: {
        Accept: "application/json",
        "X-Cliente": "app",
        ...(tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}),
        ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(init.headers as Record<string, string> | undefined),
      },
    });
  if (!tokens.access && tokens.refresh) await renovarSessao();
  let r = await fazer();
  if (r.status === 401 && tokens.refresh && (await renovarSessao())) r = await fazer();
  let data: unknown = null;
  try {
    data = await r.json();
  } catch {
    data = null;
  }
  return { ok: r.ok, status: r.status, data: data as T };
}
