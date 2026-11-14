/** A verificação mostra o nome de uma pessoa: não deve aparecer nos motores de busca. */
export const metadata = { title: "Verificação de certificado | ProEnglish", robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
