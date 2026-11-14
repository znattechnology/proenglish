import { Suspense } from "react";
import { ConfirmarEmailNovo } from "@/components/pe/conta/ConfirmarEmailNovo";

export const metadata = { title: "Confirmar o email novo | ProEnglish", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <Suspense>
      <ConfirmarEmailNovo />
    </Suspense>
  );
}
