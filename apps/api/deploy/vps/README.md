# ProEnglish API no servidor mambo-labtic

Servidor `2.31.122.170` (utilizador `deploy`), partilhado com o LabTIC e O Mambo.
A API e a sua base de dados PostgreSQL correm em Docker, em `/opt/proenglish`.
O Caddy de `/opt/proxy` trata do HTTPS e encaminha o endereço da API (por agora `proenglish-api.2.31.122.170.sslip.io`; o domínio novo junta-se depois).

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
| `api`      | `ghcr.io/znattechnology/proenglish-api` | 512 MB  | interna + publica  |

Não há nginx, certbot nem Redis: o Caddy faz o HTTPS, o WhiteNoise serve os ficheiros
estáticos e a aplicação não usa Redis em produção.

## 1. Instalação inicial (uma vez)

```sh
ssh deploy@2.31.122.170
mkdir -p /opt/proenglish && cd /opt/proenglish
git clone <URL do repositório> app      # repositório privado: usar um token só de leitura
cd app/apps/api/deploy/vps
cp .env.example .env && chmod 600 .env
nano .env        # obrigatórias marcadas com * (o deploy.sh recusa avançar sem elas)
docker compose up -d postgres
mkdir -p /opt/proenglish/logs
```

A imagem da API não se compila aqui: vem do GitHub Container Registry no primeiro deploy
automático (secção 5). Para arrancar antes disso, à mão:
`echo <token com read:packages> | docker login ghcr.io -u <utilizador> --password-stdin`
e `./deploy.sh ghcr.io/znattechnology/proenglish-api:latest`.

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
./deploy.sh ghcr.io/znattechnology/proenglish-api:latest   # migrações, API, tarefas agendadas
```

Guardar `neon.dump` fora do servidor e apagá-lo de lá. Manter o projecto no Neon uma ou
duas semanas sem uso, como recurso, e só depois apagá-lo.

## 3. Caddy e DNS

O Caddy é o que já existe em `/opt/proxy`, partilhado: o deploy automático nunca lhe toca.
O bloco do ProEnglish acrescenta-se uma vez. Além de encaminhar, grava o `X-Real-IP` (o IP
real do aluno, para os limites de pedidos) e acrescenta HSTS; a API precisa de
`TRUSTED_PROXY=True` no `.env` para o ler e para reconhecer o HTTPS.

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
```

A linha do cron é instalada pelo `deploy.sh` (ver secção 6).

Ficam 7 dias no servidor e 30 dias no R2. Repor uma cópia:

```sh
docker exec -i proenglish-postgres-1 pg_restore -U proenglish -d proenglish \
  --clean --if-exists --no-owner < /opt/proenglish/copias/proenglish-AAAA-MM-DD-HHMM.dump
```

## 5. Deploy automático (GitHub Actions)

Cada push para `main` com alterações em `apps/api` corre `.github/workflows/api-deploy.yml`:

1. **Testes** (`api-tests.yml`): se falharem, nada é publicado.
2. **Imagem**: construída no GitHub e publicada em
   `ghcr.io/znattechnology/proenglish-api:<commit>` (e `:latest`). O servidor não compila.
3. **Deploy**: por SSH, actualiza o código em `/opt/proenglish/app` (só para o
   `docker-compose.yml` e os scripts) e corre `deploy.sh <imagem>`:
   - confirma o `.env` (obrigatórias, `TRUSTED_PROXY`, segredo do Vapi; avisa se
     `PAGAMENTOS_SIMULADOS=True`);
   - descarrega a imagem, aplica as migrações com ela (a API antiga continua a servir);
   - troca a API e espera até 3 minutos que fique saudável (`/api/health/`);
   - **se não ficar, volta à imagem anterior** e o workflow falha (as migrações não são
     desfeitas: têm de ser sempre compatíveis com a versão anterior);
   - instala as tarefas agendadas e apaga imagens antigas (ficam a nova e a anterior).
4. **Verificação de fora**: `<API_URL>/api/health/` pelo Caddy (variável `API_URL` do repositório; por omissão o endereço sslip.io).

Também se corre à mão em Actions > API Deploy > Run workflow.

**Configurar uma vez no GitHub** (Settings do repositório):

- *Secrets and variables > Actions*: `VPS_HOST` (`2.31.122.170`) e `VPS_SSH_KEY`. A chave
  cria-se só para isto e a pública vai para `~deploy/.ssh/authorized_keys` no servidor:
  ```sh
  ssh-keygen -t ed25519 -f proenglish-deploy -C "github-actions proenglish" -N ""
  ssh-copy-id -i proenglish-deploy.pub deploy@2.31.122.170
  # conteúdo de proenglish-deploy (a privada) -> secret VPS_SSH_KEY; depois apagar o ficheiro
  ```
- *Environments*: criar `producao`. Opcional: "Required reviewers" para aprovar cada
  deploy antes de correr.

A imagem fica privada no GitHub (o pacote herda a visibilidade do repositório); o servidor
entra no registo só durante o deploy, com o token temporário do workflow.

**Voltar a uma versão anterior**: Actions > API Deploy > Run workflow num commit antigo, ou
no servidor `./deploy.sh ghcr.io/znattechnology/proenglish-api:<commit>` (a imagem anterior
está sempre guardada no servidor).

## 6. Tarefas agendadas

Estão em `crontab.txt` e o `deploy.sh` instala-as no crontab do utilizador `deploy`, entre
`# >>> proenglish` e `# <<< proenglish`, sem tocar nas dos outros projectos. Para mudar uma
hora, editar `crontab.txt` e fazer deploy. Cada tarefa corre dentro da API em execução
(`tarefa.sh`) e regista em `/opt/proenglish/logs/cron.log`.

| Quando (UTC) | Comando | O que faz |
|---|---|---|
| de 5 em 5 min | `verificar_conversas_vapi` | cobra e avalia as conversas por voz; retoma avaliações paradas |
| de 15 em 15 min | `enviar_lembretes_meta` | lembrete da meta diária |
| de hora a hora | `terminar_testes` | avisos e fim dos testes grátis |
| de hora a hora | `enviar_lembretes_renovacao` | renovações e subscrições terminadas |
| de hora a hora | `fechar_competicoes` | início e fecho das competições |
| de hora a hora | `transcrever_aulas` | transcrições que ficaram por fazer |
| dia 1, 02:00 | `fechar_ganhos` | ganhos mensais dos professores |
| 03:30 | `apagar_gravacoes_exames` | gravações dos exames com mais de 12 meses |
| 03:55 | `copia-bd.sh` | cópia da base (servidor e R2) |

## Cuidados

- **Nunca `docker compose down -v`**: o `-v` apaga o volume com a base de dados.
- Nunca `docker image prune -a` nem `docker system prune`: o servidor é partilhado.
- Os limites de memória estão dimensionados para o servidor de 4 GB partilhado. Subir
  workers ou `shared_buffers` só depois de subir a máquina.
- Ficheiros enviados pelos utilizadores: com `USE_S3=True` vão para o S3; caso contrário
  ficam no volume `media`, que **não** entra na cópia diária.
