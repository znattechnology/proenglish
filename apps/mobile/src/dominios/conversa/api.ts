/**
 * Conversa com o tutor: preparar, sessão em curso, resumo, progresso, teste de nível falado,
 * conversas curtas (lição e aula) e exame oral do curso.
 * Igual a apps/web/src/domains/student/conversa/api.ts (+ exame em curso/api.ts e conversa da aula em curso/fala.ts).
 *
 * Modelo de confiança: a duração, os minutos do plano e as notas são sempre calculados no servidor
 * (a partir da chamada confirmada pelo serviço de voz). A app só cria e termina a sessão, manda a
 * transcrição provisória (para mostrar) e o que só pode baixar o resultado (falas escritas e frases vistas).
 */
import type { OfertaPlano } from "@/dominios/subscricao/api";
import { api } from "@/api/base";

export type Nivel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type Correcao = "suave" | "directa";
export type Frase = { en: string; pt: string };
export type Ajuste = { disse: string; certo: string; porque: string };
/** escrito: o aluno escreveu em vez de falar (as frases-alvo dessa fala contam só "com ajuda"). */
export type Fala = { quem: "tutor" | "aluno"; texto: string; escrito?: boolean };
export type Objectivo = { en: string; pt: string };
export type ObjectivoResultado = Objectivo & { usado: boolean; com_ajuda: boolean };
export type PadraoConversa = { chave: string; descricao: string; errado: string; certo: string; estado: "novo" | "recorrente" | "superado" };
export type PadraoPerfil = { chave: string; descricao: string; errado: string; certo: string; ocorrencias: number; ultima_ocorrencia: string | null; superado: boolean };
export type ModoConversa = "vapi" | "simulado";

export type Situacao = {
  id: string;
  titulo: string;
  descricao: string;
  minutos_sugeridos: number;
  area: string;
  nivel: Nivel | null;
  correcao: Correcao | null;
  curso: { id: string; titulo: string } | null;
};

export type Preparar = {
  situacoes: Situacao[];
  objectivos: Record<string, Objectivo[]>;
  perfil: { nivel: Nivel | null };
  niveis: Nivel[];
  areas: { id: string; nome: string }[];
  preferencias: { nivel: Nivel; correcao: Correcao; area: string };
  quota: {
    plano: string;
    minutos_dia: number | null;
    minutos_usados: number;
    minutos_restantes: number | null;
    max_minutos_sessao: number;
    pode_comecar: boolean;
    motivo: null | "sem_minutos" | "plano_sem_tutor" | "teste_expirado";
  };
  modo: ModoConversa;
  vapi: { public_key: string; assistant_id: string } | null;
};

export type NovaSessao = {
  id: string;
  situacao: { id: string; titulo: string };
  max_segundos: number;
  primeira_fala: string;
  frases: Frase[];
  objectivos: Objectivo[];
  vapi: { assistant_id: string; assistant_overrides: Record<string, unknown> } | null;
};

/** O que é preciso para abrir uma conversa curta (lição, aula, exame, teste de nível). */
export type ConversaAberta = { sessao: NovaSessao; modo: ModoConversa; chave_publica: string | null };

export type Notas = { geral: number | null; fluencia: number | null; gramatica: number | null; pronuncia: number | null; vocabulario: number | null };

export type Resumo = {
  id: string;
  situacao: { id: string | null; titulo: string };
  iniciada_em: string;
  minutos: number;
  minutos_cobrados: number;
  segundos: number;
  estado: "avaliada" | "sem_avaliacao" | "em_curso" | "a_avaliar" | "nao_ligou";
  notas: Notas | null;
  transcricao: Fala[];
  transcricao_provisoria?: boolean;
  correccoes: Ajuste[];
  palavras_bem_usadas: string[];
  resumo: string | null;
  objectivos: ObjectivoResultado[];
  padroes: PadraoConversa[];
  fala?: { segundos: number; ppm: number | null; palavras_por_turno: number | null; quota: number | null; fonte: "medido" | "estimado"; frase: string } | null;
};

export type Progresso = {
  media: number | null;
  variacao_mes: number | null;
  sessoes: number;
  minutos: number;
  por_competencia: { chave: string; nome: string; valor: number | null; nota: string }[];
  ultimas: { id: string; titulo: string; iniciada_em: string; minutos: number; geral: number | null }[];
  padroes: PadraoPerfil[];
  frases_sozinho: { total: number; a_recuperar?: number; recentes: { texto: string; traducao: string; vezes: number; dias: number; ultima_vez: string | null }[] };
};

export type ResultadoDiagnostico = {
  id: string;
  estado: Resumo["estado"];
  avaliado: boolean;
  nivel: Nivel | null;
  niveis: { falar: Nivel | null; ouvir: Nivel | null; gramatica: Nivel | null; vocabulario: Nivel | null } | null;
  explicacoes: Partial<Record<"falar" | "ouvir" | "gramatica" | "vocabulario", string>>;
  resumo: string | null;
  feito_em: string;
};
export type EstadoDiagnostico = {
  disponivel: boolean;
  feitos_30_dias: number;
  limite: number;
  proximo_em: string | null;
  max_segundos: number;
  ultimo: ResultadoDiagnostico | null;
  modo: ModoConversa;
};

/* Exame oral do curso (apps/web/src/domains/shared/exameOral.ts e curso/api.ts). */
export type NotasExame = { fluencia: number | null; gramatica: number | null; vocabulario: number | null; tarefa: number | null; pronuncia: number | null };
export type ExameOral = {
  id: string;
  curso: { id: string; titulo: string };
  estado: "em_curso" | "a_avaliar" | "avaliado" | "insuficiente" | "anulado";
  criado_em: string;
  avaliado_em: string | null;
  notas: NotasExame;
  nota_ia: number | null;
  nota: number | null;
  nota_minima: number;
  aprovado: boolean;
  nivel_cefr: Nivel | null;
  frases_usadas: string[];
  frases_total: number;
  relatorio: string | null;
  a_treinar: string[];
  pode_repetir_em: string | null;
  consentimento_gravacao: boolean;
  gravacao_url: string | null;
  gravacao_apagada: boolean;
  revisao: { nota: number; comentario: string; por: string | null; em: string | null } | null;
  sessao_id: string | null;
};
export type EstadoExame = {
  disponivel: boolean;
  /** plano: o plano do aluno não inclui o exame (vem com `oferta`). */
  motivo: null | "progresso" | "aprovado" | "aguardar" | "tentativas" | "curso_pratica" | "desligado" | "plano";
  mensagem: string | null;
  oferta?: OfertaPlano | null;
  progresso: number;
  limiar_progresso: number;
  duracao_minutos: number;
  nota_minima: number;
  nivel_alvo: string | null;
  area: string | null;
  temas: { titulo: string; descricao: string }[];
  frases: { en: string; pt: string }[];
  frases_total: number;
  aprovado: boolean;
  pode_repetir_em: string | null;
  em_curso: string | null;
  tentativas: ExameOral[];
};
export type ExameComecado = ConversaAberta & { exame_id: string; gravacao: boolean };

/* Frases e conversa de uma aula em vídeo (apps/web/src/domains/student/curso/fala.ts). */
export type EstadoBanco = "vista" | "reconhecida" | "com_ajuda" | "sozinho";
export type FraseDaAula = { id: number; texto: string; traducao: string; tipo: "frase" | "palavra"; inicio: number | null; fim: number | null; estado: EstadoBanco | null };
export type FalaDaAula = {
  frases: FraseDaAula[];
  conversa: { disponivel: boolean; motivo: string | null; mensagem: string | null; max_segundos: number };
};

const BASE = "/practice/conversa";
const CURSOS = "/student/video-courses";
const PRATICA = "/student/practice-courses";

// Etiquetas de outros domínios (cursos, início): a conversa e o exame contam para a nota do curso e para o início.
const DEPOIS_DE_ESTUDAR = ["Estatisticas", "Liga", "Conquistas", "Certificados", "InicioResumo", "NotasCurso", "ProgressoCurso", "Curso", "Exame", "ExameOral"];

export const conversaApi = api.enhanceEndpoints({ addTagTypes: ["ConversaPreparar", "ConversaProgresso", "ExameOral", "FalaMeta"] }).injectEndpoints({
  endpoints: (build) => ({
    conversaPreparar: build.query<Preparar, void>({
      query: () => `${BASE}/preparar/`,
      providesTags: ["ConversaPreparar"],
      keepUnusedDataFor: 0,
    }),
    conversaComecar: build.mutation<NovaSessao, { situacao: string; nivel: Nivel; correcao: Correcao; area: string }>({
      query: (body) => ({ url: `${BASE}/sessoes/`, method: "POST", body }),
    }),
    /** A chamada ligou de facto: o tempo cobrado começa aqui (não ao criar a sessão). */
    conversaLigada: build.mutation<unknown, { id: string; call_id?: string }>({
      query: ({ id, call_id }) => ({ url: `${BASE}/sessoes/${id}/ligada/`, method: "POST", body: call_id ? { call_id } : {} }),
    }),
    conversaResponder: build.mutation<{ tutor: string }, { id: string; texto: string; escrito?: boolean }>({
      query: ({ id, texto, escrito }) => ({ url: `${BASE}/sessoes/${id}/responder/`, method: "POST", body: { texto, escrito: Boolean(escrito) } }),
    }),
    /** Só baixa o resultado: o aluno escreveu em vez de falar, ou viu a frase-alvo em inglês. */
    conversaAjuda: build.mutation<{ ok: boolean }, { id: string; escrito?: string; revelada?: string }>({
      query: ({ id, ...body }) => ({ url: `${BASE}/sessoes/${id}/ajuda/`, method: "POST", body }),
    }),
    conversaAjuste: build.mutation<{ ajuste: Ajuste | null }, { id: string; frase: string }>({
      query: ({ id, frase }) => ({ url: `${BASE}/sessoes/${id}/ajuste/`, method: "POST", body: { frase } }),
    }),
    conversaTerminar: build.mutation<Resumo, { id: string; transcricao: Fala[]; call_id?: string | null; reveladas?: string[] }>({
      query: ({ id, ...body }) => ({ url: `${BASE}/sessoes/${id}/terminar/`, method: "POST", body }),
      invalidatesTags: ["ConversaPreparar", "ConversaProgresso", "FalaMeta"],
      async onQueryStarted(_a, { dispatch, queryFulfilled }) {
        try {
          await queryFulfilled;
          dispatch(api.util.invalidateTags(DEPOIS_DE_ESTUDAR as never));
        } catch {
          /* o ecrã trata o erro */
        }
      },
    }),
    conversaResumo: build.query<Resumo, string>({
      query: (id) => `${BASE}/sessoes/${id}/`,
      providesTags: ["ConversaProgresso"],
    }),
    conversaProgresso: build.query<Progresso, void>({
      query: () => `${BASE}/progresso/`,
      providesTags: ["ConversaProgresso"],
    }),

    // Teste de nível falado.
    conversaDiagnostico: build.query<EstadoDiagnostico, void>({
      query: () => `${BASE}/diagnostico/`,
      keepUnusedDataFor: 0,
    }),
    conversaComecarDiagnostico: build.mutation<{ sessao: NovaSessao; modo: ModoConversa; chave_publica: string | null }, void>({
      query: () => ({ url: `${BASE}/diagnostico/comecar/`, method: "POST", body: {} }),
    }),
    conversaResultadoDiagnostico: build.query<ResultadoDiagnostico, string>({
      query: (id) => `${BASE}/diagnostico/${id}/`,
      keepUnusedDataFor: 0,
    }),

    // Conversas curtas: no fim de uma lição do laboratório e depois de uma aula em vídeo.
    conversaComecarLicao: build.mutation<ConversaAberta, string>({
      query: (challengeId) => ({ url: `${PRATICA}/challenges/${challengeId}/conversa/`, method: "POST", body: {} }),
    }),
    conversaFalaDaAula: build.query<FalaDaAula, string>({
      query: (chapterId) => `${CURSOS}/chapters/${chapterId}/fala/`,
    }),
    conversaComecarAula: build.mutation<ConversaAberta, string>({
      query: (chapterId) => ({ url: `${CURSOS}/chapters/${chapterId}/conversa/`, method: "POST", body: {} }),
    }),

    // Exame oral do curso.
    exameOralEstado: build.query<EstadoExame, string>({
      query: (courseId) => `${CURSOS}/${courseId}/exame/`,
      providesTags: (_r, _e, id) => [{ type: "ExameOral", id }],
    }),
    exameOralComecar: build.mutation<ExameComecado, { courseId: string; consentimento: boolean }>({
      query: ({ courseId, consentimento }) => ({ url: `${CURSOS}/${courseId}/exame/`, method: "POST", body: { consentimento } }),
    }),
    exameOralResultado: build.query<ExameOral, string>({
      query: (id) => `${CURSOS}/exames/${id}/`,
      keepUnusedDataFor: 0,
    }),
    exameOralApagarGravacao: build.mutation<ExameOral, { id: string; courseId: string }>({
      query: ({ id }) => ({ url: `${CURSOS}/exames/${id}/gravacao/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, a) => [{ type: "ExameOral", id: a.courseId }],
    }),
  }),
});

export const {
  useConversaPrepararQuery,
  useConversaComecarMutation,
  useConversaLigadaMutation,
  useConversaResponderMutation,
  useConversaAjudaMutation,
  useConversaAjusteMutation,
  useConversaTerminarMutation,
  useConversaResumoQuery,
  useConversaProgressoQuery,
  useConversaDiagnosticoQuery,
  useConversaComecarDiagnosticoMutation,
  useLazyConversaResultadoDiagnosticoQuery,
  useConversaComecarLicaoMutation,
  useConversaFalaDaAulaQuery,
  useConversaComecarAulaMutation,
  useExameOralEstadoQuery,
  useExameOralComecarMutation,
  useLazyExameOralResultadoQuery,
  useExameOralApagarGravacaoMutation,
} = conversaApi;

/** Caminho do "terminar" para o envio de último recurso (ao sair do ecrã a meio da conversa). */
export const caminhoTerminar = (id: string) => `${BASE}/sessoes/${id}/terminar/`;

/** Mensagem do erro da API (`{codigo, mensagem}`), ou uma mensagem por omissão. */
export function erroConversa(e: unknown, padrao = "Não foi possível começar a conversa. Tente outra vez.") {
  const x = e as { status?: number | string; data?: { mensagem?: string; error?: string; detail?: string } } | undefined;
  if (x?.status === "FETCH_ERROR") return "Sem ligação ao servidor. Verifique a Internet e tente outra vez.";
  const d = x?.data;
  return d?.mensagem ?? (typeof d?.error === "string" ? d.error : undefined) ?? d?.detail ?? padrao;
}

/** A fala contém a frase? (aproximado, só para o painel ao vivo: quem decide é o servidor no fim). */
export function disseFrase(frase: string, fala: string) {
  const norm = (t: string) =>
    t
      .toLowerCase()
      .replace(/[‘’`]/g, "'")
      .replace(/\bcan't\b/g, "can not")
      .replace(/\bwon't\b/g, "will not")
      .replace(/n't\b/g, " not")
      .replace(/'ll\b/g, " will")
      .replace(/'re\b/g, " are")
      .replace(/'m\b/g, " am")
      .replace(/'ve\b/g, " have")
      .replace(/'d\b/g, " would")
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter(Boolean);
  const a = norm(frase);
  const b = norm(fala);
  if (!a.length || !b.length) return false;
  let ant: number[] = new Array(b.length + 1).fill(0);
  for (const x of a) {
    const act = [0];
    for (let j = 1; j <= b.length; j++) act.push(x === b[j - 1] ? ant[j - 1] + 1 : Math.max(ant[j], act[j - 1]));
    ant = act;
  }
  return ant[b.length] / a.length >= 0.8;
}

export const NIVEIS: Nivel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

export const NIVEIS_DESCRICAO: Record<Nivel, string> = {
  A1: "o tutor usa frases curtas e fala muito devagar.",
  A2: "o tutor fala devagar, com frases simples do trabalho.",
  B1: "o tutor fala devagar e usa frases do dia a dia de trabalho.",
  B2: "o tutor fala a um ritmo normal e pede mais detalhes.",
  C1: "o tutor fala como um colega e usa expressões idiomáticas.",
  C2: "o tutor fala ao ritmo de um falante nativo.",
};

export const NOME_NIVEL: Record<Nivel, string> = {
  A1: "Iniciante",
  A2: "Elementar",
  B1: "Intermédio",
  B2: "Intermédio avançado",
  C1: "Avançado",
  C2: "Proficiente",
};

export const DESCRICAO_NIVEL: Record<Nivel, string> = {
  A1: "Conheço palavras e frases muito simples",
  A2: "Consigo falar de rotinas e tarefas simples",
  B1: "Consigo conversar sobre o trabalho com algum apoio",
  B2: "Participo em reuniões e discussões com à-vontade",
  C1: "Exprimo-me com fluência e precisão em contexto profissional",
  C2: "Uso o inglês como um falante nativo",
};

export const eNivel = (v: unknown): v is Nivel => typeof v === "string" && (NIVEIS as string[]).includes(v);

export const COMPETENCIAS: Record<string, string> = {
  geral: "Geral",
  fluencia: "Fluência",
  gramatica: "Gramática",
  pronuncia: "Pronúncia",
  vocabulario: "Vocabulário",
};

export const COMPETENCIAS_EXAME: { chave: keyof NotasExame; nome: string; ajuda: string }[] = [
  { chave: "fluencia", nome: "Fluência", ajuda: "Falar sem parar muito e manter a conversa" },
  { chave: "gramatica", nome: "Gramática", ajuda: "Frases correctas para o nível do curso" },
  { chave: "vocabulario", nome: "Vocabulário", ajuda: "Palavras do trabalho e do curso" },
  { chave: "tarefa", nome: "Tarefas", ajuda: "Fazer o que cada tarefa pedia" },
  { chave: "pronuncia", nome: "Pronúncia", ajuda: "Clareza dos sons" },
];

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** "21 de novembro". */
export const dataLonga = (iso: string) => {
  const d = new Date(iso);
  return `${d.getDate()} de ${MESES[d.getMonth()]}`;
};
/** "21 nov". */
export const diaMesCurto = (d: Date) => `${d.getDate()} ${MESES_CURTOS[d.getMonth()]}`;
const hora = (d: Date) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

/** "Hoje às 14:30", "Ontem às 09:05", "3 de novembro às 18:00". */
export function quandoFoi(iso: string) {
  const d = new Date(iso);
  const hoje = new Date();
  const ontem = new Date(Date.now() - 86_400_000);
  if (d.toDateString() === hoje.toDateString()) return `Hoje às ${hora(d)}`;
  if (d.toDateString() === ontem.toDateString()) return `Ontem às ${hora(d)}`;
  return `${dataLonga(iso)} às ${hora(d)}`;
}

/** Dia e hora na hora de Luanda (UTC+1, sem hora de Verão): "21 de novembro às 14:30 (hora de Luanda)". */
export function dataHoraLuanda(iso: string) {
  const d = new Date(new Date(iso).getTime() + 60 * 60_000);
  const hh = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  return `${d.getUTCDate()} de ${MESES[d.getUTCMonth()]} às ${hh} (hora de Luanda)`;
}

/** "45 min", "1 h 48". */
export function duracao(minutos: number) {
  const m = Math.round(minutos);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${String(r).padStart(2, "0")}` : `${h} h`;
}

export const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.max(0, s) % 60).padStart(2, "0")}`;
