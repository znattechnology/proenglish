"use client";

import Link from "next/link";
import { Award, BookOpen, Check, GraduationCap, Heart, MessagesSquare, Mic, type LucideIcon } from "lucide-react";
import { Botao } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { kz, type Oferta, type RecursoOferta } from "@/src/domains/student/subscricao/api";

const ICONE: Record<RecursoOferta, LucideIcon> = {
  vidas: Heart,
  licoes: BookOpen,
  analises: Mic,
  conversa: MessagesSquare,
  exame: GraduationCap,
  certificado: Award,
};

/** Endereço do checkout com o formulário do teste grátis em foco (o fluxo de teste vive no checkout). */
function ligacaoTeste(ligacao: string) {
  return `${ligacao}${ligacao.includes("?") ? "&" : "?"}teste=1`;
}

/**
 * O plano que resolve o limite a que o aluno chegou: nome, preço por mês, o que ganha (o primeiro
 * ganho é o que resolve este limite) e os botões para assinar ou experimentar. A API decide tudo;
 * aqui só se mostra. `saidas` são as saídas gratuitas (esperar, recarregar, saltar, voltar), que
 * ficam sempre por baixo, como acções secundárias.
 */
export function OfertaPlano({ oferta, saidas, className }: { oferta: Oferta; saidas?: React.ReactNode; className?: string }) {
  const { plano, ganhos } = oferta;
  const [principal, ...outros] = ganhos;
  const Icone = ICONE[oferta.recurso] ?? Check;
  const teste = plano.pode_experimentar && plano.dias_teste > 0;

  return (
    <div className={cnPe("flex w-full flex-col gap-4", className)}>
      <section
        aria-label={`Plano ${plano.nome}`}
        className="pe-sobre-marca flex flex-col gap-4 rounded-pe-fala bg-pe-azul-marca px-5 pb-5 pt-[18px] text-pe-sobre-marca md:px-6 md:pb-6"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className="m-0 font-pe-titulo text-[20px] font-bold leading-[26px]">{plano.nome}</h3>
          <p className="m-0 flex items-baseline gap-1 font-pe-titulo text-pe-realce">
            <span className="text-[26px] font-bold leading-8 tabular-nums">{kz(plano.preco_mensal_kz)}</span>
            <span className="text-[15px] font-semibold">/mês</span>
          </p>
        </div>

        {principal ? (
          <p className="m-0 flex items-center gap-3 rounded-pe-fala-s bg-pe-realce px-3.5 py-3 text-[16px] font-semibold leading-[22px] text-pe-tinta">
            <Icone aria-hidden className="size-5 shrink-0" />
            {principal}
          </p>
        ) : null}

        {outros.length ? (
          <ul className="m-0 flex list-none flex-col gap-2 p-0 text-[15px] leading-[22px]">
            {outros.map((g) => (
              <li key={g} className="flex items-start gap-2.5">
                <Check aria-hidden className="mt-0.5 size-[18px] shrink-0 text-pe-realce" />
                {g}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <div className="flex flex-col gap-3">
        <Botao asChild tipo="realce" larguraTotal>
          <Link href={oferta.ligacao}>Assinar o {plano.nome}</Link>
        </Botao>
        {teste ? (
          <Botao asChild tipo="secundario" larguraTotal>
            <Link href={ligacaoTeste(oferta.ligacao)}>Experimentar {plano.dias_teste} dias grátis</Link>
          </Botao>
        ) : null}
        {saidas}
      </div>
    </div>
  );
}

/**
 * Folha (telemóvel) ou janela (desktop) de um limite: o título e a mensagem da API e, se houver
 * plano que o resolva, a oferta. Sem oferta, fica só a mensagem com as saídas gratuitas.
 */
export function FolhaOferta({
  aberto,
  aoMudar,
  titulo,
  mensagem,
  oferta,
  topo,
  aviso,
  children,
}: {
  aberto: boolean;
  aoMudar: (v: boolean) => void;
  titulo: string;
  mensagem?: React.ReactNode;
  oferta?: Oferta | null;
  topo?: React.ReactNode;
  /** Erro ou nota a mostrar acima dos botões. */
  aviso?: React.ReactNode;
  /** As saídas gratuitas (botões secundários). */
  children?: React.ReactNode;
}) {
  return (
    <Dialogo aberto={aberto} aoMudar={aoMudar} titulo={titulo} descricao={mensagem} topo={topo} largura={440}>
      {aviso}
      {oferta ? <OfertaPlano oferta={oferta} saidas={children} /> : <div className="flex flex-col gap-3">{children}</div>}
    </Dialogo>
  );
}
