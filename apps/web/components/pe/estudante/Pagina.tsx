import { cnPe } from "@/lib/pe";

/**
 * Contentor de todas as páginas novas. No desktop o conteúdo fica centrado no espaço
 * ao lado da barra lateral e cresce até 1280px, para não deixar uma faixa vazia à direita
 * em ecrãs largos. No telemóvel ocupa a largura toda com 20px de margem.
 */
export function Pagina({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <main className={cnPe("mx-auto flex w-full max-w-[1280px] flex-col gap-5 px-5 pb-8 pt-4 md:px-10 md:py-8 xl:px-12", className)}>
      {children}
    </main>
  );
}
