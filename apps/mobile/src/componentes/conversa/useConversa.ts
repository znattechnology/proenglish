/**
 * Uma conversa com o tutor, do "a ligar" ao resumo (igual a apps/web/components/pe/conversa/useConversa.ts).
 *
 * Modo "vapi": voz em tempo real (chamada.ts); o tutor ouve enquanto o microfone estiver ligado.
 * Modo "simulado" (ensaio, sem chamadas pagas): o aluno escreve e o telemóvel lê a resposta do tutor.
 * Em ambos dá para escrever em vez de falar (menos no exame e no teste de nível: `semTexto`).
 *
 * O servidor não confia na app: na voz, a nota, os minutos e o perfil de fala vêm da chamada
 * confirmada pelo Vapi. A app manda o id da chamada, a transcrição (só para mostrar) e o que só pode
 * BAIXAR o resultado: as falas escritas e as frases-alvo que o aluno viu em inglês (`revelar`).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { pedir } from "@/api/base";
import {
  caminhoTerminar,
  useConversaAjudaMutation,
  useConversaAjusteMutation,
  useConversaLigadaMutation,
  useConversaResponderMutation,
  useConversaTerminarMutation,
  type Ajuste,
  type Fala,
  type ModoConversa,
  type NovaSessao,
  type Resumo,
} from "@/dominios/conversa/api";
import { ligar, vozDisponivel, type Chamada } from "./chamada";
import { falar, pararDeFalar } from "./voz";

export type OpcoesConversa = { semAjustes?: boolean; semTexto?: boolean };
export type EstadoConversa = "a_ligar" | "em_curso" | "a_terminar" | "terminada" | "erro";
export type FalaViva = Fala & { id: string; ajuste?: Ajuste | null };

let contador = 0;
const novoId = () => `f${++contador}`;

export function useConversa(sessao: NovaSessao, modo: ModoConversa, chavePublica: string | null, opcoes: OpcoesConversa = {}) {
  const simulado = modo === "simulado";
  const [estado, setEstado] = useState<EstadoConversa>(simulado ? "em_curso" : "a_ligar");
  const [erro, setErro] = useState<string | null>(null);
  const [falas, setFalas] = useState<FalaViva[]>(() => (simulado && sessao.primeira_fala ? [{ id: novoId(), quem: "tutor", texto: sessao.primeira_fala }] : []));
  const [parcial, setParcial] = useState<{ quem: "tutor" | "aluno"; texto: string } | null>(null);
  const [tutorAFalar, setTutorAFalar] = useState(simulado);
  const [microfone, setMicrofone] = useState(modo === "vapi");
  const [segundos, setSegundos] = useState(0);
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [reveladas, setReveladas] = useState<string[]>([]);

  const [pedirAjuste] = useConversaAjusteMutation();
  const [responder] = useConversaResponderMutation();
  const [terminarApi] = useConversaTerminarMutation();
  const [avisarLigada] = useConversaLigadaMutation();
  const [avisarAjuda] = useConversaAjudaMutation();

  const chamada = useRef<Chamada | null>(null);
  const falasRef = useRef<FalaViva[]>([]);
  const terminada = useRef(false);
  const decorridos = useRef(0);
  const terminouNoLimite = useRef(false);
  const semAjustes = useRef(Boolean(opcoes.semAjustes));
  const reveladasRef = useRef<string[]>([]);
  const terminarRef = useRef<() => Promise<void>>(async () => {});
  const saidaPendente = useRef<ReturnType<typeof setTimeout> | null>(null);
  const microfoneRef = useRef(modo === "vapi");

  useEffect(() => {
    falasRef.current = falas;
  }, [falas]);
  useEffect(() => {
    microfoneRef.current = microfone;
  }, [microfone]);

  const corpoTerminar = useCallback(
    () => ({
      transcricao: falasRef.current.map(({ quem, texto, escrito }) => ({ quem, texto, ...(escrito ? { escrito: true } : {}) })),
      call_id: chamada.current?.id ?? null,
      reveladas: reveladasRef.current,
    }),
    []
  );

  const juntar = useCallback(
    (quem: "tutor" | "aluno", texto: string, escrito = false) => {
      const t = texto.trim();
      if (!t) return null;
      const id = novoId();
      setFalas((f) => {
        // O Vapi parte uma resposta do tutor em vários "finais": juntam-se se forem seguidos.
        const ultima = f[f.length - 1];
        if (ultima && ultima.quem === quem && quem === "tutor") return [...f.slice(0, -1), { ...ultima, texto: `${ultima.texto} ${t}` }];
        return [...f, { id, quem, texto: t, ...(escrito ? { escrito: true } : {}) }];
      });
      if (quem === "aluno" && t.split(/\s+/).length >= 3 && !semAjustes.current) {
        pedirAjuste({ id: sessao.id, frase: t })
          .unwrap()
          .then((r) => setFalas((f) => f.map((x) => (x.id === id ? { ...x, ajuste: r.ajuste } : x))))
          .catch((e: { status?: number }) => {
            if (e?.status === 409) semAjustes.current = true; // o tempo acabou: deixa de pedir ajustes
            setFalas((f) => f.map((x) => (x.id === id ? { ...x, ajuste: null } : x)));
          });
      }
      return id;
    },
    [pedirAjuste, sessao.id]
  );

  // Resposta do tutor no modo de ensaio.
  const respostaSimulada = useCallback(
    async (texto: string, escrito = false) => {
      setTutorAFalar(true);
      try {
        const r = await responder({ id: sessao.id, texto, escrito }).unwrap();
        if (terminada.current) return;
        juntar("tutor", r.tutor);
        falar(r.tutor, () => setTutorAFalar(false));
      } catch {
        setTutorAFalar(false);
        setErro("O tutor não respondeu. Tente outra vez.");
      }
    },
    [juntar, responder, sessao.id]
  );

  const terminar = useCallback(async () => {
    if (terminada.current) return;
    terminada.current = true;
    setEstado("a_terminar");
    const corpo = corpoTerminar();
    chamada.current?.parar();
    pararDeFalar();
    setTutorAFalar(false);
    setMicrofone(false);
    try {
      const r = await terminarApi({ id: sessao.id, ...corpo }).unwrap();
      setResumo(r);
      setEstado("terminada");
    } catch {
      terminada.current = false;
      setErro("Não conseguimos guardar a conversa. Tente terminar outra vez.");
      setEstado("em_curso");
    }
  }, [sessao.id, terminarApi, corpoTerminar]);
  useEffect(() => {
    terminarRef.current = terminar;
  }, [terminar]);

  // Ligar.
  useEffect(() => {
    let cancelado = false;
    if (modo === "simulado") {
      const abrir = setTimeout(() => {
        void avisarLigada({ id: sessao.id });
        falar(sessao.primeira_fala, () => setTutorAFalar(false));
      }, 0);
      return () => {
        clearTimeout(abrir);
        pararDeFalar();
      };
    }
    (async () => {
      try {
        const voz = vozDisponivel();
        if (!voz.disponivel) {
          // Sem voz neste telemóvel: fecha já a sessão no servidor (não chegou a ligar, não gasta minutos).
          terminada.current = true;
          void pedir(caminhoTerminar(sessao.id), { method: "POST", body: JSON.stringify(corpoTerminar()) }).catch(() => {});
          setErro(voz.motivo);
          setEstado("erro");
          return;
        }
        if (!chavePublica || !sessao.vapi) throw new Error("sem_vapi");
        const c = await ligar(chavePublica, sessao.vapi.assistant_id, sessao.vapi.assistant_overrides, {
          aoLigar: () => {
            setEstado((e) => (e === "a_ligar" ? "em_curso" : e));
            // O id da chamada: o servidor vai buscá-la ao Vapi (duração, transcrição, gravação).
            void avisarLigada({ id: sessao.id, call_id: chamada.current?.id ?? undefined });
          },
          aoTutorAFalar: setTutorAFalar,
          aoTranscricao: (quem, texto, final) => {
            if (final) {
              setParcial(null);
              juntar(quem, texto);
            } else setParcial({ quem, texto });
          },
          aoTerminar: () => {
            if (!terminada.current) void terminarRef.current();
          },
          aoErro: (motivo) => {
            if (terminada.current) return;
            setErro(motivo === "microfone" ? "O telemóvel não deu acesso ao microfone. Autorize o microfone nas definições e tente outra vez." : "A ligação ao tutor falhou. Verifique a Internet e tente outra vez.");
            setEstado((e) => (e === "a_ligar" ? "erro" : e));
          },
        });
        if (cancelado) return c.parar();
        chamada.current = c;
        // aoLigar pode ter chegado antes de sabermos o id: avisa outra vez (é idempotente).
        if (c.id) void avisarLigada({ id: sessao.id, call_id: c.id });
      } catch {
        if (cancelado) return;
        setErro("Não foi possível ligar ao tutor. Tente outra vez daqui a pouco.");
        setEstado("erro");
      }
    })();
    return () => {
      cancelado = true;
      chamada.current?.parar();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- liga uma vez por sessão
  }, [sessao.id]);

  // Se o tutor não atender em 25 s, mostra o erro em vez de ficar a "ligar" para sempre.
  useEffect(() => {
    if (estado !== "a_ligar") return;
    const t = setTimeout(() => {
      chamada.current?.parar();
      setErro("O tutor não atendeu. Verifique a Internet e tente outra vez.");
      setEstado("erro");
    }, 25_000);
    return () => clearTimeout(t);
  }, [estado]);

  // Relógio (o servidor recalcula a duração; isto é só para mostrar e para parar no limite).
  useEffect(() => {
    if (estado !== "em_curso") return;
    const t = setInterval(() => {
      decorridos.current += 1;
      setSegundos(decorridos.current);
      if (decorridos.current >= sessao.max_segundos && !terminouNoLimite.current) {
        terminouNoLimite.current = true; // se falhar, não repete a cada segundo: fica o botão Terminar
        void terminarRef.current();
      }
    }, 1000);
    return () => clearInterval(t);
  }, [estado, sessao.max_segundos]);

  // Se o aluno sair do ecrã a meio, a conversa é guardada na mesma.
  useEffect(() => {
    if (saidaPendente.current) clearTimeout(saidaPendente.current); // voltou a montar (modo estrito): não era uma saída
    return () => {
      saidaPendente.current = setTimeout(() => {
        if (terminada.current) return;
        terminada.current = true;
        chamada.current?.parar();
        pararDeFalar();
        void pedir(caminhoTerminar(sessao.id), { method: "POST", body: JSON.stringify(corpoTerminar()) }).catch(() => {});
      }, 0);
    };
  }, [sessao.id, corpoTerminar]);

  const alternarMicrofone = useCallback(() => {
    if (estado !== "em_curso" || modo !== "vapi") return;
    const novo = !microfoneRef.current;
    chamada.current?.silenciar(!novo);
    microfoneRef.current = novo;
    setMicrofone(novo);
  }, [estado, modo]);

  const escrever = useCallback(
    (texto: string) => {
      const t = texto.trim();
      if (!t || estado !== "em_curso" || (opcoes.semTexto && modo === "vapi")) return;
      setErro(null);
      juntar("aluno", t, true);
      if (modo === "vapi" && chamada.current) {
        // Avisa já (antes do fim): as frases-alvo escritas contam só "com ajuda".
        void avisarAjuda({ id: sessao.id, escrito: t });
        chamada.current.enviarTexto(t);
      } else {
        void respostaSimulada(t, true);
      }
    },
    [avisarAjuda, estado, juntar, modo, opcoes.semTexto, respostaSimulada, sessao.id]
  );

  /** O aluno pediu para ver uma frase-alvo em inglês: nesta conversa conta no máximo "com ajuda". */
  const revelar = useCallback(
    (en: string) => {
      if (reveladasRef.current.includes(en)) return;
      reveladasRef.current = [...reveladasRef.current, en];
      setReveladas(reveladasRef.current);
      void avisarAjuda({ id: sessao.id, revelada: en });
    },
    [avisarAjuda, sessao.id]
  );

  const ouvirOutraVez = useCallback(() => {
    const ultima = [...falasRef.current].reverse().find((f) => f.quem === "tutor");
    if (!ultima) return;
    // Lido no telemóvel com o microfone do Vapi desligado, para não entrar na transcrição.
    const c = modo === "vapi" ? chamada.current : null;
    c?.silenciar(true);
    setTutorAFalar(true);
    falar(ultima.texto, () => {
      setTutorAFalar(false);
      c?.silenciar(!microfoneRef.current);
    });
  }, [modo]);

  return {
    estado,
    erro,
    limparErro: () => setErro(null),
    falas,
    parcial,
    tutorAFalar,
    microfone,
    segundos,
    resumo,
    terminar,
    alternarMicrofone,
    escrever,
    ouvirOutraVez,
    reveladas,
    revelar,
    /** No modo de ensaio não há reconhecimento de fala no telemóvel: responde-se a escrever. */
    soEscrita: simulado,
  };
}

export type Conversa = ReturnType<typeof useConversa>;
