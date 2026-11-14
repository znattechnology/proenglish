/**
 * Falar depois do vídeo de uma aula: frases aprovadas pelo professor, "Repetir em voz alta"
 * (análise de pronúncia) e a conversa de 3 minutos com o tutor.
 * API Django: /api/v1/student/video-courses/chapters/<id>/fala|frases/<f>/falar|conversa/.
 */
import { DJANGO_BASE_URL } from "@/src/domains/shared/api/baseQuery";
import type { ConversaLicao } from "@/src/domains/student/laboratorio/api";
import { cursoApi } from "./api";

const BASE = "/student/video-courses";

export type EstadoBanco = "vista" | "reconhecida" | "com_ajuda" | "sozinho";

export type FraseDaAula = {
  id: number;
  texto: string;
  traducao: string;
  tipo: "frase" | "palavra";
  inicio: number | null;
  fim: number | null;
  /** Estado da frase no banco do aluno (null: ainda não entrou). */
  estado: EstadoBanco | null;
};

export type FalaDaAula = {
  frases: FraseDaAula[];
  conversa: { disponivel: boolean; motivo: string | null; mensagem: string | null; max_segundos: number };
};

export type AnaliseFrase = {
  analise: { nota: number; aceite: boolean; transcricao: string; palavras: string[]; mensagem: string | null };
  estado: EstadoBanco | null;
};

export type ErroFala = { codigo?: string; mensagem?: string; alternativa?: "revisao" };

export const falaAulaApi = cursoApi.enhanceEndpoints({ addTagTypes: ["FalaAula"] }).injectEndpoints({
  endpoints: (build) => ({
    falaDaAula: build.query<FalaDaAula, string>({
      query: (chapterId) => `${BASE}/chapters/${chapterId}/fala/`,
      providesTags: (_r, _e, id) => [{ type: "FalaAula", id }],
    }),
    falarFrase: build.mutation<AnaliseFrase, { chapterId: string; fraseId: number; audio: Blob; segundos: number }>({
      // fetch próprio: a base desta fatia força JSON e a gravação vai em multipart.
      queryFn: async ({ chapterId, fraseId, audio, segundos }) => {
        const corpo = new FormData();
        corpo.append("audio", audio, "gravacao.webm");
        corpo.append("segundos", String(segundos));
        try {
          const r = await fetch(`${DJANGO_BASE_URL}${BASE}/chapters/${chapterId}/frases/${fraseId}/falar/`, { method: "POST", body: corpo, credentials: "include" });
          const dados = await r.json().catch(() => ({}));
          if (!r.ok) return { error: { status: r.status, data: dados } };
          return { data: dados as AnaliseFrase };
        } catch (e) {
          return { error: { status: "FETCH_ERROR", error: String(e) } };
        }
      },
    }),
    comecarConversaAula: build.mutation<ConversaLicao, string>({
      query: (chapterId) => ({ url: `${BASE}/chapters/${chapterId}/conversa/`, method: "POST", body: {} }),
    }),
  }),
  overrideExisting: process.env.NODE_ENV === "development",
});

export const { useFalaDaAulaQuery, useFalarFraseMutation, useComecarConversaAulaMutation } = falaAulaApi;

/** A mensagem de erro que a API devolveu (ou a de recurso). */
export function erroFala(e: unknown, recurso: string): ErroFala {
  const d = (e as { data?: ErroFala })?.data;
  return { codigo: d?.codigo, mensagem: d?.mensagem ?? recurso, alternativa: d?.alternativa };
}
