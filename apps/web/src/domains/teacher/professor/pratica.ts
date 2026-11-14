/** Cursos de prática do professor: unidades, lições, exercícios e a geração de lições com IA. */
import { professorApi, type DetalheCurso } from "./api";

export type TipoExercicio = "escolher" | "assistir" | "completar" | "traduzir" | "ordenar" | "pares" | "verdadeiro_falso" | "escuta" | "pronuncia" | "conversa";

export type Exercicio = {
  id?: string;
  tipo: TipoExercicio;
  ordem?: number;
  enunciado: string;
  frase: string;
  opcoes: { id?: string; texto: string; certa: boolean }[];
  pares: { a: string; b: string }[];
  resposta: string;
  explicacao: string;
  audio_url: string | null;
  acerto?: number | null;
  tentativas?: number;
};

export type LicaoPratica = { id: string; titulo: string; ordem: number; exercicios: number; tipos: string[]; acerto: number | null; tentativas: number };
export type UnidadePratica = { id: string; titulo: string; descricao: string; ordem: number; licoes: LicaoPratica[] };
export type EstruturaPratica = { curso: DetalheCurso; unidades: UnidadePratica[] };
export type LicaoComExercicios = { licao: { id: string; titulo: string; unidade: { id: string; titulo: string; ordem: number } }; curso: { id: string; titulo: string }; exercicios: Exercicio[] };
export type LicaoGerada = { titulo_sugerido: string; exercicios: Exercicio[]; descartados: number };

const P = "/teacher/pratica";

export const praticaApi = professorApi.enhanceEndpoints({ addTagTypes: ["Pratica", "Exercicios"] }).injectEndpoints({
  endpoints: (build) => ({
    estruturaPratica: build.query<EstruturaPratica, string>({ query: (c) => `${P}/${c}/estrutura/`, providesTags: ["Pratica"] }),
    novaUnidade: build.mutation<UnidadePratica, { curso: string; titulo: string }>({
      query: ({ curso, titulo }) => ({ url: `${P}/${curso}/unidades/`, method: "POST", body: { titulo } }),
      invalidatesTags: ["Pratica", "Verificacao", "Cursos"],
    }),
    mudarUnidade: build.mutation<UnidadePratica, { id: string; titulo: string }>({
      query: ({ id, titulo }) => ({ url: `${P}/unidades/${id}/`, method: "PATCH", body: { titulo } }),
      invalidatesTags: ["Pratica"],
    }),
    apagarUnidade: build.mutation<void, string>({
      query: (id) => ({ url: `${P}/unidades/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Pratica", "Verificacao", "Cursos"],
    }),
    ordenarUnidades: build.mutation<unknown, { curso: string; ids: string[] }>({
      query: ({ curso, ids }) => ({ url: `${P}/${curso}/unidades/ordem/`, method: "POST", body: { ids } }),
      invalidatesTags: ["Pratica"],
    }),
    novaLicao: build.mutation<LicaoPratica, { unidade: string; titulo: string }>({
      query: ({ unidade, titulo }) => ({ url: `${P}/unidades/${unidade}/licoes/`, method: "POST", body: { titulo } }),
      invalidatesTags: ["Pratica", "Verificacao", "Cursos"],
    }),
    mudarLicao: build.mutation<LicaoPratica, { id: string; titulo?: string; unidade?: string }>({
      query: ({ id, ...body }) => ({ url: `${P}/licoes/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Pratica", "Exercicios"],
    }),
    apagarLicao: build.mutation<void, string>({
      query: (id) => ({ url: `${P}/licoes/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Pratica", "Verificacao", "Cursos"],
    }),
    ordenarLicoes: build.mutation<unknown, { unidade: string; ids: string[] }>({
      query: ({ unidade, ids }) => ({ url: `${P}/unidades/${unidade}/licoes/ordem/`, method: "POST", body: { ids } }),
      invalidatesTags: ["Pratica"],
    }),
    exercicios: build.query<LicaoComExercicios, string>({ query: (l) => `${P}/licoes/${l}/exercicios/`, providesTags: ["Exercicios"] }),
    novoExercicio: build.mutation<Exercicio, { licao: string; e: Exercicio }>({
      query: ({ licao, e }) => ({ url: `${P}/licoes/${licao}/exercicios/`, method: "POST", body: e }),
      invalidatesTags: ["Exercicios", "Pratica", "Verificacao"],
    }),
    guardarExercicio: build.mutation<Exercicio, Exercicio & { id: string }>({
      query: (e) => ({ url: `${P}/exercicios/${e.id}/`, method: "PUT", body: e }),
      invalidatesTags: ["Exercicios", "Pratica", "Verificacao"],
    }),
    apagarExercicio: build.mutation<void, string>({
      query: (id) => ({ url: `${P}/exercicios/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Exercicios", "Pratica", "Verificacao"],
    }),
    ordenarExercicios: build.mutation<unknown, { licao: string; ids: string[] }>({
      query: ({ licao, ids }) => ({ url: `${P}/licoes/${licao}/exercicios/ordem/`, method: "POST", body: { ids } }),
      invalidatesTags: ["Exercicios"],
    }),
    gerarAudio: build.mutation<Exercicio, string>({
      query: (id) => ({ url: `${P}/exercicios/${id}/audio/`, method: "POST", body: {} }),
      invalidatesTags: ["Exercicios"],
    }),
    gerarLicao: build.mutation<LicaoGerada, { curso: string; unidade: string; objectivo: string; palavras: string[]; quantos: number }>({
      query: ({ curso, ...body }) => ({ url: `${P}/${curso}/gerar-licao/`, method: "POST", body }),
    }),
    guardarLicaoGerada: build.mutation<{ licao: LicaoPratica; exercicios: Exercicio[] }, { unidade: string; titulo: string; exercicios: Exercicio[] }>({
      query: ({ unidade, ...body }) => ({ url: `${P}/unidades/${unidade}/licoes/com-exercicios/`, method: "POST", body }),
      invalidatesTags: ["Pratica", "Verificacao", "Cursos"],
    }),
  }),
});

export const {
  useEstruturaPraticaQuery,
  useNovaUnidadeMutation,
  useMudarUnidadeMutation,
  useApagarUnidadeMutation,
  useOrdenarUnidadesMutation,
  useNovaLicaoMutation,
  useMudarLicaoMutation,
  useApagarLicaoMutation,
  useOrdenarLicoesMutation,
  useExerciciosQuery,
  useNovoExercicioMutation,
  useGuardarExercicioMutation,
  useApagarExercicioMutation,
  useOrdenarExerciciosMutation,
  useGerarAudioMutation,
  useGerarLicaoMutation,
  useGuardarLicaoGeradaMutation,
} = praticaApi;

export const TIPOS: { valor: TipoExercicio; nome: string; texto: string }[] = [
  { valor: "escolher", nome: "Escolher", texto: "Uma pergunta e várias respostas, uma certa." },
  { valor: "completar", nome: "Completar", texto: "Uma frase com uma palavra em falta, para escolher ou escrever." },
  { valor: "traduzir", nome: "Traduzir", texto: "O aluno escreve em inglês uma frase em português." },
  { valor: "ordenar", nome: "Ordenar", texto: "O aluno põe as palavras de uma frase pela ordem certa." },
  { valor: "pares", nome: "Pares", texto: "Ligar palavras às suas traduções." },
  { valor: "verdadeiro_falso", nome: "Verdadeiro ou falso", texto: "Uma afirmação para o aluno dizer se é certa." },
  { valor: "escuta", nome: "Escuta", texto: "O aluno ouve uma frase e responde ou escreve o que ouviu." },
  { valor: "pronuncia", nome: "Pronúncia", texto: "O aluno diz uma frase em voz alta." },
];
// "Conversa com o tutor" dentro das lições fica de fora até estar ligada ao tutor: os alunos saltam os que existirem.
export const nomeTipo = (t: string) => TIPOS.find((x) => x.valor === t)?.nome ?? (t === "assistir" ? "Escolher com imagem" : t === "conversa" ? "Conversa (desligada)" : t);

export const exercicioVazio = (tipo: TipoExercicio): Exercicio => ({
  tipo,
  enunciado: "",
  frase: "",
  opcoes: tipo === "escolher" || tipo === "assistir" ? [{ texto: "", certa: true }, { texto: "", certa: false }, { texto: "", certa: false }] : [],
  pares: tipo === "pares" ? [{ a: "", b: "" }, { a: "", b: "" }, { a: "", b: "" }] : [],
  resposta: tipo === "verdadeiro_falso" ? "verdadeiro" : "",
  explicacao: "",
  audio_url: null,
});

/** Uma linha curta para listas: o que o aluno vê primeiro. */
export function resumoExercicio(e: Exercicio) {
  switch (e.tipo) {
    case "completar":
    case "pronuncia":
    case "escuta":
      return e.frase || e.enunciado;
    case "ordenar":
      return e.resposta || e.enunciado;
    case "pares":
      return e.pares.map((p) => p.a).filter(Boolean).join(", ");
    case "escolher":
    case "assistir": {
      const ops = e.opcoes.map((o) => o.texto).filter(Boolean).join(" / ");
      return ops ? `${e.enunciado} → ${ops}` : e.enunciado;
    }
    default:
      return e.enunciado || e.frase;
  }
}

/** Palavras entre parênteses rectos numa frase de completar. */
export const palavrasEntreParenteses = (frase: string) => Array.from(frase.matchAll(/\[([^\]]+)\]/g), (m) => m[1].trim()).filter(Boolean);

/** "Unidade 3: Reuniões de segurança", sem repetir quando o título já é "Unidade 3". */
export const nomeUnidade = (n: number, titulo: string) => (titulo.trim().toLowerCase() === `unidade ${n}` ? `Unidade ${n}` : `Unidade ${n}: ${titulo}`);
