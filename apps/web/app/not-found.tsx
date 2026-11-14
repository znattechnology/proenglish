import Link from "next/link";
import { Destinos, Estado } from "@/components/pe/estados/Estado";

export const metadata = { title: "Página não encontrada | ProEnglish" };

export default function NaoEncontrada() {
  return (
    <Estado
      simbolo="404"
      titulo="Esta página não existe"
      texto="Pode ter mudado de endereço ou a ligação estar incompleta. Escolha por onde continuar:"
      rodape={
        <>
          Chegou aqui por uma ligação nossa? Diga-nos onde, pelos contactos nos{" "}
          <Link href="/termos#contactos" className="text-pe-tinta-suave underline underline-offset-[3px]">
            Termos de utilização
          </Link>
          .
        </>
      }
    >
      <Destinos
        itens={[
          { href: "/user/dashboard", nome: "Início", texto: "O seu painel, com o curso onde ficou" },
          { href: "/user/courses", nome: "Cursos" },
          { href: "/user/laboratory", nome: "Laboratório de prática" },
        ]}
      />
    </Estado>
  );
}
