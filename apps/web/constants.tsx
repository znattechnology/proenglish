
import { LayoutDashboard, Users, BookOpen, UserCog, MessageSquare, DollarSign, Settings2, BarChart2, Package, Bus } from 'lucide-react';


export const sidebarLinks = [
  {
    title: "Home",
    url: "/dashboard",
    icon: LayoutDashboard,
    isActive: true,
    items: [
      {
        title: "Visão Geral",
        url: "/dashboard",
      },
    ],
  },
  {
    title: "Utilizadores",
    url: "/dashboard/users",
    icon: Users,
    items: [
      { title: "Utilizadores", url: "/dashboard/users/users" },
      { title: "Facturas", url: "/dashboard/users/faturas" },
      { title: "Equipa", url: "/dashboard/users/team" },
    ],
  },
  {
    title: "Cursos",
    url: "/dashboard/content",
    icon: BookOpen,
    items: [
      { title: "Criar curso", url: "/dashboard/content/create-course" },
      { title: "Cursos", url: "/dashboard/content/courses" },
    ],
  },
  {
    title: "Live",
    url: "/dashboard/live",
    icon: MessageSquare, // Escolha um ícone apropriado
    items: [
      { title: "Live", url: "/dashboard/live/live" },
      { title: "Próximas Live", url: "/dashboard/live/upcoming-live" },
      { title: "Live Pessoal", url: "/dashboard/live/personal-live" },
      { title: "Gravadas", url: "/dashboard/live/recordings" },
      { title: "Passadas", url: "/dashboard/live/previous-live" },
    ],
  },
  {
    title: "Analítica",
    url: "/dashboard/analitycs",
    icon: BarChart2,
    items: [
      { title: "Cursos", url: "/dashboard/analityc/course-analitcs" },
      { title: "Utilizadores", url: "/dashboard/analityc/users-analitcs" },
      { title: "Compras", url: "/dashboard/analityc/orders-analitcs" },
    ],
  },
  {
    title: "Definições",
    url: "/dashboard/manage",
    icon: Settings2,
    items: [
      { title: "Banner", url: "/dashboard/manage/banner" },
      { title: "Faq", url: "/dashboard/manage/faq" },
      { title: "Categorias", url: "/dashboard/manage/categories" },
    ],
  },
  {
    title: "Ajuda",
    url: "/dashboard/help",
    icon: Package, // Escolha um ícone apropriado
    items: [],
  },
];


export const exploreWorlds = [
  {
    id: 'world-1',
    imgUrl: '/service-2.jpg',
    title: 'Inglês para Petróleo & Gás',
    description: 'Especializado para Sonangol, Total Angola e Chevron. Aprenda terminologia técnica, protocolos de segurança e comunicação internacional específica do sector energético angolano.',
    icon: '🛢️',
    companies: ['Sonangol', 'Total Angola', 'Chevron'],
    students: '2.5K+',
    level: 'Técnico-Profissional',
    duration: '3-6 meses',
    certification: 'Certificado Internacional'
  },
  {
    id: 'world-2',
    imgUrl: '/service-3.jpg',
    title: 'Inglês Bancário',
    description: 'Desenvolvido para BAI, BFA e Standard Bank. Domine transacções internacionais, análise de crédito, compliance e atendimento a clientes internacionais.',
    icon: '🏦',
    companies: ['BAI', 'BFA', 'Standard Bank'],
    students: '1.8K+',
    level: 'Profissional-Executivo',
    duration: '2-4 meses',
    certification: 'Certificado Bancário'
  },
  {
    id: 'world-3',
    imgUrl: '/service-4.jpg',
    title: 'Inglês para TI & Telecomunicações',
    description: 'Criado para Unitel, MS Telecom e startups tech. Vocabulário de programação, metodologias ágeis, cloud computing e liderança de equipas remotas.',
    icon: '💻',
    companies: ['Unitel', 'MS Telecom', 'Angola Telecom'],
    students: '1.2K+',
    level: 'Técnico-Avançado',
    duration: '2-5 meses',
    certification: 'Certificado Tech'
  },
  {
    id: 'world-4',
    imgUrl: '/service-5.jpg',
    title: 'Inglês Executivo',
    description: 'Para C-Level e gestores sénior. Liderança internacional, negociações estratégicas, apresentações executivas e networking global com foco no mercado angolano.',
    icon: '👔',
    companies: ['Multinacionais', 'Governo', 'ONGs'],
    students: '950+',
    level: 'Executivo-CEO',
    duration: '4-8 meses',
    certification: 'Certificado Executivo'
  },
  {
    id: 'world-5',
    imgUrl: '/service-6.jpg',
    title: 'Inglês com IA Personal Tutor',
    description: 'A nossa tecnologia exclusiva! Correcção da pronúncia em tempo real, feedback personalizado para sotaque angolano e aprendizagem adaptativa com inteligência artificial.',
    icon: '🤖',
    companies: ['Exclusivo ProEnglish'],
    students: '3.2K+',
    level: 'Todos os níveis',
    duration: 'Contínuo',
    certification: 'Certificado IA-Enhanced'
  },
];


export const startingFeatures = [
  'Encontre um mundo que se adeque ao seu perfil e que queira explorar',
  'Entre no mundo da aprendizagem de inglês com segurança e confiança',
  'Não precisa de rodeios, mantenha-se focado e divirta-se enquanto aprende',
];

export const newFeatures = [
  {
    imgUrl: '/vrpano.svg',
    title: 'A new world',
    subtitle:
        'we have the latest update with new world for you to try never mind',
  },
  {
    imgUrl: '/headset.svg',
    title: 'Mais realista',
    subtitle:
        'Na última actualização, a experiência tornou-se mais realista do que nunca, proporcionando aprendizagem imersiva',
  },
];

export const insights = [
  {
    imgUrl: '/planet-06.png',
    title: 'A revolução do ensino digital chegou a Angola',
    subtitle:
        'Tecnologia avançada de ensino de inglês adaptada à realidade angolana. Aprenda com metodologias inovadoras e conteúdo localizado.',
  },
  {
    imgUrl: '/planet-07.png',
    title: '7 dicas para dominar facilmente o inglês angolano',
    subtitle:
        'Descubra as melhores técnicas adaptadas para o contexto angolano. Metodologias comprovadas que aceleram a sua aprendizagem de inglês.',
  },
  {
    imgUrl: '/planet-08.png',
    title: 'Com uma plataforma pode explorar o mundo todo virtualmente',
    subtitle:
        'Acesso global a oportunidades internacionais. Ligue-se ao mundo através do inglês e expanda os seus horizontes profissionais.',
  },
];

export const socials = [
  {
    name: 'twitter',
    url: '/twitter.svg',
  },
  {
    name: 'linkedin',
    url: '/linkedin.svg',
  },
  {
    name: 'instagram',
    url: '/instagram.svg',
  },
  {
    name: 'facebook',
    url: '/facebook.svg',
  },
];

export const navigation = [
  {
    id: "0",
    title: "Features",
    url: "#features",
  },
  {
    id: "1",
    title: "Preços",
    url: "#pricing",
  },
  {
    id: "2",
    title: "Como usar",
    url: "#how-to-use",
  },
  {
    id: "3",
    title: "Roteiro",
    url: "#roadmap",
  },
  {
    id: "4",
    title: "Nova conta",
    url: "#signup",
    onlyMobile: true,
  },
  {
    id: "5",
    title: "Iniciar sessão",
    url: "#login",
    onlyMobile: true,
  },
];
