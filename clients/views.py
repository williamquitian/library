from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Value, Count, Sum, OuterRef, IntegerField, DecimalField, CharField, Subquery, DateField
from django.db.models.functions import Concat
from datetime import date, datetime, timedelta
from django.utils.formats import date_format
from django.http import JsonResponse
from django.db.models.functions import Coalesce
from django.utils.timezone import localtime
from .forms import ClientForm, CommentForm, DocumentForm, SendMoneyForm, SendPackageForm
from .forms import MoneyOrderForm, SendMoneyReportForm
from .models import Client, Document, FidelityCard, SendMoney, MoneyOrder, Profession
from companies.models import Company
from dal import autocomplete
from django.utils import timezone
import pytz


@login_required
def list_clients(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if is_mobile(user_agent):
        return redirect('mobile_search_client')  
    
    return render(request, 'clients/tmpl_list.html', context={'app_name':first_url_segment(request)})

@login_required
def list_clients_ajax(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        today = date.today()
        target_date = today - timedelta(days=30)

        count_sm_subquery = SendMoney.objects.filter(
            client=OuterRef('pk'),
            creation_date__gte=target_date
        ).values('client').annotate(
            count=Count('id')
        ).values('count')[:1]

        sum_sm_subquery = SendMoney.objects.filter(
            client=OuterRef('pk'),
            creation_date__gte=target_date
        ).values('client').annotate(
            total=Sum('amount')
        ).values('total')[:1]

        count_mo_subquery = MoneyOrder.objects.filter(
            client=OuterRef('pk'),
            created_at__gte=target_date
        ).values('client').annotate(
            count=Count('id')
        ).values('count')[:1]

        sum_mo_subquery = MoneyOrder.objects.filter(
            client=OuterRef('pk'),
            created_at__gte=target_date
        ).values('client').annotate(
            total=Sum('amount')
        ).values('total')[:1]

        latest_sm_date_subquery = SendMoney.objects.filter(
            client=OuterRef('pk')
        ).order_by('-creation_date').values('creation_date')[:1]
        
        clients = Client.objects.annotate(
            name=Concat('first_name', Value(' '), 'last_name'),
            count_sm=Coalesce(Subquery(count_sm_subquery, output_field=IntegerField()), 0),
            sum_sm=Concat(Value('$'), Coalesce(Subquery(sum_sm_subquery, output_field=DecimalField()), 0, output_field=DecimalField()), output_field=CharField()),
            count_mo=Coalesce(Subquery(count_mo_subquery, output_field=IntegerField()), 0),
            sum_mo=Concat(Value('$'), Coalesce(Subquery(sum_mo_subquery, output_field=DecimalField()), 0, output_field=DecimalField()), output_field=CharField()),
            last_sm_date=Subquery(latest_sm_date_subquery, output_field=DateField()),
            doc_count=Count('documents')
        ).values(
            'id', 'name', 'phone', 'date_of_birth','country__name', 'doc_count',
            'last_sm_date', 'count_sm', 'sum_sm', 'count_mo', 'sum_mo'
        )

        formatted_data = []
        for p in clients:
            p['date_of_birth'] = p['date_of_birth'].strftime('%m/%d/%Y') if p['date_of_birth'] else None
            p['last_sm_date'] = utc_to_local(p['last_sm_date']).strftime('%m/%d/%Y') if p['last_sm_date'] else None
            formatted_data.append(p)

        return JsonResponse({'data': list(formatted_data)})

@login_required
def create_client(request):
    form = ClientForm()
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            new_client = form.save()
            return redirect('view_client', pk=new_client.id, tab='details')
    
    context = {'form' : form, 'app_name':first_url_segment(request)}
    return render(request, 'clients/create_client.html', context=context)

@login_required
def update_client(request, pk):
    row_client = get_object_or_404(Client, id = pk)
    if request.method == "POST":
        form = ClientForm(request.POST, instance=row_client)    
        changes = []
        for field in form.changed_data:
            old_value = form.initial[field]
            new_value = request.POST[field]
            changes.append(f" ({form.fields[field].label}: {old_value} -> {new_value}) ")
        if form.is_valid():            
            form.save()
            if changes:
                change_log = "\n".join(changes)
                row_client.log_modification(request.user, change_log)
            return redirect('view_client', pk=row_client.pk, tab='details')
    else:
        form = ClientForm(instance=row_client)
    
    context = {'form' : form, 'app_name':first_url_segment(request)}
    return render(request, 'clients/create_client.html', context=context)

@login_required
def view_client(request, pk, tab):
    client = get_object_or_404(Client, pk=pk)
    comments = client.comments.all().order_by('-created_at')
    documents = client.documents.all().order_by('-creation_date')
    sendmoney = client.sendmoney.all().order_by('-creation_date')
    sendpackage = client.sendpackage.all().order_by('-creation_date')
    moneyorder = client.moneyorder.all().order_by('-created_at')
    fidelitycards = FidelityCard.objects.filter(client=client.id).annotate(count=Count('card_num'))
   
    comment_form = CommentForm()
    context = {
        'client' : client, 
        'comment_form':comment_form, 
        'comments':comments, 
        'documents':documents,
        'sendmoney':sendmoney,
        'sendpackage':sendpackage,
        'moneyorder':moneyorder,
        'fidelitycards':fidelitycards,
        'tab': tab,
        'app_name':first_url_segment(request)
        }
    return render(request, 'clients/view_client.html', context=context)

@login_required
def add_comment(request, pk, tab):
    client = Client.objects.get(id = pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.client = client
            comment.author = request.user
            comment.save()
        
    return redirect('view_client', pk=client.pk, tab=tab)

@login_required
def upload_document(request, pk):
    client = Client.objects.get(id = pk)
    document_form = DocumentForm()
    
    if request.method == 'POST':
        document_form = DocumentForm(request.POST, request.FILES)
        if document_form.is_valid():
            doc = document_form.save(commit=False)
            doc.client = client
            doc.author = request.user
            doc.save()
            messages.success(request, "Documento agregado con exito!")
            return redirect('view_client', pk=client.pk, tab='documents')
        
    context = {'client' : client, 'document_form':document_form, 'app_name':first_url_segment(request)}
    return render(request, 'clients/upload_document.html', context=context)

@login_required
def view_document(request, pk):
    doc = Document.objects.get(id = pk)
    context = {'doc' : doc, 'app_name':first_url_segment(request)}
    return render(request, 'clients/view_document.html', context=context)

@login_required
def new_transfer_package(request, pk):
    client = Client.objects.get(id = pk)
    sendmoney_form = SendMoneyForm(client=client, prefix='Money')
    sendpackage_form = SendPackageForm(prefix='Package')
    
    if request.method == 'POST':
        if 'Money-amount' in request.POST:
            sendmoney_form = SendMoneyForm(request.POST, client=client, author=request.user, prefix='Money')
            if sendmoney_form.is_valid():                
                sendmoney = sendmoney_form.save(commit=False)

                if sendmoney_form.cleaned_data['new_card'] and sendmoney.fidelitycard.id == 0:
                    fidelitycard = FidelityCard.objects.filter(card_num = sendmoney_form.cleaned_data['new_card'])
                    if(fidelitycard):
                        sendmoney.fidelitycard = fidelitycard.first()
                    else:
                        sendmoney.fidelitycard = FidelityCard.objects.create(author=request.user, card_num=sendmoney_form.cleaned_data['new_card'])
               
                sendmoney.client = client
                sendmoney.author = request.user                
                sendmoney.save()
                messages.success(request, "Envío de dinero guardado con exito!")
                return redirect('view_client', pk=client.pk, tab='packages')              

        if 'submit-package' in request.POST:
            sendpackage_form = SendPackageForm(request.POST, prefix='Package')
            if sendpackage_form.is_valid():
                sendpackage = sendpackage_form.save(commit=False)
                sendpackage.client = client
                sendpackage.author = request.user
                sendpackage.save()
                messages.success(request, "Envío de packete guardado con exito!")
                return redirect('view_client', pk=client.pk, tab='packages')   
    
    context = {
        'client' : client, 
        'sendmoney_form':sendmoney_form, 
        'sendpackage_form':sendpackage_form, 
        'app_name':first_url_segment(request)
    }
    return render(request, 'clients/new_transfer_package.html', context=context)

@login_required
def new_moneyorder(request, pk):
    client = Client.objects.get(id = pk)
    moneyorder_form = MoneyOrderForm()
    
    if request.method == "POST":
        moneyorder_form = MoneyOrderForm(request.POST)
        if moneyorder_form.is_valid():
            moneyorder = moneyorder_form.save(commit=False)
            moneyorder.client = client
            moneyorder.author = request.user
            moneyorder.save()
            messages.success(request, "Money Order guardada con exito!")
            return redirect('view_client', pk=client.pk, tab='moneyorders')

    context = {'client' : client, 'moneyorder_form' : moneyorder_form, 'app_name':first_url_segment(request)}
    return render(request, 'clients/new_moneyorder.html', context=context)

def first_url_segment(request):
    path = request.path.strip("/").split("/")
    return path[0] if path else ""

def utc_to_local(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:  # naive datetime
        # explicitly mark it as UTC
        dt = dt.replace(tzinfo=pytz.UTC)

    return localtime(dt)

@login_required
def search_clients(request):
    """Sugerencias para el autocomplete de jQuery UI.

    Devuelve la lista de objetos {label, value, id} que espera el widget: se
    busca palabra por palabra para que "JUAN PEREZ" encuentre al cliente aunque
    el nombre y el apellido estén en columnas distintas.
    """
    term = request.GET.get('term', '')

    qs = Client.objects.all()
    for word in term.split():
        qs = qs.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word))

    results = [
        {'id': c.id, 'label': str(c), 'value': str(c)}
        for c in qs.order_by('first_name', 'last_name')[:20]
    ]

    return JsonResponse(results, safe=False)

class ProfessionAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Profession.objects.none()

        qs = Profession.objects.all().order_by('name')

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs
    
class ClientAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Client.objects.none()

        qs = Client.objects.all()

        # Palabra por palabra, para que "JUAN PEREZ" encuentre al cliente aunque
        # el nombre y el apellido estén en columnas distintas.
        for word in (self.q or '').split():
            qs = qs.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word))

        return qs.order_by('first_name', 'last_name')

class CompanyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Company.objects.none()

        qs = Company.objects.all().order_by('name')

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs
    
@login_required
def report_clients(request):
    form = SendMoneyReportForm(initial={'author': request.user})

    #context = {'app_name':first_url_segment(request), 'form': form, 'sendmoney':sendmoney}
    return render(request, 'clients/report_clients.html', context={'app_name':first_url_segment(request), 'form':form})

@login_required
def report_send_money_ajax(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        columns = ['client__first_name', 'creation_date', 'country__name', 'author__username', 'broker_number', 'amount']
        
        orderColumn = 'creation_date'
        if request.GET.get('order[0][column]'):
            orderColumn = request.GET.get('order[0][column]')
            if int(orderColumn) > 5:
                orderColumn = 5
            orderColumn = columns[ int(orderColumn) ]

        if request.GET.get('order[0][dir]') == "desc":
            orderColumn = "-" + orderColumn

        data = []
        total_amount = [0,0,0,0]
        count_total = [0,0,0,0]
        total_cancel = [0,0,0,0]
        count_cancel = [0,0,0,0]
        total_paid = [0,0,0,0]
        count_paid = [0,0,0,0]
        count_mo = [0,0,0,0]
        total = [0,0,0,0]

        try:
            author = request.user.id
            if request.GET.get('id_author'):
                author = request.GET.get('id_author')
            filter_date = datetime.strptime(request.GET.get('id_creation_date'), '%m/%d/%Y').date()

            start_of_day = timezone.make_aware(datetime(filter_date.year, filter_date.month, filter_date.day, 0, 0, 0))
            end_of_day = timezone.make_aware(datetime(filter_date.year, filter_date.month, filter_date.day, 23, 59, 59, 999999))
            
            sendmoney_list = SendMoney.objects.filter(creation_date__range=(start_of_day, end_of_day))
            moneyorder_list = MoneyOrder.objects.filter(created_at__range=(start_of_day, end_of_day))
            if author != '0':
                sendmoney_list = sendmoney_list.filter(author = author)
                moneyorder_list = moneyorder_list.filter(author = author)
            sendmoney_list = sendmoney_list.order_by(orderColumn)

            for sm in sendmoney_list:
                row_amount = ['', '', '', '']                
                row_amount[sm.broker_id-1] = f"${sm.amount:,.2f}"
                if sm.amount > 0:
                    count_total[sm.broker_id-1] += 1
                    total_amount[sm.broker_id-1] += sm.amount
                else:
                    resultsNegative = SendMoney.objects.filter(broker_number=sm.broker_number, broker_id=sm.broker_id)
                    if resultsNegative.count() == 1:
                        count_paid[sm.broker_id-1] += 1
                        count_total[sm.broker_id-1] += 1
                        total_paid[sm.broker_id-1] += sm.amount
                    elif resultsNegative.count() == 2:                        
                        resultsCanceled = SendMoney.objects.filter(broker_number=sm.broker_number, broker_id=sm.broker_id, amount__gt = 0)
                        if date_format(localtime(resultsCanceled.first().creation_date), format='m/d/Y', use_l10n=False) == request.GET.get('id_creation_date'):
                            count_total[sm.broker_id-1] -= 1
                        else:
                            count_cancel[sm.broker_id-1] += 1
                            total_cancel[sm.broker_id-1] += sm.amount

                data.append({
                    'broker_number': '-' if sm.broker_number== 0 else sm.broker_number,
                    'country': sm.country.name,
                    'author': sm.author.username,
                    'client': sm.client.first_name + " " + sm.client.last_name,
                    'creation_date': date_format(localtime(sm.creation_date), format='m/d/Y h:i a', use_l10n=False),
                    'intermex':row_amount[0],
                    'viamericas':row_amount[1],
                    'ria':row_amount[2],
                    'moneygram':row_amount[3],
                })

                count_mo=[
                    moneyorder_list.filter(broker_moneyorder = 2).count(), 
                    moneyorder_list.filter(broker_moneyorder = 2).aggregate(Sum('amount'))['amount__sum'] if moneyorder_list.filter(broker_moneyorder = 2).count() > 0 else 0,
                    moneyorder_list.filter(broker_moneyorder = 1).count(),                     
                    moneyorder_list.filter(broker_moneyorder = 1).aggregate(Sum('amount'))['amount__sum'] if moneyorder_list.filter(broker_moneyorder = 1).count() > 0 else 0,
                ]
        except Exception:
            pass
        
        for index, item in enumerate(total_amount):
            total[index] = total_amount[index] + total_cancel[index] + total_paid[index]
            if index == 0:
                total[0] += count_mo[1]
            if index == 1:
                total[1] += count_mo[3]
            
            total[index] = f"${total[index]:,.2f}"
            total_amount[index] = f"${total_amount[index]:,.2f}"
            total_cancel[index] = f"${total_cancel[index]:,.2f}"
            total_paid[index] = f"${total_paid[index]:,.2f}"

        count_mo[1] = f"${count_mo[1]:,.2f}"
        count_mo[3] = f"${count_mo[3]:,.2f}"

        return JsonResponse({
            'data': list(data), 
            "total_amount": total_amount,
            "count_total":count_total,
            "count_paid": count_paid,
            "total_cancel": total_cancel,
            "total_paid":total_paid,
            "count_cancel":count_cancel,
            "count_mo":count_mo,
            "total":total
        }, safe=False)

@login_required
def report_money_order_ajax(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        columns = ['client__first_name', 'created_at', 'broker_moneyorder__broker_moneyorder_name', 'author__username', 'amount']

        orderColumn = 'created_at'
        if request.GET.get('order[0][column]'):
            orderColumn = request.GET.get('order[0][column]')
            orderColumn = columns[ int(orderColumn) ]

        if request.GET.get('order[0][dir]') == "desc":
            orderColumn = "-" + orderColumn

        data = []
        total_amount = 0
        count_mo = 0

        try:
            author = request.user.id
            if request.GET.get('id_author'):
                author = request.GET.get('id_author')
            filter_date = datetime.strptime(request.GET.get('id_creation_date'), '%m/%d/%Y').date()

            start_of_day = timezone.make_aware(datetime(filter_date.year, filter_date.month, filter_date.day, 0, 0, 0))
            end_of_day = timezone.make_aware(datetime(filter_date.year, filter_date.month, filter_date.day, 23, 59, 59, 999999))
            
            moneyorder_list = MoneyOrder.objects.filter(created_at__range=(start_of_day, end_of_day))
            if author != '0':
                moneyorder_list = moneyorder_list.filter(author = author)
            moneyorder_list = moneyorder_list.order_by(orderColumn)

            for mo in moneyorder_list:
                total_amount += mo.amount
                count_mo += 1
                data.append({
                    'amount': "$" + str(mo.amount),
                    'broker': mo.broker_moneyorder.broker_moneyorder_name,
                    'author': mo.author.username,
                    'client': mo.client.first_name + " " + mo.client.last_name,
                    'created_at': date_format(localtime(mo.created_at), format='DATETIME_FORMAT', use_l10n=False),
                })
        except Exception:
            pass

        return JsonResponse({'data': list(data), "total_amount": total_amount, "count_mo": count_mo}, safe=False)
    
def is_mobile(user_agent: str):
    return any(m in user_agent for m in ['Mobile', 'Android', 'iPhone', 'Opera Mini', 'IEMobile'])

@login_required
def mobile_search_client(request):   
    query = request.GET.get('q', '')
    page_obj = None

    if query:
        clients = Client.objects.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(
            Q(full_name__icontains=query)
        ).order_by('first_name', 'last_name')

        paginator = Paginator(clients, 10) 
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    return render(request, 'clients/tmpl_search_client.html', {
        'query': query,
        'page_obj': page_obj
    })

@login_required
def mobile_upload_document(request, pk):
    client = Client.objects.get(id = pk)
    document_form = DocumentForm()
    
    if request.method == 'POST':
        document_form = DocumentForm(request.POST, request.FILES)
        if document_form.is_valid():
            doc = document_form.save(commit=False)
            doc.client = client
            doc.author = request.user
            doc.save()
            messages.success(request, "Documento agregado con exito!")
            return redirect('mobile_upload_document', pk=client.pk)
        
    context = {'client' : client, 'document_form':document_form}
    return render(request, 'clients/mobile_upload_document.html', context=context)


@login_required
def delete_sendmoney(request, pk):
    row_sm = get_object_or_404(SendMoney, id = pk)    
    client_id=row_sm.client_id
    row_sm.delete()
              
    return redirect('view_client', pk=client_id, tab='packages')

'''@login_required
def company_detail_ajax(request):
    company_id = request.GET.get('id')

    if not company_id:
        return JsonResponse({'error': 'No ID'}, status=400)

    company = get_object_or_404(Company, id = company_id)

    data = {
        'id': company.id,
        'name': company.name,
        'color': company.color,
        'account_number': company.account_number if company.city else "",
        'city': company.city.city_with_state if company.city else "",
        'comment': company.comment if company.city else "",
        'checks': [
            {
                'amount': check.amount,
                'check_number': check.check_number,
                'broker': check.broker.broker_moneyorder_name,
                'author': check.author.username,
                'manager': check.manager.name,
                'id_manager': check.manager.id,
                'phone': check.manager.phone,
                'created_at': date_format(
                    timezone.localtime(check.created_at),
                    'SHORT_DATETIME_FORMAT'
                )
            }
        for check in company.checks.all().order_by('-created_at')
        ]
    }

    return JsonResponse(data)'''
