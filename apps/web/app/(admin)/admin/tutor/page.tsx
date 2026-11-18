"use client";

import Link from "next/link";
import { useState } from "react";
import { Aviso, Botao, Campo, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useConfiguracaoTutorQuery, useMudarConfiguracaoTutorMutation, type ConfiguracaoTutor } from "@/src/domains/admin/administracao/tutor";

const PROVEDORES: { valor: ConfiguracaoTutor["provedor"]; nome: string; texto: string }[] = [
  { valor: "anthropic", nome: "Anthropic (Claude)", texto: "Os modelos Claude. O Haiku é o mais barato; o Sonnet conversa melhor nos níveis altos." },
  { valor: "openai", nome: "OpenAI (GPT)", texto: "Os modelos GPT, como alternativa." },
];

/**
 * Tutor de conversa: o modelo de IA que o Vapi usa e a duração máxima de cada conversa. Os minutos
 * de cada plano (por dia, por mês e do teste do gratuito) mudam-se em Planos e códigos.
 */
export default function ConfiguracaoDoTutor() {
  const { data, isLoading, isError, refetch } = useConfiguracaoTutorQuery();

  if (isLoading)
    return (
      <Pagina className="max-w-[760px] gap-6">
        <Osso className="h-10 w-2/3" />
        <Osso className="h-[320px]" />
      </Pagina>
    );
  if (isError || !data)
    return (
      <Pagina className="max-w-[760px] gap-4">
        <h1 className="m-0 text-pe-titulo-m">Não foi possível abrir a configuração do tutor</h1>
        <Botao onClick={() => void refetch()}>Tentar outra vez</Botao>
      </Pagina>
    );

  return <Formulario data={data} />;
}

function Formulario({ data }: { data: ConfiguracaoTutor }) {
  const [guardar, { isLoading: aGuardar }] = useMudarConfiguracaoTutorMutation();
  const [provedor, setProvedor] = useState<ConfiguracaoTutor["provedor"]>(data.provedor);
  const [modelo, setModelo] = useState(data.modelo);
  const [minutos, setMinutos] = useState(String(data.max_minutos_sessao));
  const [erros, setErros] = useState<Record<string, string>>({});
  const [mensagem, setMensagem] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);

  return (
    <Pagina className="max-w-[760px] gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-[38px]">Tutor de conversa</h1>
        <p className="m-0 max-w-[62ch] text-pe-tinta-suave">
          O modelo de IA que conversa com os alunos (no Vapi) e a duração máxima de cada conversa. É o recurso mais caro da plataforma: cada minuto custa cerca de US$ 0,10 a 0,15. Os minutos de cada plano mudam-se em{" "}
          <Link href="/admin/plans" className="font-semibold">
            Planos e códigos
          </Link>
          .
        </p>
      </div>

      <form
        className="flex flex-col gap-6"
        onSubmit={async (e) => {
          e.preventDefault();
          setErros({});
          setMensagem(null);
          try {
            await guardar({ provedor, modelo: modelo.trim(), max_minutos_sessao: Number(minutos) }).unwrap();
            setMensagem({ tipo: "certo", texto: "Guardado. As conversas novas já usam esta configuração." });
          } catch (x) {
            setErros(errosPorCampo(x));
            setMensagem({ tipo: "errado", texto: mensagemErro(x, "Não foi possível guardar.") });
          }
        }}
      >
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 p-0 font-pe-titulo text-[18px] font-semibold">Fornecedor</legend>
          {PROVEDORES.map((p) => (
            <label key={p.valor} className={cnPe("flex cursor-pointer items-start gap-3 rounded-pe-md border px-4 py-3", provedor === p.valor ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-pe-linha")}>
              <input
                type="radio"
                name="provedor"
                checked={provedor === p.valor}
                onChange={() => {
                  setProvedor(p.valor);
                  if (!data.sugestoes[p.valor].includes(modelo)) setModelo(data.sugestoes[p.valor][0] ?? "");
                }}
                className="mt-1 size-4 accent-pe-azul-marca"
              />
              <span className="flex flex-col">
                <span className="font-semibold">{p.nome}</span>
                <span className="text-[14px] leading-5 text-pe-tinta-suave">{p.texto}</span>
              </span>
            </label>
          ))}
          {erros.provedor ? <p className="m-0 text-[14px] text-pe-errado">{erros.provedor}</p> : null}
        </fieldset>

        <div className="flex flex-col gap-2">
          <Campo
            rotulo="Modelo"
            list="modelos-tutor"
            value={modelo}
            onChange={(e) => setModelo(e.target.value)}
            erro={erros.modelo}
            ajuda="O nome exacto do modelo no Vapi. Escolha uma sugestão ou escreva outro; teste uma conversa depois de mudar."
          />
          <datalist id="modelos-tutor">
            {data.sugestoes[provedor].map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <div className="flex flex-wrap gap-2">
            {data.sugestoes[provedor].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setModelo(m)}
                className={cnPe("min-h-9 rounded-full border px-3 text-[14px]", modelo === m ? "border-pe-azul-marca bg-pe-azul-marca text-pe-sobre-marca" : "border-pe-linha hover:bg-pe-fundo-suave")}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <Campo
          rotulo="Minutos máximos por conversa"
          inputMode="numeric"
          value={minutos}
          onChange={(e) => setMinutos(e.target.value)}
          erro={erros.max_minutos_sessao}
          ajuda="Entre 1 e 60. Uma conversa nunca passa disto, nem dos minutos que restam ao aluno no dia ou no mês."
        />

        {mensagem ? <Aviso tipo={mensagem.tipo}>{mensagem.texto}</Aviso> : null}
        <div className="flex flex-wrap items-center gap-4">
          <Botao type="submit" disabled={aGuardar}>
            {aGuardar ? "A guardar…" : "Guardar"}
          </Botao>
          {data.alterado_em ? (
            <span className="text-[14px] text-pe-tinta-suave">Alterado em {new Date(data.alterado_em).toLocaleString("pt-PT")}</span>
          ) : (
            <span className="text-[14px] text-pe-tinta-suave">Ainda com a configuração do servidor.</span>
          )}
        </div>
      </form>
    </Pagina>
  );
}
