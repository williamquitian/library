from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class BalanceAccountQuerySet(models.QuerySet):
    """Equivalente en SQL de la propiedad `BalanceAccount.is_manual`."""

    def active(self):
        return self.filter(is_active=True)

    def manual(self):
        return self.active().filter(broker__isnull=True, broker_moneyorder__isnull=True)

    def automatic(self):
        return self.active().exclude(broker__isnull=True, broker_moneyorder__isnull=True)


class BalanceAccount(models.Model):
    """Catálogo de cuentas del balance.

    Las cuentas se enlazan opcionalmente con los brokers que ya existen en la app
    `clients`, y de ahí sale el movimiento automático del día:

    - **automáticas** (Intermex, Viamericas, Ria, Money Gram): las mueve el CRM.
      El cajero las cuadra en su balance personal contra el balance final que
      reporta la empresa.
    - **manuales** (Boss Revolution, Loteria, Reserva, Fondo Cambio, Venta diaria
      / Clover, Sobrantes): sin enlace a ningún broker. Son cifras del negocio y
      no de un cajero, así que se digitan una sola vez al día en el balance
      diario y no se cuadran contra nada.
    """

    name = models.CharField(max_length=80, unique=True, verbose_name='Nombre')
    broker = models.ForeignKey(
        'clients.Broker',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='balance_accounts',
        verbose_name='Broker de envíos',
    )
    broker_moneyorder = models.ForeignKey(
        'clients.BrokerMoneyOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='balance_accounts',
        verbose_name='Broker de cheques / money orders',
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    objects = BalanceAccountQuerySet.as_manager()

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Cuenta de balance'
        verbose_name_plural = 'Cuentas de balance'

    def __str__(self):
        return self.name

    @property
    def is_manual(self):
        """True cuando la cuenta no tiene transacciones en el CRM."""
        return self.broker_id is None and self.broker_moneyorder_id is None


class DailyBalance(models.Model):
    """Cifras digitadas a mano. `user` distingue las dos formas de fila:

    - **de cajero** (`user` = el cajero): cuentas automáticas, se digitan en
      `/balance/personal`. Llevan balance inicial y balance final de la empresa.
    - **de tienda** (`user` = NULL): cuentas manuales, se digitan en
      `/balance/diario`. Una sola cifra del negocio por cuenta y día; la digita
      cualquier cajero y `author` guarda quién fue.

    `balance.services` solo lee las filas de tienda cuando no hay un cajero
    seleccionado: así la plata del negocio nunca se le atribuye a un cajero ni se
    cuenta dos veces.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='daily_balances',
        verbose_name='Usuario',
    )
    account = models.ForeignKey(
        BalanceAccount,
        on_delete=models.PROTECT,
        related_name='daily_balances',
        verbose_name='Cuenta',
    )
    date = models.DateField(default=timezone.localdate, db_index=True, verbose_name='Fecha')
    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Balance inicial',
    )
    # Cuentas manuales, sin transacciones en el CRM: el cajero digita al cierre
    # lo que se vendió o se movió. Admite negativos (p. ej. Reserva -550).
    manual_movement = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Movimiento del día',
    )
    company_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Balance final empresa',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='daily_balances_created',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'account', 'date'],
                name='unique_daily_balance',
            ),
            # `NULL != NULL`, así que la restricción de arriba no cubre las filas
            # de tienda: son justo las que no pueden duplicarse.
            models.UniqueConstraint(
                fields=['account', 'date'],
                condition=models.Q(user__isnull=True),
                name='unique_store_daily_balance',
            ),
        ]
        ordering = ['-date', 'account__order']
        verbose_name = 'Balance diario'
        verbose_name_plural = 'Balances diarios'

    def __str__(self):
        return f"{self.user or 'Tienda'} · {self.account} · {self.date}"


class BalanceMovement(models.Model):
    """Movimiento de efectivo de la caja: traslados entre cajeros, depósitos a
    caja fuerte, depósitos bancarios y gastos.

    Un traslado es doble partida en una sola fila: `from_user` entrega y
    `to_user` recibe el mismo monto. No se crean dos registros, así que las dos
    cajas no pueden descuadrarse entre sí. `amount` se guarda siempre positivo;
    el signo lo aplica `balance.services` según el usuario que se esté viendo.
    """

    TRANSFER = 'transfer'
    SAFEBOX = 'safebox'
    BANK = 'bank'
    EXPENSE = 'expense'
    CHECK_FEE = 'check_fee'

    MOVEMENT_TYPES = [
        (TRANSFER, 'Traslado entre usuarios'),
        (SAFEBOX, 'Depósito a caja fuerte'),
        (BANK, 'Depósito bancario'),
        (EXPENSE, 'Gasto / retiro de caja'),
        (CHECK_FEE, 'Cobro fee cheque devuelto'),
    ]

    # Tipos que SUMAN efectivo a la caja del usuario; el resto lo restan.
    INCOME_TYPES = {CHECK_FEE}

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
        verbose_name='Tipo de movimiento',
    )
    date = models.DateField(default=timezone.localdate, db_index=True, verbose_name='Fecha')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto',
    )
    from_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='movements_out',
        verbose_name='Entrega',
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements_in',
        verbose_name='Recibe',
    )
    account = models.ForeignKey(
        BalanceAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name='Cuenta',
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descripción',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='movements_created',
    )

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Movimiento de caja'
        verbose_name_plural = 'Movimientos de caja'

    def __str__(self):
        return f"{self.get_movement_type_display()} · {self.amount}"

    def clean(self):
        super().clean()
        if self.movement_type == self.TRANSFER:
            if self.to_user_id is None:
                raise ValidationError(
                    {'to_user': 'Un traslado necesita el usuario que recibe.'}
                )
            if self.to_user_id == self.from_user_id:
                raise ValidationError(
                    {'to_user': 'El usuario que recibe debe ser distinto al que entrega.'}
                )
        elif self.to_user_id is not None:
            raise ValidationError(
                {'to_user': 'Solo los traslados entre usuarios llevan un usuario que recibe.'}
            )
