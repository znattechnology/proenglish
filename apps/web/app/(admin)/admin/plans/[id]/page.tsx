"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Aviso, Botao, Campo, Interruptor, Osso } from "@/components/pe";
import { AreaTexto } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { kz, mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { useMudarPlanoMutation, usePlanosQuery, type Plano } from "@/src/domains/admin/administracao/negocio";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";

export default function EditarPlano() {
  const { id } = useParams<{ id: string }>();
  const { data, isError } = usePlanosQuery();
  const p = data?.find((x) => x.id === id);
  return (
    <Pagina className="max-w-[880px] gap-6">
      <Link href="/admin/plans" className="-mb-2 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        Planos
      </Link>
      {isError ? <Aviso tipo="errado">Não conseguimos carregar o plano.</Aviso> : !data ? <Osso className="h-96 rounded-pe-md" /> : !p ? <Aviso tipo="errado">Este plano não existe.</Aviso> : <Formulario key={p.id} p={p} />}
    </Pagina>
  );
}

const numero = (s: string) => (s.trim() === "" ? null : Number(s.replace(/\D/g, "")));

function Formulario({ p }: { p: Plano }) {
  const router = useRouter();
  const [guardar, { isLoading }] = useMudarPlanoMutation();
  const gratuito = p.tipo === "FREE";
  const [v, setV] = useState({
    nome: p.nome,
    descricao: p.descricao,
    mensal: String(p.preco_mensal_kz),
    anual: p.preco_anual_kz == null ? "" : String(p.preco_anual_kz),
    teste: String(p.dias_teste),
    destaque: p.destaque,
    activo: p.activo,
    licoes: p.limites.licoes_dia == null ? "" : String(p.limites.licoes_dia),
    vidas: p.limites.vidas == null ? "" : String(p.limites.vidas),
    conversa: p.limites.conversa_min_dia == null ? "" : String(p.limites.conversa_min_dia),
    nativo: String(p.limites.sessoes_nativo_mes),
    protecoes: String(p.limites.protecoes_semana),
    detalhada: String(p.limites.pronuncia_detalhada_dia ?? 0),
    certificados: p.certificados,
  });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const muda = <K extends keyof typeof v>(k: K, x: (typeof v)[K]) => setV((a) => ({ ...a, [k]: x }));
  const mensal = numero(v.mensal) ?? 0;
  const anual = numero(v.anual);
  const precoMudou = mensal !== p.preco_mensal_kz || anual !== (p.preco_anual_kz ?? null);

  return (
    <form
      noValidate
      className="flex flex-col gap-8"
      onSubmit={async (e) => {
        e.preventDefault();
        setGeral(null);
        const er: Record<string, string> = {};
        if (!v.nome.trim()) er.nome = "Escreva o nome do plano.";
        if (!gratuito && mensal <= 0) er.preco_mensal_kz = "Escreva o preço mensal em kwanzas.";
        if (!gratuito && anual != null && anual > mensal * 12) er.preco_anual_kz = "O preço anual não pode ser mais do que 12 meses.";
        if (!gratuito && anual != null && anual < mensal) er.preco_anual_kz = "O preço anual não pode ser menos do que um mês.";
        setErros(er);
        if (Object.keys(er).length) return;
        try {
          await guardar({
            id: p.id,
            nome: v.nome.trim(),
            descricao: v.descricao.trim(),
            ...(gratuito ? {} : { preco_mensal_kz: mensal, preco_anual_kz: anual, dias_teste: numero(v.teste) ?? 0, activo: v.activo }),
            destaque: v.destaque,
            certificados: v.certificados,
            limites: {
              licoes_dia: numero(v.licoes),
              vidas: numero(v.vidas),
              conversa_min_dia: numero(v.conversa),
              sessoes_nativo_mes: numero(v.nativo) ?? 0,
              protecoes_semana: numero(v.protecoes) ?? 0,
              pronuncia_detalhada_dia: numero(v.detalhada) ?? 0,
            },
          }).unwrap();
          router.push("/admin/plans");
        } catch (x) {
          // Os limites vêm como "limites.vidas": junto do campo certo.
          setErros(Object.fromEntries(Object.entries(errosPorCampo(x)).map(([k, m]) => [k.replace(/^limites\./, ""), m])));
          setGeral(mensagemErro(x, "Não foi possível guardar o plano."));
        }
      }}
    >
      <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-[38px]">Editar o {p.nome}</h1>

      <section aria-labelledby="t-preco" className="flex flex-col gap-4">
        <h2 id="t-preco" className={h2}>
          Preço e apresentação
        </h2>
        <Campo rotulo="Nome" value={v.nome} onChange={(e) => muda("nome", e.target.value)} erro={erros.nome} />
        <AreaTexto rotulo="Descrição curta" rows={2} maxLength={200} value={v.descricao} onChange={(e) => muda("descricao", e.target.value)} erro={erros.descricao} />
        {gratuito ? null : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Campo rotulo="Preço mensal (Kz)" inputMode="numeric" value={v.mensal} onChange={(e) => muda("mensal", e.target.value)} erro={erros.preco_mensal_kz} />
              <Campo
                rotulo="Preço anual (Kz)"
                inputMode="numeric"
                value={v.anual}
                onChange={(e) => muda("anual", e.target.value)}
                erro={erros.preco_anual_kz}
                ajuda={mensal && anual ? `Equivale a ${(anual / mensal).toLocaleString("pt-PT", { maximumFractionDigits: 1 })} meses.` : "Vazio para não ter plano anual."}
              />
              <Campo rotulo="Dias de teste grátis" inputMode="numeric" value={v.teste} onChange={(e) => muda("teste", e.target.value)} erro={erros.dias_teste} ajuda="0 para não ter teste." />
            </div>
            <Interruptor rotulo="Mostrar como o mais escolhido" descricao="Destaque no site e no checkout. Só um plano pode estar em destaque." ligado={v.destaque} aoMudar={(x) => muda("destaque", x)} />
            <Interruptor rotulo="Plano activo" descricao="Desligado, deixa de aparecer para novas subscrições e quem o tem não consegue renovar: fica com ele até ao fim do período pago." ligado={v.activo} aoMudar={(x) => muda("activo", x)} />
          </>
        )}
      </section>

      <section aria-labelledby="t-limites" className="flex flex-col gap-4">
        <h2 id="t-limites" className={h2}>
          Limites
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Lições por dia" inputMode="numeric" value={v.licoes} onChange={(e) => muda("licoes", e.target.value)} erro={erros.licoes_dia} ajuda="Vazio para ilimitado." />
          <Campo rotulo="Vidas" inputMode="numeric" value={v.vidas} onChange={(e) => muda("vidas", e.target.value)} erro={erros.vidas} ajuda="Vazio para ilimitado." />
          <Campo rotulo="Minutos de conversa por dia" inputMode="numeric" value={v.conversa} onChange={(e) => muda("conversa", e.target.value)} erro={erros.conversa_min_dia} ajuda="Vazio para sem limite." />
          <Campo
            rotulo="Avaliações de pronúncia detalhadas por dia"
            inputMode="numeric"
            value={v.detalhada}
            onChange={(e) => muda("detalhada", e.target.value)}
            erro={erros.pronuncia_detalhada_dia}
            ajuda="Nota por palavra e por som (Azure Speech, quando ligado no servidor). Acima do limite, a avaliação é a normal. 0 para nenhuma."
          />
          <Campo rotulo="Sessões com professor nativo por mês" inputMode="numeric" value={v.nativo} onChange={(e) => muda("nativo", e.target.value)} erro={erros.sessoes_nativo_mes} ajuda="Só aparece na descrição do plano: as sessões ainda não existem na plataforma." />
          <Campo
            rotulo="Protecções de dias seguidos por semana"
            inputMode="numeric"
            value={v.protecoes}
            onChange={(e) => muda("protecoes", e.target.value)}
            erro={erros.protecoes_semana}
            ajuda="Guardam os dias seguidos num dia em que não pratique. Ainda não se aplica: por agora só aparece na descrição."
          />
        </div>
        <Interruptor rotulo="Certificados" descricao="Os alunos deste plano recebem certificados dos cursos que terminam." ligado={v.certificados} aoMudar={(x) => muda("certificados", x)} />
      </section>

      {precoMudou && p.assinantes ? (
        <Aviso tipo="info">
          O novo preço só vale para subscrições novas. Os {num(p.assinantes)} assinantes actuais mantêm {kz(p.preco_mensal_kz)}.
        </Aviso>
      ) : null}
      {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3 border-t border-pe-linha pt-5">
        <Botao asChild tipo="secundario" tamanho="medio">
          <Link href="/admin/plans">Cancelar</Link>
        </Botao>
        <Botao type="submit" tamanho="medio" disabled={isLoading}>
          {isLoading ? "A guardar…" : "Guardar plano"}
        </Botao>
      </div>
    </form>
  );
}
