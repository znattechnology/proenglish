"use client";

import { useState } from "react";
import { Aviso, Botao, Campo, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { MudarPalavraPasse } from "@/components/pe/conta/MudarPalavraPasse";
import { CabecaPerfil } from "@/components/pe/professor/SeparadoresPerfil";
import { telefoneLegivel } from "@/src/domains/student/subscricao/api";
import { errosDoServidor, useGuardarPerfilMutation, usePerfilQuery, type Perfil } from "@/src/domains/student/perfil/api";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";

export default function DefinicoesProfessor() {
  const { data: perfil, isError, refetch } = usePerfilQuery();
  return (
    <Pagina className="gap-7">
      <CabecaPerfil activo="Definições" texto="A sua conta: contacto e palavra-passe." />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar a sua conta.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !perfil ? (
        <Osso className="h-80 max-w-[640px] rounded-pe-md" />
      ) : (
        <div className="flex max-w-[640px] flex-col gap-8">
          <Conta perfil={perfil} />
          <Seguranca temSenha={perfil.has_password !== false} />
        </div>
      )}
    </Pagina>
  );
}

function Conta({ perfil }: { perfil: Perfil }) {
  const [guardar, { isLoading }] = useGuardarPerfilMutation();
  const estrangeiro = (perfil.phone ?? "").startsWith("+") && !(perfil.phone ?? "").startsWith("+244");
  const [telefone, setTelefone] = useState(estrangeiro ? perfil.phone ?? "" : telefoneLegivel((perfil.phone ?? "").replace(/^\+244/, "")));
  const [erro, setErro] = useState<string | undefined>();
  const [estado, setEstado] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);

  return (
    <section aria-labelledby="t-conta" className="flex flex-col gap-4">
      <h2 id="t-conta" className={h2}>
        Conta
      </h2>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setEstado(null);
          const digitos = telefone.replace(/\D/g, "");
          if (!estrangeiro && digitos && !/^9\d{8}$/.test(digitos)) return setErro("Escreva os 9 dígitos do número, a começar por 9.");
          setErro(undefined);
          const r = await guardar({ phone: estrangeiro ? perfil.phone : digitos ? `+244${digitos}` : null });
          if ("error" in r && r.error) {
            const { campos, geral } = errosDoServidor(r.error);
            setErro(campos.phone);
            setEstado(geral ? { tipo: "errado", texto: geral } : null);
            return;
          }
          setEstado({ tipo: "certo", texto: "Alterações guardadas." });
        }}
      >
        <Campo rotulo="Email" type="email" value={perfil.email} disabled ajuda="Para mudar o email, fale com a equipa ProEnglish." />
        <Campo
          rotulo="Telefone"
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          value={telefone}
          disabled={estrangeiro}
          onChange={(e) => setTelefone(e.target.value)}
          erro={erro}
          ajuda="Só a equipa ProEnglish o vê, para falar consigo sobre os seus cursos e pagamentos."
        />
        {estado ? <Aviso tipo={estado.tipo}>{estado.texto}</Aviso> : null}
        <Botao type="submit" tamanho="medio" className="self-start" disabled={isLoading}>
          {isLoading ? "A guardar…" : "Guardar alterações"}
        </Botao>
      </form>
    </section>
  );
}

function Seguranca({ temSenha }: { temSenha: boolean }) {
  const [aberto, setAberto] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);
  return (
    <section aria-labelledby="t-seguranca" className="flex flex-col items-start gap-3 border-t border-pe-linha pt-6">
      <h2 id="t-seguranca" className={h2}>
        Segurança
      </h2>
      <Botao tipo="secundario" tamanho="medio" onClick={() => setAberto(true)}>
        {temSenha ? "Mudar a palavra-passe" : "Criar uma palavra-passe"}
      </Botao>
      {feito ? <Aviso tipo="certo">{feito}</Aviso> : null}
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Para fechar a conta de professor, fale com a equipa ProEnglish: os seus cursos têm alunos inscritos e é preciso decidir o que lhes acontece.</p>
      {aberto ? <MudarPalavraPasse temSenha={temSenha} aberto aoMudar={setAberto} aoMudada={setFeito} /> : null}
    </section>
  );
}
