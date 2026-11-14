/**
 * Revisão de hoje (repetição espaçada do banco de frases). Igual a apps/web/src/domains/student/revisao/api.ts.
 * API Django: /api/v1/student/revisao/. Os exercícios e a correcção vêm do servidor.
 */
import { api } from "@/api/base";
import type { DetalhePronuncia } from "@/dominios/laboratorio/api";
import { enviarGravacao, type Gravacao } from "@/dominios/laboratorio/gravacao";

const R = "/student/revisao";

export type FormaRevisao = "escolher" | "completar" | "traduzir" | "ouvir_repetir";
export type EstadoItem = "vista" | "reconhecida" | "com_ajuda" | "sozinho";

export type ExercicioRevisao = {
  id: string;
  origem: "item" | "padrao";
  forma: FormaRevisao;
  item_id: number | null;
  estado: EstadoItem | null;
  nova: boolean;
  padrao: { chave: string; descricao: string } | null;
  titulo: string;
  texto_en: string | null;
  traducao: string | null;
  frase_com_espaco: string | null;
  opcoes: string[] | null;
  audio_texto: string | null;
};

export type SessaoRevisao = { dia: string; total: number; para_rever: number; novos: number; minutos: number; exercicios: ExercicioRevisao[] };

export type ResumoRevisao = { para_rever: number; minutos: number; feitas_hoje: number };

export type AnaliseGravacao = { nota: number; aceite: boolean; transcricao: string; palavras: string[]; mensagem: string | null; detalhe?: DetalhePronuncia | null };

export type ResultadoRevisao = {
  correcta: boolean;
  nota: "errei" | "dificil" | "certo" | "facil";
  contou: boolean;
  resposta_certa: string;
  texto: string;
  traducao: string | null;
  explicacao: string | null;
  estado_antes: EstadoItem | null;
  estado_depois: EstadoItem | null;
  subiu: boolean;
  /** A frase deixou de contar como dita sozinho (falhou em dias seguidos). */
  desceu?: boolean;
  pontos: number;
  proxima_revisao: string | null;
  intervalo_dias: number | null;
  semelhanca?: number;
  analise?: AnaliseGravacao;
};

export type FimRevisao = {
  respondidos: number;
  acertos: number;
  pontos: number;
  minutos: number;
  subiram: { texto: string; traducao: string | null; antes: EstadoItem; depois: EstadoItem; depois_rotulo: string }[];
  /** Frases 'sozinho' falhadas em dias seguidos: voltaram a 'com_ajuda'. */
  desceram?: { texto: string; traducao: string | null; antes: EstadoItem; depois: EstadoItem; depois_rotulo: string }[];
  restam_hoje: number;
  amanha: number;
  meta: { minutos_hoje: number; meta_minutos: number; cumprida: boolean; sequencia: number };
};

export const revisaoApi = api
  .enhanceEndpoints({ addTagTypes: ["Revisao", "LabProgresso", "LabSequencia", "Estatisticas", "Liga", "Conquistas", "InicioResumo"] })
  .injectEndpoints({
    endpoints: (build) => ({
      resumoRevisao: build.query<ResumoRevisao, void>({
        query: () => `${R}/resumo/`,
        providesTags: ["Revisao"],
      }),
      sessaoRevisao: build.query<SessaoRevisao, void>({
        query: () => `${R}/hoje/`,
        keepUnusedDataFor: 0,
      }),
      responderRevisao: build.mutation<ResultadoRevisao, { exercicioId: string; forma: FormaRevisao; resposta: string; segundos: number }>({
        query: ({ exercicioId, forma, resposta, segundos }) => ({
          url: `${R}/responder/`,
          method: "POST",
          body: { exercicio_id: exercicioId, forma, resposta, segundos, pistas: 0 },
        }),
      }),
      saltarRevisao: build.mutation<{ saltado: boolean; pontos: number; proxima_revisao: string | null }, { exercicioId: string }>({
        query: ({ exercicioId }) => ({ url: `${R}/saltar/`, method: "POST", body: { exercicio_id: exercicioId } }),
      }),
      terminarRevisao: build.mutation<FimRevisao, { inicio: string }>({
        query: ({ inicio }) => ({ url: `${R}/terminar/`, method: "POST", body: { inicio } }),
        invalidatesTags: ["Revisao", "LabProgresso", "LabSequencia", "Estatisticas", "Liga", "Conquistas", "InicioResumo"],
      }),
    }),
  });

export const { useResumoRevisaoQuery, useSessaoRevisaoQuery, useResponderRevisaoMutation, useSaltarRevisaoMutation, useTerminarRevisaoMutation } = revisaoApi;

/** Ouvir e repetir: a gravação vai em multipart. */
export function falarRevisao(exercicioId: string, g: Gravacao, segundos: number) {
  return enviarGravacao<ResultadoRevisao>(`${R}/falar/`, { exercicio_id: exercicioId, segundos: String(segundos) }, g);
}

/** "7 frases" / "1 frase". */
export function nFrases(n: number) {
  return `${n} ${n === 1 ? "frase" : "frases"}`;
}
