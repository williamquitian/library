from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from accounts.views import first_url_segment
from clients.models import Check
from .models import Company
from .forms import CompanyForm 

@login_required
def list(request):
    companies = Company.objects.all()
    return render(request, 'companies/company_list.html', context={'companies':companies, 'app_name':first_url_segment(request)})

@login_required
def create(request):
    company_form = CompanyForm()

    if request.method == "POST":
        company_form = CompanyForm(request.POST)
        if company_form.is_valid():
            company_form.save()
            messages.success(request, "Empresa creada con exito!")
            return redirect('companies-list')

    return render(request, 'companies/company_form.html', {'form': company_form})

@login_required
def edit(request, pk):
    obj = get_object_or_404(Company, pk=pk)
    company_form = CompanyForm(instance=obj)

    if request.method == "POST":
        company_form = CompanyForm(request.POST, instance=obj)
        if company_form.is_valid():
            company_form.save()
            messages.success(request, "Empresa modificada con exito!")
            return redirect('companies-list')
        
    # El template recorre check.manager, así que se precarga para evitar una
    # consulta por cheque.
    checks = Check.objects.filter(
        company=company_form.instance
    ).select_related('manager')
    
    return render(request, 'companies/company_form.html', 
                  {'form': company_form, 'checks': checks}
                  )

@login_required
def get_company_info(request):
    company_id = request.GET.get('id')

    if not company_id:
        return JsonResponse({'error': 'No ID'}, status=400)

    if company_id.isdigit():
        company = get_object_or_404(Company, id = company_id)
        last_check = company.checks.all().order_by('-created_at').first()

        data = {
            "id": company.id,
            "name": company.name,
            "account_number": company.account_number,
            "color": company.color,
            "city": str(company.city) if company.city else None,
            "city_id": company.city_id,
            "comment": company.comment,
            "manager": last_check.manager_id if last_check else None,
            "phone": last_check.manager.phone if last_check and last_check.manager else None,
        }
    else:
        data = {
            "name": company_id.upper(),
            "color": "green"
        }

    return JsonResponse(data)