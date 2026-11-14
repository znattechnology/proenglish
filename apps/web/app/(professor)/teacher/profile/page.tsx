"use client";

import { useRef, useState } from "react";
import { Camera } from "lucide-react";
import { useDispatch } from "react-redux";
import { AreaTexto, Aviso, Botao, Campo, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaPerfil } from "@/components/pe/professor/SeparadoresPerfil";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { enviarFicheiro } from "@/src/domains/teacher/professor/envio";
import { perfilApi, useMudarPerfilProfessorMutation, usePerfilProfessorQuery, useTirarFotografiaMutation, type PerfilProfessor } from "@/src/domains/teacher/professor/perfil";

export default function PerfilPublico() {
  const { data, isError, refetch } = usePerfilProfessorQuery();
  return (
    <Pagina className="gap-7">
      <CabecaPerfil activo="Perfil público" texto="O que os alunos vêem na página de cada curso seu." />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o perfil.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-96 max-w-[760px] rounded-pe-md" />
      ) : (
        <Formulario p={data} />
      )}
    </Pagina>
  );
}

function Fotografia({ url, iniciais, tamanho }: { url: string | null; iniciais: string; tamanho: "g" | "p" }) {
  const cls = tamanho === "g" ? "size-24 text-[30px] rounded-pe-fala" : "size-14 text-[20px] rounded-pe-fala-s";
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className={`${cls} shrink-0 object-cover`} />
  ) : (
    <span aria-hidden className={`${cls} flex shrink-0 items-center justify-center bg-pe-azul-marca font-pe-titulo font-bold text-pe-sobre-marca`}>
      {iniciais}
    </span>
  );
}

function Formulario({ p }: { p: PerfilProfessor }) {
  const dispatch = useDispatch();
  const { checkAuth } = useDjangoAuth();
  const [mudar, { isLoading }] = useMudarPerfilProfessorMutation();
  const [tirar] = useTirarFotografiaMutation();
  const [v, setV] = useState({ nome: p.nome, cidade: p.cidade, especialidade: p.especialidade, experiencia: p.experiencia, sobre: p.sobre });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const [envio, setEnvio] = useState<number | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const muda = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setV((x) => ({ ...x, [k]: e.target.value }));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setEstado(null);
    const er: Record<string, string> = {};
    if (v.nome.trim().length < 2) er.nome = "Escreva o seu nome completo.";
    setErros(er);
    if (Object.keys(er).length) return;
    try {
      await mudar(v).unwrap();
      setEstado({ tipo: "certo", texto: "Alterações guardadas." });
      if (v.nome.trim() !== p.nome) void checkAuth(); // o nome na barra lateral vem da sessão
    } catch (x) {
      setErros(errosPorCampo(x));
      setEstado({ tipo: "errado", texto: mensagemErro(x, "Não foi possível guardar. Tente outra vez.") });
    }
  }

  async function enviarFoto(f: File) {
    setEstado(null);
    if (f.size > 5 * 1024 ** 2) return setEstado({ tipo: "errado", texto: "A fotografia tem mais de 5 MB. Escolha uma mais pequena." });
    setEnvio(0);
    try {
      await enviarFicheiro({ tipo: "fotografia" }, f, setEnvio);
      dispatch(perfilApi.util.invalidateTags(["Perfil"]));
    } catch (x) {
      setEstado({ tipo: "errado", texto: mensagemErro(x, "Não foi possível enviar a fotografia.") });
    } finally {
      setEnvio(null);
    }
  }

  const especialidade = v.especialidade.trim();
  const sobre = v.sobre.trim();

  return (
    <div className="flex flex-col gap-8 xl:flex-row xl:items-start">
      <form noValidate onSubmit={guardar} className="flex max-w-[640px] flex-1 flex-col gap-5">
        <div className="flex items-center gap-4">
          <Fotografia url={p.fotografia} iniciais={p.iniciais} tamanho="g" />
          <div className="flex flex-col items-start gap-1">
            <Botao tipo="secundario" tamanho="pequeno" onClick={() => input.current?.click()} disabled={envio != null}>
              <Camera aria-hidden className="size-[18px]" />
              {envio != null ? `A enviar ${Math.round(envio * 100)}%` : p.fotografia ? "Mudar a fotografia" : "Pôr uma fotografia"}
            </Botao>
            {p.fotografia ? (
              <button
                type="button"
                onClick={() => {
                  setEstado(null);
                  tirar()
                    .unwrap()
                    .catch((x) => setEstado({ tipo: "errado", texto: mensagemErro(x, "Não foi possível tirar a fotografia.") }));
                }}
                className="min-h-11 px-1 text-[15px] font-semibold text-pe-tinta-suave underline underline-offset-[3px] hover:text-pe-tinta">
                Tirar a fotografia
              </button>
            ) : (
              <span className="text-pe-legenda text-pe-tinta-suave">Quadrada, de cara. PNG, JPG ou WebP até 5 MB.</span>
            )}
            <input
              ref={input}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) void enviarFoto(f);
              }}
            />
          </div>
        </div>
        <Campo rotulo="Nome" value={v.nome} onChange={muda("nome")} autoComplete="name" maxLength={120} erro={erros.nome} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Cidade" value={v.cidade} onChange={muda("cidade")} maxLength={80} placeholder="Luanda" erro={erros.cidade} />
          <Campo rotulo="Especialidade" value={v.especialidade} onChange={muda("especialidade")} maxLength={120} placeholder="Inglês técnico para Petróleo e Gás" erro={erros.especialidade} />
        </div>
        <Campo rotulo="Experiência" value={v.experiencia} onChange={muda("experiencia")} maxLength={160} placeholder="10 anos como intérprete em plataformas de perfuração" erro={erros.experiencia} />
        <AreaTexto
          rotulo="Sobre si"
          rows={5}
          maxLength={800}
          value={v.sobre}
          onChange={muda("sobre")}
          erro={erros.sobre}
          ajuda={`Conte o que fez antes de ensinar e como são os seus cursos. ${v.sobre.length} de 800 caracteres.`}
        />
        {estado ? <Aviso tipo={estado.tipo}>{estado.texto}</Aviso> : null}
        <Botao type="submit" tamanho="medio" className="self-start" disabled={isLoading}>
          {isLoading ? "A guardar…" : "Guardar alterações"}
        </Botao>
      </form>

      <aside aria-labelledby="t-previsao" className="flex w-full flex-col gap-3 xl:sticky xl:top-6 xl:w-[380px]">
        <h2 id="t-previsao" className="m-0 font-pe-titulo text-[18px] font-semibold leading-6">
          Como os alunos o vêem
        </h2>
        <div className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-5">
          <div className="flex items-center gap-3">
            <Fotografia url={p.fotografia} iniciais={p.iniciais} tamanho="p" />
            <div className="flex min-w-0 flex-col">
              <span className="font-semibold">Prof. {v.nome.trim() || p.nome}</span>
              {[especialidade, v.cidade.trim()].filter(Boolean).length ? <span className="text-pe-legenda text-pe-tinta-suave">{[especialidade, v.cidade.trim()].filter(Boolean).join(", ")}</span> : null}
            </div>
          </div>
          {v.experiencia.trim() ? <p className="m-0 text-[15px] leading-[22px]">{v.experiencia.trim()}</p> : null}
          {sobre ? <p className="m-0 line-clamp-4 whitespace-pre-line text-[15px] leading-[22px] text-pe-tinta-suave">{sobre}</p> : null}
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            {p.cursos_publicados} {p.cursos_publicados === 1 ? "curso" : "cursos"} na ProEnglish{p.desde ? `, desde ${p.desde}` : ""}.
          </p>
        </div>
        {!sobre && !especialidade ? (
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            Enquanto não escrever a especialidade ou o texto sobre si, este quadro não aparece aos alunos.
          </p>
        ) : null}
      </aside>
    </div>
  );
}
