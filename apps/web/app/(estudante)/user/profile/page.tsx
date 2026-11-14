"use client";

import Link from "next/link";
import { BarChart3, ChevronRight, CreditCard, LogOut, Medal, Receipt, Settings, Trophy, Bell, MessageSquareHeart } from "lucide-react";
import { Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { categoriaPt } from "@/src/domains/student/inicio/api";
import { useEstadoVidasQuery, useSequenciaQuery } from "@/src/domains/student/laboratorio/api";
import { iniciais, usePerfilQuery } from "@/src/domains/student/perfil/api";
import { dataPt, useMinhaSubscricaoQuery } from "@/src/domains/student/subscricao/api";

export default function PaginaPerfil() {
  const { logout } = useDjangoAuth();
  const { data: perfil } = usePerfilQuery();
  const { data: sub } = useMinhaSubscricaoQuery();
  const { data: sequencia } = useSequenciaQuery();
  const { data: vidas } = useEstadoVidasQuery();

  const subtitulo = [categoriaPt(perfil?.preferences?.area), perfil?.preferences?.cidade].filter(Boolean).join(", ");
  const gratuito = !sub || sub.plan.plan_type === "FREE";
  const itens = [
    { href: "/user/analytics", nome: "Estatísticas", texto: "Tempo, lições e respostas certas", Icone: BarChart3 },
    { href: "/user/certificates", nome: "Certificados", texto: "Os certificados dos cursos que concluiu", Icone: Medal },
    { href: "/user/laboratory/achievements", nome: "Conquistas e liga", texto: "Medalhas e a sua posição", Icone: Trophy },
    {
      href: "/user/subscription",
      nome: "Subscrição",
      texto: sub ? (gratuito ? "Plano Gratuito" : `${sub.plan.name}, válido até ${dataPt(sub.expires_at, { day: "numeric", month: "long" })}`) : "O seu plano",
      Icone: CreditCard,
    },
    { href: "/user/billing", nome: "Pagamentos e recibos", texto: "Os recibos dos seus pagamentos", Icone: Receipt },
    { href: "/user/settings", nome: "Definições", texto: "Dados, meta diária, avisos e palavra-passe", Icone: Settings },
    { href: "/user/notifications", nome: "Notificações", texto: "Os avisos que recebeu", Icone: Bell },
    { href: "/user/feedback", nome: "Dar a sua opinião", texto: "Diga-nos o que está a correr bem e o que mudar", Icone: MessageSquareHeart },
  ];

  return (
    <Pagina className="max-w-[720px]">
      <section aria-label="O seu perfil" className="pe-sobre-marca flex flex-col gap-5 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca">
        <div className="flex items-center gap-4">
          <span aria-hidden className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-[22px_22px_22px_0] bg-pe-realce font-pe-titulo text-[22px] font-bold text-pe-tinta">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {perfil?.avatar ? <img src={perfil.avatar} alt="" className="size-full object-cover" /> : iniciais(perfil?.name)}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            {perfil ? <h1 className="m-0 truncate font-pe-titulo text-[24px] font-bold leading-[30px]">{perfil.name}</h1> : <Osso className="h-7 w-48" />}
            {subtitulo ? <span className="text-[15px]">{subtitulo}</span> : null}
            {sub ? (
              <Etiqueta tipo={gratuito ? "neutra" : "realce"} className="mt-0.5">
                {sub.plan.name}
              </Etiqueta>
            ) : null}
          </div>
        </div>
        <dl className="m-0 grid grid-cols-2 gap-3">
          {[
            [String(sequencia?.current_streak ?? "–"), sequencia?.current_streak === 1 ? "dia seguido" : "dias seguidos"],
            [vidas ? vidas.points.toLocaleString("pt-PT") : "–", "pontos"],
          ].map(([n, r]) => (
            <div key={r} className="flex flex-col-reverse rounded-pe-md bg-white/10 px-4 py-3">
              <dt className="text-[14px] leading-5">{r}</dt>
              <dd className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tabular-nums">{n}</dd>
            </div>
          ))}
        </dl>
      </section>

      <nav aria-label="Conta" className="flex flex-col">
        {itens.map(({ href, nome, texto, Icone }) => (
          <Link key={href} href={href} className="flex min-h-[68px] items-center gap-4 border-b border-pe-fundo-forte py-2 text-pe-tinta no-underline hover:bg-pe-fundo-suave hover:text-pe-tinta">
            <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-[14px_14px_14px_0] bg-pe-fundo-forte">
              <Icone className="size-5" />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="font-semibold leading-[22px]">{nome}</span>
              <span className="truncate text-pe-legenda text-pe-tinta-suave">{texto}</span>
            </span>
            <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
          </Link>
        ))}
      </nav>

      <Botao tipo="ligacao" className="self-start" onClick={() => void logout()}>
        <LogOut aria-hidden /> Sair da conta
      </Botao>
    </Pagina>
  );
}
