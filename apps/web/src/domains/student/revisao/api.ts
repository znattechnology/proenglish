/**
 * Revisão de hoje (repetição espaçada do banco de frases). API Django: /api/v1/student/revisao/.
 * Fica na fatia do laboratório para partilhar a cache (vidas, sequência, meta do dia).
 */
import { aposEstudo, quandoCorrerBem } from "@/src/domains/student/sincronizar";
import { DJANGO_BASE_URL } from "@/src/domains/shared/api/baseQuery";
import type { AnaliseGravacao } from "@/src/domains/student/curso/fala";
import { studentPracticeApiSlice } from "../practice-courses/api/studentPracticeApiSlice";
import { enviarGravacao } from "../laboratorio/enviarGravacao";

const R = `${DJANGO_BASE_URL}/student/revisao`;

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

export type SessaoRevisao = {
  dia: string;
  total: number;
  para_rever: number;
  novos: number;
  minutos: number;
  exercicios: ExercicioRevisao[];
};

export type ResumoRevisao = { para_rever: number; minutos: number; feitas_hoje: number };

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

export const revisaoApi = studentPracticeApiSlice.injectEndpoints({
  endpoints: (build) => ({
    resumoRevisao: build.query<ResumoRevisao, void>({
      query: () => `${R}/resumo/`,
      providesTags: ["Revisao"],
    }),
    sessaoRevisao: build.query<SessaoRevisao, void>({
      query: () => `${R}/hoje/`,
      // A sessão é lida uma vez ao abrir; não recarrega por baixo do jogador.
      keepUnusedDataFor: 0,
    }),
    responderRevisao: build.mutation<ResultadoRevisao, { exercicioId: string; forma: FormaRevisao; resposta: string; segundos: number; pistas?: number }>({
      query: ({ exercicioId, forma, resposta, segundos, pistas }) => ({
        url: `${R}/responder/`,
        method: "POST",
        body: { exercicio_id: exercicioId, forma, resposta, segundos, pistas: pistas ?? 0 },
      }),
    }),
    falarRevisao: build.mutation<ResultadoRevisao, { exercicioId: string; audio: Blob; segundos: number }>({
      // fetch próprio (multipart), com renovação da sessão num 401.
      queryFn: ({ exercicioId, audio, segundos }) =>
        enviarGravacao<ResultadoRevisao>(`${R}/falar/`, () => {
          const corpo = new FormData();
          corpo.append("audio", audio, "gravacao.webm");
          corpo.append("exercicio_id", exercicioId);
          corpo.append("segundos", String(segundos));
          return corpo;
        }),
    }),
    /** Saltar um exercício falado (sem microfone, sem análises, análise em baixo): sem pontos; a frase volta amanhã. */
    saltarRevisao: build.mutation<{ saltado: boolean; pontos: number; proxima_revisao: string | null }, { exercicioId: string }>({
      query: ({ exercicioId }) => ({ url: `${R}/saltar/`, method: "POST", body: { exercicio_id: exercicioId } }),
    }),
    terminarRevisao: build.mutation<FimRevisao, { inicio: string }>({
      query: ({ inicio }) => ({ url: `${R}/terminar/`, method: "POST", body: { inicio } }),
      invalidatesTags: ["Revisao", "StudentProgress", "StudentStreak"],
      onQueryStarted: quandoCorrerBem(aposEstudo),
    }),
  }),
  overrideExisting: process.env.NODE_ENV === "development",
});

export const { useResumoRevisaoQuery, useSessaoRevisaoQuery, useResponderRevisaoMutation, useFalarRevisaoMutation, useSaltarRevisaoMutation, useTerminarRevisaoMutation } = revisaoApi;

/** "7 frases" / "1 frase". */
export function nFrases(n: number) {
  return `${n} ${n === 1 ? "frase" : "frases"}`;
}
