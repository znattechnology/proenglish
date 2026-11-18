"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, ChevronRight, Flame, Mic, Star, Trophy } from "lucide-react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { useEstadoVidasQuery, useSequenciaQuery } from "@/src/domains/student/laboratorio/api";
import { useLigaQuery } from "@/src/domains/student/progresso/api";
import { useMeusCursosQuery, useProgressoCursoQuery, type CursoVideo } from "@/src/domains/student/inicio/api";
import { BarraProgresso, Botao, Logo, MarcaIcone, Osso, Vidas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { contextoCurso, LinhaCursoInscrito, ListaCursos } from "@/components/pe/estudante/Cursos";
import { SinoNotificacoes } from "@/components/pe/estudante/Navegacao";
import { PedidoOpiniao } from "@/components/pe/opiniao/PedidoOpiniao";
import { CartaoRevisao } from "@/components/pe/revisao/CartaoRevisao";
import { ResumoFala } from "@/components/pe/fala/Fala";
import { usePerfilQuery } from "@/src/domains/student/perfil/api";
import { hrefDoPasso, nomeDoPasso, useProximoPassoQuery, type ProximoPasso } from "@/src/domains/student/curso/api";
import { accaoDoPasso, duracaoDoPasso } from "@/components/pe/curso/Percurso";

/** A API representa "vidas ilimitadas" (planos pagos) com 999. */
const VIDAS_ILIMITADAS = 999;
const ilimitadas = (vidas?: number) => vidas !== undefined && vidas >= VIDAS_ILIMITADAS;

function saudacao(nome?: string) {
  const h = new Date().getHours();
  const parte = h < 12 ? "Bom dia" : h < 19 ? "Boa tarde" : "Boa noite";
  const primeiro = nome?.trim().split(/\s+/)[0];
  return primeiro ? `${parte}, ${primeiro}` : parte;
}

export default function Inicio() {
  const { user } = useDjangoAuth();
  const userId = user?.id ?? "";
  // As mesmas fontes do laboratório e da liga, para os números baterem certo entre ecrãs.
  const { data: seq } = useSequenciaQuery(undefined, { skip: !user });
  const { data: estadoVidas } = useEstadoVidasQuery(undefined, { skip: !user });
  const { data: liga } = useLigaQuery(undefined, { skip: !user });
  const vidas = estadoVidas ? (estadoVidas.unlimited ? VIDAS_ILIMITADAS : estadoVidas.current) : undefined;
  const { data: cursos, isLoading: aCarregarCursos, isError: erroCursos, refetch } = useMeusCursosQuery(userId, { skip: !userId });

  // O passo seguinte é decidido pelo servidor (aula, laboratório ou conversa); lê-se de novo a cada entrada.
  const { data: proximo } = useProximoPassoQuery(undefined, { skip: !user, refetchOnMountOrArgChange: true });
  // O curso em destaque é o do passo seguinte; sem passo, o primeiro da lista.
  const emDestaque = (proximo && cursos?.find((c) => c.courseId === proximo.curso.id)) || cursos?.[0];
  const primeiro = emDestaque;
  const outros = (cursos ?? []).filter((c) => c.courseId !== emDestaque?.courseId);

  // Quem acabou de criar conta e ainda não escolheu área nem fez o acolhimento vai primeiro para lá.
  const router = useRouter();
  const { data: perfil } = usePerfilQuery(undefined, { skip: !user });
  const precisaAcolhimento = !!perfil && perfil.role === "student" && !perfil.preferences?.acolhimento && !perfil.preferences?.area;
  useEffect(() => {
    if (precisaAcolhimento) router.replace("/user/primeira-entrada");
  }, [precisaAcolhimento, router]);

  return (
    <>
      {/* Cabeçalho do telemóvel: no desktop o logótipo já está na barra lateral. */}
      <header className="flex items-center justify-between px-5 pb-2 pt-4 md:hidden">
        <Logo altura={36} />
        <div className="flex items-center gap-1">
          <Contadores sequencia={seq?.current_streak} vidas={vidas} />
          <SinoNotificacoes />
        </div>
      </header>

      <Pagina className="gap-8 pt-3">
        <div className="flex items-end justify-between gap-4">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">{saudacao(user?.name)}</h1>
          <div className="hidden md:block">
            <Contadores sequencia={seq?.current_streak} vidas={vidas} />
          </div>
        </div>

        {/* Quanto fala: a medida principal do progresso (fase 3). */}
        {user ? <ResumoFala /> : null}

        <div className="grid gap-8 md:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)] md:items-start xl:gap-12">
          <div className="flex flex-col gap-8">
            {aCarregarCursos ? (
              <Osso className="h-[200px] rounded-pe-fala" />
            ) : erroCursos ? (
              <ErroCursos aoTentar={refetch} />
            ) : primeiro ? (
              <Continuar curso={primeiro} userId={userId} proximo={proximo?.curso.id === primeiro.courseId ? proximo : null} />
            ) : (
              <PrimeiroCurso />
            )}

            {outros.length > 0 ? (
              <section aria-labelledby="titulo-cursos" className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between">
                  <h2 id="titulo-cursos" className="m-0 text-pe-titulo-s">
                    Os seus cursos
                  </h2>
                  <Link href="/user/courses" className="text-[15px] font-semibold">
                    Ver todos
                  </Link>
                </div>
                <ListaCursos>
                  {outros.slice(0, 3).map((c) => (
                    <LinhaCursoInscrito key={c.courseId} curso={c} userId={userId} />
                  ))}
                </ListaCursos>
              </section>
            ) : null}
          </div>

          <div className="flex flex-col gap-8">
            <section aria-labelledby="titulo-praticar" className="flex flex-col gap-3">
              <h2 id="titulo-praticar" className="m-0 text-pe-titulo-s">
                Praticar hoje
              </h2>
              <CartaoRevisao />
              <AtalhoPratica
                href="/user/laboratory/speaking/real-time"
                icone={<Mic />}
                titulo="Conversa com o tutor"
                texto="Fale 5 minutos sobre uma situação do seu trabalho."
              />
              <AtalhoPratica
                href="/user/laboratory"
                icone={<Star />}
                titulo="Laboratório de prática"
                texto={
                  vidas === undefined
                    ? "Lições de 5 minutos, com vidas e pontos."
                    : ilimitadas(vidas)
                      ? "Lições de 5 minutos. Vidas ilimitadas no seu plano."
                      : `Lições de 5 minutos. Tem ${vidas} ${vidas === 1 ? "vida" : "vidas"}.`
                }
              />
            </section>

            {liga ? (
              <Link
                href="/user/laboratory/achievements#liga"
                className="flex items-center gap-4 rounded-pe-md bg-pe-fundo-suave px-4 py-3.5 text-pe-tinta no-underline hover:text-pe-tinta"
              >
                <Trophy aria-hidden className="size-6 shrink-0 text-pe-azul-marca" />
                <span className="flex flex-1 flex-col">
                  <span className="font-semibold leading-[22px]">{liga.liga.nome}</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">
                    {liga.eu.posicao}.º lugar esta semana, {liga.eu.pontos_semana.toLocaleString("pt-PT")} pontos
                  </span>
                </span>
                <ChevronRight aria-hidden className="size-5 text-pe-tinta-suave" />
              </Link>
            ) : null}
            <PedidoOpiniao />
          </div>
        </div>
      </Pagina>
    </>
  );
}

/**
 * Dias seguidos e vidas, lado a lado. Não aparece nada enquanto os dados não chegam,
 * e "0 dias" não se mostra: a sequência só aparece quando já existe.
 */
function Contadores({ sequencia, vidas }: { sequencia?: number; vidas?: number }) {
  if (!sequencia && vidas === undefined) return null;
  return (
    <div className="flex items-center gap-3">
      {sequencia ? (
        <span
          role="img"
          aria-label={`${sequencia} ${sequencia === 1 ? "dia seguido" : "dias seguidos"}`}
          className="inline-flex items-center gap-1 rounded-pe-sm bg-pe-fundo-suave px-2.5 py-1.5 text-[15px] font-semibold leading-5"
        >
          <Flame aria-hidden className="size-[18px] fill-pe-realce text-pe-tinta" />
          {sequencia} {sequencia === 1 ? "dia" : "dias"}
        </span>
      ) : null}
      {vidas !== undefined ? <Vidas quantas={vidas} ilimitadas={ilimitadas(vidas)} /> : null}
    </div>
  );
}

/** O único destaque do ecrã: o passo seguinte do curso onde ficou. */
function Continuar({ curso, userId, proximo }: { curso: CursoVideo; userId: string; proximo: ProximoPasso | null }) {
  const { data: progresso, isLoading } = useProgressoCursoQuery({ userId, courseId: curso.courseId });
  const pct = Math.round(progresso?.overallProgress ?? 0);
  const comecou = pct > 0;

  if (proximo) {
    const p = proximo.passo;
    const duracao = duracaoDoPasso(p);
    return (
      <section
        aria-labelledby="titulo-continuar"
        className="pe-sobre-marca flex flex-col gap-4 rounded-pe-fala bg-pe-azul-marca px-6 py-6 text-pe-sobre-marca md:px-8"
      >
        <div className="flex flex-col gap-1">
          <span className="text-pe-legenda font-semibold">
            A seguir em {curso.title}, {p.unidade}
          </span>
          <h2 id="titulo-continuar" className="m-0 text-[22px] font-bold leading-7 md:text-pe-titulo-m">
            {p.tipo === "questionario" ? `Questionário da ${p.unidade}` : p.titulo}
          </h2>
          <span className="text-[15px] leading-[22px]">
            {nomeDoPasso(p)}
            {duracao ? `, cerca de ${duracao}` : ""}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <BarraProgresso
            valor={proximo.total ? Math.round((100 * proximo.feitos) / proximo.total) : 0}
            rotulo={`Passos feitos em ${curso.title}`}
            cor="realce"
            className="flex-1 bg-white/20"
          />
          <span className="text-pe-legenda font-semibold tabular-nums">
            {proximo.feitos} de {proximo.total} passos
          </span>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Botao asChild tipo="realce" className="self-stretch md:self-start">
            <Link href={hrefDoPasso(curso.courseId, p)}>{accaoDoPasso(p)}</Link>
          </Botao>
          <Link href={`/user/courses/${curso.courseId}`} className="self-center text-[15px] font-semibold text-pe-sobre-marca underline-offset-[3px] hover:text-pe-realce md:self-auto">
            Ver o percurso todo
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="titulo-continuar"
      className="pe-sobre-marca flex flex-col gap-4 rounded-pe-fala bg-pe-azul-marca px-6 py-6 text-pe-sobre-marca md:px-8"
    >
      <div className="flex flex-col gap-1">
        <span className="text-pe-legenda font-semibold">{contextoCurso(curso)}</span>
        <h2 id="titulo-continuar" className="m-0 text-[22px] font-bold leading-7 md:text-pe-titulo-m">
          {curso.title}
        </h2>
      </div>
      {isLoading ? (
        <Osso className="h-2 w-full opacity-30" />
      ) : !comecou ? (
        <p className="m-0 text-[15px] leading-[22px]">Ainda não começou. A primeira aula leva cerca de 8 minutos.</p>
      ) : (
        <div className="flex items-center gap-3">
          <BarraProgresso valor={pct} rotulo={`Progresso em ${curso.title}`} cor="realce" className="flex-1 bg-white/20" />
          <span className="text-pe-legenda font-semibold">{pct}%</span>
        </div>
      )}
      <Botao asChild tipo="realce" className="self-stretch md:self-start">
        <Link href={`/user/courses/${curso.courseId}`}>{comecou ? "Continuar curso" : "Começar o curso"}</Link>
      </Botao>
    </section>
  );
}

/** Sem cursos: o destaque passa a ser escolher o primeiro. */
function PrimeiroCurso() {
  return (
    <section aria-labelledby="titulo-primeiro" className="pe-sobre-marca flex flex-col gap-4 rounded-pe-fala bg-pe-azul-marca px-6 py-6 text-pe-sobre-marca md:px-8">
      <MarcaIcone fundo="realce" tamanho={56}>
        <BookOpen />
      </MarcaIcone>
      <div className="flex flex-col gap-1.5">
        <h2 id="titulo-primeiro" className="m-0 text-[22px] font-bold leading-7 md:text-pe-titulo-m">
          Escolha o seu primeiro curso
        </h2>
        <p className="m-0 text-[15px] leading-[22px]">Há cursos por área profissional. A primeira aula leva cerca de 8 minutos.</p>
      </div>
      <Botao asChild tipo="realce" className="self-stretch md:self-start">
        <Link href="/user/courses/explore">Explorar cursos</Link>
      </Botao>
    </section>
  );
}

function AtalhoPratica({ href, icone, titulo, texto }: { href: string; icone: React.ReactNode; titulo: string; texto: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-4 rounded-pe-md border border-pe-linha px-4 py-3.5 text-pe-tinta no-underline hover:border-pe-linha-forte hover:text-pe-tinta"
    >
      <MarcaIcone fundo="marca" tamanho={44}>
        {icone}
      </MarcaIcone>
      <span className="flex flex-1 flex-col">
        <span className="font-semibold leading-[22px]">{titulo}</span>
        <span className="text-pe-legenda text-pe-tinta-suave">{texto}</span>
      </span>
      <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
    </Link>
  );
}

function ErroCursos({ aoTentar }: { aoTentar: () => void }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-pe-md bg-pe-errado-suave px-4 py-4">
      <p className="m-0">
        <span className="font-semibold">Não conseguimos carregar os seus cursos.</span> O problema é do nosso lado; o seu progresso está guardado.
      </p>
      <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={aoTentar}>
        Tentar outra vez
      </Botao>
    </div>
  );
}
