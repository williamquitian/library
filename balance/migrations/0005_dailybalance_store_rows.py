"""Las cuentas manuales pasan a ser filas de tienda: `user` puede ser NULL.

La restricción parcial es la que de verdad importa: `unique_daily_balance`
no sirve para las filas de tienda porque en SQL `NULL != NULL`.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('balance', '0004_alter_balancemovement_movement_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailybalance',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='daily_balances', to=settings.AUTH_USER_MODEL, verbose_name='Usuario'),
        ),
        migrations.AddConstraint(
            model_name='dailybalance',
            constraint=models.UniqueConstraint(condition=models.Q(('user__isnull', True)), fields=('account', 'date'), name='unique_store_daily_balance'),
        ),
    ]
