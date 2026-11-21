"use client";

import Link from "next/link";
import { useState } from "react";
import { BookOpen, Briefcase, Check, Fuel, Globe, Landmark, Laptop, Lock, Scale, Stethoscope } from "lucide-react";
import { Aviso, Botao, Logo, Osso } from "@/components/pe";
import { Perguntas } from "@/components/pe/acolhimento/TesteBasico";
import { entrarEcraInteiro } from "@/components/pe/acolhimento/ecraInteiro";
import { cnPe } from "@/lib/pe";
import {
  testeNecessario,
  useColocacaoQuery,
  useColocarMutation,
  useIniciarTesteColocacaoMutation,
  type NivelColocacao,
  type NivelDisponivel,
  type ResultadoColocacao,
} from "@/src/domains/student/curso/colocacao";
import type { TentativaTeste } from "@/src/domains/student/curso/testeBasico";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { AREAS, errosDoServidor, useGuardarPerfilMutation, useMetaQuery, useMudarMetaMutation, usePerfilQuery } from "@/src/domains/student/perfil/api";

const GERAL = "General English";

const ICONES: Record<string, React.ComponentType<{ className?: string }>> = {
  [GERAL]: Globe,
  "Industry English": Fuel,
  "Financial English": Landmark,
  "Business English": Briefcase,
  "Medical English": Stethoscope,
  "Legal English": Scale,
  "Technical English": Laptop,
};

const METAS = [
  { min: 5, nome: "Leve" },
  { min: 10, nome: "Normal" },
  { min: 15, nome: "Sério" },
  { min: 20, nome: "Intenso" },
];

const dataHora = (iso: string) => new Date(iso).toLocaleString("pt-PT", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

/**
 * Primeira entrada: área e meta diária; o nível em que começa o English Communication Skills
 * (A1 entra logo; outro nível pede um teste de 30 perguntas dos níveis abaixo, 70% em cada, em
 * ecrã inteiro); e o
 * curso onde ficou inscrito. Quem decide o nível e faz a inscrição é o servidor (/student/colocacao/).
 * Ocupa o ecrã inteiro, sem a navegação, como as lições.
 */
export default function PrimeiraEntrada() {
  const { data: perfil } = usePerfilQuery();
  const [passo, setPasso] = useState<1 | 2 | 3>(1);
  const [area, setArea] = useState<string | null>(null);
  const { data: metaGuardada } = useMetaQuery();
  const [metaEscolhida, setMeta] = useState<number | null>(null);
  const meta = metaEscolhida ?? metaGuardada?.daily_goal_minutes ?? 10;
  const [guardar, { isLoading: aGuardar }] = useGuardarPerfilMutation();
  const [mudarMeta] = useMudarMetaMutation();
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<{ r: ResultadoColocacao; tentativa: TentativaTeste | null } | null>(null);
  const areaEscolhida = area ?? perfil?.preferences.area ?? null;
  const primeiroNome = perfil?.name?.trim().split(/\s+/)[0];

  return (
    <div className="flex min-h-dvh flex-col bg-pe-fundo">
      <header className="flex items-center justify-between gap-4 border-b border-pe-linha px-5 py-3 md:px-10">
        <Logo altura={32} />
        <ol aria-label={`Passo ${passo} de 3`} className="m-0 flex list-none gap-1.5 p-0">
          {[1, 2, 3].map((n) => (
            <li key={n} aria-hidden className={cnPe("h-1.5 w-8 rounded-full", n <= passo ? "bg-pe-azul-marca" : "bg-pe-fundo-forte")} />
          ))}
        </ol>
      </header>

      <main className="mx-auto flex w-full max-w-[720px] flex-1 flex-col gap-7 px-5 py-8 md:py-12">
        <span className="text-[14px] font-semibold leading-5 text-pe-tinta-suave">Passo {passo} de 3</span>

        {passo === 1 ? (
          <>
            <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">
              {primeiroNome ? `Olá, ${primeiroNome}. ` : "Olá. "}Vamos preparar o seu curso.
            </h1>
            <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
              <legend className="mb-3 p-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">O que quer aprender?</legend>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {AREAS.map((a) => {
                  const Icone = ICONES[a.valor] ?? BookOpen;
                  const sel = a.valor === areaEscolhida;
                  const geral = a.valor === GERAL;
                  return (
                    <label
                      key={a.valor}
                      className={cnPe(
                        "flex min-h-[88px] cursor-pointer flex-col justify-between gap-2 rounded-pe-md p-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                        geral && "col-span-2 sm:col-span-3",
                        sel ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                      )}
                    >
                      <input type="radio" name="area" value={a.valor} checked={sel} onChange={() => setArea(a.valor)} className="sr-only" />
                      <Icone aria-hidden className={cnPe("size-6", sel ? "text-pe-realce" : "text-pe-azul-marca")} />
                      <span className="flex flex-col">
                        <span className="font-semibold leading-[22px]">{geral ? "Inglês geral" : `Inglês para ${a.nome}`}</span>
                        {geral ? (
                          <span className={cnPe("text-[14px] leading-5", sel ? "opacity-85" : "text-pe-tinta-suave")}>
                            <span lang="en">English Communication Skills</span>, para qualquer profissão
                          </span>
                        ) : null}
                      </span>
                    </label>
                  );
                })}
              </div>
              <span className="text-[14px] leading-5 text-pe-tinta-suave">
                Todos começam pelo inglês geral. Os cursos de cada área abrem-se a partir do nível básico (A2).
              </span>
            </fieldset>

            <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
              <legend className="mb-3 p-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">Quanto tempo por dia?</legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {METAS.map((m) => {
                  const sel = m.min === meta;
                  return (
                    <label
                      key={m.min}
                      className={cnPe(
                        "flex cursor-pointer flex-col items-center rounded-pe-md px-2 py-3 text-center has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                        sel ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border border-pe-linha hover:bg-pe-fundo-suave"
                      )}
                    >
                      <input type="radio" name="meta" value={m.min} checked={sel} onChange={() => setMeta(m.min)} className="sr-only" />
                      <span className="font-pe-titulo text-[20px] font-bold tabular-nums">{m.min} min</span>
                      <span className="text-[14px] leading-5 text-pe-tinta-suave">{m.nome}</span>
                    </label>
                  );
                })}
              </div>
              <span className="text-[14px] leading-5 text-pe-tinta-suave">Pode mudar isto nas definições.</span>
            </fieldset>

            <p className="m-0 text-pe-tinta-suave">A seguir: escolha o nível em que quer começar.</p>
            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
            <Botao
              className="self-start"
              disabled={!areaEscolhida || aGuardar}
              onClick={async () => {
                setErro(null);
                try {
                  await Promise.all([guardar({ preferences: { area: areaEscolhida! } }).unwrap(), mudarMeta(meta).unwrap()]);
                  setPasso(2);
                } catch (e) {
                  setErro(errosDoServidor(e).geral ?? "Não foi possível guardar. Tente outra vez.");
                }
              }}
            >
              {aGuardar ? "A guardar…" : "Continuar"}
            </Botao>
            {!areaEscolhida ? <span className="-mt-4 text-[14px] text-pe-tinta-suave">Escolha o que quer aprender para continuar.</span> : null}
          </>
        ) : passo === 2 || !resultado ? (
          <EscolherNivel
            aoColocar={(r, tentativa) => {
              setResultado({ r, tentativa });
              setPasso(3);
            }}
          />
        ) : (
          <Pronto r={resultado.r} tentativa={resultado.tentativa} area={areaEscolhida} />
        )}
      </main>
    </div>
  );
}

function EscolherNivel({ aoColocar }: { aoColocar: (r: ResultadoColocacao, tentativa: TentativaTeste | null) => void }) {
  const { data, isLoading, isError, refetch } = useColocacaoQuery();
  const [colocar, { isLoading: aColocar }] = useColocarMutation();
  const [escolhido, setEscolhido] = useState<NivelColocacao | null>(null);
  const [emTeste, setEmTeste] = useState<NivelDisponivel | null>(null);
  // O teste entregue, enquanto o servidor guarda o nível (ou se falhar, para tentar outra vez).
  const [entregue, setEntregue] = useState<{ nivel: NivelColocacao; t: TentativaTeste } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const aplicar = async (nivel: NivelColocacao, tentativa: TentativaTeste | null) => {
    setErro(null);
    try {
      aoColocar(await colocar(nivel).unwrap(), tentativa);
    } catch (e) {
      const n = data?.niveis.find((x) => x.nivel === nivel);
      if (testeNecessario(e) && n) {
        setEntregue(null);
        setEmTeste(n);
      } else setErro(mensagemErro(e, "Não foi possível guardar o nível. Tente outra vez."));
    }
  };

  if (entregue)
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Teste entregue</h1>
        {erro ? (
          <>
            <Aviso tipo="errado">{erro}</Aviso>
            <Botao disabled={aColocar} onClick={() => void aplicar(entregue.nivel, entregue.t)}>
              {aColocar ? "A guardar…" : "Tentar outra vez"}
            </Botao>
          </>
        ) : (
          <p className="m-0 text-pe-tinta-suave">A guardar o seu nível…</p>
        )}
      </div>
    );

  // Um teste de colocação a meio retoma-se logo (o tempo continua a contar).
  const aMeio = data?.em_curso?.perguntas ? data.em_curso : null;
  const nivelAMeio = aMeio ? data?.niveis.find((n) => n.nivel === aMeio.para) ?? null : null;
  const noTeste = emTeste ?? nivelAMeio;
  if (noTeste)
    return (
      <TesteDeColocacao
        n={noTeste}
        aMeio={aMeio}
        aoVoltar={() => setEmTeste(null)}
        aoEntregar={(t) => {
          setEntregue({ nivel: noTeste.nivel, t });
          void aplicar(noTeste.nivel, t);
        }}
      />
    );
  if (isLoading) return <Osso className="h-[420px] rounded-pe-md" />;
  if (isError || !data)
    return (
      <div className="flex flex-col items-start gap-4">
        <h1 className="m-0 text-pe-titulo-m">Não conseguimos carregar os níveis</h1>
        <Botao onClick={() => void refetch()}>Tentar outra vez</Botao>
      </div>
    );

  const sel = data.niveis.find((n) => n.nivel === escolhido) ?? null;
  // Já fez um teste de colocação há menos de 24 horas: se esse teste cobriu o nível abaixo do
  // escolhido, o servidor coloca-o pelo resultado; senão, este nível só abre com um teste novo.
  const espera = data.proxima_tentativa_em;
  const cobre = (n: NivelDisponivel) => {
    const anterior = n.niveis_teste[n.niveis_teste.length - 1];
    return !!anterior && !!data.ultima?.niveis.includes(anterior);
  };
  const semTeste = (n: NivelDisponivel) => n.pode_entrar || (!!espera && cobre(n));
  const bloqueado = (n: NivelDisponivel) => !n.pode_entrar && !!espera && !cobre(n);

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">Em que nível quer começar?</h1>
        <p className="m-0 max-w-[60ch] text-pe-tinta-suave">
          No A1 começa logo. Para outro nível, faz um teste escrito de 30 perguntas com todos os níveis abaixo do que escolheu: começa no nível a seguir ao último em que acertar {data.regras.aprovacao}%, a contar do A1.
        </p>
      </div>
      <div role="radiogroup" aria-label="Níveis" className="flex flex-col gap-2.5">
        {data.niveis.map((n) => {
          const activo = n.nivel === escolhido;
          return (
            <button
              key={n.nivel}
              type="button"
              role="radio"
              aria-checked={activo}
              onClick={() => setEscolhido(n.nivel)}
              className={cnPe(
                "flex items-start gap-4 rounded-pe-md px-4 py-3.5 text-left",
                activo ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
              )}
            >
              <span aria-hidden className={cnPe("flex size-12 shrink-0 items-center justify-center rounded-pe-fala-s font-pe-titulo text-[18px] font-bold", activo ? "bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo-forte text-pe-azul-marca")}>
                {n.nivel}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="font-semibold leading-[22px]">{n.nome}</span>
                <span className="text-[14px] leading-5 text-pe-tinta-suave">{n.descricao}</span>
                <span className={cnPe("mt-1 flex items-center gap-1.5 text-[14px] font-semibold leading-5", n.pode_entrar ? "text-pe-certo" : "text-pe-azul-marca")}>
                  {n.pode_entrar ? <Check aria-hidden className="size-4" /> : <Lock aria-hidden className="size-4" />}
                  {n.niveis_teste.length === 0
                    ? "Começa logo"
                    : n.pode_entrar
                      ? "Já tem os níveis anteriores"
                      : `Teste de ${n.perguntas} perguntas: ${n.niveis_teste.join(", ")}`}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {sel && espera && semTeste(sel) && !sel.pode_entrar ? (
        <Aviso tipo="info">
          Já fez o teste de colocação. Pode repeti-lo a partir de {dataHora(espera)}; até lá, começa no nível que esse teste mostrou.
        </Aviso>
      ) : null}
      {sel && espera && bloqueado(sel) ? (
        <Aviso tipo="info">
          O teste que fez não chega ao {sel.nivel}. Pode fazer um teste novo a partir de {dataHora(espera)}; até lá, escolha um nível até ao {data.ultima?.para}.
        </Aviso>
      ) : null}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <Botao
        className="self-start"
        disabled={!sel || aColocar || bloqueado(sel)}
        onClick={() => {
          if (!sel) return;
          if (semTeste(sel)) void aplicar(sel.nivel, null);
          else setEmTeste(sel);
        }}
      >
        {!sel ? "Escolha um nível" : aColocar ? "A guardar…" : semTeste(sel) ? (sel.pode_entrar ? `Começar no ${sel.nivel}` : "Continuar") : "Fazer o teste de colocação"}
      </Botao>
    </>
  );
}

/** O teste de colocação, aqui mesmo: regras, ecrã inteiro e as perguntas. */
function TesteDeColocacao({ n, aMeio, aoVoltar, aoEntregar }: { n: NivelDisponivel; aMeio: TentativaTeste | null; aoVoltar: () => void; aoEntregar: (t: TentativaTeste) => void }) {
  const [iniciar, { isLoading: aIniciar }] = useIniciarTesteColocacaoMutation();
  const [tentativa, setTentativa] = useState<TentativaTeste | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const aDecorrer = tentativa ?? aMeio;

  if (aDecorrer) return <Perguntas key={aDecorrer.id} t={aDecorrer} aoEntregar={aoEntregar} />;

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">Teste para começar no {n.nivel}</h1>
        <p className="m-0 max-w-[60ch] text-pe-tinta-suave">
          O teste tem perguntas de {n.niveis_teste.join(", ")}. Cada nível conta em separado: começa no nível a seguir ao último em que acertar 70%, a contar do A1. Se acertar em todos, começa no {n.nivel}.
        </p>
      </div>
      <dl className="m-0 grid w-full gap-x-8 gap-y-4 rounded-pe-fala bg-pe-fundo-suave p-6 sm:grid-cols-3">
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">perguntas de escolha</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{n.perguntas}</dd>
        </div>
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">minutos, sem pausa</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{n.minutos}</dd>
        </div>
        <div className="flex flex-col-reverse">
          <dt className="text-[14px] leading-5 text-pe-tinta-suave">certas em cada nível</dt>
          <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">70%</dd>
        </div>
      </dl>
      <Aviso tipo="info">
        O teste abre em ecrã inteiro. Se sair do ecrã (outro separador, outra janela ou outra app), a pergunta em que está é anulada e conta como errada. Só pode repetir o teste 24 horas depois.
      </Aviso>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-4">
        <Botao
          disabled={aIniciar}
          onClick={async () => {
            setErro(null);
            await entrarEcraInteiro();
            try {
              setTentativa(await iniciar(n.nivel).unwrap());
            } catch (e) {
              setErro(mensagemErro(e, "Não foi possível abrir o teste. Tente outra vez."));
            }
          }}
        >
          {aIniciar ? "A abrir o teste…" : "Começar o teste"}
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" onClick={aoVoltar}>
          Escolher outro nível
        </Botao>
      </div>
    </>
  );
}

function Pronto({ r, tentativa, area }: { r: ResultadoColocacao; tentativa: TentativaTeste | null; area: string | null }) {
  const sector = !!area && area !== GERAL;
  const nomeArea = AREAS.find((a) => a.valor === area)?.nome;
  const temBasico = r.tem_nivel_basico;
  const resultado = tentativa?.resultado ? Object.entries(tentativa.resultado) : [];

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">Começa no {r.nivel}</h1>
        {r.no_nivel_escolhido ? (
          tentativa ? <p className="m-0 text-pe-tinta-suave">Passou em todos os níveis do teste.</p> : null
        ) : (
          <p className="m-0 text-pe-tinta-suave">
            Escolheu o {r.escolhido}, mas o teste mostrou que o melhor é começar no {r.nivel}. Pode repetir o teste daqui a 24 horas para subir.
          </p>
        )}
      </div>

      {resultado.length ? (
        <ul aria-label="Resultado por nível" className="m-0 grid list-none gap-2 p-0 sm:grid-cols-4">
          {resultado.map(([nivel, x]) => (
            <li key={nivel} className={cnPe("flex flex-col rounded-pe-md px-4 py-3", x?.aprovado ? "bg-pe-certo-suave" : "bg-pe-fundo-suave")}>
              <span className="font-pe-titulo text-[18px] font-bold">{nivel}</span>
              <span className="text-[14px] leading-5 tabular-nums">
                {x?.certas} de {x?.total} certas
              </span>
              <span className="text-[14px] font-semibold leading-5">{x?.aprovado ? "Passou" : "Não passou"}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {r.curso ? (
        <section aria-labelledby="t-curso" className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-5 md:p-6">
          <span className="text-[14px] font-semibold leading-5 text-pe-tinta-suave">O seu curso</span>
          <h2 id="t-curso" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
            {r.curso.titulo}
          </h2>
          {r.inscrito ? (
            <>
              <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Já está inscrito. Comece pela primeira vídeo-aula com a professora Luena.</p>
              <div className="flex flex-wrap gap-3">
                <Botao asChild>
                  <Link href={`/user/courses/${r.curso.id}`}>Começar o curso</Link>
                </Botao>
                {r.curso_pratica ? (
                  <Botao asChild tipo="secundario">
                    <Link href="/user/laboratory/learn">Abrir o laboratório</Link>
                  </Botao>
                ) : null}
              </div>
            </>
          ) : r.motivo === "plano" ? (
            <>
              <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Este curso faz parte dos planos pagos. Escolha um plano para se inscrever.</p>
              <Botao asChild className="self-start">
                <Link href="/user/subscription">Ver os planos</Link>
              </Botao>
            </>
          ) : (
            <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Não foi possível fazer a inscrição agora. Pode inscrever-se a partir da página do curso.</p>
          )}
        </section>
      ) : (
        <Aviso tipo="info">O curso do nível {r.nivel} está a ser preparado. O seu nível ficou guardado: quando o curso abrir, aparece no seu painel.</Aviso>
      )}

      {sector && nomeArea ? (
        <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
          {temBasico
            ? `Já tem o nível básico: pode também inscrever-se nos cursos de ${nomeArea}.`
            : `Os cursos de ${nomeArea} abrem-se quando chegar ao nível básico (A2 concluído ou provado num teste).`}
        </p>
      ) : null}

      <Link href="/user/dashboard" className="min-h-11 self-start py-2.5 font-semibold text-pe-azul-marca underline-offset-[3px]">
        Ir para o painel
      </Link>
    </>
  );
}
