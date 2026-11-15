/**
 * Envio de ficheiros do professor (vídeo da aula, materiais, capa).
 * 1. Pede à API onde pôr o ficheiro (S3 em produção, o próprio servidor em desenvolvimento).
 * 2. Envia os bytes com progresso.
 * 3. Confirma, e a API liga o ficheiro à aula, ao material ou ao curso.
 */
const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";
const ORIGEM_API = new URL(API).origin;

export type AlvoEnvio = { tipo: "video"; aula: string } | { tipo: "material"; aula: string } | { tipo: "capa"; curso: string } | { tipo: "fotografia" };

type Pedido = { modo: "s3" | "local"; upload_url: string; metodo: "PUT" | "POST"; cabecalhos?: Record<string, string>; chave?: string; token?: string };

function caminhoInicio(a: AlvoEnvio) {
  if (a.tipo === "video") return `/teacher/aulas/${a.aula}/video/`;
  if (a.tipo === "material") return `/teacher/aulas/${a.aula}/materiais/`;
  if (a.tipo === "fotografia") return "/teacher/perfil/fotografia/enviar/";
  return `/teacher/cursos/${a.curso}/capa/`;
}

async function pedirJson<T>(caminho: string, corpo: unknown): Promise<T> {
  const r = await fetch(`${API}${caminho}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw { status: r.status, data: dados };
  return dados as T;
}

function enviarBytes(p: Pedido, ficheiro: File, aoProgredir?: (f: number) => void, sinal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = p.upload_url.startsWith("/") ? `${ORIGEM_API}${p.upload_url}` : p.upload_url;
    xhr.open(p.metodo, url);
    if (p.modo === "local") xhr.withCredentials = true;
    for (const [k, v] of Object.entries(p.cabecalhos ?? {})) xhr.setRequestHeader(k, v);
    if (!p.cabecalhos || !Object.keys(p.cabecalhos).some((k) => k.toLowerCase() === "content-type")) xhr.setRequestHeader("Content-Type", ficheiro.type || "application/octet-stream");
    xhr.upload.onprogress = (e) => e.lengthComputable && aoProgredir?.(e.loaded / e.total);
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject({ status: xhr.status, data: { message: "O envio do ficheiro falhou. Tente outra vez." } }));
    xhr.onerror = () => reject({ status: 0, data: { message: "Sem ligação. Verifique a Internet e tente outra vez." } });
    xhr.onabort = () => reject({ status: 0, data: { message: "Envio cancelado." }, cancelado: true });
    sinal?.addEventListener("abort", () => xhr.abort());
    xhr.send(ficheiro);
  });
}

export async function enviarFicheiro<T = unknown>(alvo: AlvoEnvio, ficheiro: File, aoProgredir?: (f: number) => void, sinal?: AbortSignal): Promise<T> {
  const p = await pedirJson<Pedido>(caminhoInicio(alvo), { nome: ficheiro.name, tamanho_bytes: ficheiro.size, tipo_mime: ficheiro.type || "application/octet-stream" });
  await enviarBytes(p, ficheiro, aoProgredir, sinal);
  return pedirJson<T>("/teacher/envios/confirmar/", { chave: p.chave ?? p.token });
}

/** Duração de um vídeo escolhido no computador, lida pelo browser antes de enviar. */
export function duracaoDoVideo(ficheiro: File): Promise<number | null> {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    const url = URL.createObjectURL(ficheiro);
    const fim = (d: number | null) => {
      URL.revokeObjectURL(url);
      resolve(d);
    };
    v.onloadedmetadata = () => fim(Number.isFinite(v.duration) ? Math.round(v.duration) : null);
    v.onerror = () => fim(null);
    v.src = url;
  });
}

/** "8:40" */
export function minSeg(s: number | null | undefined) {
  if (s == null) return null;
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.round(s % 60)).padStart(2, "0")}`;
}

/** "8 min 40 s" */
export function duracaoPorExtenso(s: number | null | undefined) {
  if (s == null) return null;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return [m ? `${m} min` : null, r ? `${r} s` : null].filter(Boolean).join(" ") || "0 s";
}

/** "180 KB", "2,1 MB" */
export function tamanho(b: number | null | undefined) {
  if (b == null) return null;
  if (b < 1024 * 1024) return `${Math.max(1, Math.round(b / 1024))} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toLocaleString("pt-PT", { maximumFractionDigits: 1 })} MB`;
  return `${(b / 1024 ** 3).toLocaleString("pt-PT", { maximumFractionDigits: 1 })} GB`;
}
