/** Criar conta (CriarConta.dc.html; web components/pe/conta/CriarConta.tsx). */
import { router, useLocalSearchParams } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useRef, useState } from "react";
import { type TextInputInstance, View } from "react-native";
import { SITE_URL } from "@/api/config";
import { mensagemErro } from "@/api/erros";
import { BotaoGoogle, ComGoogle, type EntradaGoogle } from "@/componentes/conta/Google";
import { AjudaSenha, FraseComLigacao, Ou, TituloConta } from "@/componentes/conta/Partes";
import { EMAIL_VALIDO, errosPorCampo, useContaRegistarMutation } from "@/dominios/conta/api";
import { useSubPlanosQuery } from "@/dominios/subscricao/api";
import { Aviso, Botao, Campo, Ecra, Logo, Texto } from "@/ui";

type Erros = Partial<Record<"name" | "email" | "password" | "password_confirm", string>>;

function validar(nome: string, email: string, senha: string, repetir: string): Erros {
  const e: Erros = {};
  if (nome.trim().split(/\s+/).filter(Boolean).length < 2) e.name = "Escreva o nome e o apelido.";
  if (!EMAIL_VALIDO.test(email.trim())) e.email = "Escreva um email válido, por exemplo nome@empresa.ao.";
  if (senha.length < 8) e.password = "A palavra-passe precisa de 8 caracteres ou mais.";
  if (repetir && repetir !== senha) e.password_confirm = "As duas palavras-passe são diferentes.";
  if (!repetir) e.password_confirm = "Repita a palavra-passe.";
  return e;
}

export default function CriarConta() {
  return <ComGoogle>{(g) => <Formulario g={g} />}</ComGoogle>;
}

function Formulario({ g }: { g: EntradaGoogle }) {
  const p = useLocalSearchParams<{ email?: string }>();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState(p.email ?? "");
  const [senha, setSenha] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erro, setErro] = useState<string | null>(null);
  const [registar, { isLoading }] = useContaRegistarMutation();
  // O limite do Gratuito vem da API de planos (pública); sem ela, não se promete um número.
  const { data: planos } = useSubPlanosQuery();
  const licoesGratis = planos?.find((pl) => pl.plan_type === "FREE")?.daily_lessons_limit;
  const refEmail = useRef<TextInputInstance>(null);
  const refSenha = useRef<TextInputInstance>(null);
  const refRepetir = useRef<TextInputInstance>(null);
  const jaExiste = !!erro && /conta com este email/.test(erro);

  const submeter = async () => {
    setErro(null);
    const v = validar(nome, email, senha, repetir);
    setErros(v);
    if (Object.keys(v).length) return;
    const mail = email.trim().toLowerCase();
    try {
      await registar({ name: nome.trim().replace(/\s+/g, " "), email: mail, password: senha, password_confirm: repetir }).unwrap();
      router.push(`/verificar-email?email=${encodeURIComponent(mail)}`);
    } catch (er) {
      const campos = errosPorCampo(er) as Erros;
      if (Object.keys(campos).length) setErros(campos);
      const m = mensagemErro(er, "Não foi possível criar a conta. Tente outra vez.");
      setErro(/existe|already|registad|cadastrad/i.test(m) ? "Já existe uma conta com este email. Entre ou recupere a palavra-passe." : Object.keys(campos).length ? null : m);
    }
  };

  return (
    <Ecra style={{ paddingTop: 24, paddingHorizontal: 24, gap: 20 }}>
      <Logo altura={40} />
      <TituloConta titulo="Criar conta" texto={licoesGratis ? `Grátis, com ${licoesGratis} ${licoesGratis === 1 ? "lição nova" : "lições novas"} por dia. Sem cartão.` : "Grátis e sem cartão."} />

      <View style={{ gap: 14 }}>
        <Campo
          rotulo="Nome completo"
          value={nome}
          onChangeText={setNome}
          erro={erros.name}
          autoComplete="name"
          textContentType="name"
          autoCapitalize="words"
          returnKeyType="next"
          submitBehavior="submit"
          onSubmitEditing={() => refEmail.current?.focus()}
        />
        <Campo
          ref={refEmail}
          rotulo="Email"
          value={email}
          onChangeText={setEmail}
          erro={erros.email}
          keyboardType="email-address"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          returnKeyType="next"
          submitBehavior="submit"
          onSubmitEditing={() => refSenha.current?.focus()}
        />
        <View style={{ gap: 4 }}>
          <Campo
            ref={refSenha}
            rotulo="Palavra-passe"
            senha
            value={senha}
            onChangeText={setSenha}
            erro={erros.password}
            autoCapitalize="none"
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="next"
            submitBehavior="submit"
            onSubmitEditing={() => refRepetir.current?.focus()}
          />
          {erros.password ? null : <AjudaSenha senha={senha} />}
        </View>
        <Campo
          ref={refRepetir}
          rotulo="Repita a palavra-passe"
          senha
          value={repetir}
          onChangeText={setRepetir}
          erro={erros.password_confirm}
          autoCapitalize="none"
          autoComplete="new-password"
          textContentType="newPassword"
          returnKeyType="go"
          onSubmitEditing={() => void submeter()}
        />
        {erro ? (
          <Aviso
            tom="erro"
            accao={
              jaExiste ? (
                <Botao tipo="ligacao" tamanho="pequeno" href={`/entrar?email=${encodeURIComponent(email.trim().toLowerCase())}`}>
                  Entrar
                </Botao>
              ) : undefined
            }
          >
            {erro}
          </Aviso>
        ) : null}
        <Botao larguraTotal carregando={isLoading} onPress={() => void submeter()} style={{ marginTop: 4 }}>
          {isLoading ? "A criar a conta…" : "Criar conta"}
        </Botao>
        <Texto v="legenda" suave>
          {"Ao criar a conta aceita os "}
          <Texto v="legenda" suave accessibilityRole="link" style={{ textDecorationLine: "underline" }} onPress={() => void WebBrowser.openBrowserAsync(`${SITE_URL}/termos`)}>
            Termos de utilização
          </Texto>
          {" e a "}
          <Texto v="legenda" suave accessibilityRole="link" style={{ textDecorationLine: "underline" }} onPress={() => void WebBrowser.openBrowserAsync(`${SITE_URL}/privacidade`)}>
            Política de privacidade
          </Texto>
          .
        </Texto>
      </View>

      <Ou />
      <View style={{ gap: 12 }}>
        {g.erro ? <Aviso tom="erro">{g.erro}</Aviso> : null}
        <BotaoGoogle texto="Criar conta com o Google" g={g} />
      </View>

      <View style={{ marginTop: "auto" }}>
        <FraseComLigacao centro frase="Já tem conta?" ligacao="Entrar" onPress={() => (router.canGoBack() ? router.back() : router.replace("/entrar"))} />
      </View>
    </Ecra>
  );
}
