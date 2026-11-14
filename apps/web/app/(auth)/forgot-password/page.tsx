import { Suspense } from "react";
import { RecuperarSenha } from "@/components/pe/conta/Codigos";

export const metadata = { title: "Recuperar a palavra-passe | ProEnglish", description: "Crie uma palavra-passe nova com um código enviado por email." };

export default function Page() {
  return (
    <Suspense>
      <RecuperarSenha />
    </Suspense>
  );
}
