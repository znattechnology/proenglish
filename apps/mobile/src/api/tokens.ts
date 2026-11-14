/**
 * Tokens da sessão. O refresh fica no cofre do telemóvel (expo-secure-store: Keychain/Keystore);
 * o access fica só em memória. Na web (só para desenvolvimento) usa o localStorage.
 */
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const CHAVE = "proenglish.refresh";
let access: string | null = null;
let refresh: string | null = null;

async function ler() {
  if (Platform.OS === "web") return globalThis.localStorage?.getItem(CHAVE) ?? null;
  return SecureStore.getItemAsync(CHAVE);
}
async function gravar(v: string | null) {
  if (Platform.OS === "web") {
    if (v) globalThis.localStorage?.setItem(CHAVE, v);
    else globalThis.localStorage?.removeItem(CHAVE);
    return;
  }
  if (v) await SecureStore.setItemAsync(CHAVE, v);
  else await SecureStore.deleteItemAsync(CHAVE);
}

export const tokens = {
  get access() {
    return access;
  },
  get refresh() {
    return refresh;
  },
  async carregar() {
    refresh = await ler();
    return refresh;
  },
  async definir(t: { access?: string | null; refresh?: string | null }) {
    if (t.access !== undefined) access = t.access;
    if (t.refresh !== undefined && t.refresh !== null) {
      refresh = t.refresh;
      await gravar(t.refresh);
    }
  },
  async limpar() {
    access = null;
    refresh = null;
    await gravar(null);
  },
};
