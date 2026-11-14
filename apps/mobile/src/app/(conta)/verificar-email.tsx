/** Confirmar o email com o código (VerificarEmail.dc.html; web components/pe/conta/Codigos.tsx). */
import { useLocalSearchParams } from "expo-router";
import { Mail } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { CampoCodigo6, EmailForte, Ligacao, TituloConta, Voltar, textoEspera, useEspera } from "@/componentes/conta/Partes";
import { segundosDoErro, useContaReenviarCodigoMutation, useContaVerificarEmailMutation } from "@/dominios/conta/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, Botao, Ecra, Texto } from "@/ui";
import { balao, cor } from "@/tema";

export default function VerificarEmail() {
  const p = useLocalSearchParams<{ email?: string; de?: string }>();
  const email = (p.email ?? "").trim().toLowerCase();
  // Vindo de "Entrar", nenhum código acabou de ser enviado: pode pedir um logo.
  const deEntrar = p.de === "entrar";
  const { iniciar } = useSessao();
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [espera, setEspera] = useEspera(deEntrar ? 0 : 60);
  const [verificar, { isLoading }] = useContaVerificarEmailMutation();
  const [reenviar, { isLoading: aReenviar }] = useContaReenviarCodigoMutation();

  if (!email)
    return (
      <Ecra style={{ paddingHorizontal: 24, gap: 28 }}>
        <Voltar />
        <TituloConta titulo="Confirme o seu email" texto="Não sabemos que email quer confirmar." />
        <Botao larguraTotal href="/entrar" substituir>
          Voltar à entrada
        </Botao>
      </Ecra>
    );

  const confirmar = async (c = codigo) => {
    setErro(null);
    if (c.length !== 6) return setErro("O código tem 6 algarismos.");
    try {
      const r = await verificar({ email, code: c }).unwrap();
      await iniciar(r); // a navegação muda sozinha para a área do estudante
    } catch (er) {
      setErro(mensagemErro(er, "O código não está certo. Confirme e tente outra vez."));
    }
  };

  const pedirOutro = async () => {
    setErro(null);
    setAviso(null);
    try {
      const r = await reenviar({ email }).unwrap();
      setAviso("Enviámos um código novo. O anterior deixa de servir.");
      setEspera(r.aguardar_segundos ?? 60);
    } catch (er) {
      const s = segundosDoErro(er);
      if (s) setEspera(s);
      else setErro(mensagemErro(er, "Não foi possível enviar outro código."));
    }
  };

  return (
    <Ecra style={{ paddingHorizontal: 24, gap: 28 }}>
      <Voltar />
      <View style={[balao.grande, { width: 72, height: 72, borderTopLeftRadius: 24, borderTopRightRadius: 24, borderBottomRightRadius: 24, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}>
        <Mail size={32} color={cor.sobreMarca} />
      </View>
      <TituloConta
        titulo="Confirme o seu email"
        texto={
          deEntrar ? (
            <Texto suave>
              {"A conta "}
              <EmailForte>{email}</EmailForte>
              {" ainda não foi confirmada. Use o código que recebeu por email ou peça um novo."}
            </Texto>
          ) : (
            <Texto suave>
              {"Enviámos um código de 6 algarismos para "}
              <EmailForte>{email}</EmailForte>
              {". Vale durante 30 minutos."}
            </Texto>
          )
        }
      />

      <View style={{ gap: 20 }}>
        <CampoCodigo6
          valor={codigo}
          aoMudar={(v) => {
            setCodigo(v);
            if (v.length === 6 && !isLoading) void confirmar(v);
          }}
          erro={erro}
          autoFocus
        />
        <Botao larguraTotal disabled={codigo.length !== 6} carregando={isLoading} onPress={() => void confirmar()}>
          {isLoading ? "A confirmar…" : "Confirmar email"}
        </Botao>
      </View>

      <View style={{ gap: 4 }}>
        <Texto suave>Não recebeu? Veja na pasta de spam.</Texto>
        {espera > 0 ? (
          <Texto suave accessibilityLiveRegion="polite">
            {textoEspera(espera)}
          </Texto>
        ) : (
          <Ligacao inactivo={aReenviar} onPress={() => void pedirOutro()}>
            {aReenviar ? "A enviar…" : deEntrar ? "Enviar um código novo" : "Enviar outro código"}
          </Ligacao>
        )}
        {aviso ? <Aviso tom="certo">{aviso}</Aviso> : null}
        <Ligacao href={`/criar-conta?email=${encodeURIComponent(email)}`}>Mudar o endereço de email</Ligacao>
      </View>
    </Ecra>
  );
}
