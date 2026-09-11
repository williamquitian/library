"""Dos cuentas manuales nuevas: la venta diaria del Clover y los sobrantes.

No se enlazan a ningún broker, así que `BalanceAccount.is_manual` las clasifica
sola: se digitan en el balance diario y no se cuadran contra la empresa.
"""

from django.db import migrations

# (orden, nombre)
ACCOUNTS = [
    (90, 'Venta diaria / Clover'),
    (100, 'Sobrantes'),
]


def seed_accounts(apps, schema_editor):
    BalanceAccount = apps.get_model('balance', 'BalanceAccount')
    for order, name in ACCOUNTS:
        # Idempotente, igual que 0002: si la cuenta ya existe solo se refresca
        # el orden.
        BalanceAccount.objects.update_or_create(name=name, defaults={'order': order})


def unseed_accounts(apps, schema_editor):
    BalanceAccount = apps.get_model('balance', 'BalanceAccount')
    names = [name for _order, name in ACCOUNTS]
    # Solo se borran las cuentas que nunca se usaron, para no romper los FK
    # PROTECT de balances o movimientos ya registrados.
    (
        BalanceAccount.objects
        .filter(name__in=names, daily_balances__isnull=True, movements__isnull=True)
        .delete()
    )


class Migration(migrations.Migration):

    dependencies = [
        ('balance', '0005_dailybalance_store_rows'),
    ]

    operations = [
        migrations.RunPython(seed_accounts, unseed_accounts),
    ]
