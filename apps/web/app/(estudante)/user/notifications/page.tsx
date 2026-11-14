"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Award, Bell, BookOpen, CreditCard, Flame, Medal, Trophy } from "lucide-react";
import { Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { quando, useMarcarLidaMutation, useMarcarTodasMutation, useNotificacoesQuery, type Notificacao, type TipoNotificacao } from "@/src/domains/student/avisos/api";

const ICONE: Record<TipoNotificacao, React.ComponentType<{ className?: string }>> = {
  streak: Flame,
  achievement: Trophy,
  league: Medal,
  certificate: Award,
  course: BookOpen,
  subscription: CreditCard,
  system: Bell,
};

export default function PaginaNotificacoes() {
  const [paginas, setPaginas] = useState(1);
  return (
    <Pagina className="max-w-[880px]">
      <Lista paginas={paginas} aoVerMais={() => setPaginas((p) => p + 1)} />
    </Pagina>
  );
}

function Lista({ paginas, aoVerMais }: { paginas: number; aoVerMais: () => void }) {
  const primeira = useNotificacoesQuery(1);
  const [marcarTodas, { isLoading: aMarcar }] = useMarcarTodasMutation();
  const porLer = primeira.data?.unread ?? 0;
  const professor = (usePathname() ?? "").startsWith("/teacher");

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Notificações</h1>
          <p className="m-0 text-pe-tinta-suave" aria-live="polite">
            {primeira.data ? (porLer ? `${porLer} por ler` : "Está tudo lido.") : " "}
          </p>
        </div>
        {porLer ? (
          <Botao tipo="secundario" tamanho="pequeno" className="self-start" disabled={aMarcar} onClick={() => marcarTodas()}>
            Marcar como lidas
          </Botao>
        ) : null}
      </div>

      {primeira.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar as notificações.</p>
          <Botao tamanho="pequeno" onClick={() => primeira.refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !primeira.data ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <Osso key={i} className="h-[76px] rounded-pe-md" />
          ))}
        </div>
      ) : !primeira.data.results.length ? (
        <div className="flex flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
          <h2 className="m-0 text-pe-titulo-s">Ainda não há notificações</h2>
          <p className="m-0 text-pe-tinta-suave">{professor ? "Aqui aparecem as respostas da revisão dos seus cursos e outros avisos da equipa ProEnglish." : "Aqui aparecem os avisos da meta diária, da liga, dos certificados, das aulas novas e da subscrição."}</p>
        </div>
      ) : (
        <ul className="m-0 flex list-none flex-col p-0">
          {Array.from({ length: paginas }, (_, i) => (
            <PaginaDeItens key={i} pagina={i + 1} ultima={i + 1 === paginas} aoVerMais={aoVerMais} />
          ))}
        </ul>
      )}

      {professor ? null : (
        <Link href="/user/settings#avisos" className="self-start py-2 font-semibold text-pe-azul-marca underline-offset-[3px]">
          Escolher que avisos recebe
        </Link>
      )}
    </>
  );
}

function PaginaDeItens({ pagina, ultima, aoVerMais }: { pagina: number; ultima: boolean; aoVerMais: () => void }) {
  const { data, isFetching } = useNotificacoesQuery(pagina);
  // Avisos novos empurram os antigos para a página seguinte: não repetir os que a anterior já mostra.
  const { data: anterior } = useNotificacoesQuery(pagina - 1, { skip: pagina === 1 });
  if (!data) return <Osso className="my-2 h-[76px] rounded-pe-md" />;
  const jaMostradas = new Set((anterior?.results ?? []).map((n) => n.id));
  return (
    <>
      {data.results
        .filter((n) => !jaMostradas.has(n.id))
        .map((n) => (
          <Item key={n.id} n={n} />
        ))}
      {ultima && data.next ? (
        <li className="pt-3">
          <Botao tipo="ligacao" tamanho="pequeno" disabled={isFetching} onClick={aoVerMais}>
            Ver as mais antigas
          </Botao>
        </li>
      ) : null}
    </>
  );
}

function Item({ n }: { n: Notificacao }) {
  const router = useRouter();
  const [marcar] = useMarcarLidaMutation();
  const Icone = ICONE[n.kind] ?? Bell;
  const conteudo = (
    <>
      <span aria-hidden className={cnPe("flex size-10 shrink-0 items-center justify-center rounded-[14px_14px_14px_0]", n.read ? "bg-pe-fundo-suave text-pe-tinta-suave" : "pe-sobre-marca bg-pe-azul-marca text-pe-realce")}>
        <Icone className="size-5" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className={cnPe("leading-[22px]", n.read ? "font-normal" : "font-semibold")}>
          {n.read ? null : <span className="sr-only">Por ler: </span>}
          {n.title}
        </span>
        {n.body ? <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{n.body}</span> : null}
      </span>
      <span className="flex shrink-0 flex-col items-end gap-2">
        <time dateTime={n.created_at} className="whitespace-nowrap text-[13px] leading-[18px] text-pe-tinta-suave">
          {quando(n.created_at)}
        </time>
        {n.read ? null : <span aria-hidden className="size-2.5 rounded-full bg-pe-azul-vivo" />}
      </span>
    </>
  );
  const classe = "flex w-full items-start gap-3 border-b border-pe-fundo-forte bg-transparent px-1 py-4 text-left text-pe-tinta no-underline hover:bg-pe-fundo-suave md:px-3";
  return (
    <li>
      {n.link ? (
        <a
          href={n.link}
          className={classe}
          onClick={(e) => {
            e.preventDefault();
            if (!n.read) void marcar(n.id);
            router.push(n.link);
          }}
        >
          {conteudo}
        </a>
      ) : (
        <button type="button" className={classe} onClick={() => !n.read && marcar(n.id)}>
          {conteudo}
        </button>
      )}
    </li>
  );
}
