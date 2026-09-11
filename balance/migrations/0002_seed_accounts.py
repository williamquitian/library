from django.db import migrations

# (orden, nombre, nombre del Broker de envíos, nombre del BrokerMoneyOrder)
# Boss Revolution, Loteria, Reserva y Fondo Cambio no tienen transacciones en el
# CRM: existen solo para cuadrar la caja (inicial y final digitados).
ACCOUNTS = [
    (10, 'Intermex', 'Intermex', 'Intermex'),
    (20, 'Viamericas', 'Viamericas', 'Viamericas'),
    (30, 'Ria', 'Ria', None),
    (40, 'Money Gram', 'Money Gram', None),
    (50, 'Boss Revolution', None, None),
    (60, 'Loteria', None, None),
    (70, 'Reserva', None, None),
    (80, 'Fondo Cambio', None, None),
]


def seed_accounts(apps, schema_editor):
    BalanceAccount = apps.get_model('balance', 'BalanceAccount')
    Broker = apps.get_model('clients', 'Broker')
    BrokerMoneyOrder = apps.get_model('clients', 'BrokerMoneyOrder')

    for order, name, broker_name, bmo_name in ACCOUNTS:
        broker = Broker.objects.filter(broker_name=broker_name).first() if broker_name else None
        bmo = (
            BrokerMoneyOrder.objects.filter(broker_moneyorder_name=bmo_name).first()
            if bmo_name else None
        )
        # Idempotente: si la cuenta ya existe solo se refrescan los enlaces.
        BalanceAccount.objects.update_or_create(
            name=name,
            defaults={'order': order, 'broker': broker, 'broker_moneyorder': bmo},
        )


def unseed_accounts(apps, schema_editor):
    BalanceAccount = apps.get_model('balance', 'BalanceAccount')
    names = [name for _order, name, _b, _bmo in ACCOUNTS]
    # Solo se borran las cuentas que nunca se usaron, para no romper FKs
    # PROTECT de balances o movimientos ya registrados.
    (
        BalanceAccount.objects
        .filter(name__in=names, daily_balances__isnull=True, movements__isnull=True)
        .delete()
    )


class Migration(migrations.Migration):

    dependencies = [
        ('balance', '0001_initial'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_accounts, unseed_accounts),
    ]
