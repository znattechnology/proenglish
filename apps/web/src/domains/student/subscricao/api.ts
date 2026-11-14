/**
 * Subscrição, planos e pagamentos por Multicaixa Express (em kwanzas).
 * Tipos iguais ao que a API Django devolve (apps/subscriptions e apps/pagamentos).
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";

export type TipoPlano = "FREE" | "PREMIUM" | "PREMIUM_PLUS";
export type Periodo = "mensal" | "anual";

export type Plano = {
  id: string;
  name: string;
  plan_type: TipoPlano;
  description: string;
  monthly_price: string;
  yearly_price: string | null;
  yearly_discount_percentage: number;
  is_most_popular: boolean;
  /** Plano em destaque (escolhido na administração). */
  destaque?: boolean;
  /** Dias de teste grátis do plano (0 = sem teste). */
  dias_teste?: number;
  /** Quem pede pode começar o teste grátis deste plano. */
  pode_experimentar?: boolean;
  /** Plano desactivado que o aluno ainda tem (ou teve há pouco): só pode renová-lo, não está à venda. */
  so_renovacao?: boolean;
  is_active?: boolean;
  features: string[];
  daily_lessons_limit: number | null;
  daily_speaking_minutes: number | null;
  hearts_limit: number;
  certificates: boolean;
  advanced_analytics: boolean;
  multiple_devices: number;
  sort_order: number;
};

export type MinhaSubscricao = {
  plan: Plano;
  status: "ACTIVE" | "CANCELED" | "EXPIRED" | "TRIAL" | string;
  started_at: string | null;
  expires_at: string | null;
  canceled_at: string | null;
  days_until_expiry: number | null;
  is_active_subscription: boolean;
  lembretes_renovacao: boolean;
  /** Fim do período pago (null no Gratuito). */
  termina_em?: string | null;
  /** O plano termina hoje (data de Angola). */
  termina_hoje?: boolean;
  /** Pode pagar já a renovação (a mesma regra que o servidor aplica). */
  pode_renovar?: boolean;
  renovavel_a_partir_de?: string | null;
  periodo?: Periodo | null;
  /** Preço do período actual para renovar (ex.: 149 500 Kz por ano). */
  valor_periodo_kz?: number | null;
  /** Está a experimentar um plano pago sem pagar. */
  em_teste?: boolean;
  teste_termina_em?: string | null;
  /** Pode começar um teste grátis (nunca experimentou nem pagou). */
  pode_experimentar?: boolean;
  /** Dias do teste em curso, ou do maior teste disponível. */
  dias_teste?: number;
  /** Plano a que pertencem esses dias de teste (para o botão "Experimentar N dias grátis"). */
  plano_teste?: TipoPlano | null;
  daily_usage?: {
    lessons_used: number;
    lessons_limit: number | null;
    speaking_minutes_used: number;
    speaking_limit: number | null;
  };
};

export type EstadoPagamento = "pendente" | "pago" | "recusado" | "expirado" | "cancelado";

export type Pagamento = {
  id: string;
  tipo: "subscricao";
  estado: EstadoPagamento;
  descricao: string;
  valor_kz: number;
  desconto_kz: number;
  total_kz: number;
  telefone_mascarado: string | null;
  codigo_promocional: string | null;
  credito_kz?: number;
  credito_dias_restantes?: number;
  credito_plano?: { nome: string; tipo: TipoPlano } | null;
  dias_extra?: number;
  metodo_codigo?: "multicaixa_express" | "sem_pagamento";
  periodo: Periodo | null;
  plano: { id: string; nome: string; tipo: TipoPlano } | null;
  motivo_falha: string | null;
  criado_em: string;
  expira_em: string | null;
  pago_em: string | null;
  numero_recibo: string | null;
  simulado: boolean;
  ativacao: { plano?: { nome: string; tipo: TipoPlano; periodo: Periodo; inicio?: string; expira_em: string | null } } | null;
};

export type EntradaHistorico = {
  id: string;
  date: string;
  description: string;
  amount_kz: number;
  method?: string;
  phone_masked?: string;
  receipt_number?: string | null;
  status?: EstadoPagamento | string;
  credit_kz?: number;
  extra_days?: number;
};

export type Historico = {
  payment_history: EntradaHistorico[];
  summary: { total_amount_paid: number; total_payments: number; currency: string };
};

export type Recibo = {
  numero_recibo: string;
  data_emissao: string;
  cliente: { nome: string; email: string };
  descricao: string;
  periodo_display: string | null;
  validade: { inicio: string; fim: string } | null;
  quantidade: number;
  subtotal_kz: number;
  desconto_kz: number;
  codigo_promocional: string | null;
  total_kz: number;
  metodo: string;
  telefone_mascarado: string | null;
  referencia: string | null;
  credito_kz?: number;
  credito_descricao?: string | null;
  linhas?: { tipo: string; descricao: string; preco_unitario_kz: number; total_kz: number }[];
  estado: EstadoPagamento;
};

/** Orçamento calculado no servidor: preço, código, crédito dos dias já pagos e o que fica a pagar. */
export type Orcamento = {
  plano: { id: string; nome: string; tipo: TipoPlano };
  periodo: Periodo;
  /** conversao_teste: paga o plano que está a experimentar; o período pago começa no fim do teste. */
  operacao: "nova" | "renovacao" | "mudanca_plano" | "conversao_teste";
  pode_comprar: boolean;
  motivo_bloqueio: string | null;
  preco_base_kz: number;
  codigo: {
    codigo: string;
    tipo: string;
    valor: number;
    descricao: string;
    duracao?: "primeiro" | "meses" | "sempre";
    duracao_meses?: number | null;
    /** Desconto de um código que já tinha e que continua nesta renovação. */
    continua?: boolean;
  } | null;
  desconto_codigo_kz: number;
  erro_codigo: { code: string; mensagem: string } | null;
  aviso_codigo: string | null;
  credito_kz: number;
  credito_total_kz: number;
  credito_dias_restantes: number;
  credito_plano: { nome: string; tipo: TipoPlano; termina_em: string } | null;
  dias_extra: number;
  final_kz: number;
  requer_pagamento: boolean;
  inicio: string;
  termina_em: string;
  linhas: { tipo: "plano" | "codigo" | "credito"; descricao: string; valor_kz: number }[];
  em_teste: boolean;
  teste_termina_em: string | null;
  pode_experimentar: boolean;
  dias_teste: number;
};

export type TesteIniciado = {
  plano: { id: string; nome: string; tipo: TipoPlano };
  status: string;
  em_teste: boolean;
  teste_termina_em: string | null;
  pode_experimentar: boolean;
  dias_teste: number;
  mensagem: string;
};

export type PrevisaoCodigo = { promo_code: string; original_price: string; discount_amount: string; final_price: string; description?: string };

/** Erro devolvido pela API: {error, code?}. */
/** Mensagens genéricas do servidor que não ajudam o aluno: usa-se o texto por omissão. */
const GENERICAS = /^(validation error|resource not found|permission denied|not found|internal server error|bad request)$/i;

/**
 * Texto de um erro da API, em qualquer dos formatos que ela usa:
 * {error: "texto"}, {error: true, message}, {mensagem, codigo}, {detail}, ou {details: {campo: [..]}}.
 */
export function mensagemErro(e: unknown, padrao = "Não foi possível concluir. Tente outra vez.") {
  const erro = e as { status?: number | string; data?: unknown } | undefined;
  if (erro?.status === "FETCH_ERROR") return "Sem ligação ao servidor. Verifique a Internet e tente outra vez.";
  const d = erro?.data as Record<string, unknown> | undefined;
  // Um 429 com mensagem própria (ex.: "Pode enviar outro daqui a 24 h") diz mais do que o texto genérico.
  const propria429 = erro?.status === 429 && d && typeof d === "object" ? [d.mensagem, d.message, d.error].find((v) => typeof v === "string" && v.trim() && !GENERICAS.test(v.trim())) : null;
  if (erro?.status === 429) return (propria429 as string | undefined) ?? "Fez muitos pedidos seguidos. Espere um pouco e tente outra vez.";
  if (!d || typeof d !== "object") return padrao;
  const texto = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : Array.isArray(v) && typeof v[0] === "string" ? v[0] : null);
  const detalhes = d.details && typeof d.details === "object" ? (d.details as Record<string, unknown>) : null;
  const candidatos = [d.mensagem, d.error, d.message, d.detail, detalhes?.detail, detalhes?.non_field_errors, ...(detalhes ? Object.values(detalhes) : [])];
  for (const c of candidatos) {
    const t = texto(c);
    if (t && !GENERICAS.test(t.trim())) return t;
  }
  return padrao;
}
export function codigoErro(e: unknown) {
  const d = (e as { data?: { code?: string; codigo?: string } } | undefined)?.data;
  return d?.code ?? d?.codigo;
}

export const subscricaoApi = createApi({
  reducerPath: "subscricaoApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Subscricao", "Pagamentos", "Planos"],
  endpoints: (build) => ({
    planos: build.query<Plano[], void>({
      query: () => "/subscriptions/plans/",
      transformResponse: (r: Plano[] | { results: Plano[] }) => (Array.isArray(r) ? r : r.results).slice().sort((a, b) => a.sort_order - b.sort_order),
      providesTags: ["Planos"],
    }),
    minhaSubscricao: build.query<MinhaSubscricao, void>({
      query: () => "/subscriptions/my-subscription/",
      providesTags: ["Subscricao"],
    }),
    lembretes: build.mutation<{ lembretes_renovacao: boolean }, boolean>({
      query: (ligados) => ({ url: "/subscriptions/my-subscription/lembretes/", method: "PATCH", body: { lembretes_renovacao: ligados } }),
      invalidatesTags: ["Subscricao"],
    }),
    orcamento: build.query<Orcamento, { plano: string; periodo: Periodo; codigo?: string | null }>({
      query: ({ plano, periodo, codigo }) => ({ url: "/pagamentos/orcamento/", params: { plan: plano, periodo, ...(codigo ? { codigo } : {}) } }),
      providesTags: ["Subscricao"],
    }),
    /** Quando não há nada a pagar (crédito ou código cobrem o preço): activa sem Multicaixa. */
    ativarSemPagamento: build.mutation<Pagamento, { planId: string; periodo: Periodo; codigo?: string | null }>({
      query: ({ planId, periodo, codigo }) => ({
        url: "/pagamentos/sem-pagamento/",
        method: "POST",
        body: { plan_id: planId, periodo, ...(codigo ? { codigo_promocional: codigo } : {}) },
      }),
      invalidatesTags: ["Subscricao", "Pagamentos"],
    }),
    /** Começa o teste grátis do plano (sem pagamento). Um teste por número Multicaixa Express. */
    iniciarTeste: build.mutation<TesteIniciado, { plano: TipoPlano; telefone: string }>({
      query: ({ plano, telefone }) => ({ url: "/pagamentos/teste/", method: "POST", body: { plano, telefone } }),
      invalidatesTags: ["Subscricao", "Planos"],
    }),
    preverCodigo: build.mutation<PrevisaoCodigo, { codigo: string; planId: string; periodo: Periodo }>({
      query: ({ codigo, planId, periodo }) => ({ url: "/subscriptions/apply-promo-code/", method: "POST", body: { promo_code: codigo, plan_id: planId, periodo } }),
    }),
    criarPagamento: build.mutation<Pagamento, { planId: string; periodo: Periodo; telefone: string; codigo?: string | null }>({
      query: ({ planId, periodo, telefone, codigo }) => ({
        url: "/pagamentos/multicaixa/",
        method: "POST",
        body: { tipo: "subscricao", plan_id: planId, periodo, telefone, ...(codigo ? { codigo_promocional: codigo } : {}) },
      }),
    }),
    pagamento: build.query<Pagamento, string>({
      query: (id) => `/pagamentos/${id}/`,
      // Quando fica pago, a subscrição e o histórico mudaram.
      async onQueryStarted(_id, { dispatch, queryFulfilled }) {
        try {
          const { data } = await queryFulfilled;
          if (data.estado === "pago") dispatch(subscricaoApi.util.invalidateTags(["Subscricao", "Pagamentos"]));
        } catch {
          /* o ecrã mostra o erro */
        }
      },
    }),
    cancelarPagamento: build.mutation<Pagamento, string>({
      query: (id) => ({ url: `/pagamentos/${id}/cancelar/`, method: "POST", body: {} }),
    }),
    historico: build.query<Historico, void>({
      query: () => "/subscriptions/payment-history/",
      providesTags: ["Pagamentos"],
    }),
    recibo: build.query<Recibo, string>({
      query: (numero) => `/pagamentos/recibos/${encodeURIComponent(numero)}/`,
    }),
  }),
});

export const {
  usePlanosQuery,
  useMinhaSubscricaoQuery,
  useLembretesMutation,
  usePreverCodigoMutation,
  useOrcamentoQuery,
  useAtivarSemPagamentoMutation,
  useIniciarTesteMutation,
  useCriarPagamentoMutation,
  usePagamentoQuery,
  useCancelarPagamentoMutation,
  useHistoricoQuery,
  useReciboQuery,
} = subscricaoApi;

/* ------------------------------------------------------------------ */
/* Formatação                                                          */
/* ------------------------------------------------------------------ */
/** "9 900 Kz", "14 950 Kz": agrupa sempre os milhares (o pt-PT não agrupa números de 4 dígitos). */
export const kz = (v: number | string | null | undefined) =>
  `${String(Math.round(Number(v ?? 0))).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0")}\u00a0Kz`;

const MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
/** "5 Dez" (ou "5 Dez 2026"): o Chrome escreve "5/12" com month:"short" em pt-PT, por isso fazemos à mão. */
export function diaMesCurto(d: Date, comAno = false) {
  return `${d.getDate()} ${MESES_CURTOS[d.getMonth()]}${comAno ? ` ${d.getFullYear()}` : ""}`;
}

export function dataPt(iso: string | null | undefined, opcoes: Intl.DateTimeFormatOptions = { day: "numeric", month: "long", year: "numeric" }) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-PT", opcoes);
}

export function precoPlano(p: Plano, periodo: Periodo) {
  return Number(periodo === "anual" && p.yearly_price ? p.yearly_price : p.monthly_price);
}

/** Período que o plano aceita: sem preço anual, é sempre mensal. */
export function periodoDoPlano(p: Plano, periodo: Periodo): Periodo {
  return periodo === "anual" && Number(p.yearly_price) > 0 ? "anual" : "mensal";
}

/** Número de telemóvel angolano para mostrar: "923 456 789". */
export function telefoneLegivel(digitos: string) {
  const d = digitos.replace(/\D/g, "").slice(0, 9);
  return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9)].filter(Boolean).join(" ");
}

/** Vantagens de cada plano em linguagem simples (a lista "features" da API está em maiúsculas e mistura inglês). */
export function vantagens(p: Plano): string[] {
  const l: string[] = [];
  l.push(p.daily_lessons_limit ? `${p.daily_lessons_limit} lições por dia` : "Lições ilimitadas");
  l.push(p.hearts_limit > 0 ? `${p.hearts_limit} vidas, que voltam com o tempo` : "Vidas ilimitadas");
  // null = sem limite; 0 = o plano não inclui conversa
  if (p.daily_speaking_minutes == null) l.push("Conversa com o tutor sem limite diário");
  else if (p.daily_speaking_minutes > 0) l.push(`${p.daily_speaking_minutes} minutos de conversa com o tutor por dia`);
  if (p.certificates) l.push("Certificados de conclusão");
  return l;
}
