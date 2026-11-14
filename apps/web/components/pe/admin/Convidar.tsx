"use client";

import { useState } from "react";
import { Aviso, Botao, Campo, Escolha, Interruptor } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useOpcoesQuery } from "@/src/domains/teacher/professor/api";
import { useConvidarMutation } from "@/src/domains/admin/administracao/api";

/** Convidar um professor: recebe um email com uma ligação para criar a conta (vale 7 dias). */
export function DialogoConvidar({ aoFechar }: { aoFechar: () => void }) {
  const { data: opcoes } = useOpcoesQuery("video");
  const [convidar, { isLoading }] = useConvidarMutation();
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [area, setArea] = useState("");
  const [livre, setLivre] = useState(false);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [enviado, setEnviado] = useState<string | null>(null);
  const areas = opcoes?.areas.filter((a) => !a.legado) ?? [];

  if (enviado)
    return (
      <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo="Convite enviado" descricao={`Enviámos o convite para ${enviado}. A ligação vale 7 dias.`}>
        <Botao tamanho="medio" className="self-end" onClick={aoFechar}>
          Fechar
        </Botao>
      </Dialogo>
    );

  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo="Convidar professor" descricao="A pessoa recebe um email com uma ligação para criar a conta de professor. A ligação vale 7 dias." largura={520}>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setGeral(null);
          const er: Record<string, string> = {};
          if (!/^\S+@\S+\.\S+$/.test(email.trim())) er.email = "Escreva um email válido.";
          if (nome.trim().length < 2) er.nome = "Escreva o nome da pessoa.";
          setErros(er);
          if (Object.keys(er).length) return;
          try {
            const c = await convidar({ email: email.trim().toLowerCase(), nome: nome.trim(), area: area || areas[0]?.valor || "", publica_sem_revisao: livre }).unwrap();
            if (c.email_enviado === false) {
              setGeral(c.message ?? "O convite foi criado, mas o email não foi enviado. Use “Reenviar” na lista de convites.");
              return;
            }
            setEnviado(email.trim().toLowerCase());
          } catch (x) {
            setErros(errosPorCampo(x));
            setGeral(mensagemErro(x, "Não foi possível enviar o convite."));
          }
        }}
      >
        <Campo rotulo="Email" type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} erro={erros.email} />
        <Campo rotulo="Nome" value={nome} onChange={(e) => setNome(e.target.value)} erro={erros.nome} />
        <Escolha rotulo="Área principal" value={area || areas[0]?.valor || ""} onChange={(e) => setArea(e.target.value)} erro={erros.area}>
          {areas.map((a) => (
            <option key={a.valor} value={a.valor}>
              {a.nome}
            </option>
          ))}
        </Escolha>
        <Interruptor rotulo="Pode publicar cursos sem revisão" descricao="Só para professores de confiança: os cursos entram logo no catálogo, sem passar pela equipa." ligado={livre} aoMudar={setLivre} />
        {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" tamanho="medio" disabled={isLoading}>
            {isLoading ? "A enviar…" : "Enviar convite"}
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
