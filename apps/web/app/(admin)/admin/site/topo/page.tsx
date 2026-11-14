"use client";

import { useState } from "react";
import { AreaTexto, Aviso, Botao, Campo, Interruptor } from "@/components/pe";
import { PaginaSeccao } from "@/components/pe/admin/Site";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useMudarTopoMutation, type Topo } from "@/src/domains/admin/administracao/site";

export default function TopoSite() {
  // Fora do formulário: guardar recarrega o rascunho e o formulário volta a montar-se.
  const [guardado, setGuardado] = useState(false);
  return (
    <PaginaSeccao titulo="Topo da página" texto="A primeira coisa que os visitantes lêem: título, texto e botões.">
      {(s) => <Formulario key={JSON.stringify({ ...s.rascunho.topo, nota_prevista: null })} guardado={guardado} setGuardado={setGuardado} topo={s.rascunho.topo} />}
    </PaginaSeccao>
  );
}

function Formulario({ topo, guardado, setGuardado }: { topo: Topo; guardado: boolean; setGuardado: (v: boolean) => void }) {
  const [t, setT] = useState({
    etiqueta: topo.etiqueta ?? "",
    titulo: topo.titulo,
    texto: topo.texto,
    b1: topo.botao_principal,
    temB2: !!topo.botao_secundario,
    b2: topo.botao_secundario ?? { texto: "Ver planos", href: "#planos" },
    mostrar_nota: topo.mostrar_nota,
  });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [guardar, { isLoading }] = useMudarTopoMutation();
  const pr = (p: Partial<typeof t>) => {
    setT((x) => ({ ...x, ...p }));
    setGuardado(false);
  };
  const nota = topo.nota_prevista;

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:items-start">
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setErros({});
          setErro(null);
          try {
            await guardar({
              etiqueta: t.etiqueta.trim() || null,
              titulo: t.titulo.trim(),
              texto: t.texto.trim(),
              botao_principal: { texto: t.b1.texto.trim(), href: t.b1.href.trim() },
              botao_secundario: t.temB2 ? { texto: t.b2.texto.trim(), href: t.b2.href.trim() } : null,
              mostrar_nota: t.mostrar_nota,
            }).unwrap();
            setGuardado(true);
          } catch (er) {
            const c = errosPorCampo(er);
            setErros(c);
            if (!["etiqueta", "titulo", "texto", "botao_principal", "botao_secundario"].some((k) => c[k])) setErro(mensagemErro(er, "Não foi possível guardar."));
          }
        }}
      >
        <Campo rotulo="Etiqueta acima do título (opcional)" maxLength={60} value={t.etiqueta} onChange={(e) => pr({ etiqueta: e.target.value })} erro={erros.etiqueta} ajuda="Deixe vazio para não mostrar." />
        <Campo rotulo="Título" maxLength={80} value={t.titulo} onChange={(e) => pr({ titulo: e.target.value })} erro={erros.titulo} ajuda={`${t.titulo.length} de 80 caracteres`} />
        <AreaTexto rotulo="Texto" rows={3} maxLength={240} value={t.texto} onChange={(e) => pr({ texto: e.target.value })} erro={erros.texto} ajuda={`${t.texto.length} de 240 caracteres`} />
        <fieldset className="m-0 grid gap-4 border-0 p-0 sm:grid-cols-2">
          <legend className="mb-3 p-0 font-semibold">Botão principal</legend>
          <Campo rotulo="Texto" maxLength={30} value={t.b1.texto} onChange={(e) => pr({ b1: { ...t.b1, texto: e.target.value } })} />
          <Campo rotulo="Leva a" value={t.b1.href} onChange={(e) => pr({ b1: { ...t.b1, href: e.target.value } })} ajuda="/signup, #planos ou https://…" />
          {erros.botao_principal ? <p className="m-0 text-pe-legenda font-semibold text-pe-errado sm:col-span-2">{erros.botao_principal}</p> : null}
        </fieldset>
        <Interruptor rotulo="Mostrar um segundo botão" ligado={t.temB2} aoMudar={(v) => pr({ temB2: v })} />
        {t.temB2 ? (
          <fieldset className="m-0 grid gap-4 border-0 p-0 sm:grid-cols-2">
            <legend className="mb-3 p-0 font-semibold">Botão secundário</legend>
            <Campo rotulo="Texto" maxLength={30} value={t.b2.texto} onChange={(e) => pr({ b2: { ...t.b2, texto: e.target.value } })} />
            <Campo rotulo="Leva a" value={t.b2.href} onChange={(e) => pr({ b2: { ...t.b2, href: e.target.value } })} ajuda="#como-funciona, #planos, #areas…" />
            {erros.botao_secundario ? <p className="m-0 text-pe-legenda font-semibold text-pe-errado sm:col-span-2">{erros.botao_secundario}</p> : null}
          </fieldset>
        ) : null}
        <Interruptor
          rotulo="Mostrar a nota das opiniões"
          descricao={nota ? `Usa a média real das opiniões aprovadas: ${nota.media.toLocaleString("pt-PT", { maximumFractionDigits: 1 })} de ${nota.total}.` : "Só aparece quando houver pelo menos 5 opiniões aprovadas."}
          ligado={t.mostrar_nota}
          aoMudar={(v) => pr({ mostrar_nota: v })}
        />
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-wrap items-center gap-4">
          <Botao type="submit" tamanho="medio" disabled={isLoading}>
            {isLoading ? "A guardar…" : "Guardar"}
          </Botao>
          {guardado ? <span role="status" className="text-[15px] text-pe-certo">Guardado no rascunho.</span> : null}
        </div>
      </form>

      <section aria-label="Pré-visualização" className="flex flex-col gap-3">
        <h2 className="m-0 text-[15px] font-semibold text-pe-tinta-suave">Pré-visualização</h2>
        <div className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-6 md:p-8">
          {t.etiqueta.trim() ? <p className="m-0 text-[14px] font-semibold text-pe-azul-marca">{t.etiqueta}</p> : null}
          <p className="m-0 text-balance font-pe-titulo text-[34px] font-bold leading-[1.1] tracking-[-0.02em]">{t.titulo || "Título"}</p>
          <p className="m-0 text-pe-tinta-suave">{t.texto}</p>
          <div className="flex flex-wrap gap-3">
            <span className="inline-flex min-h-11 items-center rounded-pe-sm bg-pe-realce px-5 font-semibold">{t.b1.texto || "Botão"}</span>
            {t.temB2 ? <span className="inline-flex min-h-11 items-center rounded-pe-sm border-2 border-pe-azul-marca px-5 font-semibold text-pe-azul-marca">{t.b2.texto || "Botão"}</span> : null}
          </div>
          {t.mostrar_nota && nota ? (
            <p className="m-0 text-[14px] text-pe-tinta-suave">
              Nota média de {nota.media.toLocaleString("pt-PT", { maximumFractionDigits: 1 })} em 5, de {nota.total} opiniões de alunos.
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
