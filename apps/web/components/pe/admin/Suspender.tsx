"use client";

import { useState } from "react";
import { Aviso, Botao, Escolha } from "@/components/pe";
import { AreaTexto } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { MOTIVOS, useSuspenderMutation, type MotivoSuspensao } from "@/src/domains/admin/administracao/api";

export function DialogoSuspender({ id, nome, temPlanoPago, aoFechar }: { id: string; nome: string; temPlanoPago: boolean; aoFechar: () => void }) {
  const [suspender, { isLoading }] = useSuspenderMutation();
  const [motivo, setMotivo] = useState<MotivoSuspensao | "">("");
  const [nota, setNota] = useState("");
  const [avisar, setAvisar] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Suspender ${nome}?`} descricao="Deixa de conseguir entrar e as sessões abertas terminam. Os dados, o progresso e os certificados ficam guardados; pode reactivar a conta quando quiser." largura={560}>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setErro(null);
          if (!motivo) return setErro("Escolha um motivo.");
          try {
            await suspender({ id, motivo, nota: nota.trim(), avisar }).unwrap();
            aoFechar();
          } catch (x) {
            setErro(mensagemErro(x, "Não foi possível suspender a conta."));
          }
        }}
      >
        <Escolha rotulo="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value as MotivoSuspensao)}>
          <option value="">Escolha um motivo</option>
          {(Object.keys(MOTIVOS) as MotivoSuspensao[]).map((m) => (
            <option key={m} value={m}>
              {MOTIVOS[m]}
            </option>
          ))}
        </Escolha>
        <AreaTexto rotulo="Nota interna (opcional)" rows={3} maxLength={500} value={nota} onChange={(e) => setNota(e.target.value)} ajuda="Só a administração vê esta nota." />
        <label className="flex items-start gap-3 text-[15px] leading-[22px]">
          <input type="checkbox" checked={avisar} onChange={(e) => setAvisar(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-pe-azul-marca" />
          <span>Avisar a pessoa por email, com o motivo</span>
        </label>
        {temPlanoPago ? <Aviso tipo="info">A subscrição paga fica em pausa enquanto a conta estiver suspensa.</Aviso> : null}
        {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" tipo="perigo" tamanho="medio" disabled={isLoading}>
            {isLoading ? "A suspender…" : "Suspender conta"}
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
