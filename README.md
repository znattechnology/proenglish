# ProEnglish

Monorepo da plataforma ProEnglish.

```
.
├── apps/
│   ├── web/   # Frontend — Next.js 14 (antigo repositório Pro-Ingles-client)
│   └── api/   # Backend — Django (antigo repositório Pro-Ingles-server / Tuwi-Backend)
├── .github/workflows/   # CI/CD de todas as apps (filtrado por caminho)
└── package.json         # scripts de conveniência na raiz
```

O histórico de commits dos dois repositórios originais foi preservado
(`git log -- apps/web` / `git log -- apps/api`).

## Desenvolvimento

### Web (`apps/web`)

```bash
npm run web:install
npm run web:dev          # http://localhost:3000
```

Variáveis de ambiente: `apps/web/.env.local`.

### API (`apps/api`)

```bash
cd apps/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver   # http://localhost:8000
```

Ou, a partir da raiz (com o virtualenv ativo): `npm run api:dev`.
Variáveis de ambiente: `apps/api/.env` (ver `apps/api/.env.example`).

## CI/CD

Os workflows estão em `.github/workflows/` e só correm quando a app respetiva muda:

| Workflow          | Dispara em                         | Faz                                   |
|-------------------|------------------------------------|---------------------------------------|
| `web-ci.yml`      | push/PR `main`/`develop`, `apps/web/**` | lint, testes e build do Next.js  |
| `web-deploy.yml`  | push `main`, `apps/web/**`         | deploy para a Vercel                  |
| `api-tests.yml`   | PR `main`/`develop`, `apps/api/**` | testes Django, qualidade, migrações   |
| `api-deploy.yml`  | push `main`, `apps/api/**`         | deploy na VPS Hostinger (Docker)      |

Secrets necessários no repositório GitHub: `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
`VERCEL_PROJECT_ID`, `VPS_PASSWORD`.

### Notas de deploy

- **Vercel**: no projeto da Vercel, definir *Root Directory* = `apps/web`
  (se usar a integração Git) ou manter o deploy via CLI do workflow, que já corre em `apps/web`.
- **VPS**: o checkout do monorepo fica em `/opt/proenglish`; o backend corre em
  `/opt/proenglish/apps/api`. No primeiro deploy o `.env` é copiado de `/opt/tuwi-backend/.env`.
  O nome do projeto Docker Compose mantém-se `tuwi-backend`, para reutilizar os volumes existentes.
