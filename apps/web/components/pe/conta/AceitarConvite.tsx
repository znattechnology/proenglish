"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Botao, Campo, Osso } from "@/components/pe";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { markAuthenticated } from "@/src/domains/auth/services/authApi";
import { CampoSenha, Titulo, erroDjango, errosPorCampo } from "./Partes";

const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";
type Convite = { nome: string; email: string; area: string; valido: boolean };

/** Um professor convidado cria aqui a conta, com a palavra-passe dele. */
export function AceitarConvite() {
  const { token } = useParams<{ token: string }>();
  const { checkAuth } = useDjangoAuth();
  const router = useRouter();
  const [convite, setConvite] = useState<Convite | null | "erro">(null);
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [aEnviar, setAEnviar] = useState(false);

  useEffect(() => {
    let vivo = true;
    fetch(`${API}/convites/${encodeURIComponent(token)}/`)
      .then(async (r) => (r.ok ? ((await r.json()) as Convite) : "erro"))
      .catch(() => "erro" as const)
      .then((c) => {
        if (!vivo) return;
        setConvite(c);
        if (c !== "erro" && c) setNome(c.nome);
      });
    return () => {
      vivo = false;
    };
  }, [token]);

  if (convite === null)
    return (
      <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-4">
        <Osso className="h-10 w-3/4" />
        <Osso className="h-40" />
      </div>
    );

  if (convite === "erro" || !convite.valido)
    return (
      <div className="flex flex-col gap-5">
        <Titulo titulo="Este convite já não é válido" texto="A ligação expirou, foi cancelada ou já foi usada. Peça à equipa ProEnglish um convite novo." />
        <Botao asChild tipo="secundario">
          <Link href="/signin">Entrar na minha conta</Link>
        </Botao>
      </div>
    );

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        setGeral(null);
        const er: Record<string, string> = {};
        if (nome.trim().length < 2) er.nome = "Escreva o seu nome completo.";
        if (senha.length < 8) er.password = "Use pelo menos 8 caracteres.";
        setErros(er);
        if (Object.keys(er).length) return;
        setAEnviar(true);
        try {
          const r = await fetch(`${API}/convites/${encodeURIComponent(token)}/aceitar/`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome: nome.trim(), password: senha }),
          });
          const dados = await r.json().catch(() => ({}));
          if (!r.ok) throw { status: r.status, data: dados };
          // Em produção a API está noutro domínio: marca a sessão também aqui, como o login normal.
          if (dados?.user) markAuthenticated(dados.user);
          await checkAuth();
          router.replace("/teacher/dashboard");
        } catch (x) {
          setErros(errosPorCampo(x));
          setGeral(erroDjango(x, "Não foi possível criar a conta. Tente outra vez."));
          setAEnviar(false);
        }
      }}
    >
      <Titulo titulo="Criar a conta de professor" texto={convite.area ? `Foi convidado para ensinar na ProEnglish, na área ${convite.area}.` : "Foi convidado para ensinar na ProEnglish."} />
      <Campo rotulo="Email" type="email" value={convite.email} disabled ajuda="É o email do convite." />
      <Campo rotulo="Nome completo" autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} erro={erros.nome} />
      <CampoSenha rotulo="Palavra-passe" autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} erro={erros.password} ajuda="Pelo menos 8 caracteres. Evite palavras comuns." />
      {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
      <Botao type="submit" larguraTotal disabled={aEnviar}>
        {aEnviar ? "A criar a conta…" : "Criar conta de professor"}
      </Botao>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">
        Ao criar a conta aceita os <Link href="/termos">Termos</Link> e a <Link href="/privacidade">Política de privacidade</Link>.
      </p>
    </form>
  );
}
