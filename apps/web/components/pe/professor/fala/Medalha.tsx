import { cnPe } from "@/lib/pe";
import type { Raridade } from "@/src/domains/teacher/professor/fala";

const COR: Record<Raridade, string> = {
  comum: "bg-pe-fundo-forte text-pe-tinta",
  rara: "bg-pe-azul-vivo text-pe-sobre-marca",
  epica: "bg-pe-azul-marca text-pe-realce",
  lendaria: "bg-pe-realce text-pe-tinta",
};

/** A medalha com a forma do balão da marca; a cor diz a raridade (sempre acompanhada do nome). */
export function Medalha({ icone, raridade, grande }: { icone: string; raridade: Raridade; grande?: boolean }) {
  return (
    <span aria-hidden className={cnPe("flex shrink-0 items-center justify-center font-pe-titulo font-bold", grande ? "size-20 rounded-pe-fala text-[30px]" : "size-11 rounded-pe-fala-s text-[17px]", COR[raridade])}>
      {icone || "★"}
    </span>
  );
}
