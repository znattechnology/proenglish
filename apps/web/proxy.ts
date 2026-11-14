import { NextRequest, NextResponse } from "next/server";
import { djangoAuthMiddleware } from "@/lib/django-middleware";

// Public routes that should always be accessible without authentication
const PUBLIC_AUTH_ROUTES = ['/signin', '/signup', '/verify-email', '/forgot-password', '/auth/google/callback', '/convite', '/confirmar-email-novo'];

function isPublicAuthRoute(pathname: string): boolean {
  return PUBLIC_AUTH_ROUTES.some(route =>
    pathname === route || pathname.startsWith(`${route}/`)
  );
}

// Manutenção: o estado é lido da API no máximo de 30 em 30 segundos.
const API = process.env.DJANGO_API_URL_INTERNA || process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";
let manutencao = { activa: false, ate: 0 };
async function emManutencao() {
  if (Date.now() < manutencao.ate) return manutencao.activa;
  try {
    const r = await fetch(`${API}/site/manutencao/`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    if (!r.ok) throw new Error(String(r.status));
    const d = await r.json();
    manutencao = { activa: !!d?.activa, ate: Date.now() + 30_000 };
  } catch {
    // API em baixo (muitas vezes é a própria manutenção): fica o último estado conhecido.
    manutencao = { activa: manutencao.activa, ate: Date.now() + 10_000 };
  }
  return manutencao.activa;
}

/** Quem já tem sessão aberta (alunos, professores, administradores) continua a usar a plataforma. */
function temSessao(request: NextRequest) {
  return !!(request.cookies.get("access_token")?.value || request.cookies.get("refresh_token")?.value);
}

const LIVRES_NA_MANUTENCAO = ["/manutencao", "/signin", "/auth/", "/forgot-password", "/verify-email", "/convite", "/confirmar-email-novo", "/certificados", "/termos", "/privacidade", "/offline"];

export default async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    !pathname.startsWith("/_next/") &&
    !pathname.startsWith("/api/") &&
    !pathname.includes(".") &&
    !LIVRES_NA_MANUTENCAO.some((p) => pathname === p || pathname.startsWith(p.endsWith("/") ? p : `${p}/`)) &&
    !temSessao(request) &&
    (await emManutencao())
  ) {
    const url = request.nextUrl.clone();
    url.pathname = "/manutencao";
    url.search = "";
    // O cabeçalho diz à página que veio do proxy: assim não redirecciona para "/" (ciclo) se o estado em cache estiver atrasado.
    const cabecalhos = new Headers(request.headers);
    cabecalhos.set("x-pe-manutencao", "1");
    return NextResponse.rewrite(url, { status: 503, headers: { "Retry-After": "600" }, request: { headers: cabecalhos } });
  }

  // Skip middleware for static files and API routes
  if (
    pathname.startsWith('/_next/') ||
    pathname.startsWith('/api/') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Allow public auth routes to pass through immediately
  if (isPublicAuthRoute(pathname)) {
    // Handle explicit logout - clear cookies
    const isExplicitLogout = request.nextUrl.searchParams.get('logout') === 'true';
    if (isExplicitLogout) {
      const response = NextResponse.next();
      response.cookies.delete('access_token');
      response.cookies.delete('refresh_token');
      response.cookies.delete('auth_state');
      return response;
    }
    return NextResponse.next();
  }

  // For all other routes, use the Django auth middleware
  return djangoAuthMiddleware(request);
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};