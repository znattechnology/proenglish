"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BookOpen, Check, Laptop, Landmark, Scale, Stethoscope, Briefcase, Fuel, Globe } from "lucide-react";
import { Aviso, Botao, Logo, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { useCatalogoCursosQuery } from "@/src/domains/student/inicio/api";
import { useCursosPraticaQuery, useEscolherCursoMutation } from "@/src/domains/student/laboratorio/api";
import { AREAS, NIVEIS, errosDoServidor, useGuardarPerfilMutation, useMetaQuery, useMudarMetaMutation, usePerfilQuery, type Nivel } from "@/src/domains/student/perfil/api";

const ICONES: Record<string, React.ComponentType<{ className?: string }>> = {
  "Industry English": Fuel,
  "Financial English": Landmark,
  "Business English": Briefcase,
  "Medical English": Stethoscope,
  "Legal English": Scale,
  "Technical English": Laptop,
  "General English": Globe,
};

const METAS = [
  { min: 5, nome: "Leve" },
  { min: 10, nome: "Normal" },
  { min: 15, nome: "Sério" },
  { min: 20, nome: "Intenso" },
];

/** 5 perguntas, da mais fácil à mais difícil (A1 a C1), em frases do trabalho. */
const PERGUNTAS: { frase: [string, string]; opcoes: string[]; certa: number }[] = [
  { frase: ["I ", " an engineer at the refinery."], opcoes: ["am", "is", "are"], certa: 0 },
  { frase: ["Yesterday we ", " the report to the manager."], opcoes: ["send", "sent", "sending"], certa: 1 },
  { frase: ["If the valve ", ", we will stop the line."], opcoes: ["leaks", "will leak", "leaked"], certa: 0 },
  { frase: ["The audit, ", " was carried out last month, found two issues."], opcoes: ["who", "what", "which"], certa: 2 },
  { frase: ["Had we known about the delay, we ", " the client earlier."], opcoes: ["would warn", "would have warned", "will warn"], certa: 1 },
];

const nivelPelaNota = (certas: number): Nivel => (certas <= 1 ? "Beginner" : certas <= 3 ? "Intermediate" : "Advanced");
const nomeNivel = (n: Nivel) => NIVEIS.find((x) => x.valor === n)?.nome ?? n;

/**
 * Primeira entrada: área e meta diária, 5 perguntas para o nível e a primeira lição.
 * Ocupa o ecrã inteiro, sem a navegação, como as lições.
 */
export default function PrimeiraEntrada() {
  const { data: perfil } = usePerfilQuery();
  const [passo, setPasso] = useState<1 | 2 | 3>(1);
  const [area, setArea] = useState<string | null>(null);
  const { data: metaGuardada } = useMetaQuery();
  const [metaEscolhida, setMeta] = useState<number | null>(null);
  const meta = metaEscolhida ?? metaGuardada?.daily_goal_minutes ?? 10;
  const [nivel, setNivel] = useState<Nivel | null>(null);
  const [guardar, { isLoading: aGuardar }] = useGuardarPerfilMutation();
  const [mudarMeta] = useMudarMetaMutation();
  const [erro, setErro] = useState<string | null>(null);
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
              <legend className="mb-3 p-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">Em que área trabalha?</legend>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {AREAS.map((a) => {
                  const Icone = ICONES[a.valor] ?? BookOpen;
                  const sel = a.valor === areaEscolhida;
                  return (
                    <label
                      key={a.valor}
                      className={cnPe(
                        "flex min-h-[88px] cursor-pointer flex-col justify-between gap-2 rounded-pe-md p-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                        sel ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                      )}
                    >
                      <input type="radio" name="area" value={a.valor} checked={sel} onChange={() => setArea(a.valor)} className="sr-only" />
                      <Icone aria-hidden className={cnPe("size-6", sel ? "text-pe-realce" : "text-pe-azul-marca")} />
                      <span className="font-semibold leading-[22px]">{a.nome}</span>
                    </label>
                  );
                })}
              </div>
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

            <p className="m-0 text-pe-tinta-suave">A seguir: 5 perguntas rápidas para saber o seu nível. Depois começa a primeira lição.</p>
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
            {!areaEscolhida ? <span className="-mt-4 text-[14px] text-pe-tinta-suave">Escolha a área para continuar.</span> : null}
          </>
        ) : passo === 2 ? (
          <Teste
            aoTerminar={async (n) => {
              setErro(null);
              try {
                await guardar({ preferences: { nivel: n, acolhimento: "concluido" } }).unwrap();
                setNivel(n);
                setPasso(3);
              } catch (e) {
                setErro(errosDoServidor(e).geral ?? "Não foi possível guardar. Tente outra vez.");
              }
            }}
            erro={erro}
          />
        ) : (
          <Pronto area={areaEscolhida} nivel={nivel ?? "Intermediate"} />
        )}
      </main>
    </div>
  );
}

function Teste({ aoTerminar, erro }: { aoTerminar: (n: Nivel) => void; erro: string | null }) {
  const [i, setI] = useState(0);
  // Uma resposta por pergunta: carregar outra vez na última (se gravar falhou) não conta a dobrar.
  const [respostas, setRespostas] = useState<boolean[]>([]);
  const [escolha, setEscolha] = useState<number | null>(null);
  const [escolherAMao, setEscolherAMao] = useState(false);
  const p = PERGUNTAS[i];
  const ultima = i === PERGUNTAS.length - 1;

  const seguinte = (acertou: boolean) => {
    const novas = [...respostas];
    novas[i] = acertou;
    setRespostas(novas);
    setEscolha(null);
    if (ultima) aoTerminar(nivelPelaNota(novas.filter(Boolean).length));
    else setI(i + 1);
  };

  if (escolherAMao)
    return (
      <>
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Qual é o seu nível de inglês?</h1>
        <div className="flex flex-col gap-2.5">
          {NIVEIS.map((n) => (
            <Botao key={n.valor} tipo="secundario" larguraTotal className="justify-start" onClick={() => aoTerminar(n.valor)}>
              {n.nome}
            </Botao>
          ))}
        </div>
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <button type="button" onClick={() => setEscolherAMao(false)} className="min-h-11 self-start bg-transparent px-0 font-semibold text-pe-azul-marca underline underline-offset-[3px]">
          Fazer as perguntas
        </button>
      </>
    );

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Complete a frase</h1>
        <p className="m-0 text-pe-tinta-suave">
          Pergunta {i + 1} de {PERGUNTAS.length}. Não há problema em errar: serve só para escolher por onde começa.
        </p>
      </div>
      <p lang="en" className="pe-sobre-marca m-0 rounded-[28px_28px_28px_0] bg-pe-azul-marca px-6 py-6 font-pe-titulo text-[24px] font-light italic leading-[34px] text-pe-sobre-marca md:text-[28px] md:leading-[40px]">
        {p.frase[0]}
        <span className="mx-1 inline-block min-w-[3.5em] rounded-[2px] border-b-2 border-pe-realce px-1 text-center font-semibold not-italic">{escolha === null ? " " : p.opcoes[escolha]}</span>
        {p.frase[1]}
      </p>
      <div role="radiogroup" aria-label="Opções" className="grid gap-2.5 sm:grid-cols-3">
        {p.opcoes.map((o, k) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={escolha === k}
            onClick={() => setEscolha(k)}
            lang="en"
            className={cnPe(
              "flex min-h-12 items-center justify-center gap-2 rounded-pe-sm px-4 text-[17px] font-semibold",
              escolha === k ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo hover:bg-pe-fundo-suave"
            )}
          >
            {escolha === k ? <Check aria-hidden className="size-4" /> : null}
            {o}
          </button>
        ))}
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-4">
        <Botao disabled={escolha === null} onClick={() => seguinte(escolha === p.certa)}>
          {ultima ? "Ver o meu nível" : "Seguinte"}
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" onClick={() => seguinte(false)}>
          Não sei
        </Botao>
      </div>
      <button type="button" onClick={() => setEscolherAMao(true)} className="min-h-11 self-start bg-transparent px-0 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]">
        Já sei o meu nível
      </button>
    </>
  );
}

function Pronto({ area, nivel }: { area: string | null; nivel: Nivel }) {
  const router = useRouter();
  const { data: catalogo, isLoading: aCarregarVideo } = useCatalogoCursosQuery(area ? { categoria: area } : undefined);
  const { data: praticas, isLoading: aCarregarPratica } = useCursosPraticaQuery();
  const [escolher, { isLoading: aEscolher }] = useEscolherCursoMutation();
  const [erro, setErro] = useState<string | null>(null);

  const daArea = (praticas ?? []).filter((c) => c.category === area);
  const pratica = daArea.find((c) => c.level === nivel) ?? daArea[0] ?? (praticas ?? [])[0];
  const videos = catalogo?.cursos ?? [];
  const video = videos.find((c) => c.level === nivel) ?? videos[0];

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">O seu nível: {nomeNivel(nivel)}</h1>
        <p className="m-0 text-pe-tinta-suave">Escolhemos o curso por onde começar. Pode mudar de nível e de área nas definições.</p>
      </div>

      {aCarregarPratica ? (
        <Osso className="h-[140px] rounded-pe-md" />
      ) : pratica ? (
        <section aria-labelledby="t-pratica" className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-5 md:p-6">
          <span className="text-[14px] font-semibold leading-5 text-pe-tinta-suave">Laboratório de prática</span>
          <h2 id="t-pratica" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
            {pratica.title}
          </h2>
          <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Lições de 5 minutos com exercícios de ouvir, falar e escrever.</p>
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <Botao
            className="self-start"
            disabled={aEscolher}
            onClick={async () => {
              setErro(null);
              try {
                await escolher(pratica.id).unwrap();
                router.push("/user/laboratory/learn");
              } catch {
                setErro("Não foi possível abrir o curso. Tente outra vez.");
              }
            }}
          >
            {aEscolher ? "A preparar…" : "Começar a primeira lição"}
          </Botao>
        </section>
      ) : null}

      {aCarregarVideo ? null : video ? (
        <section aria-labelledby="t-video" className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-5 md:p-6">
          <span className="text-[14px] font-semibold leading-5 text-pe-tinta-suave">Curso em vídeo da sua área</span>
          <h2 id="t-video" className="m-0 text-[18px] font-semibold leading-6">
            {video.title}
          </h2>
          <Link href={`/user/courses/${video.courseId}`} className="self-start font-semibold text-pe-azul-marca underline-offset-[3px]">
            Ver o curso
          </Link>
        </section>
      ) : null}

      <Link href="/user/dashboard" className="min-h-11 self-start py-2.5 font-semibold text-pe-azul-marca underline-offset-[3px]">
        Ir para o painel
      </Link>
    </>
  );
}
