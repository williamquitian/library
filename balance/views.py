from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import superuser_required

from . import services
from .forms import (
    BalanceDateForm,
    BalanceMonthForm,
    BalanceMovementForm,
    DailyBalanceForm,
)
from .models import BalanceAccount, BalanceMovement, DailyBalance

User = get_user_model()


def _selected_date(request):
    """Devuelve (fecha, usuario, form listo para renderizar).

    El form se valida ligado al GET, pero se devuelve **sin ligar** con los
    valores ya parseados: el JS del datepicker espera el valor en formato
    backend (YYYY-MM-DD) y un form ligado re-renderiza la cadena cruda del GET,
    que la librería corrompe al mostrarla.
    """
    show_user = request.user.is_superuser
    bound = BalanceDateForm(request.GET or None, show_user=show_user)

    day = date.today()
    user = request.user
    if bound.is_bound and bound.is_valid():
        day = bound.cleaned_data.get('date') or day
        if show_user:
            user = bound.cleaned_data.get('user') or request.user

    initial = {'date': day}
    if show_user:
        initial['user'] = user
    return day, user, BalanceDateForm(initial=initial, show_user=show_user)


@login_required
def personal(request):
    """Balance personal del día: cifras digitadas + movimientos del cajero."""
    day, target_user, date_form = _selected_date(request)
    # Las cuentas manuales son cifras del negocio y no de un cajero: se digitan
    # en la vista diaria.
    accounts = list(BalanceAccount.objects.automatic())

    existing = {
        d.account_id: d
        for d in DailyBalance.objects.filter(date=day, user=target_user)
    }
    edit_forms = {
        account.id: DailyBalanceForm(
            request.POST or None,
            instance=existing.get(account.id),
            prefix=f'acc{account.id}',
        )
        for account in accounts
    }

    if request.method == 'POST':
        if all(f.is_valid() for f in edit_forms.values()):
            with transaction.atomic():
                for account in accounts:
                    form = edit_forms[account.id]
                    if form.is_empty:
                        continue
                    obj = form.save(commit=False)
                    obj.user = target_user
                    obj.account = account
                    obj.date = day
                    obj.author = request.user
                    obj.save()
            messages.success(request, 'Balance guardado.')
            url = reverse('balance-personal')
            return redirect(f"{url}?date={day:%m/%d/%Y}&user={target_user.pk}")
        messages.error(request, 'Revise los valores digitados.')

    rows = services.build_balance(day, user=target_user, accounts=accounts)
    for row in rows:
        row['form'] = edit_forms[row['account'].id]
        row['editable'] = True

    movements = (
        BalanceMovement.objects.filter(date=day)
        .filter(from_user=target_user)
        .select_related('from_user', 'to_user', 'account')
    )
    received = (
        BalanceMovement.objects.filter(
            date=day, to_user=target_user, movement_type=BalanceMovement.TRANSFER
        ).select_related('from_user', 'to_user', 'account')
    )

    context = {
        'scope': 'personal',
        'date': day,
        'date_form': date_form,
        'target_user': target_user,
        'rows': rows,
        'total': services.totals_row(rows),
        'movements': list(movements) + list(received),
        'movement_form': BalanceMovementForm(
            current_user=request.user, initial={'date': day}
        ),
        'line_labels': services.LINE_LABELS,
    }
    return render(request, 'balance/tmpl_personal.html', context)


@login_required
def diario(request):
    """Balance del día de todo el negocio, sumando a todos los cajeros.

    Es además donde se digitan las cuentas manuales: una sola cifra de la tienda
    por cuenta y día, que captura o corrige cualquier cajero.
    """
    day, _user, date_form = _selected_date(request)
    # Una consulta y el corte en Python, que es lo que ya hace `is_manual`.
    accounts = list(BalanceAccount.objects.active())
    manual = [a for a in accounts if a.is_manual]
    automatic = [a for a in accounts if not a.is_manual]

    existing = {
        d.account_id: d
        for d in DailyBalance.objects.filter(
            date=day, user__isnull=True, account__in=manual
        )
    }
    edit_forms = {
        account.id: DailyBalanceForm(
            request.POST or None,
            instance=existing.get(account.id),
            prefix=f'acc{account.id}',
            is_manual=True,
        )
        for account in manual
    }

    if request.method == 'POST':
        if all(f.is_valid() for f in edit_forms.values()):
            with transaction.atomic():
                for account in manual:
                    form = edit_forms[account.id]
                    if form.is_empty:
                        continue
                    obj = form.save(commit=False)
                    # Fila de tienda: sin cajero dueño, `author` guarda quién la
                    # digitó.
                    obj.user = None
                    obj.account = account
                    obj.date = day
                    obj.author = request.user
                    obj.save()
            messages.success(request, 'Balance guardado.')
            url = reverse('balance-diario')
            return redirect(f"{url}?date={day:%m/%d/%Y}")
        messages.error(request, 'Revise los valores digitados.')

    rows = services.build_balance(day, user=None, accounts=accounts)
    for row in rows:
        row['editable'] = row['is_manual']
        if row['is_manual']:
            row['form'] = edit_forms[row['account'].id]

    # Resumen por cajero: cuánto efectivo tiene cada uno al cierre. Solo se
    # recorren los cajeros con actividad ese día, y solo las cuentas
    # automáticas: las manuales no son de nadie.
    per_user = []
    for user in services.users_with_activity(day):
        user_rows = services.build_balance(day, user=user, accounts=automatic)
        per_user.append({'user': user, 'total': services.totals_row(user_rows)})

    context = {
        'scope': 'diario',
        'date': day,
        'date_form': date_form,
        'rows': rows,
        'total': services.totals_row(rows),
        'per_user': per_user,
        'line_labels': services.LINE_LABELS,
    }
    return render(request, 'balance/tmpl_diario.html', context)


@login_required
@superuser_required
def mensual(request):
    """Grilla día a día del mes. Solo superusuarios."""
    today = date.today()
    form = BalanceMonthForm(
        request.GET or None,
        initial={'month': today.month, 'year': today.year},
    )
    month, year, user = today.month, today.year, None
    if form.is_bound and form.is_valid():
        month = form.cleaned_data['month']
        year = form.cleaned_data['year']
        user = form.cleaned_data.get('user')

    data = services.build_month(year, month, user=user)

    context = {
        'scope': 'mensual',
        'date': date(year, month, 1),
        'month_form': form,
        'data': data,
        'accounts': data['accounts'],
        'rows': data['account_rows'],
        'total': data['total'],
        'per_user': services.build_month_per_user(year, month),
        'line_labels': services.LINE_LABELS,
    }
    return render(request, 'balance/tmpl_mensual.html', context)


@login_required
@transaction.atomic
def movement_create(request):
    """Registra un movimiento de efectivo. Solo POST."""
    if request.method != 'POST':
        return redirect('balance-personal')

    form = BalanceMovementForm(request.POST, current_user=request.user)
    if form.is_valid():
        movement = form.save(commit=False)
        movement.from_user = request.user
        movement.author = request.user
        movement.save()
        messages.success(request, 'Movimiento registrado.')
        day = movement.date
    else:
        for field, errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else field
            messages.error(request, f"{label}: {' '.join(errors)}")
        day = date.today()

    url = reverse('balance-personal')
    return redirect(f"{url}?date={day:%m/%d/%Y}")


@login_required
@superuser_required
@transaction.atomic
def movement_delete(request, pk):
    """Elimina un movimiento. Es un registro de dinero: solo superusuarios."""
    movement = get_object_or_404(BalanceMovement, pk=pk)
    if request.method != 'POST':
        return redirect('balance-personal')

    day = movement.date
    movement.delete()
    messages.success(request, 'Movimiento eliminado.')
    url = reverse('balance-personal')
    return redirect(f"{url}?date={day:%m/%d/%Y}")
