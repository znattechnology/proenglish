"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Menu, X } from "lucide-react";

/** Menu das secções em ecrãs abaixo de 1024 px (no desktop as ligações ficam no cabeçalho). */
export function MenuMovel({ ligacoes }: { ligacoes: { nome: string; href: string; actual?: boolean }[] }) {
  const [aberto, setAberto] = useState(false);
  const id = useId();
  const botao = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAberto(false);
        botao.current?.focus();
      }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aberto]);

  return (
    <div className="lg:hidden">
      <button
        ref={botao}
        type="button"
        aria-expanded={aberto}
        aria-controls={id}
        aria-label={aberto ? "Fechar o menu" : "Abrir o menu"}
        onClick={() => setAberto((v) => !v)}
        className="flex size-11 items-center justify-center rounded-pe-sm bg-transparent text-pe-azul-marca hover:bg-pe-fundo-suave"
      >
        {aberto ? <X aria-hidden className="size-6" /> : <Menu aria-hidden className="size-6" />}
      </button>
      <nav id={id} aria-label="Secções" hidden={!aberto} className="absolute inset-x-0 top-full z-30 border-b border-pe-linha bg-pe-fundo shadow-pe-2">
        <ul className="m-0 flex list-none flex-col px-4 py-2">
          {ligacoes.map((l) => (
            <li key={l.href}>
              <a
                href={l.href}
                aria-current={l.actual ? "page" : undefined}
                onClick={() => setAberto(false)}
                className="flex min-h-12 items-center border-b border-pe-fundo-forte font-semibold text-pe-tinta no-underline last:border-0 hover:text-pe-azul-marca"
              >
                {l.nome}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
