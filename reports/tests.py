"""Tests de `reports.views.summary_report`.

El foco es la atribución de las cancelaciones (montos negativos de `SendMoney`):
los agregados por método de pago filtran `amount__gt=0`, así que el monto negativo
se resta a mano dentro del bucle y tiene que caer en el bucket del método con que
se pagó el envío original.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from clients.models import Broker, Client, Country, FidelityCard, SendMoney

from reports.views import summary_report


class SummaryReportCancelacionesTests(TestCase):
    """Fixtures mínimas: un cajero, un broker y un cliente al que colgarle envíos."""

    def setUp(self):
        self.day = date(2026, 6, 15)
        self.cashier = User.objects.create_user('cajera', password='x')

        # 'Viamericas' -> indx 'viamericas', la clave que usan las plantillas y el
        # broker del caso real que destapó el bug.
        self.broker = Broker.objects.create(broker_name='Viamericas')
        self.country = Country.objects.create(iso='SV', name='El Salvador')
        self.card = FidelityCard.objects.create(card_num=999001, author=self.cashier)
        self.client_obj = Client.objects.create(
            first_name='JUAN', last_name='PEREZ', country=self.country,
            date_of_birth=date(1990, 1, 1),
        )

    # ---------- helpers ----------

    def _at(self, day, hour=10):
        """Datetime consciente de zona horaria a la hora `hour` de `day`.

        La hora importa: la regla de las 23 horas del bucle mira la distancia
        entre el envío y su cancelación.
        """
        return timezone.make_aware(datetime.combine(day, time(hour=hour)))

    def _send_money(self, amount, broker_number, day=None, hour=10,
                    payment_method='cash'):
        return SendMoney.objects.create(
            client=self.client_obj, amount=Decimal(amount),
            creation_date=self._at(day or self.day, hour), country=self.country,
            broker=self.broker, fidelitycard=self.card, author=self.cashier,
            broker_number=broker_number, payment_method=payment_method,
        )

    def _filters(self, start=None, end=None, author=None):
        """Mismo recorte de días que arman las vistas de `reports`."""
        start = start or self.day
        end = end or start
        return {
            'author': author,
            'start_dt': timezone.make_aware(datetime.combine(start, datetime.min.time())),
            'end_dt': timezone.make_aware(datetime.combine(end, datetime.max.time())),
        }

    def _summary(self, **kwargs):
        return summary_report(self._filters(**kwargs))

    # ---------- tests ----------

    def test_cancelacion_con_tarjeta_no_toca_el_bucket_de_efectivo(self):
        """El bug: los -4,000 de una cancelación de tarjeta salían de efectivo."""
        self._send_money('1000.00', broker_number=10)
        self._send_money('4000.00', broker_number=20, hour=10, payment_method='card')
        self._send_money('-4000.00', broker_number=20, hour=15, payment_method='card')

        summary = self._summary()

        self.assertEqual(summary['send_moneys_cash']['viamericas']['sum'], Decimal('1000.00'))
        self.assertEqual(summary['send_moneys_card']['viamericas']['sum'], Decimal('0.00'))

        # La regla de las 23 horas se deja como estaba a propósito: descuenta del
        # conteo de efectivo aunque la cancelación sea de tarjeta. Se afirma para
        # que un cambio accidental salte aquí.
        self.assertEqual(summary['send_moneys_cash']['viamericas']['count'], 0)
        self.assertEqual(summary['send_moneys_card']['viamericas']['count'], 1)

    def test_una_cancelacion_en_efectivo_sigue_restando_de_efectivo(self):
        """El camino que ya funcionaba no cambia."""
        self._send_money('1000.00', broker_number=30, hour=10)
        self._send_money('-1000.00', broker_number=30, hour=15)
        self._send_money('500.00', broker_number=31, payment_method='card')

        summary = self._summary()

        self.assertEqual(summary['send_moneys_cash']['viamericas']['sum'], Decimal('0.00'))
        self.assertEqual(summary['send_moneys_card']['viamericas']['sum'], Decimal('500.00'))

    def test_cada_bucket_cuadra_con_la_suma_por_metodo_de_la_tabla(self):
        """El invariante: bucket == SUM(amount) GROUP BY payment_method."""
        self._send_money('1000.00', broker_number=40)
        self._send_money('4000.00', broker_number=41, hour=10, payment_method='card')
        self._send_money('-4000.00', broker_number=41, hour=15, payment_method='card')
        self._send_money('250.00', broker_number=42, payment_method='vialink')
        self._send_money('300.00', broker_number=43, hour=10, payment_method='vialink')
        self._send_money('-300.00', broker_number=43, hour=15, payment_method='vialink')

        filters = self._filters()
        summary = summary_report(filters)

        por_metodo = {
            row['payment_method']: row['total']
            for row in SendMoney.objects
            .filter(creation_date__range=(filters['start_dt'], filters['end_dt']))
            .values('payment_method').annotate(total=Sum('amount')).order_by()
        }

        for metodo, bucket in (('cash', 'send_moneys_cash'),
                               ('card', 'send_moneys_card'),
                               ('vialink', 'send_moneys_vialink')):
            with self.subTest(metodo=metodo):
                self.assertEqual(summary[bucket]['viamericas']['sum'], por_metodo[metodo])

    def test_cancelacion_con_tarjeta_sin_envios_de_tarjeta_en_el_rango(self):
        """El envío es de ayer y la cancelación de hoy: el bucket de tarjeta
        arranca en None porque hoy no hubo ningún envío positivo con tarjeta."""
        ayer = self.day - timedelta(days=1)
        self._send_money('500.00', broker_number=50, day=ayer, hour=10, payment_method='card')
        self._send_money('-500.00', broker_number=50, hour=10, payment_method='card')

        summary = self._summary()

        self.assertEqual(summary['send_moneys_card']['viamericas']['sum'], Decimal('-500.00'))
        # >= 23 horas entre el envío y la cancelación: cuenta como cancelación.
        self.assertEqual(summary['sm_canceled']['viamericas']['sum'], Decimal('-500.00'))
        self.assertEqual(summary['sm_canceled']['viamericas']['count'], 1)
        # Efectivo no se enteró: sigue sin ninguna fila en el rango.
        self.assertIsNone(summary['send_moneys_cash']['viamericas']['sum'])

    def test_una_cancelacion_con_tarjeta_no_descuadra_el_total(self):
        """`total` excluye tarjeta y ViaLink a propósito, así que una cancelación
        de tarjeta ya no le quita nada al total de efectivo."""
        self._send_money('1000.00', broker_number=60)
        self._send_money('4000.00', broker_number=61, hour=10, payment_method='card')
        self._send_money('-4000.00', broker_number=61, hour=15, payment_method='card')

        summary = self._summary()

        self.assertEqual(summary['total']['viamericas'], Decimal('1000.00'))

    def test_el_filtro_por_cajero_no_cambia_la_atribucion(self):
        """Con `author` puesto, el bucket de la cancelación sigue siendo el suyo."""
        self._send_money('4000.00', broker_number=70, hour=10, payment_method='card')
        self._send_money('-4000.00', broker_number=70, hour=15, payment_method='card')

        summary = self._summary(author=self.cashier)

        self.assertEqual(summary['send_moneys_card']['viamericas']['sum'], Decimal('0.00'))
        self.assertIsNone(summary['send_moneys_cash']['viamericas']['sum'])
