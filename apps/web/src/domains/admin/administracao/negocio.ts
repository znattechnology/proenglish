/** Administração: subscrições, pagamentos, planos, códigos, opiniões, ganhos dos professores e relatórios. */
import { administracaoApi, type Pessoa, type PorPlano, type TipoPlano } from "./api";

export type EstadoSubscricao = "activa" | "em_teste" | "a_expirar" | "falhou" | "cancelada";
export type ResumoSubscricoes = {
  assinantes_pagos: number;
  premium: number;
  premium_plus: number;
  em_teste: number;
  receita_mes_kz: number;
  receita_ate: string;
  passam_a_pagar_pct: number | null;
  cancelam_pct: number | null;
  por_plano: PorPlano[];
  recentes: { id: string; utilizador: Pessoa; descricao: string; valor_kz: number; data: string }[];
  atencao: { falhados_semana: number; falhados_semana_kz: number; terminam_3_dias: number };
};
export type LinhaSubscricao = { id: string; utilizador: Pessoa; plano: string; periodo: "mensal" | "anual" | "teste"; estado: EstadoSubscricao; proxima_data: string | null; pagamento: string | null; nota: string | null };
export type ListaSubscricoes = { total: number; pagas: number; em_teste: number; paginas: number; resultados: LinhaSubscricao[] };
export type PagamentoFalhado = { id: string; utilizador: Pessoa; plano: string; valor_kz: number; falhou_a: string; motivo: string; pedidos: number };

export type Plano = {
  id: string;
  tipo: TipoPlano;
  nome: string;
  descricao: string;
  preco_mensal_kz: number;
  preco_anual_kz: number | null;
  dias_teste: number;
  destaque: boolean;
  activo: boolean;
  limites: { licoes_dia: number | null; vidas: number | null; conversa_min_dia: number | null; sessoes_nativo_mes: number; protecoes_semana: number };
  certificados: boolean;
  utilizadores: number;
  assinantes: number;
};
export type MudancaPlano = Partial<Omit<Plano, "id" | "tipo" | "utilizadores" | "assinantes" | "limites">> & { limites?: Partial<Plano["limites"]> };

export type Utilizacao = { utilizador: { id: string; nome: string; email: string }; data: string; valor_desconto_kz: number; plano: string; periodo: string; renovacao: boolean };
export type EstadoCodigo = "rascunho" | "activo" | "esgotado" | "expirado" | "desligado";
export type Codigo = {
  id: string;
  codigo: string;
  desconto: { tipo: "percentagem" | "valor"; valor: number };
  aplica: { planos: TipoPlano[]; periodo: "todos" | "mensal" | "anual" };
  duracao: { tipo: "primeiro" | "meses" | "sempre"; meses: number | null };
  so_primeira_compra: boolean;
  max_usos: number | null;
  usos: number;
  termina: string | null;
  estado: EstadoCodigo;
  descricao: string;
  exemplo?: string;
  /** Já tem pagamentos ou reservas: desconto, planos e duração não podem mudar. */
  bloqueado?: boolean;
};
export type NovoCodigo = Omit<Codigo, "id" | "usos" | "estado" | "descricao" | "exemplo"> & { estado?: "rascunho" | "activo" };
export type ListaCodigos = { numeros: { activos: number; rascunhos: number; usados_mes: number; pessoas_mes: number; desconto_mes_kz: number; continuam_2_mes_pct: number | null }; resultados: Codigo[] };

export type Opiniao = {
  id: string;
  nome: string;
  area: string | null;
  plano: string | null;
  nota: number;
  comentario: string;
  momento: string;
  estado: "por_rever" | "aprovada" | "recusada";
  permite_publico: boolean;
  permite_contacto: boolean;
  /** Email da pessoa, só quando aceitou ser contactada. */
  contacto?: string | null;
  criada_em: string;
  nota_interna: string;
};
export type ListaOpinioes = { numeros: { total: number; novas_mes: number; media: number | null; por_rever: number; por_rever_publicas: number; no_site: number }; total: number; paginas: number; resultados: Opiniao[] };
export type Testemunho = { id: string; nome_curto: string; area: string | null; texto: string; nota: number; mostrar: boolean; ordem: number };

export type LinhaGanho = {
  id: string;
  professor: { id: string; nome: string; email: string };
  mes: string;
  alunos: number;
  minutos: number;
  quota: number;
  valor_kz: number;
  conta: { banco: string; banco_nome: string; terminada_em: string; titular: string; confirmada_em: string | null } | null;
  estado: "a_processar" | "pago";
  pago_em: string | null;
  referencia: string;
};
export type GanhosMes = { mes: string; nome: string; pago_a: string; percentagem: number; total_kz: number; por_pagar_kz: number; linhas: LinhaGanho[] };

export type Relatorio = {
  periodo: number;
  periodo_receita_kz?: number;
  periodo_anterior_receita_kz?: number;
  receita_recorrente_mes_kz?: number;
  receita_mes_variacao_pct?: number | null;
  receita_mes_kz: number;
  receita_variacao_pct: number | null;
  receita_por_assinante_kz: number | null;
  retencao_3_meses_pct: number | null;
  teste_para_pago_pct: number | null;
  receita_por_mes: { mes: string; nome_curto: string; valor_kz: number }[];
  por_provincia: { provincia: string; nome: string; assinantes: number }[];
  sem_provincia: number;
  assinantes_total: number;
};

const api = administracaoApi.enhanceEndpoints({ addTagTypes: ["Subscricoes", "Falhados", "Planos", "Codigos", "Opinioes", "Testemunhos", "Ganhos"] }).injectEndpoints({
  endpoints: (build) => ({
    resumoSubscricoes: build.query<ResumoSubscricoes, void>({ query: () => "/admin/subscricoes/resumo/", providesTags: ["Subscricoes"] }),
    subscricoes: build.query<ListaSubscricoes, { estado: string; q?: string; pagina: number; dias?: number }>({
      query: ({ estado, q, pagina, dias }) => ({ url: "/admin/subscricoes/", params: { estado, pagina, ...(q ? { q } : {}), ...(dias && estado === "a_expirar" ? { dias } : {}) } }),
      providesTags: ["Subscricoes"],
    }),
    falhados: build.query<{ total_em_risco_kz: number; resultados: PagamentoFalhado[] }, void>({ query: () => "/admin/pagamentos/falhados/", providesTags: ["Falhados"] }),
    novoPedido: build.mutation<{ aviso?: string | null }, string>({ query: (id) => ({ url: `/admin/pagamentos/${id}/novo-pedido/`, method: "POST", body: {} }), invalidatesTags: ["Falhados", "Subscricoes"] }),
    lembrete: build.mutation<unknown, string>({ query: (id) => ({ url: `/admin/pagamentos/${id}/lembrete/`, method: "POST", body: {} }) }),

    planos: build.query<Plano[], void>({ query: () => "/admin/planos/", providesTags: ["Planos"] }),
    mudarPlano: build.mutation<Plano, { id: string } & MudancaPlano>({ query: ({ id, ...body }) => ({ url: `/admin/planos/${id}/`, method: "PATCH", body }), invalidatesTags: ["Planos"] }),
    codigos: build.query<ListaCodigos, string>({ query: (estado) => ({ url: "/admin/codigos/", params: { estado } }), providesTags: ["Codigos"] }),
    codigo: build.query<Codigo & { utilizacoes?: Utilizacao[] }, string>({ query: (id) => `/admin/codigos/${id}/`, providesTags: ["Codigos"] }),
    criarCodigo: build.mutation<Codigo, NovoCodigo>({ query: (body) => ({ url: "/admin/codigos/", method: "POST", body }), invalidatesTags: ["Codigos"] }),
    mudarCodigo: build.mutation<Codigo, { id: string } & Partial<NovoCodigo>>({ query: ({ id, ...body }) => ({ url: `/admin/codigos/${id}/`, method: "PATCH", body }), invalidatesTags: ["Codigos"] }),
    activarCodigo: build.mutation<Codigo, string>({ query: (id) => ({ url: `/admin/codigos/${id}/activar/`, method: "POST", body: {} }), invalidatesTags: ["Codigos"] }),
    desligarCodigo: build.mutation<Codigo, string>({ query: (id) => ({ url: `/admin/codigos/${id}/desligar/`, method: "POST", body: {} }), invalidatesTags: ["Codigos"] }),

    opinioes: build.query<ListaOpinioes, { estado: string; pagina: number }>({ query: (params) => ({ url: "/admin/opinioes/", params }), providesTags: ["Opinioes"] }),
    mudarOpiniao: build.mutation<Opiniao, { id: string; estado?: Opiniao["estado"]; nota_interna?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/opinioes/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Opinioes", "Testemunhos", "Painel"],
    }),
    testemunhos: build.query<Testemunho[], void>({ query: () => "/admin/testemunhos/", providesTags: ["Testemunhos"] }),
    mudarTestemunho: build.mutation<Testemunho, { id: string; mostrar: boolean }>({ query: ({ id, ...body }) => ({ url: `/admin/testemunhos/${id}/`, method: "PATCH", body }), invalidatesTags: ["Testemunhos"] }),
    ordenarTestemunhos: build.mutation<unknown, string[]>({ query: (ids) => ({ url: "/admin/testemunhos/ordem/", method: "POST", body: { ids } }), invalidatesTags: ["Testemunhos"] }),

    ganhosAdmin: build.query<GanhosMes, string | undefined>({ query: (mes) => ({ url: "/admin/ganhos/", params: mes ? { mes } : {} }), providesTags: ["Ganhos"] }),
    ibanGanho: build.query<{ iban: string; banco: string; banco_nome: string; titular: string }, string>({ query: (id) => `/admin/ganhos/${id}/iban/`, keepUnusedDataFor: 0 }),
    marcarPago: build.mutation<unknown, { id: string; referencia: string }>({
      query: ({ id, referencia }) => ({ url: `/admin/ganhos/${id}/pago/`, method: "POST", body: { referencia } }),
      invalidatesTags: ["Ganhos"],
    }),

    relatorio: build.query<Relatorio, number>({ query: (periodo) => ({ url: "/admin/relatorios/", params: { periodo } }) }),
  }),
});

export const {
  useResumoSubscricoesQuery,
  useSubscricoesQuery,
  useFalhadosQuery,
  useNovoPedidoMutation,
  useLembreteMutation,
  usePlanosQuery,
  useMudarPlanoMutation,
  useCodigosQuery,
  useCodigoQuery,
  useCriarCodigoMutation,
  useMudarCodigoMutation,
  useActivarCodigoMutation,
  useDesligarCodigoMutation,
  useOpinioesQuery,
  useMudarOpiniaoMutation,
  useTestemunhosQuery,
  useMudarTestemunhoMutation,
  useOrdenarTestemunhosMutation,
  useGanhosAdminQuery,
  useLazyIbanGanhoQuery,
  useMarcarPagoMutation,
  useRelatorioQuery,
} = api;

export const ESTADO_SUBSCRICAO: Record<EstadoSubscricao, { nome: string; tipo: "certo" | "realce" | "errado" | "neutra" }> = {
  activa: { nome: "Activa", tipo: "certo" },
  em_teste: { nome: "Em teste", tipo: "realce" },
  a_expirar: { nome: "A expirar", tipo: "realce" },
  falhou: { nome: "Falhou", tipo: "errado" },
  cancelada: { nome: "Cancelada", tipo: "neutra" },
};
