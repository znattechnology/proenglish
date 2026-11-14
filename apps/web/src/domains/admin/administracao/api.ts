/**
 * Área da administração (base nova). Todas as rotas exigem papel admin (ou superutilizador).
 * Números reais: nada aqui é inventado no cliente.
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";

export type Papel = "student" | "teacher" | "admin";
export type TipoPlano = "FREE" | "PREMIUM" | "PREMIUM_PLUS";
export type EstadoUtilizador = "activo" | "email_por_verificar" | "suspenso";
export type Pessoa = { id: string; nome: string; email: string; iniciais: string };

export type Painel = {
  numeros: {
    utilizadores: number;
    novos_mes: number;
    estudantes: number;
    pagantes: number;
    professores: number;
    professores_por_activar: number;
    email_por_verificar: number;
    email_por_verificar_3d: number;
    assinantes_pagos: number;
    receita_mes_kz: number;
  };
  atencao: { pagamentos_falhados_semana: number; terminam_3_dias: number; opinioes_por_rever: number; cursos_em_revisao: number };
  por_plano: PorPlano[];
  recentes: { id: string; nome: string; email: string; papel: Papel; criado_em: string }[];
};

/** Utilizadores de um plano: nos pagos, separa quem pagou, quem está em teste e quem o recebeu sem pagar. */
export type PorPlano = { plano: TipoPlano; nome: string; utilizadores: number; pagos?: number; em_teste?: number; atribuidos?: number };

export type LinhaUtilizador = Pessoa & { papel: Papel; plano: string | null; estado: EstadoUtilizador; ultima_entrada: string | null };
export type ListaUtilizadores = {
  numeros: { total: number; novos_mes: number; estudantes: number; pagantes: number; professores: number; professores_por_activar: number; email_por_verificar: number; email_por_verificar_3d: number };
  total: number;
  paginas: number;
  resultados: LinhaUtilizador[];
};
export type FiltroUtilizadores = { q?: string; papel?: Papel; plano?: TipoPlano; estado?: EstadoUtilizador; pagina: number };

export type DetalheUtilizador = {
  utilizador: {
    id: string;
    nome: string;
    email: string;
    telefone: string | null;
    papel: Papel;
    provincia: string | null;
    provincia_nome?: string | null;
    profissao: string | null;
    cidade: string | null;
    plano: { tipo: TipoPlano; nome: string; periodo: "mensal" | "anual" | null; renova_a: string | null; termina_a: string | null } | null;
    estado: EstadoUtilizador;
    suspensao: { motivo: string; nota: string; desde: string; por: string | null } | null;
    email_verificado: boolean;
    verificado_em: string | null;
    entra_com_google: boolean;
    tem_senha: boolean;
    criado_em: string;
    ultima_entrada: string | null;
    deve_mudar_senha?: boolean;
    /** Email novo à espera de confirmação (o antigo continua a valer até lá). */
    email_pendente?: string | null;
    /** Quem está a ver pode gerir esta conta (um administrador só é gerido por superutilizadores). */
    pode_gerir?: boolean;
  };
  numeros: { cursos: number; concluidos: number; pontos: number; dias_seguidos: number };
  actividade: { quando: string; texto: string }[];
  pagamentos: { id: string; data: string; descricao: string; valor_kz: number; estado: "pago" | "pendente" | "falhou" | "expirado" | "cancelado" }[];
  professor: { cursos_publicados: number; alunos: number; publica_sem_revisao: boolean } | null;
};
export type MudancaUtilizador = Partial<{ nome: string; email: string; telefone: string | null; papel: Papel; plano: TipoPlano; publica_sem_revisao: boolean; provincia: string | null }>;
export type MotivoSuspensao = "pagamento_contestado" | "partilha_conta" | "abusivo" | "pedido_proprio" | "outro";

export type Convite = { email_enviado?: boolean; message?: string; id: string; email: string; nome: string; area: string; publica_sem_revisao: boolean; estado: "pendente" | "aceite" | "expirado" | "cancelado"; enviado_em: string; expira_em: string };

export type EstadoCurso = "rascunho" | "em_revisao" | "publicado" | "arquivado";
export type LinhaCurso = { id: string; titulo: string; tipo: "video" | "pratica"; professor: { id: string; nome: string }; area: string | null; nivel: string | null; estado: EstadoCurso; alunos: number; conclusao: number | null; actualizado_em: string | null; submetido_em: string | null };
export type ListaCursos = {
  numeros: { publicados: number; publicados_video: number; publicados_pratica: number; rascunhos: number; rascunhos_parados_30d: number; em_revisao: number; inscricoes: number; inscricoes_mes: number; conclusao_media: number | null };
  total: number;
  paginas: number;
  resultados: LinhaCurso[];
};
export type AnaliseCursos = {
  periodo: number;
  activos_dia_media: number;
  activos_dia: { dia: string; n: number }[];
  activos_semana: number;
  pct_activos_semana: number | null;
  inscricoes_novas: number;
  inscricoes_variacao_pct: number | null;
  licoes_concluidas: number;
  licoes_por_dia: number;
  por_area: { area: string; inscricoes: number }[];
  conclusao_baixa: { id: string; titulo: string; tipo: "video" | "pratica"; alunos: number; conclusao: number; desistencia: { texto: string; alunos: number; pct: number } | null }[];
  gerado_em?: string;
  cache_segundos?: number;
};
export type ItemVerificacao = { chave: string; titulo: string; ok: boolean; detalhe: string };
export type CursoEmRevisao = {
  id: string;
  tipo: "video" | "pratica";
  titulo: string;
  descricao: string;
  area: string | null;
  nivel: string | null;
  estado: EstadoCurso;
  imagem: string | null;
  professor: { id: string; nome: string; email: string };
  submetido_em: string | null;
  aprovado_em: string | null;
  motivo_recusa: string | null;
  estado_antes_revisao?: "arquivado" | "rascunho" | null;
  verificacao: { itens: ItemVerificacao[]; pode_submeter: boolean };
};
export type ExercicioRevisao = { id: string; tipo: string; enunciado: string; frase: string; opcoes: { texto: string; certa: boolean }[]; pares: { a: string; b: string }[]; resposta: string; explicacao: string; audio_url: string | null };
export type DetalheRevisao = {
  curso: CursoEmRevisao & { acesso?: "todos" | "premium"; motivo_recusa: string | null };
  professor: { id: string; nome: string; email: string; cursos_publicados: number };
  verificacao: { itens: ItemVerificacao[]; pode_submeter: boolean };
  estrutura: {
    seccoes?: { id: string; titulo: string; aulas: { id: string; titulo: string; tipo?: string; video: { url: string; nome: string | null } | null; duracao_s: number | null; resumo: string; materiais: { id: string; nome: string; url: string }[]; questionario: { activo: boolean; perguntas: number; nota_minima: number } }[] }[];
    unidades?: { id: string; titulo: string; licoes: { id: string; titulo: string; exercicios: ExercicioRevisao[] }[] }[];
  };
};

export const administracaoApi = createApi({
  reducerPath: "administracaoApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Painel", "Utilizadores", "Utilizador", "Convites", "Cursos", "Revisao"],
  endpoints: (build) => ({
    provincias: build.query<{ valor: string; nome: string }[], void>({ query: () => "/users/provincias/", keepUnusedDataFor: 3600 }),
    painelAdmin: build.query<Painel, void>({ query: () => "/admin/painel/", providesTags: ["Painel"] }),
    utilizadores: build.query<ListaUtilizadores, FiltroUtilizadores>({
      query: (f) => ({ url: "/admin/utilizadores/", params: Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined && v !== "")) }),
      providesTags: ["Utilizadores"],
    }),
    utilizador: build.query<DetalheUtilizador, string>({ query: (id) => `/admin/utilizadores/${id}/`, providesTags: ["Utilizador"] }),
    mudarUtilizador: build.mutation<DetalheUtilizador, { id: string } & MudancaUtilizador>({
      query: ({ id, ...body }) => ({ url: `/admin/utilizadores/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Utilizador", "Utilizadores", "Painel"],
    }),
    suspender: build.mutation<unknown, { id: string; motivo: MotivoSuspensao; nota: string; avisar: boolean }>({
      query: ({ id, ...body }) => ({ url: `/admin/utilizadores/${id}/suspender/`, method: "POST", body }),
      invalidatesTags: ["Utilizador", "Utilizadores", "Painel"],
    }),
    reactivar: build.mutation<unknown, string>({
      query: (id) => ({ url: `/admin/utilizadores/${id}/reactivar/`, method: "POST", body: {} }),
      invalidatesTags: ["Utilizador", "Utilizadores", "Painel"],
    }),
    terminarSessoes: build.mutation<unknown, string>({ query: (id) => ({ url: `/admin/utilizadores/${id}/terminar-sessoes/`, method: "POST", body: {} }) }),
    obrigarMudarSenha: build.mutation<unknown, string>({
      query: (id) => ({ url: `/admin/utilizadores/${id}/obrigar-mudar-senha/`, method: "POST", body: {} }),
      invalidatesTags: ["Utilizador"],
    }),
    enviarEmail: build.mutation<{ enviados: number; falhados: number; a_enviar?: number; em_segundo_plano?: boolean; message?: string }, { ids: string[]; assunto: string; mensagem: string }>({
      query: (body) => ({ url: "/admin/utilizadores/email/", method: "POST", body }),
    }),
    convites: build.query<Convite[], void>({ query: () => "/admin/convites/", providesTags: ["Convites"] }),
    convidar: build.mutation<Convite, { email: string; nome: string; area: string; publica_sem_revisao: boolean }>({
      query: (body) => ({ url: "/admin/convites/", method: "POST", body }),
      invalidatesTags: ["Convites", "Painel", "Utilizadores"],
    }),
    cancelarConvite: build.mutation<void, string>({ query: (id) => ({ url: `/admin/convites/${id}/`, method: "DELETE" }), invalidatesTags: ["Convites", "Painel"] }),
    reenviarConvite: build.mutation<unknown, string>({ query: (id) => ({ url: `/admin/convites/${id}/reenviar/`, method: "POST", body: {} }), invalidatesTags: ["Convites"] }),

    cursosAdmin: build.query<ListaCursos, { tipo?: string; estado?: string; q?: string; pagina: number }>({
      query: (f) => ({ url: "/admin/cursos/", params: Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined && v !== "")) }),
      providesTags: ["Cursos"],
    }),
    analiseCursos: build.query<AnaliseCursos, number>({ query: (periodo) => ({ url: "/admin/cursos/analise/", params: { periodo } }) }),
    filaRevisao: build.query<{ total: number; resultados: CursoEmRevisao[] }, void>({ query: () => "/admin/cursos/revisao/", providesTags: ["Revisao"] }),
    cursoRevisao: build.query<DetalheRevisao, string>({ query: (id) => `/admin/cursos/${id}/`, providesTags: ["Revisao"] }),
    aprovar: build.mutation<unknown, string>({ query: (id) => ({ url: `/admin/cursos/${id}/aprovar/`, method: "POST", body: {} }), invalidatesTags: ["Revisao", "Cursos", "Painel"] }),
    recusar: build.mutation<unknown, { id: string; motivo: string }>({
      query: ({ id, motivo }) => ({ url: `/admin/cursos/${id}/recusar/`, method: "POST", body: { motivo } }),
      invalidatesTags: ["Revisao", "Cursos", "Painel"],
    }),
    arquivarAdmin: build.mutation<unknown, { id: string; modo: "manter" | "fechar"; motivo: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/cursos/${id}/arquivar/`, method: "POST", body }),
      invalidatesTags: ["Revisao", "Cursos", "Painel"],
    }),
  }),
});

export const {
  useProvinciasQuery,
  usePainelAdminQuery,
  useUtilizadoresQuery,
  useUtilizadorQuery,
  useMudarUtilizadorMutation,
  useSuspenderMutation,
  useReactivarMutation,
  useTerminarSessoesMutation,
  useObrigarMudarSenhaMutation,
  useEnviarEmailMutation,
  useConvitesQuery,
  useConvidarMutation,
  useCancelarConviteMutation,
  useReenviarConviteMutation,
  useCursosAdminQuery,
  useAnaliseCursosQuery,
  useFilaRevisaoQuery,
  useCursoRevisaoQuery,
  useAprovarMutation,
  useRecusarMutation,
  useArquivarAdminMutation,
} = administracaoApi;

export const PAPEL: Record<Papel, string> = { student: "Estudante", teacher: "Professor", admin: "Administrador" };
export const ESTADO_UTILIZADOR: Record<EstadoUtilizador, { nome: string; tipo: "certo" | "realce" | "errado" }> = {
  activo: { nome: "Activo", tipo: "certo" },
  email_por_verificar: { nome: "Email por verificar", tipo: "realce" },
  suspenso: { nome: "Suspenso", tipo: "errado" },
};
export const MOTIVOS: Record<MotivoSuspensao, string> = {
  pagamento_contestado: "Pagamento contestado",
  partilha_conta: "Partilha da conta",
  abusivo: "Comportamento abusivo",
  pedido_proprio: "Pedido da própria pessoa",
  outro: "Outro",
};

/** "Hoje, 08:14", "Ontem", "Há 5 dias", "2 Nov". */
export function quandoEntrou(iso: string | null, agora = new Date()) {
  if (!iso) return "Nunca";
  const d = new Date(iso);
  const dias = Math.floor((new Date(agora).setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);
  const hora = d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
  if (dias <= 0) return `Hoje, ${hora}`;
  if (dias === 1) return "Ontem";
  if (dias < 30) return `Há ${dias} dias`;
  return diaMesCurto(d);
}
