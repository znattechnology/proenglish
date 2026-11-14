"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Volume2, X, XCircle } from "lucide-react";
import { BarraProgresso, Botao, Vidas } from "@/components/pe";
import { cnPe } from "@/lib/pe";

/* ------------------------------------------------------------------ */
/* Cabeçalho da lição: sair, progresso e vidas.                        */
/* ------------------------------------------------------------------ */
export function CabecalhoLicao({
  feitos,
  total,
  vidas,
  ilimitadas,
  aoSair,
}: {
  feitos: number;
  total: number;
  vidas: number | null;
  ilimitadas: boolean;
  aoSair: () => void;
}) {
  const pct = total ? (100 * feitos) / total : 0;
  return (
    <header className="border-b border-pe-linha md:border-pe-linha">
      <div className="mx-auto flex max-w-[960px] items-center gap-3 px-4 py-3 md:gap-5 md:px-6 md:py-4">
        <button
          type="button"
          onClick={aoSair}
          aria-label="Sair da lição"
          className="flex size-11 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta hover:bg-pe-fundo-suave"
        >
          <X aria-hidden className="size-6" />
        </button>
        <BarraProgresso valor={pct} rotulo={`Exercício ${Math.min(feitos + 1, total)} de ${total}`} altura={12} className="flex-1" />
        <span className="hidden shrink-0 text-[15px] text-pe-tinta-suave md:inline">
          {Math.min(feitos + 1, total)} de {total}
        </span>
        {vidas !== null ? <Vidas quantas={vidas} ilimitadas={ilimitadas} /> : null}
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Botão de ouvir: toca o áudio de referência.                         */
/* ------------------------------------------------------------------ */
export function BotaoOuvir({ src, rotulo = "Ouvir", sobreMarca = false, grande = false }: { src: string; rotulo?: string; sobreMarca?: boolean; grande?: boolean }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [aTocar, setATocar] = useState(false);
  useEffect(() => () => audio.current?.pause(), []);
  const tocar = () => {
    if (!audio.current) {
      audio.current = new Audio(src);
      audio.current.addEventListener("ended", () => setATocar(false));
    }
    audio.current.currentTime = 0;
    void audio.current.play().then(() => setATocar(true)).catch(() => setATocar(false));
  };
  if (grande) {
    return (
      <button
        type="button"
        onClick={tocar}
        aria-label={aTocar ? "A tocar" : rotulo}
        className="pe-sobre-marca flex size-24 items-center justify-center self-center rounded-pe-fala bg-pe-azul-marca text-pe-sobre-marca hover:bg-pe-azul-vivo md:size-28"
      >
        <Volume2 aria-hidden className="size-10" />
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={tocar}
      className={cnPe(
        "inline-flex min-h-11 items-center gap-2 self-start bg-transparent p-0 text-[15px] font-semibold underline underline-offset-[3px]",
        sobreMarca ? "text-pe-sobre-marca" : "text-pe-azul-marca"
      )}
    >
      <Volume2 aria-hidden className="size-5" />
      {aTocar ? "A tocar" : rotulo}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Enunciado: título e, quando há, o balão do supervisor/tutor.        */
/* ------------------------------------------------------------------ */
export function Enunciado({ titulo, children }: { titulo: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-5 md:gap-7">
      <h1 className="m-0 text-[22px] font-bold leading-7 md:text-pe-titulo-m">{titulo}</h1>
      {children}
    </div>
  );
}

export function BalaoEnunciado({ autor, children, audio }: { autor?: string | null; children: React.ReactNode; audio?: string | null }) {
  return (
    <div className="pe-sobre-marca flex max-w-[560px] flex-col gap-1.5 self-start rounded-pe-fala bg-pe-azul-marca px-6 py-4 text-pe-sobre-marca md:px-7 md:py-5">
      {autor ? <span className="text-pe-legenda font-semibold">{autor}</span> : null}
      <p className="m-0 text-[20px] leading-[30px] md:text-[24px] md:leading-9">{children}</p>
      {audio ? <BotaoOuvir src={audio} sobreMarca /> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Rodapé: verificar, ou o resultado (certo/errado) e continuar.       */
/* ------------------------------------------------------------------ */
export type EstadoRodape =
  | { tipo: "verificar"; pronto: boolean; aVerificar: boolean }
  | { tipo: "certo"; explicacao?: string | null }
  | { tipo: "errado"; dica?: string | null; perdeuVida: boolean };

export function RodapeLicao({
  estado,
  dicaTeclado,
  aoVerificar,
  aoContinuar,
  aoTentarOutraVez,
  textoContinuar = "Continuar",
  textoVerificar = "Verificar",
}: {
  estado: EstadoRodape;
  dicaTeclado?: string;
  aoVerificar: () => void;
  aoContinuar: () => void;
  aoTentarOutraVez: () => void;
  textoContinuar?: string;
  /** Texto do botão antes de verificar (p.ex. "Continuar" num exercício que só se salta). */
  textoVerificar?: string;
}) {
  const certo = estado.tipo === "certo";
  const errado = estado.tipo === "errado";
  return (
    <footer
      className={cnPe(
        "border-t motion-safe:transition-colors",
        certo ? "border-transparent bg-pe-certo-suave" : errado ? "border-transparent bg-pe-errado-suave" : "border-pe-linha bg-pe-fundo"
      )}
    >
      <div className="mx-auto flex max-w-[960px] flex-col gap-3 px-5 pb-5 pt-4 md:flex-row md:items-center md:justify-between md:gap-8 md:px-6 md:py-5">
        {certo || errado ? (
          <div role="status" aria-live="assertive" className="flex min-w-0 gap-3">
            {certo ? (
              <CheckCircle2 aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-certo md:size-8" />
            ) : (
              <XCircle aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-errado md:size-8" />
            )}
            <div className="flex flex-col gap-0.5">
              <span className={cnPe("font-pe-titulo text-[18px] font-bold leading-6 md:text-pe-titulo-s", certo ? "text-pe-certo" : "text-pe-errado")}>
                {certo ? "Certo" : estado.tipo === "errado" && estado.perdeuVida ? "Ainda não. Perdeu uma vida" : "Ainda não"}
              </span>
              {certo && estado.explicacao ? <span className="text-[15px] leading-[22px] md:text-pe-corpo">{estado.explicacao}</span> : null}
              {errado && estado.tipo === "errado" && estado.dica ? <span className="text-[15px] leading-[22px] md:text-pe-corpo">{estado.dica}</span> : null}
            </div>
          </div>
        ) : (
          <p className="m-0 hidden text-pe-legenda text-pe-tinta-suave md:block">{dicaTeclado}</p>
        )}
        <div className="md:shrink-0">
          {estado.tipo === "verificar" ? (
            <Botao larguraTotal className="md:w-auto md:min-w-[200px]" disabled={!estado.pronto || estado.aVerificar} onClick={aoVerificar}>
              {estado.aVerificar ? "A verificar…" : textoVerificar}
            </Botao>
          ) : certo ? (
            <Botao larguraTotal className="md:w-auto md:min-w-[200px]" onClick={aoContinuar} autoFocus>
              {textoContinuar}
            </Botao>
          ) : (
            <Botao larguraTotal className="md:w-auto md:min-w-[200px]" onClick={aoTentarOutraVez} autoFocus>
              Tentar outra vez
            </Botao>
          )}
        </div>
      </div>
    </footer>
  );
}
