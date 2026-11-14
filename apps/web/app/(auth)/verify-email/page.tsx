import { Suspense } from "react";
import { VerificarEmail } from "@/components/pe/conta/Codigos";

export const metadata = { title: "Confirmar o email | ProEnglish", description: "Confirme o seu email para activar a conta." };

export default function Page() {
  return (
    <Suspense>
      <VerificarEmail />
    </Suspense>
  );
}
