/**
 * Primeira entrada (acolhimento): quem acabou de criar conta e ainda não escolheu a área nem fez o
 * acolhimento vai primeiro para /primeira-entrada (igual ao painel da web,
 * apps/web/app/(estudante)/user/dashboard/page.tsx).
 */
import { router } from "expo-router";
import { useEffect } from "react";
import { useSessao } from "@/sessao/ContextoSessao";
import type { Preferencias } from "./api";

/** true quando o estudante ainda tem de passar pela primeira entrada. */
export function usePrecisaPrimeiraEntrada() {
  const { utilizador } = useSessao();
  const pref = (utilizador?.preferences ?? {}) as Preferencias;
  // Sem `preferences` o perfil completo ainda não chegou: não decidir já.
  return !!utilizador && utilizador.role === "student" && !!utilizador.preferences && !pref.acolhimento && !pref.area;
}

/**
 * Para o separador Início: se for preciso, troca o ecrã pela primeira entrada (uma vez).
 * Devolve o mesmo booleano, para o ecrã não mostrar nada enquanto muda.
 */
export function useIrParaPrimeiraEntrada() {
  const precisa = usePrecisaPrimeiraEntrada();
  useEffect(() => {
    if (precisa) router.push("/primeira-entrada");
  }, [precisa]);
  return precisa;
}

/** Áreas (as mesmas categorias dos cursos). */
export const AREAS: { valor: string; nome: string }[] = [
  { valor: "Industry English", nome: "Petróleo e Gás" },
  { valor: "Financial English", nome: "Banca" },
  { valor: "Business English", nome: "Negócios" },
  { valor: "Medical English", nome: "Saúde" },
  { valor: "Legal English", nome: "Direito" },
  { valor: "Technical English", nome: "Tecnologia" },
  { valor: "General English", nome: "Outra área" },
];

export const METAS = [
  { min: 5, nome: "Leve" },
  { min: 10, nome: "Normal" },
  { min: 15, nome: "Sério" },
  { min: 20, nome: "Intenso" },
];

/** 5 perguntas, da mais fácil à mais difícil (A1 a C1), em frases do trabalho. */
export const PERGUNTAS: { frase: [string, string]; opcoes: string[]; certa: number }[] = [
  { frase: ["I ", " an engineer at the refinery."], opcoes: ["am", "is", "are"], certa: 0 },
  { frase: ["Yesterday we ", " the report to the manager."], opcoes: ["send", "sent", "sending"], certa: 1 },
  { frase: ["If the valve ", ", we will stop the line."], opcoes: ["leaks", "will leak", "leaked"], certa: 0 },
  { frase: ["The audit, ", " was carried out last month, found two issues."], opcoes: ["who", "what", "which"], certa: 2 },
  { frase: ["Had we known about the delay, we ", " the client earlier."], opcoes: ["would warn", "would have warned", "will warn"], certa: 1 },
];
