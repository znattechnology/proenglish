import { useLocalSearchParams } from "expo-router";
import { Jogador } from "@/componentes/licao/Jogador";

/** Leitor de lições do laboratório (ecrã inteiro). */
export default function EcraLicao() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <Jogador key={id} lessonId={String(id)} />;
}
