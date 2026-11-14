"""
Provedor Multicaixa Express real via EMIS - POR IMPLEMENTAR.

Aguarda o acordo comercial com a EMIS. Quando existir, implementar esta
classe e definir ``PAGAMENTOS_PROVEDOR=emis`` (e ``PAGAMENTOS_SIMULADOS=False``).
Nada mais no sistema precisa de mudar.

O que a integração real precisa:

1. Credenciais de comerciante (fornecidas pela EMIS / banco adquirente):
   identificador do comerciante/terminal (merchant id / POS id), chave ou
   token de API e, se aplicável, certificado cliente (mTLS). Guardar em
   variáveis de ambiente (ex.: ``EMIS_MERCHANT_ID``, ``EMIS_API_KEY``,
   ``EMIS_API_URL``), nunca no código.

2. ``iniciar(pagamento)``: pedido de pagamento "push" para
   ``pagamento.telefone`` (formato 2449XXXXXXXX) com
   ``pagamento.total_kz`` em AOA e uma referência nossa (``pagamento.id``).
   Guardar o identificador devolvido em ``referencia_externa``.
   Respeitar timeouts/idempotência do lado da EMIS (reenviar com a mesma
   referência não pode gerar duas cobranças).

3. URL de callback (webhook) público, ex.:
   ``POST /api/v1/pagamentos/webhooks/emis/`` (ainda não existe), que:
   * verifica a assinatura/HMAC do pedido com o segredo partilhado da EMIS
     (rejeitar se inválida; comparar em tempo constante) e, se possível,
     a origem/IP;
   * localiza o Pagamento por ``referencia_externa``/referência nossa;
   * valida montante e moeda contra ``pagamento.total_kz``;
   * chama ``services.confirmar_pagamento`` ou ``services.marcar_falha``
     (ambos idempotentes e com lock por linha).

4. ``consultar(pagamento)``: consulta de estado na API da EMIS, usada pela
   leitura lazy (GET pagamentos/<id>/) como fallback se o callback falhar.
   Mapear os códigos da EMIS para pendente/pago/recusado/expirado.

5. ``cancelar(pagamento)``: se a EMIS suportar anular um push pendente.

6. Reconciliação: um job periódico que consulta pendentes antigos e compara
   com os extratos da EMIS.
"""

from .base import ProvedorPagamento


class MulticaixaEMIS(ProvedorPagamento):
    codigo = 'emis'
    simulado = False

    def iniciar(self, pagamento):
        raise NotImplementedError(
            'Integração Multicaixa Express (EMIS) ainda não implementada. '
            'Ver apps/pagamentos/provedores/emis.py.'
        )

    def consultar(self, pagamento):
        raise NotImplementedError(
            'Integração Multicaixa Express (EMIS) ainda não implementada. '
            'Ver apps/pagamentos/provedores/emis.py.'
        )
