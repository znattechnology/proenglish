/**
 * Exame oral de um curso (fase 6): tipos e textos partilhados pelo aluno e pelo professor.
 * Espelha apps/api/apps/practice/conversa/exame.py (exame_dict).
 */
import type { NivelCefr } from "./niveis";

export type NotasExame = { fluencia: number | null; gramatica: number | null; vocabulario: number | null; tarefa: number | null; pronuncia: number | null };

export type ExameOral = {
  id: string;
  curso: { id: string; titulo: string };
  estado: "em_curso" | "a_avaliar" | "avaliado" | "insuficiente" | "anulado";
  criado_em: string;
  avaliado_em: string | null;
  notas: NotasExame;
  /** Nota da IA (0-100). */
  nota_ia: number | null;
  /** A que conta: a do professor, quando a reviu; senão a da IA. */
  nota: number | null;
  nota_minima: number;
  aprovado: boolean;
  nivel_cefr: NivelCefr | null;
  frases_usadas: string[];
  frases_total: number;
  relatorio: string | null;
  a_treinar: string[];
  pode_repetir_em: string | null;
  consentimento_gravacao: boolean;
  gravacao_url: string | null;
  gravacao_apagada: boolean;
  revisao: { nota: number; comentario: string; por: string | null; em: string | null } | null;
  sessao_id: string | null;
};

/** Ordem e nomes das competências do exame. A pronúncia só aparece quando for medida. */
export const COMPETENCIAS_EXAME: { chave: keyof NotasExame; nome: string; ajuda: string }[] = [
  { chave: "fluencia", nome: "Fluência", ajuda: "Falar sem parar muito e manter a conversa" },
  { chave: "gramatica", nome: "Gramática", ajuda: "Frases correctas para o nível do curso" },
  { chave: "vocabulario", nome: "Vocabulário", ajuda: "Palavras do trabalho e do curso" },
  { chave: "tarefa", nome: "Tarefas", ajuda: "Fazer o que cada tarefa pedia" },
  { chave: "pronuncia", nome: "Pronúncia", ajuda: "Clareza dos sons" },
];

export const dataCurta = (iso: string) => new Date(iso).toLocaleDateString("pt-PT", { day: "numeric", month: "long" });

/** Dia e hora na hora de Luanda (ex.: "21 de novembro às 14:30"), para quando o aluno pode repetir. */
export const dataHoraLuanda = (iso: string) => {
  const d = new Date(iso);
  const dia = d.toLocaleDateString("pt-PT", { day: "numeric", month: "long", timeZone: "Africa/Luanda" });
  const hora = d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit", timeZone: "Africa/Luanda" });
  return `${dia} às ${hora} (hora de Luanda)`;
};
