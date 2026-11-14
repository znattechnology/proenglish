"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { Aviso, Botao, Campo, Escolha, Interruptor, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { PAPEL, useMudarUtilizadorMutation, useProvinciasQuery, useUtilizadorQuery, type DetalheUtilizador, type MudancaUtilizador, type Papel, type TipoPlano } from "@/src/domains/admin/administracao/api";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";

export default function EditarUtilizador() {
  const { userId } = useParams<{ userId: string }>();
  const { data, isError } = useUtilizadorQuery(userId);
  return (
    <Pagina className="max-w-[880px] gap-6">
      <Link href={`/admin/users/${userId}`} className="-mb-2 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        {data?.utilizador.nome ?? "Utilizador"}
      </Link>
      {isError ? <Aviso tipo="errado">Não conseguimos carregar o utilizador.</Aviso> : !data ? <Osso className="h-96 rounded-pe-md" /> : <Formulario key={data.utilizador.id} d={data} />}
    </Pagina>
  );
}

function Formulario({ d }: { d: DetalheUtilizador }) {
  const u = d.utilizador;
  const router = useRouter();
  const { user: eu } = useDjangoAuth();
  const proprio = eu?.id === u.id;
  const { data: provincias } = useProvinciasQuery();
  const [guardar, { isLoading }] = useMudarUtilizadorMutation();
  const inicial = {
    nome: u.nome,
    email: u.email,
    telefone: u.telefone ?? "",
    papel: u.papel,
    plano: (u.plano?.tipo ?? "FREE") as TipoPlano,
    provincia: u.provincia ?? "",
    publica_sem_revisao: d.professor?.publica_sem_revisao ?? false,
  };
  const [v, setV] = useState(inicial);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [avisoOk, setAvisoOk] = useState<string | null>(null);
  const muda = <K extends keyof typeof v>(k: K, x: (typeof v)[K]) => setV((a) => ({ ...a, [k]: x }));
  const mudancas = Object.fromEntries(Object.entries(v).filter(([k, x]) => x !== inicial[k as keyof typeof inicial])) as Partial<typeof v>;
  const sujo = Object.keys(mudancas).length > 0;

  return (
    <form
      noValidate
      className="flex flex-col gap-8"
      onSubmit={async (e) => {
        e.preventDefault();
        setGeral(null);
        const er: Record<string, string> = {};
        if (v.nome.trim().length < 2) er.nome = "Escreva o nome completo.";
        if (!/^\S+@\S+\.\S+$/.test(v.email.trim())) er.email = "Escreva um email válido.";
        setErros(er);
        if (Object.keys(er).length) return;
        const corpo: MudancaUtilizador = { ...mudancas } as MudancaUtilizador;
        if ("telefone" in mudancas) corpo.telefone = v.telefone.trim() || null;
        if ("provincia" in mudancas) corpo.provincia = v.provincia || null;
        // O plano e a publicação sem revisão dependem do papel que fica depois de guardar.
        if (v.papel !== "student") delete corpo.plano;
        if (v.papel !== "teacher") delete corpo.publica_sem_revisao;
        try {
          const r = (await guardar({ id: u.id, ...corpo }).unwrap()) as DetalheUtilizador & { message?: string };
          if (r.message && "email" in corpo) {
            setGeral(null);
            setAvisoOk(r.message);
            return;
          }
          router.push(`/admin/users/${u.id}`);
        } catch (x) {
          setErros(errosPorCampo(x));
          setGeral(mensagemErro(x, "Não foi possível guardar."));
        }
      }}
    >
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-[38px]">Editar dados</h1>
        <p className="m-0 text-pe-tinta-suave">
          {u.nome}, {PAPEL[u.papel].toLowerCase()}.
        </p>
      </div>

      <section aria-labelledby="t-pessoais" className="flex flex-col gap-4">
        <h2 id="t-pessoais" className={h2}>
          Dados pessoais
        </h2>
        <Campo rotulo="Nome completo" value={v.nome} onChange={(e) => muda("nome", e.target.value)} erro={erros.nome} />
        <Campo rotulo="Email" type="email" value={v.email} onChange={(e) => muda("email", e.target.value)} erro={erros.email} ajuda="Se mudar, a pessoa recebe um código no endereço novo. Até o confirmar, continua a entrar com o actual." />
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Telefone" type="tel" value={v.telefone} onChange={(e) => muda("telefone", e.target.value)} erro={erros.telefone} />
          <Escolha rotulo="Província" value={v.provincia} onChange={(e) => muda("provincia", e.target.value)} erro={erros.provincia}>
            <option value="">Não indicada</option>
            {provincias?.map((p) => (
              <option key={p.valor} value={p.valor}>
                {p.nome}
              </option>
            ))}
          </Escolha>
        </div>
      </section>

      <section aria-labelledby="t-acesso" className="flex flex-col gap-4">
        <h2 id="t-acesso" className={h2}>
          Acesso
        </h2>
        <Escolha
          rotulo="Papel"
          value={v.papel}
          disabled={proprio}
          onChange={(e) => muda("papel", e.target.value as Papel)}
          erro={erros.papel}
          ajuda={proprio ? "Não pode mudar o seu próprio papel." : u.papel === "admin" || v.papel === "admin" ? "Só um superutilizador pode dar ou tirar o papel de administrador." : "Mudar o papel termina as sessões abertas da pessoa."}
        >
          {(Object.keys(PAPEL) as Papel[]).map((p) => (
            <option key={p} value={p}>
              {PAPEL[p]}
            </option>
          ))}
        </Escolha>
        {v.papel === "student" ? (
          <Escolha rotulo="Plano" value={v.plano} onChange={(e) => muda("plano", e.target.value as TipoPlano)} erro={erros.plano} ajuda="Mudar aqui não cobra nem devolve dinheiro. Para isso use Subscrições e pagamentos.">
            <option value="FREE">Gratuito</option>
            <option value="PREMIUM">Premium</option>
            <option value="PREMIUM_PLUS">Premium Plus</option>
          </Escolha>
        ) : null}
        {v.papel === "teacher" ? (
          <Interruptor
            rotulo="Pode publicar cursos sem revisão"
            descricao="Os cursos deste professor entram logo no catálogo, sem passar pela equipa."
            ligado={v.publica_sem_revisao}
            aoMudar={(x) => muda("publica_sem_revisao", x)}
          />
        ) : null}
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">
          Para suspender ou reactivar a conta, use o botão na página do utilizador.
        </p>
      </section>

      {avisoOk ? (
        <Aviso tipo="certo">
          {avisoOk} <Link href={`/admin/users/${u.id}`}>Voltar ao utilizador</Link>
        </Aviso>
      ) : null}
      {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-3 border-t border-pe-linha pt-5">
        {sujo ? <span className="mr-auto text-[15px] text-pe-tinta-suave">Tem alterações por guardar.</span> : null}
        <Botao asChild tipo="secundario" tamanho="medio">
          <Link href={`/admin/users/${u.id}`}>{sujo ? "Descartar" : "Voltar"}</Link>
        </Botao>
        <Botao type="submit" tamanho="medio" disabled={isLoading || !sujo}>
          {isLoading ? "A guardar…" : "Guardar alterações"}
        </Botao>
      </div>
    </form>
  );
}
