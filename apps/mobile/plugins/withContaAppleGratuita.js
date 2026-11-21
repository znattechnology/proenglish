/**
 * Build de iPhone com uma conta Apple gratuita (Xcode, "Personal Team"): tira a capacidade de
 * notificações remotas (aps-environment), que essas contas não podem assinar.
 *
 * Só actua com PROENGLISH_IOS_GRATIS=1 (ver o script "telefone:ios" em package.json). A app só
 * usa notificações locais (o lembrete da meta diária), que continuam a funcionar.
 */
const { createRunOncePlugin, withEntitlementsPlist } = require("expo/config-plugins");

function withContaAppleGratuita(config) {
  if (process.env.PROENGLISH_IOS_GRATIS !== "1") return config;
  return withEntitlementsPlist(config, (c) => {
    delete c.modResults["aps-environment"];
    return c;
  });
}

module.exports = createRunOncePlugin(withContaAppleGratuita, "proenglish-conta-apple-gratuita", "1.0.0");
