from django import forms
from dal import autocomplete
from clients.models import Client, Comment, Document, SendMoney, SendPackage, MoneyOrder, FidelityCard, Check, ReturnedCheck, ReturnedCheckEvent
from companies.models import Company, Manager
from .utils.forms import get_country_choices
from datetime import date
from django.db.models import Count
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML, Field
from crispy_forms.bootstrap import PrependedText, AppendedText
from bootstrap_datepicker_plus.widgets import DatePickerInput
from crispy_forms.bootstrap import InlineRadios
from django.contrib.auth import get_user_model
from django_select2.forms import Select2Widget

User = get_user_model()  

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'email', 'address',
                  'country', 'date_of_birth', 'profession', 'company']
        labels = {
            'first_name': ('Nombre '),
            'last_name': ('Apellido '),
            'phone': ('Teléfono '),
            'email': ('E-mail '),
            'address' : ('Dirección'),
            'country': ('País '),
            'date_of_birth': ('Fecha de nacimiento '),
            'profession': ('Profesión '),
            'company': ('Empresa '),
        }
        widgets = {
            'date_of_birth':forms.TextInput(
                attrs={'type': 'date'}
                ),
            'first_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'last_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'email':forms.TextInput(attrs={'style': 'text-transform: lowercase;'}),
            'profession': autocomplete.ModelSelect2(url='profession-autocomplete'),
            'company': autocomplete.ModelSelect2(
                url='company-autocomplete',
                attrs={'class': 'uppercase-select2'},
            ),
        }  
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['country'].choices = self.fields['country'].choices = get_country_choices(Client)

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()

        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            self.add_error('date_of_birth', "El cliente debe tener mas de 18 años.")
        return dob

class CommentForm(forms.ModelForm): 
    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': ('Nuevo commentario: '),
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows':2}),
        }

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['name', 'document_type', 'due_date']
        labels = {
            'name': 'Archivo',
            'document_type': 'Tipo de documento',
            'due_date': 'Fecha de vencimiento',
        }
        widgets = {
            'due_date':forms.DateInput(
                format='%m/%d/%Y',
                attrs={
                    'type': 'date',
                    'style': 'width: 150px;',
                    #'placeholder':'mm/dd/yyyy',
                    }
                )
        }

class SendMoneyForm(forms.ModelForm):
    new_card = forms.IntegerField(min_value=0, required=False, label='Nueva tarjeta')

    class Meta:
        model = SendMoney
        fields = ['amount', 'country', 'broker', 'fidelitycard', 'broker_number', 'payment_method']
        autofocus = "broker_number"
        labels = {
            'amount': 'Valor',
            'country': 'País',
            'broker': 'Empresa',
            'fidelitycard': 'Tarjeta Cliente',
            'broker_number': 'Número de envío',
            'payment_method': 'Forma de pago',
        }

        widgets = {
            'payment_method': forms.RadioSelect(
                attrs={'class': 'form-check-inline'}
            )
        }

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client', None) 
        self.author = kwargs.pop('author', None) 
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.fields['country'].choices = self.fields['country'].choices = get_country_choices(SendMoney)

        id_fidelitycard = [0, 1]
        counter = {}
        cards_assigned = self.client.sendmoney.values('fidelitycard').annotate(item_count=Count('id'))

        for item in cards_assigned:
            id_fidelitycard.append(item['fidelitycard'])
            counter[item['fidelitycard']] = item['item_count']

        self.fields['fidelitycard'].queryset = FidelityCard.objects.filter(id__in=id_fidelitycard).order_by('card_num')

        choices = []
        for ch in self.fields['fidelitycard'].queryset:
            if(ch.id != 0 ):
                choices.append((ch.id, f"{ch} ({counter[ch.id] if ch.id in counter else 0})"))

        choices.append((0, "Nueva tarjeta"))
        self.fields['fidelitycard'].choices = choices
        self.fields['amount'].widget.attrs.update({'autofocus': 'autofocus'})
        self.helper.layout = Layout(
            Div(
                Div(PrependedText('amount', '$'), css_class='col-md-5'),
                Div('broker_number', css_class='col-md-7'),
                css_class='row'
            ),            
            'country',
            'broker',
            Div(
                Div('fidelitycard', css_class='col-md-5'),
                Div('new_card', css_class='col-md-5', id="div_row_id_Money-new_card"),
                css_class='row' 
            ),
            InlineRadios('payment_method')
        )

    def clean(self):
        cleaned_data = super().clean()
        new_card = cleaned_data.get('new_card')
        fidelitycard = cleaned_data.get('fidelitycard')
        
        if  fidelitycard.id == 0 and not new_card:
            raise forms.ValidationError("Por favor ingrese una nueva tarjeta.")
        elif fidelitycard.id == 0 and new_card:
            cards = SendMoney.objects.exclude(client=self.client).filter(fidelitycard__card_num=new_card)
            if(cards):                
                raise forms.ValidationError("Tarjeta ya asignada")
        
        if (cleaned_data.get('broker_number') and cleaned_data.get('broker')):
            duplicate = SendMoney.objects.filter(broker_number=cleaned_data.get('broker_number'), broker=cleaned_data.get('broker'))
            if(duplicate.count()>0):
                if(duplicate.count()>1 or (duplicate.first().amount*-1) != cleaned_data.get('amount')):
                    raise forms.ValidationError(
                        f"Error: Ya existe un envío con el número {duplicate.first().broker_number} y compañia {duplicate.first().broker}."
                    )

class SendPackageForm(forms.ModelForm):
    class Meta:
        model = SendPackage
        fields = [ 'weight', 'shipper', 'country', 'size_length', 'size_heigth', 'size_width']
        labels = {
            'weight': 'Peso',
            'country': 'País',
            'shipper': 'Empresa',
            'size_length': 'Largo',
            'size_heigth': 'Alto',
            'size_width': 'Ancho',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        size_length = cleaned_data.get('size_length')
        size_heigth = cleaned_data.get('size_heigth')
        size_width = cleaned_data.get('size_width')
        weight = cleaned_data.get('weight')

        if not weight and (not size_length or not size_heigth or not size_width):
            raise forms.ValidationError(
                "Peso o tamaño del paquete es obligatorio."
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'].choices = self.fields['country'].choices = get_country_choices(SendPackage)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                AppendedText('weight', 'lb'),
                css_class="input-group input-group-sm mb-2",
            ),              
            HTML('<label class="form-label requiredField">Tamaño:</label>'),
            Div(
                Div(AppendedText('size_length', 'in'), css_class='col-md-4'),
                #Div(HTML("<div class='d-flex align-items-end' style='height: 80%;'><span class='mb-2'>x</span></div>"), css_class='col-md-1'),
                Div(AppendedText('size_heigth', 'in'), css_class='col-md-4'),
                #Div(HTML("<div class='d-flex align-items-end' style='height: 80%;'><span class='mb-2'>x</span></div>"), css_class='col-md-1'),
                Div(AppendedText('size_width', 'in'), css_class='col-md-4'),
                css_class='row'  # or 'row'
            ),
            HTML('<span class="badge text-bg-warning" style="font-size:1.10em;" id="volume"></span>'),
            'shipper',
            'country',
        )

class MoneyOrderForm (forms.ModelForm):
    class Meta:
        model = MoneyOrder
        fields = ['amount', 'broker_moneyorder']
        labels = {
            'amount' : 'Valor',
            'broker_moneyorder' : 'Empresa'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                PrependedText('amount', '$'),
                css_class="input-group input-group-sm mb-2",
            ),
            'broker_moneyorder',
        )

class SendMoneyReportForm(forms.Form):
    creation_date = forms.DateField(
        required=False,
        initial=date.today(),
        widget= DatePickerInput(options={"format": "MM/DD/YYYY","showTodayButton": True}),
        label='Fecha reporte',
        #initial=date.today().strftime("%m/%d/%Y"),    
    )
    
    author = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.all(),
        label='Usuario',
        empty_label=None
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        extra_choice = [(0, 'Todos los usuarios')]
        original_choices = list(self.fields['author'].choices)

        self.fields['author'].choices = extra_choice + original_choices

class CheckForm(forms.ModelForm):
    company = forms.ModelChoiceField(
            queryset = Company.objects.order_by('name'),
            label = 'Empresa',
            widget = Select2Widget( {
                'data-placeholder': 'Buscar empresa',
                'data-tags': 'true',
            })
        )
    
    manager = forms.ModelChoiceField(
            queryset = Manager.objects.order_by('name'), 
            label = 'Contacto',
            required=False,
            widget = Select2Widget( {
                'data-placeholder': 'Buscar contacto',
                'data-tags': 'true',
            })
        )
    
    class Meta:
        model = Check
        fields = ['amount', 'comm_percent', 'check_number', 'broker', 'company', 'manager']
        labels = {
            'amount' : 'Valor',
            'check_number' : 'Número de cheque',
            'broker' : 'Pagador',
            'comm_percent' : 'Comisión'
        }     

    def _get_validation_exclusions(self):
        # 'client' no es campo del formulario (la vista lo asigna sobre la
        # instancia), pero sin él Django saltea el UniqueConstraint de
        # client+amount+check_number y el duplicado explota como IntegrityError.
        exclude = super()._get_validation_exclusions()
        exclude.discard('client')
        return exclude

class CheckUpdateForm(CheckForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["amount"].disabled = True
        self.fields["check_number"].disabled = True
        self.fields["comm_percent"].disabled = True
        self.fields["company"].disabled = True

class SearchCheckForm(forms.Form):
    """Busca el cheque que se va a devolver. Los tres campos son obligatorios.

    Cliente + número + valor es justo el UNIQUE de `Check`
    (`unique_check_client_amount_number`), así que la búsqueda no puede traer
    más de un resultado. Sin el cliente sí sería ambigua: en la base hay pares
    (número, valor) repetidos entre clientes distintos.

    Los tipos copian los del modelo para que el match contra la base sea exacto
    y la validación de formato salga gratis.
    """

    # El select trae el id del cliente en su propio value, así que no hace falta
    # el campo oculto que llevaba el autocomplete de jQuery UI.
    client = forms.ModelChoiceField(
        queryset=Client.objects.order_by('first_name', 'last_name'),
        label="Cliente",
        # Sin `data-theme`: select2 lee los data-* del <select> como opciones, y
        # pedir el tema 'bootstrap-5' —cuya hoja no carga nadie— dejaba el
        # desplegable sin estilos y sin resaltado. El tema 'default' sí viene
        # con su CSS en el media de dal.
        widget=autocomplete.ModelSelect2(
            url='client-autocomplete',
            attrs={'data-placeholder': 'Buscar cliente'},
        ),
    )
    check_number = forms.IntegerField(label="Número de cheque")
    amount = forms.DecimalField(
        label="Valor", max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'}),
    )

class ReturnedCheckUpdateForm(forms.Form):
    """Formulario único del expediente: acción, fecha, fee, imagen y observación.

    Antes había un form por cada botón de desenlace más otro para el archivo y
    el comentario; los campos compartidos se copiaban por JavaScript.
    """

    outcome = forms.ChoiceField(label='Acción', required=False, choices=[])

    date = forms.DateField(
        label='Fecha',
        required=False,
        input_formats=['%m/%d/%Y', '%Y-%m-%d'],
        widget=DatePickerInput(options={"format": "MM/DD/YYYY", "showTodayButton": True}),
    )

    fee = forms.DecimalField(
        label='Fee', required=False, max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'}),
    )

    file_path = forms.FileField(
        label='Imagen del cheque', required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'}),
    )

    comment = forms.CharField(
        label='Observación', required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, returned_check=None, **kwargs):
        super().__init__(*args, **kwargs)
        labels = ReturnedCheckEvent.ACTION_LABELS
        actions = ReturnedCheckEvent.ACTIONS_BY_STATUS.get(
            getattr(returned_check, 'status', None), [])

        if actions:
            self.fields['outcome'].choices = (
                [('', 'Ninguna')] + [(a, labels[a]) for a in actions]
            )
        else:
            # Expediente cerrado: solo se pueden agregar observaciones.
            del self.fields['outcome']
            del self.fields['fee']
            del self.fields['file_path']


class ReturnCheckForm(forms.ModelForm):
    comment = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )

    # El datepicker emite MM/DD/YYYY pero con LANGUAGE_CODE='es' Django parsea
    # %d/%m/%Y: sin input_formats, cualquier fecha después del día 12 es inválida.
    date_returned = forms.DateField(
        input_formats=['%m/%d/%Y', '%Y-%m-%d'],
        widget=DatePickerInput(options={"format": "MM/DD/YYYY", "showTodayButton": True}),
        label='Fecha de devolución',
    )

    class Meta:
        model = ReturnedCheck
        fields = ['date_returned', 'original_check', 'comment', 'file_path']
        labels = {
            'date_returned': 'Fecha de devolución',
            'file_path': 'Imagen del cheque',
        }
        widgets = {
            'original_check': forms.HiddenInput(),
            'file_path': forms.FileInput(
                attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
        }