import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra ?? {}) as { apiUrl?: string; siteUrl?: string };

/** Endereço da API Django (…/api/v1). Em desenvolvimento num telemóvel físico, use o IP do computador. */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL || extra.apiUrl || "http://localhost:8000/api/v1").replace(/\/$/, "");

/** Site público (páginas legais, verificação de certificados). */
export const SITE_URL = (process.env.EXPO_PUBLIC_SITE_URL || extra.siteUrl || "http://localhost:3000").replace(/\/$/, "");

/** Endereço absoluto para ficheiros servidos pela API (/media/...). */
export function urlAbsoluto(caminho?: string | null) {
  if (!caminho) return null;
  if (/^https?:\/\//.test(caminho)) return caminho;
  const origem = API_URL.replace(/\/api\/v1$/, "");
  return `${origem}${caminho.startsWith("/") ? "" : "/"}${caminho}`;
}
