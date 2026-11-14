"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Aviso, Botao, Campo } from "@/components/pe";
import { useRegisterMutation } from "@/src/domains/auth/services/authApi";
import { manterParametros, useEntrarComGoogle } from "./Entrar";
import { BotaoGoogle, CampoSenha, Ou, Titulo, erroDjango, errosPorCampo } from "./Partes";

type Erros = Partial<Record<"name" | "email" | "password" | "password_confirm", string>>;

function validar(nome: string, email: string, senha: string, repetir: string): Erros {
  const e: Erros = {};
  if (nome.trim().split(/\s+/).filter(Boolean).length < 2) e.name = "Escreva o nome e o apelido.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) e.email = "Escreva um email válido, por exemplo nome@empresa.ao.";
  if (senha.length < 8) e.password = "A palavra-passe precisa de 8 caracteres ou mais.";
  if (repetir && repetir !== senha) e.password_confirm = "As duas palavras-passe são diferentes.";
  if (!repetir) e.password_confirm = "Repita a palavra-passe.";
  return e;
}

export function CriarConta() {
  const router = useRouter();
  const sp = useSearchParams();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState(sp.get("email") ?? "");
  const [senha, setSenha] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erro, setErro] = useState<string | null>(null);
  const [registar, { isLoading }] = useRegisterMutation();
  const google = useEntrarComGoogle();
  const plano = sp.get("plan");

  return (
    <>
      <Titulo titulo="Criar conta" texto={plano ? "Primeiro a conta, depois escolhe como paga o plano." : "Grátis, com 3 lições por dia. Sem cartão."} />
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          const v = validar(nome, email, senha, repetir);
          setErros(v);
          if (Object.keys(v).length) return;
          const mail = email.trim().toLowerCase();
          try {
            await registar({ name: nome.trim().replace(/\s+/g, " "), email: mail, password: senha, password_confirm: repetir, role: "student" }).unwrap();
            router.push(`/verify-email${manterParametros(sp, { email: mail })}`);
          } catch (er) {
            const campos = errosPorCampo(er) as Erros;
            if (Object.keys(campos).length) setErros(campos);
            const m = erroDjango(er, "Não foi possível criar a conta. Tente outra vez.");
            setErro(/existe|already|registad|cadastrad/i.test(m) ? "Já existe uma conta com este email. Entre ou recupere a palavra-passe." : Object.keys(campos).length ? null : m);
          }
        }}
      >
        <Campo rotulo="Nome completo" autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} erro={erros.name} required autoFocus />
        <Campo rotulo="Email" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} erro={erros.email} required />
        <CampoSenha rotulo="Palavra-passe" autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} erro={erros.password} ajuda="Tem 8 caracteres ou mais" required />
        <CampoSenha rotulo="Repita a palavra-passe" autoComplete="new-password" value={repetir} onChange={(e) => setRepetir(e.target.value)} erro={erros.password_confirm} required />
        {erro ? (
          <Aviso tipo="errado">
            {erro}{" "}
            {/conta com este email/.test(erro) ? (
              <Link href={`/signin${manterParametros(sp, { email: email.trim().toLowerCase() })}`} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
                Entrar
              </Link>
            ) : null}
          </Aviso>
        ) : null}
        <Botao type="submit" larguraTotal disabled={isLoading}>
          {isLoading ? "A criar a conta…" : "Criar conta"}
        </Botao>
        <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave">
          Ao criar a conta aceita os{" "}
          <Link href="/termos" target="_blank" className="text-pe-tinta-suave underline underline-offset-[3px]">
            Termos de utilização
          </Link>{" "}
          e a{" "}
          <Link href="/privacidade" target="_blank" className="text-pe-tinta-suave underline underline-offset-[3px]">
            Política de privacidade
          </Link>
          .
        </p>
      </form>
      <Ou />
      {google.erro ? <Aviso tipo="errado">{google.erro}</Aviso> : null}
      <BotaoGoogle texto="Criar conta com o Google" aoCarregar={() => google.abrir(sp)} aCarregar={google.aAbrir} />
      <p className="m-0 text-pe-tinta-suave">
        Já tem conta?{" "}
        <Link href={`/signin${manterParametros(sp)}`} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
          Entrar
        </Link>
      </p>
    </>
  );
}
