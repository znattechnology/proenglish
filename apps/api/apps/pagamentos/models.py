"""
Modelos de pagamento (Multicaixa Express, valores inteiros em kwanzas).
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .telefone import mascarar_telefone


# Pagamentos pendentes expiram ao fim de 5 minutos
DURACAO_PENDENTE = timedelta(minutes=5)


class Pagamento(models.Model):
    # O ProEnglish vende só subscrições: os cursos não se compram à parte,
    # o acesso a cada curso vem do plano (Course.user_has_access).
    TIPO_SUBSCRICAO = 'subscricao'
    TIPOS = [
        (TIPO_SUBSCRICAO, 'Subscrição'),
    ]

    PERIODO_MENSAL = 'mensal'
    PERIODO_ANUAL = 'anual'
    PERIODOS = [
        (PERIODO_MENSAL, 'Mensal'),
        (PERIODO_ANUAL, 'Anual'),
    ]
    # Mapeamento para o billing_cycle da app subscriptions
    CICLO_POR_PERIODO = {PERIODO_MENSAL: 'MONTHLY', PERIODO_ANUAL: 'YEARLY'}

    PENDENTE = 'pendente'
    PAGO = 'pago'
    RECUSADO = 'recusado'
    EXPIRADO = 'expirado'
    CANCELADO = 'cancelado'
    ESTADOS = [
        (PENDENTE, 'Pendente'),
        (PAGO, 'Pago'),
        (RECUSADO, 'Recusado'),
        (EXPIRADO, 'Expirado'),
        (CANCELADO, 'Cancelado'),
    ]

    METODO_MCX = 'multicaixa_express'
    # Preço final 0 Kz (crédito do plano atual e/ou código de 100%): ativado sem Multicaixa
    METODO_SEM_PAGAMENTO = 'sem_pagamento'
    METODOS = [(METODO_MCX, 'Multicaixa Express'), (METODO_SEM_PAGAMENTO, 'Sem pagamento')]
    PROVEDOR_INTERNO = 'interno'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pagamentos'
    )
    tipo = models.CharField(max_length=20, choices=TIPOS, default=TIPO_SUBSCRICAO)

    plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan', on_delete=models.PROTECT, related_name='pagamentos',
    )
    periodo = models.CharField(max_length=10, choices=PERIODOS)

    valor_kz = models.PositiveIntegerField(help_text='Preço base em kwanzas (inteiro)')
    desconto_kz = models.PositiveIntegerField(default=0, help_text='Desconto do código em kwanzas')
    codigo_promocional = models.CharField(max_length=50, null=True, blank=True)
    uso_promo = models.OneToOneField(
        'subscriptions.PromoCodeUsage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagamento', help_text='Reserva do código (libertada se o pagamento falhar)',
    )
    # Desconto de um código já usado que continua nesta renovação (duração "meses"/"sempre"):
    # não reserva nova utilização.
    promo_renovacao = models.BooleanField(default=False)

    # Mudança de plano: os dias pagos do plano atual viram crédito
    credito_kz = models.PositiveIntegerField(
        default=0, help_text='Crédito do plano anterior usado (abatido + convertido em dias)')
    credito_abatido_kz = models.PositiveIntegerField(
        default=0, help_text='Parte do crédito abatida ao preço')
    credito_dias_restantes = models.PositiveIntegerField(
        default=0, help_text='Dias que faltavam no plano anterior quando o crédito foi calculado')
    credito_plano = models.ForeignKey(
        'subscriptions.SubscriptionPlan', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', help_text='Plano de onde veio o crédito',
    )
    dias_extra = models.PositiveIntegerField(
        default=0, help_text='Dias acrescentados ao período com a sobra do crédito')
    # Preenchido quando os dias que faltavam deste período foram convertidos em
    # crédito de outro plano (ou o plano foi mudado): deixa de dar crédito.
    creditado_em = models.DateTimeField(null=True, blank=True)

    metodo = models.CharField(max_length=30, choices=METODOS, default=METODO_MCX)
    telefone = models.CharField(max_length=9, help_text='Normalizado: 9 dígitos, começa por 9')
    provedor = models.CharField(max_length=30, help_text='Código do provedor (ex.: simulado, emis)')
    referencia_externa = models.CharField(max_length=100, blank=True, default='')

    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDENTE)
    motivo_falha = models.CharField(max_length=255, blank=True, default='')
    expira_em = models.DateTimeField()
    pago_em = models.DateTimeField(null=True, blank=True)
    # Período de serviço pago (subscrições), preenchido na confirmação
    periodo_inicio = models.DateTimeField(null=True, blank=True)
    periodo_fim = models.DateTimeField(null=True, blank=True)
    numero_recibo = models.CharField(max_length=20, unique=True, null=True, blank=True)

    # O que foi ativado (preenchido na confirmação; garante idempotência)
    historico = models.OneToOneField(
        'subscriptions.SubscriptionHistory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pagamento',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'estado'], name='pagamento_user_estado_idx'),
            models.Index(fields=['estado', 'expira_em'], name='pagamento_estado_expira_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                name='pagamento_desconto_ate_valor',
                check=Q(desconto_kz__lte=models.F('valor_kz')),
            ),
            models.CheckConstraint(
                name='pagamento_total_nao_negativo',
                check=Q(valor_kz__gte=models.F('desconto_kz') + models.F('credito_abatido_kz')),
            ),
            # Um único pagamento pendente por utilizador (qualquer plano)
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(estado='pendente'),
                name='pagamento_um_pendente_por_utilizador',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} {self.total_kz} Kz - {self.estado} ({self.user_id})'

    def save(self, *args, **kwargs):
        if not self.expira_em:
            self.expira_em = timezone.now() + DURACAO_PENDENTE
        super().save(*args, **kwargs)

    @property
    def total_kz(self):
        return self.valor_kz - self.desconto_kz - self.credito_abatido_kz

    @property
    def valor_do_periodo_kz(self):
        """O que este período valeu ao aluno: pago + crédito trazido do plano anterior."""
        return self.total_kz + self.credito_kz

    @property
    def telefone_mascarado(self):
        return mascarar_telefone(self.telefone)

    @property
    def billing_cycle(self):
        return self.CICLO_POR_PERIODO.get(self.periodo)

    @property
    def descricao(self):
        return f'Plano {self.plan.name} - {self.get_periodo_display()}'


class SequenciaRecibo(models.Model):
    """Contador de recibos por ano (PE-R-<ano>-<NNNNNN>)."""

    ano = models.PositiveIntegerField(primary_key=True)
    ultimo = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.ano}: {self.ultimo}'


class LembreteRenovacao(models.Model):
    """Registo de lembrete de renovação enviado (evita repetições)."""

    D3 = 'D3'
    D0 = 'D0'
    # Período de teste: 2 dias antes do fim do teste
    T2 = 'T2'
    TIPOS = [
        (D3, '3 dias antes do fim'),
        (D0, 'Último dia'),
        (T2, 'Teste: 2 dias antes do fim'),
    ]

    subscription = models.ForeignKey(
        'subscriptions.UserSubscription', on_delete=models.CASCADE,
        related_name='lembretes_renovacao_enviados',
    )
    tipo = models.CharField(max_length=2, choices=TIPOS)
    fim_periodo = models.DateTimeField(help_text='expires_at da subscrição no momento do envio')
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enviado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'tipo', 'fim_periodo'],
                name='lembrete_renovacao_unico_por_periodo',
            ),
        ]

    def __str__(self):
        return f'{self.subscription_id} {self.tipo} {self.fim_periodo:%Y-%m-%d}'


# ---------------------------------------------------------------------------
# Ganhos dos professores (ver apps/pagamentos/ganhos.py)
# ---------------------------------------------------------------------------

class GanhoMensal(models.Model):
    """Parte de um professor na percentagem da receita de subscrições de um mês."""

    A_PROCESSAR = 'a_processar'
    PAGO = 'pago'
    ESTADOS = [(A_PROCESSAR, 'A processar'), (PAGO, 'Pago')]

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ganhos_mensais')
    mes = models.DateField(help_text='Primeiro dia do mês (hora de Luanda)')
    alunos_pagantes = models.PositiveIntegerField(default=0)
    segundos = models.PositiveIntegerField(default=0)
    quota = models.DecimalField(max_digits=7, decimal_places=6, default=0,
                                help_text='Parte do bolo (0 a 1)')
    valor_kz = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=A_PROCESSAR)
    pago_em = models.DateField(null=True, blank=True)
    referencia = models.CharField(max_length=100, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-mes', '-valor_kz']
        constraints = [
            models.UniqueConstraint(fields=['professor', 'mes'], name='ganho_unico_por_professor_mes'),
        ]

    def __str__(self):
        return f'{self.professor_id} {self.mes:%Y-%m}: {self.valor_kz} Kz ({self.estado})'


class ContaRecebimento(models.Model):
    """Conta bancária (IBAN angolano) onde o professor recebe os ganhos."""

    professor = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conta_recebimento')
    banco = models.CharField(max_length=20)
    iban = models.CharField(max_length=25, help_text='Normalizado, sem espaços (AO06 + 21 dígitos)')
    titular = models.CharField(max_length=120)
    confirmada_em = models.DateTimeField()

    def __str__(self):
        return f'{self.professor_id} {self.banco} •••• {self.iban[-4:]}'


class AlteracaoContaRecebimento(models.Model):
    """Alteração da conta à espera do código enviado por email."""

    professor = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alteracao_conta_recebimento')
    banco = models.CharField(max_length=20)
    iban = models.CharField(max_length=25)
    titular = models.CharField(max_length=120)
    verificacao = models.ForeignKey(
        'users.EmailVerification', on_delete=models.CASCADE, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.professor_id} -> {self.banco} •••• {self.iban[-4:]}'


class RegistoContaRecebimento(models.Model):
    """
    Registo (auditoria) do que se fez com a conta de recebimento de um professor: pedidos de
    alteração, confirmações, cancelamentos e consultas do IBAN completo pela administração.
    Nunca guarda o IBAN completo: só o banco e os últimos 4 dígitos.
    """

    PEDIDO = 'pedido'
    CONFIRMADA = 'confirmada'
    CANCELADA = 'cancelada'
    IBAN_CONSULTADO = 'iban_consultado'
    PAGO = 'pago'
    ACCOES = [
        (PEDIDO, 'Alteração pedida (código enviado)'),
        (CONFIRMADA, 'Alteração confirmada'),
        (CANCELADA, 'Alteração cancelada'),
        (IBAN_CONSULTADO, 'IBAN completo consultado'),
        (PAGO, 'Ganho marcado como pago'),
    ]

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='registos_conta_recebimento')
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Quem fez a acção (o professor ou o administrador)')
    accao = models.CharField(max_length=20, choices=ACCOES)
    banco = models.CharField(max_length=20, blank=True, default='')
    terminada_em = models.CharField(max_length=4, blank=True, default='')
    ganho = models.ForeignKey(GanhoMensal, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    ip = models.CharField(max_length=45, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        indexes = [models.Index(fields=['professor', '-criado_em'])]

    def __str__(self):
        return f'{self.professor_id} {self.accao} {self.banco} •••• {self.terminada_em} ({self.criado_em:%Y-%m-%d})'
