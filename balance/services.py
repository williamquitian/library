"""Cálculo del balance de caja.

Todas las cifras automáticas salen de las transacciones que el CRM ya guarda
(`SendMoney`, `MoneyOrder`, `Check`, `ReturnedCheck`) más los movimientos de
efectivo de `BalanceMovement`. Lo que se digita a mano -- balance inicial,
movimiento del día de las cuentas manuales y balance final de la empresa -- vive
en `DailyBalance`.

Solo el efectivo entra al balance: un envío pagado con tarjeta o por ViaLink se
agrega aparte y se muestra como memo, porque ese dinero nunca pasó por el cajón.

Las consultas se agrupan por día y por broker en una sola pasada, así que el
costo no depende del número de cuentas: son ~6 consultas para un día y ~6 para
un mes completo.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils.timezone import make_aware

from clients.models import Check, MoneyOrder, ReturnedCheck, SendMoney

from .models import BalanceAccount, BalanceMovement, DailyBalance

ZERO = Decimal('0.00')


def _z(value):
    """Normaliza el cero negativo: Decimal('-0.00') se imprimiría como "$-0.00"."""
    return value or ZERO

# Signo de cada línea sobre el efectivo en caja. Cambiar una regla de negocio es
# cambiar una línea de este diccionario.
#
#   send_money_cash (+) el cliente entrega efectivo para enviar
#   money_order     (+) el cliente paga el money order: el efectivo entra
#   checks          (-) se paga efectivo al cliente por su cheque
#
# Los cheques devueltos NO están aquí a propósito: el día que el cheque rebota
# no se mueve efectivo (la plata salió el día que se cambió el cheque). Sumarlo
# otra vez descuadraría la caja contra el dinero físico del cajón. Se muestra
# aparte, como saldo pendiente de cobrar al cliente.
LINE_SIGNS = {
    'send_money_cash': Decimal('1'),
    'money_order': Decimal('1'),
    'checks': Decimal('-1'),
}

# Líneas automáticas que sí entran al total, en el orden de la tarjeta.
LINE_LABELS = [
    ('send_money_cash', 'Envíos en efectivo'),
    ('money_order', 'Money orders'),
    ('checks', 'Cheques'),
]

# Envíos que el cliente NO paga en efectivo (`SendMoney.payment_method`): el
# dinero entra por el datáfono o por ViaLink y nunca pasa por el cajón, así que
# no puede sumar al balance de caja. Se agregan aparte y se muestran como memo,
# igual que la comisión de cheques. Es la misma regla que ya aplica
# `reports.views.summary_report`, que excluye los dos del total.
#
# Un método que no esté en este dict cae en `send_money_cash` a propósito: el
# valor por omisión del modelo es `cash`, y mandar plata a un bucket sin línea
# dejaría la caja corta sin causa visible.
SEND_MONEY_CASHLESS = {
    'card': 'send_money_card',
    'vialink': 'send_money_vialink',
}


def day_bounds(day):
    """Rango consciente de zona horaria que cubre `day` completo.

    Mismo patrón que `reports.views`, para que el balance y los reportes
    existentes recorten los días exactamente igual.
    """
    start = make_aware(datetime.combine(day, datetime.min.time()))
    end = make_aware(datetime.combine(day, datetime.max.time()))
    return start, end


def _by_day(queryset, date_expr, key_field, value_field='amount'):
    """-> {(fecha, key): total} en una sola consulta agregada."""
    rows = (
        queryset.annotate(_day=date_expr)
        .values('_day', key_field)
        .annotate(total=Sum(value_field))
    )
    return {(row['_day'], row[key_field]): (row['total'] or ZERO) for row in rows}


def collect(start_date, end_date, user=None):
    """Agrega todas las líneas automáticas entre dos fechas (ambas incluidas).

    Devuelve un dict anidado ``{fecha: {clave: Decimal}}`` donde la clave es
    ``(línea, broker_id)``. `user` restringe al autor de la transacción; sin él
    se agregan todos los cajeros.
    """
    start_dt, _ = day_bounds(start_date)
    _, end_dt = day_bounds(end_date)
    trunc = TruncDate('creation_date')
    trunc_created = TruncDate('created_at')

    send_money_qs = SendMoney.objects.filter(creation_date__range=(start_dt, end_dt))
    money_order_qs = MoneyOrder.objects.filter(created_at__range=(start_dt, end_dt))
    check_qs = Check.objects.filter(created_at__range=(start_dt, end_dt))

    if user is not None:
        send_money_qs = send_money_qs.filter(author=user)
        money_order_qs = money_order_qs.filter(author=user)
        check_qs = check_qs.filter(author=user)

    data = defaultdict(lambda: defaultdict(lambda: ZERO))

    # Los montos negativos de SendMoney son cancelaciones: para un balance de
    # caja son simplemente efectivo que salió ese día, así que se suman tal
    # cual. No se replica la lógica de 23 horas de `reports.views.summary_report`
    # (que además hace una consulta por fila). Una cancelación de un envío con
    # tarjeta ya viene marcada `card`, así que resta de la línea que le toca.
    #
    # El método de pago decide si el envío entra al cajón, así que se agrupa
    # también por él. `_by_day` solo admite una clave, y son dos: la agregación
    # va en línea, en una sola consulta. Cada fila suma a su línea por método y
    # al bruto `send_money`, de forma que siempre se cumple
    # `send_money == cash + card + vialink` y ningún monto se pierde.
    send_money_rows = (
        send_money_qs.annotate(_day=trunc)
        .values('_day', 'broker', 'payment_method')
        .annotate(total=Sum('amount'))
    )
    for row in send_money_rows:
        total = row['total'] or ZERO
        key = SEND_MONEY_CASHLESS.get(row['payment_method'], 'send_money_cash')
        data[row['_day']][(key, row['broker'])] += total
        data[row['_day']][('send_money', row['broker'])] += total

    for (day, broker_id), total in _by_day(money_order_qs, trunc_created, 'broker_moneyorder').items():
        data[day][('money_order', broker_id)] += total

    for (day, broker_id), total in _by_day(check_qs, trunc_created, 'broker').items():
        data[day][('checks', broker_id)] += total

    for (day, broker_id), total in _by_day(check_qs, trunc_created, 'broker', 'commission').items():
        data[day][('checks_commission', broker_id)] += total

    return data


def collect_movements(start_date, end_date, user=None):
    """Movimientos de efectivo agregados por día y cuenta.

    Devuelve ``{fecha: {('out'|'in', account_id): Decimal}}``.

    En la vista personal, `out` es todo lo que el usuario entregó y `in` lo que
    recibió por traslado. En la vista diaria (sin usuario) los traslados entre
    cajeros **se excluyen**: son internos y no cambian el efectivo del negocio.
    """
    qs = BalanceMovement.objects.filter(date__range=(start_date, end_date))
    data = defaultdict(lambda: defaultdict(lambda: ZERO))

    income = BalanceMovement.INCOME_TYPES

    if user is None:
        qs = qs.exclude(movement_type=BalanceMovement.TRANSFER)
        rows = qs.values('date', 'account', 'movement_type').annotate(total=Sum('amount'))
        for row in rows:
            bucket = 'in' if row['movement_type'] in income else 'out'
            data[row['date']][(bucket, row['account'])] += row['total'] or ZERO
        return data

    own = qs.filter(from_user=user).values(
        'date', 'account', 'movement_type').annotate(total=Sum('amount'))
    for row in own:
        bucket = 'in' if row['movement_type'] in income else 'out'
        data[row['date']][(bucket, row['account'])] += row['total'] or ZERO

    in_rows = (
        qs.filter(to_user=user, movement_type=BalanceMovement.TRANSFER)
        .values('date', 'account')
        .annotate(total=Sum('amount'))
    )
    for row in in_rows:
        data[row['date']][('in', row['account'])] += row['total'] or ZERO

    return data


def _build_row(account, day_data, movement_data, daily):
    """Arma la tarjeta vertical de una cuenta para un día."""
    initial = daily.initial_balance if daily else ZERO
    manual_movement = daily.manual_movement if daily else ZERO
    # Una cuenta manual no se cuadra contra nada: sin balance final de la empresa
    # no hay diferencia que calcular, aunque la columna arrastre un valor viejo.
    company_balance = (
        None if account.is_manual else (daily.company_balance if daily else None)
    )

    # Los envíos cuelgan de `clients.Broker`; cheques, money orders y
    # devoluciones cuelgan de `clients.BrokerMoneyOrder`.
    broker_for = {
        'send_money_cash': account.broker_id,
        'money_order': account.broker_moneyorder_id,
        'checks': account.broker_moneyorder_id,
    }
    lines = {
        key: _z(LINE_SIGNS[key] * day_data.get((key, broker_for[key]), ZERO))
        for key, _label in LINE_LABELS
    }

    # Memos informativos: ninguno entra en el total.
    #
    #  - tarjeta y ViaLink: el cliente pagó fuera del cajón, así que el envío
    #    existe pero el efectivo no. `send_money` queda como el bruto de los
    #    tres métodos, solo para mostrar.
    #  - comisión de cheques: el balance usa el monto bruto del cheque, igual
    #    que la hoja de cálculo actual.
    send_money_gross = day_data.get(('send_money', account.broker_id), ZERO)
    card = day_data.get(('send_money_card', account.broker_id), ZERO)
    vialink = day_data.get(('send_money_vialink', account.broker_id), ZERO)
    commission = day_data.get(('checks_commission', account.broker_moneyorder_id), ZERO)

    outflows = _z(-movement_data.get(('out', account.id), ZERO))
    inflows = _z(movement_data.get(('in', account.id), ZERO))

    final_cash = _z(
        initial + sum(lines.values()) + manual_movement + outflows + inflows
    )
    difference = None if company_balance is None else final_cash - company_balance

    return {
        'account': account,
        'is_manual': account.is_manual,
        'initial': initial,
        'manual_movement': _z(manual_movement),
        'send_money': _z(send_money_gross),
        'send_money_cash': lines['send_money_cash'],
        'send_money_card': _z(card),
        'send_money_vialink': _z(vialink),
        'send_money_cashless': _z(card + vialink),
        'money_order': lines['money_order'],
        'checks': lines['checks'],
        'checks_commission': commission,
        'outflows': outflows,
        'inflows': inflows,
        'final_cash': final_cash,
        'company_balance': company_balance,
        'difference': difference,
        'daily': daily,
    }


class _AggregatedDaily:
    """Stand-in de `DailyBalance` para la vista diaria, donde las cifras
    digitadas por varios cajeros se suman en una sola."""

    pk = None

    def __init__(self, initial_balance, company_balance, manual_movement=None):
        self.initial_balance = initial_balance or ZERO
        self.company_balance = company_balance
        self.manual_movement = manual_movement or ZERO


def _daily_map(start_date, end_date, user, accounts):
    """-> ``{fecha: {account_id: fila digitada}}`` para el rango.

    Las dos formas de fila de `DailyBalance` se leen distinto:

    - **de cajero**: su propia fila si se pidió un cajero; si no, la suma de lo
      que digitaron todos (`_AggregatedDaily`).
    - **de tienda** (cuentas manuales): solo se leen cuando **no** hay cajero
      seleccionado, porque son plata del negocio y no de nadie en particular. Se
      devuelve la instancia real de `DailyBalance` y no un agregado, porque la
      vista `diario` le liga el formulario con `instance=`.
    """
    data = defaultdict(dict)
    qs = DailyBalance.objects.filter(date__range=(start_date, end_date))

    if user is not None:
        for row in qs.filter(user=user):
            data[row.date][row.account_id] = row
        return data

    for row in qs.filter(user__isnull=False).values('date', 'account').annotate(
        initial=Sum('initial_balance'), company=Sum('company_balance'),
        manual=Sum('manual_movement'),
    ):
        data[row['date']][row['account']] = _AggregatedDaily(
            row['initial'], row['company'], row['manual']
        )

    # Una consulta que solo se paga si hay alguna cuenta manual en juego.
    if any(account.is_manual for account in accounts):
        for row in qs.filter(user__isnull=True):
            data[row.date][row.account_id] = row

    return data


def build_balance(day, user=None, accounts=None):
    """Filas del balance de un día, una por cuenta activa."""
    if accounts is None:
        accounts = list(BalanceAccount.objects.active())

    day_data = collect(day, day, user=user).get(day, {})
    movement_data = collect_movements(day, day, user=user).get(day, {})
    daily_map = _daily_map(day, day, user, accounts).get(day, {})

    return [
        _build_row(account, day_data, movement_data, daily_map.get(account.id))
        for account in accounts
    ]


def totals_row(rows):
    """Fila TOTAL: suma vertical de todas las cuentas."""
    keys = [
        'initial', 'manual_movement',
        'send_money', 'send_money_cash', 'send_money_card', 'send_money_vialink',
        'send_money_cashless', 'money_order', 'checks',
        'checks_commission', 'outflows', 'inflows',
        'final_cash',
    ]
    total = {key: _z(sum((row[key] for row in rows), ZERO)) for key in keys}

    company_values = [r['company_balance'] for r in rows if r['company_balance'] is not None]
    total['company_balance'] = sum(company_values, ZERO) if company_values else None
    total['difference'] = (
        None if total['company_balance'] is None
        else total['final_cash'] - total['company_balance']
    )
    return total


# Claves aditivas a lo largo del mes.
FLOW_KEYS = [
    'send_money', 'send_money_cash', 'send_money_card', 'send_money_vialink',
    'send_money_cashless', 'money_order', 'checks', 'checks_commission',
    'outflows', 'inflows', 'manual_movement',
]


def _has_activity(row):
    return any(row[k] for k in FLOW_KEYS) or bool(row['initial']) or (
        row['company_balance'] is not None
    )


def summarize_month(days, accounts):
    """Resumen del mes por cuenta y total general.

    Los flujos (envíos, money orders, cheques, devueltos, salidas) **sí** se
    suman a lo largo del mes: son aditivos. El balance inicial y el balance
    final **no** se suman -- sumar 30 aperturas no significa nada. Se toma la
    apertura del primer día con captura y el cierre del último día con
    movimiento.
    """
    rows = []
    for index, account in enumerate(accounts):
        account_days = [entry['rows'][index] for entry in days]

        summary = {key: _z(sum((d[key] for d in account_days), ZERO)) for key in FLOW_KEYS}

        opening = next((d['initial'] for d in account_days if d['initial']), ZERO)
        closing = next(
            (d for d in reversed(account_days) if _has_activity(d)),
            None,
        )

        summary.update({
            'account': account,
            'is_manual': account.is_manual,
            'initial': opening,
            'final_cash': closing['final_cash'] if closing else ZERO,
            'company_balance': closing['company_balance'] if closing else None,
            'daily': None,
        })
        summary['difference'] = (
            None if summary['company_balance'] is None
            else _z(summary['final_cash'] - summary['company_balance'])
        )
        rows.append(summary)

    total = {key: _z(sum((r[key] for r in rows), ZERO))
             for key in FLOW_KEYS + ['initial', 'final_cash']}
    company = [r['company_balance'] for r in rows if r['company_balance'] is not None]
    total['company_balance'] = _z(sum(company, ZERO)) if company else None
    total['difference'] = (
        None if total['company_balance'] is None
        else _z(total['final_cash'] - total['company_balance'])
    )
    return rows, total


def build_month(year, month, user=None):
    """Grilla día a día del mes: una fila por día con el total de cada cuenta."""
    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)

    accounts = list(BalanceAccount.objects.active())
    month_data = collect(first_day, last_day, user=user)
    movement_data = collect_movements(first_day, last_day, user=user)
    daily_map = _daily_map(first_day, last_day, user, accounts)

    days = []
    day = first_day
    while day <= last_day:
        rows = [
            _build_row(
                account,
                month_data.get(day, {}),
                movement_data.get(day, {}),
                daily_map.get(day, {}).get(account.id),
            )
            for account in accounts
        ]
        days.append({'date': day, 'rows': rows, 'total': totals_row(rows)})
        day += timedelta(days=1)

    account_rows, month_total = summarize_month(days, accounts)
    return {'accounts': accounts, 'days': days, 'total': month_total,
            'account_rows': account_rows,
            'first_day': first_day, 'last_day': last_day}


def build_month_per_user(year, month):
    """Desglose del mes por cajero: una fila por usuario con actividad."""
    first_day = datetime(year, month, 1).date()
    last_day = (
        datetime(year + 1, 1, 1).date() if month == 12
        else datetime(year, month + 1, 1).date()
    ) - timedelta(days=1)

    per_user = []
    for user in users_with_activity(first_day, last_day):
        data = build_month(year, month, user=user)
        per_user.append({'user': user, 'total': data['total']})
    return per_user


def users_with_activity(start_date, end_date=None):
    """Cajeros con transacciones o movimientos en el rango (ambos incluidos).

    Evita recorrer toda la tabla de usuarios: solo se calcula el balance de
    quien realmente movió dinero.
    """
    from django.contrib.auth.models import User

    end_date = end_date or start_date
    start_dt, _ = day_bounds(start_date)
    _, end_dt = day_bounds(end_date)
    author_ids = set()
    author_ids.update(
        SendMoney.objects.filter(creation_date__range=(start_dt, end_dt))
        .values_list('author_id', flat=True).distinct()
    )
    author_ids.update(
        MoneyOrder.objects.filter(created_at__range=(start_dt, end_dt))
        .values_list('author_id', flat=True).distinct()
    )
    author_ids.update(
        Check.objects.filter(created_at__range=(start_dt, end_dt))
        .values_list('author_id', flat=True).distinct()
    )
    author_ids.update(
        ReturnedCheck.objects.filter(date_returned__range=(start_date, end_date))
        .values_list('author_id', flat=True).distinct()
    )
    movements = BalanceMovement.objects.filter(date__range=(start_date, end_date))
    author_ids.update(movements.values_list('from_user_id', flat=True).distinct())
    author_ids.update(
        m for m in movements.values_list('to_user_id', flat=True).distinct() if m
    )
    author_ids.update(
        DailyBalance.objects.filter(date__range=(start_date, end_date))
        .exclude(user__isnull=True)
        .values_list('user_id', flat=True).distinct()
    )

    return User.objects.filter(pk__in=author_ids).order_by('username')
