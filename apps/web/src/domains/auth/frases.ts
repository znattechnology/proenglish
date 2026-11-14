/**
 * "A frase de hoje" das páginas de entrada: frases reais do trabalho em Angola,
 * com a palavra a aprender destacada e o contexto em que se usa.
 */
export type FraseDoDia = { antes: string; destaque: string; depois: string; pt: string };

export const FRASES: FraseDoDia[] = [
  { antes: "Could you walk me through the ", destaque: "figures", depois: "?", pt: "Pode explicar-me os números, passo a passo? Usa-se em reuniões, quando quer que alguém detalhe um relatório." },
  { antes: "Let's ", destaque: "follow up", depois: " on this next week.", pt: "Voltamos a este assunto na próxima semana. Bom para fechar uma reunião sem deixar o tema cair." },
  { antes: "I'll have the report ready ", destaque: "by", depois: " Friday.", pt: "Terei o relatório pronto até sexta. \"By\" marca o prazo limite, não o dia exacto." },
  { antes: "Please ", destaque: "make sure", depois: " the valve is closed.", pt: "Certifique-se de que a válvula está fechada. Frase de todos os dias nas instruções de segurança." },
  { antes: "Sorry, could you ", destaque: "repeat", depois: " that more slowly?", pt: "Desculpe, pode repetir mais devagar? A frase mais útil numa chamada difícil." },
  { antes: "We need to ", destaque: "sort out", depois: " the delay with the supplier.", pt: "Temos de resolver o atraso com o fornecedor. \"Sort out\" é resolver um problema prático." },
  { antes: "Thank you for your ", destaque: "patience", depois: ".", pt: "Obrigado pela sua paciência. Para responder a um cliente que esperou." },
  { antes: "I'm calling ", destaque: "regarding", depois: " your invoice.", pt: "Estou a ligar por causa da sua factura. Mais formal do que \"about\"." },
  { antes: "Could we ", destaque: "reschedule", depois: " the meeting to Thursday?", pt: "Podemos mudar a reunião para quinta-feira? Para propor outra data com educação." },
  { antes: "The shift ", destaque: "handover", depois: " is at six.", pt: "A passagem de turno é às seis. Vocabulário de quem trabalha por turnos." },
  { antes: "Let me ", destaque: "double-check", depois: " and get back to you.", pt: "Deixe-me confirmar e já lhe digo. Ganha tempo sem parecer inseguro." },
  { antes: "What's the ", destaque: "deadline", depois: " for this?", pt: "Qual é o prazo para isto? Pergunte cedo, antes de aceitar uma tarefa." },
  { antes: "I'd like to ", destaque: "raise", depois: " a concern about safety.", pt: "Gostaria de levantar uma preocupação sobre segurança. \"Raise\" é trazer um tema à discussão." },
  { antes: "Can you ", destaque: "cc", depois: " my manager on that email?", pt: "Pode pôr o meu chefe em cópia nesse email? \"cc\" lê-se \"si-si\"." },
];

/** A frase do dia em Luanda (muda à meia-noite de Angola). */
export function fraseDeHoje(agora = new Date()): FraseDoDia {
  const dia = new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Luanda", year: "numeric", month: "2-digit", day: "2-digit" }).format(agora);
  const n = Math.floor(Date.parse(`${dia}T00:00:00Z`) / 86_400_000);
  return FRASES[((n % FRASES.length) + FRASES.length) % FRASES.length];
}
