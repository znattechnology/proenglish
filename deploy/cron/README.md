# Cron da API ProEnglish

`proenglish.cron` lista as tarefas periódicas que a API precisa. Não há outro
agendador no projeto (nem CronJob no k8s, nem serviço no docker-compose, e o
crontab criado por `apps/api/terraform/digitalocean/user_data.sh` só tem backup
e monitorização), por isso sem isto não há lembretes de renovação, os planos
pagos terminados não voltam ao Gratuito e os lembretes da meta não saem.

| Comando | Quando | O que faz |
| --- | --- | --- |
| `terminar_testes` | de hora a hora | Testes grátis dos planos pagos: aviso (app + email) 2 dias antes do fim, uma vez por teste; os testes que terminaram sem pagamento voltam ao Gratuito (o progresso fica) e o aluno é avisado. |
| `enviar_lembretes_renovacao` | de hora a hora | Lembrete D-3 (faltam <= 72 h) e D-0 (faltam <= 24 h), uma vez por período, **antes** de expirar; depois volta ao Gratuito os planos pagos terminados (o progresso fica); resolve pagamentos pendentes fora de prazo (liberta códigos promocionais reservados). |
| `enviar_lembretes_meta` | a cada 15 min | Lembrete da meta diária de estudo, à hora escolhida por cada aluno. |
| `fechar_competicoes` | de hora a hora | Avisa os participantes quando uma competição começa; quando termina, grava a classificação final, atribui os prémios (certificado de mérito / medalha) e avisa os vencedores. |

Ambos são idempotentes: correr duas vezes seguidas não duplica avisos.

## Depois de cada deploy (não é cron)

Quando o deploy muda as regras da nota dos cursos (`GradeCalculatorService.CALCULATION_VERSION`
sobe), as notas guardadas ficam com a versão antiga. A emissão de certificados já não confia nelas
(recalcula sempre antes de emitir) e as páginas das notas recalculam as antigas quando o aluno as
abre, mas o painel do professor e as listas lêem a nota guardada. Depois de `migrate`, correr uma
vez (idempotente; só toca nas notas de versão antiga):

```bash
cd /opt/proenglish/apps/api
./venv/bin/python manage.py recalcular_notas_cursos --so-antigas
```

Não está numa migração porque recalcula cada aluno em cada curso (pode demorar com muitos alunos).

## Instalar no VPS

1. Entrar no VPS com o utilizador que corre a API (não root, se possível).
2. Copiar o ficheiro e substituir os marcadores:

   ```bash
   cp deploy/cron/proenglish.cron /tmp/proenglish.cron
   sed -i \
     -e 's#__PROJECT_DIR__#/opt/proenglish/apps/api#g' \
     -e 's#__VENV__#/opt/proenglish/apps/api/venv#g' \
     -e 's#__LOG_DIR__#/opt/proenglish/logs#g' \
     /tmp/proenglish.cron
   mkdir -p /opt/proenglish/logs
   ```

   Se a API correr em Docker (como em `user_data.sh`), troque
   `cd __PROJECT_DIR__ && ... __VENV__/bin/python manage.py` por
   `docker compose -f /opt/proenglish/docker-compose.yml exec -T <serviço-da-api> python manage.py`.

3. Testar os comandos à mão uma vez (sem alterar nada):

   ```bash
   cd /opt/proenglish/apps/api
   ./venv/bin/python manage.py enviar_lembretes_renovacao --dry-run
   ./venv/bin/python manage.py enviar_lembretes_meta --dry-run
   ```

4. Juntar ao crontab existente **sem apagar** as linhas que lá estão (backup, monitor):

   ```bash
   crontab -l > /tmp/crontab.atual 2>/dev/null || true
   cat /tmp/crontab.atual /tmp/proenglish.cron | crontab -
   crontab -l   # confirmar
   ```

   Alternativa (root): copiar para `/etc/cron.d/proenglish`, acrescentando o nome
   do utilizador como 6.º campo em cada linha (`5 * * * * proenglish cd ...`).

5. Confirmar ao fim de uma hora: `tail /opt/proenglish/logs/cron-renovacao.log`.

## Fuso horário

O relógio do VPS está provavelmente em UTC (`timedatectl` mostra). Não é preciso
mudá-lo: o Django usa `TIME_ZONE='UTC'` e os comandos fazem as contas do dia em
`Africa/Luanda` (UTC+1, sem hora de verão). As horas do crontab são as do
relógio do VPS; como os comandos correm de hora a hora / a cada 15 minutos, a
diferença de 1 hora não tem efeito.
