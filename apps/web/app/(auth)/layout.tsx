import Link from "next/link";
import { Logo } from "@/components/pe";
import { fraseDeHoje } from "@/src/domains/auth/frases";

// A frase muda todos os dias: a página é refeita de hora a hora.
export const revalidate = 3600;

/**
 * Páginas de entrada e conta (base visual `.pe`). No desktop, à esquerda, a frase de hoje;
 * à direita, o formulário. No telemóvel, só o formulário.
 */
export default function LayoutConta({ children }: { children: React.ReactNode }) {
  const f = fraseDeHoje();
  return (
    <div className="pe flex min-h-dvh bg-pe-fundo text-pe-tinta">
      <section aria-label="A frase de hoje" className="hidden flex-1 flex-col items-center justify-center bg-pe-fundo-suave p-12 lg:flex">
        <div className="flex w-full max-w-[480px] flex-col gap-6">
        <figure className="pe-sobre-marca m-0 flex max-w-[480px] flex-col gap-4 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-10 text-pe-sobre-marca">
          <figcaption className="text-[15px] font-semibold leading-5">A frase de hoje</figcaption>
          <blockquote lang="en" className="m-0 font-pe-titulo text-[32px] font-light italic leading-[44px]">
            {f.antes}
            <mark className="rounded-[2px] bg-pe-realce px-1.5 font-semibold not-italic text-pe-tinta">{f.destaque}</mark>
            {f.depois}
          </blockquote>
          <p className="m-0 text-[16px] leading-6">{f.pt}</p>
        </figure>
        <p className="m-0 max-w-[480px] text-[15px] leading-[22px] text-pe-tinta-suave">Todos os dias há uma frase nova do trabalho à sua espera aqui.</p>
        </div>
      </section>
      <main className="flex flex-1 flex-col items-center justify-center px-5 py-10 md:p-12">
        <div className="flex w-full max-w-[400px] flex-col gap-7">
          <Link href="/" aria-label="ProEnglish, página inicial" className="self-start">
            <Logo altura={44} />
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}
