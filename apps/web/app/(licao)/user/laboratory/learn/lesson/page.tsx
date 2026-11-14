import { redirect } from "next/navigation";

/** Endereço antigo sem lição: o trilho indica qual é a lição actual. */
export default function SemLicao() {
  redirect("/user/laboratory/learn");
}
