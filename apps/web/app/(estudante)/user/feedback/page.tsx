"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { AreaTexto, Aviso, Botao } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { NOTAS, useEnviarOpiniaoMutation, useEstadoOpiniaoQuery } from "@/src/domains/student/opiniao/api";

export default function PaginaOpiniao() {
  return (
    <Pagina className="max-w-[720px]">
      <Suspense>
        <Formulario />
      </Suspense>
    </Pagina>
  );
}

function Formulario() {
  const sp = useSearchParams();
  const { data: estado } = useEstadoOpiniaoQuery();
  // Vindo do cartão do Painel, a frase e o momento ficam no endereço; aqui só se pedem se não vierem.
  const chave = sp.get("chave") ?? (estado?.should_show_prompt ? estado.chave : null);
  const trigger = sp.get("trigger") ?? (estado?.should_show_prompt ? estado.trigger : null);
  const frase = chave && estado?.chave === chave ? estado.frase : null;

  const [nota, setNota] = useState<number | null>(null);
  const [comentario, setComentario] = useState("");
  const [publico, setPublico] = useState(false);
  const [contacto, setContacto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviada, setEnviada] = useState(false);
  const [enviar, { isLoading }] = useEnviarOpiniaoMutation();

  if (enviada)
    return (
      <div className="flex flex-col items-start gap-4 py-6">
        <CheckCircle2 aria-hidden className="size-10 text-pe-certo" />
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Obrigado pela sua opinião</h1>
        <p className="m-0 text-pe-tinta-suave">
          Lemos todas as opiniões.{publico ? " Se a escolhermos para o site, aparece com o seu primeiro nome, a inicial do apelido e a área." : ""}
        </p>
        <Botao asChild>
          <Link href="/user/dashboard">Voltar ao início</Link>
        </Botao>
      </div>
    );

  return (
    <form
      noValidate
      className="flex flex-col gap-7"
      onSubmit={async (e) => {
        e.preventDefault();
        setErro(null);
        if (!nota) return setErro("Escolha uma nota de 1 a 5.");
        try {
          await enviar({
            rating: nota,
            comment: comentario.trim(),
            trigger: trigger ?? "manual",
            context_data: chave ? { chave } : {},
            allow_public: publico && !!comentario.trim(),
            allow_contact: contacto,
          }).unwrap();
          setEnviada(true);
          window.scrollTo({ top: 0 }); // o agradecimento é mais curto do que o formulário
        } catch (er) {
          const d = (er as { data?: { non_field_errors?: string[]; detail?: string } })?.data;
          setErro(d?.non_field_errors?.[0] ?? d?.detail ?? "Não foi possível enviar. Tente outra vez.");
        }
      }}
    >
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-10">{frase ?? "Como está a correr o ProEnglish?"}</h1>
        <p className="m-0 text-pe-tinta-suave">A sua opinião ajuda-nos a melhorar as lições.</p>
      </div>

      <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
        <legend className="mb-3 p-0 font-semibold leading-[22px]">A sua nota</legend>
        <div className="grid grid-cols-5 gap-2">
          {NOTAS.map((nome, i) => {
            const n = i + 1;
            const sel = nota === n;
            return (
              <label
                key={n}
                className={cnPe(
                  "flex cursor-pointer flex-col items-center gap-1 rounded-[18px_18px_18px_0] px-1 py-3 text-center has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                  sel ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                )}
              >
                <input type="radio" name="nota" value={n} checked={sel} onChange={() => setNota(n)} className="sr-only" />
                <span className={cnPe("font-pe-titulo text-[26px] font-bold leading-8 tabular-nums", sel && "text-pe-realce")}>{n}</span>
                <span className="text-[12px] leading-4 sm:text-[13px]">{nome}</span>
              </label>
            );
          })}
        </div>
        <span className="min-h-5 text-[15px] leading-5 text-pe-tinta-suave" aria-live="polite">
          {nota ? `${nota} de 5: ${NOTAS[nota - 1].toLowerCase()}` : "1 é mau, 5 é muito bom."}
        </span>
      </fieldset>

      <AreaTexto
        rotulo="Quer contar mais? (opcional)"
        rows={5}
        maxLength={2000}
        value={comentario}
        onChange={(e) => setComentario(e.target.value)}
        placeholder="O que está a correr bem? O que mudaria?"
        ajuda={`${comentario.length} de 2000 caracteres`}
      />

      <div className="flex flex-col gap-3">
        <label className={cnPe("flex items-start gap-3 text-[15px] leading-[22px]", !comentario.trim() && "text-pe-tinta-suave")}>
          <input type="checkbox" checked={publico} disabled={!comentario.trim()} onChange={(e) => setPublico(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-pe-azul-marca" />
          <span>
            Pode mostrar a minha opinião no site, só com o primeiro nome, a inicial do apelido e a área.
            {!comentario.trim() ? " (Escreva um comentário para poder escolher.)" : ""}
          </span>
        </label>
        <label className="flex items-start gap-3 text-[15px] leading-[22px]">
          <input type="checkbox" checked={contacto} onChange={(e) => setContacto(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-pe-azul-marca" />
          <span>Podem contactar-me por email sobre esta opinião.</span>
        </label>
      </div>

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <Botao type="submit" className="self-start" disabled={isLoading}>
        {isLoading ? "A enviar…" : "Enviar opinião"}
      </Botao>
    </form>
  );
}
