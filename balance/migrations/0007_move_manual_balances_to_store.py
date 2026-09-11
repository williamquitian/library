"""Las cifras manuales ya digitadas pasan a ser de la tienda.

Dos cosas, y ninguna se puede deshacer:

1. Las filas de cajero de una cuenta manual se funden en una sola fila de tienda
   (`user=NULL`) con la suma de lo digitado. Sin esto la plata quedaría huérfana:
   `balance.services` ya no lee filas de cajero en cuentas manuales.
2. `company_balance` se borra en las cuentas manuales. Ya no se cuadran contra la
   empresa, así que el valor no se muestra en ninguna parte y dejarlo ahí solo
   confundiría a quien mire la tabla.
"""

from collections import defaultdict
from decimal import Decimal

from django.db import migrations

ZERO = Decimal('0.00')


def _manual_rows(DailyBalance):
    """Filas de cuentas sin broker enlazado, que es la definición de `is_manual`."""
    return DailyBalance.objects.filter(
        account__broker__isnull=True,
        account__broker_moneyorder__isnull=True,
    )


def move_to_store(apps, schema_editor):
    DailyBalance = apps.get_model('balance', 'DailyBalance')

    grouped = defaultdict(list)
    cashier_rows = _manual_rows(DailyBalance).exclude(user__isnull=True)
    for row in cashier_rows.order_by('updated_at'):
        grouped[(row.account_id, row.date)].append(row)

    for (account_id, day), rows in grouped.items():
        initial = sum((r.initial_balance for r in rows), ZERO)
        manual = sum((r.manual_movement for r in rows), ZERO)
        store = DailyBalance.objects.filter(
            account_id=account_id, date=day, user__isnull=True
        ).first()

        if store is None:
            # `author` de la fila más reciente: es quien digitó por última vez.
            DailyBalance.objects.create(
                user=None, account_id=account_id, date=day,
                initial_balance=initial, manual_movement=manual,
                company_balance=None, author=rows[-1].author,
            )
        else:
            store.initial_balance += initial
            store.manual_movement += manual
            store.company_balance = None
            store.save()

        DailyBalance.objects.filter(pk__in=[r.pk for r in rows]).delete()

    _manual_rows(DailyBalance).update(company_balance=None)


class Migration(migrations.Migration):

    dependencies = [
        ('balance', '0006_seed_manual_accounts'),
    ]

    operations = [
        migrations.RunPython(move_to_store, migrations.RunPython.noop),
    ]
