/** Administração do conteúdo do site público: rascunho, publicação e manutenção. */
import { administracaoApi } from "./api";
import { DJANGO_BASE_URL } from "@/src/domains/shared/api/baseQuery";
import { tokenRefreshCoordinator } from "@/lib/token-refresh-coordinator";

export type Seccao = "topo" | "numeros" | "empresas" | "servicos" | "precos" | "perguntas" | "definicoes";
export type Botao = { texto: string; href: string };
export type Topo = {
  etiqueta: string | null;
  titulo: string;
  texto: string;
  botao_principal: Botao;
  botao_secundario: Botao | null;
  mostrar_nota: boolean;
  nota_prevista: { media: number; total: number } | null;
};
export type Fonte = "manual" | "utilizadores" | "alunos_activos_semana" | "areas" | "cursos";
export type Onde = "topo" | "sobre" | "rodape";
export type NumeroSite = { id: number; valor: string; texto: string; onde: Onde; fonte: Fonte; mostrar: boolean; ordem: number; valor_mostrado: string };
export type Empresa = { id: number; nome: string; area: string; logo_url: string | null; no_topo: boolean; na_faixa: boolean; ordem: number };
export type Icone = "bot" | "microfone" | "balao" | "livro" | "certificado" | "laboratorio";
export type Servico = { id: number; titulo: string; texto: string; icone: Icone; leva_a: string | null; ordem: number };
export type Pergunta = { id: number; pergunta: string; resposta: string; ordem: number };
export type PlanoSite = {
  id: string;
  tipo: "FREE" | "PREMIUM" | "PREMIUM_PLUS";
  nome: string;
  preco_mensal_kz: number;
  preco_anual_kz: number | null;
  dias_teste: number;
  destaque: boolean;
  subtitulo: string;
  etiqueta: string | null;
  botao: string;
  nota_angola: string | null;
  caracteristicas: string[];
};
export type Definicoes = {
  titulo: string;
  descricao: string;
  palavras_chave: string;
  ga_id: string | null;
  pixel_id: string | null;
  email: string | null;
  telefone: string | null;
  instagram: string | null;
  linkedin: string | null;
  facebook: string | null;
};
export type Manutencao = { activa: boolean; mensagem: string; volta_em: string | null };
export type EstadoSite = {
  rascunho: { topo: Topo; numeros: NumeroSite[]; empresas: Empresa[]; servicos: Servico[]; precos: { mostrar_anual: boolean; planos: PlanoSite[] }; perguntas: Pergunta[]; definicoes: Definicoes };
  publicado_em: string | null;
  alterado_em: Record<Seccao, string | null>;
  ha_alteracoes: boolean;
  manutencao: Manutencao;
  contagens: { numeros: number; empresas: number; servicos: number; perguntas: number; testemunhos_no_site: number };
};

export type Lista = "numeros" | "empresas" | "servicos" | "perguntas";
type ItemDe<L extends Lista> = L extends "numeros" ? NumeroSite : L extends "empresas" ? Empresa : L extends "servicos" ? Servico : Pergunta;

const B = "/admin/site";

const api = administracaoApi.enhanceEndpoints({ addTagTypes: ["Site"] }).injectEndpoints({
  endpoints: (build) => ({
    estadoSite: build.query<EstadoSite, void>({ query: () => `${B}/`, providesTags: ["Site"] }),
    mudarTopo: build.mutation<EstadoSite, Partial<Omit<Topo, "nota_prevista">>>({ query: (body) => ({ url: `${B}/topo/`, method: "PATCH", body }), invalidatesTags: ["Site"] }),
    mudarPrecos: build.mutation<EstadoSite, { mostrar_anual?: boolean; planos?: Partial<PlanoSite>[] }>({ query: (body) => ({ url: `${B}/precos/`, method: "PATCH", body }), invalidatesTags: ["Site"] }),
    mudarDefinicoes: build.mutation<EstadoSite, Partial<Definicoes>>({ query: (body) => ({ url: `${B}/definicoes/`, method: "PATCH", body }), invalidatesTags: ["Site"] }),
    criarItem: build.mutation<unknown, { lista: Lista; dados: Record<string, unknown> }>({ query: ({ lista, dados }) => ({ url: `${B}/${lista}/`, method: "POST", body: dados }), invalidatesTags: ["Site"] }),
    mudarItem: build.mutation<unknown, { lista: Lista; id: number; dados: Record<string, unknown> }>({ query: ({ lista, id, dados }) => ({ url: `${B}/${lista}/${id}/`, method: "PATCH", body: dados }), invalidatesTags: ["Site"] }),
    apagarItem: build.mutation<unknown, { lista: Lista; id: number }>({ query: ({ lista, id }) => ({ url: `${B}/${lista}/${id}/`, method: "DELETE" }), invalidatesTags: ["Site"] }),
    ordenar: build.mutation<unknown, { lista: Lista; ids: number[] }>({ query: ({ lista, ids }) => ({ url: `${B}/${lista}/ordem/`, method: "POST", body: { ids } }), invalidatesTags: ["Site"] }),
    enviarLogo: build.mutation<Empresa, { id: number; ficheiro: File }>({
      // fetch próprio: a base força JSON e o logótipo vai em multipart.
      queryFn: async ({ id, ficheiro }) => {
        const enviar = () => {
          const corpo = new FormData();
          corpo.append("logo", ficheiro);
          return fetch(`${DJANGO_BASE_URL}${B}/empresas/${id}/logo/`, { method: "POST", body: corpo, credentials: "include" });
        };
        try {
          let r = await enviar();
          if (r.status === 401) {
            // Sessão expirada: renovar e tentar uma vez, como os outros pedidos (sharedBaseQuery).
            try {
              await tokenRefreshCoordinator.refreshToken();
            } catch {
              tokenRefreshCoordinator.clearTokens();
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- recarregar a página toda limpa o estado da sessão
              window.location.href = "/signin?reason=session_expired";
              return { error: { status: 401, data: { message: "Session expired" } } };
            }
            r = await enviar();
          }
          const dados = await r.json().catch(() => ({}));
          return r.ok ? { data: dados as Empresa } : { error: { status: r.status, data: dados } };
        } catch (e) {
          return { error: { status: "FETCH_ERROR", error: String(e) } };
        }
      },
      invalidatesTags: ["Site"],
    }),
    tirarLogo: build.mutation<unknown, number>({ query: (id) => ({ url: `${B}/empresas/${id}/logo/`, method: "DELETE" }), invalidatesTags: ["Site"] }),
    publicar: build.mutation<EstadoSite, void>({ query: () => ({ url: `${B}/publicar/`, method: "POST", body: {} }), invalidatesTags: ["Site"] }),
    descartar: build.mutation<EstadoSite, void>({ query: () => ({ url: `${B}/descartar/`, method: "POST", body: {} }), invalidatesTags: ["Site"] }),
    mudarManutencao: build.mutation<EstadoSite, { activa: boolean; mensagem?: string; volta_em?: string | null }>({ query: (body) => ({ url: `${B}/manutencao/`, method: "POST", body }), invalidatesTags: ["Site"] }),
  }),
});

export const {
  useEstadoSiteQuery,
  useMudarTopoMutation,
  useMudarPrecosMutation,
  useMudarDefinicoesMutation,
  useCriarItemMutation,
  useMudarItemMutation,
  useApagarItemMutation,
  useOrdenarMutation,
  useEnviarLogoMutation,
  useTirarLogoMutation,
  usePublicarMutation,
  useDescartarMutation,
  useMudarManutencaoMutation,
} = api;
export type { ItemDe };

export const SECCOES_SITE: { chave: Seccao; nome: string; href: string }[] = [
  { chave: "topo", nome: "Topo da página", href: "/admin/site/topo" },
  { chave: "numeros", nome: "Números", href: "/admin/site/numeros" },
  { chave: "empresas", nome: "Empresas", href: "/admin/site/empresas" },
  { chave: "servicos", nome: "O que oferecemos", href: "/admin/site/servicos" },
  { chave: "precos", nome: "Planos e preços", href: "/admin/site/precos" },
  { chave: "perguntas", nome: "Perguntas frequentes", href: "/admin/site/perguntas" },
  { chave: "definicoes", nome: "Definições e SEO", href: "/admin/site/definicoes" },
];

export const FONTES: Record<Fonte, string> = {
  manual: "Escrito à mão",
  utilizadores: "Alunos registados (automático)",
  alunos_activos_semana: "Alunos activos nos últimos 7 dias (automático)",
  areas: "Áreas profissionais com cursos (automático)",
  cursos: "Cursos publicados (automático)",
};
export const ONDE: Record<Onde, string> = { topo: "Topo", sobre: "Página Sobre", rodape: "Rodapé" };
export const ICONES: Record<Icone, string> = { livro: "Livro", laboratorio: "Laboratório", bot: "Robô", microfone: "Microfone", balao: "Balão de conversa", certificado: "Certificado" };
