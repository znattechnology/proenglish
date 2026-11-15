/**
 * Certificados (canvas Certificados; web user/certificates/page.tsx): os emitidos (descarregar o PDF,
 * partilhar a ligação de verificação) e os cursos a caminho de um certificado.
 */
import * as Clipboard from "expo-clipboard";
import { Directory, File, Paths } from "expo-file-system";
import { router } from "expo-router";
import * as Sharing from "expo-sharing";
import { Award, Check, Copy, Download, Lock, Share2 } from "lucide-react-native";
import { useState } from "react";
import { Pressable, Share, View } from "react-native";
import { renovarSessao } from "@/api/base";
import { SITE_URL } from "@/api/config";
import { mensagemErro } from "@/api/erros";
import { tokens } from "@/api/tokens";
import { diaMesCurto, useCursoCertificadosQuery, useEmitirCertificadoCursoMutation, type Certificados } from "@/dominios/cursos/api";
import { FolhaOferta, OfertaPlano } from "@/componentes/subscricao/Oferta";
import { ofertaDe, type OfertaPlano as Oferta } from "@/dominios/subscricao/api";
import { Aviso, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Etiqueta, Osso, Texto } from "@/ui";
import { cor, fonte, raio } from "@/tema";

export default function EcraCertificados() {
  const { data, isLoading, isError, error, refetch } = useCursoCertificadosQuery();
  const [aActualizar, setAActualizar] = useState(false);
  const site = SITE_URL.replace(/^https?:\/\//, "");

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Certificados" />}
      aoActualizar={async () => {
        setAActualizar(true);
        await refetch();
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
      style={{ gap: 16 }}
    >
      {isError ? (
        <EstadoErro titulo="Não conseguimos carregar os certificados" erro={error} aoTentar={refetch} />
      ) : isLoading || !data ? (
        <View accessible accessibilityLabel="A carregar" accessibilityState={{ busy: true }} style={{ gap: 12 }}>
          <Osso altura={230} />
          <Osso altura={22} largura="40%" />
          <Osso altura={76} />
        </View>
      ) : (
        <>
          {!data.plano_inclui_certificados ? (
            <View style={{ gap: 12 }}>
              <View style={{ flexDirection: "row", gap: 10, padding: 16, borderRadius: raio.md, backgroundColor: cor.realceSuave }}>
                <Lock size={20} color={cor.tinta} style={{ marginTop: 1 }} />
                <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>O seu plano não inclui certificados. O progresso dos seus cursos fica guardado.</Texto>
              </View>
              {data.oferta ? <OfertaPlano oferta={data.oferta} /> : null}
            </View>
          ) : null}

          {data.certificados.length ? (
            data.certificados.map((c) => <CartaoCertificado key={c.id} c={c} />)
          ) : (
            <EstadoVazio
              icone={<Award size={26} color={cor.azulMarca} />}
              titulo="Ainda não tem certificados"
              texto="Conclua um curso com 70% ou mais na nota final para receber o primeiro."
              accao={
                !data.em_curso.length ? (
                  <Botao larguraTotal href="/cursos">
                    Ver os cursos
                  </Botao>
                ) : undefined
              }
            />
          )}

          {data.em_curso.length ? <ACaminho emCurso={data.em_curso} podeEmitir={data.plano_inclui_certificados} /> : null}

          <Texto v="legenda" suave>
            Cada certificado tem um número. Qualquer empresa pode confirmá-lo em {site}/certificados/verificar, sem precisar de conta.
          </Texto>
        </>
      )}
    </Ecra>
  );
}

/** Descarrega o PDF (pedido autenticado) para a cache e abre a folha do sistema para o abrir ou guardar. */
async function abrirPdf(url: string, numero: string) {
  const pasta = new Directory(Paths.cache, "certificados");
  if (!pasta.exists) pasta.create({ intermediates: true, idempotent: true });
  const destino = new File(pasta, `certificado-${numero.replace(/[^A-Za-z0-9-]/g, "")}.pdf`);
  const descarregar = () =>
    File.downloadFileAsync(url, destino, { idempotent: true, headers: { "X-Cliente": "app", ...(tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}) } });
  if (!tokens.access && tokens.refresh) await renovarSessao();
  let ficheiro: File;
  try {
    ficheiro = await descarregar();
  } catch (e) {
    // Access expirado: renova e tenta uma vez.
    if (!String(e).includes("401") || !(await renovarSessao())) throw e;
    ficheiro = await descarregar();
  }
  if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(ficheiro.uri, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Certificado ProEnglish" });
}

function CartaoCertificado({ c }: { c: Certificados["certificados"][number] }) {
  const [aDescarregar, setADescarregar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const revogado = c.estado === "revogado";
  return (
    <View style={{ borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, overflow: "hidden" }}>
      <View style={{ backgroundColor: cor.azulMarca, paddingVertical: 18, paddingHorizontal: 20, borderBottomRightRadius: 24, gap: 4 }}>
        <Texto v="mini" forte cor={cor.sobreMarca} style={{ fontSize: 13, lineHeight: 18 }}>
          Certificado de conclusão
        </Texto>
        <Texto v="tituloS" accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 19 }}>
          {c.curso.titulo}
        </Texto>
      </View>
      <View style={{ paddingVertical: 14, paddingHorizontal: 20, flexDirection: "row", flexWrap: "wrap", rowGap: 10 }}>
        <Dado rotulo="Nota final" valor={`${Math.round(c.nota_final)}%`} />
        <Dado rotulo="Emitido em" valor={diaMesCurto(new Date(c.emitido_em), true)} />
        <View style={{ width: "50%" }}>
          <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
            Número
          </Texto>
          <Texto forte numeros style={{ letterSpacing: 0.6 }} selectable>
            {c.numero}
          </Texto>
        </View>
        <View style={{ width: "50%", gap: 2 }}>
          <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
            Estado
          </Texto>
          <Etiqueta tom={revogado ? "errado" : "certo"}>{revogado ? "Revogado" : "Válido"}</Etiqueta>
        </View>
        {c.nivel_fala_texto ? (
          <View style={{ width: "100%", gap: 2, paddingTop: 4 }}>
            <Texto forte>{c.nivel_fala_texto}</Texto>
            {c.notas_fala?.length ? (
              <Texto v="legenda" suave>
                {c.notas_fala.map((n) => `${n.nome} ${n.nota}`).join(", ")}
              </Texto>
            ) : null}
          </View>
        ) : null}
      </View>
      <View style={{ paddingHorizontal: 20, paddingBottom: 18, gap: 8 }}>
        {revogado ? (
          <Aviso tom="erro">Este certificado foi revogado e já não é válido. Fale com o apoio se tiver dúvidas.</Aviso>
        ) : (
          <>
            {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Botao
                tamanho="pequeno"
                style={{ flex: 1 }}
                carregando={aDescarregar}
                icone={aDescarregar ? undefined : <Download size={18} color={cor.sobreMarca} />}
                onPress={async () => {
                  setErro(null);
                  setADescarregar(true);
                  try {
                    await abrirPdf(c.pdf_url, c.numero);
                  } catch {
                    setErro("Não foi possível descarregar o PDF. Verifique a ligação e tente outra vez.");
                  } finally {
                    setADescarregar(false);
                  }
                }}
              >
                Descarregar
              </Botao>
              <Botao
                tipo="secundario"
                tamanho="pequeno"
                style={{ flex: 1 }}
                icone={<Share2 size={18} color={cor.azulMarca} />}
                onPress={() => Share.share({ message: `O meu certificado ProEnglish de "${c.curso.titulo}" (n.º ${c.numero}). Confirme aqui: ${c.ligacao_verificacao}`, url: c.ligacao_verificacao })}
              >
                Partilhar
              </Botao>
            </View>
            <Pressable
              accessibilityRole="button"
              hitSlop={6}
              onPress={async () => {
                await Clipboard.setStringAsync(c.ligacao_verificacao);
                setCopiado(true);
                setTimeout(() => setCopiado(false), 2500);
              }}
              style={{ flexDirection: "row", alignItems: "center", gap: 6, minHeight: 44, alignSelf: "flex-start" }}
            >
              {copiado ? <Check size={18} color={cor.certo} /> : <Copy size={18} color={cor.azulMarca} />}
              <Texto forte cor={copiado ? cor.certo : cor.azulMarca} accessibilityLiveRegion="polite">
                {copiado ? "Ligação copiada" : "Copiar ligação de verificação"}
              </Texto>
            </Pressable>
          </>
        )}
      </View>
    </View>
  );
}

function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <View style={{ width: "50%" }}>
      <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
        {rotulo}
      </Texto>
      <Texto forte numeros>
        {valor}
      </Texto>
    </View>
  );
}

function ACaminho({ emCurso, podeEmitir }: { emCurso: Certificados["em_curso"]; podeEmitir: boolean }) {
  const [emitir, { isLoading }] = useEmitirCertificadoCursoMutation();
  const [erro, setErro] = useState<string | null>(null);
  // 403 CERTIFICADOS_NAO_INCLUIDOS com o plano que os inclui.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: Oferta } | null>(null);
  return (
    <View style={{ gap: 10 }}>
      <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
        A caminho
      </Texto>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      {emCurso.map((c) => {
        const falta = c.em_falta[0];
        const texto = c.pode_emitir
          ? "Cumpre tudo o que o certificado pede."
          : falta
            ? `${falta.mensagem}${c.em_falta.length > 1 ? `. Falta${c.em_falta.length > 2 ? "m" : ""} mais ${c.em_falta.length - 1} ${c.em_falta.length > 2 ? "requisitos" : "requisito"}.` : ""}`
            : `Precisa de ${c.nota_minima}% na nota final.`;
        return (
          <View key={c.curso.id} style={{ gap: 8, padding: 16, borderRadius: raio.md, backgroundColor: cor.fundoSuave }}>
            <Pressable accessibilityRole="link" accessibilityLabel={`${c.curso.titulo}, ${Math.round(c.nota_final)}%. ${texto}`} onPress={() => router.push(`/curso/${c.curso.id}/notas`)} style={{ gap: 8 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
                <Texto forte style={{ flex: 1 }}>
                  {c.curso.titulo}
                </Texto>
                <Texto forte numeros>
                  {Math.round(c.nota_final)}%
                </Texto>
              </View>
              <BarraProgresso valor={c.progresso} rotulo={`Aulas concluídas em ${c.curso.titulo}`} />
              <Texto v="legenda" suave>
                {texto}
              </Texto>
            </Pressable>
            {c.pode_emitir && podeEmitir ? (
              <Botao
                tamanho="medio"
                carregando={isLoading}
                onPress={async () => {
                  setErro(null);
                  const r = await emitir(c.curso.id);
                  if (!("error" in r && r.error)) return;
                  const oferta = ofertaDe(r.error);
                  if (oferta) setLimite({ mensagem: mensagemErro(r.error, "O seu plano não inclui certificados."), oferta });
                  else setErro(mensagemErro(r.error, "Não foi possível emitir o certificado."));
                }}
              >
                Receber o certificado
              </Botao>
            ) : null}
          </View>
        );
      })}
      {limite ? (
        <FolhaOferta aberto aoFechar={() => setLimite(null)} titulo="Os certificados não estão no seu plano" mensagem={limite.mensagem} oferta={limite.oferta}>
          <Botao tipo="ligacao" larguraTotal onPress={() => setLimite(null)}>
            Agora não
          </Botao>
        </FolhaOferta>
      ) : null}
    </View>
  );
}
