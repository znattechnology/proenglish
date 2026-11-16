/**
 * Converte as ligações da web (as que a API põe nas notificações: "/user/billing",
 * "/user/courses/<id>/chapters/<cap>", ...) nas rotas da app (mapa de rotas do BRIEF).
 * Serve às notificações na app e às notificações push.
 *
 *   destinoDaLigacao("/user/upgrade?plan=PREMIUM") → { tipo: "app", rota: "/checkout/PREMIUM" }
 *   destinoDaLigacao("/privacidade")               → { tipo: "externo", url: "<SITE_URL>/privacidade" }
 */
import { SITE_URL } from "@/api/config";

export type Destino = { tipo: "app"; rota: string } | { tipo: "externo"; url: string };

/** Parâmetros de consulta (o URLSearchParams do React Native é incompleto). */
type Consulta = Record<string, string>;
function lerConsulta(texto: string): Consulta {
  const q: Consulta = {};
  for (const par of texto.split("&")) {
    if (!par) continue;
    const [k, v = ""] = par.split("=");
    try {
      q[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, " "));
    } catch {
      q[k] = v;
    }
  }
  return q;
}
export function escreverConsulta(q: Record<string, string | null | undefined>) {
  const s = Object.entries(q)
    .filter(([, v]) => v)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v!)}`)
    .join("&");
  return s ? `?${s}` : "";
}

type Regra = [RegExp, (m: RegExpMatchArray, q: Consulta, ancora: string) => string];

const REGRAS: Regra[] = [
  [/^\/user\/?$/, () => "/inicio"],
  [/^\/user\/dashboard\/?$/, () => "/inicio"],
  [/^\/user\/primeira-entrada\/?$/, () => "/primeira-entrada"],
  // Cursos em vídeo
  [/^\/user\/courses\/?$/, () => "/cursos"],
  [/^\/user\/courses\/explore\/?$/, () => "/cursos/explorar"],
  [/^\/user\/courses\/([^/]+)\/chapters\/([^/]+)\/?$/, (m) => `/curso/${m[1]}/aula/${m[2]}`],
  [/^\/user\/courses\/([^/]+)\/exame\/?$/, (m) => `/curso/${m[1]}/exame`],
  [/^\/user\/courses\/([^/]+)\/grades\/?$/, (m) => `/curso/${m[1]}/notas`],
  [/^\/user\/courses\/([^/]+)\/?$/, (m) => `/curso/${m[1]}`],
  [/^\/user\/grades\/?$/, () => "/notas"],
  [/^\/user\/certificates\/?$/, () => "/certificados"],
  // Laboratório
  [/^\/user\/laboratory(\/learn(\/lesson)?)?\/?$/, () => "/praticar"],
  [/^\/user\/laboratory\/learn\/courses\/?$/, () => "/lab/escolher-curso"],
  [/^\/user\/laboratory\/learn\/shop\/?$/, () => "/lab/loja"],
  [/^\/user\/laboratory\/learn\/lesson\/([^/]+)\/?$/, (m) => `/licao/${m[1]}`],
  [/^\/user\/laboratory\/review\/?$/, () => "/revisao"],
  [/^\/user\/teste-basico\/?$/, () => "/teste-basico"],
  [/^\/user\/laboratory\/achievements\/?$/, (_m, _q, ancora) => (ancora === "liga" ? "/liga" : "/conquistas")],
  [/^\/user\/laboratory\/leaderboard\/?$/, () => "/liga"],
  // Conversa
  [/^\/user\/laboratory\/speaking(\/real-time)?\/?$/, () => "/conversa"],
  [/^\/user\/laboratory\/speaking\/progress\/?$/, () => "/conversa/progresso"],
  [/^\/user\/laboratory\/speaking\/summary\/([^/]+)\/?$/, (m) => `/conversa/resumo/${m[1]}`],
  // Perfil, subscrição e pagamentos
  [/^\/user\/profile\/?$/, () => "/perfil"],
  [/^\/user\/settings\/?$/, () => "/definicoes"],
  [/^\/user\/analytics\/?$/, () => "/estatisticas"],
  [/^\/user\/notifications\/?$/, () => "/notificacoes"],
  [/^\/user\/subscription\/?$/, () => "/subscricao"],
  [/^\/user\/billing\/?$/, (_m, q) => `/recibos${escreverConsulta({ recibo: q.recibo })}`],
  [/^\/user\/feedback\/?$/, (_m, q) => `/opiniao${escreverConsulta({ trigger: q.trigger, chave: q.chave })}`],
  [
    /^\/user\/upgrade\/?$/,
    (_m, q) => {
      const plano = (q.plan ?? "").toUpperCase();
      const s = escreverConsulta({ periodo: q.periodo, codigo: q.codigo });
      return plano && plano !== "FREE" ? `/checkout/${plano}${s}` : `/planos${s}`;
    },
  ],
];

/** Para onde leva uma ligação vinda da API. null quando a ligação está vazia. */
export function destinoDaLigacao(ligacao?: string | null): Destino | null {
  const l = (ligacao ?? "").trim();
  if (!l) return null;
  // Ligação absoluta para o próprio site: trata-se como caminho; para outro sítio: abre no browser.
  let caminho = l;
  if (/^https?:\/\//i.test(l)) {
    if (!l.startsWith(SITE_URL)) return { tipo: "externo", url: l };
    caminho = l.slice(SITE_URL.length) || "/";
  }
  if (!caminho.startsWith("/")) caminho = `/${caminho}`;
  const [semAncora, ancora = ""] = caminho.split("#");
  const [base, consulta = ""] = semAncora.split("?");
  const q = lerConsulta(consulta);
  for (const [re, f] of REGRAS) {
    const m = base.match(re);
    if (m) return { tipo: "app", rota: f(m, q, ancora) };
  }
  // Outras áreas do estudante sem ecrã na app: o início. Páginas públicas (privacidade, termos...): o site.
  if (base.startsWith("/user")) return { tipo: "app", rota: "/inicio" };
  return { tipo: "externo", url: `${SITE_URL}${caminho}` };
}
