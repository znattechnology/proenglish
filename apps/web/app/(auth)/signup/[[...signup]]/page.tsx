import { Suspense } from "react";
import { CriarConta } from "@/components/pe/conta/CriarConta";

export const metadata = { title: "Criar conta | ProEnglish", description: "Crie a sua conta ProEnglish, grátis e sem cartão." };

export default function Page() {
  return (
    <Suspense>
      <CriarConta />
    </Suspense>
  );
}
