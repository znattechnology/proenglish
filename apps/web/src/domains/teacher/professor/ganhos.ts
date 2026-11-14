/** Ganhos do professor: parte das subscrições do mês, dividida pelo tempo que os alunos pagantes passam nos cursos de cada um. */
import { diaMesCurto, professorApi } from "./api";

export type ContaRecebimento = { banco: string; banco_nome: string; terminada_em: string; titular: string; confirmada_em?: string | null };
export type Ganhos = {
  percentagem: number;
  dia_pagamento: number;
  regras?: { segundos_por_exercicio: number; max_pratica_min_dia: number; max_video_min_dia: number };
  este_mes: { valor_kz: number; ate: string; alunos_pagantes: number; minutos: number };
  proximo_pagamento: { data: string; referente: string };
  total_recebido: { valor_kz: number; desde: string | null };
  meses: { mes: string; nome: string; alunos: number; minutos: number; valor_kz: number; pago_a: string; pago_em?: string | null; estado: "a_processar" | "pago" }[];
  conta: ContaRecebimento | null;
  alteracao_pendente: (ContaRecebimento & { expira_em: string }) | null;
};

export const ganhosApi = professorApi.enhanceEndpoints({ addTagTypes: ["Ganhos"] }).injectEndpoints({
  endpoints: (build) => ({
    ganhos: build.query<Ganhos, void>({ query: () => "/teacher/ganhos/", providesTags: ["Ganhos"] }),
    bancos: build.query<{ valor: string; nome: string }[], void>({ query: () => "/teacher/ganhos/bancos/", keepUnusedDataFor: 3600 }),
    pedirMudancaConta: build.mutation<{ alteracao_pendente: Ganhos["alteracao_pendente"]; mensagem: string }, { banco: string; iban: string; titular: string }>({
      query: (body) => ({ url: "/teacher/ganhos/conta/", method: "POST", body }),
      invalidatesTags: ["Ganhos"],
    }),
    confirmarConta: build.mutation<Ganhos, string>({
      query: (codigo) => ({ url: "/teacher/ganhos/conta/confirmar/", method: "POST", body: { codigo } }),
      invalidatesTags: ["Ganhos"],
    }),
    cancelarMudancaConta: build.mutation<unknown, void>({
      query: () => ({ url: "/teacher/ganhos/conta/pendente/", method: "DELETE" }),
      invalidatesTags: ["Ganhos"],
    }),
  }),
});

export const { useGanhosQuery, useBancosQuery, usePedirMudancaContaMutation, useConfirmarContaMutation, useCancelarMudancaContaMutation } = ganhosApi;

export { kz } from "@/src/domains/student/subscricao/api";
export const diaMes = (iso: string) => diaMesCurto(new Date(`${iso.slice(0, 10)}T12:00:00`));
