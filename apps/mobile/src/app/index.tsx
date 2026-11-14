import { Redirect } from "expo-router";
import { useSessao } from "@/sessao/ContextoSessao";

export default function Inicio() {
  const { estado } = useSessao();
  return <Redirect href={estado === "com-sessao" ? "/inicio" : "/entrar"} />;
}
