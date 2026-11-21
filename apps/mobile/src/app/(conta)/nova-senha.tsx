/** Recuperar a palavra-passe, passo 2: código e palavra-passe nova (NovaSenha.dc.html; web Codigos.tsx). */
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState } from "react";
import { type TextInputInstance, View } from "react-native";
import { estadoErro, mensagemErro } from "@/api/erros";
import { AjudaSenha, CampoCodigoLinha, EmailForte, Ligacao, TituloConta, Voltar, textoEspera, useEspera } from "@/componentes/conta/Partes";
import { useContaConfirmarRecuperacaoMutation, useContaPedirRecuperacaoMutation } from "@/dominios/conta/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, Botao, Campo, Ecra, Texto } from "@/ui";

export default function NovaSenha() {
  const p = useLocalSearchParams<{ email?: string }>();
  const email = (p.email ?? "").trim().toLowerCase();
  const { entrar } = useSessao();
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [erroRepetir, setErroRepetir] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [espera, setEspera] = useEspera(60);
  const [aEntrar, setAEntrar] = useState(false);
  const [pedir, { isLoading: aPedir }] = useContaPedirRecuperacaoMutation();
  const [confirmar, { isLoading: aConfirmar }] = useContaConfirmarRecuperacaoMutation();
  const refSenha = useRef<TextInputInstance>(null);
  const refRepetir = useRef<TextInputInstance>(null);

  if (!email)
    return (
      <Ecra style={{ paddingHorizontal: 24, gap: 28 }}>
        <Voltar />
        <TituloConta titulo="Crie uma palavra-passe nova" texto="Não sabemos de que conta é. Peça o código outra vez." />
        <Botao larguraTotal href="/recuperar-senha" substituir>
          Pedir o código
        </Botao>
      </Ecra>
    );

  const pedirOutro = async () => {
    setErro(null);
    setAviso(null);
    try {
      await pedir({ email }).unwrap();
      setEspera(60);
      setAviso("Enviámos outro código. O anterior deixa de servir.");
    } catch (er) {
      const st = estadoErro(er);
      setErro(st === 403 || st === 429 ? "Pediu muitos códigos seguidos. Espere um minuto e tente outra vez." : mensagemErro(er, "Não foi possível enviar o código. Tente outra vez."));
    }
  };

  const guardar = async () => {
    setErro(null);
    setErroRepetir(null);
    if (codigo.length !== 6) return setErro("O código tem 6 algarismos.");
    if (senha.length < 8) return setErro("A palavra-passe nova precisa de 8 caracteres ou mais.");
    if (senha !== repetir) return setErroRepetir("As duas palavras-passe são diferentes.");
    try {
      await confirmar({ email, code: codigo, newPassword: senha }).unwrap();
    } catch (er) {
      return setErro(mensagemErro(er, "Não foi possível guardar a palavra-passe. Tente outra vez."));
    }
    setAEntrar(true);
    const r = await entrar(email, senha);
    setAEntrar(false);
    if (!r.ok) router.replace(`/entrar?email=${encodeURIComponent(email)}&senha=alterada`);
  };

  const ocupado = aConfirmar || aEntrar;
  return (
    <Ecra style={{ paddingHorizontal: 24, gap: 24 }}>
      <Voltar />
      <TituloConta
        passo="Passo 2 de 2"
        titulo="Crie uma palavra-passe nova"
        texto={
          <Texto suave>
            {"Se houver uma conta com "}
            <EmailForte>{email}</EmailForte>
            {", o código já foi para lá. Vale durante 30 minutos."}
          </Texto>
        }
      />
      <View style={{ gap: 16 }}>
        <View style={{ gap: 2 }}>
          <CampoCodigoLinha valor={codigo} aoMudar={setCodigo} autoFocus />
          {espera > 0 ? (
            <Texto v="legenda" suave accessibilityLiveRegion="polite" style={{ paddingVertical: 10 }}>
              {textoEspera(espera)}
            </Texto>
          ) : (
            <Ligacao inactivo={aPedir} onPress={() => void pedirOutro()}>
              {aPedir ? "A enviar…" : "Enviar outro código"}
            </Ligacao>
          )}
          {aviso ? <Aviso tom="certo">{aviso}</Aviso> : null}
        </View>
        <View style={{ gap: 4 }}>
          <Campo
            ref={refSenha}
            rotulo="Palavra-passe nova"
            senha
            value={senha}
            onChangeText={setSenha}
            autoCapitalize="none"
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="next"
            submitBehavior="submit"
            onSubmitEditing={() => refRepetir.current?.focus()}
          />
          <AjudaSenha senha={senha} />
        </View>
        <Campo
          ref={refRepetir}
          rotulo="Repita a palavra-passe nova"
          senha
          value={repetir}
          onChangeText={setRepetir}
          erro={erroRepetir}
          autoCapitalize="none"
          autoComplete="new-password"
          textContentType="newPassword"
          returnKeyType="go"
          onSubmitEditing={() => void guardar()}
        />
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <Botao larguraTotal carregando={ocupado} onPress={() => void guardar()} style={{ marginTop: 4 }}>
          {ocupado ? "A guardar…" : "Guardar e entrar"}
        </Botao>
      </View>
      <Ligacao onPress={() => (router.canGoBack() ? router.back() : router.replace(`/recuperar-senha?email=${encodeURIComponent(email)}`))}>Usar outro email</Ligacao>
    </Ecra>
  );
}
