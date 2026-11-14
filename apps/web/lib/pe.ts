import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Como `cn()`, mas sabe que `text-pe-rotulo` (tamanho) e `text-pe-tinta` (cor)
 * são grupos diferentes. Sem isto, juntar as duas apagava uma delas.
 */
const twMergePe = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "pe-titulo-xl",
            "pe-titulo-l",
            "pe-titulo-m",
            "pe-titulo-s",
            "pe-voz",
            "pe-corpo-l",
            "pe-corpo",
            "pe-rotulo",
            "pe-legenda",
          ],
        },
      ],
      shadow: [{ shadow: ["pe-1", "pe-2"] }],
      rounded: [{ rounded: ["pe-sm", "pe-md", "pe-fala", "pe-fala-aluno", "pe-fala-m", "pe-fala-s"] }],
    },
  },
});

export function cnPe(...inputs: ClassValue[]) {
  return twMergePe(clsx(inputs));
}
