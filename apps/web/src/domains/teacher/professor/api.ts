/**
 * Área do professor (base nova): painel, lista de cursos e ciclo de vida do curso
 * (submeter para revisão, arquivar). Os cursos só chegam ao catálogo depois de o admin aprovar.
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";
import { mensagemErro as mensagemErroBase } from "@/src/domains/student/subscricao/api";
import { nivelEmFrase } from "@/src/domains/shared/niveis";

export type EstadoCurso = "rascunho" | "em_revisao" | "publicado" | "arquivado";
export type TipoCurso = "video" | "pratica";

export type CursoProfessor = {
  id: string;
  tipo: TipoCurso;
  titulo: string;
  area: string | null;
  nivel: string | null;
  estado: EstadoCurso;
  motivo_recusa: string | null;
  imagem: string | null;
  alunos: number;
  conclusao: number | null;
  aulas: number | null;
  aulas_sem_video: number | null;
  seccoes: number | null;
  unidades: number | null;
  licoes: number | null;
  exercicios: number | null;
  acerto: number | null;
  actualizado_em: string | null;
};

export type NumerosCursos = {
  publicados: number;
  rascunhos: number;
  em_revisao: number;
  arquivados?: number;
  alunos: number;
  alunos_novos_mes?: number;
  aulas?: number | null;
  seccoes?: number | null;
  licoes?: number | null;
  exercicios?: number | null;
  conclusao_media: number | null;
  acerto_medio?: number | null;
};

export type Tropeco = { challenge_id: string; licao_id?: string; unidade_id?: string; frase: string; tipo: string; curso_id: string; curso: string; onde: string; erros: number; acerto: number | null };

export type Painel = {
  numeros: NumerosCursos & { arquivados: number; alunos_activos_7d: number };
  cursos: CursoProfessor[];
  tropecos: Tropeco[];
};

export type DefinicoesCurso = {
  visivel_catalogo: boolean;
  inscricao_livre: boolean;
  maximo_alunos: number | null;
  nota_minima: number;
  /** Exame oral obrigatório para o certificado (fase 6) e nota mínima para o passar. */
  exame_oral: boolean;
  nota_minima_exame: number;
  pode_repetir: boolean;
  mostrar_progresso: boolean;
  resumo_semanal: boolean;
  tempo_limite_questionario_min: number | null;
  certificado_automatico: boolean;
};

export type DetalheCurso = CursoProfessor & {
  descricao: string;
  categoria: string;
  nivel_codigo: string;
  submetido_em: string | null;
  aprovado_em: string | null;
  modo_arquivo: "manter" | "fechar" | null;
  arquivado_em: string | null;
  definicoes: DefinicoesCurso;
  /** Último motivo da equipa ProEnglish (recusa ou arquivo), também nos cursos arquivados. */
  motivo_moderacao?: string | null;
  moderacao?: { accao: "recusar" | "arquivar" | null; motivo: string; em: string | null } | null;
  /** Só vem quando a API o conhece; sem ele, as definições não mostram nem enviam o acesso. */
  acesso?: "todos" | "premium";
};

export type Opcao = { valor: string; nome: string; legado?: boolean };
export type NovoCurso = { tipo: TipoCurso; titulo: string; descricao: string; area: string; nivel: string; acesso: "todos" | "premium"; seccoes?: string[]; unidades?: string[] };
export type MudancaCurso = Partial<{ titulo: string; descricao: string; area: string; nivel: string; acesso: "todos" | "premium"; definicoes: Partial<DefinicoesCurso> }>;

export type Material = { id: string; nome: string; url: string; tamanho_bytes: number | null; tipo: string };
export type Aula = {
  id: string;
  titulo: string;
  ordem: number;
  video: { url: string; nome: string | null; tamanho_bytes: number | null } | null;
  duracao_s: number | null;
  percentagem_vista: 50 | 80 | 100;
  tipo?: string;
  seccao?: string;
  /** Falso enquanto a aula não tem vídeo: os alunos ainda não a vêem. */
  visivel_alunos?: boolean;
  resumo: string;
  materiais: Material[];
  questionario: { activo: boolean; perguntas: number; nota_minima: number };
  /** Lição de prática a seguir a esta aula (de um curso de prática do mesmo professor). */
  licao_pratica?: LicaoLigada | null;
  /** Transcrição automática do vídeo (null sem vídeo). */
  transcricao?: EstadoTranscricao | null;
};
export type EstadoTranscricao = {
  estado: "pendente" | "a_processar" | "pronta" | "erro" | "manual" | null;
  erro: string | null;
  origem: "whisper" | "professor" | "existente" | null;
  em: string | null;
  /** Quando foi pedida (pendente/a_processar). */
  desde: string | null;
  /** Transcrição escrita à mão para um vídeo que entretanto foi trocado. */
  video_mudou: boolean;
};
export type LicaoLigada = {
  id: string;
  titulo: string;
  unidade: { id: string; titulo: string };
  curso: { id: string; titulo: string; estado: EstadoCurso };
};
export type CursoComLicoes = {
  id: string;
  titulo: string;
  estado: EstadoCurso;
  unidades: { id: string; titulo: string; licoes: { id: string; titulo: string }[] }[];
};
export type Seccao = { id: string; titulo: string; ordem: number; aulas: Aula[] };
export type Estrutura = { curso: DetalheCurso; seccoes: Seccao[] };

export type Pergunta = { id?: string; enunciado: string; opcoes: string[]; correcta: number; explicacao: string };
export type Questionario = { activo: boolean; nota_minima: number; perguntas: Pergunta[] };

export type ItemVerificacao = { chave: string; titulo: string; ok: boolean; detalhe: string };
/** Recomendações que não impedem a publicação (p.ex. aulas com vídeo sem frases aprovadas). */
export type AvisoVerificacao = { chave: string; titulo: string; detalhe: string };
export type Verificacao = { itens: ItemVerificacao[]; pode_submeter: boolean; avisos?: AvisoVerificacao[] };

export const professorApi = createApi({
  reducerPath: "professorApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Painel", "Cursos", "Verificacao", "Curso", "Estrutura", "Questionario"],
  endpoints: (build) => ({
    painel: build.query<Painel, void>({
      query: () => "/teacher/painel/",
      providesTags: ["Painel"],
    }),
    cursos: build.query<{ numeros: NumerosCursos; resultados: CursoProfessor[] }, { tipo: TipoCurso; estado?: EstadoCurso }>({
      query: ({ tipo, estado }) => ({ url: "/teacher/cursos/", params: estado ? { tipo, estado } : { tipo } }),
      providesTags: ["Cursos"],
    }),
    opcoes: build.query<{ areas: Opcao[]; niveis: Opcao[] }, TipoCurso>({
      query: (tipo) => ({ url: "/teacher/cursos/opcoes/", params: { tipo } }),
      keepUnusedDataFor: 3600,
    }),
    criarCurso: build.mutation<DetalheCurso, NovoCurso>({
      query: (body) => ({ url: "/teacher/cursos/", method: "POST", body }),
      invalidatesTags: ["Painel", "Cursos"],
    }),
    curso: build.query<DetalheCurso, string>({
      query: (id) => `/teacher/cursos/${id}/`,
      providesTags: ["Curso"],
    }),
    mudarCurso: build.mutation<DetalheCurso, { id: string } & MudancaCurso>({
      query: ({ id, ...body }) => ({ url: `/teacher/cursos/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Painel", "Cursos", "Curso", "Estrutura", "Verificacao"],
    }),
    estrutura: build.query<Estrutura, string>({
      query: (id) => `/teacher/cursos/${id}/estrutura/`,
      providesTags: ["Estrutura"],
    }),
    novaSeccao: build.mutation<Seccao, { curso: string; titulo: string }>({
      query: ({ curso, titulo }) => ({ url: `/teacher/cursos/${curso}/seccoes/`, method: "POST", body: { titulo } }),
      invalidatesTags: ["Estrutura", "Verificacao", "Cursos"],
    }),
    mudarSeccao: build.mutation<Seccao, { id: string; titulo: string }>({
      query: ({ id, titulo }) => ({ url: `/teacher/seccoes/${id}/`, method: "PATCH", body: { titulo } }),
      invalidatesTags: ["Estrutura"],
    }),
    apagarSeccao: build.mutation<void, string>({
      query: (id) => ({ url: `/teacher/seccoes/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Estrutura", "Verificacao", "Cursos"],
    }),
    ordenarSeccoes: build.mutation<unknown, { curso: string; ids: string[] }>({
      query: ({ curso, ids }) => ({ url: `/teacher/cursos/${curso}/seccoes/ordem/`, method: "POST", body: { ids } }),
      invalidatesTags: ["Estrutura"],
    }),
    novaAula: build.mutation<Aula, { seccao: string; titulo: string }>({
      query: ({ seccao, titulo }) => ({ url: `/teacher/seccoes/${seccao}/aulas/`, method: "POST", body: { titulo } }),
      invalidatesTags: ["Estrutura", "Verificacao", "Cursos"],
    }),
    mudarAula: build.mutation<Aula, { id: string } & Partial<Pick<Aula, "titulo" | "resumo" | "percentagem_vista" | "duracao_s">> & { seccao?: string; licao_pratica?: string | null }>({
      query: ({ id, ...body }) => ({ url: `/teacher/aulas/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Estrutura", "Verificacao"],
    }),
    licoesPratica: build.query<CursoComLicoes[], string>({
      query: (curso) => `/teacher/cursos/${curso}/licoes-pratica/`,
      transformResponse: (r: { cursos: CursoComLicoes[] }) => r?.cursos ?? [],
    }),
    apagarAula: build.mutation<void, string>({
      query: (id) => ({ url: `/teacher/aulas/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Estrutura", "Verificacao", "Cursos"],
    }),
    ordenarAulas: build.mutation<unknown, { seccao: string; ids: string[] }>({
      query: ({ seccao, ids }) => ({ url: `/teacher/seccoes/${seccao}/aulas/ordem/`, method: "POST", body: { ids } }),
      invalidatesTags: ["Estrutura"],
    }),
    apagarMaterial: build.mutation<void, string>({
      query: (id) => ({ url: `/teacher/materiais/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Estrutura"],
    }),
    questionario: build.query<Questionario, string>({
      query: (aula) => `/teacher/aulas/${aula}/questionario/`,
      providesTags: ["Questionario"],
    }),
    guardarQuestionario: build.mutation<Questionario, { aula: string } & Questionario>({
      query: ({ aula, ...body }) => ({ url: `/teacher/aulas/${aula}/questionario/`, method: "PUT", body }),
      invalidatesTags: ["Questionario", "Estrutura", "Verificacao"],
    }),
    verificacao: build.query<Verificacao, string>({
      query: (id) => `/teacher/cursos/${id}/verificacao/`,
      providesTags: ["Verificacao"],
    }),
    submeter: build.mutation<unknown, string>({
      query: (id) => ({ url: `/teacher/cursos/${id}/submeter/`, method: "POST", body: {} }),
      invalidatesTags: ["Painel", "Cursos", "Verificacao", "Curso", "Estrutura"],
    }),
    cancelarRevisao: build.mutation<unknown, string>({
      query: (id) => ({ url: `/teacher/cursos/${id}/cancelar-revisao/`, method: "POST", body: {} }),
      invalidatesTags: ["Painel", "Cursos", "Verificacao", "Curso", "Estrutura"],
    }),
    arquivar: build.mutation<unknown, { id: string; modo: "manter" | "fechar" }>({
      query: ({ id, modo }) => ({ url: `/teacher/cursos/${id}/arquivar/`, method: "POST", body: { modo } }),
      invalidatesTags: ["Painel", "Cursos", "Verificacao", "Curso", "Estrutura"],
    }),
  }),
});

export const {
  usePainelQuery,
  useCursosQuery,
  useVerificacaoQuery,
  useSubmeterMutation,
  useCancelarRevisaoMutation,
  useArquivarMutation,
  useOpcoesQuery,
  useCriarCursoMutation,
  useCursoQuery,
  useMudarCursoMutation,
  useEstruturaQuery,
  useNovaSeccaoMutation,
  useMudarSeccaoMutation,
  useApagarSeccaoMutation,
  useOrdenarSeccoesMutation,
  useNovaAulaMutation,
  useMudarAulaMutation,
  useApagarAulaMutation,
  useLicoesPraticaQuery,
  useOrdenarAulasMutation,
  useApagarMaterialMutation,
  useQuestionarioQuery,
  useGuardarQuestionarioMutation,
} = professorApi;

/** Nome do estado como o professor o lê, e a cor da etiqueta. */
export const ESTADO: Record<EstadoCurso, { nome: string; tipo: "certo" | "neutra" | "realce" | "errado" }> = {
  publicado: { nome: "Publicado", tipo: "certo" },
  em_revisao: { nome: "Em revisão", tipo: "realce" },
  rascunho: { nome: "Rascunho", tipo: "neutra" },
  arquivado: { nome: "Arquivado", tipo: "neutra" },
};

/** "Petróleo e Gás, nível B1" a partir da área e do nível. */
export function areaNivel(c: Pick<CursoProfessor, "area" | "nivel">) {
  return [c.area, nivelEmFrase(c.nivel)].filter(Boolean).join(", ");
}

export const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v)}%`);
/** "1 240": agrupa sempre os milhares (o pt-PT não agrupa números de 4 dígitos). */
export const num = (v: number | null | undefined) => (v == null ? "–" : String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"));

export { diaMesCurto } from "@/src/domains/student/subscricao/api";

/**
 * Mensagem de erro do professor. Num curso publicado, a API recusa (409 quebra_curso) o que estragaria
 * o curso e diz porquê em `details.problemas`: junta essa lista à mensagem.
 */
export function erroProfessor(e: unknown, padrao: string) {
  const d = (e as { data?: { message?: string; details?: { problemas?: string[]; itens?: { ok?: boolean; titulo?: string; detalhe?: string }[] } } })?.data;
  const base = mensagemErroBase(e, padrao);
  // Prática: details.problemas (textos); vídeo: details.itens (lista de verificação).
  const problemas = d?.details?.problemas ?? d?.details?.itens?.filter((i) => i.ok === false).map((i) => [i.titulo, i.detalhe].filter(Boolean).join(": "));
  return problemas?.length ? `${base} ${problemas.join(" ")}` : base;
}
