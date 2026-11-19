"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cnPe } from "@/lib/pe";

/**
 * As personagens da história das aulas (Kalandula Tech, A1), com a primeira frase que dizem nos guiões.
 * Retratos em public/site/personagens, feitos a partir das fichas aprovadas (docs/conteudo/imagens/site-personagens.json).
 * Uma fila que se desliza (dedo ou setas), sem passagem automática: quem lê decide o ritmo.
 */
const PERSONAGENS = [
  { id: "ana", nome: "Ana Domingos", papel: "Recepcionista da Kalandula Tech", frase: "I'm Ana. Ana Domingos. What's your name?" },
  { id: "paulo", nome: "Paulo Mendes", papel: "Técnico de informática, no primeiro dia", frase: "Good morning. I'm Paulo Mendes. It's my first day." },
  { id: "baptista", nome: "Sr. João Baptista", papel: "Director, o chefe do Paulo", frase: "Paulo! Good morning. Welcome to the team." },
  { id: "silvia", nome: "Sílvia Neto", papel: "Contabilista, de Benguela", frase: "Hi, Paulo. Nice to meet you. I'm an accountant." },
  { id: "mateus", nome: "Mateus", papel: "Engenheiro, de Huambo; trabalha em Cabinda", frase: "I'm from Huambo. And you?" },
  { id: "thandi", nome: "Thandi Mokoena", papel: "Engenheira sul-africana, de Joanesburgo", frase: "Good morning. I'm Thandi Mokoena. I have a meeting with Mr Baptista." },
  { id: "nuno", nome: "Nuno", papel: "Estagiário, acabado de chegar a Luanda", frase: "Ana, I'm new in Luanda. Is there a bank near here?" },
];

export function Personagens() {
  const fila = useRef<HTMLUListElement>(null);
  const [inicio, setInicio] = useState(true);
  const [fim, setFim] = useState(false);

  useEffect(() => {
    const el = fila.current;
    if (!el) return;
    const ver = () => {
      setInicio(el.scrollLeft <= 4);
      setFim(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4);
    };
    ver();
    el.addEventListener("scroll", ver, { passive: true });
    window.addEventListener("resize", ver);
    return () => {
      el.removeEventListener("scroll", ver);
      window.removeEventListener("resize", ver);
    };
  }, []);

  const andar = (sentido: 1 | -1) => {
    const el = fila.current;
    if (!el) return;
    const cartao = el.querySelector("li");
    const passo = cartao ? cartao.getBoundingClientRect().width + 24 : el.clientWidth * 0.8;
    const calmo = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollBy({ left: sentido * passo, behavior: calmo ? "auto" : "smooth" });
  };

  const seta = "flex size-12 items-center justify-center rounded-full border-2 border-pe-azul-marca bg-pe-fundo text-pe-azul-marca hover:bg-pe-fundo-suave disabled:cursor-default disabled:opacity-35 disabled:hover:bg-pe-fundo";

  return (
    <section id="personagens" aria-labelledby="t-personagens" className="scroll-mt-4 overflow-hidden bg-pe-fundo-suave">
      <div className="mx-auto max-w-[1200px] px-4 pt-14 md:px-6 md:pt-20">
        <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
          <div className="flex min-w-0 max-w-[640px] flex-col gap-3">
            <h2 id="t-personagens" className="m-0 font-pe-titulo text-[30px] font-bold leading-[1.15] tracking-[-0.015em] md:text-[2.5rem]">
              As pessoas que vai conhecer nas aulas
            </h2>
            <p className="m-0 text-pe-corpo-l text-pe-tinta-suave">
              As aulas contam uma história: a de uma pequena empresa de tecnologia em Luanda, a Kalandula Tech. Acompanha estas personagens no dia-a-dia de trabalho e aprende com elas o inglês de cada situação.
            </p>
          </div>
          <div className="hidden gap-3 md:flex">
            <button type="button" className={seta} onClick={() => andar(-1)} disabled={inicio} aria-label="Personagens anteriores">
              <ChevronLeft aria-hidden className="size-6" />
            </button>
            <button type="button" className={seta} onClick={() => andar(1)} disabled={fim} aria-label="Personagens seguintes">
              <ChevronRight aria-hidden className="size-6" />
            </button>
          </div>
        </div>
      </div>

      {/* A fila corre até à borda do ecrã; à esquerda alinha com o texto da secção. */}
      <ul
        ref={fila}
        className="m-0 mt-8 flex px-4 [scroll-padding-inline:1rem] md:px-[max(1.5rem,calc((100vw-1200px)/2+1.5rem))] md:[scroll-padding-inline:max(1.5rem,calc((100vw-1200px)/2+1.5rem))] list-none snap-x snap-mandatory gap-6 overflow-x-auto pb-2 [scrollbar-width:none] md:mt-10 [&::-webkit-scrollbar]:hidden"
      >
          {PERSONAGENS.map((p, i) => (
            <li key={p.id} className="flex w-[78%] max-w-[300px] shrink-0 snap-start flex-col gap-4 sm:w-[300px]">
              <div className={cnPe("aspect-[4/5] overflow-hidden bg-pe-fundo-forte", i % 2 ? "rounded-pe-fala-aluno" : "rounded-pe-fala")}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/site/personagens/${p.id}-800.webp`}
                  srcSet={`/site/personagens/${p.id}-400.webp 400w, /site/personagens/${p.id}-800.webp 800w`}
                  sizes="300px"
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="block size-full object-cover"
                />
              </div>
              <div className="flex flex-col gap-1">
                <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{p.nome}</h3>
                <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">{p.papel}</p>
              </div>
              <p lang="en" className="m-0 font-pe-titulo text-[18px] font-light italic leading-[27px] text-pe-azul-marca">
                “{p.frase}”
              </p>
            </li>
          ))}
      </ul>

      <div className="mx-auto max-w-[1200px] px-4 pb-14 pt-6 md:px-6 md:pb-20">
        <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave">São personagens da história das aulas; a cada nível juntam-se outras.</p>
      </div>
    </section>
  );
}
