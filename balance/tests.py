from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clients.models import (
    Broker, BrokerMoneyOrder, Check, Client, Country, FidelityCard, MoneyOrder,
    SendMoney,
)
from companies.models import Company

from balance import services
from balance.models import BalanceAccount, BalanceMovement, DailyBalance

ZERO = Decimal('0.00')


class BalanceServicesTests(TestCase):
    """El módulo maneja dinero: se cubre la aritmética de `services`."""

    def setUp(self):
        self.day = date(2026, 6, 15)
        self.cashier = User.objects.create_user('cajera', password='x')
        self.other = User.objects.create_user('otra', password='x')

        self.broker = Broker.objects.create(broker_name='Intermex')
        self.bmo = BrokerMoneyOrder.objects.create(broker_moneyorder_name='Intermex')
        self.account = BalanceAccount.objects.create(
            name='Intermex Test', broker=self.broker,
            broker_moneyorder=self.bmo, order=1,
        )
        self.manual = BalanceAccount.objects.create(name='Loteria Test', order=2)

        self.country = Country.objects.create(iso='SV', name='El Salvador')
        self.card = FidelityCard.objects.create(card_num=999001, author=self.cashier)
        self.client_obj = Client.objects.create(
            first_name='JUAN', last_name='PEREZ', country=self.country,
            date_of_birth=date(1990, 1, 1),
        )
        self.company = Company.objects.create(name='ACME TEST')

    # ---------- helpers ----------

    def _at(self, day):
        """Datetime consciente de zona horaria a media mañana de `day`."""
        return timezone.make_aware(
            timezone.datetime.combine(day, timezone.datetime.min.time())
        ) + timedelta(hours=10)

    def _send_money(self, amount, day=None, author=None, broker_number=1,
                    payment_method='cash'):
        return SendMoney.objects.create(
            client=self.client_obj, amount=Decimal(amount),
            creation_date=self._at(day or self.day), country=self.country,
            broker=self.broker, fidelitycard=self.card,
            author=author or self.cashier, broker_number=broker_number,
            payment_method=payment_method,
        )

    def _check(self, amount, day=None, author=None):
        return Check.objects.create(
            client=self.client_obj, amount=Decimal(amount), commission=ZERO,
            check_number=12345, company=self.company, broker=self.bmo,
            author=author or self.cashier, created_at=self._at(day or self.day),
            comm_percent=Decimal('1.5'),
        )

    def _money_order(self, amount, day=None, author=None):
        return MoneyOrder.objects.create(
            client=self.client_obj, amount=Decimal(amount),
            created_at=self._at(day or self.day), broker_moneyorder=self.bmo,
            author=author or self.cashier,
        )

    def _rows(self, day=None, user=None):
        rows = services.build_balance(
            day or self.day, user=user, accounts=[self.account, self.manual],
        )
        return {row['account'].name: row for row in rows}

    # ---------- pruebas ----------

    def _store(self, initial='0.00', movement='0.00', account=None, day=None,
               company_balance=None):
        """Fila de tienda: cuenta manual, sin cajero dueño."""
        return DailyBalance.objects.create(
            user=None, account=account or self.manual, date=day or self.day,
            initial_balance=Decimal(initial), manual_movement=Decimal(movement),
            company_balance=company_balance, author=self.cashier,
        )

    def test_manual_account_has_no_automatic_lines(self):
        """Una cuenta sin brokers nunca recoge transacciones."""
        self._send_money('500.00')
        self._check('300.00')

        row = self._rows()['Loteria Test']

        self.assertTrue(row['is_manual'])
        self.assertEqual(row['send_money'], ZERO)
        self.assertEqual(row['checks'], ZERO)
        self.assertEqual(row['final_cash'], ZERO)

    def test_the_daily_sale_of_a_manual_account_is_typed_on_the_daily_view(self):
        """Loteria/Boss Revolution: la venta del día se digita al cierre.

        Reproduce la hoja de cálculo: BOSS REVOLUTION 740 + 125 = 865.
        """
        self._store('740.00', '125.00')

        row = self._rows()['Loteria Test']

        self.assertEqual(row['manual_movement'], Decimal('125.00'))
        self.assertEqual(row['final_cash'], Decimal('865.00'))

    def test_a_manual_movement_can_be_negative(self):
        """RESERVA de la hoja de cálculo: 20.000 - 550 = 19.450."""
        self._store('20000.00', '-550.00')

        self.assertEqual(self._rows()['Loteria Test']['final_cash'], Decimal('19450.00'))

    def test_a_manual_movement_defaults_to_zero(self):
        """FONDO CAMBIO: sin movimiento, el final es igual al inicial."""
        self._store('2000.00')
        row = self._rows()['Loteria Test']

        self.assertEqual(row['manual_movement'], ZERO)
        self.assertEqual(row['final_cash'], Decimal('2000.00'))

    def test_a_store_figure_is_not_attributed_to_any_cashier(self):
        """Con un cajero seleccionado la cuenta manual vale cero: la plata es de
        la tienda, así que no puede aparecer en la caja de nadie ni sumarse una
        vez por cajero."""
        self._store('740.00', '125.00')

        row = self._rows(user=self.cashier)['Loteria Test']

        self.assertEqual(row['initial'], ZERO)
        self.assertEqual(row['manual_movement'], ZERO)
        self.assertEqual(row['final_cash'], ZERO)

    def test_a_manual_account_never_shows_a_company_balance(self):
        """No se cuadra contra la empresa, ni siquiera si la columna trae un
        valor viejo de antes del cambio."""
        self._store('740.00', '125.00', company_balance=Decimal('900.00'))

        row = self._rows()['Loteria Test']

        self.assertIsNone(row['company_balance'])
        self.assertIsNone(row['difference'])

    def test_a_manual_account_still_adds_to_the_daily_total(self):
        """La plata de la tienda sí entra al efectivo del negocio."""
        self._store('740.00', '125.00')
        total = services.totals_row(list(self._rows().values()))

        self.assertEqual(total['final_cash'], Decimal('865.00'))
        self.assertIsNone(total['company_balance'])

    def test_send_money_adds_and_cancellation_subtracts(self):
        """Una fila negativa es efectivo devuelto: resta sin lógica especial."""
        self._send_money('500.00', broker_number=11)
        self._send_money('-200.00', broker_number=11)

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money'], Decimal('300.00'))
        self.assertEqual(row['final_cash'], Decimal('300.00'))

    def test_a_send_money_paid_by_card_does_not_move_the_drawer(self):
        """El cliente pagó por el datáfono: el envío existe pero el efectivo no
        pasó por la caja, así que no puede sumar al balance."""
        self._send_money('900.00', payment_method='card', broker_number=41)

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money_card'], Decimal('900.00'))
        self.assertEqual(row['send_money_cash'], ZERO)
        self.assertEqual(row['final_cash'], ZERO)

    def test_a_send_money_paid_by_vialink_does_not_move_the_drawer(self):
        """ViaLink se cobra por el enlace: mismo caso que la tarjeta."""
        self._send_money('300.00', payment_method='vialink', broker_number=42)

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money_vialink'], Decimal('300.00'))
        self.assertEqual(row['send_money_cash'], ZERO)
        self.assertEqual(row['final_cash'], ZERO)

    def test_the_three_payment_methods_add_up_to_the_gross_sends(self):
        """Solo el efectivo cuadra la caja, pero el bruto sigue visible: si las
        tres líneas no sumaran el total, un monto se estaría perdiendo."""
        self._send_money('1000.00', broker_number=51)
        self._send_money('400.00', payment_method='card', broker_number=52)
        self._send_money('250.00', payment_method='vialink', broker_number=53)

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money'], Decimal('1650.00'))
        self.assertEqual(row['send_money_cash'], Decimal('1000.00'))
        self.assertEqual(row['send_money_cashless'], Decimal('650.00'))
        self.assertEqual(row['final_cash'], Decimal('1000.00'))

    def test_an_unknown_payment_method_counts_as_cash(self):
        """El valor por omisión del modelo es efectivo: un método que el balance
        no conoce se cuenta en caja en vez de desaparecer del total, que dejaría
        la caja corta sin causa visible."""
        send = self._send_money('120.00', broker_number=54)
        # Se salta el modelo a propósito: `choices` no valida en la base, y el
        # caso que se prueba es justo un valor que el balance no conoce.
        SendMoney.objects.filter(pk=send.pk).update(payment_method='zelle')

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money_cash'], Decimal('120.00'))
        self.assertEqual(row['send_money'], Decimal('120.00'))
        self.assertEqual(row['final_cash'], Decimal('120.00'))

    def test_cancelling_a_card_send_leaves_the_cash_untouched(self):
        """La devolución vuelve a la tarjeta: resta de su propia línea y el
        efectivo del día no se entera."""
        self._send_money('500.00', broker_number=61)
        self._send_money('800.00', payment_method='card', broker_number=62)
        self._send_money('-800.00', payment_method='card', broker_number=62)

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['send_money_card'], ZERO)
        self.assertEqual(row['send_money_cash'], Decimal('500.00'))
        self.assertEqual(row['final_cash'], Decimal('500.00'))

    def test_the_daily_total_keeps_the_card_lines_out_of_the_cash(self):
        """La tarjeta TOTAL suma las líneas nuevas sin meterlas al efectivo."""
        self._send_money('1000.00', broker_number=71)
        self._send_money('400.00', payment_method='card', broker_number=72)

        total = services.totals_row(list(self._rows().values()))

        self.assertEqual(total['send_money_cash'], Decimal('1000.00'))
        self.assertEqual(total['send_money_card'], Decimal('400.00'))
        self.assertEqual(total['final_cash'], Decimal('1000.00'))

    def test_checks_subtract_and_commission_is_a_memo(self):
        """El cheque resta a valor bruto; la comisión no entra en el total."""
        check = self._check('1000.00')
        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['checks'], Decimal('-1000.00'))
        self.assertEqual(row['checks_commission'], check.commission)
        self.assertEqual(row['final_cash'], Decimal('-1000.00'))

    def test_money_orders_add_because_the_cash_comes_in(self):
        """El cliente paga el money order, así que el efectivo entra (+)."""
        self._money_order('1316.00')
        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['money_order'], Decimal('1316.00'))
        self.assertEqual(row['final_cash'], Decimal('1316.00'))

    def test_transfer_moves_cash_between_cashiers_with_one_row(self):
        """Doble partida: un solo registro resta al emisor y suma al receptor."""
        BalanceMovement.objects.create(
            movement_type=BalanceMovement.TRANSFER, date=self.day,
            amount=Decimal('1200.00'), from_user=self.cashier,
            to_user=self.other, account=self.account, author=self.cashier,
        )
        self.assertEqual(BalanceMovement.objects.count(), 1)

        sender = self._rows(user=self.cashier)['Intermex Test']
        receiver = self._rows(user=self.other)['Intermex Test']

        self.assertEqual(sender['outflows'], Decimal('-1200.00'))
        self.assertEqual(sender['final_cash'], Decimal('-1200.00'))
        self.assertEqual(receiver['inflows'], Decimal('1200.00'))
        self.assertEqual(receiver['final_cash'], Decimal('1200.00'))

    def test_transfers_are_internal_for_the_daily_view(self):
        """Un traslado entre cajeros no cambia el efectivo del negocio."""
        BalanceMovement.objects.create(
            movement_type=BalanceMovement.TRANSFER, date=self.day,
            amount=Decimal('1200.00'), from_user=self.cashier,
            to_user=self.other, account=self.account, author=self.cashier,
        )
        row = self._rows(user=None)['Intermex Test']

        self.assertEqual(row['outflows'], ZERO)
        self.assertEqual(row['final_cash'], ZERO)

    def test_bank_deposit_leaves_the_business_in_the_daily_view(self):
        """Un depósito bancario sí sale del efectivo del negocio."""
        BalanceMovement.objects.create(
            movement_type=BalanceMovement.BANK, date=self.day,
            amount=Decimal('12500.00'), from_user=self.cashier,
            account=self.account, author=self.cashier,
        )
        row = self._rows(user=None)['Intermex Test']

        self.assertEqual(row['outflows'], Decimal('-12500.00'))

    def test_difference_is_none_until_company_balance_is_entered(self):
        DailyBalance.objects.create(
            user=self.cashier, account=self.account, date=self.day,
            initial_balance=Decimal('100.00'), author=self.cashier,
        )
        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['initial'], Decimal('100.00'))
        self.assertIsNone(row['company_balance'])
        self.assertIsNone(row['difference'])

    def test_full_spreadsheet_scenario(self):
        """Reproduce la fila INTERMEX de la hoja de cálculo:
        inicial 0 + envíos 18.250 - depósitos 12.500 - cheques 5.000 = 750."""
        DailyBalance.objects.create(
            user=self.cashier, account=self.account, date=self.day,
            initial_balance=ZERO, company_balance=Decimal('810.00'),
            author=self.cashier,
        )
        self._send_money('18250.00', broker_number=21)
        self._check('5000.00')
        BalanceMovement.objects.create(
            movement_type=BalanceMovement.BANK, date=self.day,
            amount=Decimal('12500.00'), from_user=self.cashier,
            account=self.account, author=self.cashier,
        )

        row = self._rows(user=self.cashier)['Intermex Test']

        self.assertEqual(row['final_cash'], Decimal('750.00'))
        self.assertEqual(row['difference'], Decimal('-60.00'))

    def test_transactions_from_other_days_are_excluded(self):
        self._send_money('999.00', day=self.day - timedelta(days=1))
        row = self._rows(user=self.cashier)['Intermex Test']
        self.assertEqual(row['send_money'], ZERO)

    def test_other_cashiers_do_not_leak_into_a_personal_balance(self):
        self._send_money('700.00', author=self.other, broker_number=31)
        row = self._rows(user=self.cashier)['Intermex Test']
        self.assertEqual(row['send_money'], ZERO)


class BalanceMovementValidationTests(TestCase):

    def setUp(self):
        self.a = User.objects.create_user('a', password='x')
        self.b = User.objects.create_user('b', password='x')

    def test_transfer_requires_a_destination(self):
        movement = BalanceMovement(
            movement_type=BalanceMovement.TRANSFER, date=date(2026, 6, 15),
            amount=Decimal('10.00'), from_user=self.a, author=self.a,
        )
        with self.assertRaises(Exception):
            movement.full_clean()

    def test_transfer_to_self_is_rejected(self):
        movement = BalanceMovement(
            movement_type=BalanceMovement.TRANSFER, date=date(2026, 6, 15),
            amount=Decimal('10.00'), from_user=self.a, to_user=self.a,
            author=self.a,
        )
        with self.assertRaises(Exception):
            movement.full_clean()

    def test_non_transfer_must_not_have_a_destination(self):
        movement = BalanceMovement(
            movement_type=BalanceMovement.BANK, date=date(2026, 6, 15),
            amount=Decimal('10.00'), from_user=self.a, to_user=self.b,
            author=self.a,
        )
        with self.assertRaises(Exception):
            movement.full_clean()


class BalanceViewTests(TestCase):
    """Renderizado y permisos de las tres vistas."""

    def setUp(self):
        self.cashier = User.objects.create_user('cajera', password='secreta')
        self.admin = User.objects.create_superuser('jefe', password='secreta')
        # Balance personal solo muestra cuentas enlazadas a un broker.
        self.account = BalanceAccount.objects.create(
            name='Cuenta Test', order=1,
            broker=Broker.objects.create(broker_name='Cuenta Test'),
        )
        self.manual = BalanceAccount.objects.create(name='Loteria Test', order=2)

    def test_login_is_required(self):
        response = self.client.get('/balance/personal')
        self.assertEqual(response.status_code, 302)

    def test_personal_renders_for_a_cashier(self):
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/personal')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cuenta Test')

    def test_personal_leaves_the_manual_accounts_out(self):
        """Son cifras del negocio: solo se digitan en el balance diario.

        El nombre de la cuenta sí sigue apareciendo en el selector del modal de
        movimientos (un depósito a caja fuerte puede ir contra Reserva), así que
        lo que se busca es la insignia que solo lleva una tarjeta manual.
        """
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/personal')

        self.assertNotContains(response, 'text-bg-secondary">Manual')
        names = [row['account'].name for row in response.context['rows']]
        self.assertEqual(names, ['Cuenta Test'])

    def test_the_daily_view_offers_the_manual_accounts_for_capture(self):
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/diario')
        rows = {row['account'].name: row for row in response.context['rows']}

        self.assertTrue(rows['Loteria Test']['editable'])
        self.assertFalse(rows['Cuenta Test']['editable'])
        self.assertNotIn('company_balance', rows['Loteria Test']['form'].fields)

    def test_daily_renders_for_a_cashier(self):
        self.client.login(username='cajera', password='secreta')
        self.assertEqual(self.client.get('/balance/diario').status_code, 200)

    def test_monthly_is_blocked_for_a_cashier(self):
        self.client.login(username='cajera', password='secreta')
        self.assertEqual(self.client.get('/balance/mensual').status_code, 403)

    def test_monthly_renders_for_a_superuser(self):
        self.client.login(username='jefe', password='secreta')
        self.assertEqual(self.client.get('/balance/mensual').status_code, 200)

    def test_monthly_link_is_hidden_from_a_cashier(self):
        """El menú desplegable no ofrece Mensual a un cajero.

        Se busca el href y no la cadena suelta: el JS del navbar menciona
        "/balance/mensual" para resaltar el menú activo y siempre se renderiza.
        """
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/personal')
        self.assertNotContains(response, 'href="/balance/mensual"')

    def test_monthly_link_is_offered_to_a_superuser(self):
        self.client.login(username='jefe', password='secreta')
        response = self.client.get('/balance/personal')
        self.assertContains(response, 'href="/balance/mensual"')

    def test_the_navbar_offers_the_three_balance_views(self):
        self.client.login(username='jefe', password='secreta')
        response = self.client.get('/balance/personal')
        for href in ['href="/balance/personal"', 'href="/balance/diario"',
                     'href="/balance/mensual"']:
            self.assertContains(response, href)

    def test_a_cashier_cannot_see_another_cashiers_balance(self):
        """El parámetro ?user= solo lo obedece un superusuario."""
        other = User.objects.create_user('otra', password='secreta')
        self.client.login(username='cajera', password='secreta')
        response = self.client.get(f'/balance/personal?user={other.pk}')
        self.assertEqual(response.context['target_user'], self.cashier)

    def test_a_superuser_can_select_another_cashier(self):
        self.client.login(username='jefe', password='secreta')
        response = self.client.get(f'/balance/personal?user={self.cashier.pk}')
        self.assertEqual(response.context['target_user'], self.cashier)

    def test_saving_the_balance_persists_the_typed_figures(self):
        self.client.login(username='cajera', password='secreta')
        response = self.client.post('/balance/personal?date=06/15/2026', {
            f'acc{self.account.id}-initial_balance': '250.00',
            f'acc{self.account.id}-company_balance': '300.00',
        })
        self.assertEqual(response.status_code, 302)
        saved = DailyBalance.objects.get(user=self.cashier, account=self.account)
        self.assertEqual(saved.initial_balance, Decimal('250.00'))
        self.assertEqual(saved.date, date(2026, 6, 15))

    def test_the_daily_view_stores_the_manual_sale_as_a_store_row(self):
        """BOSS REVOLUTION 740 + 125: una sola fila sin cajero dueño, con
        `author` de quien la digitó."""
        self.client.login(username='cajera', password='secreta')
        response = self.client.post('/balance/diario?date=06/15/2026', {
            f'acc{self.manual.id}-initial_balance': '740.00',
            f'acc{self.manual.id}-manual_movement': '125.00',
        })
        self.assertEqual(response.status_code, 302)

        saved = DailyBalance.objects.get(account=self.manual)
        self.assertIsNone(saved.user)
        self.assertEqual(saved.author, self.cashier)
        self.assertEqual(saved.date, date(2026, 6, 15))
        self.assertEqual(saved.initial_balance, Decimal('740.00'))
        self.assertEqual(saved.manual_movement, Decimal('125.00'))
        self.assertIsNone(saved.company_balance)

    def test_a_second_cashier_corrects_the_store_row_instead_of_duplicating_it(self):
        """La cifra es de la tienda: dos cajeros no pueden dejar dos filas y
        que el diario las sume."""
        other = User.objects.create_user('otra', password='secreta')
        self.client.login(username='cajera', password='secreta')
        self.client.post('/balance/diario?date=06/15/2026', {
            f'acc{self.manual.id}-initial_balance': '740.00',
            f'acc{self.manual.id}-manual_movement': '125.00',
        })

        self.client.login(username='otra', password='secreta')
        self.client.post('/balance/diario?date=06/15/2026', {
            f'acc{self.manual.id}-initial_balance': '740.00',
            f'acc{self.manual.id}-manual_movement': '200.00',
        })

        saved = DailyBalance.objects.get(account=self.manual)
        self.assertEqual(saved.manual_movement, Decimal('200.00'))
        self.assertEqual(saved.author, other)

    def test_a_manual_account_cannot_receive_a_company_balance_through_the_post(self):
        self.client.login(username='cajera', password='secreta')
        self.client.post('/balance/diario?date=06/15/2026', {
            f'acc{self.manual.id}-initial_balance': '740.00',
            f'acc{self.manual.id}-company_balance': '900.00',
        })

        self.assertIsNone(DailyBalance.objects.get(account=self.manual).company_balance)

    def test_the_store_figure_is_not_charged_to_any_cashier(self):
        """Aparece una sola vez en el total del negocio y en la caja de nadie."""
        DailyBalance.objects.create(
            user=None, account=self.manual, date=date(2026, 6, 15),
            initial_balance=Decimal('740.00'), manual_movement=Decimal('125.00'),
            author=self.cashier,
        )
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/diario?date=06/15/2026')

        rows = {row['account'].name: row for row in response.context['rows']}
        self.assertEqual(rows['Loteria Test']['final_cash'], Decimal('865.00'))
        self.assertEqual(response.context['total']['final_cash'], Decimal('865.00'))
        for entry in response.context['per_user']:
            self.assertEqual(entry['total']['final_cash'], ZERO)

    def test_the_new_manual_accounts_are_seeded(self):
        """Las agrega la migración 0006, sin broker: manuales por construcción."""
        for name in ['Venta diaria / Clover', 'Sobrantes']:
            self.assertTrue(BalanceAccount.objects.get(name=name).is_manual)

    def test_a_date_after_the_12th_is_parsed_as_month_day_year(self):
        """Con LANGUAGE_CODE='es' Django parsearía 09/15 como día 9 mes 15
        (inválido) y caería a hoy. `input_formats` lo evita."""
        self.client.login(username='cajera', password='secreta')
        response = self.client.get('/balance/personal?date=09/15/2026')
        self.assertEqual(response.context['date'], date(2026, 9, 15))

    def test_creating_a_transfer_records_one_row(self):
        other = User.objects.create_user('otra', password='secreta')
        self.client.login(username='cajera', password='secreta')
        response = self.client.post('/balance/movimiento/nuevo', {
            'movement_type': 'transfer', 'date': '06/15/2026',
            'amount': '1200.00', 'to_user': other.pk, 'account': self.account.pk,
            'description': 'Traslado de turno',
        })
        self.assertEqual(response.status_code, 302)
        movement = BalanceMovement.objects.get()
        self.assertEqual(movement.from_user, self.cashier)
        self.assertEqual(movement.to_user, other)
        self.assertEqual(movement.amount, Decimal('1200.00'))

    def test_from_user_cannot_be_forged_through_the_post(self):
        other = User.objects.create_user('otra', password='secreta')
        self.client.login(username='cajera', password='secreta')
        self.client.post('/balance/movimiento/nuevo', {
            'movement_type': 'bank', 'date': '06/15/2026', 'amount': '50.00',
            'from_user': other.pk, 'author': other.pk,
        })
        movement = BalanceMovement.objects.get()
        self.assertEqual(movement.from_user, self.cashier)
        self.assertEqual(movement.author, self.cashier)

    def test_a_cashier_cannot_delete_a_movement(self):
        movement = BalanceMovement.objects.create(
            movement_type=BalanceMovement.BANK, date=date(2026, 6, 15),
            amount=Decimal('50.00'), from_user=self.cashier, author=self.cashier,
        )
        self.client.login(username='cajera', password='secreta')
        response = self.client.post(f'/balance/movimiento/{movement.pk}/eliminar')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(BalanceMovement.objects.filter(pk=movement.pk).exists())
