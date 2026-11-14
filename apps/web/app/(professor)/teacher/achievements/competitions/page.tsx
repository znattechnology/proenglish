"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Campo, Escolha, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { CabecaConquistas } from "@/components/pe/professor/fala/CabecaConquistas";
import { cnPe } from "@/lib/pe";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { diaMesCurto, mensagemErro } from "@/src/domains/student/subscricao/api";
import { num, useCursosQuery } from "@/src/domains/teacher/professor/api";
import {
  CONTA,
  PREMIO,
  useApagarCompeticaoMutation,
  useClassificacaoQuery,
  useCompeticoesQuery,
  useCriarCompeticaoMutation,
  type Competicao,
  type NovaCompeticao,
} from "@/src/domains/teacher/professor/fala";

const dia = (iso: string) => diaMesCurto(new Date(`${iso.slice(0, 10)}T12:00:00`));
const ESTADO = { activa: { nome: "Activa", tipo: "certo" }, agendada: { nome: "Agendada", tipo: "realce" }, terminada: { nome: "Terminada", tipo: "neutra" } } as const;

export default function Competicoes() {
  const { data, isError, refetch } = useCompeticoesQuery();
  const [nova, setNova] = useState(false);
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const lista = data?.resultados ?? [];
  const actual = lista.find((c) => c.id === escolhida) ?? lista.find((c) => c.estado === "activa") ?? lista[0];
  const n = data?.numeros;

  return (
    <Pagina className="gap-7">
      <CabecaConquistas activo="Competições" texto="Competições entre os alunos dos seus cursos, com datas suas. Os alunos inscritos entram automaticamente.">
        <Botao tamanho="medio" onClick={() => setNova(true)}>
          <Plus aria-hidden className="size-5" />
          Nova competição
        </Botao>
      </CabecaConquistas>

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar as competições.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data || !n ? (
        <Osso className="h-72 rounded-pe-md" />
      ) : (
        <>
          <Numeros
            itens={[
              { nome: "Competições activas", valor: num(n.activas), nota: n.terminam_esta_semana ? `${n.terminam_esta_semana} termina${n.terminam_esta_semana === 1 ? "" : "m"} esta semana` : "nenhuma termina esta semana" },
              { nome: "Alunos a participar", valor: num(n.participantes), nota: n.pct_activos == null ? undefined : `${Math.round(n.pct_activos)}% praticaram esta semana` },
              { nome: "Média de pontos", valor: num(n.media_pontos), nota: "por participante, esta semana" },
              { nome: "Média de dias seguidos", valor: n.media_dias_seguidos == null ? "–" : n.media_dias_seguidos.toLocaleString("pt-PT", { maximumFractionDigits: 1 }), nota: "dos participantes" },
            ]}
          />
          {lista.length ? (
            <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <ul className="m-0 flex list-none flex-col gap-3 p-0">
                {lista.map((c) => (
                  <CartaoCompeticao key={c.id} c={c} activa={actual?.id === c.id} aoVer={() => setEscolhida(c.id)} />
                ))}
              </ul>
              {actual ? <Classificacao c={actual} /> : null}
            </div>
          ) : (
            <div className="flex max-w-[640px] flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
              <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Crie a primeira competição</h2>
              <p className="m-0 text-pe-tinta-suave">Uma semana a contar lições ou um mês a contar minutos de conversa. Os primeiros lugares recebem um certificado de mérito ou uma medalha.</p>
              <Botao tamanho="pequeno" onClick={() => setNova(true)}>
                Nova competição
              </Botao>
            </div>
          )}
        </>
      )}
      {nova ? <DialogoNova aoFechar={() => setNova(false)} /> : null}
    </Pagina>
  );
}

function CartaoCompeticao({ c, activa, aoVer }: { c: Competicao; activa: boolean; aoVer: () => void }) {
  const [remover, { isLoading }] = useApagarCompeticaoMutation();
  const [cancelar, setCancelar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  return (
    <li className={cnPe("flex flex-col gap-3 rounded-pe-md border p-4", activa ? "border-2 border-pe-azul-marca" : "border-pe-linha")}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col">
          <span className="font-pe-titulo text-[18px] font-semibold leading-6">{c.nome}</span>
          <span className="text-pe-legenda text-pe-tinta-suave">{c.todos_os_cursos ? "Todos os seus cursos" : c.cursos.map((x) => x.titulo).join(", ")}</span>
        </div>
        <Etiqueta tipo={ESTADO[c.estado].tipo}>{ESTADO[c.estado].nome}</Etiqueta>
      </div>
      <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-2 text-[15px] sm:grid-cols-4">
        {[
          ["Conta", CONTA[c.conta].nome],
          ["Período", `${dia(c.inicio)} a ${dia(c.fim)}`],
          ["Participantes", num(c.participantes)],
          ["Prémio", `${PREMIO[c.premio]} para ${c.premio_lugares === 1 ? "o 1.º" : `os ${c.premio_lugares} primeiros`}`],
        ].map(([k, v]) => (
          <div key={k} className="flex flex-col">
            <dt className="text-pe-legenda text-pe-tinta-suave">{k}</dt>
            <dd className="m-0">{v}</dd>
          </div>
        ))}
      </dl>
      {c.estado === "activa" ? <BarraProgresso valor={c.tempo_decorrido} rotulo={`Tempo decorrido: ${Math.round(c.tempo_decorrido)}%`} /> : null}
      <div className="flex flex-wrap gap-3">
        {c.estado !== "agendada" ? (
          <Botao tipo="ligacao" tamanho="pequeno" onClick={aoVer} aria-pressed={activa}>
            Ver classificação
          </Botao>
        ) : null}
        {c.minha && c.estado === "agendada" ? (
          <Botao tipo="ligacao" tamanho="pequeno" className="text-pe-errado hover:text-pe-errado" onClick={() => setCancelar(true)}>
            Cancelar competição
          </Botao>
        ) : null}
      </div>
      <Dialogo aberto={cancelar} aoMudar={setCancelar} titulo={`Cancelar "${c.nome}"?`} descricao="A competição ainda não começou. É apagada e os alunos não recebem nenhum aviso.">
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setCancelar(false)}>
            Manter
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={isLoading}
            onClick={async () => {
              setErro(null);
              try {
                await remover(c.id).unwrap();
                setCancelar(false);
              } catch (x) {
                setErro(mensagemErro(x, "Não foi possível cancelar a competição."));
              }
            }}
          >
            Cancelar competição
          </Botao>
        </div>
      </Dialogo>
    </li>
  );
}

function Classificacao({ c }: { c: Competicao }) {
  const { data, isError } = useClassificacaoQuery(c.id, { skip: c.estado === "agendada" });
  return (
    <section aria-labelledby="t-class" className="flex flex-col gap-3 xl:sticky xl:top-6">
      <h2 id="t-class" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
        Classificação: {c.nome}
      </h2>
      {c.estado === "agendada" ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Começa a {dia(c.inicio)}.</p>
      ) : isError ? (
        <Aviso tipo="errado">Não conseguimos carregar a classificação.</Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !data.linhas.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda ninguém pontuou.</p>
      ) : (
        <table className="w-full border-collapse tabular-nums">
          <caption className="sr-only">Classificação</caption>
          <thead>
            <tr>
              {["Lugar", "Aluno", CONTA[data.conta].unidade, "Pontos"].map((t, i) => (
                <th key={t} scope="col" className={cnPe("border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave", i >= 2 ? "text-right" : "text-left")}>
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.linhas.map((l) => (
              <tr key={l.aluno_id} className={l.lugar <= c.premio_lugares && l.valor > 0 ? "bg-pe-realce-suave" : undefined}>
                <td className="border-b border-pe-fundo-forte p-3 font-semibold">{l.lugar}</td>
                <td className="border-b border-pe-fundo-forte p-3">{l.nome}</td>
                <td className="border-b border-pe-fundo-forte p-3 text-right">{num(l.valor)}</td>
                <td className="border-b border-pe-fundo-forte p-3 text-right">{num(l.pontos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function hojeMais(dias: number) {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function DialogoNova({ aoFechar }: { aoFechar: () => void }) {
  const { data: video } = useCursosQuery({ tipo: "video", estado: "publicado" });
  const { data: pratica } = useCursosQuery({ tipo: "pratica", estado: "publicado" });
  const cursos = [...(pratica?.resultados ?? []), ...(video?.resultados ?? [])];
  const [criar, { isLoading }] = useCriarCompeticaoMutation();
  const [v, setV] = useState<NovaCompeticao>({ nome: "", cursos: [], conta: "licoes", inicio: hojeMais(1), fim: hojeMais(7), premio: "certificado_merito", premio_lugares: 3 });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const muda = (p: Partial<NovaCompeticao>) => setV((x) => ({ ...x, ...p }));

  return (
    <Dialogo aberto aoMudar={(x) => !x && aoFechar()} titulo="Nova competição" descricao="Os alunos inscritos nos cursos escolhidos entram automaticamente e recebem um aviso quando começa." largura={600}>
      <form
        noValidate
        className="-mx-1 flex max-h-[min(64vh,640px)] flex-col gap-4 overflow-y-auto px-1 pb-1"
        onSubmit={async (e) => {
          e.preventDefault();
          setGeral(null);
          const er: Record<string, string> = {};
          if (v.nome.trim().length < 3) er.nome = "Escreva o nome da competição.";
          if (v.fim < v.inicio) er.fim = "O fim tem de ser depois do início.";
          setErros(er);
          if (Object.keys(er).length) return;
          try {
            await criar({ ...v, nome: v.nome.trim() }).unwrap();
            aoFechar();
          } catch (x) {
            setErros(errosPorCampo(x));
            setGeral(mensagemErro(x, "Não foi possível criar a competição."));
          }
        }}
      >
        <Campo rotulo="Nome" value={v.nome} maxLength={60} onChange={(e) => muda({ nome: e.target.value })} erro={erros.nome} placeholder="Semana da segurança" />
        <fieldset className="m-0 flex flex-col gap-1.5 border-0 p-0">
          <legend className="mb-1.5 p-0 text-pe-rotulo">Cursos</legend>
          <label className="flex min-h-10 items-center gap-2">
            <input type="checkbox" checked={!v.cursos.length} onChange={() => muda({ cursos: [] })} className="size-5 accent-pe-azul-marca" />
            Todos os meus cursos publicados
          </label>
          {cursos.map((c) => (
            <label key={c.id} className="flex min-h-10 items-center gap-2">
              <input
                type="checkbox"
                checked={v.cursos.includes(c.id)}
                onChange={(e) => muda({ cursos: e.target.checked ? [...v.cursos, c.id] : v.cursos.filter((x) => x !== c.id) })}
                className="size-5 accent-pe-azul-marca"
              />
              {c.tipo === "pratica" ? "Prática: " : ""}
              {c.titulo}
            </label>
          ))}
          {erros.cursos ? <p className="m-0 text-pe-legenda font-semibold text-pe-errado">{erros.cursos}</p> : null}
        </fieldset>
        <Escolha rotulo="O que conta" value={v.conta} onChange={(e) => muda({ conta: e.target.value as NovaCompeticao["conta"] })} erro={erros.conta}>
          {(Object.keys(CONTA) as NovaCompeticao["conta"][]).map((k) => (
            <option key={k} value={k}>
              {CONTA[k].nome}
            </option>
          ))}
        </Escolha>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Começa a" type="date" min={hojeMais(0)} value={v.inicio} onChange={(e) => muda({ inicio: e.target.value })} erro={erros.inicio} />
          <Campo rotulo="Termina a" type="date" min={v.inicio} value={v.fim} onChange={(e) => muda({ fim: e.target.value })} erro={erros.fim} ajuda="No máximo 31 dias." />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Escolha rotulo="Prémio" value={v.premio} onChange={(e) => muda({ premio: e.target.value as NovaCompeticao["premio"] })}>
            <option value="certificado_merito">Certificado de mérito</option>
            <option value="medalha">Medalha no perfil</option>
          </Escolha>
          <Escolha rotulo="Para quantos" value={v.premio_lugares} onChange={(e) => muda({ premio_lugares: Number(e.target.value) })}>
            {[1, 3, 5, 10].map((k) => (
              <option key={k} value={k}>
                {k === 1 ? "O 1.º lugar" : `Os ${k} primeiros`}
              </option>
            ))}
          </Escolha>
        </div>
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">Prémios em meses de plano só podem ser dados pela equipa ProEnglish.</p>
        {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" tamanho="medio" disabled={isLoading}>
            {isLoading ? "A criar…" : "Criar competição"}
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
