"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Escolha, Interruptor, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca } from "@/components/pe/professor/Partes";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  useApagarItemMutation,
  useCriarItemMutation,
  useDescartarMutation,
  useEstadoSiteQuery,
  useMudarItemMutation,
  useOrdenarMutation,
  usePublicarMutation,
  type EstadoSite,
  type Lista,
} from "@/src/domains/admin/administracao/site";

/** Moldura das páginas de uma secção: voltar, título e a faixa de publicar quando há alterações. */
export function PaginaSeccao({ titulo, texto, children, accoes }: { titulo: string; texto?: string; children: (s: EstadoSite) => React.ReactNode; accoes?: React.ReactNode }) {
  const { data, isError, refetch } = useEstadoSiteQuery();
  return (
    <Pagina className="gap-6">
      <Link href="/admin/site" className="-mb-2 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        Conteúdo do site
      </Link>
      <Cabeca titulo={titulo} texto={texto}>
        {accoes}
      </Cabeca>
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o conteúdo do site.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : (
        <>
          {children(data)}
          <FaixaPublicar estado={data} />
        </>
      )}
    </Pagina>
  );
}

/** Lembra que as alterações só chegam ao site depois de publicar. */
export function FaixaPublicar({ estado, completa }: { estado: EstadoSite; completa?: boolean }) {
  const [publicar, p] = usePublicarMutation();
  const [descartar, d] = useDescartarMutation();
  const [confirmar, setConfirmar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  // A mensagem de "Publicado" só vale até ao próximo rascunho.
  const [visto, setVisto] = useState(estado.ha_alteracoes);
  if (visto !== estado.ha_alteracoes) {
    setVisto(estado.ha_alteracoes);
    if (estado.ha_alteracoes) setFeito(null);
  }

  if (!estado.ha_alteracoes)
    return feito ? (
      <Aviso tipo="certo" className="sticky bottom-3">
        {feito}
      </Aviso>
    ) : completa ? (
      <p className="m-0 text-[15px] text-pe-tinta-suave">Não há alterações por publicar: o site mostra o que está aqui.</p>
    ) : null;

  return (
    <div className="sticky bottom-3 z-10 flex flex-col gap-3 rounded-[20px_20px_20px_0] bg-pe-azul-marca p-4 text-pe-sobre-marca shadow-pe-2 sm:flex-row sm:items-center sm:px-6">
      <p className="m-0 flex-1 text-[15px] leading-[22px]">
        Há alterações por publicar. Os visitantes continuam a ver a versão anterior até carregar em Publicar.
        {erro ? <span className="mt-1 block font-semibold text-pe-realce">{erro}</span> : null}
      </p>
      <div className="flex shrink-0 gap-2">
        <button type="button" onClick={() => setConfirmar(true)} className="min-h-11 rounded-pe-sm border-2 border-pe-sobre-marca bg-transparent px-4 font-semibold text-pe-sobre-marca">
          Descartar
        </button>
        <button
          type="button"
          disabled={p.isLoading}
          onClick={async () => {
            setErro(null);
            try {
              await publicar().unwrap();
              setFeito("Publicado. O site mostra as alterações dentro de um minuto.");
            } catch (e) {
              setErro(mensagemErro(e, "Não foi possível publicar. Tente outra vez."));
            }
          }}
          className="min-h-11 rounded-pe-sm bg-pe-realce px-5 font-semibold text-pe-tinta disabled:opacity-60"
        >
          {p.isLoading ? "A publicar…" : "Publicar alterações"}
        </button>
      </div>
      <Dialogo aberto={confirmar} aoMudar={setConfirmar} titulo="Descartar as alterações?" descricao="Todas as secções voltam ao que está publicado no site. Não dá para desfazer.">
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setConfirmar(false)}>
            Manter
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={d.isLoading}
            onClick={async () => {
              try {
                await descartar().unwrap();
                setFeito("Alterações descartadas.");
              } catch (e) {
                setErro(mensagemErro(e, "Não foi possível descartar."));
              }
              setConfirmar(false);
            }}
          >
            Descartar alterações
          </Botao>
        </div>
      </Dialogo>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Listas (números, empresas, serviços, perguntas)                     */
/* ------------------------------------------------------------------ */

export type CampoLista = {
  chave: string;
  rotulo: string;
  tipo: "texto" | "area" | "escolha" | "interruptor";
  max?: number;
  ajuda?: string;
  descricao?: string;
  opcoes?: Record<string, string>;
  /** Só aparece quando esta condição for verdadeira (ex.: valor só para números manuais). */
  se?: (d: Record<string, unknown>) => boolean;
};

type Item = { id: number } & Record<string, unknown>;

export function ListaSite<T extends Item>({
  lista,
  itens,
  nome,
  novo,
  campos,
  porDefeito,
  linha,
  extra,
  maximo,
}: {
  lista: Lista;
  itens: T[];
  nome: { um: string; artigo: "o" | "a"; novo: string };
  novo?: string;
  campos: CampoLista[];
  porDefeito: Record<string, unknown>;
  linha: (i: T) => React.ReactNode;
  extra?: (i: T) => React.ReactNode;
  maximo: number;
}) {
  const [aberto, setAberto] = useState<T | "novo" | null>(null);
  const [apagar, setApagar] = useState<T | null>(null);
  const [ordenar, o] = useOrdenarMutation();
  const [apagarItem, a] = useApagarItemMutation();
  const [erro, setErro] = useState<string | null>(null);

  const mover = async (i: number, delta: number) => {
    const ids = itens.map((x) => x.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    try {
      await ordenar({ lista, ids }).unwrap();
    } catch (e) {
      setErro(mensagemErro(e, "Não foi possível mudar a ordem."));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {itens.length ? (
        <ol className="m-0 flex list-none flex-col p-0">
          {itens.map((it, i) => (
            <li key={it.id} className="flex flex-col gap-3 border-b border-pe-fundo-forte py-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">{linha(it)}</div>
              <div className="flex shrink-0 flex-wrap items-center gap-1">
                {extra?.(it)}
                <button type="button" aria-label={`Subir ${nome.um}`} disabled={i === 0 || o.isLoading} onClick={() => mover(i, -1)} className="flex size-11 items-center justify-center rounded-pe-sm bg-transparent text-pe-tinta-suave hover:bg-pe-fundo-suave disabled:opacity-30">
                  <ArrowUp aria-hidden className="size-5" />
                </button>
                <button type="button" aria-label={`Descer ${nome.um}`} disabled={i === itens.length - 1 || o.isLoading} onClick={() => mover(i, 1)} className="flex size-11 items-center justify-center rounded-pe-sm bg-transparent text-pe-tinta-suave hover:bg-pe-fundo-suave disabled:opacity-30">
                  <ArrowDown aria-hidden className="size-5" />
                </button>
                <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setAberto(it)}>
                  Editar
                </Botao>
                <Botao tipo="ligacao" tamanho="pequeno" className="text-pe-errado hover:text-pe-errado" onClick={() => setApagar(it)}>
                  Apagar
                </Botao>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Ainda não há nada nesta secção. No site, ela não aparece enquanto estiver vazia.</p>
      )}
      {itens.length < maximo ? (
        <Botao tipo="secundario" tamanho="medio" className="self-start" onClick={() => setAberto("novo")}>
          {novo ?? nome.novo}
        </Botao>
      ) : (
        <p className="m-0 text-[15px] text-pe-tinta-suave">Chegou ao máximo de {maximo}. Apague um para juntar outro.</p>
      )}

      {aberto ? <FormItem key={aberto === "novo" ? "novo" : aberto.id} lista={lista} item={aberto === "novo" ? null : aberto} nome={nome} campos={campos} porDefeito={porDefeito} aoFechar={() => setAberto(null)} /> : null}

      <Dialogo aberto={!!apagar} aoMudar={(v) => !v && setApagar(null)} titulo={`Apagar ${nome.artigo} ${nome.um}?`} descricao="Sai do rascunho já; do site, só quando publicar.">
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(null)}>
            Manter
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={a.isLoading}
            onClick={async () => {
              if (!apagar) return;
              try {
                await apagarItem({ lista, id: apagar.id }).unwrap();
              } catch (e) {
                setErro(mensagemErro(e, "Não foi possível apagar."));
              }
              setApagar(null);
            }}
          >
            Apagar
          </Botao>
        </div>
      </Dialogo>
    </div>
  );
}

function FormItem({
  lista,
  item,
  nome,
  campos,
  porDefeito,
  aoFechar,
}: {
  lista: Lista;
  item: Item | null;
  nome: { um: string; novo: string };
  campos: CampoLista[];
  porDefeito: Record<string, unknown>;
  aoFechar: () => void;
}) {
  const [dados, setDados] = useState<Record<string, unknown>>(() => {
    const base = { ...porDefeito };
    if (item) for (const c of campos) base[c.chave] = item[c.chave] ?? (c.tipo === "interruptor" ? false : "");
    return base;
  });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [criar, c] = useCriarItemMutation();
  const [mudar, m] = useMudarItemMutation();
  const pr = (k: string, v: unknown) => setDados((d) => ({ ...d, [k]: v }));
  const visiveis = campos.filter((f) => !f.se || f.se(dados));

  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={item ? `Editar ${nome.um}` : nome.novo} largura={560}>
      <form
        noValidate
        className="flex max-h-[65dvh] flex-col gap-4 overflow-y-auto pr-1"
        onSubmit={async (e) => {
          e.preventDefault();
          setErros({});
          setErro(null);
          const corpo: Record<string, unknown> = {};
          for (const f of visiveis) corpo[f.chave] = typeof dados[f.chave] === "string" ? (dados[f.chave] as string).trim() : dados[f.chave];
          try {
            if (item) await mudar({ lista, id: item.id, dados: corpo }).unwrap();
            else await criar({ lista, dados: corpo }).unwrap();
            aoFechar();
          } catch (er) {
            const porCampo = errosPorCampo(er);
            setErros(porCampo);
            if (!visiveis.some((f) => porCampo[f.chave])) setErro(mensagemErro(er, "Não foi possível guardar."));
          }
        }}
      >
        {visiveis.map((f) => {
          const v = dados[f.chave];
          if (f.tipo === "interruptor") return <Interruptor key={f.chave} rotulo={f.rotulo} descricao={f.descricao} ligado={!!v} aoMudar={(x) => pr(f.chave, x)} />;
          if (f.tipo === "escolha")
            return (
              <Escolha key={f.chave} rotulo={f.rotulo} ajuda={f.ajuda} erro={erros[f.chave]} value={String(v ?? "")} onChange={(e) => pr(f.chave, e.target.value)}>
                {Object.entries(f.opcoes ?? {}).map(([k, n]) => (
                  <option key={k} value={k}>
                    {n}
                  </option>
                ))}
              </Escolha>
            );
          const comum = {
            rotulo: f.rotulo,
            erro: erros[f.chave],
            maxLength: f.max,
            value: String(v ?? ""),
            ajuda: f.ajuda ?? (f.max ? `${String(v ?? "").length} de ${f.max} caracteres` : undefined),
          };
          return f.tipo === "area" ? (
            <AreaTexto key={f.chave} {...comum} rows={4} onChange={(e) => pr(f.chave, e.target.value)} />
          ) : (
            <Campo key={f.chave} {...comum} onChange={(e) => pr(f.chave, e.target.value)} />
          );
        })}
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3 pt-2">
          <Botao type="button" tipo="secundario" tamanho="medio" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" tamanho="medio" disabled={c.isLoading || m.isLoading}>
            {c.isLoading || m.isLoading ? "A guardar…" : "Guardar"}
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
