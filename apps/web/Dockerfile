# Web do ProEnglish (Next.js) para o servidor partilhado, atrás do Caddy.
# Os endereços públicos (NEXT_PUBLIC_*) ficam fixos na imagem no momento do build.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_DJANGO_API_URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_FRONTEND_URL
ENV NEXT_PUBLIC_DJANGO_API_URL=$NEXT_PUBLIC_DJANGO_API_URL \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_FRONTEND_URL=$NEXT_PUBLIC_FRONTEND_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN test -n "$NEXT_PUBLIC_DJANGO_API_URL" || { echo "falta NEXT_PUBLIC_DJANGO_API_URL"; exit 1; }
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S web && adduser -S web -G web
COPY --from=build --chown=web:web /app/.next/standalone ./
COPY --from=build --chown=web:web /app/.next/static ./.next/static
COPY --from=build --chown=web:web /app/public ./public
USER web
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/robots.txt || exit 1
CMD ["node", "server.js"]
