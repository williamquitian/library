from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator, RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal
import shortuuid
import re
import os
import math

phone_regex = RegexValidator(
    regex=r'^\d{10}$', 
    message="Número de télefono debe tener 10 dígitos."
)

class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, null=True)
    creation_date = models.DateTimeField(default=timezone.now)
    phone = models.CharField(max_length=20, null=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    country = models.ForeignKey('Country', on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True)
    cards = models.ManyToManyField('FidelityCard', through='SendMoney')
    profession = models.ForeignKey('Profession', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.first_name + " " + self.last_name
    
    def clean(self):
        super().clean()
        if self.first_name: self.first_name = self.first_name.upper()
        if self.last_name: self.last_name = self.last_name.upper()
        if self.email: self.email = self.email.lower()
        if self.phone: self.phone = re.sub(r'\D', '', self.phone.lower()) 
    
    def log_modification(self, user, changes):
        comment_content = f"Cliente modificado:\n{changes}"
        Comment.objects.create(client=self, author=user, content=comment_content)
    
    def get_sendmoney_sum_month(self):
        today = date.today()
        target_date = today - timedelta(days=30)
        total_month = SendMoney.objects.filter(client=self, creation_date__gte=target_date).aggregate(Sum('amount'))['amount__sum']
        if total_month:
            return round(total_month, 2)
        else:
            return 0
    
    def get_sendmoney_count_month(self):
        today = date.today()
        target_date = today - timedelta(days=30)
        return SendMoney.objects.filter(client=self, creation_date__gte=target_date).aggregate(Count('amount'))['amount__count']

class Document(models.Model):
    DOCUMENT_TYPES = [
        ("AT" , "Autorización de trabajo"),
        ("CC" , "Cédula de Ciudadanía "),
        ("CE" , "Credencial Electoral"),
        ("DNI" , "DNI"),
        ("DUI" , "Documento Único de Identificación"),
        ("DPI" , "DPI"),
        ("F1025" , "F1025"),
        ("FA" , "Foto Actual"),
        ("IE" , "Identificación estatal"),
        ("LC" , "Licencia de Conducir"),
        ("MC" , "Matrícula Consular"),
        ("PA" , "Pasaporte"),
        ("PI" , "Prueba de Ingresos"),
        ("RN" , "Registro Nacional"),
        ("RE" , "Residencia"),
        ("RENAP" , "RENAP"),
    ]

    def upload_rename(instance, filename):
        ext = filename.split('.')[-1]
        new_filename = "%s.%s" % (shortuuid.uuid(), ext)
        return new_filename

    def validate_file_size(value):
        max_size = 2 * 1024 * 1024  # 2 MB
        if value.size > max_size:
            raise ValidationError('El archivo debe pesar menos de 2MB.')
    
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='documents')
    creation_date = models.DateTimeField(default=timezone.now)
    name = models.FileField(upload_to=upload_rename, validators=[FileExtensionValidator(['pdf','jpg', 'jpeg']), validate_file_size])
    document_type = models.CharField(max_length=5, choices=DOCUMENT_TYPES)  
    due_date = models.DateField(null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
    @property
    def is_past_due(self):
        if self.due_date:
            return date.today() > self.due_date
        else:
            return None
    @property
    def ext(self):
        root, extension = os.path.splitext(self.name.name)
        extension = extension.lstrip('.')
        return extension

class Comment(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.author} on {self.client}"
    
class Country(models.Model):
    iso = models.CharField(max_length=2, null=False)
    name = models.CharField(max_length=80, null=False)

    def __str__(self):
        return f"{self.name}"

class SendMoney(models.Model):
    PAYMENT_METHODS = [
        ("cash","Efectivo"),
        ("card","Tarjeta"),
        ("vialink","ViaLink"),
    ]
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='sendmoney')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    creation_date = models.DateTimeField(default=timezone.now, db_index=True)
    country = models.ForeignKey('Country', on_delete=models.CASCADE)
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE)    
    fidelitycard = models.ForeignKey('FidelityCard', on_delete=models.CASCADE, default=1, related_name='sendmoney')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    broker_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(99999999)])
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cash')  

    @property
    def allow_delete(self):
        time_difference = timezone.now() - self.creation_date
        return round(time_difference.total_seconds() / 3600, 1) < 4
      

class Broker(models.Model):
    broker_name = models.CharField(max_length=80)
    
    def __str__(self):
        return f"{self.broker_name}"
    
class SendPackage(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='sendpackage')
    size_length = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, validators=[MinValueValidator(0.1), MaxValueValidator(9999.9)])
    size_width = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, validators=[MinValueValidator(0.1), MaxValueValidator(9999.9)])
    size_heigth = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, validators=[MinValueValidator(0.1), MaxValueValidator(9999.9)])
    weight = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, validators=[MinValueValidator(0.1), MaxValueValidator(9999.9)])
    creation_date = models.DateTimeField(default=timezone.now)
    country = models.ForeignKey('Country', on_delete=models.CASCADE)
    shipper = models.ForeignKey('Shipper', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
class Shipper(models.Model):
    shipper_name = models.CharField(max_length=80)
    
    def __str__(self):
        return f"{self.shipper_name}"
    
class MoneyOrder(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='moneyorder')
    amount = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(1.0), MaxValueValidator(999999.9)])
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    broker_moneyorder = models.ForeignKey('BrokerMoneyOrder', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

class BrokerMoneyOrder(models.Model):
    broker_moneyorder_name = models.CharField(max_length=80)
    
    def __str__(self):
        return f"{self.broker_moneyorder_name}"
    
class FidelityCard(models.Model):
    card_num = models.IntegerField(unique=True, validators=[MinValueValidator(1), MaxValueValidator(99999999)])
    created_at = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        if self.card_num == 0:
            return 'Sin tarjeta'
        elif self.card_num == -1:
            return 'Nueva tarjeta'
        else:
            return f"{self.card_num}"

class Profession(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super().save(*args, **kwargs)

class Check(models.Model):
    COMMISSION_PERCENT = [
        (Decimal('2.0'), "2%"),
        (Decimal('1.5'), "1.5%"),
        (Decimal('1.0'), "1%"),
        (Decimal('0.0'), "0%"),
        (Decimal('0.5'), "0.5%"),
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='checks')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2)
    check_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(99999999)])
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='checks')
    manager = models.ForeignKey('companies.Manager', related_name='checks', on_delete=models.CASCADE, null=True, blank=True)
    broker = models.ForeignKey('BrokerMoneyOrder', on_delete=models.CASCADE, related_name='broker')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    comm_percent = models.DecimalField(max_digits=3, decimal_places=1, choices=COMMISSION_PERCENT, default=Decimal('1.5'))  

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'amount', 'check_number'],
                name='unique_check_client_amount_number',
                violation_error_message='Este cliente ya tiene un cheque con ese número y ese valor.',
            )
        ]

    def save(self, *args, **kwargs):
        raw_commission = (self.amount * self.comm_percent)/100
        rounded_final = math.floor(self.amount - raw_commission)

        # store adjusted commission only
        self.commission = self.amount - Decimal(str(rounded_final))
        super().save(*args, **kwargs)

    @property
    def allow_delete(self):
        time_difference = timezone.now() - self.created_at
        return round(time_difference.total_seconds() / 3600, 1) < 6
    
    @property
    def net_amount(self):
        return self.amount - self.commission

class ReturnedCheck(models.Model):
    """Expediente de un cheque devuelto.

    Un cheque puede rebotar, re-depositarse y volver a rebotar. `original_check`
    sigue siendo OneToOne (hay un UNIQUE real en la base), así que los ciclos
    NO se modelan con filas nuevas de este modelo, sino con los eventos hijos
    de `ReturnedCheckEvent`: un expediente por cheque, con toda su historia.
    """

    STATUS_PENDING = 'pendiente'
    STATUS_REDEPOSITED = 'redepositado'
    STATUS_RECOVERED = 'recuperado'
    STATUS_WRITTEN_OFF = 'perdido'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_REDEPOSITED, 'Re-depositado'),
        (STATUS_RECOVERED, 'Recuperado'),
        (STATUS_WRITTEN_OFF, 'Pérdida'),
    ]

    # Estados en los que el cliente todavía debe plata.
    OPEN_STATUSES = [STATUS_PENDING, STATUS_REDEPOSITED]

    original_check = models.OneToOneField(
        Check,
        on_delete=models.PROTECT,
        related_name="returned_check"
    )

    reversal_check = models.OneToOneField(
        Check,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal_check"
    )

    def upload_rename(instance, filename):
        ext = filename.split('.')[-1]
        new_filename = "%s.%s" % (shortuuid.uuid(), ext)
        return new_filename

    def validate_file_size(value):
        max_size = 2 * 1024 * 1024  # 2 MB
        if value.size > max_size:
            raise ValidationError('El archivo debe pesar menos de 2MB.')

    date_returned = models.DateField(default=timezone.now)
    fees = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date_payoff = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    file_path = models.FileField(upload_to=upload_rename, null=True, blank=True, validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png']), validate_file_size])
    file_name = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name='Estado',
    )

    def __str__(self):
        return f"Returned: {self.original_check.check_number}"

    @property
    def is_open(self):
        """True mientras quede plata por cobrarle al cliente."""
        return self.status in self.OPEN_STATUSES

    @property
    def total_fees(self):
        """Un fee por cada rebote: se acumulan a lo largo del expediente."""
        return sum((e.fee for e in self.events.all()), Decimal('0.00'))

    @property
    def ext(self):
        """Extensión del archivo adjunto ('pdf', 'jpg'…), para elegir el visor.

        `ReturnedCheck` no tenía esta propiedad, así que la plantilla del visor
        comparaba contra vacío y un PDF terminaba dentro de un <img>.
        """
        if not self.file_path:
            return ''
        _root, extension = os.path.splitext(self.file_path.name)
        return extension.lstrip('.').lower()

    @property
    def attempts(self):
        """Cuántas veces ha rebotado este cheque (la devolución inicial cuenta)."""
        return self.events.filter(
            event_type__in=[ReturnedCheckEvent.RETURNED, ReturnedCheckEvent.BOUNCED]
        ).count()

    @property
    def timeline(self):
        """Historial completo del expediente, del más nuevo al más viejo.

        Los eventos ya salen ascendentes por el `ordering` del modelo, así que
        invertirlos acá evita otra consulta y aprovecha el `prefetch_related`.
        """
        return list(reversed(self.events.all()))


class ReturnedCheckEvent(models.Model):
    """Cada intento del expediente: devolución, re-depósito y su resultado.

    Es lo que permite rebotes ilimitados sin tocar el UNIQUE de
    `ReturnedCheck.original_check`.
    """

    RETURNED = 'returned'
    REDEPOSITED = 'redeposited'
    CLEARED = 'cleared'
    BOUNCED = 'bounced'
    PAID_CASH = 'paid_cash'
    PAID_CHECK = 'paid_check'
    WRITTEN_OFF = 'written_off'
    COMMENT = 'comment'

    EVENT_TYPES = [
        (RETURNED, 'Devuelto'),
        (REDEPOSITED, 'Re-depositado'),
        (CLEARED, 'Re-depósito exitoso'),
        (BOUNCED, 'Rebotó de nuevo'),
        (PAID_CASH, 'Cliente pagó en efectivo'),
        (PAID_CHECK, 'Cliente pagó con cheque'),
        (WRITTEN_OFF, 'Dado por perdido'),
        (COMMENT, 'Comentario'),
    ]

    # Etiquetas del selector de acción: en imperativo, porque ahí el usuario
    # elige qué hacer. Las de EVENT_TYPES están en pasado para el historial.
    ACTION_LABELS = {
        REDEPOSITED: 'Re-depositar',
        CLEARED: 'Re-depósito exitoso',
        BOUNCED: 'Rebotó de nuevo',
        PAID_CASH: 'Cliente pagó en efectivo',
        PAID_CHECK: 'Pago con cheque',
        WRITTEN_OFF: 'Dar por perdido',
    }

    # Desenlaces que puede registrar el usuario, según en qué estado esté el
    # expediente. Un comentario suelto (acción vacía) siempre se puede grabar.
    ACTIONS_BY_STATUS = {
        ReturnedCheck.STATUS_PENDING: [REDEPOSITED, PAID_CASH, PAID_CHECK, WRITTEN_OFF],
        ReturnedCheck.STATUS_REDEPOSITED: [CLEARED, BOUNCED, PAID_CASH, PAID_CHECK, WRITTEN_OFF],
    }

    returned_check = models.ForeignKey(
        ReturnedCheck,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(
        max_length=15, choices=EVENT_TYPES, verbose_name='Evento')
    date = models.DateField(
        default=timezone.localdate, db_index=True, verbose_name='Fecha')
    fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Fee cobrado')
    comment = models.TextField(blank=True, verbose_name='Observaciones')
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        ordering = ['date', 'created_at']
        verbose_name = 'Evento de cheque devuelto'
        verbose_name_plural = 'Eventos de cheques devueltos'

    def __str__(self):
        return f"{self.get_event_type_display()} · {self.date}"
