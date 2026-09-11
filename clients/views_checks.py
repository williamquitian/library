"""Vistas de cheques: alta, edición y borrado desde la ficha del cliente."""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from .forms import CheckForm, CheckUpdateForm, ReturnCheckForm, ReturnedCheckUpdateForm, SearchCheckForm
from .models import Client, Check, ReturnedCheck, ReturnedCheckEvent
from .views import first_url_segment
from companies.models import Company, Manager
from companies.forms import CompanyForm, ManagerForm

DEFAULT_RETURN_FEE = Decimal('35.00')

# Acciones que pueden cobrar fee; en las demás se ignora lo que traiga el
# formulario. El campo se muestra u oculta con esta misma lista.
FEE_ACTIONS = (
    ReturnedCheckEvent.REDEPOSITED,
    ReturnedCheckEvent.CLEARED,
    ReturnedCheckEvent.BOUNCED,
    ReturnedCheckEvent.PAID_CASH,
    ReturnedCheckEvent.PAID_CHECK,
)

def _parse_fee(raw, default=DEFAULT_RETURN_FEE):
    """El fee llega como texto del POST y puede venir vacío."""
    if raw in (None, ''):
        return default
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _parse_event_date(raw):
    """Fecha del evento en MM/DD/YYYY (formato del datepicker), o hoy."""
    if raw:
        for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    return timezone.localdate()

@login_required
def new_check(request, pk):
    client = Client.objects.get(id = pk)
    check_form = CheckForm(prefix='Check')
    manager_form = ManagerForm( prefix='Manager')
    company_form = CompanyForm( prefix='Company')

    if request.method == 'POST':
        modified_data = request.POST.copy()
        company_form = CompanyForm(modified_data, prefix='Company')
        if modified_data['Check-company'] and modified_data['Check-company'].isdigit():
            company = Company.objects.get(pk=modified_data['Check-company'])
            company_form = CompanyForm(request.POST, instance=company, prefix='Company')
        
        if company_form.is_valid(): 
            company = company_form.save()
            modified_data['Check-company'] = company.id

        modified_data['Manager-name'] = modified_data['Check-manager']
        manager_form = ManagerForm(modified_data, prefix='Manager')
        if modified_data['Check-manager'] and modified_data['Check-manager'].isdigit():
            manager = Manager.objects.get(pk=modified_data['Check-manager'])
            modified_data['Manager-name'] = manager.name
            manager_form = ManagerForm( modified_data, instance=manager, prefix='Manager')
        
        if manager_form.is_valid(): 
            manager = manager_form.save()
            modified_data['Check-manager'] = manager.id
             
        check_form = CheckForm(modified_data, prefix='Check', instance=Check(client=client, author=request.user))
        if check_form.is_valid() and company_form.is_valid() and not(isinstance(modified_data['Check-manager'], int) ^ manager_form.is_valid()): 
            check_form = check_form.save(commit=False)
            check_form.client = client
            check_form.author = request.user
            check_form.save()
            messages.success(request, 
                f"Cheque número <b>{check_form.check_number}</b> guardado con exito! <br>"
                f"<b>Valor:</b> ${check_form.amount} <br>"
                f"<b>Comisión ({check_form.comm_percent}%):</b> ${check_form.commission} <br>"
                f"<b>Total a pagar:</b> <h3>${check_form.amount - check_form.commission}</h3>"
            )
            return redirect('view_client', pk=client.pk, tab='checks')   

    context = {
        'client' : client, 
        'check_form' : check_form, 
        'manager_form' : manager_form,
        'company_form' : company_form,
        'app_name':first_url_segment(request),
    }

    return render( request, 'clients/new_check2.html', context )

@login_required
def get_manager_phone(request):
    manager = Manager.objects.get(id = request.GET.get('id'))
    return JsonResponse({'phone': manager.phone}, safe=False)

@login_required
def update_check(request, pk):
    row_check = get_object_or_404(Check, id = pk)    

    if request.method == "POST":   
        modified_data = request.POST.copy()        
        company_form = CompanyForm(request.POST, instance=row_check.company, prefix='Company')
        if company_form.is_valid(): 
            company_form.save()

        modified_data['Manager-name'] = modified_data['Check-manager']
        manager_form = ManagerForm(modified_data, prefix='Manager')
        if modified_data['Check-manager'] and modified_data['Check-manager'].isdigit():
            manager = Manager.objects.get(pk=modified_data['Check-manager'])
            modified_data['Manager-name'] = manager.name
            manager_form = ManagerForm( modified_data, instance=manager, prefix='Manager')
        
        if manager_form.is_valid(): 
            manager = manager_form.save()
            
        check_form = CheckUpdateForm(modified_data, instance=row_check, prefix='Check')        
        if check_form.is_valid() and company_form.is_valid():
            check_form.save()
            messages.success(request, "Cheque modificado con exito!")
            return redirect('view_client', pk=row_check.client_id, tab='checks')   
    else:
        check_form = CheckUpdateForm(instance = row_check, prefix='Check')
        manager_form = ManagerForm(instance = row_check.manager, prefix='Manager')
        company_form = CompanyForm(instance = row_check.company, prefix='Company')

    context = {
        'client' : row_check.client, 
        'check_form' : check_form, 
        'manager_form' : manager_form,
        'company_form' : company_form,
        'app_name':first_url_segment(request),
    }
    return render( request, 'clients/new_check2.html', context )

@login_required
def delete_check(request, pk):
    row_ch = get_object_or_404(Check, id = pk)    
    client_id=row_ch.client_id
    messages.success(request, f"Cheque <b>#{row_ch.check_number}</b> por valor de <b>${row_ch.amount}</b> eliminado correctamente!")
    row_ch.delete()
              
    return redirect('view_client', pk=client_id, tab='checks')



@login_required
def list_returned_check(request):
    if request.method != "POST":
        show_inactive = request.GET.get('inactive') == '1'

        returns = ReturnedCheck.objects.select_related(
            'original_check',
            'original_check__client',
            'original_check__broker',
            'original_check__company',
        ).prefetch_related('events')

        if show_inactive:
            returns = returns.exclude(status__in=ReturnedCheck.OPEN_STATUSES)
        else:
            returns = returns.filter(status__in=ReturnedCheck.OPEN_STATUSES)

        # El form se instancia aquí sólo para que la plantilla pueda emitir su
        # media: los <script> del datepicker tienen que cargarse con la página,
        # no dentro del fragmento del expediente que se inyecta por AJAX (jQuery
        # ejecuta los <script src> inyectados sin respetar el orden y
        # datetimepicker reventaba por cargarse antes que moment.js).
        context = {'returnCheckForm':ReturnCheckForm(),
                   'returns':returns, 'show_inactive':show_inactive }
        return render(request, 'clients/returned_check_list.html', context=context)

@login_required
def new_return_check(request):
    """Alta de una devolución: buscar el cheque y registrarlo como pendiente.

    Todo pasa por esta vista y por POST, sin AJAX: el `step` del botón que se
    apretó dice si toca buscar el cheque o grabar la devolución.
    """
    search_form = SearchCheckForm()
    return_form = None
    check = None

    if request.method == "POST":
        if request.POST.get('step') == 'guardar':
            return_form = ReturnCheckForm(request.POST, request.FILES)
            if return_form.is_valid():
                return _create_return(request, return_form)
            # Falló la validación: hay que repintar la ficha y los criterios,
            # que viajan en el otro <form> y no vienen en este POST.
            check = _posted_check(request)
            search_form = _search_form_for(check)
        else:
            search_form = SearchCheckForm(request.POST)
            if search_form.is_valid():
                check = _find_check(request, search_form.cleaned_data)
                if check is not None:
                    return_form = ReturnCheckForm(initial={
                        'original_check': check,
                        'date_returned': timezone.localdate(),
                    })

    # El media va combinado y siempre, aunque todavía no se haya buscado nada:
    # los <script> del datepicker y del select2 tienen que cargarse con la
    # página. Sumarlos respeta el orden interno de cada uno (moment antes que
    # datetimepicker, select2.full antes que autocomplete_light).
    context = {'searchCheckForm': search_form,
               'returnCheckForm': return_form,
               'check': check,
               'media': SearchCheckForm().media + ReturnCheckForm().media}
    return render(request, 'clients/returned_check_new_page.html', context=context)


def _find_check(request, criteria):
    """El cheque de la búsqueda, o None dejando dicho por qué no sirve.

    Cliente + número + valor es el UNIQUE de `Check`, así que el filtro no
    puede devolver más de una fila.
    """
    check = Check.objects.select_related('client', 'company', 'manager').filter(
        client=criteria['client'],
        check_number=criteria['check_number'],
        amount=criteria['amount'],
    ).first()

    if check is None:
        messages.error(request, "No se encontró ningún cheque con esos datos.")
        return None

    # `original_check` es OneToOne: un cheque tiene un solo expediente.
    if ReturnedCheck.objects.filter(original_check=check).exists():
        messages.error(
            request,
            f"El cheque <b>#{check.check_number}</b> ya tiene una devolución "
            f'registrada. <a href="{reverse("list_returned_check")}">Ver expedientes</a>.'
        )
        return None

    return check


def _posted_check(request):
    """El cheque que venía en el formulario de alta, para repintar la ficha."""
    return Check.objects.select_related('client', 'company', 'manager').filter(
        pk=request.POST.get('original_check')).first()


def _search_form_for(check):
    """Deja la tarjeta de búsqueda con los criterios del cheque ya encontrado."""
    if check is None:
        return SearchCheckForm()
    return SearchCheckForm(initial={'client': check.client,
                                    'check_number': check.check_number,
                                    'amount': check.amount})


def _create_return(request, form):
    """Graba el expediente en pendiente y su primer evento.

    El fee del primer evento va en 0.00: los fees se cobran en el desenlace, no
    al registrar la devolución (igual que la historia sembrada en la 0043).
    """
    with transaction.atomic():
        returned_check = form.save(commit=False)
        returned_check.author = request.user
        returned_check.status = ReturnedCheck.STATUS_PENDING
        if returned_check.file_path:
            returned_check.file_name = str(returned_check.file_path)
        returned_check.save()

        ReturnedCheckEvent.objects.create(
            returned_check=returned_check,
            event_type=ReturnedCheckEvent.RETURNED,
            date=returned_check.date_returned,
            fee=Decimal('0.00'),
            comment=form.cleaned_data['comment'],
            author=request.user,
        )

    check = returned_check.original_check
    messages.success(
        request,
        f"Cheque <b>#{check.check_number}</b> por valor de <b>${check.amount}</b> "
        "registrado como devuelto."
    )
    return redirect('list_returned_check')

@login_required
def update_return_check(request, pk):
    """Expediente completo: historial arriba y un solo formulario abajo.

    El POST hace todo lo que antes estaba repartido entre `update_return_check`,
    `redeposit_return_check` y `resolve_return_check`: guarda la imagen y la
    observación y, si se eligió una acción, registra el desenlace.
    """
    returned_check = get_object_or_404(
        ReturnedCheck.objects.select_related('original_check', 'original_check__client'),
        id=pk,
    )

    if request.method != "POST":
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            return JsonResponse({'error': 'Invalid non-AJAX request'}, status=400)

        form = ReturnedCheckUpdateForm(
            returned_check=returned_check,
            initial={'date': timezone.localdate(), 'fee': DEFAULT_RETURN_FEE},
        )
        html_content = render_to_string(
            'clients/returned_check_update.html',
            {'returned_check': returned_check, 'returnCheckForm': form,
             'fee_actions': list(FEE_ACTIONS)},
            request=request
        )
        return JsonResponse({'html': html_content})

    action = request.POST.get("outcome") or ""
    event_date = _parse_event_date(request.POST.get("date"))
    comment = request.POST.get("comment") or ""
    attached = _attach_file(request, returned_check)

    if not action:
        if comment or attached:
            ReturnedCheckEvent.objects.create(
                returned_check=returned_check,
                event_type=ReturnedCheckEvent.COMMENT,
                date=event_date,
                fee=Decimal('0.00'),
                comment=comment or "Imagen del cheque actualizada.",
                author=request.user,
            )
            messages.success(request, "Observación guardada.")
        return redirect('list_returned_check')

    if not returned_check.is_open:
        messages.error(request, "Este expediente ya está cerrado.")
        return redirect('list_returned_check')

    if action not in ReturnedCheckEvent.ACTIONS_BY_STATUS.get(returned_check.status, []):
        messages.error(request, "Acción no válida para el estado del expediente.")
        return redirect('list_returned_check')

    # El fee solo se cobra en las acciones que lo llevan; en el resto se ignora
    # lo que venga del formulario. Casilla vacía = sin fee.
    fee = (
        _parse_fee(request.POST.get("fee"), Decimal('0.00'))
        if action in FEE_ACTIONS else Decimal('0.00')
    )

    with transaction.atomic():
        if action == ReturnedCheckEvent.REDEPOSITED:
            _redeposit(request, returned_check, event_date, fee, comment)
        else:
            _resolve(request, returned_check, action, event_date, fee, comment)

    return redirect('list_returned_check')


def _attach_file(request, returned_check):
    """Guarda la imagen del cheque. Devuelve True si quedó grabada."""
    file_path = request.FILES.get("file_path")
    if not file_path:
        return False

    returned_check.file_path = file_path
    returned_check.file_name = str(file_path)
    try:
        returned_check.full_clean()
        returned_check.save()
        return True
    except ValidationError as e:
        for field, field_errors in e.message_dict.items():
            for error in field_errors:
                messages.error(request, f"Error en '{field}': {error}")
        # Sin esto el archivo inválido seguía en la instancia y el `save()` del
        # desenlace lo terminaba grabando igual.
        returned_check.refresh_from_db(fields=['file_path', 'file_name'])
        return False


def _redeposit(request, returned_check, event_date, fee, comment):
    """El cheque se vuelve a mandar al banco. Queda esperando resultado."""
    returned_check.status = ReturnedCheck.STATUS_REDEPOSITED
    returned_check.save(update_fields=['status', 'updated_at'])

    ReturnedCheckEvent.objects.create(
        returned_check=returned_check,
        event_type=ReturnedCheckEvent.REDEPOSITED,
        date=event_date,
        fee=fee,
        comment=comment,
        author=request.user,
    )
    messages.success(request, "Cheque marcado como re-depositado.")


def _resolve(request, returned_check, outcome, event_date, fee, comment):
    """Registra el desenlace: pasó, rebotó otra vez, pagó en efectivo o se perdió."""
    if outcome == ReturnedCheckEvent.BOUNCED:
        # Vuelve a pendiente y suma otro fee al saldo del cliente.
        returned_check.status = ReturnedCheck.STATUS_PENDING
        returned_check.save(update_fields=['status', 'updated_at'])
        note = "Rebote registrado. El cheque sigue pendiente."

    elif outcome == ReturnedCheckEvent.CLEARED:
        # El cheque terminó pagando: no entra el monto, solo el fee de penalidad.
        returned_check.status = ReturnedCheck.STATUS_RECOVERED
        returned_check.date_payoff = event_date
        returned_check.fees = fee
        returned_check.save(update_fields=['status', 'date_payoff', 'fees', 'updated_at'])
        note = "Re-depósito exitoso. Expediente cerrado."

    elif outcome in (ReturnedCheckEvent.PAID_CASH, ReturnedCheckEvent.PAID_CHECK):
        _build_reversal_check(request.user, returned_check, fee, event_date)
        returned_check.status = ReturnedCheck.STATUS_RECOVERED
        returned_check.date_payoff = event_date
        returned_check.fees = fee
        returned_check.save()
        note = "Pago del cliente registrado. Expediente cerrado."

    else:  # written_off
        returned_check.status = ReturnedCheck.STATUS_WRITTEN_OFF
        returned_check.save(update_fields=['status', 'updated_at'])
        note = "Expediente cerrado como pérdida."

    ReturnedCheckEvent.objects.create(
        returned_check=returned_check, event_type=outcome, date=event_date,
        fee=fee, comment=comment, author=request.user)

    if outcome == ReturnedCheckEvent.CLEARED and fee > 0:
        _register_fee_income(request.user, returned_check, fee, event_date)

    messages.success(request, note)


def _build_reversal_check(user, returned_check, fee, event_date):
    """Clona el cheque original en negativo por (monto + fees acumulados).

    Lo leen los reportes vía `reversal_check`
    (reports/templates/reports/tmpl_rpt_chk.html).
    """
    original = returned_check.original_check
    total_fees = returned_check.total_fees + fee

    reversal = Check.objects.get(pk=original.pk)
    reversal.pk = None
    reversal._state.adding = True
    reversal.amount = (original.amount + total_fees) * -1
    reversal.created_at = timezone.now()
    reversal.author = user
    reversal.comm_percent = Decimal('0.0')
    reversal.save()

    # `Check.save()` recalcula la comisión con math.floor, y con un monto
    # negativo con centavos deja una comisión espuria (-1070.25 -> 0.75).
    # Se fuerza a cero sin volver a pasar por save().
    Check.objects.filter(pk=reversal.pk).update(commission=Decimal('0.00'))
    reversal.commission = Decimal('0.00')

    returned_check.reversal_check = reversal
    return reversal


def _register_fee_income(user, returned_check, fee, event_date):
    """Ingreso de caja por el fee cobrado, en la cuenta del broker del cheque."""
    from balance.models import BalanceAccount, BalanceMovement

    broker_mo = returned_check.original_check.broker
    account = BalanceAccount.objects.filter(broker_moneyorder=broker_mo).first()

    BalanceMovement.objects.create(
        movement_type=BalanceMovement.CHECK_FEE,
        date=event_date,
        amount=fee,
        from_user=user,
        account=account,
        description=f"Fee cheque devuelto #{returned_check.original_check.check_number}",
        author=user,
    )


@login_required
def view_return_check_file(request, pk):
    check = get_object_or_404(ReturnedCheck, id=pk)
    return render(request, 'clients/view_returned_check.html', {'doc' : check})
