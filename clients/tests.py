"""Pruebas del ciclo de devolución de cheques.

El módulo mueve dinero real: cubre los rebotes repetidos (antes imposibles) y
las regresiones de los errores encontrados en el análisis.
"""

import atexit
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.timezone import make_aware

from balance.models import BalanceAccount, BalanceMovement
from companies.models import Company

from clients.models import (
    BrokerMoneyOrder, Check, Client, Country, ReturnedCheck,
    ReturnedCheckEvent,
)

ZERO = Decimal('0.00')

# `STORAGES['default']` es S3: sin esto, cualquier test que grabe un FileField
# sube el archivo al bucket real. Los adjuntos de prueba van a un temporal.
_TEST_MEDIA = tempfile.mkdtemp(prefix='unimex-test-media-')
atexit.register(shutil.rmtree, _TEST_MEDIA, ignore_errors=True)

temp_media = override_settings(STORAGES={
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _TEST_MEDIA},
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
})


@temp_media
class ReturnedCheckCycleTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('cajera', password='secreta')
        self.bmo = BrokerMoneyOrder.objects.create(broker_moneyorder_name='Intermex')
        self.country = Country.objects.create(iso='SV', name='El Salvador')
        self.company = Company.objects.create(name='ACME TEST')
        self.client_obj = Client.objects.create(
            first_name='JUAN', last_name='PEREZ', country=self.country,
            date_of_birth=date(1990, 1, 1),
        )
        self.account = BalanceAccount.objects.create(
            name='Intermex Test', broker_moneyorder=self.bmo, order=1)

    def _check(self, amount, number=1001, client=None):
        return Check.objects.create(
            client=client or self.client_obj, amount=Decimal(amount), commission=ZERO,
            check_number=number, company=self.company, broker=self.bmo,
            author=self.user, comm_percent=Decimal('1.5'),
        )

    def _client(self, first_name):
        return Client.objects.create(
            first_name=first_name, last_name='PEREZ', country=self.country,
            date_of_birth=date(1990, 1, 1),
        )

    def _return(self, check, day=date(2026, 6, 1)):
        rc = ReturnedCheck.objects.create(
            original_check=check, date_returned=day,
            status=ReturnedCheck.STATUS_PENDING, author=self.user)
        ReturnedCheckEvent.objects.create(
            returned_check=rc, event_type=ReturnedCheckEvent.RETURNED,
            date=day, fee=ZERO, author=self.user)
        return rc

    def _post(self, url, **data):
        self.client.login(username='cajera', password='secreta')
        return self.client.post(url, data)

    # ---------- el caso que antes era imposible ----------

    def test_a_check_can_bounce_redeposit_and_bounce_again(self):
        check = self._check('1000.00')
        rc = self._return(check)

        self._post(f'/clients/update_return_check/{rc.id}', outcome='redeposited', date='06/05/2026')
        rc.refresh_from_db()
        self.assertEqual(rc.status, ReturnedCheck.STATUS_REDEPOSITED)

        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='bounced', date='06/10/2026', fee='35.00')
        rc.refresh_from_db()
        self.assertEqual(rc.status, ReturnedCheck.STATUS_PENDING)

        # …y otra vez, sin límite
        self._post(f'/clients/update_return_check/{rc.id}', outcome='redeposited', date='06/15/2026')
        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='bounced', date='06/20/2026', fee='35.00')
        rc.refresh_from_db()

        self.assertEqual(rc.status, ReturnedCheck.STATUS_PENDING)
        self.assertEqual(rc.events.count(), 5)
        self.assertEqual(rc.attempts, 3)   # devolución inicial + 2 rebotes

    def test_each_bounce_adds_its_own_fee(self):
        check = self._check('1000.00')
        rc = self._return(check)

        self.assertEqual(rc.total_fees, ZERO)

        self._post(f'/clients/update_return_check/{rc.id}', outcome='redeposited', date='06/05/2026')
        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='bounced', date='06/10/2026', fee='35.00')
        rc.refresh_from_db()
        self.assertEqual(rc.total_fees, Decimal('35.00'))

        self._post(f'/clients/update_return_check/{rc.id}', outcome='redeposited', date='06/15/2026')
        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='bounced', date='06/20/2026', fee='35.00')
        rc.refresh_from_db()
        self.assertEqual(rc.total_fees, Decimal('70.00'))

    # ---------- desenlaces ----------

    def test_a_successful_redeposit_closes_it_and_charges_the_fee_as_cash_in(self):
        check = self._check('1000.00')
        rc = self._return(check)
        self._post(f'/clients/update_return_check/{rc.id}', outcome='redeposited', date='06/05/2026')

        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='cleared', date='06/12/2026', fee='35.00')
        rc.refresh_from_db()

        self.assertEqual(rc.status, ReturnedCheck.STATUS_RECOVERED)

        movement = BalanceMovement.objects.get()
        self.assertEqual(movement.movement_type, BalanceMovement.CHECK_FEE)
        self.assertEqual(movement.amount, Decimal('35.00'))
        self.assertEqual(movement.account, self.account)
        self.assertEqual(movement.date, date(2026, 6, 12))
        # El monto del cheque NO entra: el cheque terminó pagando solo.
        self.assertFalse(Check.objects.filter(amount__lt=0).exists())

    def test_written_off_closes_the_file(self):
        rc = self._return(self._check('800.00'))
        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='written_off', date='06/30/2026')
        rc.refresh_from_db()

        self.assertEqual(rc.status, ReturnedCheck.STATUS_WRITTEN_OFF)
        self.assertFalse(rc.is_open)

    def test_a_closed_file_rejects_further_outcomes(self):
        rc = self._return(self._check('800.00'))
        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='written_off', date='06/30/2026')

        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='paid_cash', date='07/01/2026', fee='35.00')
        rc.refresh_from_db()
        self.assertEqual(rc.status, ReturnedCheck.STATUS_WRITTEN_OFF)

    # ---------- regresiones de los errores encontrados ----------

    def test_paid_cash_reversal_has_zero_commission_even_with_cents(self):
        """Regresión: `Check.save()` recalculaba la comisión con math.floor y
        dejaba 0.75 en un reverso de -1070.25."""
        check = self._check('1035.25')
        rc = self._return(check)

        self._post(f'/clients/update_return_check/{rc.id}',
                   outcome='paid_cash', date='06/30/2026', fee='35.00')
        rc.refresh_from_db()

        reversal = rc.reversal_check
        self.assertIsNotNone(reversal)
        self.assertEqual(reversal.amount, Decimal('-1070.25'))
        self.assertEqual(reversal.commission, ZERO)

    # ---------- alta de la devolución ----------

    def _search(self, client_obj, number, amount):
        """Paso 1 del alta: buscar el cheque por los tres criterios."""
        return self._post('/clients/new_return_check', step='buscar',
                          client=client_obj.id, check_number=number, amount=amount)

    def test_searching_a_duplicated_check_number_finds_the_right_client(self):
        """Regresión: `get()` lanzaba MultipleObjectsReturned sin capturar.

        En la base real hay 15 pares (número, monto) duplicados. El
        UniqueConstraint de Check es client+amount+check_number, así que los
        duplicados siguen siendo posibles entre clientes distintos: por eso el
        cliente es parte de los criterios y la búsqueda deja de ser ambigua.
        """
        self._check('1000.00', number=1043)
        maria = self._client('MARIA')
        self._check('1000.00', number=1043, client=maria)
        self._check('1000.00', number=1043, client=self._client('PEDRO'))

        response = self._search(maria, 1043, '1000.00')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['check'].client, maria)
        self.assertIsNotNone(response.context['returnCheckForm'])

    def test_registering_a_return_leaves_it_pending_with_its_first_event(self):
        check = self._check('1000.00')

        response = self._post('/clients/new_return_check', step='guardar',
                              original_check=check.id, date_returned='06/01/2026',
                              comment='Fondos insuficientes')

        self.assertEqual(response.status_code, 302)
        rc = ReturnedCheck.objects.get(original_check=check)
        self.assertEqual(rc.status, ReturnedCheck.STATUS_PENDING)
        self.assertEqual(rc.date_returned, date(2026, 6, 1))
        self.assertEqual(rc.author, self.user)

        event = rc.events.get()
        self.assertEqual(event.event_type, ReturnedCheckEvent.RETURNED)
        self.assertEqual(event.date, date(2026, 6, 1))
        # El fee se cobra en el desenlace, no al registrar la devolución.
        self.assertEqual(event.fee, ZERO)
        self.assertEqual(event.comment, 'Fondos insuficientes')

    def test_searching_a_check_that_does_not_exist_shows_no_form(self):
        response = self._search(self.client_obj, 9999, '1000.00')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['check'])
        self.assertIsNone(response.context['returnCheckForm'])
        self.assertEqual(ReturnedCheck.objects.count(), 0)

    def test_a_check_that_is_already_returned_cannot_be_returned_again(self):
        """`original_check` es OneToOne: un cheque tiene un solo expediente."""
        check = self._check('1000.00')
        self._return(check)

        response = self._search(self.client_obj, check.check_number, '1000.00')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['check'])
        self.assertEqual(ReturnedCheck.objects.count(), 1)

    def test_a_png_is_accepted_as_the_check_image(self):
        """El modelo sólo aceptaba pdf/jpg/jpeg y el alta pide también png."""
        check = self._check('1000.00')

        response = self._post(
            '/clients/new_return_check', step='guardar', original_check=check.id,
            date_returned='06/01/2026', comment='',
            file_path=SimpleUploadedFile('cheque.png', b'imagen', content_type='image/png'))

        self.assertEqual(response.status_code, 302)
        rc = ReturnedCheck.objects.get(original_check=check)
        self.assertTrue(rc.file_path)
        self.assertEqual(rc.ext, 'png')

    def test_an_unsupported_file_type_is_rejected(self):
        check = self._check('1000.00')

        response = self._post(
            '/clients/new_return_check', step='guardar', original_check=check.id,
            date_returned='06/01/2026', comment='',
            file_path=SimpleUploadedFile('cheque.gif', b'imagen', content_type='image/gif'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('file_path', response.context['returnCheckForm'].errors)
        self.assertEqual(ReturnedCheck.objects.count(), 0)
        # La ficha se repinta para que la cajera no pierda la búsqueda.
        self.assertEqual(response.context['check'], check)

    def test_an_empty_fee_does_not_crash(self):
        """Regresión: `Decimal('')` lanzaba InvalidOperation sin capturar."""
        rc = self._return(self._check('500.00'))
        response = self._post(f'/clients/update_return_check/{rc.id}',
                              outcome='paid_cash', date='06/30/2026', fee='')
        self.assertEqual(response.status_code, 302)
        rc.refresh_from_db()
        self.assertEqual(rc.status, ReturnedCheck.STATUS_RECOVERED)


@temp_media
class ReturnedCheckFileViewerTests(TestCase):
    """El visor elige <iframe> para PDF y <img> para imagen.

    Regresión: la plantilla comparaba `doc.ext`, que no existía en
    `ReturnedCheck` (es de `Document`), así que un PDF caía siempre en el
    <img> y se veía roto.
    """

    def setUp(self):
        self.user = User.objects.create_user('cajera', password='secreta')
        self.bmo = BrokerMoneyOrder.objects.create(broker_moneyorder_name='Intermex')
        self.country = Country.objects.create(iso='SV', name='El Salvador')
        self.company = Company.objects.create(name='ACME TEST')
        client_obj = Client.objects.create(
            first_name='ANA', last_name='LOPEZ', country=self.country,
            date_of_birth=date(1990, 1, 1))
        self.check = Check.objects.create(
            client=client_obj, amount=Decimal('500.00'), commission=ZERO,
            check_number=3001, company=self.company, broker=self.bmo,
            author=self.user, comm_percent=Decimal('1.5'))

    def _returned(self, filename):
        rc = ReturnedCheck.objects.create(
            original_check=self.check, date_returned=date(2026, 6, 1),
            status=ReturnedCheck.STATUS_PENDING, author=self.user)
        rc.file_path = filename
        rc.file_name = filename
        rc.save(update_fields=['file_path', 'file_name'])
        return rc

    def test_ext_is_lowercase_and_without_the_dot(self):
        self.assertEqual(self._returned('abc.PDF').ext, 'pdf')

    def test_ext_is_empty_without_a_file(self):
        rc = ReturnedCheck.objects.create(
            original_check=self.check, date_returned=date(2026, 6, 1),
            status=ReturnedCheck.STATUS_PENDING, author=self.user)
        self.assertEqual(rc.ext, '')

    def test_a_pdf_renders_in_an_iframe(self):
        rc = self._returned('comprobante.pdf')
        self.client.login(username='cajera', password='secreta')
        html = self.client.get(
            f'/clients/view_return_check_file/{rc.id}/').content.decode()

        self.assertIn('<iframe', html)
        self.assertNotIn('<img', html)
        self.assertIn(str(self.check.check_number), html)

    def test_an_image_renders_in_an_img_tag(self):
        rc = self._returned('cheque.jpg')
        self.client.login(username='cajera', password='secreta')
        html = self.client.get(
            f'/clients/view_return_check_file/{rc.id}/').content.decode()

        self.assertIn('<img', html)
        self.assertNotIn('<iframe', html)


@temp_media
class ReturnedCheckSingleFormTests(TestCase):
    """El expediente se maneja con un solo formulario y un selector de acción.

    Antes había un form por botón de desenlace más otro para archivo y
    comentario, y los campos compartidos se copiaban por JavaScript.
    """

    def setUp(self):
        self.user = User.objects.create_user('cajera', password='secreta')
        bmo = BrokerMoneyOrder.objects.create(broker_moneyorder_name='Intermex')
        country = Country.objects.create(iso='SV', name='El Salvador')
        company = Company.objects.create(name='ACME TEST')
        client_obj = Client.objects.create(
            first_name='JUAN', last_name='PEREZ', country=country,
            date_of_birth=date(1990, 1, 1))
        check = Check.objects.create(
            client=client_obj, amount=Decimal('1000.00'), commission=ZERO,
            check_number=1001, company=company, broker=bmo, author=self.user,
            comm_percent=Decimal('1.5'))
        self.rc = ReturnedCheck.objects.create(
            original_check=check, date_returned=date(2026, 6, 1),
            status=ReturnedCheck.STATUS_PENDING, author=self.user)
        ReturnedCheckEvent.objects.create(
            returned_check=self.rc, event_type=ReturnedCheckEvent.RETURNED,
            date=date(2026, 6, 1), fee=ZERO, comment='Rebotó por fondos',
            author=self.user)
        self.client.login(username='cajera', password='secreta')

    def _url(self):
        return f'/clients/update_return_check/{self.rc.id}'

    def _fragment(self):
        return self.client.get(
            self._url(), headers={'x-requested-with': 'XMLHttpRequest'}
        ).json()['html']

    def test_a_pending_file_offers_the_four_actions(self):
        html = self._fragment()
        for option in ['Ninguna', 'Re-depositar', 'Cliente pagó en efectivo',
                       'Dar por perdido']:
            self.assertIn(option, html)
        # Los desenlaces del re-depósito no aplican todavía.
        self.assertNotIn('Rebotó de nuevo', html)

    def test_a_closed_file_only_takes_comments(self):
        self.rc.status = ReturnedCheck.STATUS_WRITTEN_OFF
        self.rc.save()
        html = self._fragment()

        self.assertNotIn('div_id_outcome', html)
        self.assertNotIn('div_id_fee', html)
        self.assertIn('div_id_comment', html)

    def test_a_comment_without_action_is_logged_and_keeps_the_status(self):
        self.client.post(self._url(), {
            'outcome': '', 'date': '06/07/2026', 'comment': 'llamé al cliente'})
        self.rc.refresh_from_db()

        self.assertEqual(self.rc.status, ReturnedCheck.STATUS_PENDING)
        event = self.rc.events.latest('id')
        self.assertEqual(event.event_type, ReturnedCheckEvent.COMMENT)
        self.assertEqual(event.comment, 'llamé al cliente')
        self.assertEqual(event.fee, ZERO)

    def test_the_timeline_lists_the_newest_event_first(self):
        self.client.post(self._url(), {
            'outcome': '', 'date': '06/07/2026', 'comment': 'llamé al cliente'})

        entries = self.rc.timeline
        self.assertEqual(
            [entry.event_type for entry in entries],
            [ReturnedCheckEvent.COMMENT, ReturnedCheckEvent.RETURNED])
        self.assertEqual(entries[0].get_event_type_display(), 'Comentario')

    def test_a_redeposit_can_charge_its_own_fee(self):
        self.client.post(self._url(), {
            'outcome': 'redeposited', 'date': '06/07/2026', 'fee': '35.00'})
        self.rc.refresh_from_db()

        self.assertEqual(self.rc.status, ReturnedCheck.STATUS_REDEPOSITED)
        self.assertEqual(self.rc.events.latest('id').fee, Decimal('35.00'))
        self.assertEqual(self.rc.total_fees, Decimal('35.00'))

    def test_a_redeposit_without_fee_charges_nothing(self):
        self.client.post(self._url(), {
            'outcome': 'redeposited', 'date': '06/07/2026', 'fee': ''})
        self.rc.refresh_from_db()

        self.assertEqual(self.rc.events.latest('id').fee, ZERO)
        self.assertEqual(self.rc.total_fees, ZERO)

    def test_an_action_that_does_not_fit_the_status_is_rejected(self):
        self.client.post(self._url(), {
            'outcome': 'cleared', 'date': '06/07/2026', 'fee': '35.00'})
        self.rc.refresh_from_db()

        self.assertEqual(self.rc.status, ReturnedCheck.STATUS_PENDING)
