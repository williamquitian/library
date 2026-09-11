from django import forms
from bootstrap_datepicker_plus.widgets import DatePickerInput
from django.contrib.auth import get_user_model
from datetime import date

User = get_user_model()

# El datepicker emite MM/DD/YYYY, pero con LANGUAGE_CODE='es' Django parsea las
# fechas como %d/%m/%Y: sin esto "09/15/2026" es inválido, el form no valida y
# el reporte cae al valor por defecto (hoy) sin avisarle al usuario.
DATE_INPUT_FORMATS = ['%m/%d/%Y', '%Y-%m-%d']

class ReportsForm(forms.Form):
    '''creation_date = forms.DateField(
        required=False,
        widget= DatePickerInput(options={"format": "MM/DD/YYYY","showTodayButton": True}),
        label='Fecha reporte',  
    )'''
    
    start_date = forms.DateField(
        required=False,
        initial=date.today,
        input_formats=DATE_INPUT_FORMATS,
        widget=DatePickerInput(options={"format": "MM/DD/YYYY", "showTodayButton": True}),
        label='Fecha inicio',
    )
    end_date = forms.DateField(
        required=False,
        initial=date.today,
        input_formats=DATE_INPUT_FORMATS,
        widget=DatePickerInput(
            range_from='start_date', 
            options={"format": "MM/DD/YYYY", "showTodayButton": True, }
        ),
        label='Fecha fin',
    )

    author = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.all(),
        label='Usuario',
        empty_label='Todos los usuarios'
    )