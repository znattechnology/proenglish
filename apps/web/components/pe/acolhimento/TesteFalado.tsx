"use client";

import { useState } from "react";
import { Loader2, Mic } from "lucide-react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { Viva } from "@/components/pe/licao/ConversaCurta";
import { cnPe } from "@/lib/pe";
import { DESCRICAO_NIVEL, NOME_NIVEL, eNivel, type NivelCefr } from "@/src/domains/shared/niveis";
import { erroConversa, useComecarDiagnosticoMutation, useDiagnosticoQuery, useLazyResultadoDiagnosticoQuery, type ResultadoDiagnostico } from "@/src/domains/student/conversa/api";
import type { ConversaLicao } from "@/src/domains/student/laboratorio/api";

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaLicao } | { tipo: "a_avaliar" } | { tipo: "resultado"; r: ResultadoDiagnostico } | { tipo: "sem_resultado"; mensagem: string };

const COMPETENCIAS: { chave: "falar" | "ouvir" | "gramatica" | "vocabulario"; nome: string }[] = [
  { chave: "falar", nome: "Falar" },
  { chave: "ouvir", nome: "Perceber" },
  { chave: "vocabulario", nome: "Vocabulário" },
  { chave: "gramatica", nome: "Gramática" },
];

/** O que cada nível quer dizer, por competência, quando o tutor não deu uma explicação. */
const POR_COMPETENCIA: Record<string, Record<NivelCefr, string>> = {
  ouvir: {
    A1: "Percebe perguntas muito simples, ditas devagar.",
    A2: "Percebe perguntas simples sobre si e o trabalho.",
    B1: "Percebe o essencial de uma conversa de trabalho clara.",
    B2: "Acompanha reuniões e conversas a ritmo normal.",
    C1: "Percebe quase tudo, mesmo com expressões e sotaques.",
    C2: "Percebe tudo, como um falante nativo.",
  },
  gramatica: {
    A1: "Frases muito curtas, com erros frequentes.",
    A2: "Frases simples; os tempos do passado ainda falham.",
    B1: "Frases correctas no dia a dia, com alguns erros.",
    B2: "Usa estruturas variadas com poucos erros.",
    C1: "Frases complexas quase sempre correctas.",
    C2: "Gramática precisa em qualquer situação.",
  },
  vocabulario: {
    A1: "Palavras básicas do dia a dia.",
    A2: "Palavras comuns do trabalho e das rotinas.",
    B1: "Vocabulário suficiente para falar do seu trabalho.",
    B2: "Vocabulário variado da sua área.",
    C1: "Vocabulário rico e preciso, com expressões.",
    C2: "Vocabulário de falante nativo.",
  },
};

function explicacao(chave: string, nivel: NivelCefr, r: ResultadoDiagnostico) {
  const dada = r.explicacoes[chave as keyof ResultadoDiagnostico["explicacoes"]];
  if (dada) return dada;
  if (chave === "falar") return `${DESCRICAO_NIVEL[nivel]}.`;
  return POR_COMPETENCIA[chave]?.[nivel] ?? "";
}

function microfonePossivel() {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

/**
 * Teste de nível falado da primeira entrada: 3 a 4 minutos de conversa com o tutor, que começa
 * fácil e vai subindo. Não gasta os minutos de conversa do plano. Sem microfone, sem tutor ou
 * quando o aluno prefere, passa para as perguntas escritas (`aoPreferirPerguntas`).
 */
export function TesteFalado({ aoTerminar, aoPreferirPerguntas, erro }: { aoTerminar: (n: NivelCefr) => void; aoPreferirPerguntas: () => void; erro: string | null }) {
  const { data: estado, isLoading, isError } = useDiagnosticoQuery();
  const [comecar, { isLoading: aComecar }] = useComecarDiagnosticoMutation();
  const [lerResultado] = useLazyResultadoDiagnosticoQuery();
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [erroInicio, setErroInicio] = useState<string | null>(null);
  const semMicrofone = !microfonePossivel();
  const minutos = Math.round((estado?.max_segundos ?? 240) / 60);

  const abrir = async () => {
    setErroInicio(null);
    try {
      const d = await comecar().unwrap();
      setFase({ tipo: "viva", dados: d });
    } catch (e) {
      setErroInicio(erroConversa(e, "Não foi possível ligar ao tutor agora."));
    }
  };

  const terminou = async (id: string) => {
    setFase({ tipo: "a_avaliar" });
    try {
      const r = await lerResultado(id).unwrap();
      if (r.avaliado && eNivel(r.nivel)) setFase({ tipo: "resultado", r });
      else
        setFase({
          tipo: "sem_resultado",
          mensagem: r.estado === "nao_ligou" ? "A chamada não chegou a ligar." : "Não ouvimos respostas suficientes para dar um nível.",
        });
    } catch {
      setFase({ tipo: "sem_resultado", mensagem: "Não conseguimos calcular o resultado." });
    }
  };

  const perguntas = (
    <Botao tipo="ligacao" tamanho="medio" className="self-start" onClick={aoPreferirPerguntas}>
      Prefiro responder a perguntas
    </Botao>
  );

  if (fase.tipo === "viva")
    return (
      <>
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Converse com o tutor</h1>
          <p className="m-0 text-pe-tinta-suave">Responda com calma e diga o máximo que conseguir. As perguntas vão ficando mais difíceis: é normal.</p>
        </div>
        <Viva dados={fase.dados} frases={[]} aoTerminar={(r) => void terminou(r.id)} aoSaltar={aoPreferirPerguntas} />
      </>
    );

  if (fase.tipo === "a_avaliar")
    return (
      <div role="status" className="flex flex-col items-start gap-4 py-6">
        <Loader2 aria-hidden className="size-8 text-pe-azul-marca motion-safe:animate-spin" />
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8">A ouvir o que disse…</h1>
        <p className="m-0 text-pe-tinta-suave">Estamos a calcular o seu nível. Demora alguns segundos.</p>
      </div>
    );

  if (fase.tipo === "resultado") return <Resultado r={fase.r} erro={erro} aoContinuar={() => aoTerminar(fase.r.nivel as NivelCefr)} />;

  if (fase.tipo === "sem_resultado")
    return (
      <>
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Ainda sem nível</h1>
        <Aviso tipo="neutro">{fase.mensagem} Pode tentar outra vez ou responder a 5 perguntas escritas.</Aviso>
        <div className="flex flex-wrap items-center gap-3">
          <Botao onClick={() => setFase({ tipo: "inicio" })}>Tentar outra vez</Botao>
          {perguntas}
        </div>
      </>
    );

  const indisponivel = isError ? "O teste falado não está disponível agora." : estado && !estado.disponivel ? `Já fez ${estado.limite} testes falados nos últimos 30 dias.` : semMicrofone ? "Este browser não deixa usar o microfone." : null;

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">Qual é o seu nível a falar?</h1>
        <p className="m-0 max-w-[60ch] text-pe-tinta-suave">
          Uma conversa de {minutos} minutos com o tutor, em inglês. Começa com perguntas fáceis sobre si e vai subindo: o seu trabalho, um problema que resolveu, uma opinião. No fim mostramos o seu nível em cada competência.
        </p>
      </div>
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-[15px] leading-[22px]">
        <li>Não gasta os minutos de conversa do seu plano.</li>
        <li>Não há respostas erradas: o tutor não corrige nem dá notas durante a conversa.</li>
        <li>A conversa não é gravada. Guardamos só o texto do que disse.</li>
      </ul>
      {isLoading ? <Osso className="h-12 w-64 rounded-pe-sm" /> : indisponivel ? <Aviso tipo="neutro">{indisponivel} Responda a 5 perguntas escritas para saber o seu nível.</Aviso> : null}
      {erroInicio ? <Aviso tipo="errado">{erroInicio} Pode responder às perguntas escritas.</Aviso> : null}
      <div className="flex flex-wrap items-center gap-3">
        {!indisponivel && !isLoading ? (
          <Botao onClick={() => void abrir()} disabled={aComecar}>
            {aComecar ? <Loader2 aria-hidden className="motion-safe:animate-spin" /> : <Mic aria-hidden />}
            Começar a conversa
          </Botao>
        ) : indisponivel ? (
          <Botao onClick={aoPreferirPerguntas}>Responder a perguntas</Botao>
        ) : null}
        {!indisponivel ? perguntas : null}
      </div>
    </>
  );
}

function Resultado({ r, erro, aoContinuar }: { r: ResultadoDiagnostico; erro: string | null; aoContinuar: () => void }) {
  const nivel = r.nivel as NivelCefr;
  return (
    <>
      <section aria-labelledby="t-nivel-fala" className="pe-sobre-marca flex flex-col gap-1 rounded-[28px_28px_28px_0] bg-pe-azul-marca px-6 py-6 text-pe-sobre-marca md:px-8">
        <h1 id="t-nivel-fala" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
          O seu nível de fala: <span className="whitespace-nowrap">{nivel}</span>
        </h1>
        <p className="m-0 font-pe-titulo text-[17px] font-light italic leading-[26px]">
          {NOME_NIVEL[nivel]}. {DESCRICAO_NIVEL[nivel]}.
        </p>
      </section>

      <ul aria-label="Nível por competência" className="m-0 grid list-none gap-x-6 p-0 sm:grid-cols-2">
        {COMPETENCIAS.map(({ chave, nome }) => {
          const n = r.niveis?.[chave];
          if (!eNivel(n)) return null;
          return (
            <li key={chave} className="flex items-start gap-3 border-b border-pe-fundo-forte py-3">
              <span className={cnPe("flex h-9 w-12 shrink-0 items-center justify-center rounded-pe-sm font-pe-titulo text-[17px] font-bold", n === nivel ? "bg-pe-fundo-suave text-pe-azul-marca" : "bg-pe-fundo-forte text-pe-tinta")}>{n}</span>
              <span className="flex min-w-0 flex-col">
                <span className="font-semibold leading-[22px]">{nome}</span>
                <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{explicacao(chave, n, r)}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">O tutor e os cursos passam a usar este nível. Vai subindo à medida que conversa.</p>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <Botao className="self-start" onClick={aoContinuar}>
        Ver por onde começar
      </Botao>
    </>
  );
}
