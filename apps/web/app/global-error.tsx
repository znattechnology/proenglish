"use client";

/**
 * Último recurso: o próprio layout falhou, por isso não há CSS nem componentes garantidos.
 * Tudo com estilos inline, nas cores da marca.
 */
export default function ErroGlobal({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const codigo = error.digest ? `ERR-${error.digest.slice(0, 8).toUpperCase()}` : null;
  return (
    <html lang="pt">
      <body style={{ margin: 0, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#ffffff", color: "#14143f", fontFamily: "system-ui, sans-serif" }}>
        <main style={{ maxWidth: 520, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          <div aria-hidden style={{ width: 88, height: 88, borderRadius: "28px 28px 28px 0", background: "#000066", color: "#ffc72c", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 40, fontWeight: 700 }}>!</div>
          <h1 style={{ margin: 0, fontSize: 28, lineHeight: "36px" }}>A ProEnglish não abriu</h1>
          <p style={{ margin: 0, color: "#54577a", lineHeight: "26px" }}>O problema é do nosso lado. O seu progresso está guardado. Tente outra vez daqui a um momento.</p>
          {codigo ? <p style={{ margin: 0, color: "#54577a", fontSize: 14 }}>Código para o apoio: {codigo}</p> : null}
          <button type="button" onClick={reset} style={{ minHeight: 52, border: 0, borderRadius: 6, background: "#000066", color: "#ffffff", fontSize: 16, fontWeight: 600, cursor: "pointer" }}>
            Tentar outra vez
          </button>
        </main>
      </body>
    </html>
  );
}
