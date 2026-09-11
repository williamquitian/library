from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def merge_comments(apps, schema_editor):
    """Pasa los comentarios del modelo viejo al historial de eventos.

    `ReturnedCheckComment` quedó de solo lectura cuando se agregó
    `ReturnedCheckEvent` (migración 0042): hoy un comentario suelto ya se graba
    como evento de tipo `comment`. Las filas viejas tienen contenido real del
    negocio (llamadas al cliente, motivos de devolución), así que se convierten
    antes de borrar la tabla.
    """
    ReturnedCheckComment = apps.get_model('clients', 'ReturnedCheckComment')
    ReturnedCheckEvent = apps.get_model('clients', 'ReturnedCheckEvent')

    for comment in ReturnedCheckComment.objects.all().iterator():
        event = ReturnedCheckEvent.objects.create(
            returned_check_id=comment.returned_check_id,
            event_type='comment',
            # La fecha del evento es un DateField: se toma en la zona local,
            # porque el `created_at` está en UTC y de noche cae al día siguiente.
            date=timezone.localtime(comment.created_at).date(),
            fee=Decimal('0.00'),
            comment=comment.comment,
            author_id=comment.author_id,
        )
        # `created_at` es auto_now_add: ni `create()` ni `bulk_create()` respetan
        # el valor que se les pase, así que la fecha original se escribe aparte.
        ReturnedCheckEvent.objects.filter(pk=event.pk).update(
            created_at=comment.created_at)


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0046_alter_returnedcheck_file_path'),
    ]

    operations = [
        # El copiado va antes del borrado: al revertir, Django deshace en orden
        # inverso, así que la tabla vuelve a existir (vacía) y los comentarios
        # se quedan en los eventos. No se pierde nada en ninguna dirección.
        migrations.RunPython(merge_comments, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='ReturnedCheckComment',
        ),
    ]
