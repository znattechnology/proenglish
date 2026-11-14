import { ObrigarMudarSenha } from "@/components/pe/conta/ObrigarMudarSenha";
/**
 * Ecrã da lição: ocupa o ecrã inteiro, sem barra lateral nem navegação,
 * para o estudante se concentrar no exercício. A sessão é verificada no proxy.ts.
 */
export default function LayoutLicao({ children }: { children: React.ReactNode }) {
  return (
    <div className="pe min-h-dvh">
      <ObrigarMudarSenha>{children}</ObrigarMudarSenha>
    </div>
  );
}
