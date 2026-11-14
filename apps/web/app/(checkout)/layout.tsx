import { ObrigarMudarSenha } from "@/components/pe/conta/ObrigarMudarSenha";
/**
 * Checkout: sem barra lateral nem navegação, só o logótipo e os passos do pagamento.
 * A sessão é verificada no proxy.ts.
 */
export default function LayoutCheckout({ children }: { children: React.ReactNode }) {
  return (
    <div className="pe min-h-dvh">
      <ObrigarMudarSenha>{children}</ObrigarMudarSenha>
    </div>
  );
}
