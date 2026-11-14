"use client";

import { ListaSite, PaginaSeccao } from "@/components/pe/admin/Site";

export default function PerguntasSite() {
  return (
    <PaginaSeccao titulo="Perguntas frequentes" texto="Aparecem no fim da página inicial, pela ordem desta lista.">
      {(s) => (
        <ListaSite
          lista="perguntas"
          itens={s.rascunho.perguntas}
          maximo={30}
          nome={{ um: "pergunta", artigo: "a", novo: "Nova pergunta" }}
          porDefeito={{ pergunta: "", resposta: "" }}
          campos={[
            { chave: "pergunta", rotulo: "Pergunta", tipo: "texto", max: 200 },
            { chave: "resposta", rotulo: "Resposta", tipo: "area", max: 1000 },
          ]}
          linha={(p) => (
            <div className="flex flex-col gap-1">
              <span className="font-semibold">{p.pergunta}</span>
              <span className="line-clamp-2 text-[15px] leading-[22px] text-pe-tinta-suave">{p.resposta}</span>
            </div>
          )}
        />
      )}
    </PaginaSeccao>
  );
}
