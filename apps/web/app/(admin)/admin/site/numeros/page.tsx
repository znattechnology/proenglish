"use client";

import { Etiqueta } from "@/components/pe";
import { ListaSite, PaginaSeccao } from "@/components/pe/admin/Site";
import { FONTES, ONDE } from "@/src/domains/admin/administracao/site";

export default function NumerosSite() {
  return (
    <PaginaSeccao titulo="Números" texto="Os números que aparecem no site. Os automáticos vêm da plataforma e actualizam-se sozinhos; use números reais.">
      {(s) => (
        <ListaSite
          lista="numeros"
          itens={s.rascunho.numeros}
          maximo={12}
          nome={{ um: "número", artigo: "o", novo: "Novo número" }}
          porDefeito={{ fonte: "manual", onde: "topo", mostrar: true, valor: "", texto: "" }}
          campos={[
            { chave: "fonte", rotulo: "De onde vem o número", tipo: "escolha", opcoes: FONTES },
            { chave: "valor", rotulo: "Número", tipo: "texto", max: 20, ajuda: "Por exemplo: 15 min", se: (d) => d.fonte === "manual" },
            { chave: "texto", rotulo: "Texto ao lado", tipo: "texto", max: 60 },
            { chave: "onde", rotulo: "Onde aparece", tipo: "escolha", opcoes: ONDE },
            { chave: "mostrar", rotulo: "Mostrar no site", tipo: "interruptor" },
          ]}
          linha={(n) => (
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-pe-titulo text-[22px] font-bold tabular-nums">{n.valor_mostrado || n.valor || "–"}</span>
              <span>{n.texto}</span>
              <span className="flex w-full flex-wrap gap-2 text-[14px] text-pe-tinta-suave">
                <Etiqueta>{ONDE[n.onde]}</Etiqueta>
                {n.fonte !== "manual" ? <Etiqueta tipo="certo">Automático</Etiqueta> : null}
                {n.mostrar ? null : <Etiqueta tipo="errado">Escondido</Etiqueta>}
              </span>
            </div>
          )}
        />
      )}
    </PaginaSeccao>
  );
}
