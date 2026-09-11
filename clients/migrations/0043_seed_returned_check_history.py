from decimal import Decimal

from django.db import migrations


def seed_history(apps, schema_editor):
    """Da estado e historial a los expedientes que ya existían.

    Antes de este cambio el único desenlace era `date_payoff` (el cliente pagó
    en efectivo), así que se reconstruye a partir de eso.
    """
    ReturnedCheck = apps.get_model('clients', 'ReturnedCheck')
    ReturnedCheckEvent = apps.get_model('clients', 'ReturnedCheckEvent')

    for rc in ReturnedCheck.objects.all():
        rc.status = 'recuperado' if rc.date_payoff else 'pendiente'
        rc.save(update_fields=['status'])

        # Idempotente: no duplicar si la migración se corre de nuevo.
        if not ReturnedCheckEvent.objects.filter(returned_check=rc).exists():
            ReturnedCheckEvent.objects.create(
                returned_check=rc,
                event_type='returned',
                date=rc.date_returned,
                fee=Decimal('0.00'),
                comment='Devolución registrada antes del historial de eventos.',
                author_id=rc.author_id,
            )
            if rc.date_payoff:
                ReturnedCheckEvent.objects.create(
                    returned_check=rc,
                    event_type='paid_cash',
                    date=rc.date_payoff,
                    fee=rc.fees or Decimal('0.00'),
                    comment='Recuperación registrada antes del historial de eventos.',
                    author_id=rc.author_id,
                )


def unseed_history(apps, schema_editor):
    ReturnedCheckEvent = apps.get_model('clients', 'ReturnedCheckEvent')
    ReturnedCheckEvent.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0042_returnedcheck_status_returnedcheckevent'),
    ]

    operations = [
        migrations.RunPython(seed_history, unseed_history),
    ]
