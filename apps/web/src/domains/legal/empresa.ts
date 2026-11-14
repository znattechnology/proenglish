/**
 * Dados da empresa que aparecem nos Termos e na Política de privacidade.
 * PREENCHER antes de publicar: enquanto um valor começar por "[", a página mostra um aviso.
 */
export const EMPRESA = {
  nomeLegal: "[Nome legal da empresa]",
  nif: "[NIF]",
  morada: "[Morada da sede], Luanda, Angola",
  emailApoio: "[email de apoio]",
  emailPrivacidade: "[email para questões de privacidade]",
  telefone: "[telefone de apoio]",
};

/** Data a partir da qual a versão actual dos documentos se aplica (AAAA-MM-DD). */
export const EM_VIGOR = { termos: "2026-11-14", privacidade: "2026-11-14" };

export const porPreencher = () => Object.values(EMPRESA).some((v) => v.includes("["));

/**
 * Gravações dos exames orais: quantos meses ficam guardadas (espelha RETENCAO_GRAVACOES_DIAS em
 * apps/api/apps/practice/conversa/exame.py e o comando apagar_gravacoes_exames).
 */
export const MESES_RETENCAO_GRAVACOES = 12;
