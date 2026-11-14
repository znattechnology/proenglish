"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";
import { Botao } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";

/** Mensagem de um erro do Django, venha ele em `error`, `detail`, `message` ou por campo. */
export function erroDjango(e: unknown, padrao = "Não foi possível concluir. Tente outra vez.") {
  return mensagemErro(e, padrao);
}

/** Erros por campo devolvidos pelo Django (`{email: [...]}` ou `{details: {email: [...]}}`), para mostrar junto de cada campo. */
export function errosPorCampo(e: unknown): Record<string, string> {
  const d = (e as { data?: unknown } | undefined)?.data as Record<string, unknown> | undefined;
  if (!d || typeof d !== "object") return {};
  const fonte = d.details && typeof d.details === "object" ? (d.details as Record<string, unknown>) : d;
  const r: Record<string, string> = {};
  for (const [k, v] of Object.entries(fonte)) {
    const m = typeof v === "string" ? v : Array.isArray(v) && typeof v[0] === "string" ? v[0] : null;
    if (m && !["error", "detail", "message", "code", "codigo", "mensagem", "non_field_errors"].includes(k)) r[k] = m;
  }
  return r;
}

/** Só caminhos internos ("/user/..."), para o ?redirect= não levar a pessoa para outro site. */
export function destinoSeguro(v: string | null | undefined) {
  if (!v || !v.startsWith("/")) return null;
  // Resolve como o browser resolveria: "/%09/site" ou "/\\site" viram outro domínio e são recusados.
  let u: URL;
  try {
    const base = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    u = new URL(v, base);
    if (u.origin !== base) return null;
  } catch {
    return null;
  }
  if (u.pathname.startsWith("//")) return null;
  if (["/signin", "/signup", "/verify-email", "/forgot-password", "/auth/"].some((p) => u.pathname.startsWith(p))) return null;
  return u.pathname + u.search + u.hash;
}

export function destinoPorPapel(papel?: string) {
  if (papel === "teacher") return "/teacher/dashboard";
  if (papel === "admin") return "/admin/dashboard";
  return "/user/dashboard";
}

/** Campo da palavra-passe com o botão "Mostrar". */
export const CampoSenha = React.forwardRef<
  HTMLInputElement,
  { rotulo: string; ajuda?: React.ReactNode; erro?: string } & Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "className">
>(({ rotulo, ajuda, erro, id, ...props }, ref) => {
  const gerado = React.useId();
  const campoId = id ?? gerado;
  const [ver, setVer] = React.useState(false);
  const descrito = erro ? `${campoId}-erro` : ajuda ? `${campoId}-ajuda` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={campoId} className="font-pe-texto text-pe-rotulo text-pe-tinta">
        {rotulo}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={campoId}
          type={ver ? "text" : "password"}
          aria-invalid={erro ? true : undefined}
          aria-describedby={descrito}
          className="h-12 w-full rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo pl-3 pr-12 font-pe-texto text-[16px] text-pe-tinta aria-[invalid=true]:border-2 aria-[invalid=true]:border-pe-errado"
          {...props}
        />
        <button
          type="button"
          onClick={() => setVer((v) => !v)}
          aria-label={ver ? "Esconder a palavra-passe" : "Mostrar a palavra-passe"}
          aria-pressed={ver}
          className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-pe-sm bg-transparent text-pe-tinta-suave hover:text-pe-tinta"
        >
          {ver ? <EyeOff aria-hidden className="size-5" /> : <Eye aria-hidden className="size-5" />}
        </button>
      </div>
      {erro ? (
        <p id={`${campoId}-erro`} className="m-0 text-pe-legenda font-semibold text-pe-errado">
          {erro}
        </p>
      ) : ajuda ? (
        <p id={`${campoId}-ajuda`} className="m-0 text-pe-legenda text-pe-tinta-suave">
          {ajuda}
        </p>
      ) : null}
    </div>
  );
});
CampoSenha.displayName = "CampoSenha";

/** Código de 6 algarismos num só campo: funciona com colar e com o preenchimento automático do telemóvel. */
export function CampoCodigo({ valor, aoMudar, erro, rotulo = "Código de 6 algarismos", autoFocus }: { valor: string; aoMudar: (v: string) => void; erro?: string; rotulo?: string; autoFocus?: boolean }) {
  const id = React.useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-pe-texto text-pe-rotulo text-pe-tinta">
        {rotulo}
      </label>
      <input
        id={id}
        value={valor}
        onChange={(e) => aoMudar(e.target.value.replace(/\D/g, "").slice(0, 6))}
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]{6}"
        maxLength={6}
        autoFocus={autoFocus}
        aria-invalid={erro ? true : undefined}
        aria-describedby={erro ? `${id}-erro` : undefined}
        placeholder="000000"
        className="h-14 w-full max-w-[260px] rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-4 font-pe-titulo text-[26px] font-bold tracking-[0.35em] tabular-nums text-pe-tinta placeholder:text-pe-linha aria-[invalid=true]:border-2 aria-[invalid=true]:border-pe-errado"
      />
      {erro ? (
        <p id={`${id}-erro`} className="m-0 text-pe-legenda font-semibold text-pe-errado">
          {erro}
        </p>
      ) : null}
    </div>
  );
}

export function Ou() {
  return (
    <div aria-hidden className="flex items-center gap-3 text-[14px] leading-5 text-pe-tinta-suave">
      <span className="h-px flex-1 bg-pe-linha" />
      ou
      <span className="h-px flex-1 bg-pe-linha" />
    </div>
  );
}

/** O "G" do Google nas cores da marca deles: é a forma que as pessoas reconhecem. */
function IconeGoogle() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-5">
      <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.7z" />
      <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1A12 12 0 0 0 12 24z" />
      <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6h-4a12 12 0 0 0 0 10.8z" />
      <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9z" />
    </svg>
  );
}

export function BotaoGoogle({ texto, aoCarregar, aCarregar }: { texto: string; aoCarregar: () => void; aCarregar?: boolean }) {
  return (
    <Botao type="button" tipo="secundario" larguraTotal onClick={aoCarregar} disabled={aCarregar}>
      <IconeGoogle />
      {aCarregar ? "A abrir o Google…" : texto}
    </Botao>
  );
}

export function Titulo({ titulo, texto, passo }: { titulo: string; texto?: React.ReactNode; passo?: string }) {
  return (
    <div className="flex flex-col gap-2">
      {passo ? <span className="text-[14px] font-semibold leading-5 text-pe-tinta-suave">{passo}</span> : null}
      <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tracking-[-0.01em] md:text-[32px] md:leading-10">{titulo}</h1>
      {texto ? <p className={cnPe("m-0 text-pe-tinta-suave")}>{texto}</p> : null}
    </div>
  );
}
