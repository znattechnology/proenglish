"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Check, Clock, X } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Logo, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  useEntregarTesteBasicoMutation,
  useEstadoTesteBasicoQuery,
  useIniciarTesteBasicoMutation,
  type EstadoTesteBasico,
  type TentativaTeste,
} from "@/src/domains/student/curso/testeBasico";

const dataHora = (iso: string) =>
  new Date(iso).toLocaleString("pt-PT", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

/** Segundos que faltam até `iso`, actualizados a cada segundo. */
function useFalta(iso: string | null) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    if (!iso) return;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [iso]);
  return iso ? Math.max(0, Math.round((new Date(iso).getTime() - agora) / 1000)) : 0;
}

export function TesteBasico() {
  const { data, isLoading, isError, refetch } = useEstadoTesteBasicoQuery();
  const [iniciar, { isLoading: aIniciar }] = useIniciarTesteBasicoMutation();
  const [resultado, setResultado] = useState<TentativaTeste | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const comecar = async () => {
    setErro(null);
    const r = await iniciar();
    if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível abrir o teste. Tente outra vez."));
  };

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[720px] flex-col px-5 pb-10 pt-5">
      <header className="flex items-center justify-between gap-4 pb-8">
        <Logo altura={36} className="h-9 w-auto" />
        <Link href="/user/courses" className="py-2 text-[15px] font-semibold">
          Sair do teste
        </Link>
      </header>

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <Osso className="h-10 w-2/3" />
          <Osso className="h-24 w-full" />
          <Osso className="h-12 w-40" />
        </div>
      ) : isError || !data ? (
        <div className="flex flex-col items-start gap-4">
          <h1 className="m-0 text-pe-titulo-m">Não conseguimos abrir o teste</h1>
          <p className="m-0 text-pe-tinta-suave">O problema é do nosso lado. Tente outra vez daqui a pouco.</p>
          <Botao onClick={() => void refetch()}>Tentar outra vez</Botao>
        </div>
      ) : resultado ? (
        <Resultado t={resultado} estado={data} />
      ) : data.tem_nivel_basico ? (
        <Aprovado />
      ) : data.em_curso?.perguntas ? (
        <Perguntas key={data.em_curso.id} t={data.em_curso} aoEntregar={setResultado} />
      ) : (
        <Entrada estado={data} aIniciar={aIniciar} erro={erro} aoComecar={() => void comecar()} />
      )}
    </div>
  );
}

function Entrada({ estado, aIniciar, erro, aoComecar }: { estado: EstadoTesteBasico; aIniciar: boolean; erro: string | null; aoComecar: () => void }) {
  const r = estado.regras;
  const certasParaPassar = Math.ceil((r.perguntas * r.aprovacao) / 100);
  return (
    <main className="flex flex-col items-start gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="m-0 text-balance font-pe-titulo text-[32px] font-bold leading-[1.12] tracking-[-0.015em] md:text-[40px]">Teste do nível básico</h1>
        <p className="m-0 max-w-[60ch] text-pe-corpo-l text-pe-tinta-suave">
          Os cursos de sector pedem, no mínimo, o nível básico de inglês. Se já o tem, prove-o aqui e inscreva-se logo em qualquer sector.
        </p>
      </div>
      <dl className="m-0 grid w-full gap-x-8 gap-y-4 rounded-pe-fala bg-pe-fundo-suave p-6 sm:grid-cols-3">
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">perguntas de escolha</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{r.perguntas}</dd>
        </div>
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">minutos, sem pausa</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{r.minutos}</dd>
        </div>
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">certas para aprovar</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{certasParaPassar}</dd>
        </div>
      </dl>
      {estado.ultima && estado.ultima.aprovado === false ? (
        <Aviso tipo="info">
          Na última tentativa acertou {estado.ultima.certas} de {estado.ultima.total}.
        </Aviso>
      ) : null}
      {estado.pode_iniciar ? (
        <>
          <p className="m-0 max-w-[60ch] text-[15px] leading-[22px] text-pe-tinta-suave">
            O tempo começa a contar quando abrir o teste e não pára se sair. Se não aprovar, pode repetir {r.espera_horas} horas depois.
          </p>
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <Botao disabled={aIniciar} onClick={aoComecar}>
            {aIniciar ? "A abrir o teste…" : "Começar o teste"}
          </Botao>
        </>
      ) : (
        <>
          <Aviso tipo="info">
            Pode repetir o teste a partir de {estado.proxima_tentativa_em ? dataHora(estado.proxima_tentativa_em) : "amanhã"}.
          </Aviso>
          <p className="m-0 max-w-[60ch] text-pe-tinta-suave">
            Entretanto, o curso geral English Communication Skills leva-o ao nível básico, a falar desde a primeira lição.
          </p>
          <Botao asChild>
            <Link href="/user/courses">Ver o curso geral</Link>
          </Botao>
        </>
      )}
    </main>
  );
}

function Perguntas({ t, aoEntregar }: { t: TentativaTeste; aoEntregar: (r: TentativaTeste) => void }) {
  const perguntas = useMemo(() => t.perguntas ?? [], [t.perguntas]);
  const [indice, setIndice] = useState(0);
  const [respostas, setRespostas] = useState<Record<string, number>>({});
  const [entregar, { isLoading }] = useEntregarTesteBasicoMutation();
  const [erro, setErro] = useState<string | null>(null);
  const falta = useFalta(t.expira_em);
  const p = perguntas[indice];
  const ultima = indice === perguntas.length - 1;
  const respondidas = Object.keys(respostas).length;

  const enviar = async () => {
    setErro(null);
    const r = await entregar({ id: t.id, respostas });
    if ("data" in r && r.data) return aoEntregar(r.data);
    setErro(mensagemErro("error" in r ? r.error : null, "Não foi possível entregar o teste. Verifique a ligação e tente outra vez."));
  };

  // Tempo esgotado: entrega o que houver (o servidor aceita uns segundos de tolerância).
  useEffect(() => {
    const id = setTimeout(() => void enviar(), Math.max(0, new Date(t.expira_em).getTime() - Date.now()));
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t.expira_em]);

  if (!p) return null;
  const minutos = Math.floor(falta / 60);
  const segundos = String(falta % 60).padStart(2, "0");

  return (
    <main className="flex flex-1 flex-col gap-6">
      <div className="flex items-center gap-4">
        <BarraProgresso valor={(respondidas / perguntas.length) * 100} rotulo={`${respondidas} de ${perguntas.length} respondidas`} className="flex-1" />
        <span className={cnPe("flex items-center gap-1.5 font-semibold tabular-nums", falta <= 60 && "text-pe-errado")} aria-live="off">
          <Clock aria-hidden className="size-4" />
          {minutos}:{segundos}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <p className="m-0 text-[15px] font-semibold text-pe-tinta-suave">
          Pergunta {indice + 1} de {perguntas.length}
        </p>
        <h1 lang="en" className="m-0 font-pe-titulo text-[24px] font-semibold leading-[1.3] md:text-[28px]">
          {p.enunciado}
        </h1>
      </div>
      <div role="radiogroup" aria-label="Opções de resposta" className="flex flex-col gap-3">
        {p.opcoes.map((o, i) => {
          const escolhida = respostas[p.id] === i;
          return (
            <button
              key={o}
              type="button"
              role="radio"
              aria-checked={escolhida}
              lang="en"
              onClick={() => setRespostas((r) => ({ ...r, [p.id]: i }))}
              className={cnPe(
                "min-h-[56px] rounded-pe-md border-2 px-5 py-3 text-left text-[18px] leading-7",
                escolhida ? "border-pe-azul-marca bg-pe-fundo-suave font-semibold" : "border-pe-linha bg-pe-fundo hover:border-pe-linha-forte"
              )}
            >
              {o}
            </button>
          );
        })}
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        <Botao tipo="secundario" disabled={indice === 0} onClick={() => setIndice((i) => i - 1)}>
          Anterior
        </Botao>
        {ultima ? (
          <Botao disabled={isLoading} onClick={() => void enviar()}>
            {isLoading ? "A entregar…" : respondidas < perguntas.length ? `Entregar com ${perguntas.length - respondidas} por responder` : "Entregar o teste"}
          </Botao>
        ) : (
          <Botao onClick={() => setIndice((i) => i + 1)}>{respostas[p.id] === undefined ? "Saltar" : "Seguinte"}</Botao>
        )}
      </div>
    </main>
  );
}

function Resultado({ t, estado }: { t: TentativaTeste; estado: EstadoTesteBasico }) {
  if (t.aprovado) return <Aprovado nota={`${t.certas} de ${t.total}`} />;
  return (
    <main className="flex flex-col items-start gap-5">
      <span aria-hidden className="flex size-14 items-center justify-center rounded-pe-fala-s bg-pe-errado-suave text-pe-errado">
        <X className="size-7" />
      </span>
      <h1 className="m-0 text-balance font-pe-titulo text-[32px] font-bold leading-[1.12]">Ainda não chegou ao nível básico</h1>
      <p className="m-0 max-w-[60ch] text-pe-corpo-l text-pe-tinta-suave">
        Acertou {t.certas} de {t.total}. Para aprovar precisa de {Math.ceil((t.total * estado.regras.aprovacao) / 100)}. Comece pelo curso geral English Communication Skills: quando o concluir, os cursos de sector abrem-se.
      </p>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Pode repetir o teste {estado.regras.espera_horas} horas depois desta tentativa.</p>
      <Botao asChild>
        <Link href="/user/courses">Ver o curso geral</Link>
      </Botao>
    </main>
  );
}

function Aprovado({ nota }: { nota?: string }) {
  return (
    <main className="flex flex-col items-start gap-5">
      <span aria-hidden className="flex size-14 items-center justify-center rounded-pe-fala-s bg-pe-certo-suave text-pe-certo">
        <Check className="size-7" />
      </span>
      <h1 className="m-0 text-balance font-pe-titulo text-[32px] font-bold leading-[1.12]">Tem o nível básico</h1>
      <p className="m-0 max-w-[60ch] text-pe-corpo-l text-pe-tinta-suave">
        {nota ? `Acertou ${nota}. ` : ""}Já pode inscrever-se em qualquer curso de sector.
      </p>
      <Botao asChild tipo="realce">
        <Link href="/user/courses">Escolher um curso de sector</Link>
      </Botao>
    </main>
  );
}
