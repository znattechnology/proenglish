"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cnPe } from "@/lib/pe";

/**
 * Janela modal da base nova: folha que sobe de baixo no telemóvel, janela centrada no desktop.
 * Foco preso dentro, Escape fecha, título e descrição ligados para leitores de ecrã.
 */
export function Dialogo({
  aberto,
  aoMudar,
  titulo,
  descricao,
  children,
  topo,
  largura = 480,
}: {
  aberto: boolean;
  aoMudar: (v: boolean) => void;
  titulo: string;
  descricao?: React.ReactNode;
  children?: React.ReactNode;
  topo?: React.ReactNode;
  largura?: number;
}) {
  return (
    <DialogPrimitive.Root open={aberto} onOpenChange={aoMudar}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[rgba(20,20,63,0.55)]" />
        <DialogPrimitive.Content
          className={cnPe(
            "pe fixed z-50 flex !min-h-0 max-h-[92dvh] flex-col gap-5 overflow-y-auto bg-pe-fundo p-6 pb-[max(24px,env(safe-area-inset-bottom))] shadow-pe-2 focus:outline-none",
            "inset-x-0 bottom-0 rounded-t-pe-md",
            "md:inset-auto md:left-1/2 md:top-1/2 md:w-[var(--largura-dialogo)] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-pe-md md:p-8"
          )}
          style={{ "--largura-dialogo": `${largura + 64}px` } as React.CSSProperties}
        >
          <div className="mx-auto flex w-full flex-col gap-5" style={{ maxWidth: largura }}>
            {topo}
            <div className="flex flex-col gap-2">
              <DialogPrimitive.Title className="m-0 font-pe-titulo text-[24px] font-bold leading-[30px]">{titulo}</DialogPrimitive.Title>
              {descricao ? <DialogPrimitive.Description className="m-0">{descricao}</DialogPrimitive.Description> : null}
            </div>
            {children}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
