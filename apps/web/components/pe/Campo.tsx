"use client";

import * as React from "react";
import { cnPe } from "@/lib/pe";

type BaseProps = {
  rotulo: string;
  ajuda?: React.ReactNode;
  erro?: string;
  className?: string;
};

const controlo =
  "w-full rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 font-pe-texto text-[16px] text-pe-tinta placeholder:text-pe-tinta-suave disabled:bg-pe-fundo-suave disabled:text-pe-tinta-suave aria-[invalid=true]:border-2 aria-[invalid=true]:border-pe-errado";

function Envolvente({
  id,
  rotulo,
  ajuda,
  erro,
  className,
  children,
}: BaseProps & { id: string; children: React.ReactNode }) {
  return (
    <div className={cnPe("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="font-pe-texto text-pe-rotulo text-pe-tinta">
        {rotulo}
      </label>
      {children}
      {erro ? (
        <p id={`${id}-erro`} className="m-0 text-pe-legenda font-semibold text-pe-errado">
          {erro}
        </p>
      ) : ajuda ? (
        <p id={`${id}-ajuda`} className="m-0 text-pe-legenda text-pe-tinta-suave">
          {ajuda}
        </p>
      ) : null}
    </div>
  );
}

function descritoPor(id: string, erro?: string, ajuda?: React.ReactNode) {
  return erro ? `${id}-erro` : ajuda ? `${id}-ajuda` : undefined;
}

/** Campo de texto com rótulo visível, ajuda opcional e mensagem de erro ligada ao campo. */
export const Campo = React.forwardRef<
  HTMLInputElement,
  BaseProps & Omit<React.InputHTMLAttributes<HTMLInputElement>, "className">
>(({ rotulo, ajuda, erro, className, id, ...props }, ref) => {
  const gerado = React.useId();
  const campoId = id ?? gerado;
  return (
    <Envolvente id={campoId} rotulo={rotulo} ajuda={ajuda} erro={erro} className={className}>
      <input
        ref={ref}
        id={campoId}
        aria-invalid={erro ? true : undefined}
        aria-describedby={descritoPor(campoId, erro, ajuda)}
        className={cnPe(controlo, "h-12")}
        {...props}
      />
    </Envolvente>
  );
});
Campo.displayName = "Campo";

/** Área de texto com as mesmas regras do Campo. */
export const AreaTexto = React.forwardRef<
  HTMLTextAreaElement,
  BaseProps & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "className">
>(({ rotulo, ajuda, erro, className, id, rows = 3, ...props }, ref) => {
  const gerado = React.useId();
  const campoId = id ?? gerado;
  return (
    <Envolvente id={campoId} rotulo={rotulo} ajuda={ajuda} erro={erro} className={className}>
      <textarea
        ref={ref}
        id={campoId}
        rows={rows}
        aria-invalid={erro ? true : undefined}
        aria-describedby={descritoPor(campoId, erro, ajuda)}
        className={cnPe(controlo, "resize-none py-2.5 leading-6")}
        {...props}
      />
    </Envolvente>
  );
});
AreaTexto.displayName = "AreaTexto";

/** Lista de escolha nativa (funciona bem em telemóvel e com leitores de ecrã). */
export const Escolha = React.forwardRef<
  HTMLSelectElement,
  BaseProps & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className">
>(({ rotulo, ajuda, erro, className, id, children, ...props }, ref) => {
  const gerado = React.useId();
  const campoId = id ?? gerado;
  return (
    <Envolvente id={campoId} rotulo={rotulo} ajuda={ajuda} erro={erro} className={className}>
      <select
        ref={ref}
        id={campoId}
        aria-invalid={erro ? true : undefined}
        aria-describedby={descritoPor(campoId, erro, ajuda)}
        className={cnPe(controlo, "h-12")}
        {...props}
      >
        {children}
      </select>
    </Envolvente>
  );
});
Escolha.displayName = "Escolha";
