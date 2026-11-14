"use client";

import { useState } from "react";
import { Aviso, Botao, Campo } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { errosDoServidor, useMudarPalavraPasseMutation } from "@/src/domains/student/perfil/api";

/** Mudar (ou criar, para quem entra com o Google) a palavra-passe. Usado pelo aluno e pelo professor. */
export function MudarPalavraPasse({ temSenha, aberto, aoMudar, aoMudada }: { temSenha: boolean; aberto: boolean; aoMudar: (v: boolean) => void; aoMudada: (mensagem: string) => void }) {
  const [mudar, { isLoading }] = useMudarPalavraPasseMutation();
  const [actual, setActual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeral(null);
    const novos: Record<string, string> = {};
    if (temSenha && !actual) novos.current_password = "Escreva a palavra-passe actual.";
    if (nova.length < 8) novos.new_password = "Use pelo menos 8 caracteres.";
    if (nova !== confirmar) novos.new_password_confirm = "As duas palavras-passe novas não são iguais.";
    setErros(novos);
    if (Object.keys(novos).length) return;
    const r = await mudar({ actual, nova, confirmar });
    if ("error" in r && r.error) {
      const { campos, geral } = errosDoServidor(r.error);
      setErros(campos);
      setGeral(geral);
      return;
    }
    aoMudada(r.data!.message);
    aoMudar(false);
  };

  return (
    <Dialogo
      aberto={aberto}
      aoMudar={aoMudar}
      titulo={temSenha ? "Mudar a palavra-passe" : "Criar uma palavra-passe"}
      descricao={temSenha ? "Depois de mudar, as sessões abertas noutros dispositivos terminam." : "Continua a poder entrar com o Google. A palavra-passe serve para entrar também com o email."}
    >
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        {temSenha ? (
          <Campo rotulo="Palavra-passe actual" type="password" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} erro={erros.current_password} />
        ) : null}
        <Campo rotulo="Palavra-passe nova" type="password" autoComplete="new-password" value={nova} onChange={(e) => setNova(e.target.value)} erro={erros.new_password} ajuda="Pelo menos 8 caracteres. Evite palavras comuns." />
        <Campo rotulo="Repita a palavra-passe nova" type="password" autoComplete="new-password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} erro={erros.new_password_confirm} />
        {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
        <Botao type="submit" larguraTotal disabled={isLoading}>
          {isLoading ? "A guardar…" : temSenha ? "Mudar a palavra-passe" : "Criar a palavra-passe"}
        </Botao>
      </form>
    </Dialogo>
  );
}

