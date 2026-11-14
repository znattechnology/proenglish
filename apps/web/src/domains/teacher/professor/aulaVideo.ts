/**
 * Transcrição e frases de uma aula em vídeo (editor do professor).
 * API Django: /api/v1/teacher/aulas/<id>/transcricao/, /aulas/<id>/frases/..., /frases/<id>/.
 */
import { professorApi, type EstadoTranscricao } from "./api";

export type LinhaTranscricao = { start: number; end: number; text: string };
export type Transcricao = EstadoTranscricao & { linhas: LinhaTranscricao[] };

export type FraseAula = {
  id: number;
  texto: string;
  traducao: string;
  tipo: "frase" | "palavra";
  estado: "proposta" | "aprovada";
  inicio: number | null;
  fim: number | null;
  ordem: number;
  criada_por_ia: boolean;
};

export type FrasesAula = {
  aula: { id: string; titulo: string; resumo: string; curso: { id: string; titulo: string }; tem_transcricao: boolean };
  frases: FraseAula[];
  ia: { estado: "a_processar" | "pronta" | "erro" | null; erro: string | null };
};

export type NovaFrase = Pick<FraseAula, "texto" | "traducao" | "tipo"> & Partial<Pick<FraseAula, "inicio" | "fim" | "estado">>;

export const aulaVideoApi = professorApi.enhanceEndpoints({ addTagTypes: ["Transcricao", "FrasesAula"] }).injectEndpoints({
  endpoints: (build) => ({
    transcricao: build.query<Transcricao, string>({
      query: (aula) => `/teacher/aulas/${aula}/transcricao/`,
      providesTags: (_r, _e, aula) => [{ type: "Transcricao", id: aula }],
    }),
    guardarTranscricao: build.mutation<Transcricao, { aula: string; linhas: LinhaTranscricao[] }>({
      query: ({ aula, linhas }) => ({ url: `/teacher/aulas/${aula}/transcricao/`, method: "PUT", body: { linhas } }),
      invalidatesTags: (_r, _e, a) => [{ type: "Transcricao", id: a.aula }, { type: "FrasesAula", id: a.aula }, "Estrutura"],
    }),
    transcrever: build.mutation<Transcricao, { aula: string; forcar?: boolean }>({
      query: ({ aula, forcar }) => ({ url: `/teacher/aulas/${aula}/transcricao/`, method: "POST", body: { forcar: !!forcar } }),
      invalidatesTags: (_r, _e, a) => [{ type: "Transcricao", id: a.aula }, "Estrutura"],
    }),
    frasesAula: build.query<FrasesAula, string>({
      query: (aula) => `/teacher/aulas/${aula}/frases/`,
      providesTags: (_r, _e, aula) => [{ type: "FrasesAula", id: aula }],
    }),
    novaFrase: build.mutation<FraseAula, { aula: string } & NovaFrase>({
      query: ({ aula, ...body }) => ({ url: `/teacher/aulas/${aula}/frases/`, method: "POST", body }),
      invalidatesTags: (_r, _e, a) => [{ type: "FrasesAula", id: a.aula }, "Verificacao"],
    }),
    proporFrases: build.mutation<FrasesAula, string>({
      query: (aula) => ({ url: `/teacher/aulas/${aula}/frases/propor/`, method: "POST", body: {} }),
      invalidatesTags: (_r, _e, aula) => [{ type: "FrasesAula", id: aula }],
    }),
    aprovarTodas: build.mutation<FrasesAula, string>({
      query: (aula) => ({ url: `/teacher/aulas/${aula}/frases/aprovar-todas/`, method: "POST", body: {} }),
      invalidatesTags: (_r, _e, aula) => [{ type: "FrasesAula", id: aula }, "Verificacao"],
    }),
    mudarFrase: build.mutation<FraseAula, { aula: string; id: number } & Partial<NovaFrase>>({
      query: ({ id, aula: _aula, ...body }) => ({ url: `/teacher/frases/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, a) => [{ type: "FrasesAula", id: a.aula }, "Verificacao"],
    }),
    apagarFrase: build.mutation<void, { aula: string; id: number }>({
      query: ({ id }) => ({ url: `/teacher/frases/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, a) => [{ type: "FrasesAula", id: a.aula }, "Verificacao"],
    }),
  }),
});

export const {
  useTranscricaoQuery,
  useGuardarTranscricaoMutation,
  useTranscreverMutation,
  useFrasesAulaQuery,
  useNovaFraseMutation,
  useProporFrasesMutation,
  useAprovarTodasMutation,
  useMudarFraseMutation,
  useApagarFraseMutation,
} = aulaVideoApi;

/** 75.4 -> "1:15". */
export function mmss(s: number | null | undefined) {
  if (s == null || !Number.isFinite(s)) return "";
  const t = Math.max(0, Math.floor(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

/** "1:15" ou "75" -> 75; vazio -> null; inválido -> undefined. */
export function lerTempo(v: string): number | null | undefined {
  const t = v.trim();
  if (!t) return null;
  const m = t.match(/^(\d{1,3}):([0-5]?\d(?:\.\d+)?)$/);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  return /^\d+(\.\d+)?$/.test(t) ? Number(t) : undefined;
}
