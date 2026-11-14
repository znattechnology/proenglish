const GENERICAS = /^(validation error|resource not found|permission denied|not found|internal server error|bad request)$/i;

/**
 * Texto de um erro da API, em qualquer dos formatos que ela usa:
 * {error: "texto"}, {error: true, message}, {mensagem, codigo}, {detail}, ou {details: {campo: [..]}}.
 * (Igual a mensagemErro da web.)
 */
export function mensagemErro(e: unknown, padrao = "Não foi possível concluir. Tente outra vez.") {
  const erro = e as { status?: number | string; data?: unknown } | undefined;
  if (erro?.status === "FETCH_ERROR") return "Sem ligação ao servidor. Verifique a Internet e tente outra vez.";
  if (erro?.status === "TIMEOUT_ERROR") return "O servidor demorou demasiado a responder. Tente outra vez.";
  const d = erro?.data as Record<string, unknown> | undefined;
  const propria429 = erro?.status === 429 && d && typeof d === "object" ? [d.mensagem, d.message, d.error].find((v) => typeof v === "string" && v.trim() && !GENERICAS.test(v.trim())) : null;
  if (erro?.status === 429) return (propria429 as string | undefined) ?? "Fez muitos pedidos seguidos. Espere um pouco e tente outra vez.";
  if (!d || typeof d !== "object") return padrao;
  const texto = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : Array.isArray(v) && typeof v[0] === "string" ? v[0] : null);
  const detalhes = d.details && typeof d.details === "object" ? (d.details as Record<string, unknown>) : null;
  const candidatos = [d.mensagem, d.error, d.message, d.detail, detalhes?.detail, detalhes?.non_field_errors, ...(detalhes ? Object.values(detalhes) : []), d.non_field_errors, ...Object.values(d)];
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

export function estadoErro(e: unknown) {
  return (e as { status?: number | string } | undefined)?.status;
}
