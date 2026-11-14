"use client";

import { ListaSite, PaginaSeccao } from "@/components/pe/admin/Site";
import { ICONES } from "@/src/domains/admin/administracao/site";

export default function ServicosSite() {
  return (
    <PaginaSeccao titulo="O que oferecemos" texto="A secção “O que encontra no ProEnglish” da página inicial. Descreva só o que a plataforma faz hoje.">
      {(s) => (
        <ListaSite
          lista="servicos"
          itens={s.rascunho.servicos}
          maximo={12}
          nome={{ um: "serviço", artigo: "o", novo: "Novo serviço" }}
          porDefeito={{ titulo: "", texto: "", icone: "livro", leva_a: "" }}
          campos={[
            { chave: "titulo", rotulo: "Título", tipo: "texto", max: 60 },
            { chave: "texto", rotulo: "Texto", tipo: "area", max: 300 },
            { chave: "icone", rotulo: "Ícone", tipo: "escolha", opcoes: ICONES },
            { chave: "leva_a", rotulo: "Ligação “Ver mais” (opcional)", tipo: "texto", max: 200, ajuda: "Uma página do site, como /certificados/verificar. Deixe vazio para não mostrar." },
          ]}
          linha={(v) => (
            <div className="flex flex-col gap-1">
              <span className="font-semibold">{v.titulo}</span>
              <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{v.texto}</span>
              {v.leva_a ? <span className="text-[14px] text-pe-tinta-suave">Leva a {v.leva_a}</span> : null}
            </div>
          )}
        />
      )}
    </PaginaSeccao>
  );
}
