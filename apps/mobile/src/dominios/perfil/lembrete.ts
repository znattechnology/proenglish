/**
 * Lembrete da meta diária na app: notificação LOCAL agendada com expo-notifications.
 *
 * Porquê local e não push: a API só sabe enviar Web Push (VAPID, /users/avisos/push/), que não
 * chega a apps nativas, e as notificações remotas não funcionam no Expo Go em Android. Uma
 * notificação local funciona no Expo Go, sem servidor nem conta de envio.
 *
 * A regra é a da web ("um aviso por dia, à hora que escolher, só se ainda não tiver praticado"):
 * agendamos um aviso por dia para os próximos 7 dias à hora escolhida (hora de Angola) e saltamos
 * hoje quando já praticou. Sempre que a app sabe mais (abrir o perfil, as definições, acabar uma
 * lição), `sincronizarLembrete` volta a agendar.
 */
import { useEffect } from "react";
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { AndroidImportance, IosAuthorizationStatus } from "expo-notifications";
import { abrirLigacao } from "./abrir";

const PREFIXO = "pe-lembrete-";
const CANAL = "lembretes";
const DIAS = 7;
const FUSO_ANGOLA_H = 1; // UTC+1, sem hora de Verão

export const lembretesSuportados = Platform.OS === "ios" || Platform.OS === "android";

// Com a app aberta, mostra o aviso na mesma (por omissão o sistema não o mostraria em Android).
if (lembretesSuportados) {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
  });
}

export type EstadoPermissao = "concedida" | "pode-pedir" | "negada" | "sem-suporte";

export async function estadoPermissao(): Promise<EstadoPermissao> {
  if (!lembretesSuportados) return "sem-suporte";
  try {
    const p = await Notifications.getPermissionsAsync();
    if (p.granted || p.ios?.status === IosAuthorizationStatus.PROVISIONAL) return "concedida";
    return p.canAskAgain ? "pode-pedir" : "negada";
  } catch {
    return "sem-suporte";
  }
}

async function criarCanal() {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync(CANAL, { name: "Lembrete da meta diária", importance: AndroidImportance.DEFAULT });
}

/** Pede autorização ao sistema. Em Android 13+ o pedido só aparece depois de existir um canal. */
export async function pedirPermissao(): Promise<boolean> {
  if (!lembretesSuportados) return false;
  try {
    await criarCanal();
    const p = await Notifications.requestPermissionsAsync({ ios: { allowAlert: true, allowSound: true, allowBadge: false } });
    return p.granted || p.ios?.status === IosAuthorizationStatus.PROVISIONAL;
  } catch {
    return false;
  }
}

export async function cancelarLembretes() {
  if (!lembretesSuportados) return;
  try {
    const todos = await Notifications.getAllScheduledNotificationsAsync();
    await Promise.all(todos.filter((n) => n.identifier.startsWith(PREFIXO)).map((n) => Notifications.cancelScheduledNotificationAsync(n.identifier)));
  } catch {
    /* nada agendado */
  }
}

/** Instante (absoluto) de "hoje + k dias, às HH:MM de Angola". */
function instanteAngola(k: number, hora: string, agora = Date.now()) {
  const [h, m] = hora.split(":").map((n) => Number(n) || 0);
  const hojeAngola = new Date(agora + FUSO_ANGOLA_H * 3_600_000);
  return new Date(Date.UTC(hojeAngola.getUTCFullYear(), hojeAngola.getUTCMonth(), hojeAngola.getUTCDate() + k, h - FUSO_ANGOLA_H, m));
}

export type DadosLembrete = {
  ligado: boolean;
  /** "19:00" (hora de Angola), como em /users/avisos/. */
  hora: string;
  /** Já praticou hoje (study-streak: practiced_today / goal_completed): hoje não há aviso. */
  praticouHoje?: boolean;
  metaMinutos?: number;
  minutosHoje?: number;
};

/** Volta a agendar os avisos dos próximos dias (ou cancela-os). Não pede autorização. */
export async function sincronizarLembrete(d: DadosLembrete) {
  if (!lembretesSuportados) return;
  await cancelarLembretes();
  if (!d.ligado || (await estadoPermissao()) !== "concedida") return;
  await criarCanal();
  const meta = d.metaMinutos ?? 0;
  const agora = Date.now();
  for (let k = 0; k < DIAS; k++) {
    const quando = instanteAngola(k, d.hora, agora);
    if (quando.getTime() <= agora + 60_000) continue;
    if (k === 0 && d.praticouHoje) continue;
    const falta = Math.max(1, Math.ceil(meta - (k === 0 ? (d.minutosHoje ?? 0) : 0)));
    const titulo = meta ? (falta === 1 ? "Falta 1 minuto para a meta de hoje" : `Faltam ${falta} minutos para a meta de hoje`) : "Ainda não praticou hoje";
    await Notifications.scheduleNotificationAsync({
      identifier: `${PREFIXO}${k}`,
      content: { title: titulo, body: "Uma lição curta chega.", data: { link: "/user/laboratory/learn" } },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: quando, channelId: CANAL },
    }).catch(() => {});
  }
}

/**
 * Ao tocar numa notificação (lembrete local ou, no futuro, push), abre a ligação que traz em
 * `data.link` (ligações da web convertidas com src/lib/rotasWeb.ts). Montar uma vez na área com
 * sessão, por exemplo em src/app/(app)/_layout.tsx.
 */
function useAbrirAoTocarNativo() {
  const resposta = Notifications.useLastNotificationResponse();
  useEffect(() => {
    const link = resposta?.notification.request.content.data?.link;
    if (typeof link === "string" && link) {
      void abrirLigacao(link);
      void Notifications.clearLastNotificationResponseAsync?.().catch(() => {});
    }
  }, [resposta]);
}

/** Na web (só desenvolvimento) não há notificações locais: não faz nada. */
export const useAbrirAoTocarNotificacao: () => void = Platform.OS === "web" ? () => {} : useAbrirAoTocarNativo;
