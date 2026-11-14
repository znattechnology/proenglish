"use client";

import { useState } from "react";
import { AreaTexto, Aviso, Botao, Campo } from "@/components/pe";
import { PaginaSeccao } from "@/components/pe/admin/Site";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useMudarDefinicoesMutation, type Definicoes } from "@/src/domains/admin/administracao/site";

const CAMPOS: { grupo: string; texto?: string; campos: { k: keyof Definicoes; rotulo: string; max?: number; area?: boolean; ajuda?: string; tipo?: string }[] }[] = [
  {
    grupo: "Pesquisa no Google",
    campos: [
      { k: "titulo", rotulo: "Título do site", max: 70 },
      { k: "descricao", rotulo: "Descrição", max: 160, area: true },
      { k: "palavras_chave", rotulo: "Palavras-chave", max: 255, ajuda: "Separadas por vírgulas." },
    ],
  },
  {
    grupo: "Contactos",
    texto: "Aparecem no rodapé e na página Sobre. Deixe vazio o que não quiser mostrar.",
    campos: [
      { k: "email", rotulo: "Email", tipo: "email" },
      { k: "telefone", rotulo: "Telefone", tipo: "tel", ajuda: "Por exemplo: +244 923 000 000" },
      { k: "instagram", rotulo: "Instagram", tipo: "url", ajuda: "https://instagram.com/…" },
      { k: "linkedin", rotulo: "LinkedIn", tipo: "url", ajuda: "https://linkedin.com/company/…" },
      { k: "facebook", rotulo: "Facebook", tipo: "url", ajuda: "https://facebook.com/…" },
    ],
  },
  {
    grupo: "Medição de visitas",
    texto: "Só carregam nos visitantes que aceitarem os cookies. Sem nenhum preenchido, o aviso de cookies não aparece.",
    campos: [
      { k: "ga_id", rotulo: "Google Analytics", ajuda: "Formato G-XXXXXXX" },
      { k: "pixel_id", rotulo: "Pixel da Meta", ajuda: "Só algarismos" },
    ],
  },
];

export default function DefinicoesSite() {
  // Fora do formulário: guardar recarrega o rascunho e o formulário volta a montar-se.
  const [guardado, setGuardado] = useState(false);
  return (
    <PaginaSeccao titulo="Definições e SEO" texto="Como o site aparece nas pesquisas, os contactos e a medição de visitas.">
      {(s) => <Formulario key={JSON.stringify(s.rascunho.definicoes)} guardado={guardado} setGuardado={setGuardado} d={s.rascunho.definicoes} />}
    </PaginaSeccao>
  );
}

function Formulario({ d, guardado, setGuardado }: { d: Definicoes; guardado: boolean; setGuardado: (v: boolean) => void }) {
  const [v, setV] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(d).map(([k, x]) => [k, x ?? ""])));
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [guardar, { isLoading }] = useMudarDefinicoesMutation();
  const opcionais = new Set(["ga_id", "pixel_id", "email", "telefone", "instagram", "linkedin", "facebook"]);

  return (
    <form
      noValidate
      className="flex max-w-[720px] flex-col gap-8"
      onSubmit={async (e) => {
        e.preventDefault();
        setErros({});
        setErro(null);
        const corpo = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, opcionais.has(k) ? x.trim() || null : x.trim()]));
        try {
          await guardar(corpo).unwrap();
          setGuardado(true);
        } catch (er) {
          const c = errosPorCampo(er);
          setErros(c);
          if (!Object.keys(c).some((k) => k in v)) setErro(mensagemErro(er, "Não foi possível guardar."));
        }
      }}
    >
      {CAMPOS.map((g) => (
        <fieldset key={g.grupo} className="m-0 flex flex-col gap-4 border-0 p-0">
          <legend className="mb-1 p-0 font-pe-titulo text-[20px] font-semibold">{g.grupo}</legend>
          {g.texto ? <p className="m-0 text-[15px] text-pe-tinta-suave">{g.texto}</p> : null}
          {g.campos.map((c) => {
            const comum = {
              rotulo: c.rotulo,
              maxLength: c.max,
              value: v[c.k] ?? "",
              erro: erros[c.k],
              ajuda: c.ajuda ?? (c.max ? `${(v[c.k] ?? "").length} de ${c.max} caracteres` : undefined),
            };
            const muda = (x: string) => {
              setV((o) => ({ ...o, [c.k]: x }));
              setGuardado(false);
            };
            return c.area ? (
              <AreaTexto key={c.k} {...comum} rows={3} onChange={(e) => muda(e.target.value)} />
            ) : (
              <Campo key={c.k} {...comum} type={c.tipo ?? "text"} onChange={(e) => muda(e.target.value)} />
            );
          })}
        </fieldset>
      ))}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-4">
        <Botao type="submit" tamanho="medio" disabled={isLoading}>
          {isLoading ? "A guardar…" : "Guardar"}
        </Botao>
        {guardado ? <span role="status" className="text-[15px] text-pe-certo">Guardado no rascunho.</span> : null}
      </div>
    </form>
  );
}
