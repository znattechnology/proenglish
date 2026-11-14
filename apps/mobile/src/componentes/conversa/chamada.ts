/**
 * A chamada de voz com o tutor (Vapi), isolada do resto da app.
 *
 * O Vapi no telemóvel é uma sala de áudio Daily (WebRTC): pedimos ao Vapi uma "web call" com a chave
 * pública e o assistente que o servidor nos deu, e entramos na sala com @daily-co/react-native-daily-js.
 * É o mesmo que faz o SDK @vapi-ai/react-native, mas sem as versões antigas que ele fixa
 * (react-native-webrtc 118, daily 0.78), que não servem para o React Native 0.88.
 *
 * Exige um "development build" (código nativo): no Expo Go e na web `vozDisponivel()` diz que não
 * e os ecrãs mostram uma mensagem em vez de rebentar. O módulo nativo só é carregado ao ligar.
 *
 * Confiança: a app não decide nada. Só avisa o servidor do id da chamada (ele vai buscá-la ao Vapi)
 * e mostra as legendas que o Vapi manda durante a conversa.
 */
import Constants, { ExecutionEnvironment } from "expo-constants";
import { NativeModules, Platform } from "react-native";
import type { DailyCall } from "@daily-co/react-native-daily-js";

export type Quem = "tutor" | "aluno";

export type EventosChamada = {
  /** O tutor está pronto a ouvir (a partir daqui conta o tempo). */
  aoLigar: () => void;
  aoTutorAFalar: (aFalar: boolean) => void;
  /** Legenda: provisória (final=false) ou final. */
  aoTranscricao: (quem: Quem, texto: string, final: boolean) => void;
  /** A chamada acabou (pelo tutor, pela rede ou por parar()). */
  aoTerminar: () => void;
  aoErro: (motivo: "microfone" | "ligacao") => void;
};

export type Chamada = {
  /** Id da chamada no Vapi (o servidor usa-o para confirmar a duração e a transcrição). */
  id: string | null;
  parar: () => void;
  silenciar: (silencio: boolean) => void;
  /** "Escrever em vez de falar": a mensagem entra na conversa como se o aluno a tivesse dito. */
  enviarTexto: (texto: string) => void;
};

export type Disponibilidade = { disponivel: true } | { disponivel: false; motivo: string };

const VAPI = "https://api.vapi.ai";

/** A voz em tempo real funciona aqui? (precisa do módulo nativo WebRTC/Daily.) */
export function vozDisponivel(): Disponibilidade {
  if (Platform.OS === "web") return { disponivel: false, motivo: "A conversa por voz não funciona na versão web da app. Use o site do ProEnglish ou a app no telemóvel." };
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient)
    return { disponivel: false, motivo: "A conversa por voz precisa da versão completa da app. No Expo Go não há chamadas de voz." };
  if (!NativeModules.WebRTCModule || !NativeModules.DailyNativeUtils)
    return { disponivel: false, motivo: "Esta versão da app ainda não tem a conversa por voz. Actualize a app e tente outra vez." };
  return { disponivel: true };
}

type ModuloDaily = typeof import("@daily-co/react-native-daily-js");

function carregarDaily(): ModuloDaily["default"] | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- carregado só ao ligar: sem o módulo nativo, o import rebenta
    const m = require("@daily-co/react-native-daily-js") as ModuloDaily;
    return m.default;
  } catch {
    return null;
  }
}

/** Liga ao tutor. Lança um erro se o Vapi recusar a chamada ou a sala não abrir. */
export async function ligar(chavePublica: string, assistantId: string, overrides: Record<string, unknown>, ev: EventosChamada): Promise<Chamada> {
  const Daily = carregarDaily();
  if (!Daily) throw new Error("sem_modulo");

  const r = await fetch(`${VAPI}/call/web`, {
    method: "POST",
    headers: { Authorization: `Bearer ${chavePublica}`, "Content-Type": "application/json" },
    body: JSON.stringify({ assistantId, assistantOverrides: overrides }),
  });
  if (!r.ok) throw new Error(`vapi_${r.status}`);
  const web = (await r.json()) as { id?: string; webCallUrl?: string };
  if (!web.webCallUrl) throw new Error("vapi_sem_sala");

  let call: DailyCall | null = Daily.createCallObject({ audioSource: true, videoSource: false });
  let ligou = false;
  let acabou = false;
  let silencioTutor: ReturnType<typeof setTimeout> | null = null;

  const marcarLigada = () => {
    if (ligou || acabou) return;
    ligou = true;
    ev.aoLigar();
  };
  const fim = () => {
    if (acabou) return;
    acabou = true;
    if (silencioTutor) clearTimeout(silencioTutor);
    const c = call;
    call = null;
    c?.destroy().catch(() => {});
    ev.aoTerminar();
  };

  call.on("app-message", (e) => {
    if (!e) return;
    if (e.data === "listening") return marcarLigada();
    let m: { type?: string; role?: string; transcriptType?: string; transcript?: string; status?: string } | null = null;
    try {
      m = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
    } catch {
      return;
    }
    if (!m) return;
    if (m.type === "transcript" && m.transcript) ev.aoTranscricao(m.role === "assistant" ? "tutor" : "aluno", m.transcript, m.transcriptType === "final");
    else if (m.type === "speech-update" && m.role === "assistant") ev.aoTutorAFalar(m.status === "started");
    else if (m.type === "status-update" && m.status === "ended") fim();
  });
  // O tutor está a falar quando o áudio dele passa um limiar (como o SDK do Vapi).
  call.on("remote-participants-audio-level", (e) => {
    if (!e) return;
    const nivel = Object.values(e.participantsAudioLevel).reduce((a, b) => a + b, 0);
    if (nivel <= 0.01) return;
    if (silencioTutor) clearTimeout(silencioTutor);
    else ev.aoTutorAFalar(true);
    silencioTutor = setTimeout(() => {
      silencioTutor = null;
      ev.aoTutorAFalar(false);
    }, 1000);
  });
  call.on("participant-joined", (e) => {
    if (!e || e.participant.local || !call) return;
    call.updateParticipant(e.participant.session_id, { setSubscribedTracks: { audio: true, video: false } });
  });
  call.on("track-started", (e) => {
    if (e?.participant && !e.participant.local && e.participant.user_name === "Vapi Speaker") call?.sendAppMessage("playable");
  });
  call.on("joined-meeting", () => marcarLigada());
  call.on("participant-left", (e) => {
    if (e && !e.participant.local) fim();
  });
  call.on("left-meeting", fim);
  call.on("camera-error", () => {
    if (!acabou) ev.aoErro("microfone");
  });
  call.on("error", () => {
    if (!acabou) ev.aoErro("ligacao");
    fim();
  });

  try {
    call.startRemoteParticipantsAudioLevelObserver(100);
  } catch {
    /* sem medidor: o estado "o tutor está a falar" vem das mensagens do Vapi */
  }

  try {
    await call.join({ url: web.webCallUrl, subscribeToTracksAutomatically: false });
  } catch (e) {
    fim();
    throw e;
  }

  return {
    id: web.id ?? null,
    parar: () => {
      if (!call) return fim();
      call.leave().catch(() => {}).finally(fim);
    },
    silenciar: (s) => {
      try {
        call?.setLocalAudio(!s);
      } catch {}
    },
    enviarTexto: (texto) => {
      call?.sendAppMessage(JSON.stringify({ type: "add-message", message: { role: "user", content: texto } }));
    },
  };
}
