"""
Sinais da app pagamentos.

``pagamento_confirmado`` é enviado (após o commit da transação) sempre que um
pagamento passa a ``pago``. Argumentos: ``sender=Pagamento``, ``pagamento``.

HOOK: notificações ao aluno (ex.: "Pagamento confirmado - recibo PE-R-...")
devem ligar-se aqui, por exemplo::

    from apps.pagamentos.signals import pagamento_confirmado

    @receiver(pagamento_confirmado)
    def notificar(sender, pagamento, **kwargs):
        ...

A app pagamentos não depende de nenhum modelo de notificações de propósito.
"""

from django.dispatch import Signal

pagamento_confirmado = Signal()

# Enviado por ``manage.py enviar_lembretes_renovacao`` para cada subscrição
# paga que termina em breve. Argumentos: ``sender=UserSubscription``,
# ``subscription``, ``tipo`` ('D3' = faltam 3 dias, 'D0' = último dia),
# ``fim_periodo`` (datetime). HOOK para notificações/emails.
lembrete_renovacao = Signal()

# Enviado quando uma subscrição paga termina sem renovação e volta ao plano
# Gratuito. Argumentos: ``sender=UserSubscription``, ``subscription``,
# ``plano_anterior``.
subscricao_expirada = Signal()

# Período de teste grátis de um plano pago (apps/pagamentos/teste.py). Argumentos:
# ``sender=UserSubscription``, ``subscription`` (+ ``fim`` no aviso de fim próximo,
# ``plano_anterior`` quando termina sem pagamento).
teste_iniciado = Signal()
teste_a_terminar = Signal()
teste_terminado = Signal()
