import Link from "next/link";
import { Documento, type Seccao } from "@/components/pe/legal/Documento";
import { EMPRESA } from "@/src/domains/legal/empresa";

export const metadata = {
  title: "Termos de utilização | ProEnglish",
  description: "As regras de utilização do ProEnglish: conta, planos, pagamentos em kwanzas, tutor com IA e certificados.",
};

const L = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <Link href={href} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
    {children}
  </Link>
);

const SECCOES: Seccao[] = [
  {
    id: "quem-somos",
    titulo: "Quem somos e o que são estes termos",
    corpo: (
      <>
        <p className="m-0">
          O ProEnglish é uma plataforma de inglês para profissionais, gerida por {EMPRESA.nomeLegal}, NIF {EMPRESA.nif}, com sede em {EMPRESA.morada} (&quot;nós&quot;).
        </p>
        <p className="m-0">
          Estes termos são o acordo entre nós e quem usa a plataforma (&quot;você&quot;). Ao criar uma conta, aceita-os. A forma como tratamos os seus dados está na <L href="/privacidade">Política de privacidade</L>, que faz parte deste acordo.
        </p>
      </>
    ),
  },
  {
    id: "conta",
    titulo: "A sua conta",
    corpo: (
      <>
        <p className="m-0">Para criar uma conta precisa de ter 18 anos ou, entre os 14 e os 17 anos, autorização de quem tem o poder paternal.</p>
        <p className="m-0">
          A conta é pessoal: não a partilhe nem empreste. Use um email que só você controla e uma palavra-passe que não usa noutros sites. Se suspeitar que alguém entrou na sua conta, mude a palavra-passe em Perfil e definições e avise-nos.
        </p>
        <p className="m-0">Os dados que nos dá (nome, email, telefone) têm de ser verdadeiros. O nome que escrever é o que aparece nos certificados.</p>
      </>
    ),
  },
  {
    id: "planos",
    titulo: "Planos e o que cada um inclui",
    corpo: (
      <>
        <p className="m-0">
          O ProEnglish funciona por subscrição. Não vendemos cursos avulsos: o plano que tem decide os cursos, as lições e os minutos de conversa com o tutor a que tem acesso.
        </p>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>
            <strong>Gratuito:</strong> sem custo e sem cartão, com um número limitado de lições por dia e minutos de conversa com o tutor.
          </li>
          <li>
            <strong>Premium e Premium Plus:</strong> pagos em kwanzas, por mês ou por ano, com mais cursos, lições sem limite diário, mais minutos de conversa e certificados.
          </li>
        </ul>
        <p className="m-0">
          Os preços e os limites de cada plano estão sempre na página <L href="/user/upgrade">Planos</L> e no momento do pagamento. O que lá estiver quando paga é o que vale para esse período.
        </p>
      </>
    ),
  },
  {
    id: "pagamentos",
    titulo: "Pagamentos e renovação",
    corpo: (
      <>
        <p className="m-0">Os pagamentos são feitos em kwanzas (Kz) por Multicaixa Express, a partir do seu telemóvel. Não pedimos nem guardamos dados de cartão.</p>
        <p className="m-0">
          Não fazemos cobranças automáticas. Quando o período pago está a terminar, avisamos 3 dias antes e no próprio dia. Se não renovar, a conta passa para o plano Gratuito no fim do período e o seu progresso fica guardado.
        </p>
        <p className="m-0">Cada pagamento tem um recibo, que pode ver e descarregar em Subscrição. Os códigos promocionais valem nas condições e no prazo indicados em cada um e não se trocam por dinheiro.</p>
      </>
    ),
  },
  {
    id: "cancelar",
    titulo: "Deixar de renovar e devoluções",
    corpo: (
      <>
        <p className="m-0">Pode deixar de renovar em qualquer altura, em Subscrição. Continua com o plano até ao fim do período que já pagou.</p>
        <p className="m-0">
          Se for cobrado duas vezes, ou cobrado sem ter recebido o plano, devolvemos o valor depois de confirmarmos o pagamento com a Multicaixa. Fora destes casos, não devolvemos a parte de um período que ficou por usar, salvo quando a lei o exigir.
        </p>
        <p className="m-0">Para pedir uma devolução, escreva para {EMPRESA.emailApoio} com o número do recibo.</p>
      </>
    ),
  },
  {
    id: "tutor",
    titulo: "Conversa com o tutor e outras funções com inteligência artificial",
    corpo: (
      <>
        <p className="m-0">
          O tutor de conversa, as correcções das suas frases e as notas das conversas são gerados por inteligência artificial. Servem para praticar e podem ter erros. Não são uma avaliação oficial nem substituem um professor ou um exame de certificação de língua.
        </p>
        <p className="m-0">
          Cada plano tem um número de minutos de conversa por dia. O tempo é contado por nós, desde que a conversa começa até terminar, e cada minuto começado conta como um minuto.
        </p>
        <p className="m-0">Não diga nem escreva ao tutor dados sensíveis, como números de documentos, palavras-passe ou informação de saúde. O que diz é transcrito para lhe dar o resumo da conversa.</p>
      </>
    ),
  },
  {
    id: "certificados",
    titulo: "Certificados",
    corpo: (
      <>
        <p className="m-0">
          Um certificado é emitido quando conclui um curso com os requisitos indicados nesse curso (por exemplo, 70% ou mais na nota final). Os certificados fazem parte dos planos pagos.
        </p>
        <p className="m-0">
          Cada certificado tem um número. Qualquer pessoa com o número pode confirmar na nossa página de verificação o seu nome, o curso, a nota e a data, sem precisar de conta. É isso que permite a uma empresa confiar no certificado.
        </p>
        <p className="m-0">Podemos revogar um certificado obtido com fraude, por exemplo com outra pessoa a fazer os questionários. Um certificado revogado aparece como tal na verificação.</p>
      </>
    ),
  },
  {
    id: "regras",
    titulo: "O que não é permitido",
    corpo: (
      <>
        <p className="m-0">Ao usar o ProEnglish, compromete-se a não:</p>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5">
          <li>partilhar a conta ou vender o acesso;</li>
          <li>copiar, gravar, publicar ou revender as aulas, os exercícios ou os materiais;</li>
          <li>tentar contornar os limites do plano, os pagamentos ou a segurança da plataforma;</li>
          <li>usar programas automáticos para fazer lições, questionários ou conversas;</li>
          <li>insultar, ameaçar ou assediar outras pessoas, incluindo nos comentários das aulas.</li>
        </ul>
        <p className="m-0">Se não cumprir estas regras, podemos suspender ou fechar a conta, conforme a gravidade, e avisamo-lo do motivo.</p>
      </>
    ),
  },
  {
    id: "conteudos",
    titulo: "Conteúdos e propriedade intelectual",
    corpo: (
      <>
        <p className="m-0">
          As aulas, os textos, os áudios, os exercícios, a marca ProEnglish e o desenho da plataforma pertencem-nos ou a quem nos deu licença para os usar. O seu plano dá-lhe o direito de os usar para aprender, não de os copiar ou distribuir.
        </p>
        <p className="m-0">O que escrever nos comentários continua a ser seu, mas autoriza-nos a mostrá-lo na plataforma enquanto o comentário existir.</p>
      </>
    ),
  },
  {
    id: "disponibilidade",
    titulo: "Disponibilidade e mudanças no serviço",
    corpo: (
      <>
        <p className="m-0">
          Fazemos o possível para que a plataforma esteja sempre disponível, mas pode haver interrupções para manutenção ou por falhas de rede, de energia ou de serviços de terceiros. Avisamos com antecedência as manutenções planeadas.
        </p>
        <p className="m-0">Podemos melhorar, mudar ou retirar cursos e funções. Se uma mudança tirar algo importante do plano que já pagou, pode pedir a devolução da parte que fica por usar.</p>
      </>
    ),
  },
  {
    id: "responsabilidade",
    titulo: "Responsabilidade",
    corpo: (
      <>
        <p className="m-0">
          O ProEnglish ajuda a aprender inglês, mas não garante um resultado, como um emprego ou uma promoção. Não respondemos por prejuízos indirectos causados pelo uso da plataforma, nem por falhas que não dependam de nós.
        </p>
        <p className="m-0">Nada nestes termos limita os direitos que a lei angolana lhe dá como consumidor.</p>
      </>
    ),
  },
  {
    id: "fim-da-conta",
    titulo: "Fechar a conta",
    corpo: (
      <p className="m-0">
        Pode apagar a conta quando quiser, em Perfil e definições. Ao apagá-la, os seus dados pessoais são retirados e a conta deixa de funcionar. Guardamos apenas o que a lei nos obriga a guardar, como os recibos. Os detalhes estão na <L href="/privacidade#prazos">Política de privacidade</L>.
      </p>
    ),
  },
  {
    id: "alteracoes",
    titulo: "Alterações a estes termos",
    corpo: (
      <p className="m-0">
        Se mudarmos estes termos, avisamos por email e na plataforma pelo menos 30 dias antes de a mudança valer. Se não concordar, pode deixar de renovar ou apagar a conta antes dessa data. A data da versão em vigor está no topo desta página.
      </p>
    ),
  },
  {
    id: "lei",
    titulo: "Lei aplicável e litígios",
    corpo: (
      <p className="m-0">
        Estes termos regem-se pela lei da República de Angola. Antes de qualquer outro passo, fale connosco para tentarmos resolver a questão. Se não for possível, são competentes os tribunais de Luanda, sem prejuízo dos direitos que a lei dá aos consumidores.
      </p>
    ),
  },
  {
    id: "contactos",
    titulo: "Contactos",
    corpo: (
      <p className="m-0">
        Para dúvidas sobre estes termos, a sua conta ou pagamentos: {EMPRESA.emailApoio}, {EMPRESA.telefone}.
      </p>
    ),
  },
];

export default function Termos() {
  return (
    <Documento
      titulo="Termos de utilização"
      tipo="termos"
      outro={{ href: "/privacidade", nome: "Política de privacidade" }}
      resumo={[
        "A conta é pessoal. Não a partilhe.",
        "Paga em kwanzas por Multicaixa Express. Não há cobranças automáticas: avisamos antes de o plano terminar.",
        "Se não renovar, passa para o Gratuito e o progresso fica guardado.",
        "O tutor e as correcções usam inteligência artificial e podem errar.",
        "Os certificados podem ser confirmados por qualquer empresa pelo número.",
        "Pode apagar a conta quando quiser.",
      ]}
      seccoes={SECCOES}
    />
  );
}
