/** Recuperar a palavra-passe, passo 1: pedir o código (RecuperarSenha.dc.html; web Codigos.tsx). */
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { estadoErro, mensagemErro } from "@/api/erros";
import { FraseComLigacao, TituloConta, Voltar } from "@/componentes/conta/Partes";
import { EMAIL_VALIDO, useContaPedirRecuperacaoMutation } from "@/dominios/conta/api";
import { Aviso, Botao, Campo, Ecra } from "@/ui";

export default function RecuperarSenha() {
  const p = useLocalSearchParams<{ email?: string }>();
  const [email, setEmail] = useState(p.email ?? "");
  const [erro, setErro] = useState<string | null>(null);
  const [pedir, { isLoading }] = useContaPedirRecuperacaoMutation();

  const enviar = async () => {
    setErro(null);
    const mail = email.trim().toLowerCase();
    if (!EMAIL_VALIDO.test(mail)) return setErro("Escreva o email da sua conta.");
    try {
      await pedir({ email: mail }).unwrap();
      router.push(`/nova-senha?email=${encodeURIComponent(mail)}`);
    } catch (er) {
      const st = estadoErro(er);
      setErro(st === 403 || st === 429 ? "Pediu muitos códigos seguidos. Espere um minuto e tente outra vez." : mensagemErro(er, "Não foi possível enviar o código. Tente outra vez."));
    }
  };

  const voltarEntrada = () => (router.canGoBack() ? router.back() : router.replace("/entrar"));

  return (
    <Ecra style={{ paddingHorizontal: 24, gap: 28 }}>
      <Voltar rotulo="Voltar à entrada" />
      <TituloConta passo="Passo 1 de 2" titulo="Esqueceu-se da palavra-passe?" texto="Escreva o email da sua conta. Enviamos-lhe um código para criar uma palavra-passe nova." />
      <View style={{ gap: 20 }}>
        <Campo
          rotulo="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          autoFocus={!email}
          returnKeyType="send"
          onSubmitEditing={() => void enviar()}
        />
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <Botao larguraTotal carregando={isLoading} onPress={() => void enviar()}>
          {isLoading ? "A enviar…" : "Enviar código"}
        </Botao>
      </View>
      <FraseComLigacao frase="Lembrou-se?" ligacao="Voltar à entrada" onPress={voltarEntrada} />
    </Ecra>
  );
}
