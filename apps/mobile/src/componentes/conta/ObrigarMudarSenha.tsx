/**
 * Mudança obrigatória da palavra-passe (web components/pe/conta/ObrigarMudarSenha.tsx).
 * Quando a administração pede para mudar a palavra-passe (`deve_mudar_senha`), a API recusa tudo
 * o resto (403 mudar_senha). Em vez de ecrãs com erros, mostra só o pedido para escolher uma nova.
 *
 * Uso: envolver a área com sessão, por exemplo em src/app/(app)/_layout.tsx:
 *   <ObrigarMudarSenha><Stack ... /></ObrigarMudarSenha>
 */
import { KeyRound } from "lucide-react-native";
import { type ReactNode, useRef, useState } from "react";
import { type TextInputInstance, View } from "react-native";
import { tokens } from "@/api/tokens";
import { errosPorCampo, useContaMudarSenhaMutation } from "@/dominios/conta/api";
import { mensagemErro } from "@/api/erros";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, Botao, Campo, Ecra, Texto, Titulo } from "@/ui";
import { cor } from "@/tema";
import { AjudaSenha } from "./Partes";

export function ObrigarMudarSenha({ children }: { children: ReactNode }) {
  const { utilizador } = useSessao();
  if (!utilizador?.deve_mudar_senha) return <>{children}</>;
  return <EcraMudarSenhaObrigatoria />;
}

/** O ecrã em si (também usado pela rota /mudar-senha-obrigatoria). */
export function EcraMudarSenhaObrigatoria({ aoMudada }: { aoMudada?: () => void }) {
  const { utilizador, iniciar, actualizarUtilizador, sair } = useSessao();
  const temSenha = utilizador?.has_password !== false;
  const [mudar, { isLoading }] = useContaMudarSenhaMutation();
  const [actual, setActual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const refNova = useRef<TextInputInstance>(null);
  const refConfirmar = useRef<TextInputInstance>(null);

  const enviar = async () => {
    setGeral(null);
    const novos: Record<string, string> = {};
    if (temSenha && !actual) novos.current_password = "Escreva a palavra-passe actual.";
    if (nova.length < 8) novos.new_password = "Use pelo menos 8 caracteres.";
    if (nova !== confirmar) novos.new_password_confirm = "As duas palavras-passe novas não são iguais.";
    setErros(novos);
    if (Object.keys(novos).length) return;
    try {
      const r = await mudar({ actual, nova, confirmar, refresh: tokens.refresh }).unwrap();
      // A API emite uma sessão nova para este telemóvel (as outras terminam).
      if (r.tokens?.access) await iniciar(r);
      else await actualizarUtilizador();
      aoMudada?.();
    } catch (e) {
      const campos = errosPorCampo(e);
      setErros(campos);
      setGeral(Object.keys(campos).length ? null : mensagemErro(e, "Não foi possível guardar. Tente outra vez."));
    }
  };

  return (
    <Ecra style={{ paddingTop: 48, gap: 20 }}>
      <KeyRound size={40} color={cor.azulMarca} />
      <View style={{ gap: 8 }}>
        <Titulo>Escolha uma palavra-passe nova</Titulo>
        <Texto suave>Por segurança, a equipa ProEnglish pediu-lhe para mudar a palavra-passe antes de continuar.</Texto>
      </View>
      <View style={{ gap: 16 }}>
        {temSenha ? (
          <Campo
            rotulo="Palavra-passe actual"
            senha
            value={actual}
            onChangeText={setActual}
            erro={erros.current_password}
            autoCapitalize="none"
            autoComplete="current-password"
            textContentType="password"
            returnKeyType="next"
            submitBehavior="submit"
            onSubmitEditing={() => refNova.current?.focus()}
          />
        ) : null}
        <View style={{ gap: 4 }}>
          <Campo
            ref={refNova}
            rotulo="Palavra-passe nova"
            senha
            value={nova}
            onChangeText={setNova}
            erro={erros.new_password}
            autoCapitalize="none"
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="next"
            submitBehavior="submit"
            onSubmitEditing={() => refConfirmar.current?.focus()}
          />
          {erros.new_password ? null : <AjudaSenha senha={nova} />}
        </View>
        <Campo
          ref={refConfirmar}
          rotulo="Repita a palavra-passe nova"
          senha
          value={confirmar}
          onChangeText={setConfirmar}
          erro={erros.new_password_confirm}
          autoCapitalize="none"
          autoComplete="new-password"
          textContentType="newPassword"
          returnKeyType="go"
          onSubmitEditing={() => void enviar()}
        />
        {geral ? <Aviso tom="erro">{geral}</Aviso> : null}
        <Botao larguraTotal carregando={isLoading} onPress={() => void enviar()}>
          {isLoading ? "A guardar…" : temSenha ? "Mudar a palavra-passe" : "Criar a palavra-passe"}
        </Botao>
      </View>
      <Botao tipo="ligacao" onPress={() => void sair()}>
        Sair da conta
      </Botao>
    </Ecra>
  );
}
