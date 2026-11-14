import type { MetadataRoute } from "next";

/** A app instalável (PWA). Valores da tela "Ícone da app" do canvas. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/user/dashboard",
    name: "ProEnglish",
    short_name: "ProEnglish",
    description: "Inglês para profissionais: cursos, prática diária e conversa com um tutor.",
    lang: "pt-PT",
    start_url: "/user/dashboard?origem=app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#000066",
    theme_color: "#000066",
    categories: ["education"],
    icons: [
      { src: "/icons/app-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/app-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/app-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Praticar uma lição", url: "/user/laboratory/learn", icons: [{ src: "/icons/app-192.png", sizes: "192x192" }] },
      { name: "Conversa com o tutor", url: "/user/laboratory/speaking/real-time", icons: [{ src: "/icons/app-192.png", sizes: "192x192" }] },
    ],
  };
}
