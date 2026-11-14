"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaSeccao, SEPARADORES_UTILIZADORES } from "@/components/pe/admin/Comum";
import { DialogoConvidar } from "@/components/pe/admin/Convidar";
import { diaMesCurto, mensagemErro } from "@/src/domains/student/subscricao/api";
import { useCancelarConviteMutation, useConvitesQuery, useReenviarConviteMutation, type Convite } from "@/src/domains/admin/administracao/api";

const ESTADO: Record<Convite["estado"], { nome: string; tipo: "realce" | "certo" | "neutra" }> = {
  pendente: { nome: "À espera", tipo: "realce" },
  aceite: { nome: "Aceite", tipo: "certo" },
  expirado: { nome: "Expirado", tipo: "neutra" },
  cancelado: { nome: "Cancelado", tipo: "neutra" },
};

export default function Convites() {
  const { data, isError, refetch } = useConvitesQuery();
  const [convidar, setConvidar] = useState(false);
  const [reenviar] = useReenviarConviteMutation();
  const [cancelar] = useCancelarConviteMutation();
  const [msg, setMsg] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const accao = async (f: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try {
      const r = (await f()) as { email_enviado?: boolean; message?: string } | undefined;
      if (r && r.email_enviado === false) return setMsg({ tipo: "errado", texto: r.message ?? "O email não foi enviado. Tente outra vez daqui a pouco." });
      setMsg({ tipo: "certo", texto: ok });
    } catch (x) {
      setMsg({ tipo: "errado", texto: mensagemErro(x, "Não foi possível concluir.") });
    }
  };

  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Utilizadores" activo="Convites de professor" itens={SEPARADORES_UTILIZADORES}>
        <Botao tamanho="medio" onClick={() => setConvidar(true)}>
          <UserPlus aria-hidden className="size-5" />
          Convidar professor
        </Botao>
      </CabecaSeccao>
      {msg ? <Aviso tipo={msg.tipo}>{msg.texto}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os convites.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !data.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Ainda não convidou professores. Os professores só entram por convite: a inscrição normal cria sempre contas de estudante.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col p-0">
          {data.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-pe-fundo-forte py-3.5">
              <span className="flex min-w-0 flex-[1_1_260px] flex-col">
                <span className="font-semibold">{c.nome}</span>
                <span className="truncate text-pe-legenda text-pe-tinta-suave">
                  {c.email}, {c.area}
                  {c.publica_sem_revisao ? ", publica sem revisão" : ""}
                </span>
              </span>
              <Etiqueta tipo={ESTADO[c.estado].tipo}>{ESTADO[c.estado].nome}</Etiqueta>
              <span className="text-[15px] tabular-nums text-pe-tinta-suave">
                Enviado a {diaMesCurto(new Date(c.enviado_em))}
                {c.estado === "pendente" ? `, vale até ${diaMesCurto(new Date(c.expira_em))}` : ""}
              </span>
              {c.estado === "pendente" || c.estado === "expirado" ? (
                <span className="ml-auto flex gap-1">
                  <Botao tipo="ligacao" tamanho="pequeno" onClick={() => accao(() => reenviar(c.id).unwrap(), `Convite reenviado para ${c.email}.`)}>
                    Reenviar
                  </Botao>
                  {c.estado === "pendente" ? (
                    <Botao tipo="ligacao" tamanho="pequeno" className="text-pe-errado hover:text-pe-errado" onClick={() => accao(() => cancelar(c.id).unwrap(), "Convite cancelado: a ligação deixou de funcionar.")}>
                      Cancelar
                    </Botao>
                  ) : null}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {convidar ? <DialogoConvidar aoFechar={() => setConvidar(false)} /> : null}
    </Pagina>
  );
}
