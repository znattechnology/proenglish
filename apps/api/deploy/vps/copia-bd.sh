#!/bin/sh
# Cópia diária da base do ProEnglish (no cron do utilizador deploy).
#
# No Neon havia histórico para voltar atrás; aqui é isto que o substitui:
# um pg_dump guardado em /opt/proenglish/copias (7 dias) e no R2, em copias-bd/
# (30 dias). O bucket é privado.
#
# Cron (crontab -e, utilizador deploy):
#   55 3 * * * /opt/proenglish/app/apps/api/deploy/vps/copia-bd.sh >> /opt/proenglish/copias.log 2>&1 # proenglish
#
# Repor:  docker exec -i proenglish-postgres-1 pg_restore -U proenglish -d proenglish --clean --if-exists --no-owner < ficheiro.dump
set -eu
umask 077  # o dump tem os hashes das palavras-passe
ENV=${PROENGLISH_ENV:-/opt/proenglish/app/apps/api/deploy/vps/.env}
DIR=${PROENGLISH_COPIAS:-/opt/proenglish/copias}
CONTENTOR=${PROENGLISH_PG:-proenglish-postgres-1}
mkdir -p "$DIR"
chmod 700 "$DIR"
val() { grep "^$1=" "$ENV" | cut -d= -f2- | tr -d '"'; }

F="proenglish-$(date +%F-%H%M).dump"
docker exec "$CONTENTOR" pg_dump -U proenglish -d proenglish -Fc > "$DIR/$F.parcial"
mv "$DIR/$F.parcial" "$DIR/$F"
find "$DIR" -name 'proenglish-*.dump' -mtime +7 -delete
find "$DIR" -name '*.parcial' -mmin +120 -delete

if [ -z "$(val R2_ACCESS_KEY_ID)" ]; then
  echo "$(date '+%F %T') AVISO $F só local: R2 por configurar no .env"
  exit 1
fi

# As chaves vão num ficheiro só para o dono, não na linha de comando.
CHAVES=$(mktemp)
trap 'rm -f "$CHAVES"' EXIT
cat > "$CHAVES" <<CHAVES_EOF
AWS_ACCESS_KEY_ID=$(val R2_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY=$(val R2_SECRET_ACCESS_KEY)
AWS_DEFAULT_REGION=auto
AWS_REQUEST_CHECKSUM_CALCULATION=when_required
AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
CHAVES_EOF
s3() {
  docker run --rm --env-file "$CHAVES" -v "$DIR:/c:ro" amazon/aws-cli:2.36.41 \
    --endpoint-url "https://$(val R2_ACCOUNT_ID).r2.cloudflarestorage.com" s3 "$@"
}
DESTINO="s3://$(val R2_BUCKET)/copias-bd"
s3 cp "/c/$F" "$DESTINO/$F" --only-show-errors

# Apagar no R2 o que tiver mais de 30 dias (a data vem no nome).
LIMITE=$(date -d '30 days ago' +%F)
s3 ls "$DESTINO/" | awk '{print $4}' | while read -r velho; do
  dia=$(echo "$velho" | sed -n 's/^proenglish-\([0-9-]\{10\}\)-.*/\1/p')
  if [ -n "$dia" ] && [ "$dia" \< "$LIMITE" ]; then s3 rm "$DESTINO/$velho" --only-show-errors; fi
done

echo "$(date '+%F %T') ok $F $(du -h "$DIR/$F" | cut -f1)"
