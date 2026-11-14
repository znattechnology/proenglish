"use client";

import { CheckCircle2, Circle, Eye, Volume2 } from "lucide-react";
import { cnPe } from "@/lib/pe";
import type { Frase } from "@/src/domains/student/conversa/api";
import { falarNoBrowser } from "./useConversa";

/**
 * Frases-alvo durante uma conversa por voz: mostra só o que a frase quer dizer em português.
 * Para contar como dita sozinho, o aluno tem de a dizer sem a ler. "Ver em inglês" mostra a frase
 * (e deixa ouvi-la), mas nesta conversa ela passa a contar só "com ajuda" (o servidor é avisado).
 */
export function FrasesAlvo({ frases, ditas, reveladas, aoRevelar, compacta = false }: { frases: Frase[]; ditas: Set<string>; reveladas: string[]; aoRevelar: (en: string) => void; compacta?: boolean }) {
  if (!frases.length) return null;
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {frases.map((f, i) => {
        const dita = ditas.has(f.en);
        const vista = reveladas.includes(f.en);
        const sentido = f.pt?.trim() || `Frase ${i + 1} da lição`;
        return (
          <li key={f.en} className={cnPe("flex items-start gap-2.5 border-b border-pe-fundo-forte last:border-b-0", compacta ? "py-1.5" : "py-2.5")}>
            {dita ? <CheckCircle2 aria-label="Já disse" className="mt-0.5 size-5 shrink-0 text-pe-certo" /> : <Circle aria-label="Ainda não disse" className="mt-0.5 size-5 shrink-0 text-pe-tinta-suave" />}
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className={cnPe("leading-[22px]", dita && "font-semibold text-pe-certo")}>{sentido}</span>
              {vista ? (
                <span className="flex flex-wrap items-center gap-x-2">
                  <span lang="en" className="text-[15px] font-semibold leading-[22px]">
                    {f.en}
                  </span>
                  <button type="button" onClick={() => falarNoBrowser(f.en)} aria-label={`Ouvir: ${f.en}`} className="flex size-9 items-center justify-center rounded-pe-sm bg-transparent text-pe-azul-marca">
                    <Volume2 aria-hidden className="size-[18px]" />
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => aoRevelar(f.en)}
                  className="flex min-h-9 items-center gap-1.5 self-start bg-transparent p-0 text-[14px] font-semibold text-pe-azul-marca underline underline-offset-[3px]"
                  aria-label={`Ver em inglês: ${sentido}. Esta frase passa a contar com ajuda.`}
                >
                  <Eye aria-hidden className="size-4" />
                  Ver em inglês
                </button>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Uma linha a explicar a regra, por baixo da lista. */
export const REGRA_FRASES = "Diga-as em inglês sem as ler. Se abrir a frase em inglês, conta como dita com ajuda.";
