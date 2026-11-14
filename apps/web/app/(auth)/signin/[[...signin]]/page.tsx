import { Suspense } from "react";
import { Entrar } from "@/components/pe/conta/Entrar";

export const metadata = { title: "Entrar | ProEnglish", description: "Entre na sua conta ProEnglish." };

export default function Page() {
  return (
    <Suspense>
      <Entrar />
    </Suspense>
  );
}
