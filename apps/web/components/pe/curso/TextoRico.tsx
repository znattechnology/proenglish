"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";
import { cnPe } from "@/lib/pe";

/**
 * Conteúdo de um capítulo escrito pelo professor. Pode vir em Markdown (editor novo)
 * ou em HTML (editor Quill antigo). Passa sempre pelo DOMPurify antes de ir para a página.
 */
export function TextoRico({ texto, className }: { texto: string; className?: string }) {
  const html = useMemo(() => {
    const t = texto.trim();
    const bruto = t.startsWith("<") ? t : (marked.parse(t, { async: false, gfm: true, breaks: false }) as string);
    return DOMPurify.sanitize(bruto, { USE_PROFILES: { html: true }, ADD_ATTR: ["target"] });
  }, [texto]);
  return <div className={cnPe("pe-texto-rico", className)} dangerouslySetInnerHTML={{ __html: html }} />;
}
