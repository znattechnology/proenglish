"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Se o browser recusar o ecrã inteiro (p.ex. numa moldura ou por uma política), o teste não pode
// ficar bloqueado: a partir daí faz-se como no iPhone e só se vigia a saída da página.
let recusado = false;

/** O browser deixa pôr a página em ecrã inteiro? (No iPhone não deixa: aí só se vigia a saída.) */
export function suportaEcraInteiro() {
  return typeof document !== "undefined" && !!document.fullscreenEnabled && !recusado;
}

/** Pede o ecrã inteiro. Tem de ser chamado num clique (o browser exige um gesto). */
export async function entrarEcraInteiro() {
  if (!suportaEcraInteiro() || document.fullscreenElement) return;
  try {
    await document.documentElement.requestFullscreen();
  } catch {
    // Recusado pelo browser: o teste continua, e a saída da página continua a ser vigiada.
    recusado = true;
  }
}

export async function sairEcraInteiro() {
  if (typeof document !== "undefined" && document.fullscreenElement) {
    try {
      await document.exitFullscreen();
    } catch {
      // sem efeito
    }
  }
}

/**
 * Vigia a saída do ecrã do teste (regra do LabTIC): mudar de separador ou de janela, ou sair do
 * ecrã inteiro. Cada saída chama `aoSair` uma vez; a seguinte só conta depois de o aluno voltar.
 * Devolve se está no ecrã inteiro (sempre true onde o browser não o suporta) e como voltar.
 */
export function useVigiaEcraInteiro(activo: boolean, aoSair: () => void) {
  const suporta = suportaEcraInteiro();
  const [dentro, setDentro] = useState(() => !suporta || (typeof document !== "undefined" && !!document.fullscreenElement));
  const fora = useRef(false);
  const aoSairRef = useRef(aoSair);
  useEffect(() => {
    aoSairRef.current = aoSair;
  }, [aoSair]);

  useEffect(() => {
    if (!activo) return;
    const sair = () => {
      if (fora.current) return;
      fora.current = true;
      aoSairRef.current();
    };
    const aoMudarVisibilidade = () => {
      if (document.visibilityState === "hidden") sair();
    };
    const aoMudarEcra = () => {
      if (document.fullscreenElement) {
        setDentro(true);
        fora.current = false;
      } else if (suporta) {
        setDentro(false);
        sair();
      }
    };
    document.addEventListener("visibilitychange", aoMudarVisibilidade);
    document.addEventListener("fullscreenchange", aoMudarEcra);
    window.addEventListener("blur", sair);
    return () => {
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
      document.removeEventListener("fullscreenchange", aoMudarEcra);
      window.removeEventListener("blur", sair);
    };
  }, [activo, suporta]);

  const voltar = useCallback(async () => {
    await entrarEcraInteiro();
    fora.current = false;
    setDentro(!suporta || !!document.fullscreenElement);
  }, [suporta]);

  return { suporta, dentro, voltar };
}
