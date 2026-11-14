import { Suspense } from "react";
import { Checkout } from "@/components/pe/subscricao/Checkout";

export default function PaginaCheckout() {
  return (
    <Suspense>
      <Checkout />
    </Suspense>
  );
}
