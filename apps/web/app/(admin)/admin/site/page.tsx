"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca } from "@/components/pe/professor/Partes";
import { FaixaPublicar } from "@/components/pe/admin/Site";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { quando } from "@/src/domains/student/avisos/api";
import { SECCOES_SITE, useEstadoSiteQuery, useMudarManutencaoMutation, type EstadoSite, type Seccao } from "@/src/domains/admin/administracao/site";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

function resumo(s: EstadoSite, c: Seccao) {
  const r = s.rascunho;
  switch (c) {
    case "topo":
      return `“${r.topo.titulo}”, com ${r.topo.botao_secundario ? "dois botões" : "um botão"}.`;
    case "numeros":
      return s.contagens.numeros ? `${plural(s.contagens.numeros, "número", "números")}; os automáticos actualizam-se sozinhos.` : "Nenhum número.";
    case "empresas":
      return s.contagens.empresas ? plural(s.contagens.empresas, "empresa", "empresas") : "Nenhuma empresa: a faixa não aparece.";
    case "servicos":
      return plural(s.contagens.servicos, "serviço", "serviços");
    case "precos":
      return `${plural(r.precos.planos.length, "plano", "planos")}. Os preços vêm de Planos e códigos.`;
    case "perguntas":
      return plural(s.contagens.perguntas, "pergunta", "perguntas");
    case "definicoes":
      return "Título, descrição, contactos, redes e medição de visitas.";
  }
}

export default function ConteudoSite() {
  const { data, isError, refetch } = useEstadoSiteQuery();
  const [manutencao, setManutencao] = useState(false);

  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Conteúdo do site" texto="As secções da página inicial e da página Sobre. O que mudar aqui só aparece no site quando carregar em Publicar.">
        <Botao asChild tipo="secundario" tamanho="medio">
          <a href="/" target="_blank" rel="noopener">
            Ver o site
          </a>
        </Botao>
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
          <Estado estado={data} aoManutencao={() => setManutencao(true)} />
          <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
            {SECCOES_SITE.map((s) => {
              const mudado = data.alterado_em[s.chave];
              const porPublicar = !!mudado && (!data.publicado_em || mudado > data.publicado_em);
              return (
                <li key={s.chave}>
                  <Link href={s.href} className="flex h-full items-center gap-4 rounded-pe-md border border-pe-linha bg-pe-fundo p-5 text-pe-tinta no-underline hover:border-pe-azul-marca hover:text-pe-tinta">
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2 font-pe-titulo text-[18px] font-semibold leading-6">
                        {s.nome}
                        {porPublicar ? <Etiqueta tipo="realce">Por publicar</Etiqueta> : null}
                      </span>
                      <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{resumo(data, s.chave)}</span>
                      {mudado ? <span className="text-[13px] leading-[18px] text-pe-tinta-suave">Mudado: {quando(mudado).toLowerCase()}</span> : null}
                    </span>
                    <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
                  </Link>
                </li>
              );
            })}
            <li>
              <Link href="/admin/feedback/testimonials" className="flex h-full items-center gap-4 rounded-pe-md border border-pe-linha bg-pe-fundo p-5 text-pe-tinta no-underline hover:border-pe-azul-marca hover:text-pe-tinta">
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="font-pe-titulo text-[18px] font-semibold leading-6">Testemunhos</span>
                  <span className="text-[15px] leading-[22px] text-pe-tinta-suave">
                    {data.contagens.testemunhos_no_site ? `${plural(data.contagens.testemunhos_no_site, "testemunho aprovado", "testemunhos aprovados")}; o site mostra até 3.` : "Nenhum aprovado: a secção não aparece."} Escolhem-se em Opiniões e testemunhos e aparecem no site em poucos minutos, sem precisar de publicar.
                  </span>
                </span>
                <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
              </Link>
            </li>
          </ul>
          <FaixaPublicar estado={data} completa />
          {manutencao ? <DialogoManutencao estado={data} aoFechar={() => setManutencao(false)} /> : null}
        </>
      )}
    </Pagina>
  );
}

function Estado({ estado, aoManutencao }: { estado: EstadoSite; aoManutencao: () => void }) {
  const m = estado.manutencao;
  const [mudar, { isLoading }] = useMudarManutencaoMutation();
  const [erro, setErro] = useState<string | null>(null);
  return (
    <div className={cnPe("flex flex-col gap-3 rounded-pe-md p-5 sm:flex-row sm:items-center", m.activa ? "bg-pe-errado-suave" : "bg-pe-certo-suave")}>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="m-0 font-semibold">{m.activa ? "O site está em manutenção." : "O site está no ar."}</p>
        <p className="m-0 text-[15px] leading-[22px]">
          {m.activa
            ? `Os visitantes vêem só a mensagem de manutenção; quem tem sessão aberta continua a usar a plataforma.${m.volta_em ? ` Volta ao ar sozinho ${new Date(m.volta_em).toLocaleString("pt-PT", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Africa/Luanda" })}, hora de Luanda.` : ""}`
            : estado.publicado_em
              ? `Última publicação: ${quando(estado.publicado_em).toLowerCase()}.`
              : "Ainda não foi publicado nada."}
        </p>
        {erro ? <p className="m-0 font-semibold text-pe-errado">{erro}</p> : null}
      </div>
      {m.activa ? (
        <Botao
          tamanho="medio"
          disabled={isLoading}
          onClick={async () => {
            setErro(null);
            try {
              await mudar({ activa: false }).unwrap();
            } catch (e) {
              setErro(mensagemErro(e, "Não foi possível tirar de manutenção."));
            }
          }}
        >
          Voltar a pôr no ar
        </Botao>
      ) : (
        <Botao tipo="secundario" tamanho="medio" onClick={aoManutencao}>
          Pôr em manutenção
        </Botao>
      )}
    </div>
  );
}

/** "2026-11-14T18:00" na hora de Luanda (o servidor lê as horas sem fuso como hora de Luanda). */
function luanda(d: Date) {
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Luanda", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(d);
  const v = (t: string) => p.find((x) => x.type === t)?.value;
  return `${v("year")}-${v("month")}-${v("day")}T${v("hour")}:${v("minute")}`;
}

function DialogoManutencao({ estado, aoFechar }: { estado: EstadoSite; aoFechar: () => void }) {
  const [mensagem, setMensagem] = useState(estado.manutencao.mensagem || "Estamos a melhorar o site. Voltamos dentro de pouco tempo.");
  const [volta, setVolta] = useState<"nunca" | "escolher">("nunca");
  const [hora, setHora] = useState(() => luanda(new Date(Date.now() + 2 * 3600_000)).slice(0, 14) + "00");
  const [erro, setErro] = useState<string | null>(null);
  const [mudar, { isLoading }] = useMudarManutencaoMutation();

  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo="Pôr o site em manutenção?" descricao="Quem abrir o site sem sessão vê só a mensagem abaixo. Alunos e professores com sessão aberta continuam a usar a plataforma." largura={520}>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          if (volta === "escolher" && !hora) return setErro("Escolha o dia e a hora em que o site volta ao ar.");
          try {
            await mudar({ activa: true, mensagem: mensagem.trim(), volta_em: volta === "escolher" ? hora : null }).unwrap();
            aoFechar();
          } catch (er) {
            setErro(mensagemErro(er, "Não foi possível pôr o site em manutenção."));
          }
        }}
      >
        <AreaTexto rotulo="Mensagem para os visitantes" rows={3} maxLength={300} value={mensagem} onChange={(e) => setMensagem(e.target.value)} ajuda={`${mensagem.length} de 300 caracteres`} />
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 p-0 font-semibold">Voltar ao ar</legend>
          <label className="flex min-h-11 items-center gap-3">
            <input type="radio" name="volta" checked={volta === "nunca"} onChange={() => setVolta("nunca")} className="size-5 accent-pe-azul-marca" />
            Só quando eu tirar
          </label>
          <label className="flex min-h-11 items-center gap-3">
            <input type="radio" name="volta" checked={volta === "escolher"} onChange={() => setVolta("escolher")} className="size-5 accent-pe-azul-marca" />
            Sozinho, a uma hora marcada
          </label>
          {volta === "escolher" ? <Campo rotulo="Dia e hora (hora de Luanda)" type="datetime-local" value={hora} min={luanda(new Date())} onChange={(e) => setHora(e.target.value)} /> : null}
        </fieldset>
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao type="button" tipo="secundario" tamanho="medio" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" tipo="perigo" tamanho="medio" disabled={isLoading}>
            Pôr em manutenção
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
