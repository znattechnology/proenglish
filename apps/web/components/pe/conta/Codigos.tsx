"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Botao, Campo } from "@/components/pe";
import {
  useConfirmPasswordResetMutation,
  useLoginMutation,
  useRequestPasswordResetMutation,
  useResendVerificationCodeMutation,
  useVerifyEmailMutation,
} from "@/src/domains/auth/services/authApi";
import { destinoDepoisDeEntrar, manterParametros } from "./Entrar";
import { CampoCodigo, CampoSenha, Titulo, erroDjango } from "./Partes";

/** Contagem decrescente para "pedir outro código". */
function useEspera(inicial: number) {
  const [s, setS] = useState(inicial);
  useEffect(() => {
    if (s <= 0) return;
    const t = setTimeout(() => setS((x) => x - 1), 1000);
    return () => clearTimeout(t);
  }, [s]);
  return [s, setS] as const;
}

function segundosDoErro(e: unknown) {
  const n = (e as { data?: { aguardar_segundos?: number } })?.data?.aguardar_segundos;
  return typeof n === "number" ? n : null;
}

/* ------------------------------------------------------------------ */
/* Confirmar o email depois de criar a conta                           */
/* ------------------------------------------------------------------ */
export function VerificarEmail() {
  const router = useRouter();
  const sp = useSearchParams();
  const email = sp.get("email") ?? "";
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  // Vindo de "Entrar", nenhum código acabou de ser enviado: pode pedir um logo.
  const deEntrar = sp.get("de") === "entrar";
  const [espera, setEspera] = useEspera(deEntrar ? 0 : 60);
  const [verificar, { isLoading }] = useVerifyEmailMutation();
  const [reenviar, { isLoading: aReenviar }] = useResendVerificationCodeMutation();

  if (!email)
    return (
      <>
        <Titulo titulo="Confirme o seu email" texto="Não sabemos que email quer confirmar." />
        <Botao asChild larguraTotal>
          <Link href="/signin">Voltar à entrada</Link>
        </Botao>
      </>
    );

  return (
    <>
      <Titulo
        titulo="Confirme o seu email"
        texto={
          deEntrar ? (
            <>
              A conta <strong className="font-semibold text-pe-tinta">{email}</strong> ainda não foi confirmada. Use o código que recebeu por email ou peça um novo.
            </>
          ) : (
            <>
              Enviámos um código de 6 algarismos para <strong className="font-semibold text-pe-tinta">{email}</strong>. Vale durante 30 minutos.
            </>
          )
        }
      />
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          if (codigo.length !== 6) return setErro("O código tem 6 algarismos.");
          try {
            const r = await verificar({ email, code: codigo }).unwrap();
            router.replace(destinoDepoisDeEntrar(sp, r.user?.role));
          } catch (er) {
            setErro(erroDjango(er, "O código não está certo. Confirme e tente outra vez."));
          }
        }}
      >
        <CampoCodigo rotulo="Código de verificação" valor={codigo} aoMudar={setCodigo} erro={erro ?? undefined} autoFocus />
        <Botao type="submit" larguraTotal disabled={isLoading}>
          {isLoading ? "A confirmar…" : "Confirmar email"}
        </Botao>
      </form>
      <div className="flex flex-col gap-1 text-[15px] leading-[22px]">
        <p className="m-0 text-pe-tinta-suave">Não recebeu? Veja na pasta de spam.</p>
        {espera > 0 ? (
          <p className="m-0 text-pe-tinta-suave" aria-live="polite">
            Pode pedir outro código daqui a {espera} {espera === 1 ? "segundo" : "segundos"}.
          </p>
        ) : (
          <button
            type="button"
            disabled={aReenviar}
            onClick={async () => {
              setErro(null);
              setAviso(null);
              try {
                const r = await reenviar({ email }).unwrap();
                setAviso("Enviámos um código novo. O anterior deixa de servir.");
                setEspera((r as { aguardar_segundos?: number }).aguardar_segundos ?? 60);
              } catch (er) {
                const s = segundosDoErro(er);
                if (s) setEspera(s);
                else setErro(erroDjango(er, "Não foi possível enviar outro código."));
              }
            }}
            className="min-h-11 self-start bg-transparent px-0 text-left font-semibold text-pe-azul-marca underline underline-offset-[3px]"
          >
            {aReenviar ? "A enviar…" : deEntrar ? "Enviar um código novo" : "Enviar outro código"}
          </button>
        )}
        {aviso ? <Aviso tipo="certo">{aviso}</Aviso> : null}
        <Link href={`/signup${manterParametros(sp, { email })}`} className="min-h-11 self-start py-2.5 font-semibold text-pe-azul-marca underline-offset-[3px]">
          Mudar o endereço de email
        </Link>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Recuperar a palavra-passe: pedir o código e criar uma nova          */
/* ------------------------------------------------------------------ */
export function RecuperarSenha() {
  const router = useRouter();
  const sp = useSearchParams();
  const [email, setEmail] = useState(sp.get("email") ?? "");
  const [passo, setPasso] = useState<1 | 2>(1);
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [erroRepetir, setErroRepetir] = useState<string | undefined>();
  const [aviso, setAviso] = useState<string | null>(null);
  const [espera, setEspera] = useEspera(0);
  const [pedir, { isLoading: aPedir }] = useRequestPasswordResetMutation();
  const [confirmar, { isLoading: aConfirmar }] = useConfirmPasswordResetMutation();
  const [entrar, { isLoading: aEntrar }] = useLoginMutation();

  const pedirCodigo = async (): Promise<boolean> => {
    setErro(null);
    const mail = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
      setErro("Escreva o email da sua conta.");
      return false;
    }
    try {
      await pedir({ email: mail }).unwrap();
      setEmail(mail);
      setPasso(2);
      setEspera(60);
      return true;
    } catch (er) {
      const st = (er as { status?: number })?.status;
      setErro(st === 403 || st === 429 ? "Pediu muitos códigos seguidos. Espere um minuto e tente outra vez." : erroDjango(er, "Não foi possível enviar o código. Tente outra vez."));
      return false;
    }
  };

  if (passo === 1)
    return (
      <>
        <Titulo passo="Passo 1 de 2" titulo="Esqueceu-se da palavra-passe?" texto="Escreva o email da sua conta. Enviamos-lhe um código para criar uma palavra-passe nova." />
        <form
          noValidate
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            void pedirCodigo();
          }}
        >
          <Campo rotulo="Email" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <Botao type="submit" larguraTotal disabled={aPedir}>
            {aPedir ? "A enviar…" : "Enviar código"}
          </Botao>
        </form>
        <p className="m-0 text-pe-tinta-suave">
          Lembrou-se?{" "}
          <Link href={`/signin${manterParametros(sp, email ? { email } : {})}`} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
            Voltar à entrada
          </Link>
        </p>
      </>
    );

  const ocupado = aConfirmar || aEntrar;
  return (
    <>
      <Titulo
        passo="Passo 2 de 2"
        titulo="Crie uma palavra-passe nova"
        texto={
          <>
            Se houver uma conta com <strong className="font-semibold text-pe-tinta">{email}</strong>, o código já foi para lá. Vale durante 30 minutos.
          </>
        }
      />
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          setErroRepetir(undefined);
          if (codigo.length !== 6) return setErro("O código tem 6 algarismos.");
          if (senha.length < 8) return setErro("A palavra-passe nova precisa de 8 caracteres ou mais.");
          if (senha !== repetir) return setErroRepetir("As duas palavras-passe são diferentes.");
          try {
            await confirmar({ email, code: codigo, newPassword: senha }).unwrap();
          } catch (er) {
            return setErro(erroDjango(er, "Não foi possível guardar a palavra-passe. Tente outra vez."));
          }
          try {
            const r = await entrar({ email, password: senha }).unwrap();
            router.replace(destinoDepoisDeEntrar(sp, r.user?.role));
          } catch {
            router.replace(`/signin${manterParametros(sp, { email, senha: "alterada" })}`);
          }
        }}
      >
        <div className="flex flex-col gap-1">
          <CampoCodigo valor={codigo} aoMudar={setCodigo} autoFocus />
          {espera > 0 ? (
            <span className="text-[14px] leading-5 text-pe-tinta-suave" aria-live="polite">
              Pode pedir outro código daqui a {espera} {espera === 1 ? "segundo" : "segundos"}.
            </span>
          ) : (
            <button
              type="button"
              disabled={aPedir}
              onClick={async () => {
                setAviso(null);
                if (await pedirCodigo()) setAviso("Enviámos outro código. O anterior deixa de servir.");
              }}
              className="min-h-11 self-start bg-transparent px-0 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]"
            >
              Enviar outro código
            </button>
          )}
          {aviso ? <Aviso tipo="certo">{aviso}</Aviso> : null}
        </div>
        <CampoSenha rotulo="Palavra-passe nova" autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} ajuda="Tem 8 caracteres ou mais" required />
        <CampoSenha rotulo="Repita a palavra-passe nova" autoComplete="new-password" value={repetir} onChange={(e) => setRepetir(e.target.value)} erro={erroRepetir} required />
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <Botao type="submit" larguraTotal disabled={ocupado}>
          {ocupado ? "A guardar…" : "Guardar e entrar"}
        </Botao>
      </form>
      <button type="button" onClick={() => setPasso(1)} className="min-h-11 self-start bg-transparent px-0 font-semibold text-pe-azul-marca underline underline-offset-[3px]">
        Usar outro email
      </button>
    </>
  );
}
