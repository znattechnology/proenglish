"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, LogOut } from "lucide-react";
import { Aviso, Botao, Campo, Escolha, Interruptor, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { MudarPalavraPasse } from "@/components/pe/conta/MudarPalavraPasse";
import { SeccaoAvisos } from "@/components/pe/avisos/Avisos";
import { cnPe } from "@/lib/pe";
import { EscolherMetaFala } from "@/components/pe/fala/Fala";
import { useMetaFalaQuery } from "@/src/domains/student/fala/api";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { normalizarNivel } from "@/src/domains/shared/niveis";
import { dataPt, mensagemErro, telefoneLegivel, useLembretesMutation, useMinhaSubscricaoQuery } from "@/src/domains/student/subscricao/api";
import {
  AREAS,
  errosDoServidor,
  iniciais,
  NIVEIS,
  useApagarContaMutation,
  useGuardarPerfilMutation,
  useMetaQuery,
  useMudarMetaMutation,
  useProvinciasQuery,
  usePerfilQuery,
  type Nivel,
  type Perfil,
} from "@/src/domains/student/perfil/api";

export default function PaginaDefinicoes() {
  const { data: perfil, isLoading, isError, refetch } = usePerfilQuery();
  const { data: sub } = useMinhaSubscricaoQuery();
  const { logout } = useDjangoAuth();

  return (
    <Pagina className="max-w-[880px]">
      <Link href="/user/profile" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px] md:hidden">
        <ArrowLeft aria-hidden className="size-5" /> Perfil
      </Link>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar os seus dados.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : isLoading || !perfil ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-5">
          <Osso className="h-20 w-80" />
          <Osso className="h-[420px] rounded-pe-md" />
        </div>
      ) : (
        <>
          <header className="flex items-center gap-4">
            <span aria-hidden className="pe-sobre-marca flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-[22px_22px_22px_0] bg-pe-azul-marca font-pe-titulo text-[22px] font-bold text-pe-sobre-marca">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {perfil.avatar ? <img src={perfil.avatar} alt="" className="size-full object-cover" /> : iniciais(perfil.name)}
            </span>
            <div className="flex min-w-0 flex-col">
              <h1 className="m-0 truncate font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-m">{perfil.name}</h1>
              <span className="text-[15px] text-pe-tinta-suave">
                Membro desde {dataPt(perfil.created_at, { month: "long", year: "numeric" })}
                {sub ? `, plano ${sub.plan.name}` : ""}
              </span>
            </div>
          </header>

          <OsSeusDados perfil={perfil} />
          <EstudoEAvisos pago={!!sub && sub.plan.plan_type !== "FREE"} lembretes={!!sub?.lembretes_renovacao} />
          <SeccaoAvisos />
          <Seguranca temSenha={perfil.has_password !== false} />

          <Botao tipo="ligacao" className="self-start" onClick={() => void logout()}>
            <LogOut aria-hidden /> Sair da conta
          </Botao>
        </>
      )}
    </Pagina>
  );
}

/* ------------------------------------------------------------------ */
/* Os seus dados                                                        */
/* ------------------------------------------------------------------ */
function OsSeusDados({ perfil }: { perfil: Perfil }) {
  const { checkAuth } = useDjangoAuth();
  const [guardar, { isLoading }] = useGuardarPerfilMutation();
  const [nome, setNome] = useState(perfil.name);
  const [telefone, setTelefone] = useState(telefoneLegivel((perfil.phone ?? "").replace(/^\+244/, "")));
  const [cidade, setCidade] = useState(perfil.preferences?.cidade ?? "");
  const [provincia, setProvincia] = useState(perfil.provincia ?? "");
  const { data: provincias } = useProvinciasQuery();
  const [area, setArea] = useState(perfil.preferences?.area ?? "");
  const [nivel, setNivel] = useState<Nivel | "">(normalizarNivel(perfil.preferences?.nivel) ?? "");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);

  const estrangeiro = (perfil.phone ?? "").startsWith("+") && !(perfil.phone ?? "").startsWith("+244");

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEstado(null);
    const digitos = telefone.replace(/\D/g, "");
    const novos: Record<string, string> = {};
    if (nome.trim().length < 2) novos.name = "Escreva o seu nome.";
    if (!estrangeiro && digitos && !/^9\d{8}$/.test(digitos)) novos.phone = "Escreva os 9 dígitos do número, a começar por 9.";
    setErros(novos);
    if (Object.keys(novos).length) return;

    const r = await guardar({
      name: nome.trim(),
      phone: estrangeiro ? perfil.phone : digitos ? `+244${digitos}` : null,
      provincia: provincia || null,
      preferences: { cidade: cidade.trim(), area, nivel: nivel || undefined },
    });
    if ("error" in r && r.error) {
      const { campos, geral } = errosDoServidor(r.error);
      setErros(campos);
      setEstado(geral ? { tipo: "errado", texto: geral } : null);
      return;
    }
    setEstado({ tipo: "certo", texto: "Alterações guardadas." });
    void checkAuth(); // o nome na barra lateral vem da sessão
  };

  return (
    <section aria-labelledby="titulo-dados" className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
      <h2 id="titulo-dados" className="m-0 font-pe-titulo text-pe-titulo-s">
        Os seus dados
      </h2>
      <form onSubmit={enviar} noValidate className="grid gap-4 md:grid-cols-2">
        <Campo rotulo="Nome completo" value={nome} onChange={(e) => setNome(e.target.value)} autoComplete="name" erro={erros.name} className="md:col-span-2" />
        <Campo rotulo="Email" type="email" value={perfil.email} disabled ajuda="O email não se pode mudar aqui." />
        {estrangeiro ? (
          <Campo rotulo="Telefone" value={perfil.phone ?? ""} disabled ajuda="Número estrangeiro." />
        ) : (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="d-telefone" className="text-pe-rotulo">
              Telefone
            </label>
            <div className={cnPe("flex h-12 overflow-hidden rounded-pe-sm border-[1.5px] focus-within:outline focus-within:outline-[3px] focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo", erros.phone ? "border-pe-errado" : "border-pe-linha-forte")}>
              <span className="flex items-center border-r border-pe-linha bg-pe-fundo-suave px-3 font-semibold">+244</span>
              <input
                id="d-telefone"
                type="tel"
                inputMode="numeric"
                autoComplete="tel-national"
                placeholder="923 456 789"
                value={telefone}
                onChange={(e) => setTelefone(telefoneLegivel(e.target.value))}
                aria-invalid={erros.phone ? true : undefined}
                aria-describedby={erros.phone ? "d-telefone-erro" : undefined}
                className="min-w-0 flex-1 border-0 bg-pe-fundo px-3 text-[16px] text-pe-tinta outline-none"
              />
            </div>
            {erros.phone ? (
              <p id="d-telefone-erro" className="m-0 text-pe-legenda font-semibold text-pe-errado">
                {erros.phone}
              </p>
            ) : null}
          </div>
        )}
        <Campo rotulo="Cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} autoComplete="address-level2" />
        <Escolha rotulo="Província (opcional)" value={provincia} onChange={(e) => setProvincia(e.target.value)} ajuda="Ajuda-nos a perceber onde estão os nossos alunos.">
          <option value="">Prefiro não dizer</option>
          {provincias?.map((p) => (
            <option key={p.valor} value={p.valor}>
              {p.nome}
            </option>
          ))}
        </Escolha>
        <Escolha rotulo="Área profissional" value={area} onChange={(e) => setArea(e.target.value)} ajuda="Usamos a área para lhe sugerir cursos.">
          <option value="">Escolha a sua área</option>
          {AREAS.map((a) => (
            <option key={a.valor} value={a.valor}>
              {a.nome}
            </option>
          ))}
        </Escolha>
        <Escolha rotulo="O seu nível de inglês" value={nivel} onChange={(e) => setNivel(e.target.value as Nivel | "")}>
          <option value="">Não sei</option>
          {NIVEIS.map((n) => (
            <option key={n.valor} value={n.valor}>
              {`${n.valor}: ${n.descricao}`}
            </option>
          ))}
        </Escolha>
        <div className="flex flex-col gap-3 md:col-span-2 md:flex-row md:items-center">
          <Botao type="submit" disabled={isLoading} className="md:self-start">
            {isLoading ? "A guardar…" : "Guardar alterações"}
          </Botao>
          {estado ? (
            <Aviso tipo={estado.tipo} className="md:flex-1">
              {estado.texto}
            </Aviso>
          ) : null}
        </div>
      </form>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Estudo e avisos (só o que tem efeito)                               */
/* ------------------------------------------------------------------ */
const METAS = [5, 10, 15, 20];

function EstudoEAvisos({ pago, lembretes }: { pago: boolean; lembretes: boolean }) {
  const { data: meta } = useMetaQuery();
  const [mudarMeta, { isLoading: aMudarMeta }] = useMudarMetaMutation();
  const [mudarLembretes, { isLoading: aMudarLembretes }] = useLembretesMutation();
  const [erro, setErro] = useState<string | null>(null);
  const actual = meta?.daily_goal_minutes;

  return (
    <section aria-labelledby="titulo-estudo" className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
      <h2 id="titulo-estudo" className="m-0 font-pe-titulo text-pe-titulo-s">
        Estudo e renovação
      </h2>
      <div className="flex flex-col gap-2">
        <span id="rotulo-meta" className="font-semibold leading-[22px]">
          Meta de estudo
        </span>
        <span className="text-pe-legenda text-pe-tinta-suave">Minutos de prática por dia. Conta para os dias seguidos.</span>
        <div role="radiogroup" aria-labelledby="rotulo-meta" className="flex flex-wrap gap-2 pt-1">
          {METAS.map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={actual === m}
              disabled={aMudarMeta || !meta}
              onClick={async () => {
                setErro(null);
                const r = await mudarMeta(m);
                if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível mudar a meta."));
              }}
              className={cnPe(
                "min-h-11 min-w-[76px] rounded-full px-4 text-[15px] font-semibold tabular-nums",
                actual === m ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
              )}
            >
              {m} min
            </button>
          ))}
        </div>
      </div>
      <MetaFala />
      {pago ? (
        <Interruptor
          rotulo="Lembretes de renovação"
          descricao="Avisamos 3 dias antes e no dia em que o plano termina."
          ligado={lembretes}
          disabled={aMudarLembretes}
          aoMudar={async (v) => {
            setErro(null);
            const r = await mudarLembretes(v);
            if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível guardar."));
          }}
        />
      ) : null}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
    </section>
  );
}

/** Meta de minutos a falar por dia (fase 3): só se mostra, não conta para os dias seguidos. */
function MetaFala() {
  const { data } = useMetaFalaQuery();
  return (
    <div className="flex flex-col gap-1">
      <EscolherMetaFala actual={data?.meta_fala_min} opcoes={data?.opcoes ?? [3, 5, 10, 15]} id="rotulo-meta-fala" rotulo="Meta de fala" />
      <span className="text-pe-legenda text-pe-tinta-suave">Minutos a falar inglês por dia (conversas, lições, revisão e aulas). Aparece em destaque no painel.</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Segurança: palavra-passe e apagar a conta                           */
/* ------------------------------------------------------------------ */
function Seguranca({ temSenha }: { temSenha: boolean }) {
  const [senha, setSenha] = useState(false);
  const [apagar, setApagar] = useState(false);
  const [feito, setFeito] = useState<string | null>(null);
  return (
    <section aria-labelledby="titulo-seguranca" className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
      <h2 id="titulo-seguranca" className="m-0 font-pe-titulo text-pe-titulo-s">
        Segurança
      </h2>
      <div className="flex flex-col items-start gap-2">
        {!temSenha ? <p className="m-0 max-w-[60ch] text-[15px] leading-[22px] text-pe-tinta-suave">Entra com o Google. Se quiser, pode também criar uma palavra-passe para entrar com o email.</p> : null}
        <Botao tipo="secundario" tamanho="medio" onClick={() => setSenha(true)}>
          {temSenha ? "Mudar a palavra-passe" : "Criar uma palavra-passe"}
        </Botao>
        {feito ? <Aviso tipo="certo">{feito}</Aviso> : null}
      </div>
      <div className="flex flex-col items-start gap-2 border-t border-pe-linha pt-4">
        <p className="m-0 max-w-[60ch] text-[15px] leading-[22px] text-pe-tinta-suave">
          Apagar a conta apaga o seu nome, email, telefone e fotografia, e deixa de poder entrar. Não se pode desfazer.
        </p>
        <Botao tipo="perigo" tamanho="medio" onClick={() => setApagar(true)}>
          Apagar a conta
        </Botao>
      </div>
      {/* Montados só quando abrem: o formulário recomeça vazio de cada vez. */}
      {senha ? <MudarPalavraPasse temSenha={temSenha} aberto aoMudar={setSenha} aoMudada={(m) => setFeito(m)} /> : null}
      {apagar ? <ApagarConta temSenha={temSenha} aberto aoMudar={setApagar} /> : null}
    </section>
  );
}

function ApagarConta({ temSenha, aberto, aoMudar }: { temSenha: boolean; aberto: boolean; aoMudar: (v: boolean) => void }) {
  const { logout } = useDjangoAuth();
  const [apagar, { isLoading }] = useApagarContaMutation();
  const [senha, setSenha] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    // Contas do Google não têm palavra-passe: confirma-se com a caixa.
    const r = await apagar(temSenha ? { password: senha } : { confirmar: true });
    if ("error" in r && r.error) {
      setErro(errosDoServidor(r.error).geral ?? "Não foi possível apagar a conta.");
      return;
    }
    // A sessão já terminou no servidor: limpa o estado local e vai para a página de entrada.
    await logout();
  };

  return (
    <Dialogo aberto={aberto} aoMudar={aoMudar} titulo="Apagar a conta?">
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        <ul className="m-0 flex flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
          <li>O seu nome, email, telefone e fotografia são apagados e deixa de poder entrar.</li>
          <li>O progresso, os pontos e os certificados deixam de estar ligados a si e não se recuperam.</li>
          <li>Se tem um plano pago, perde os dias que faltam. Não há reembolso automático.</li>
          <li>Os recibos dos pagamentos ficam guardados sem o seu nome, porque são registos fiscais.</li>
        </ul>
        {temSenha ? (
          <Campo rotulo="Escreva a sua palavra-passe para confirmar" type="password" autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} />
        ) : (
          <label className="flex items-start gap-3 text-[15px] leading-[22px]">
            <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-pe-errado" />
            <span>Percebo que a conta é apagada para sempre.</span>
          </label>
        )}
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-col gap-3">
          <Botao type="button" larguraTotal onClick={() => aoMudar(false)}>
            Manter a conta
          </Botao>
          <Botao type="submit" tipo="perigo" larguraTotal disabled={isLoading || (temSenha ? !senha : !confirmo)}>
            {isLoading ? "A apagar…" : "Apagar a conta para sempre"}
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
