"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { URL_TERMINAR, useAjudaMutation, useAjusteMutation, useLigadaMutation, useResponderMutation, useTerminarMutation, type Ajuste, type Fala, type NovaSessao, type Resumo } from "@/src/domains/student/conversa/api";

/**
 * Uma conversa com o tutor, do "a ligar" ao resumo.
 * Modo "vapi": voz em tempo real pelo Vapi (o tutor ouve enquanto o microfone estiver ligado).
 * Modo "simulado": sem chamadas pagas; o browser reconhece a fala (quando sabe) e lê a resposta do tutor.
 * Em ambos os modos dá para escrever em vez de falar (menos no exame e no teste de nível: `semTexto`).
 *
 * O servidor não confia no que o browser lhe diz: na voz, a nota, os minutos e o perfil de fala vêm
 * da chamada confirmada pelo serviço de voz. O browser manda o id da chamada (para o servidor a ir
 * buscar), a transcrição (só para mostrar) e o que só pode BAIXAR o resultado: as falas escritas e as
 * frases-alvo que o aluno viu em inglês (`revelar`).
 */
export type OpcoesConversa = { semAjustes?: boolean; semTexto?: boolean };

export type Estado = "a_ligar" | "em_curso" | "a_terminar" | "terminada" | "erro";
export type FalaViva = Fala & { id: string; ajuste?: Ajuste | null };

type Reconhecedor = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
};

// O SDK do Vapi não exporta tipos úteis para os eventos; só usamos isto.
type VapiCliente = {
  on: (evento: string, f: (...a: never[]) => void) => void;
  start: (assistente: string, overrides?: Record<string, unknown>) => Promise<unknown | null>;
  stop: () => void;
  setMuted: (m: boolean) => void;
  say: (texto: string) => void;
  send: (m: unknown) => void;
};

let contador = 0;
const novoId = () => `f${++contador}`;

/**
 * Lê um texto em inglês com a voz do browser.
 * Prefere vozes locais do sistema: as vozes "Google" do Chrome são geradas na rede,
 * demoram a começar e engasgam-se a meio.
 */
// Vozes naturais conhecidas (macOS, Windows, Android), pela ordem em que as preferimos.
const PREFERIDAS = ["Daniel", "Serena", "Kate", "Arthur", "Martha", "Microsoft Sonia", "Microsoft Libby", "Microsoft Ryan", "Microsoft Hazel", "Samantha", "Karen", "Moira", "Tessa", "Microsoft Aria", "Microsoft Jenny", "Microsoft Zira"];
// Vozes de brincadeira do macOS, que também se dizem "inglês".
const EVITAR = /^(Albert|Bahh|Bells|Boing|Bubbles|Borbulhar|Cellos|Good News|Bad News|Boas notícias|Más notícias|Jester|Organ|Órgão|Superstar|Trinoids|Whisper|Wobble|Zarvox|Oscilador|Grandma|Grandpa|Junior|Júnior|Ralph|Fred|Kathy)\b/i;

function escolherVoz() {
  const en = window.speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-").startsWith("en") && !EVITAR.test(v.name));
  for (const nome of PREFERIDAS) {
    const v = en.find((x) => x.localService && x.name.startsWith(nome));
    if (v) return v;
  }
  const local = en.filter((v) => v.localService);
  return local.find((v) => v.lang.replace("_", "-") === "en-GB") ?? local[0] ?? en.find((v) => v.lang.replace("_", "-") === "en-GB") ?? en[0] ?? null;
}

let esperaFala: ReturnType<typeof setTimeout> | null = null;

function falarNoBrowser(texto: string, aoAcabar?: () => void) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return aoAcabar?.();
  const sintese = window.speechSynthesis;
  if (esperaFala) clearTimeout(esperaFala);
  if (sintese.speaking || sintese.pending) sintese.cancel();
  const u = new SpeechSynthesisUtterance(texto);
  u.lang = "en-GB";
  u.rate = 1;
  let acabou = false;
  const fim = () => {
    if (acabou) return;
    acabou = true;
    aoAcabar?.();
  };
  u.onend = fim;
  u.onerror = fim;
  const falar = () => {
    const voz = escolherVoz();
    if (voz) {
      u.voice = voz;
      u.lang = voz.lang;
    }
    sintese.speak(u);
  };
  // Falar logo a seguir a cancel() engasga o Chrome; e as vozes podem ainda não ter carregado.
  esperaFala = setTimeout(() => {
    esperaFala = null;
    if (sintese.getVoices().length) return falar();
    let feito = false;
    const aoCarregar = () => {
      if (feito) return;
      feito = true;
      sintese.removeEventListener("voiceschanged", aoCarregar);
      falar();
    };
    sintese.addEventListener("voiceschanged", aoCarregar);
    setTimeout(aoCarregar, 600);
  }, 60);
}

export function reconhecimentoDisponivel() {
  if (typeof window === "undefined") return false;
  const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return Boolean(w.SpeechRecognition ?? w.webkitSpeechRecognition);
}

export function useConversa(sessao: NovaSessao, modo: "vapi" | "simulado", chavePublica: string | null, opcoes: OpcoesConversa = {}) {
  const simulado = modo === "simulado";
  // No modo simulado o tutor abre a conversa logo, sem esperar por uma ligação.
  const [estado, setEstado] = useState<Estado>(simulado ? "em_curso" : "a_ligar");
  const [erro, setErro] = useState<string | null>(null);
  const [falas, setFalas] = useState<FalaViva[]>(() => (simulado && sessao.primeira_fala ? [{ id: novoId(), quem: "tutor", texto: sessao.primeira_fala }] : []));
  const [parcial, setParcial] = useState<{ quem: "tutor" | "aluno"; texto: string } | null>(null);
  const [tutorAFalar, setTutorAFalar] = useState(simulado);
  const [microfone, setMicrofone] = useState(modo === "vapi");
  const [segundos, setSegundos] = useState(0);
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [reveladas, setReveladas] = useState<string[]>([]);

  const [pedirAjuste] = useAjusteMutation();
  const [responder] = useResponderMutation();
  const [terminarApi] = useTerminarMutation();
  const [avisarLigada] = useLigadaMutation();
  const [avisarAjuda] = useAjudaMutation();

  const vapi = useRef<VapiCliente | null>(null);
  const idChamada = useRef<string | null>(null);
  const reconhecedor = useRef<Reconhecedor | null>(null);
  const falasRef = useRef<FalaViva[]>([]);
  const terminada = useRef(false);
  const decorridos = useRef(0);
  const terminouNoLimite = useRef(false);
  const semAjustes = useRef(Boolean(opcoes.semAjustes));
  const reveladasRef = useRef<string[]>([]);
  const terminarRef = useRef<() => Promise<void>>(async () => {});
  const saidaPendente = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    falasRef.current = falas;
  }, [falas]);

  const transcricao = useCallback((): Fala[] => falasRef.current.map(({ quem, texto, escrito }) => ({ quem, texto, ...(escrito ? { escrito: true } : {}) })), []);
  const corpoTerminar = useCallback(() => ({ transcricao: transcricao(), call_id: idChamada.current, reveladas: reveladasRef.current }), [transcricao]);

  const juntar = useCallback(
    (quem: "tutor" | "aluno", texto: string, escrito = false) => {
      const t = texto.trim();
      if (!t) return null;
      const id = novoId();
      setFalas((f) => {
        // O Vapi parte uma resposta em vários "finais"; juntamo-los se forem da mesma pessoa seguidos.
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

  // Resposta do tutor no modo simulado (e quando se escreve no modo simulado).
  const respostaSimulada = useCallback(
    async (texto: string, escrito = false) => {
      setTutorAFalar(true);
      try {
        const r = await responder({ id: sessao.id, texto, escrito }).unwrap();
        if (terminada.current) return;
        juntar("tutor", r.tutor);
        falarNoBrowser(r.tutor, () => setTutorAFalar(false));
      } catch {
        setTutorAFalar(false);
        setErro("O tutor não respondeu. Tente dizer outra vez.");
      }
    },
    [juntar, responder, sessao.id]
  );

  const terminar = useCallback(async () => {
    if (terminada.current) return;
    terminada.current = true;
    setEstado("a_terminar");
    try {
      vapi.current?.stop();
    } catch {}
    reconhecedor.current?.abort();
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setTutorAFalar(false);
    setMicrofone(false);
    try {
      const r = await terminarApi({ id: sessao.id, ...corpoTerminar() }).unwrap();
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
        void avisarLigada(sessao.id);
        falarNoBrowser(sessao.primeira_fala, () => setTutorAFalar(false));
      }, 0);
      return () => {
        clearTimeout(abrir);
        cancelado = true;
        window.speechSynthesis?.cancel();
        reconhecedor.current?.abort();
      };
    }
    (async () => {
      try {
        if (!chavePublica || !sessao.vapi) throw new Error("sem_vapi");
        const { default: Vapi } = await import("@vapi-ai/web");
        if (cancelado) return;
        const v = new Vapi(chavePublica) as unknown as VapiCliente;
        vapi.current = v;
        v.on("call-start", () => {
          setEstado("em_curso");
          // O id da chamada: o servidor pede-a ao serviço de voz (duração, transcrição, gravação).
          void avisarLigada({ id: sessao.id, call_id: idChamada.current ?? undefined });
        });
        v.on("speech-start", () => setTutorAFalar(true));
        v.on("speech-end", () => setTutorAFalar(false));
        v.on("message", ((m: { type?: string; role?: string; transcriptType?: string; transcript?: string }) => {
          if (m.type !== "transcript" || !m.transcript) return;
          const quem = m.role === "assistant" ? "tutor" : "aluno";
          if (m.transcriptType === "final") {
            setParcial(null);
            juntar(quem, m.transcript);
          } else setParcial({ quem, texto: m.transcript });
        }) as never);
        v.on("call-end", () => {
          if (!terminada.current) void terminarRef.current();
        });
        v.on("error", (() => {
          if (terminada.current) return;
          setErro("A ligação ao tutor falhou. Verifique a Internet e tente outra vez.");
          setEstado((e) => (e === "a_ligar" ? "erro" : e));
        }) as never);
        const chamada = await v.start(sessao.vapi.assistant_id, sessao.vapi.assistant_overrides);
        if (!chamada && !cancelado) throw new Error("vapi_recusou");
        const id = (chamada as { id?: unknown } | null)?.id;
        if (typeof id === "string" && id !== idChamada.current) {
          idChamada.current = id;
          // call-start pode ter chegado antes de start() acabar: avisa outra vez (é idempotente).
          void avisarLigada({ id: sessao.id, call_id: id });
        }
      } catch (e) {
        if (cancelado) return;
        const negado = e instanceof DOMException && e.name === "NotAllowedError";
        setErro(negado ? "O browser não deu acesso ao microfone. Autorize o microfone e tente outra vez." : "Não foi possível ligar ao tutor. Tente outra vez daqui a pouco.");
        setEstado("erro");
      }
    })();
    return () => {
      cancelado = true;
      try {
        vapi.current?.stop();
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- liga uma vez por sessão
  }, [sessao.id]);

  // Se o Vapi não ligar em 25 s, mostra o erro em vez de ficar a "ligar" para sempre.
  useEffect(() => {
    if (estado !== "a_ligar") return;
    const t = setTimeout(() => {
      try {
        vapi.current?.stop();
      } catch {}
      setErro("O tutor não atendeu. Verifique a Internet e tente outra vez.");
      setEstado("erro");
    }, 25_000);
    return () => clearTimeout(t);
  }, [estado]);

  // Relógio da conversa (o servidor recalcula a duração; isto é só para mostrar e para parar no limite).
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

  // Se a pessoa fechar o separador a meio, a conversa é guardada na mesma.
  useEffect(() => {
    const aoSair = () => {
      if (terminada.current) return;
      terminada.current = true;
      fetch(URL_TERMINAR(sessao.id), {
        method: "POST",
        keepalive: true,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpoTerminar()),
      }).catch(() => {});
    };
    if (saidaPendente.current) clearTimeout(saidaPendente.current); // voltou a montar (modo estrito): não era uma saída
    window.addEventListener("pagehide", aoSair);
    return () => {
      window.removeEventListener("pagehide", aoSair);
      saidaPendente.current = setTimeout(aoSair, 0); // sair da página pela navegação da app também conta
    };
  }, [sessao.id, corpoTerminar]);

  const alternarMicrofone = useCallback(() => {
    if (estado !== "em_curso") return;
    if (modo === "vapi") {
      setMicrofone((m) => {
        vapi.current?.setMuted(m);
        return !m;
      });
      return;
    }
    // Simulado: tocar para falar, tocar outra vez (ou parar de falar) para enviar.
    if (microfone) return reconhecedor.current?.stop();
    const w = window as unknown as { SpeechRecognition?: new () => Reconhecedor; webkitSpeechRecognition?: new () => Reconhecedor };
    const R = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!R) return setErro("Este browser não reconhece fala. Use o botão Escrever.");
    window.speechSynthesis?.cancel();
    setTutorAFalar(false);
    const r = new R();
    r.lang = "en-US";
    r.interimResults = true;
    r.continuous = false;
    let final = "";
    r.onresult = (e) => {
      let provisorio = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) final += res[0].transcript;
        else provisorio += res[0].transcript;
      }
      setParcial({ quem: "aluno", texto: (final + provisorio).trim() });
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed") setErro("O browser não deu acesso ao microfone. Autorize o microfone ou use o botão Escrever.");
      else if (e.error !== "no-speech" && e.error !== "aborted") setErro("Não percebemos o que disse. Tente outra vez.");
    };
    r.onend = () => {
      setMicrofone(false);
      setParcial(null);
      if (final.trim() && !terminada.current) {
        juntar("aluno", final);
        void respostaSimulada(final);
      }
    };
    reconhecedor.current = r;
    setErro(null);
    setMicrofone(true);
    r.start();
  }, [estado, juntar, microfone, modo, respostaSimulada]);

  const escrever = useCallback(
    (texto: string) => {
      const t = texto.trim();
      if (!t || estado !== "em_curso" || opcoes.semTexto) return;
      setErro(null);
      juntar("aluno", t, true);
      if (modo === "vapi" && vapi.current) {
        // Avisa já (antes do fim): as frases-alvo escritas contam só "com ajuda".
        void avisarAjuda({ id: sessao.id, escrito: t });
        vapi.current.send({ type: "add-message", message: { role: "user", content: t } });
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
    // Lido no browser, com o microfone do Vapi desligado, para não entrar na transcrição.
    const v = modo === "vapi" ? vapi.current : null;
    v?.setMuted(true);
    setTutorAFalar(true);
    falarNoBrowser(ultima.texto, () => {
      setTutorAFalar(false);
      v?.setMuted(!microfone);
    });
  }, [microfone, modo]);

  return { estado, erro, limparErro: () => setErro(null), falas, parcial, tutorAFalar, microfone, segundos, resumo, terminar, alternarMicrofone, escrever, ouvirOutraVez, reveladas, revelar };
}

export { falarNoBrowser };
