#!/bin/sh
# Deploy do ProEnglish no servidor partilhado (correm-no os workflows api-deploy.yml e
# web-deploy.yml por SSH; também se pode correr à mão). Só mexe no projecto compose
# "proenglish" e no bloco "# >>> proenglish" do crontab: nunca toca no Caddy nem nos outros
# projectos.
#
#   ./deploy.sh api <imagem>    p.ex. ./deploy.sh api ghcr.io/znattechnology/proenglish-api:<sha>
#   ./deploy.sh web <imagem>    p.ex. ./deploy.sh web ghcr.io/znattechnology/proenglish-web:<sha>
#   ./deploy.sh <imagem>        o mesmo que "api" (forma antiga)
#
# API: confirma o .env -> descarrega a imagem -> migrações -> troca a API -> espera que fique
# saudável (se não ficar, volta à imagem anterior e falha) -> instala as tarefas agendadas.
# Web: descarrega -> troca -> espera que fique saudável (senão volta à anterior).
# Atenção: voltar atrás repõe a imagem, não desfaz migrações. As migrações têm de ser
# compatíveis com a versão anterior (só acrescentar), como têm sido.
set -eu

case "${1:-}" in
  api|web) SERVICO=$1; NOVA=${2:?uso: deploy.sh api|web <imagem>} ;;
  "") echo "uso: deploy.sh api|web <imagem>" >&2; exit 2 ;;
  *) SERVICO=api; NOVA=$1 ;;
esac
DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"
ENV_FILE="$DIR/.env"
if [ "$SERVICO" = api ]; then VAR=API_IMAGE; else VAR=WEB_IMAGE; fi
CONTENTOR="proenglish-$SERVICO-1"

msg() { echo "== $*"; }
erro() { echo "ERRO: $*" >&2; exit 1; }

test -f "$ENV_FILE" || erro "falta $ENV_FILE (ver README, instalação inicial)"
val() { grep "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '"' || true; }

# Um deploy de cada vez (a API e a web podem chegar ao mesmo tempo e ambas escrevem no .env).
exec 9> /opt/proenglish/.deploy.lock
flock -w 900 9 || erro "outro deploy em curso há mais de 15 minutos"

# ── 1. Configuração mínima ─────────────────────────────────────────────────
msg "Configuração ($SERVICO)"
falta=""
for v in POSTGRES_PASSWORD SECRET_KEY ALLOWED_HOSTS FRONTEND_URL BACKEND_BASE_URL CORS_ALLOWED_ORIGINS; do
  [ -n "$(val $v)" ] || falta="$falta $v"
done
[ -z "$falta" ] || erro "variáveis vazias no .env:$falta"
[ "$(val TRUSTED_PROXY)" = "True" ] || erro "TRUSTED_PROXY=True é obrigatório atrás do Caddy (IP dos alunos e HTTPS)"
case "$(val SECRET_KEY)" in django-insecure*) erro "SECRET_KEY de desenvolvimento" ;; esac
# Avisos que não param o deploy (decisões do negócio):
if [ "$(val PAGAMENTOS_SIMULADOS)" = "True" ]; then
  echo "AVISO: PAGAMENTOS_SIMULADOS=True: qualquer pessoa pode activar planos sem pagar."
fi
if [ -n "$(val VAPI_PRIVATE_KEY)" ]; then
  case "$(val VAPI_WEBHOOK_SECRET)" in ""|default_webhook_secret) erro "VAPI_WEBHOOK_SECRET por definir com o Vapi ligado" ;; esac
fi

# ── 2. Imagem ──────────────────────────────────────────────────────────────
ANTERIOR=$(val $VAR)
msg "Imagem nova: $NOVA (anterior: ${ANTERIOR:-nenhuma})"
docker pull --quiet "$NOVA" >/dev/null

definir_imagem() {
  # A imagem em uso fica no .env: o docker compose lê-a, e os comandos à mão usam a mesma.
  tmp=$(mktemp "$DIR/.env.XXXXXX")
  grep -v "^$VAR=" "$ENV_FILE" > "$tmp" || true
  echo "$VAR=$1" >> "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

esperar_saude() {
  i=0
  while [ $i -lt 36 ]; do  # até 3 minutos
    estado=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}sem-healthcheck{{end}}' "$CONTENTOR" 2>/dev/null || echo "?")
    [ "$estado" = "healthy" ] && return 0
    sleep 5; i=$((i + 1))
  done
  return 1
}

# ── 3. API: base de dados e migrações (a API antiga continua a servir) ──────
if [ "$SERVICO" = api ]; then
  msg "Base de dados"
  docker compose up -d --wait postgres
  msg "Migrações"
  API_IMAGE="$NOVA" docker compose run --rm --no-deps api python manage.py migrate --noinput
fi

# ── 4. Trocar o serviço ────────────────────────────────────────────────────
msg "A trocar: $SERVICO"
definir_imagem "$NOVA"
docker compose up -d --no-deps "$SERVICO"
if ! esperar_saude; then
  echo "ERRO: $SERVICO não ficou saudável com a imagem nova" >&2
  docker compose logs --tail=100 "$SERVICO" >&2 || true
  if [ -n "$ANTERIOR" ] && [ "$ANTERIOR" != "$NOVA" ]; then
    msg "A voltar à imagem anterior: $ANTERIOR"
    definir_imagem "$ANTERIOR"
    docker compose up -d --no-deps "$SERVICO"
    if esperar_saude; then echo "Imagem anterior reposta e saudável."; else echo "ERRO: a imagem anterior também não ficou saudável" >&2; fi
  fi
  exit 1
fi
docker compose ps

# ── 5. Tarefas agendadas (só o bloco do ProEnglish no crontab) ─────────────
msg "Tarefas agendadas"
mkdir -p /opt/proenglish/logs
tmp=$(mktemp)
crontab -l 2>/dev/null | sed '/^# >>> proenglish/,/^# <<< proenglish/d' \
  | grep -v '# proenglish$' > "$tmp" || true   # também a linha antiga da cópia, se existir
{ echo "# >>> proenglish (gerido por deploy.sh: não editar aqui)"; grep -v '^#' crontab.txt | sed '/^$/d'; echo "# <<< proenglish"; } >> "$tmp"
crontab "$tmp"
rm -f "$tmp"

# ── 6. Limpeza: ficam a imagem nova e a anterior (para voltar atrás) ───────
REPO=${NOVA%:*}
docker images "$REPO" --format '{{.Repository}}:{{.Tag}}' | while read -r img; do
  [ "$img" = "$NOVA" ] || [ "$img" = "$ANTERIOR" ] || docker rmi "$img" >/dev/null 2>&1 || true
done
# (Sem "docker image prune": o servidor é partilhado e isso apagaria imagens dos outros projectos.)

msg "Deploy concluído: $SERVICO $NOVA"
