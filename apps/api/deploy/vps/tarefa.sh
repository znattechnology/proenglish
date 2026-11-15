#!/bin/sh
# Corre um comando do Django dentro da API em execução e regista-o (usado pelo crontab.txt).
#   tarefa.sh <comando> [argumentos]
# Registo em /opt/proenglish/logs/cron.log, que nunca passa das últimas 20 000 linhas.
set -u
DIR=$(cd "$(dirname "$0")" && pwd)
LOG=${PROENGLISH_CRON_LOG:-/opt/proenglish/logs/cron.log}
mkdir -p "$(dirname "$LOG")"
{
  echo "$(date -u '+%F %T') == $*"
  cd "$DIR" && docker compose exec -T api python manage.py "$@"
  echo "$(date -u '+%F %T') == $1 terminou ($?)"
} >> "$LOG" 2>&1
if [ "$(wc -l < "$LOG")" -gt 25000 ]; then
  tail -n 20000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
