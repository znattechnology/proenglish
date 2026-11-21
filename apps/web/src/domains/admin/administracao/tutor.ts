/** Configuração do tutor de conversa (modelo de IA no Vapi e duração máxima): /api/v1/admin/tutor/. */
import { administracaoApi } from "./api";

export type ConfiguracaoTutor = {
  provedor: "anthropic" | "openai";
  modelo: string;
  max_minutos_sessao: number;
  alterado_em: string | null;
  sugestoes: Record<"anthropic" | "openai", string[]>;
};

const api = administracaoApi.enhanceEndpoints({ addTagTypes: ["Tutor"] }).injectEndpoints({
  endpoints: (build) => ({
    configuracaoTutor: build.query<ConfiguracaoTutor, void>({ query: () => "/admin/tutor/", providesTags: ["Tutor"] }),
    mudarConfiguracaoTutor: build.mutation<ConfiguracaoTutor, Partial<Pick<ConfiguracaoTutor, "provedor" | "modelo" | "max_minutos_sessao">>>({
      query: (body) => ({ url: "/admin/tutor/", method: "PATCH", body }),
      invalidatesTags: ["Tutor"],
    }),
  }),
});

export const { useConfiguracaoTutorQuery, useMudarConfiguracaoTutorMutation } = api;
