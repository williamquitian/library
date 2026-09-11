from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .forms import ReportsForm
from datetime import date, datetime
from clients.models import Sum, Count, MoneyOrder, Check, SendMoney, Broker, BrokerMoneyOrder
from django.utils.timezone import make_aware

# Bucket de `summary` que le toca a cada método de pago de `SendMoney`. Un método
# desconocido cae en efectivo a propósito, misma regla que
# `balance.services.SEND_MONEY_CASHLESS`: el default del modelo es `cash`, y mandar
# plata a un bucket que no existe la borraría del reporte.
SEND_MONEY_BUCKETS = {
    'cash': 'send_moneys_cash',
    'card': 'send_moneys_card',
    'vialink': 'send_moneys_vialink',
}

def _rendered_form(start_date, end_date, author):
    """Form sin ligar para renderizar.

    El JS del datepicker espera el valor en formato backend (YYYY-MM-DD). Un
    form ligado re-renderiza la cadena cruda del GET ("09/03/2026") y la
    librería la corrompe al mostrarla, así que se devuelve uno sin ligar con
    los valores ya parseados.
    """
    return ReportsForm(initial={
        'start_date': start_date, 'end_date': end_date, 'author': author,
    })


@login_required
def reports_sm(request):
    form = ReportsForm(request.GET or None, initial={'author': request.user})
    sendmoneys = SendMoney.objects.all()
    filters = {}
    
    if form.is_bound and form.is_valid():
        filters["author"] = form.cleaned_data.get('author')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
    else:
        filters["author"] = request.user
        start_date = date.today()
        end_date = date.today()
    
    filters["start_dt"] = make_aware(datetime.combine(start_date, datetime.min.time()))
    filters["end_dt"] = make_aware(datetime.combine(end_date, datetime.max.time()))
    sendmoneys = sendmoneys.filter(creation_date__range=( filters["start_dt"], filters["end_dt"]))
    if filters["author"]:
        sendmoneys = sendmoneys.filter(author=filters["author"])

    form = _rendered_form(start_date, end_date, filters["author"])
    return render(request, 'reports/tmpl_rpt_sm.html', context={'form':form, 'sendmoneys':sendmoneys, 'summary':summary_report(filters)})

@login_required
def reports_chk(request):
    form = ReportsForm(request.GET or None, initial={'author': request.user})
    checks = Check.objects.all()
    filters = {}
    
    if form.is_bound and form.is_valid():
        filters["author"] = form.cleaned_data.get('author')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
    else:
        filters["author"] = request.user
        start_date = date.today()
        end_date = date.today()
    
    filters["start_dt"] = make_aware(datetime.combine(start_date, datetime.min.time()))
    filters["end_dt"] = make_aware(datetime.combine(end_date, datetime.max.time()))
    checks = checks.filter(created_at__range=( filters["start_dt"], filters["end_dt"]))
    if filters["author"]:
        checks = checks.filter(author=filters["author"])

    form = _rendered_form(start_date, end_date, filters["author"])
    return render(request, 
                  'reports/tmpl_rpt_chk.html', 
                  context={
                      'form':form, 
                      'checks':checks, 
                      'summary':summary_report(filters), 
                      'bottom_line':bottom_line(filters)
                      }
                  )

@login_required
def reports_mo(request):
    form = ReportsForm(request.GET or None, initial={'author': request.user, 'start_date': date.today(), 'end_date': date.today()})
    moneyorders = MoneyOrder.objects.all()
    filters = {}
    
    if form.is_bound and form.is_valid():
        filters["author"] = form.cleaned_data.get('author')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
    else:
        filters["author"] = request.user
        start_date = date.today()
        end_date = date.today()
    
    filters["start_dt"] = make_aware(datetime.combine(start_date, datetime.min.time()))
    filters["end_dt"] = make_aware(datetime.combine(end_date, datetime.max.time()))
    moneyorders = moneyorders.filter(created_at__range=( filters["start_dt"], filters["end_dt"]))
    if filters["author"]:
        moneyorders = moneyorders.filter(author=filters["author"])

    form = _rendered_form(start_date, end_date, filters["author"])
    return render(request, 'reports/tmpl_rpt_mo.html', context={'form':form, 'moneyorders':moneyorders, 'summary':summary_report(filters)})

def summary_report(filters):
    summary = {"checks":{}, "money_orders":{},"send_moneys":{}, "send_moneys_cash":{},"send_moneys_card":{},"send_moneys_vialink":{}, "sm_canceled":{},"sm_paid":{},"total":{}}
    checks = Check.objects.filter(created_at__range=( filters["start_dt"], filters["end_dt"]))
    moneyorders = MoneyOrder.objects.filter(created_at__range=( filters["start_dt"], filters["end_dt"]))
    sendmoneys = SendMoney.objects.filter(creation_date__range=( filters["start_dt"], filters["end_dt"]))

    if filters["author"]:
        checks = checks.filter(author=filters["author"])
        moneyorders = moneyorders.filter(author=filters["author"])
        sendmoneys = sendmoneys.filter(author=filters["author"])

    for broker in Broker.objects.all():
        indx = broker.broker_name.lower().replace(" ", "")
        summary["send_moneys"][indx] = {'sum': 0, 'count': 0}
        summary["sm_canceled"][indx] = {'sum': 0, 'count': 0}
        summary["sm_paid"][indx] = {'sum': 0, 'count': 0}
        
        sendmoneys_tmp = sendmoneys.filter(broker__broker_name=broker.broker_name, amount__gt=0)
        summary["send_moneys"][indx] = sendmoneys_tmp.aggregate(sum=Sum('amount'), count=Count('id'))

        sendmoneys_cash = sendmoneys.filter(broker__broker_name=broker.broker_name, payment_method='cash', amount__gt=0)
        summary["send_moneys_cash"][indx] = sendmoneys_cash.aggregate(sum=Sum('amount'), count=Count('id'))

        sendmoneys_card = sendmoneys.filter(broker__broker_name=broker.broker_name, payment_method='card', amount__gt=0)
        summary["send_moneys_card"][indx] = sendmoneys_card.aggregate(sum=Sum('amount'), count=Count('id'))

        sendmoneys_vialink = sendmoneys.filter(broker__broker_name=broker.broker_name, payment_method='vialink', amount__gt=0)
        summary["send_moneys_vialink"][indx] = sendmoneys_vialink.aggregate(sum=Sum('amount'), count=Count('id'))

        sendmoneys_canceled = sendmoneys.filter(broker__broker_name=broker.broker_name, amount__lt=0)

        for sm in sendmoneys_canceled:
            count_sm = SendMoney.objects.filter(broker_number=sm.broker_number, broker=sm.broker).order_by('creation_date')
            # Los agregados de arriba filtran amount__gt=0, así que la cancelación se
            # resta aquí a mano, y le toca al bucket de SU método de pago: cancelar un
            # envío con tarjeta no saca efectivo del cajón. `sum` viene en None cuando
            # ese método no tuvo envíos positivos en el rango.
            canceled_bucket = summary[SEND_MONEY_BUCKETS.get(sm.payment_method, "send_moneys_cash")][indx]

            if count_sm.count() == 2:
                time_difference = count_sm[1].creation_date - count_sm[0].creation_date
                hours_diff = time_difference.total_seconds() / 3600
                if hours_diff < 23:
                    summary["send_moneys_cash"][indx]["count"] -= 1
                else:    
                    summary["sm_canceled"][indx]["count"] += 1
                    summary["sm_canceled"][indx]["sum"] += sm.amount

                canceled_bucket["sum"] = (canceled_bucket["sum"] or 0) + sm.amount
            elif count_sm.count() == 1:
                summary["sm_paid"][indx]["count"] += 1
                summary["send_moneys_cash"][indx]["count"] += 1
                summary["sm_paid"][indx]["sum"] += sm.amount
                
            '''if sendmoneys_tmp.filter(broker_number=sm.broker_number):
                summary["send_moneys"][indx]["count"] -= 1
                summary["send_moneys"][indx]["sum"] += sm.amount
            else:
                sm_prev_days = SendMoney.objects.filter(creation_date__lt=( filters["start_dt"]))
                if filters["author"]:
                    sm_prev_days = sm_prev_days.filter(author=filters["author"])
                sm_prev_days = sm_prev_days.filter(broker__broker_name=broker.broker_name, amount__gt=0, broker_number=sm.broker_number)

                if sm_prev_days:
                    summary["sm_canceled"][indx]["count"] += 1
                    summary["sm_canceled"][indx]["sum"] += sm.amount
                else:
                    summary["sm_paid"][indx]["count"] += 1
                    summary["send_moneys"][indx]["count"] += 1
                    summary["sm_paid"][indx]["sum"] += sm.amount'''

    for broker_mo in BrokerMoneyOrder.objects.all():
        indx = broker_mo.broker_moneyorder_name.lower().replace(" ", "")
        summary["checks"][indx] = {'sum': 0, 'count': 0}
        summary["money_orders"][indx] = {'sum': 0, 'count': 0}
        
        moneyorders_tmp = moneyorders.filter(broker_moneyorder__broker_moneyorder_name=broker_mo.broker_moneyorder_name)
        summary["money_orders"][indx] = moneyorders_tmp.aggregate(sum=Sum('amount'), count=Count('id'))

        checks_tmp = checks.filter(broker__broker_moneyorder_name=broker_mo.broker_moneyorder_name)
        summary["checks"][indx] = checks_tmp.aggregate(sum=Sum('amount')*-1, count=Count('id'))

    for broker in Broker.objects.all():
        indx = broker.broker_name.lower().replace(" ", "")
        summary["total"][indx] = 0
        excluded = ["total", "send_moneys", "send_moneys_card", "send_moneys_vialink"]
        
        for row in summary:
            if row not in excluded and indx in summary[row] and summary[row][indx]["sum"] is not None:               
                summary["total"][indx] += summary[row][indx]["sum"]
    
    return summary

def bottom_line(filters):
    summary = {"com_checks":{},"checks":{}}
    checks = Check.objects.filter(created_at__range=( filters["start_dt"], filters["end_dt"]))

    if filters["author"]:
        checks = checks.filter(author=filters["author"])

    for broker in Broker.objects.all():
        indx = broker.broker_name.lower().replace(" ", "")

    for broker_mo in BrokerMoneyOrder.objects.all():
        indx = broker_mo.broker_moneyorder_name.lower().replace(" ", "")
        summary["com_checks"][indx] = {'sum': 0, 'count': 0}
        summary["checks"][indx] = {'sum': 0, 'count': 0}
        
        checks_tmp = checks.filter(broker__broker_moneyorder_name=broker_mo.broker_moneyorder_name)
        summary["com_checks"][indx] = checks_tmp.aggregate(sum=Sum('commission'), count=Count('id'))
        summary["checks"][indx] = checks_tmp.aggregate(sum=Sum('amount'), count=Count('id'))
    
    return summary