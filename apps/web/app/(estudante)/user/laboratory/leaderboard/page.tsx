import { redirect } from "next/navigation";

/** A classificação semanal está na página das conquistas. */
export default function Classificacao() {
  redirect("/user/laboratory/achievements#liga");
}
