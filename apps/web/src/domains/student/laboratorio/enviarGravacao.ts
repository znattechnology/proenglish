/**
 * Envia uma gravação (multipart) com fetch próprio — a base das fatias força JSON — e, como os outros
 * pedidos (sharedBaseQuery), renova a sessão e tenta uma vez quando a resposta é 401.
 * Usado pela revisão, pelas lições (pronúncia e Responder).
 */
import type { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import { tokenRefreshCoordinator } from "@/lib/token-refresh-coordinator";

type Resultado<T> = { data: T; error?: undefined } | { error: FetchBaseQueryError; data?: undefined };

export async function enviarGravacao<T>(url: string, corpo: () => FormData): Promise<Resultado<T>> {
  const enviar = () => fetch(url, { method: "POST", body: corpo(), credentials: "include" });
  try {
    let r = await enviar();
    if (r.status === 401) {
      try {
        await tokenRefreshCoordinator.refreshToken();
      } catch {
        tokenRefreshCoordinator.clearTokens();
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- recarregar a página toda limpa o estado da sessão
        window.location.href = "/signin?reason=session_expired";
        return { error: { status: 401, data: { message: "Session expired" } } };
      }
      r = await enviar();
    }
    const dados = await r.json().catch(() => ({}));
    return r.ok ? { data: dados as T } : { error: { status: r.status, data: dados } };
  } catch (e) {
    return { error: { status: "FETCH_ERROR", error: String(e) } };
  }
}
