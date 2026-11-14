/**
 * Conteúdo publicado do site (GET /api/v1/site/), lido no servidor e guardado 1 minuto.
 * Se a API falhar, a página usa os textos por defeito abaixo (verdadeiros e sem números inventados).
 */
export type Site = {
  topo: {
    etiqueta: string | null;
    titulo: string;
    texto: string;
    botao_principal: { texto: string; href: string };
    botao_secundario: { texto: string; href: string } | null;
    mostrar_nota: boolean;
    nota: { media: number; total: number } | null;
  };
  numeros: { id: string; valor: string; texto: string; onde: "topo" | "sobre" | "rodape" }[];
  empresas: { id: string; nome: string; area: string; logo_url: string | null; no_topo: boolean; na_faixa: boolean }[];
  servicos: { id: string; titulo: string; texto: string; icone: string; leva_a: string | null }[];
  areas: { valor: string; nome: string; cursos: number }[];
  precos: {
    mostrar_anual: boolean;
    planos: {
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
    }[];
  };
  testemunhos: { id: string; nome: string; area: string | null; texto: string; nota: number }[];
  perguntas: { id: string; pergunta: string; resposta: string }[];
  definicoes: {
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
  manutencao: { activa: boolean; mensagem: string; volta_em: string | null };
  publicado_em: string | null;
};

export const SITE_POR_DEFEITO: Site = {
  topo: {
    etiqueta: null,
    titulo: "Fale inglês no seu trabalho",
    texto: "Cursos por área profissional, 15 minutos de prática por dia e conversa com um tutor de inteligência artificial. Feito para quem trabalha e estuda em Angola.",
    botao_principal: { texto: "Experimentar grátis", href: "/signup" },
    botao_secundario: { texto: "Ver planos", href: "#planos" },
    mostrar_nota: false,
    nota: null,
  },
  numeros: [],
  empresas: [],
  servicos: [],
  areas: [],
  precos: { mostrar_anual: true, planos: [] },
  testemunhos: [],
  perguntas: [],
  definicoes: {
    titulo: "ProEnglish: inglês para o seu trabalho",
    descricao: "Cursos de inglês por área profissional, feitos para Angola. 15 minutos por dia e conversa com um tutor de IA.",
    palavras_chave: "",
    ga_id: null,
    pixel_id: null,
    email: null,
    telefone: null,
    instagram: null,
    linkedin: null,
    facebook: null,
  },
  manutencao: { activa: false, mensagem: "", volta_em: null },
  publicado_em: null,
};

const API = process.env.DJANGO_API_URL_INTERNA || process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";

export async function lerSite(): Promise<Site> {
  try {
    const r = await fetch(`${API}/site/`, { next: { revalidate: 60, tags: ["site"] } });
    if (!r.ok) return SITE_POR_DEFEITO;
    const d = (await r.json()) as Partial<Site>;
    return { ...SITE_POR_DEFEITO, ...d, topo: { ...SITE_POR_DEFEITO.topo, ...d.topo }, definicoes: { ...SITE_POR_DEFEITO.definicoes, ...d.definicoes } } as Site;
  } catch {
    return SITE_POR_DEFEITO;
  }
}

/** Frase do trabalho para cada área (o que um profissional dessa área diz mesmo). */
export const FRASES_AREA: Record<string, { frase: string; texto: string }> = {
  "Petróleo e Gás": { frase: "Could you send me the drilling report by Friday?", texto: "Reuniões de segurança, relatórios de turno e instruções em plataforma." },
  Banca: { frase: "Your transfer will arrive within two business days.", texto: "Atendimento, contas, taxas e reclamações explicadas com clareza." },
  Saúde: { frase: "Where exactly does it hurt?", texto: "Consulta, triagem e passagem de turno com doentes e colegas estrangeiros." },
  Direito: { frase: "The contract takes effect on the first of March.", texto: "Contratos, prazos e correspondência formal." },
  Tecnologia: { frase: "The deploy failed, so we rolled back.", texto: "Reuniões diárias, documentação e conversas com equipas remotas." },
  Gestão: { frase: "Let us move this decision to next quarter.", texto: "Apresentações, negociação e reuniões com parceiros internacionais." },
  Negócios: { frase: "Please find the revised proposal attached.", texto: "Emails, propostas e reuniões com clientes e fornecedores." },
  Geral: { frase: "Nice to meet you. I work in the finance team.", texto: "Apresentar-se, pequenas conversas e o inglês de todos os dias no escritório." },
};

/** Estado da manutenção, lido sem cache; null se a API não responder. */
export async function lerManutencao(): Promise<Site["manutencao"] | null> {
  try {
    const r = await fetch(`${API}/site/manutencao/`, { cache: "no-store", signal: AbortSignal.timeout(2000) });
    if (!r.ok) return null;
    return { ...SITE_POR_DEFEITO.manutencao, ...(await r.json()) };
  } catch {
    return null;
  }
}
