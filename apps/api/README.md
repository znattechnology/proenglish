# Trigger rebuild

# Trigger deploy Thu Mar  5 10:30:44 WAT 2026

## Testes

Correm com o test runner do Django e `core.test_settings` (a partir de `apps/api`):

```bash
# tudo (o mesmo que `npm run api:test` na raiz)
python manage.py test --settings=core.test_settings

# uma app, um módulo ou um teste
python manage.py test apps.users --settings=core.test_settings
python manage.py test apps.users.tests.test_fase3 --settings=core.test_settings
```

Use uma base local no `DATABASE_URL` (o test runner cria e apaga a `test_<nome>`).
O `pytest` (pytest-django, configurado em `pytest.ini`, usado pelo `Makefile`) corre o
mesmo conjunto: `pytest` ou `pytest apps/users`.

## Pagamentos Multicaixa Express (AOA) — `apps/pagamentos`

Pagamentos em kwanzas (inteiros) por Multicaixa Express. Enquanto não há acordo
com a EMIS usa-se um **provedor simulado**; o provedor real (`MulticaixaEMIS`,
ver `apps/pagamentos/provedores/emis.py`) substitui-o só por configuração.

Endpoints (`/api/v1/pagamentos/`, autenticados, só o dono vê/atua — 404 para outros):

| Método | Caminho | Descrição |
|---|---|---|
| POST | `multicaixa/` | `{tipo: subscricao\|curso, plan_id?, periodo?: mensal\|anual, course_id?, telefone, codigo_promocional?}` → 201 pagamento `pendente` |
| GET | `<id>/` | Estado atual (resolução lazy), `numero_recibo` e `ativacao` quando pago |
| POST | `<id>/cancelar/` | Só enquanto pendente |
| POST | `<id>/simular/` | `{resultado: aprovar\|recusar\|expirar}` — 404 se `PAGAMENTOS_SIMULADOS` for False |
| GET | `recibos/<numero>/` | Recibo `PE-R-<ano>-<NNNNNN>` |

Simulador (por número): termina em `0000` → recusado; `1111` → fica pendente e
expira aos 5 min; outro → pago 6 s após a criação. Pagamentos aparecem em
`/api/v1/subscriptions/payment-history/`. Preço de cursos: modelo `PrecoCurso` (admin).

Renovação (sem débito automático): correr diariamente
`python manage.py enviar_lembretes_renovacao` (expira subscrições pagas
terminadas → plano Gratuito; lembretes D-3 e D-0 via sinal
`apps.pagamentos.signals.lembrete_renovacao`). Lembretes ligam/desligam em
`PATCH /api/v1/subscriptions/my-subscription/lembretes/`.

Settings (variáveis de ambiente):

| Variável | Omissão | Notas |
|---|---|---|
| `PAGAMENTOS_PROVEDOR` | `simulado` | `simulado` ou `emis` (por implementar) |
| `PAGAMENTOS_SIMULADOS` | igual a `DEBUG` | Permite o simulador e `simular/`. **Nunca `True` em produção.** Com `False` e provedor `simulado`, a criação devolve 503. |
| `PAGAMENTOS_LIMITE_CRIACAO` | `10/min` | Throttle por utilizador em `multicaixa/` |
