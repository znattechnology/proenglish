# ProEnglish API no servidor mambo-labtic

Servidor `2.31.122.170` (utilizador `deploy`), partilhado com o LabTIC e O Mambo.
A API e a sua base de dados PostgreSQL correm em Docker, em `/opt/proenglish`.
O Caddy de `/opt/proxy` trata do HTTPS e encaminha `api.proenglish.cloud` para a API.

```
/opt/proenglish/
├── app/                      checkout do monorepo
│   └── apps/api/deploy/vps/  docker-compose.yml, .env, copia-bd.sh
├── copias/                   dumps diários (7 dias)
└── copias.log
```

| Serviço    | Imagem               | Memória | Rede               |
|------------|----------------------|---------|--------------------|
| `postgres` | `postgres:18-alpine` | 256 MB  | interna            |
| `api`      | `proenglish/api`     | 512 MB  | interna + publica  |

Não há nginx, certbot nem Redis: o Caddy faz o HTTPS, o WhiteNoise serve os ficheiros
estáticos e a aplicação não usa Redis em produção.

## 1. Instalação inicial (uma vez)

```sh
ssh deploy@2.31.122.170
mkdir -p /opt/proenglish && cd /opt/proenglish
git clone <URL do repositório> app
cd app/apps/api/deploy/vps
cp .env.example .env && chmod 600 .env
nano .env        # POSTGRES_PASSWORD, SECRET_KEY, R2_* e as chaves copiadas da produção actual
docker compose build api
docker compose up -d postgres
```

Nesta altura a base existe mas está vazia. **Não correr `migrate`** se os dados vêm do
Neon: o passo 2 traz o esquema e os dados juntos.

## 2. Trazer os dados do Neon

Fazer numa janela de manutenção, com a API antiga parada, para não se perderem escritas.

```sh
# a) Versão do Neon: tem de ser 18 ou inferior.
docker run --rm postgres:18-alpine psql "<DATABASE_URL do Neon>" -Atc "show server_version"

# b) Dump (usar o endereço directo do Neon, sem "-pooler" no nome do host).
docker run --rm postgres:18-alpine pg_dump "<DATABASE_URL do Neon>" -Fc --no-owner --no-acl \
  > /opt/proenglish/neon.dump

# c) Repor na base local.
docker exec -i proenglish-postgres-1 pg_restore -U proenglish -d proenglish --no-owner --no-acl \
  < /opt/proenglish/neon.dump

# d) Conferir: as contagens têm de bater com as do Neon.
docker exec proenglish-postgres-1 psql -U proenglish -d proenglish -c \
  "select relname, n_live_tup from pg_stat_user_tables order by n_live_tup desc limit 15"

# e) Aplicar migrações que faltem e arrancar.
docker compose run --rm api python manage.py migrate --noinput
docker compose up -d api
```

Guardar `neon.dump` fora do servidor e apagá-lo de lá. Manter o projecto no Neon uma ou
duas semanas sem uso, como recurso, e só depois apagá-lo.

## 3. Caddy e DNS

1. Acrescentar o conteúdo de `Caddyfile.snippet` a `/opt/proxy/caddy/Caddyfile`
   (fazer antes uma cópia `Caddyfile.bak-<data>`), validar e recarregar:
   ```sh
   cd /opt/proxy
   docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
   docker compose exec caddy caddy reload   --config /etc/caddy/Caddyfile
   ```
2. Testar em `https://proenglish-api.2.31.122.170.sslip.io/api/health/`
   (juntar esse nome a `ALLOWED_HOSTS` enquanto durar o teste).
3. Apontar o registo A de `api.proenglish.cloud` para `2.31.122.170`.
4. No frontend (Vercel), confirmar que as variáveis de URL da API apontam para
   `https://api.proenglish.cloud/api/v1`.

## 4. Cópias de segurança

No Cloudflare R2 (conta `fc0cfcd5098d0414eee8b09f4602ea3d`): criar o bucket privado
`proenglish-copias` e um token de API com "Object Read & Write" só para esse bucket.
Pôr as chaves no `.env` (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`).

```sh
/opt/proenglish/app/apps/api/deploy/vps/copia-bd.sh      # testar à mão; tem de acabar em "ok"
crontab -e
# 55 3 * * * /opt/proenglish/app/apps/api/deploy/vps/copia-bd.sh >> /opt/proenglish/copias.log 2>&1 # proenglish
```

Ficam 7 dias no servidor e 30 dias no R2. Repor uma cópia:

```sh
docker exec -i proenglish-postgres-1 pg_restore -U proenglish -d proenglish \
  --clean --if-exists --no-owner < /opt/proenglish/copias/proenglish-AAAA-MM-DD-HHMM.dump
```

## 5. Deploys seguintes

Automáticos pelo workflow `api-deploy.yml` (push para `main` com alterações em `apps/api`).
Precisa dos secrets `VPS_HOST` e `VPS_SSH_KEY` no GitHub. À mão:

```sh
cd /opt/proenglish/app && git pull
cd apps/api/deploy/vps
docker compose build api
docker compose run --rm api python manage.py migrate --noinput
docker compose up -d api
```

## Cuidados

- **Nunca `docker compose down -v`**: o `-v` apaga o volume com a base de dados.
- Os limites de memória estão dimensionados para o servidor de 4 GB partilhado. Subir
  workers ou `shared_buffers` só depois de subir a máquina.
- Ficheiros enviados pelos utilizadores: com `USE_S3=True` vão para o S3; caso contrário
  ficam no volume `media`, que **não** entra na cópia diária.
