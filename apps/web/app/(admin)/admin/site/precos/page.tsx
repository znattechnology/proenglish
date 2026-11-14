"use client";

import Link from "next/link";
import { useState } from "react";
import { Aviso, Botao, Campo, Interruptor } from "@/components/pe";
import { PaginaSeccao } from "@/components/pe/admin/Site";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { kz } from "@/components/pe/site/Landing";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useMudarPrecosMutation, type PlanoSite } from "@/src/domains/admin/administracao/site";

type Textos = Pick<PlanoSite, "subtitulo" | "etiqueta" | "botao" | "nota_angola">;

export default function PrecosSite() {
  // Fora do formulário: guardar recarrega o rascunho e o formulário volta a montar-se.
  const [guardado, setGuardado] = useState(false);
  return (
    <PaginaSeccao titulo="Planos e preços" texto="Os preços, os dias de teste e o que cada plano inclui vêm de Planos e códigos. Aqui escolhe só os textos dos cartões.">
      {(s) => <Formulario key={JSON.stringify(s.rascunho.precos)} guardado={guardado} setGuardado={setGuardado} anual={s.rascunho.precos.mostrar_anual} planos={s.rascunho.precos.planos} />}
    </PaginaSeccao>
  );
}

function Formulario({ anual: anualInicial, planos, guardado, setGuardado }: { anual: boolean; planos: PlanoSite[]; guardado: boolean; setGuardado: (v: boolean) => void }) {
  const [anual, setAnual] = useState(anualInicial);
  const [textos, setTextos] = useState<Record<string, Textos>>(() => Object.fromEntries(planos.map((p) => [p.tipo, { subtitulo: p.subtitulo, etiqueta: p.etiqueta ?? "", botao: p.botao, nota_angola: p.nota_angola ?? "" }])));
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [guardar, { isLoading }] = useMudarPrecosMutation();
  const mudar = (tipo: string, k: keyof Textos, v: string) => {
    setTextos((t) => ({ ...t, [tipo]: { ...t[tipo], [k]: v } }));
    setGuardado(false);
  };

  return (
    <form
      noValidate
      className="flex flex-col gap-6"
      onSubmit={async (e) => {
        e.preventDefault();
        setErros({});
        setErro(null);
        try {
          await guardar({
            mostrar_anual: anual,
            planos: Object.entries(textos).map(([tipo, t]) => ({
              tipo: tipo as PlanoSite["tipo"],
              subtitulo: t.subtitulo.trim(),
              etiqueta: t.etiqueta?.trim() || null,
              botao: t.botao.trim(),
              nota_angola: t.nota_angola?.trim() || null,
            })),
          }).unwrap();
          setGuardado(true);
        } catch (er) {
          const c = errosPorCampo(er);
          setErros(c);
          if (!Object.keys(c).some((k) => k.startsWith("planos."))) setErro(mensagemErro(er, "Não foi possível guardar."));
        }
      }}
    >
      <Interruptor rotulo="Mostrar o preço anual" descricao="Junta “Ou … por ano” por baixo do preço mensal, nos planos que têm preço anual." ligado={anual} aoMudar={(v) => (setAnual(v), setGuardado(false))} />
      <div className="grid gap-5 lg:grid-cols-3">
        {planos.map((p) => {
          const t = textos[p.tipo];
          const er = (k: string) => erros[`planos.${p.tipo}.${k}`];
          return (
            <fieldset key={p.tipo} className="m-0 flex min-w-0 flex-col gap-4 rounded-pe-md border border-pe-linha p-5">
              <legend className="px-1 font-pe-titulo text-[18px] font-semibold">{p.nome}</legend>
              <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
                {kz(p.preco_mensal_kz)}
                {p.preco_mensal_kz ? " por mês" : ""}
                {p.preco_anual_kz ? `, ${kz(p.preco_anual_kz)} por ano` : ""}
                {p.dias_teste ? `, ${p.dias_teste} dias de teste` : ""}.{" "}
                <Link href={`/admin/plans/${p.id}`}>Mudar em Planos</Link>
              </p>
              <Campo rotulo="Subtítulo" maxLength={80} value={t.subtitulo} onChange={(e) => mudar(p.tipo, "subtitulo", e.target.value)} erro={er("subtitulo")} />
              <Campo rotulo="Etiqueta (opcional)" maxLength={30} value={t.etiqueta ?? ""} onChange={(e) => mudar(p.tipo, "etiqueta", e.target.value)} erro={er("etiqueta")} ajuda="Por exemplo: O mais escolhido" />
              <Campo rotulo="Texto do botão" maxLength={30} value={t.botao} onChange={(e) => mudar(p.tipo, "botao", e.target.value)} erro={er("botao")} />
              <Campo rotulo="Nota por baixo (opcional)" maxLength={120} value={t.nota_angola ?? ""} onChange={(e) => mudar(p.tipo, "nota_angola", e.target.value)} erro={er("nota_angola")} />
            </fieldset>
          );
        })}
      </div>
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
