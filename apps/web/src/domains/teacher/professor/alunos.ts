/** Alunos e resultados do professor: só os alunos dos seus cursos, sem emails nem telefones. */
import { tokenRefreshCoordinator } from "@/lib/token-refresh-coordinator";
import type { ExameOral } from "@/src/domains/shared/exameOral";
import type { NivelCefr } from "@/src/domains/shared/niveis";
import { diaMesCurto, professorApi, type TipoCurso } from "./api";

export type EstadoAluno = "activo" | "pouco_activo" | "em_risco" | "novo";
export type LinhaAluno = {
  id: string;
  nome: string;
  iniciais: string;
  curso: { id: string; titulo: string; tipo: TipoCurso };
  outros_cursos: number;
  progresso: number;
  acerto: number | null;
  ultima_actividade: string | null;
  estado: EstadoAluno;
};
export type ListaAlunos = {
  numeros: { alunos: number; cursos: number; activos_7d: number; pct_activos: number; em_risco: number; acerto_medio: number | null };
  total: number;
  paginas: number;
  resultados: LinhaAluno[];
};
export type FiltroAlunos = { filtro: "todos" | "activos" | "em_risco"; curso?: string; q?: string; pagina: number };

export type DetalheAluno = {
  aluno: { id: string; nome: string; iniciais: string; profissao: string | null; cidade: string | null; inscrito_em: string | null; plano: string };
  numeros: {
    dias_seguidos: number;
    pratica_de: "manhã" | "tarde" | "noite" | null;
    pontos: number;
    liga: { nome: string; posicao: number } | null;
    acerto: number | null;
    acerto_variacao_30d: number | null;
    conversa_min: number;
    conversas: number;
  };
  cursos: { id: string; titulo: string; tipo: TipoCurso; progresso: number; nota: number | null; abaixo_minimo: boolean }[];
  onde_erra: { tema: string; onde: string; erros: number }[];
};

export type Resultados = {
  periodo: number;
  conclusao_por_curso: { id: string; titulo: string; tipo: TipoCurso; conclusao: number | null; alunos: number }[];
  faixas: { nome: string; alunos: number }[];
  perguntas_dificeis: { challenge_id: string; licao_id?: string; unidade_id?: string; frase: string; tipo: string; curso_id: string; curso: string; onde: string; acerto: number; respostas: number }[];
};

/** Fase 6: perfil de fala do aluno e exames orais nos cursos do professor. */
export type ExameDoAluno = ExameOral & { aluno: { id: string; nome: string } };
export type FalaDoAluno = {
  perfil: {
    niveis: Record<"falar" | "ouvir" | "vocabulario" | "gramatica", NivelCefr | null>;
    conversas_avaliadas: number;
    padroes: { chave: string; descricao: string; errado: string; certo: string; ocorrencias: number }[];
    frases_sozinho: number;
    frases_sozinho_cursos: number;
  };
  /** Fase 3: minutos a falar por semana (8), palavras por minuto e palavras a treinar. */
  fala?: {
    semanas: { inicio: string; segundos: number; ppm: number | null; actual: boolean }[];
    palavras_treinar: { palavra: string; tentativas: number; falhas: number; media: number | null; fonema: string | null }[];
    meta_min: number;
  } | null;
  exames: ExameDoAluno[];
};
export type RevisaoExame = { id: string; alunoId: string } & ({ confirmar: true } | { nota: number; comentario: string });

const alunosApi = professorApi.enhanceEndpoints({ addTagTypes: ["FalaAluno"] }).injectEndpoints({
  endpoints: (build) => ({
    alunos: build.query<ListaAlunos, FiltroAlunos>({
      query: ({ filtro, curso, q, pagina }) => ({ url: "/teacher/alunos/", params: { filtro, pagina, ...(curso ? { curso } : {}), ...(q ? { q } : {}) } }),
    }),
    aluno: build.query<DetalheAluno, string>({ query: (id) => `/teacher/alunos/${id}/` }),
    falaAluno: build.query<FalaDoAluno, string>({
      query: (id) => `/teacher/alunos/${id}/fala/`,
      providesTags: (_r, _e, id) => [{ type: "FalaAluno", id }],
    }),
    reverExame: build.mutation<ExameDoAluno, RevisaoExame>({
      query: (a) => ({ url: `/teacher/exames/${a.id}/rever/`, method: "POST", body: "confirmar" in a ? { confirmar: true } : { nota: a.nota, comentario: a.comentario } }),
      invalidatesTags: (_r, _e, a) => [{ type: "FalaAluno", id: a.alunoId }],
    }),
    resultados: build.query<Resultados, number>({ query: (periodo) => ({ url: "/teacher/resultados/", params: { periodo } }) }),
  }),
});

export const { useAlunosQuery, useAlunoQuery, useResultadosQuery, useFalaAlunoQuery, useReverExameMutation } = alunosApi;

const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";

/** Descarrega um CSV da API com a sessão (cookie) e entrega-o ao browser. */
export async function descarregarCsv(caminho: string, nome: string) {
  let r = await fetch(`${API}${caminho}`, { credentials: "include" });
  if (r.status === 401) {
    // A sessão expirou: renova (como as outras chamadas) e tenta outra vez.
    await tokenRefreshCoordinator.refreshToken().catch(() => {});
    r = await fetch(`${API}${caminho}`, { credentials: "include" });
  }
  if (!r.ok) throw new Error("Não foi possível exportar.");
  // Usa o nome que o servidor sugere (ex.: com a data), se vier.
  const sugerido = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(r.headers.get("Content-Disposition") ?? "")?.[1];
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: sugerido ? decodeURIComponent(sugerido) : nome });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "Hoje", "Ontem", "Há 12 dias", "3 Set". */
export function haQuanto(iso: string | null, agora = Date.now()) {
  if (!iso) return "Nunca";
  const d = new Date(iso);
  const dias = Math.floor((new Date(agora).setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);
  if (dias <= 0) return "Hoje";
  if (dias === 1) return "Ontem";
  if (dias < 60) return `Há ${dias} dias`;
  return diaMesCurto(d);
}
