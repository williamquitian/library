from django import forms
from .models import Company, Manager
from django.db.models import Case, When, Value, IntegerField
from django_select2.forms import ModelSelect2Widget
from django_select2.forms import Select2Widget


class CityWidget(ModelSelect2Widget):
    search_fields = ['name__icontains']

    def get_queryset(self):
        qs = super().get_queryset()

        return qs.annotate(
            priority=Case(
                When(state__short_name='TN', then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            )
        ).order_by('priority', 'name')

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company                                                                     
        fields = ['account_number', 'name', 'city','color', 'comment']
        labels = {
            'account_number': 'Numero de cuenta',
            'name': 'Nombre de la empresa',              
            'city': 'Ciudad'                                                 ,
            'comment': 'Comentarios',
        }
        widgets = {
            'city': CityWidget,
            'color': forms.RadioSelect(attrs={'class': 'color-radio'}),
            'comment': forms.Textarea(attrs={'rows':3})
        }

class ManagerForm(forms.ModelForm):
    class Meta:
        model = Manager
        fields = ['name','phone']
        labels = {
            'phone' : 'Teléfono de contacto'
        }