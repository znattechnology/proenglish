"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Aviso, Botao, Campo } from "@/components/pe";
import { CampoCodigo, Titulo, erroDjango } from "./Partes";

const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";

/** A equipa ProEnglish mudou o email da conta: a pessoa confirma o endereço novo com o código que lá recebeu. */
export function ConfirmarEmailNovo() {
  const sp = useSearchParams();
  const [email, setEmail] = useState(sp.get("email") ?? "");
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aEnviar, setAEnviar] = useState(false);
  const [feito, setFeito] = useState(false);

  if (feito)
    return (
      <div className="flex flex-col gap-5">
        <Titulo titulo="Email confirmado" texto={`A partir de agora entra com ${email.trim().toLowerCase()}.`} />
        <Botao asChild>
          <Link href="/signin">Entrar</Link>
        </Botao>
      </div>
    );

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        setErro(null);
        if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setErro("Escreva o email novo.");
        if (codigo.length !== 6) return setErro("Escreva os 6 algarismos do código.");
        setAEnviar(true);
        try {
          const r = await fetch(`${API}/users/confirmar-email-novo/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email.trim().toLowerCase(), code: codigo }),
          });
          const dados = await r.json().catch(() => ({}));
          if (!r.ok) throw { status: r.status, data: dados };
          setFeito(true);
        } catch (x) {
          setErro(erroDjango(x, "O código não está certo ou já expirou."));
        } finally {
          setAEnviar(false);
        }
      }}
    >
      <Titulo titulo="Confirmar o email novo" texto="A equipa ProEnglish mudou o email da sua conta. Escreva o código que recebeu no endereço novo. Até confirmar, continua a entrar com o email antigo." />
      <Campo rotulo="Email novo" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <CampoCodigo valor={codigo} aoMudar={setCodigo} />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <Botao type="submit" larguraTotal disabled={aEnviar}>
        {aEnviar ? "A confirmar…" : "Confirmar o email"}
      </Botao>
    </form>
  );
}
