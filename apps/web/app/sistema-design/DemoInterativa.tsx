"use client";

import { useState } from "react";
import { AreaTexto, Botao, Campo, Escolha, Interruptor, Pilulas } from "@/components/pe";

const FILTROS = ["Todos", "Activos", "Rascunhos"] as const;

export function DemoInterativa() {
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>("Todos");
  const [lembrete, setLembrete] = useState(true);
  const [email, setEmail] = useState("maria.santos@empresa");

  const erro = email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) ? "Falta o domínio no email, por exemplo @empresa.ao." : undefined;

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <form className="flex flex-col gap-4" onSubmit={(e) => e.preventDefault()}>
        <Campo rotulo="Nome completo" defaultValue="Maria Santos" autoComplete="name" />
        <Campo rotulo="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} erro={erro} autoComplete="email" />
        <Escolha rotulo="Área profissional" defaultValue="Petróleo e Gás" ajuda="Escolhe os cursos que lhe sugerimos.">
          <option>Petróleo e Gás</option>
          <option>Banca</option>
          <option>Saúde</option>
          <option>Direito</option>
          <option>Tecnologia</option>
          <option>Gestão</option>
        </Escolha>
        <AreaTexto rotulo="Quer contar mais? (opcional)" placeholder="O que mais gostou? O que podemos melhorar?" />
        <Botao type="submit" larguraTotal>
          Guardar alterações
        </Botao>
      </form>
      <div className="flex flex-col gap-6">
        <Pilulas rotulo="Estado" opcoes={FILTROS} valor={filtro} aoMudar={setFiltro} />
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">A mostrar: {filtro.toLowerCase()}.</p>
        <div>
          <Interruptor
            rotulo="Lembrete diário"
            descricao="Um aviso por dia, só se ainda não tiver praticado."
            ligado={lembrete}
            aoMudar={setLembrete}
          />
          <Interruptor rotulo="Novidades da plataforma" descricao="Funcionalidades novas, uma vez por mês." ligado={false} aoMudar={() => {}} />
        </div>
      </div>
    </div>
  );
}
