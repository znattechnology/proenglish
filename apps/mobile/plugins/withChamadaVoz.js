/**
 * Configuração nativa da conversa por voz com o tutor (Vapi sobre Daily/WebRTC).
 *
 * Faz o mesmo que @daily-co/config-plugin-rn-daily-js (só microfone, sem câmara nem partilha de ecrã),
 * que ainda não declara suporte para o Expo SDK 58:
 *  - Android: o serviço em primeiro plano do Daily (a chamada continua com o ecrã bloqueado)
 *    e o empacotamento das bibliotecas nativas que o WebRTC precisa.
 *  - As permissões ficam em app.json (android.permissions e ios.infoPlist).
 */
const { AndroidConfig, createRunOncePlugin, withAndroidManifest, withAppBuildGradle } = require("expo/config-plugins");

const SERVICO = "com.daily.reactlibrary.DailyOngoingMeetingForegroundService";

function withServicoDaily(config) {
  return withAndroidManifest(config, (c) => {
    const app = AndroidConfig.Manifest.getMainApplicationOrThrow(c.modResults);
    app.service = app.service ?? [];
    if (!app.service.some((s) => s.$?.["android:name"] === SERVICO)) {
      app.service.push({ $: { "android:name": SERVICO, "android:exported": "false", "android:foregroundServiceType": "microphone" } });
    }
    return c;
  });
}

function withEmpacotamentoJni(config) {
  return withAppBuildGradle(config, (c) => {
    const linha = "android.packagingOptions.jniLibs.useLegacyPackaging = true";
    if (!c.modResults.contents.includes(linha)) c.modResults.contents += `\n${linha}\n`;
    return c;
  });
}

const withChamadaVoz = (config) => withEmpacotamentoJni(withServicoDaily(config));

module.exports = createRunOncePlugin(withChamadaVoz, "withChamadaVoz", "1.0.0");
