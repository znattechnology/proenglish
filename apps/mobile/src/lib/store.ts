import { configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";
import { AppState } from "react-native";
import { addNetworkStateListener as ouvirRede } from "expo-network";
import { api } from "@/api/base";

export const store = configureStore({
  reducer: { [api.reducerPath]: api.reducer },
  middleware: (m) => m().concat(api.middleware),
});

// No telemóvel não há "window focus": voltar à app = focus; recuperar a rede = reconnect.
setupListeners(store.dispatch, (dispatch, { onFocus, onFocusLost, onOnline, onOffline }) => {
  const app = AppState.addEventListener("change", (s) => dispatch(s === "active" ? onFocus() : onFocusLost()));
  const rede = ouvirRede((e) => dispatch(e.isInternetReachable === false || e.isConnected === false ? onOffline() : onOnline()));
  return () => {
    app.remove();
    rede.remove();
  };
});

export type Estado = ReturnType<typeof store.getState>;
