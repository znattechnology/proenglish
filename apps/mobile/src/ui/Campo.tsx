import { Eye, EyeOff } from "lucide-react-native";
import { forwardRef, useState } from "react";
import { Pressable, TextInput, type TextInputInstance, type TextInputProps, View } from "react-native";
import { cor, fonte, raio } from "@/tema";
import { Texto } from "./Texto";

export type CampoProps = TextInputProps & {
  rotulo: string;
  ajuda?: string;
  erro?: string | null;
  /** Campo de palavra-passe com botão para mostrar/esconder. */
  senha?: boolean;
  multilinha?: boolean;
};

/** Campo de texto com rótulo por cima, ajuda e erro por baixo (como na web). */
export const Campo = forwardRef<TextInputInstance, CampoProps>(function Campo(
  { rotulo, ajuda, erro, senha, multilinha, style, editable = true, ...props },
  ref
) {
  const [ver, setVer] = useState(false);
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 4 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      {ajuda ? <Texto v="legenda" suave>{ajuda}</Texto> : null}
      <View>
        <TextInput
          ref={ref}
          accessibilityLabel={rotulo}
          accessibilityHint={erro ?? ajuda}
          placeholderTextColor={cor.tintaSuave}
          secureTextEntry={senha && !ver}
          multiline={multilinha}
          editable={editable}
          onFocus={(e) => {
            setFoco(true);
            props.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFoco(false);
            props.onBlur?.(e);
          }}
          style={[
            {
              minHeight: multilinha ? 120 : 48,
              paddingHorizontal: 12,
              paddingRight: senha ? 52 : 12,
              paddingVertical: multilinha ? 12 : 0,
              textAlignVertical: multilinha ? "top" : "center",
              fontFamily: fonte.texto,
              fontSize: 16,
              color: cor.tinta,
              backgroundColor: editable ? cor.fundo : cor.fundoSuave,
              borderWidth: foco || erro ? 2 : 1.5,
              borderColor: erro ? cor.errado : foco ? cor.azulVivo : cor.linhaForte,
              borderRadius: raio.sm,
            },
            style,
          ]}
          {...props}
        />
        {senha ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={ver ? "Esconder a palavra-passe" : "Mostrar a palavra-passe"}
            onPress={() => setVer((v) => !v)}
            style={{ position: "absolute", right: 2, top: 2, width: 44, height: 44, alignItems: "center", justifyContent: "center" }}
          >
            {ver ? <EyeOff size={20} color={cor.tintaSuave} /> : <Eye size={20} color={cor.tintaSuave} />}
          </Pressable>
        ) : null}
      </View>
      {erro ? (
        <Texto v="legenda" cor={cor.errado} accessibilityLiveRegion="polite">
          {erro}
        </Texto>
      ) : null}
    </View>
  );
});
