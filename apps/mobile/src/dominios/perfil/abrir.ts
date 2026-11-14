import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { SITE_URL } from "@/api/config";
import { destinoDaLigacao } from "@/lib/rotasWeb";

/** Abre uma ligação vinda da API (notificação, push): rota da app ou página do site no browser. */
export async function abrirLigacao(ligacao?: string | null) {
  const d = destinoDaLigacao(ligacao);
  if (!d) return;
  if (d.tipo === "app") router.push(d.rota);
  else await WebBrowser.openBrowserAsync(d.url).catch(() => {});
}

/** Abre uma página pública do site (privacidade, termos) no browser da app. */
export function abrirSite(caminho: string) {
  return WebBrowser.openBrowserAsync(`${SITE_URL}${caminho}`).catch(() => {});
}
