"use client";

import { useState } from "react";
import { Download, Landmark } from "lucide-react";
import { Aviso, Botao, Campo, Escolha, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { CampoCodigo, errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { descarregarCsv } from "@/src/domains/teacher/professor/alunos";
import {
  diaMes,
  kz,
  useBancosQuery,
  useCancelarMudancaContaMutation,
  useConfirmarContaMutation,
  useGanhosQuery,
  usePedirMudancaContaMutation,
  type Ganhos,
} from "@/src/domains/teacher/professor/ganhos";

const h2 = "m-0 font-pe-titulo text-[22px] font-semibold leading-7";

export default function PaginaGanhos() {
  const { data, isError, refetch } = useGanhosQuery();
  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Ganhos" texto="Quanto recebe pelos seus cursos e quando." />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os ganhos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <>
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-72 rounded-pe-md" />
        </>
      ) : (
        <Conteudo g={data} />
      )}
    </Pagina>
  );
}

function Conteudo({ g }: { g: Ganhos }) {
  const [erro, setErro] = useState<string | null>(null);
  return (
    <>
      <Numeros
        itens={[
          { nome: "Este mês", valor: kz(g.este_mes.valor_kz), nota: `estimativa até hoje, ${diaMes(g.este_mes.ate)}` },
          { nome: "Próximo pagamento", valor: diaMes(g.proximo_pagamento.data), nota: `referente a ${g.proximo_pagamento.referente}` },
          { nome: "Total recebido", valor: kz(g.total_recebido.valor_kz), nota: g.total_recebido.desde ? `desde ${g.total_recebido.desde}` : "ainda sem pagamentos" },
          { nome: "Alunos que pagam", valor: num(g.este_mes.alunos_pagantes), nota: "estudaram nos seus cursos este mês" },
        ]}
      />

      <div className="grid gap-9 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="t-meses" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 id="t-meses" className={h2}>
              Pagamentos por mês
            </h2>
            {g.meses.length ? (
              <Botao
                tipo="secundario"
                tamanho="pequeno"
                onClick={async () => {
                  setErro(null);
                  try {
                    await descarregarCsv("/teacher/ganhos/exportar/", "ganhos.csv");
                  } catch {
                    setErro("Não foi possível exportar. Tente outra vez.");
                  }
                }}
              >
                <Download aria-hidden className="size-[18px]" />
                Exportar
              </Botao>
            ) : null}
          </div>
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          {g.meses.length ? (
            <div className="-mx-5 overflow-x-auto px-5 md:mx-0 md:px-0">
            <table className="w-full min-w-[520px] border-collapse tabular-nums">
              <caption className="sr-only">Pagamentos por mês</caption>
              <thead>
                <tr>
                  {["Mês", "Alunos", "Valor", "Pagamento", "Estado"].map((t, i) => (
                    <th key={t} scope="col" className={`border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave ${i === 1 || i === 2 ? "text-right" : "text-left"}`}>
                      {t}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {g.meses.map((m) => (
                  <tr key={m.mes}>
                    <td className="border-b border-pe-fundo-forte p-3">{m.nome}</td>
                    <td className="border-b border-pe-fundo-forte p-3 text-right">{num(m.alunos)}</td>
                    <td className="border-b border-pe-fundo-forte p-3 text-right font-semibold">{kz(m.valor_kz)}</td>
                    <td className="border-b border-pe-fundo-forte p-3">{m.estado === "pago" ? `Pago a ${diaMes(m.pago_em ?? m.pago_a)}` : `Previsto para ${diaMes(m.pago_a)}`}</td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <Etiqueta tipo={m.estado === "pago" ? "certo" : "realce"}>{m.estado === "pago" ? "Pago" : "A processar"}</Etiqueta>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda não há meses fechados. O primeiro aparece aqui no início do mês seguinte.</p>
          )}
          <p className="m-0 max-w-[68ch] text-[15px] leading-[22px] text-pe-tinta-suave">
            Todos os meses, {g.percentagem}% do que os alunos pagam pelas subscrições é dividido entre os professores, conforme o tempo que os alunos Premium e Premium Plus
            passam nos cursos de cada um. O tempo dos alunos do plano Gratuito, e de quem não pagou nada nesse mês, não conta.
            {g.regras
              ? ` Na prática, cada exercício conta ${g.regras.segundos_por_exercicio} segundos, uma vez por dia, até ${g.regras.max_pratica_min_dia} minutos por aluno e por dia; nos vídeos conta o tempo visto, até ${Math.round(g.regras.max_video_min_dia / 60)} horas por dia.`
              : ""}{" "}
            O pagamento é feito a dia {g.dia_pagamento} do mês seguinte.
          </p>
        </section>

        <Conta g={g} />
      </div>
    </>
  );
}

function Conta({ g }: { g: Ganhos }) {
  const [aberto, setAberto] = useState(false);
  const [cancelar] = useCancelarMudancaContaMutation();
  const c = g.conta;
  const p = g.alteracao_pendente;
  return (
    <section aria-labelledby="t-conta" className="flex flex-col gap-3">
      <h2 id="t-conta" className={h2}>
        Para onde vai o dinheiro
      </h2>
      {c ? (
        <dl className="m-0 flex flex-col gap-3 rounded-pe-md bg-pe-fundo-suave p-5">
          <div className="flex items-center gap-3">
            <Landmark aria-hidden className="size-6 shrink-0 text-pe-azul-marca" />
            <div className="flex flex-col">
              <dt className="sr-only">Banco</dt>
              <dd className="m-0 font-semibold">{c.banco_nome}</dd>
              <dt className="sr-only">Conta</dt>
              <dd className="m-0 text-[15px] text-pe-tinta-suave">IBAN terminado em {c.terminada_em}</dd>
            </div>
          </div>
          <div className="flex gap-2 text-[15px]">
            <dt className="text-pe-tinta-suave">Titular</dt>
            <dd className="m-0">{c.titular}</dd>
          </div>
        </dl>
      ) : (
        <Aviso tipo="info">Ainda não indicou a conta para receber. Sem ela, os pagamentos ficam à espera.</Aviso>
      )}
      {p ? (
        <Aviso tipo="neutro">
          Pediu para mudar para {p.banco_nome}, IBAN terminado em {p.terminada_em}. Falta confirmar com o código que enviámos para o seu email.{" "}
          <button type="button" onClick={() => setAberto(true)} className="font-semibold underline underline-offset-[3px]">
            Escrever o código
          </button>{" "}
          ou{" "}
          <button type="button" onClick={() => void cancelar()} className="font-semibold underline underline-offset-[3px]">
            cancelar
          </button>
          .
        </Aviso>
      ) : null}
      <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => setAberto(true)}>
        {c ? "Mudar a conta" : "Indicar a conta"}
      </Botao>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">Por segurança, a mudança só vale depois de confirmar o código enviado para o seu email.</p>
      {aberto ? <DialogoConta pendente={!!p} aoFechar={() => setAberto(false)} /> : null}
    </section>
  );
}

function DialogoConta({ pendente, aoFechar }: { pendente: boolean; aoFechar: () => void }) {
  const { data: bancos } = useBancosQuery();
  const [pedir, { isLoading: aPedir }] = usePedirMudancaContaMutation();
  const [confirmar, { isLoading: aConfirmar }] = useConfirmarContaMutation();
  const [passo, setPasso] = useState<"dados" | "codigo">(pendente ? "codigo" : "dados");
  const [banco, setBanco] = useState("");
  const [iban, setIban] = useState("");
  const [titular, setTitular] = useState("");
  const [codigo, setCodigo] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [geral, setGeral] = useState<string | null>(null);

  const ibanLimpo = iban.replace(/\s/g, "").toUpperCase();
  const ibanLegivel = ibanLimpo.replace(/(.{4})/g, "$1 ").trim();

  return (
    <Dialogo
      aberto
      aoMudar={(v) => !v && aoFechar()}
      titulo={passo === "dados" ? "Conta para receber" : "Confirmar a mudança"}
      descricao={passo === "dados" ? "Uma conta bancária em Angola, em kwanzas, em seu nome." : mensagem ?? "Escreva o código de 6 algarismos que enviámos para o seu email."}
    >
      {passo === "dados" ? (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setGeral(null);
            const er: Record<string, string> = {};
            if (!banco) er.banco = "Escolha o banco.";
            if (!/^AO\d{23}$/.test(ibanLimpo)) er.iban = "O IBAN angolano começa por AO06 e tem 25 caracteres.";
            if (titular.trim().length < 3) er.titular = "Escreva o nome do titular, como está no banco.";
            setErros(er);
            if (Object.keys(er).length) return;
            try {
              const r = await pedir({ banco, iban: ibanLimpo, titular: titular.trim() }).unwrap();
              setMensagem(r.mensagem);
              setPasso("codigo");
            } catch (x) {
              setErros(errosPorCampo(x));
              setGeral(mensagemErro(x, "Não foi possível guardar. Tente outra vez."));
            }
          }}
        >
          <Escolha rotulo="Banco" value={banco} onChange={(e) => setBanco(e.target.value)} erro={erros.banco}>
            <option value="">Escolha o banco</option>
            {bancos?.map((b) => (
              <option key={b.valor} value={b.valor}>
                {b.nome}
              </option>
            ))}
          </Escolha>
          <Campo
            rotulo="IBAN"
            value={ibanLegivel}
            onChange={(e) => setIban(e.target.value)}
            placeholder="AO06 0000 0000 0000 0000 0000 0"
            autoComplete="off"
            spellCheck={false}
            maxLength={32}
            erro={erros.iban}
          />
          <Campo rotulo="Titular da conta" value={titular} onChange={(e) => setTitular(e.target.value)} autoComplete="name" erro={erros.titular} />
          {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
          <Botao type="submit" larguraTotal disabled={aPedir}>
            {aPedir ? "A enviar o código…" : "Continuar"}
          </Botao>
        </form>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setGeral(null);
            if (codigo.length !== 6) return setErros({ codigo: "Escreva os 6 algarismos." });
            setErros({});
            try {
              await confirmar(codigo).unwrap();
              aoFechar();
            } catch (x) {
              setErros({ codigo: mensagemErro(x, "Código errado. Tente outra vez.") });
            }
          }}
        >
          <CampoCodigo valor={codigo} aoMudar={setCodigo} erro={erros.codigo} autoFocus />
          <Botao type="submit" larguraTotal disabled={aConfirmar}>
            {aConfirmar ? "A confirmar…" : "Confirmar a conta"}
          </Botao>
        </form>
      )}
    </Dialogo>
  );
}
