/** Opinião do aluno sobre a plataforma: quando pedir, enviar e adiar. */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";

export type EstadoOpiniao = { should_show_prompt: boolean; trigger: string | null; chave: string | null; frase: string | null };
export type NovaOpiniao = { rating: number; comment?: string; trigger?: string; context_data?: Record<string, unknown>; allow_public?: boolean; allow_contact?: boolean; feedback_type?: string };

export const opiniaoApi = createApi({
  reducerPath: "opiniaoApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Estado"],
  endpoints: (build) => ({
    estadoOpiniao: build.query<EstadoOpiniao, void>({ query: () => "/users/feedback/status/", providesTags: ["Estado"] }),
    enviarOpiniao: build.mutation<{ message: string }, NovaOpiniao>({
      query: (body) => ({ url: "/users/feedback/submit/", method: "POST", body }),
      invalidatesTags: ["Estado"],
    }),
    adiarOpiniao: build.mutation<unknown, { trigger: string; chave: string }>({
      query: ({ trigger, chave }) => ({ url: "/users/feedback/dismiss/", method: "POST", body: { trigger, action: "skipped", context_data: { chave } } }),
      invalidatesTags: ["Estado"],
    }),
  }),
});

export const { useEstadoOpiniaoQuery, useEnviarOpiniaoMutation, useAdiarOpiniaoMutation } = opiniaoApi;

export const NOTAS = ["Mau", "Fraco", "Razoável", "Bom", "Muito bom"];
