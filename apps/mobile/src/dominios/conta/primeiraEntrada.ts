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

/** O curso geral: todos começam por ele (English Communication Skills). */
export const AREA_GERAL = "General English";

/** O que quer aprender (as mesmas categorias dos cursos; igual a AREAS da web). O inglês geral primeiro. */
export const AREAS: { valor: string; nome: string }[] = [
  { valor: AREA_GERAL, nome: "Inglês geral" },
  { valor: "Industry English", nome: "Petróleo e Gás" },
  { valor: "Financial English", nome: "Banca" },
  { valor: "Business English", nome: "Negócios" },
  { valor: "Medical English", nome: "Saúde" },
  { valor: "Legal English", nome: "Direito" },
  { valor: "Technical English", nome: "Tecnologia" },
];

/** "Inglês geral" ou "Inglês para <área>". */
export function rotuloArea(a: { valor: string; nome: string }) {
  return a.valor === AREA_GERAL ? a.nome : `Inglês para ${a.nome}`;
}

export const METAS = [
  { min: 5, nome: "Leve" },
  { min: 10, nome: "Normal" },
  { min: 15, nome: "Sério" },
  { min: 20, nome: "Intenso" },
];
