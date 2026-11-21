/**
 * Subscrição, planos e pagamentos por Multicaixa Express (em kwanzas).
 * Igual a apps/web/src/domains/student/subscricao/api.ts (tipos do que a API Django devolve).
 * Só subscrição: não há compras de cursos avulsos.
 */
import { api } from "@/api/base";

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
  destaque?: boolean;
  dias_teste?: number;
  pode_experimentar?: boolean;
  /** Plano desactivado que o aluno ainda tem: só pode renová-lo. */
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
  status: string;
  started_at: string | null;
  expires_at: string | null;
  canceled_at: string | null;
  days_until_expiry: number | null;
  is_active_subscription: boolean;
  lembretes_renovacao: boolean;
  termina_em?: string | null;
  termina_hoje?: boolean;
  pode_renovar?: boolean;
  renovavel_a_partir_de?: string | null;
  periodo?: Periodo | null;
  valor_periodo_kz?: number | null;
  em_teste?: boolean;
  teste_termina_em?: string | null;
  pode_experimentar?: boolean;
  dias_teste?: number;
  plano_teste?: TipoPlano | null;
  daily_usage?: { lessons_used: number; lessons_limit: number | null; speaking_minutes_used: number; speaking_limit: number | null };
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
  estado: EstadoPagamento;
};

/** Orçamento calculado no servidor: preço, código, crédito dos dias já pagos e o que fica a pagar. */
export type Orcamento = {
  plano: { id: string; nome: string; tipo: TipoPlano };
  periodo: Periodo;
  operacao: "nova" | "renovacao" | "mudanca_plano" | "conversao_teste";
  pode_comprar: boolean;
  motivo_bloqueio: string | null;
  preco_base_kz: number;
  codigo: { codigo: string; tipo: string; valor: number; descricao: string; continua?: boolean } | null;
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

/**
 * Oferta de plano quando o aluno chega a um limite (vidas, lições, análises, conversa, exame,
 * certificado). Vem no corpo do erro ou do GET; null = já tem o melhor plano ou nenhum resolve.
 * O cliente só mostra: quem decide o plano e os ganhos é a API (apps/api/apps/subscriptions/oferta.py).
 */
export type OfertaPlano = {
  recurso: "vidas" | "licoes" | "analises" | "conversa" | "exame" | "certificado";
  plano: { tipo: Exclude<TipoPlano, "FREE">; nome: string; preco_mensal_kz: number; preco_anual_kz: number | null; dias_teste: number; pode_experimentar: boolean };
  /** O primeiro é o que resolve este limite. */
  ganhos: string[];
  /** Rota da web; na app vai-se para /checkout/<tipo>. */
  ligacao: string;
};

function eOferta(v: unknown): v is OfertaPlano {
  const o = v as OfertaPlano | null | undefined;
  return !!o && typeof o === "object" && !!o.plano && typeof o.plano.tipo === "string" && Array.isArray(o.ganhos);
}

/**
 * A oferta que vem num erro da API ({status, data: {oferta}}) ou num corpo já lido ({oferta}).
 * undefined = a resposta não traz o campo; null = traz, mas não há plano a sugerir.
 */
export function ofertaDe(v: unknown): OfertaPlano | null | undefined {
  const x = v as { data?: { oferta?: unknown }; oferta?: unknown } | null | undefined;
  const corpo = x && typeof x === "object" && x.data && typeof x.data === "object" && "oferta" in x.data ? x.data : x;
  if (!corpo || typeof corpo !== "object" || !("oferta" in corpo)) return undefined;
  return eOferta(corpo.oferta) ? corpo.oferta : null;
}

export const subscricaoApi = api.enhanceEndpoints({ addTagTypes: ["Subscricao", "Pagamentos", "Planos"] }).injectEndpoints({
  endpoints: (build) => ({
    subPlanos: build.query<Plano[], void>({
      query: () => "/subscriptions/plans/",
      transformResponse: (r: Plano[] | { results: Plano[] }) => (Array.isArray(r) ? r : r.results).slice().sort((a, b) => a.sort_order - b.sort_order),
      providesTags: ["Planos"],
    }),
    subMinha: build.query<MinhaSubscricao, void>({
      query: () => "/subscriptions/my-subscription/",
      providesTags: ["Subscricao"],
    }),
    subLembretes: build.mutation<{ lembretes_renovacao: boolean }, boolean>({
      query: (ligados) => ({ url: "/subscriptions/my-subscription/lembretes/", method: "PATCH", body: { lembretes_renovacao: ligados } }),
      invalidatesTags: ["Subscricao"],
    }),
    subOrcamento: build.query<Orcamento, { plano: string; periodo: Periodo; codigo?: string | null }>({
      query: ({ plano, periodo, codigo }) => ({ url: "/pagamentos/orcamento/", params: { plan: plano, periodo, ...(codigo ? { codigo } : {}) } }),
      providesTags: ["Subscricao"],
    }),
    /** Nada a pagar (crédito ou código cobrem o preço): activa sem Multicaixa. */
    subAtivarSemPagamento: build.mutation<Pagamento, { planId: string; periodo: Periodo; codigo?: string | null }>({
      query: ({ planId, periodo, codigo }) => ({ url: "/pagamentos/sem-pagamento/", method: "POST", body: { plan_id: planId, periodo, ...(codigo ? { codigo_promocional: codigo } : {}) } }),
      invalidatesTags: ["Subscricao", "Pagamentos"],
    }),
    /** Teste grátis do plano. Um teste por número Multicaixa Express. */
    subIniciarTeste: build.mutation<TesteIniciado, { plano: TipoPlano; telefone: string }>({
      query: ({ plano, telefone }) => ({ url: "/pagamentos/teste/", method: "POST", body: { plano, telefone } }),
      invalidatesTags: ["Subscricao", "Planos"],
    }),
    subCriarPagamento: build.mutation<Pagamento, { planId: string; periodo: Periodo; telefone: string; codigo?: string | null }>({
      query: ({ planId, periodo, telefone, codigo }) => ({
        url: "/pagamentos/multicaixa/",
        method: "POST",
        body: { tipo: "subscricao", plan_id: planId, periodo, telefone, ...(codigo ? { codigo_promocional: codigo } : {}) },
      }),
    }),
    subPagamento: build.query<Pagamento, string>({
      query: (id) => `/pagamentos/${id}/`,
      keepUnusedDataFor: 0,
      // Quando fica pago, a subscrição e o histórico mudaram.
      async onQueryStarted(_id, { dispatch, queryFulfilled }) {
        try {
          const { data } = await queryFulfilled;
          if (data.estado === "pago") dispatch(api.util.invalidateTags(["Subscricao", "Pagamentos", "StudentProgress", "Perfil"] as never));
        } catch {
          /* o ecrã mostra o erro */
        }
      },
    }),
    subCancelarPagamento: build.mutation<Pagamento, string>({
      query: (id) => ({ url: `/pagamentos/${id}/cancelar/`, method: "POST", body: {} }),
    }),
    subHistorico: build.query<Historico, void>({
      query: () => "/subscriptions/payment-history/",
      providesTags: ["Pagamentos"],
    }),
    subRecibo: build.query<Recibo, string>({
      query: (numero) => `/pagamentos/recibos/${encodeURIComponent(numero)}/`,
    }),
  }),
});

export const {
  useSubPlanosQuery,
  useSubMinhaQuery,
  useSubLembretesMutation,
  useSubOrcamentoQuery,
  useSubAtivarSemPagamentoMutation,
  useSubIniciarTesteMutation,
  useSubCriarPagamentoMutation,
  useSubPagamentoQuery,
  useSubCancelarPagamentoMutation,
  useSubHistoricoQuery,
  useSubReciboQuery,
} = subscricaoApi;

/* ------------------------------------------------------------------ */
/* Formatação                                                          */
/* ------------------------------------------------------------------ */
/** "9 900 Kz", "14 950 Kz": agrupa sempre os milhares. */
export const kz = (v: number | string | null | undefined) => `${String(Math.round(Number(v ?? 0))).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} Kz`;

/** "14 950 Kz/mês" */
export const kzMes = (v: number | string | null | undefined) => `${kz(v)}/mês`;

/** Número com milhares agrupados ("1 240"). */
export const milhares = (v: number | null | undefined) => String(Math.round(Number(v ?? 0))).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

/**
 * Datas como no canvas (grafia pré-2009, meses com maiúscula):
 * longa "2 de Dezembro de 2026", diaMes "2 de Dezembro", mesAno "Dezembro de 2026", curta "2 Dez".
 */
export function dataPt(iso: string | null | undefined, formato: "longa" | "diaMes" | "mesAno" | "curta" = "longa") {
  if (!iso) return "";
  // Só a data ("2026-11-08"): meio-dia local, para não mudar de dia com o fuso.
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return "";
  const dia = d.getDate();
  const mes = MESES[d.getMonth()];
  if (formato === "diaMes") return `${dia} de ${mes}`;
  if (formato === "mesAno") return `${mes} de ${d.getFullYear()}`;
  if (formato === "curta") return `${dia} ${MESES_CURTOS[d.getMonth()]}`;
  return `${dia} de ${mes} de ${d.getFullYear()}`;
}

/** "14:30" (hora local). */
export function horaPt(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
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

/** Vantagens de cada plano em linguagem simples. */
export function vantagens(p: Plano): string[] {
  const l: string[] = [];
  l.push(p.daily_lessons_limit ? `${p.daily_lessons_limit} lições por dia` : "Lições ilimitadas");
  l.push(p.hearts_limit > 0 ? `${p.hearts_limit} vidas, que voltam com o tempo` : "Vidas ilimitadas");
  if (p.daily_speaking_minutes == null) l.push("Conversa com o tutor sem limite diário");
  else if (p.daily_speaking_minutes > 0) l.push(`${p.daily_speaking_minutes} minutos de conversa com o tutor por dia`);
  if (p.certificates) l.push("Certificados de conclusão");
  return l;
}

/**
 * Número Multicaixa Express usado nesta sessão da app (a web guarda-o no sessionStorage):
 * serve para "Enviar o pedido outra vez" sem voltar a escrever.
 */
let telefoneMcx = "";
export const numeroMcx = {
  get: () => telefoneMcx,
  set: (d: string) => {
    telefoneMcx = d;
  },
};
