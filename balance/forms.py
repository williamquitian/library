from datetime import date
from decimal import Decimal

from bootstrap_datepicker_plus.widgets import DatePickerInput
from django import forms
from django.contrib.auth import get_user_model

from .models import BalanceAccount, BalanceMovement, DailyBalance

User = get_user_model()

# El widget del datepicker emite MM/DD/YYYY, pero con LANGUAGE_CODE='es' Django
# parsea las fechas como %d/%m/%Y. Sin esto, "09/15/2026" es inválido y el form
# cae silenciosamente al valor por defecto. Se fija explícitamente en el campo
# porque `input_formats` sí gana sobre los formatos del locale.
DATE_INPUT_FORMATS = ['%m/%d/%Y', '%Y-%m-%d']


class BalanceDateForm(forms.Form):
    """Filtro de fecha para las vistas personal y diaria."""

    date = forms.DateField(
        required=False,
        initial=date.today,
        input_formats=DATE_INPUT_FORMATS,
        widget=DatePickerInput(options={"format": "MM/DD/YYYY", "showTodayButton": True}),
        label='Fecha',
    )
    user = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_active=True).order_by('username'),
        label='Usuario',
        empty_label='Todos los usuarios',
    )

    def __init__(self, *args, show_user=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Un cajero solo ve su propia caja: el selector de usuario existe
        # únicamente para superusuarios.
        if not show_user:
            self.fields.pop('user')


class BalanceMonthForm(forms.Form):
    """Filtro de mes para la vista mensual (solo superusuarios)."""

    MONTHS = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    month = forms.TypedChoiceField(choices=MONTHS, coerce=int, label='Mes')
    year = forms.TypedChoiceField(choices=[], coerce=int, label='Año')
    user = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_active=True).order_by('username'),
        label='Usuario',
        empty_label='Todos los usuarios',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = date.today().year
        self.fields['year'].choices = [(y, y) for y in range(current_year - 5, current_year + 1)]


class DailyBalanceForm(forms.ModelForm):
    """Una tarjeta del balance: las cifras que digita el cajero.

    Una cuenta manual no se cuadra contra nada, así que `company_balance` ni
    siquiera existe en su formulario: no se renderiza y no se puede mandar por
    POST.
    """

    class Meta:
        model = DailyBalance
        fields = ['initial_balance', 'manual_movement', 'company_balance']
        widgets = {
            'initial_balance': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}
            ),
            'manual_movement': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}
            ),
            'company_balance': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01',
                       'placeholder': 'Sin digitar'}
            ),
        }

    def __init__(self, *args, is_manual=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_manual = is_manual
        if is_manual:
            del self.fields['company_balance']
        # El cajero no tiene por qué llenar todas las cuentas: en blanco es cero.
        self.fields['initial_balance'].required = False
        self.fields['manual_movement'].required = False

    def clean_initial_balance(self):
        value = self.cleaned_data.get('initial_balance')
        return Decimal('0.00') if value is None else value

    def clean_manual_movement(self):
        value = self.cleaned_data.get('manual_movement')
        return Decimal('0.00') if value is None else value

    @property
    def is_empty(self):
        """True si no se digitó nada: evita crear filas de ceros por cuenta."""
        if self.instance.pk:
            return False
        return not any(self.data.get(self.add_prefix(f)) for f in self.fields)


class BalanceMovementForm(forms.ModelForm):
    """Alta de un movimiento de efectivo.

    `from_user` y `author` los asigna la vista con `request.user`; nunca llegan
    desde el POST.
    """

    date = forms.DateField(
        initial=date.today,
        input_formats=DATE_INPUT_FORMATS,
        widget=DatePickerInput(options={"format": "MM/DD/YYYY", "showTodayButton": True}),
        label='Fecha',
    )

    class Meta:
        model = BalanceMovement
        fields = ['movement_type', 'date', 'amount', 'to_user', 'account', 'description']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'description': forms.TextInput(attrs={'placeholder': 'Opcional'}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.fields['account'].queryset = BalanceAccount.objects.filter(is_active=True)
        self.fields['account'].empty_label = 'Sin cuenta asignada'
        self.fields['account'].required = False
        self.fields['to_user'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['to_user'].empty_label = 'Seleccione un usuario'
        if current_user is not None:
            self.fields['to_user'].queryset = self.fields['to_user'].queryset.exclude(
                pk=current_user.pk
            )

    def clean(self):
        cleaned = super().clean()
        # `Model.clean()` valida la coherencia tipo/destinatario, pero necesita
        # `from_user` puesto antes de correr.
        if self.current_user is not None:
            self.instance.from_user = self.current_user
        return cleaned
