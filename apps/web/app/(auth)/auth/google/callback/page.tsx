"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Aviso, Botao } from "@/components/pe";
import { destinoDepoisDeEntrar } from "@/components/pe/conta/Entrar";
import { Titulo, erroDjango } from "@/components/pe/conta/Partes";
import { useGoogleOAuthLoginMutation } from "@/src/domains/auth/services/authApi";

/** O Google volta para aqui com um código; trocamo-lo pela sessão no servidor. */
function VoltaDoGoogle() {
  const router = useRouter();
  const sp = useSearchParams();
  const [entrarGoogle] = useGoogleOAuthLoginMutation();
  // Erros que o Google já devolve no endereço (cancelar, falta do código).
  const [erro, setErro] = useState<string | null>(() =>
    sp.get("error") === "access_denied" ? "Cancelou a entrada com o Google." : sp.get("error") || !sp.get("code") ? "O Google não devolveu a autorização. Tente outra vez." : null
  );
  const [demora, setDemora] = useState(false);
  const feito = useRef(false); // o código só se pode usar uma vez (modo estrito monta duas vezes)

  useEffect(() => {
    const t = setTimeout(() => setDemora(true), 8000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (feito.current) return;
    feito.current = true;
    const code = sp.get("code");
    if (sp.get("error") || !code) return;
    let guardado = "";
    try {
      guardado = sessionStorage.getItem("pe_destino_google") ?? "";
      sessionStorage.removeItem("pe_destino_google");
    } catch {}
    entrarGoogle({ code, state: sp.get("state") ?? undefined }) // o servidor confirma que o pedido saiu daqui
      .unwrap()
      .then((r) => router.replace(destinoDepoisDeEntrar(new URLSearchParams(guardado), r.user?.role)))
      .catch((e) => setErro(erroDjango(e, "Não foi possível entrar com o Google. Tente outra vez.")));
  }, [entrarGoogle, router, sp]);

  if (erro)
    return (
      <>
        <Titulo titulo="Não foi possível entrar com o Google" />
        <Aviso tipo="errado">{erro}</Aviso>
        <Botao asChild larguraTotal>
          <Link href="/signin">Voltar à entrada</Link>
        </Botao>
      </>
    );

  return (
    <>
      <Titulo titulo="A entrar com o Google" texto="Estamos a confirmar a sua conta. Demora uns segundos." />
      <Loader2 aria-hidden className="size-8 text-pe-azul-marca motion-safe:animate-spin" />
      {demora ? (
        <p className="m-0 text-pe-tinta-suave" role="status">
          Está a demorar?{" "}
          <Link href="/signin" className="font-semibold text-pe-azul-marca underline-offset-[3px]">
            Voltar à entrada
          </Link>
        </p>
      ) : null}
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <VoltaDoGoogle />
    </Suspense>
  );
}
