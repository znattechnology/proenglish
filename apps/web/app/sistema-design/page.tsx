import { notFound } from "next/navigation";
import { Info, Mic, Volume2 } from "lucide-react";
import {
  Aviso,
  BalaoFala,
  BarraProgresso,
  Botao,
  Cartao,
  Etiqueta,
  Logo,
  MarcaIcone,
  Osso,
  Realce,
  Separadores,
  Vidas,
} from "@/components/pe";
import { DemoInterativa } from "./DemoInterativa";
import { OfertaPlano } from "@/components/pe/subscricao/Oferta";

export const metadata = { title: "Sistema de design | ProEnglish" };

/** Página de referência da base visual. Só existe em desenvolvimento. */
export default function SistemaDesign() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <div className="pe">
      <div className="mx-auto flex max-w-[960px] flex-col gap-16 px-4 py-10 md:px-8">
        <header className="flex flex-col gap-4">
          <Logo versao="azul-assinatura" altura={56} />
          <h1 className="m-0 font-pe-titulo text-pe-titulo-l text-pe-tinta">Sistema de design</h1>
          <p className="m-0 max-w-[60ch] text-pe-tinta-suave">
            Os componentes da base visual nova. Tudo o que está aqui vive dentro de <code>.pe</code> e não mexe nas páginas
            antigas.
          </p>
        </header>

        <Seccao titulo="Letra">
          <p className="m-0 font-pe-titulo text-pe-titulo-xl">Fale inglês no seu trabalho</p>
          <p className="m-0 font-pe-titulo text-pe-titulo-m">Continue a sua lição</p>
          <p className="m-0 font-pe-titulo text-pe-titulo-s">Unidade 3: Reuniões de segurança</p>
          <p className="m-0 font-pe-titulo text-pe-voz italic">Could you send me the drilling report by Friday?</p>
          <p className="m-0 max-w-[65ch] text-pe-corpo-l">
            Cursos por área profissional, 15 minutos por dia e conversa com um tutor de IA. Os números ficam em Montserrat:
            14 950 Kz por mês, 7 dias seguidos, 1 240 pontos.
          </p>
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">Legenda: 2 lições por dia, sem cartão.</p>
        </Seccao>

        <Seccao titulo="Botões">
          <div className="flex flex-wrap items-center gap-3">
            <Botao>Continuar lição</Botao>
            <Botao tipo="secundario">Aula anterior</Botao>
            <Botao tipo="realce">Experimentar grátis</Botao>
            <Botao tipo="perigo">Sair e perder o progresso</Botao>
            <Botao tipo="ligacao">Agora não</Botao>
            <Botao disabled>Verificar</Botao>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Botao tamanho="medio">
              <Mic aria-hidden /> Começar a conversa
            </Botao>
            <Botao tamanho="pequeno" tipo="secundario">
              Exportar
            </Botao>
          </div>
        </Seccao>

        <Seccao titulo="Balões de fala">
          <div className="flex flex-col gap-3">
            <BalaoFala autor="O supervisor pede-lhe um relatório">
              Could you <Realce>send</Realce> me the drilling report by Friday?
            </BalaoFala>
            <BalaoFala quem="aluno">Sure. I will send it on Thursday afternoon.</BalaoFala>
          </div>
        </Seccao>

        <Seccao titulo="Estado e progresso">
          <div className="flex flex-wrap gap-2">
            <Etiqueta>Rascunho</Etiqueta>
            <Etiqueta tipo="certo">Publicado</Etiqueta>
            <Etiqueta tipo="errado">Pagamento falhou</Etiqueta>
            <Etiqueta tipo="realce">Mais escolhido</Etiqueta>
            <Etiqueta tipo="marca">Premium</Etiqueta>
          </div>
          <div className="flex max-w-[420px] flex-col gap-2">
            <div className="flex items-center justify-between text-pe-legenda">
              <span>12 de 30 aulas</span>
              <span className="font-semibold">40%</span>
            </div>
            <BarraProgresso valor={40} rotulo="Progresso no curso" />
          </div>
          <div className="flex items-center gap-6">
            <Vidas quantas={3} />
            <Vidas quantas={1} />
            <Vidas quantas={0} ilimitadas />
          </div>
        </Seccao>

        <Seccao titulo="Avisos">
          <Aviso icone={<Info aria-hidden />}>Incluído no seu Premium. No plano Gratuito pode fazer as 3 primeiras aulas.</Aviso>
          <Aviso tipo="certo">Certo. Depois de &quot;could you&quot; o verbo fica na forma base: send.</Aviso>
          <Aviso tipo="errado">Ainda não. Perdeu uma vida.</Aviso>
        </Seccao>

        <Seccao titulo="Cartões e navegação">
          <Separadores
            rotulo="Cursos"
            activo="Os meus"
            itens={[
              { nome: "Os meus", href: "/sistema-design" },
              { nome: "Explorar", href: "/sistema-design#explorar" },
            ]}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <Cartao>
              <span className="text-pe-legenda text-pe-tinta-suave">Petróleo e Gás, intermédio</span>
              <span className="font-pe-titulo text-pe-titulo-s">Inglês para reuniões de segurança</span>
              <BarraProgresso valor={40} rotulo="Progresso" />
              <span className="text-pe-legenda">12 de 30 aulas</span>
            </Cartao>
            <Cartao className="flex-row items-center gap-4">
              <MarcaIcone tamanho={56}>
                <Volume2 />
              </MarcaIcone>
              <span className="flex flex-col">
                <span className="font-semibold">Rever 12 palavras</span>
                <span className="text-pe-legenda text-pe-tinta-suave">Vocabulário da semana passada</span>
              </span>
            </Cartao>
          </div>
        </Seccao>

        <Seccao titulo="Formulários e escolhas">
          <DemoInterativa />
        </Seccao>

        <Seccao titulo="Oferta num limite">
          <div className="max-w-[440px]">
            <OfertaPlano
              oferta={{
                recurso: "vidas",
                plano: { tipo: "PREMIUM", nome: "Premium", preco_mensal_kz: 14950, preco_anual_kz: 149500, dias_teste: 7, pode_experimentar: true },
                ganhos: ["Vidas ilimitadas", "Lições novas sem limite", "Análises de pronúncia sem limite", "10 minutos de conversa com o tutor por dia"],
                ligacao: "/user/upgrade?plan=PREMIUM",
              }}
              saidas={<p className="m-0 text-center text-pe-legenda text-pe-tinta-suave">As saídas gratuitas ficam aqui (recarregar, saltar, voltar).</p>}
            />
          </div>
        </Seccao>

        <Seccao titulo="A carregar">
          <div className="flex max-w-[420px] flex-col gap-3" aria-busy="true" aria-label="A carregar">
            <Osso className="h-[30px] w-3/5" />
            <Osso className="h-[150px] rounded-pe-fala" />
            <Osso className="h-16 rounded-pe-md" />
          </div>
        </Seccao>
      </div>
    </div>
  );
}

function Seccao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="m-0 border-b border-pe-linha pb-2 font-pe-titulo text-pe-titulo-s">{titulo}</h2>
      {children}
    </section>
  );
}
