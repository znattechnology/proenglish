"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Aviso, Botao, Campo } from "@/components/pe";
import { useLazyGetGoogleOAuthUrlQuery, useLoginMutation } from "@/src/domains/auth/services/authApi";
import { BotaoGoogle, CampoSenha, Ou, Titulo, destinoPorPapel, destinoSeguro, erroDjango } from "./Partes";

/** Parâmetros que passam de uma página de conta para a outra (plano escolhido, curso, destino). */
export function manterParametros(sp: URLSearchParams, extra: Record<string, string> = {}) {
  const p = new URLSearchParams();
  for (const k of ["redirect", "plan", "id", "showSignUp"]) {
    const v = sp.get(k);
    if (v) p.set(k, v);
  }
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Para onde vai a pessoa depois de entrar. */
export function destinoDepoisDeEntrar(sp: URLSearchParams, papel?: string) {
  const redirect = destinoSeguro(sp.get("redirect"));
  if (redirect) return redirect;
  const curso = sp.get("id");
  if (curso && sp.get("showSignUp") !== null) return `/user/courses/${curso}`;
  const plano = sp.get("plan");
  if (plano && (!papel || papel === "student")) return `/user/upgrade?plan=${encodeURIComponent(plano)}`;
  return destinoPorPapel(papel);
}

export function useEntrarComGoogle() {
  const [pedirUrl] = useLazyGetGoogleOAuthUrlQuery();
  const [aAbrir, setAAbrir] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const abrir = async (sp: URLSearchParams) => {
    setErro(null);
    setAAbrir(true);
    try {
      // Guarda o destino: o Google volta para /auth/google/callback sem os nossos parâmetros.
      try {
        sessionStorage.setItem("pe_destino_google", manterParametros(sp));
      } catch {}
      const r = await pedirUrl().unwrap();
      if (!r.auth_url) throw new Error("sem url");
      window.location.href = r.auth_url;
    } catch {
      setAAbrir(false);
      setErro("Não foi possível abrir o Google. Tente outra vez ou entre com o email.");
    }
  };
  return { abrir, aAbrir, erro };
}

export function Entrar() {
  const router = useRouter();
  const sp = useSearchParams();
  const [email, setEmail] = useState(sp.get("email") ?? "");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [entrar, { isLoading }] = useLoginMutation();
  const google = useEntrarComGoogle();
  const sessaoTerminou = sp.get("reason") === "session_expired";
  const senhaMudou = sp.get("senha") === "alterada";

  return (
    <>
      <Titulo titulo="Entrar na sua conta" texto="Retome a lição onde parou." />
      {sessaoTerminou ? <Aviso tipo="info">A sua sessão terminou. Entre outra vez para continuar.</Aviso> : null}
      {senhaMudou ? <Aviso tipo="certo">A palavra-passe foi alterada. Entre com a nova.</Aviso> : null}
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          if (!email.trim() || !senha) return setErro("Escreva o email e a palavra-passe.");
          try {
            const r = await entrar({ email: email.trim().toLowerCase(), password: senha }).unwrap();
            router.replace(destinoDepoisDeEntrar(sp, r.user?.role));
          } catch (er) {
            const m = erroDjango(er, "O email ou a palavra-passe não estão certos.");
            if (/verificad|verified/i.test(m)) {
              router.push(`/verify-email${manterParametros(sp, { email: email.trim().toLowerCase(), de: "entrar" })}`);
              return;
            }
            if ((er as { status?: number })?.status === 403) return setErro("Tentou muitas vezes seguidas. Espere um minuto e tente outra vez.");
            setErro(/inválid|invalid|credenciais/i.test(m) ? "O email ou a palavra-passe não estão certos." : m);
          }
        }}
      >
        <Campo rotulo="Email" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus={!email} />
        <div className="flex flex-col">
          <CampoSenha rotulo="Palavra-passe" autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} required autoFocus={!!email} />
          <Link href={`/forgot-password${manterParametros(sp, email ? { email } : {})}`} className="self-start py-3 text-[15px] font-semibold leading-5 text-pe-azul-marca underline-offset-[3px]">
            Esqueci-me da palavra-passe
          </Link>
        </div>
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <Botao type="submit" larguraTotal disabled={isLoading}>
          {isLoading ? "A entrar…" : "Entrar"}
        </Botao>
      </form>
      <Ou />
      {google.erro ? <Aviso tipo="errado">{google.erro}</Aviso> : null}
      <BotaoGoogle texto="Entrar com o Google" aoCarregar={() => google.abrir(sp)} aCarregar={google.aAbrir} />
      <p className="m-0 text-pe-tinta-suave">
        Ainda não tem conta?{" "}
        <Link href={`/signup${manterParametros(sp)}`} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
          Criar conta grátis
        </Link>
      </p>
    </>
  );
}
