import Link from "next/link";
import { Documento, type Seccao } from "@/components/pe/legal/Documento";
import { EMPRESA, MESES_RETENCAO_GRAVACOES } from "@/src/domains/legal/empresa";

export const metadata = {
  title: "Política de privacidade | ProEnglish",
  description: "Que dados o ProEnglish recolhe, para quê, com quem partilha, quanto tempo guarda e como exerce os seus direitos.",
};

const L = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <Link href={href} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
    {children}
  </Link>
);

/** Uma linha "o quê / para quê" das tabelas de dados e de serviços externos. */
function Tabela({ cabecalho, linhas }: { cabecalho: [string, string]; linhas: [React.ReactNode, React.ReactNode][] }) {
  return (
    <div className="overflow-x-auto rounded-pe-md border border-pe-linha">
      <table className="w-full min-w-[480px] border-collapse text-left text-[15px] leading-[22px]">
        <thead>
          <tr className="bg-pe-fundo-suave">
            <th scope="col" className="w-[38%] px-4 py-2.5 font-semibold">
              {cabecalho[0]}
            </th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              {cabecalho[1]}
            </th>
          </tr>
        </thead>
        <tbody>
          {linhas.map(([a, b], i) => (
            <tr key={i} className="border-t border-pe-linha align-top">
              <td className="px-4 py-3 font-semibold">{a}</td>
              <td className="px-4 py-3">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SECCOES: Seccao[] = [
  {
    id: "responsavel",
    titulo: "Quem é responsável pelos seus dados",
    corpo: (
      <>
        <p className="m-0">
          O responsável pelo tratamento dos seus dados pessoais é {EMPRESA.nomeLegal}, NIF {EMPRESA.nif}, com sede em {EMPRESA.morada}. Para qualquer questão sobre privacidade, escreva para {EMPRESA.emailPrivacidade}.
        </p>
        <p className="m-0">Tratamos os dados de acordo com a Lei n.º 22/11, de 17 de Junho, Lei da Protecção de Dados Pessoais de Angola.</p>
      </>
    ),
  },
  {
    id: "dados",
    titulo: "Que dados recolhemos",
    corpo: (
      <Tabela
        cabecalho={["Dados", "De onde vêm"]}
        linhas={[
          ["Conta: nome, email, palavra-passe", "Do formulário de criar conta, ou da sua conta Google se entrar com o Google (nesse caso também a foto). A palavra-passe é guardada cifrada: nem nós a conseguimos ler."],
          ["Perfil: telefone, cidade, área profissional, nível, meta diária", "Do que preenche em Perfil e definições. São opcionais, excepto o telefone para pagar."],
          ["Estudo: aulas vistas, respostas, notas, pontos, vidas, conquistas, dias seguidos", "Do que faz nos cursos e no laboratório de prática."],
          ["Conversas com o tutor e teste de nível falado: a transcrição do que diz e do que o tutor responde, as correcções, as notas e o seu nível", "Da conversa por voz ou por escrito. O áudio é processado em tempo real para ser transcrito e não é gravado."],
          ["Exame oral de um curso: a transcrição, as notas e o relatório e, só se autorizar, a gravação do áudio", "Do exame. Sem a sua autorização não há gravação e o exame vale o mesmo. Ver “Gravações de áudio”."],
          ["Exercícios de pronúncia: a nota e o texto reconhecido de cada resposta", "Do microfone, só quando carrega para gravar. O áudio é enviado para análise e não o guardamos: guardamos só a nota e o texto."],
          ["Pagamentos: número de telemóvel Multicaixa Express, plano, valor, data, recibos", "Do pagamento. Não recebemos dados de cartão nem o seu PIN."],
          ["Dados técnicos: endereço IP, tipo de browser, horas de acesso", "Do seu dispositivo, quando usa a plataforma."],
        ]}
      />
    ),
  },
  {
    id: "finalidades",
    titulo: "Para que usamos os dados",
    corpo: (
      <>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>
            <strong>Dar-lhe o serviço que pediu</strong> (o contrato connosco): a conta, os cursos, o progresso, a conversa com o tutor, as notas, os certificados e os pagamentos.
          </li>
          <li>
            <strong>Avisos sobre a conta</strong>: códigos de confirmação, recibos, lembretes de renovação e mudanças a estes documentos.
          </li>
          <li>
            <strong>Segurança</strong> (interesse legítimo): limitar tentativas de entrada, detectar fraude e manter registos técnicos para resolver falhas.
          </li>
          <li>
            <strong>Melhorar os cursos</strong> (interesse legítimo): estatísticas agregadas, por exemplo os exercícios onde mais pessoas erram. Não as usamos para o identificar.
          </li>
          <li>
            <strong>Cumprir a lei</strong>: guardar recibos e responder a pedidos legítimos de autoridades.
          </li>
          <li>
            <strong>Notícias e novidades</strong>, só se as aceitar. Pode deixar de as receber em qualquer altura.
          </li>
        </ul>
        <p className="m-0">Não vendemos os seus dados nem os usamos para publicidade.</p>
      </>
    ),
  },
  {
    id: "gravacoes",
    titulo: "Gravações de áudio",
    corpo: (
      <>
        <p className="m-0">Só gravamos o áudio do exame oral de um curso, e só quando o autoriza no ecrã antes de começar (“Autorizo a gravação desta prova para o professor a poder ouvir”). Guardamos a data dessa autorização.</p>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>
            <strong>Para quê</strong>: para o professor do curso poder ouvir o exame antes de confirmar ou rever a nota dada pela inteligência artificial.
          </li>
          <li>
            <strong>Quem pode ouvir</strong>: você e o professor do curso. A equipa ProEnglish só acede se for preciso para resolver um problema ou uma reclamação sobre a nota.
          </li>
          <li>
            <strong>Onde fica</strong>: no serviço de voz Vapi, que faz a chamada com o tutor (ver “Com quem partilhamos”).
          </li>
          <li>
            <strong>Quanto tempo</strong>: {MESES_RETENCAO_GRAVACOES} meses depois do exame. Depois é apagada automaticamente. A nota e o relatório do exame ficam.
          </li>
          <li>
            <strong>Apagar antes</strong>: no resultado do exame, em “Apagar a gravação”, ou escrevendo para {EMPRESA.emailPrivacidade}. Quando apaga a conta, as gravações também são apagadas.
          </li>
        </ul>
        <p className="m-0">
          Não gravamos as conversas com o tutor, o teste de nível falado nem as lições. Nos exercícios de pronúncia, o áudio de cada resposta é enviado para análise e não é guardado: ficam só a nota e o texto reconhecido. Se no futuro a pronúncia passar a ser avaliada por um serviço especializado, só gravaremos com a sua autorização e actualizaremos esta política antes.
        </p>
      </>
    ),
  },
  {
    id: "partilha",
    titulo: "Com quem partilhamos",
    corpo: (
      <>
        <p className="m-0">
          Usamos alguns serviços externos para fazer a plataforma funcionar. Recebem apenas os dados de que precisam para a sua parte do trabalho, não os podem usar para outros fins e estão obrigados a protegê-los.
        </p>
        <Tabela
          cabecalho={["Serviço", "Para quê e que dados"]}
          linhas={[
            ["Vapi", "A conversa por voz com o tutor: o áudio em tempo real, a transcrição e o seu primeiro nome. Guarda o registo de cada chamada (a transcrição e a duração), que usamos para confirmar a conversa, os minutos e as notas. Guarda a gravação do exame oral, só quando a autoriza."],
            ["Anthropic (Claude)", "As correcções das suas frases, as respostas escritas do tutor e a avaliação das conversas, do teste de nível e do exame oral: o texto das conversas e o nível."],
            ["OpenAI", "A análise da pronúncia (o áudio das respostas) e o assistente de dúvidas (o texto das perguntas)."],
            ["Microsoft (Azure Speech)", "A avaliação detalhada da pronúncia, quando está ligada: o áudio de cada resposta e o texto que devia dizer. Não guardamos esse áudio."],
            ["Google", "Entrar com o Google, se escolher essa opção, e o envio dos emails da plataforma."],
            ["Amazon Web Services", "A transmissão dos vídeos das aulas. Não recebe dados do seu perfil."],
            ["Cloudflare", "As cópias de segurança da base de dados, cifradas."],
            ["Multicaixa Express (EMIS) e o seu banco", "Os pagamentos: o número de telemóvel e o valor."],
          ]}
        />
        <p className="m-0">Também podemos ter de entregar dados a tribunais ou autoridades, quando a lei o exigir.</p>
      </>
    ),
  },
  {
    id: "fora-de-angola",
    titulo: "Dados tratados fora de Angola",
    corpo: (
      <p className="m-0">
        Alguns dos serviços da secção anterior tratam dados fora de Angola, sobretudo nos Estados Unidos e na União Europeia. Fazemos essas transferências nos termos da Lei n.º 22/11, com contratos que obrigam cada serviço a proteger os dados e, quando a lei o exige, com autorização da Agência de Protecção de Dados.
      </p>
    ),
  },
  {
    id: "publico",
    titulo: "O que fica visível para outras pessoas",
    corpo: (
      <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
        <li>
          <strong>Verificação de certificados</strong>: quem tiver o número de um certificado seu vê o seu nome completo, o curso, a nota, o nível de fala e as notas do exame oral, e a data. Não vê o seu email, as gravações nem outros dados.
        </li>
        <li>
          <strong>O professor do curso</strong>: vê o seu progresso, as notas, o seu nível de fala, os erros que repete e os exames orais do curso dele (e ouve a gravação, se a autorizou). Não vê as transcrições das suas conversas.
        </li>
        <li>
          <strong>Liga semanal</strong>: os outros alunos da sua liga vêem o seu primeiro nome com a inicial do apelido (por exemplo, &quot;Ana E.&quot;) e os pontos da semana.
        </li>
        <li>
          <strong>Comentários nas aulas</strong>: quem vê a aula vê o seu nome e o que escreveu.
        </li>
      </ul>
    ),
  },
  {
    id: "prazos",
    titulo: "Quanto tempo guardamos",
    corpo: (
      <>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>Os dados da conta, do estudo e das conversas (incluindo as notas e os relatórios dos exames orais): enquanto a conta existir.</li>
          <li>As gravações dos exames orais: {MESES_RETENCAO_GRAVACOES} meses, ou menos se as apagar.</li>
          <li>Os recibos e os registos de pagamento: pelo prazo que a lei fiscal e comercial angolana exige, mesmo depois de apagar a conta.</li>
          <li>Os registos técnicos de segurança: só o tempo necessário para detectar e resolver problemas.</li>
          <li>Os certificados emitidos: enquanto a conta existir. Depois de apagar a conta, a verificação de um certificado seu deixa de mostrar o seu nome.</li>
        </ul>
        <p className="m-0">
          Quando apaga a conta em Perfil e definições, o nome, o email, o telefone e as preferências são substituídos por dados anónimos e a conta deixa de funcionar. O progresso que fica deixa de estar ligado a si.
        </p>
      </>
    ),
  },
  {
    id: "direitos",
    titulo: "Os seus direitos",
    corpo: (
      <>
        <p className="m-0">Tem direito a:</p>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>saber que dados temos sobre si e receber uma cópia;</li>
          <li>corrigir dados errados (a maioria pode corrigir em Perfil e definições);</li>
          <li>pedir que apaguemos os seus dados (pode apagar a conta sozinho);</li>
          <li>opor-se a um tratamento baseado no nosso interesse legítimo;</li>
          <li>retirar o consentimento que deu, por exemplo para receber novidades.</li>
        </ul>
        <p className="m-0">
          Para exercer estes direitos, escreva para {EMPRESA.emailPrivacidade} a partir do email da conta. Respondemos no prazo de 30 dias. Se achar que não tratámos bem os seus dados, pode apresentar queixa à Agência de Protecção de Dados (APD).
        </p>
      </>
    ),
  },
  {
    id: "seguranca",
    titulo: "Como protegemos os dados",
    corpo: (
      <p className="m-0">
        As ligações são cifradas, as palavras-passe são guardadas cifradas e a sessão fica num cookie que os scripts da página não conseguem ler. Limitamos as tentativas de entrada e de códigos, as cópias de segurança são cifradas e só quem precisa para o trabalho tem acesso aos dados. Se houver uma falha de segurança que afecte os seus dados, avisamo-lo e à APD, como a lei exige.
      </p>
    ),
  },
  {
    id: "cookies",
    titulo: "Cookies e armazenamento no browser",
    corpo: (
      <>
        <p className="m-0">Usamos apenas cookies e armazenamento local necessários para a plataforma funcionar:</p>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>a sessão (para não ter de entrar em cada página), que dura até 7 dias;</li>
          <li>o seu tipo de conta e se tem sessão aberta, para o levar à página certa;</li>
          <li>preferências de ecrã guardadas no seu browser.</li>
        </ul>
        <p className="m-0">
          No site público, e só se aceitar no aviso de cookies, podemos usar o Google Analytics (Google), para contar as visitas, e o Pixel da Meta (Facebook e Instagram), para medir os anúncios. Se recusar, estas ferramentas não são carregadas. Pode mudar a escolha a qualquer momento em “Preferências de cookies”, no rodapé do site.
        </p>
      </>
    ),
  },
  {
    id: "menores",
    titulo: "Menores de idade",
    corpo: (
      <p className="m-0">
        Quem tem menos de 18 anos só pode usar o ProEnglish com autorização de quem tem o poder paternal, como explicam os <L href="/termos#conta">Termos de utilização</L>. Se souber que um menor criou uma conta sem essa autorização, avise-nos e apagamos os dados.
      </p>
    ),
  },
  {
    id: "alteracoes",
    titulo: "Alterações a esta política",
    corpo: (
      <p className="m-0">
        Se mudarmos esta política de forma importante, avisamos por email e na plataforma antes de a mudança valer. A data da versão em vigor está no topo desta página.
      </p>
    ),
  },
  {
    id: "contactos",
    titulo: "Contactos",
    corpo: (
      <p className="m-0">
        Questões de privacidade: {EMPRESA.emailPrivacidade}. Outras questões: {EMPRESA.emailApoio}, {EMPRESA.telefone}. Morada: {EMPRESA.morada}.
      </p>
    ),
  },
];

export default function Privacidade() {
  return (
    <Documento
      titulo="Política de privacidade"
      tipo="privacidade"
      outro={{ href: "/termos", nome: "Termos de utilização" }}
      resumo={[
        "Recolhemos o necessário para o ensinar: conta, progresso, conversas com o tutor e pagamentos.",
        "O áudio das conversas e da pronúncia é analisado e não fica gravado. Guardamos a transcrição.",
        `Só o exame oral pode ser gravado, e só com a sua autorização: ouvem-no você e o professor do curso, durante ${MESES_RETENCAO_GRAVACOES} meses.`,
        "Não vendemos os seus dados nem os usamos para publicidade.",
        "Alguns serviços que usamos, como o tutor com inteligência artificial, tratam dados fora de Angola.",
        "Quem tiver o número de um certificado seu vê o seu nome, o curso e a nota.",
        "Pode ver, corrigir e apagar os seus dados. Apagar a conta está em Perfil e definições.",
      ]}
      seccoes={SECCOES}
    />
  );
}
