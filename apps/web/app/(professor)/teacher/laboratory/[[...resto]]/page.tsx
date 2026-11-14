import { redirect } from "next/navigation";

/** Endereços da área antiga do professor (laboratório): vão para os cursos de prática. */
export default function LaboratorioAntigo() {
  redirect("/teacher/practice");
}
