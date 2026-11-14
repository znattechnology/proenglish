import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_FRONTEND_URL || "http://localhost:3000";
  return ["/", "/about", "/termos", "/privacidade"].map((p) => ({ url: `${base}${p}`, changeFrequency: p === "/" ? "weekly" : "monthly", priority: p === "/" ? 1 : 0.5 }));
}
