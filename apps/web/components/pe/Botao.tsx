import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cnPe } from "@/lib/pe";

/**
 * Botão do sistema ProEnglish.
 * - principal: a acção principal do ecrã (uma por ecrã).
 * - secundario: alternativa à principal.
 * - realce: só para a acção de venda ou de começar (ex.: "Experimentar grátis").
 * - perigo: acções destrutivas (apagar, suspender, sair e perder o progresso).
 * - ligacao: acção terciária, com aspecto de ligação sublinhada.
 * Use `asChild` para pôr o estilo num <Link>.
 */
const botaoVariantes = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-pe-sm font-pe-texto font-semibold no-underline transition-colors disabled:cursor-not-allowed [&_svg]:size-5 [&_svg]:shrink-0",
  {
    variants: {
      tipo: {
        principal:
          "bg-pe-azul-marca text-pe-sobre-marca hover:bg-pe-azul-vivo hover:text-pe-sobre-marca disabled:bg-pe-fundo-forte disabled:text-pe-tinta-suave",
        secundario:
          "border-2 border-pe-azul-marca bg-pe-fundo text-pe-azul-marca hover:bg-pe-fundo-suave hover:text-pe-azul-marca disabled:border-pe-linha disabled:text-pe-tinta-suave",
        realce:
          "bg-pe-realce text-pe-tinta hover:shadow-pe-2 hover:text-pe-tinta disabled:bg-pe-fundo-forte disabled:text-pe-tinta-suave",
        perigo:
          "border-2 border-pe-errado bg-pe-fundo text-pe-errado hover:bg-pe-errado-suave hover:text-pe-errado",
        ligacao:
          "bg-transparent px-1 text-pe-azul-marca underline underline-offset-[3px] hover:text-pe-azul-vivo",
      },
      tamanho: {
        grande: "min-h-[52px] px-6 text-[16px] leading-5",
        medio: "min-h-12 px-5 text-[16px] leading-5",
        pequeno: "min-h-11 px-4 text-[15px] leading-5",
      },
      larguraTotal: { true: "w-full", false: "" },
    },
    compoundVariants: [{ tipo: "ligacao", class: "px-1" }],
    defaultVariants: { tipo: "principal", tamanho: "grande", larguraTotal: false },
  }
);

export interface BotaoProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof botaoVariantes> {
  asChild?: boolean;
}

export const Botao = React.forwardRef<HTMLButtonElement, BotaoProps>(
  ({ className, tipo, tamanho, larguraTotal, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        // Nunca submeter formulários sem querer.
        type={asChild ? undefined : (type ?? "button")}
        className={cnPe(botaoVariantes({ tipo, tamanho, larguraTotal }), className)}
        {...props}
      />
    );
  }
);
Botao.displayName = "Botao";

export { botaoVariantes };
