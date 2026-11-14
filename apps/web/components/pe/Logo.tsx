import Image from "next/image";

const FICHEIROS = {
  azul: { src: "/logo/Logo_azul.png", w: 1216, h: 946 },
  "azul-assinatura": { src: "/logo/Logo_azul_com_assinatura.png", w: 2022, h: 946 },
  branco: { src: "/logo/Logo_Branco.png", w: 1216, h: 946 },
  "branco-assinatura": { src: "/logo/Logo_Branco_com_assinatura.png", w: 2022, h: 946 },
} as const;

/**
 * Logótipo ProEnglish. Azul sobre fundos claros, branco sobre azul-marca.
 * A versão com assinatura ("Fluência ao alcance de todos") é só para páginas públicas.
 */
export function Logo({
  versao = "azul",
  altura = 36,
  className,
}: {
  versao?: keyof typeof FICHEIROS;
  altura?: number;
  className?: string;
}) {
  const f = FICHEIROS[versao];
  return (
    <Image
      src={f.src}
      alt="ProEnglish"
      width={Math.round((f.w / f.h) * altura)}
      height={altura}
      priority
      className={className}
    />
  );
}
