"use client";

import { useRef, useState } from "react";
import { Aviso, Etiqueta } from "@/components/pe";
import { ListaSite, PaginaSeccao } from "@/components/pe/admin/Site";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useEnviarLogoMutation, useTirarLogoMutation, type Empresa } from "@/src/domains/admin/administracao/site";

export default function EmpresasSite() {
  const [erro, setErro] = useState<string | null>(null);
  return (
    <PaginaSeccao titulo="Empresas" texto="Empresas cujos profissionais estudam no ProEnglish. Junte só empresas que autorizaram aparecer no site.">
      {(s) => (
        <>
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <ListaSite
            lista="empresas"
            itens={s.rascunho.empresas}
            maximo={40}
            nome={{ um: "empresa", artigo: "a", novo: "Nova empresa" }}
            porDefeito={{ nome: "", area: "", na_faixa: true, no_topo: false }}
            campos={[
              { chave: "nome", rotulo: "Nome", tipo: "texto", max: 80 },
              { chave: "area", rotulo: "Área (opcional)", tipo: "texto", max: 60 },
              { chave: "na_faixa", rotulo: "Mostrar na faixa de empresas", tipo: "interruptor", descricao: "Por baixo do topo da página inicial." },
            ]}
            linha={(e) => (
              <div className="flex items-center gap-4">
                <span className="flex h-12 w-24 shrink-0 items-center justify-center rounded-pe-sm bg-pe-fundo-suave">
                  {e.logo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={e.logo_url} alt="" className="max-h-10 max-w-[88px] object-contain" />
                  ) : (
                    <span className="text-[13px] text-pe-tinta-suave">Sem logótipo</span>
                  )}
                </span>
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="font-semibold">{e.nome}</span>
                  <span className="flex flex-wrap gap-2 text-[14px] text-pe-tinta-suave">
                    {e.area ? <span>{e.area}</span> : null}
                    {e.na_faixa ? <Etiqueta>Na faixa</Etiqueta> : <Etiqueta tipo="errado">Escondida</Etiqueta>}
                  </span>
                </span>
              </div>
            )}
            extra={(e) => <Logotipo e={e} aoErro={setErro} />}
          />
        </>
      )}
    </PaginaSeccao>
  );
}

function Logotipo({ e, aoErro }: { e: Empresa; aoErro: (m: string | null) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [enviar, { isLoading }] = useEnviarLogoMutation();
  const [tirar] = useTirarLogoMutation();
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="image/png,image/webp"
        className="sr-only"
        aria-label={`Logótipo de ${e.nome}`}
        onChange={async (ev) => {
          const f = ev.target.files?.[0];
          ev.target.value = "";
          if (!f) return;
          aoErro(null);
          if (f.size > 1024 * 1024) return aoErro("O logótipo tem de ter no máximo 1 MB.");
          try {
            await enviar({ id: e.id, ficheiro: f }).unwrap();
          } catch (er) {
            aoErro(mensagemErro(er, "Não foi possível enviar o logótipo. Use PNG ou WebP até 1 MB."));
          }
        }}
      />
      <button type="button" disabled={isLoading} onClick={() => ref.current?.click()} className="min-h-11 px-2 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]">
        {isLoading ? "A enviar…" : e.logo_url ? "Trocar logótipo" : "Juntar logótipo"}
      </button>
      {e.logo_url ? (
        <button type="button" onClick={() => tirar(e.id).unwrap().catch((er) => aoErro(mensagemErro(er, "Não foi possível tirar o logótipo.")))} className="min-h-11 px-2 text-[15px] text-pe-tinta-suave underline underline-offset-[3px]">
          Tirar
        </button>
      ) : null}
    </>
  );
}
