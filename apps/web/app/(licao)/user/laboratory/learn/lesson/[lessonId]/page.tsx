import { Jogador } from "@/components/pe/licao/Jogador";

export default async function PaginaLicao({ params }: { params: Promise<{ lessonId: string }> }) {
  const { lessonId } = await params;
  return <Jogador key={lessonId} lessonId={lessonId} />;
}
