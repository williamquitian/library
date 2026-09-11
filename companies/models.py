from django.db import models
from django.core.validators import RegexValidator

phone_regex = RegexValidator(
    regex=r'^\d{10}$', 
    message="Número de télefono debe tener 10 dígitos."
)

class State(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10, null=True)

    def __str__(self):
        return self.name

class City(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey('State', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'state'],
                name='unique_city_name_state'
            )
        ]

    @property
    def city_with_state(self):
        if self.id:
            return f"{self.name}, {self.state.short_name}"
        return ""

    def __str__(self):
        return self.city_with_state
    
class Company(models.Model):
    COLOR_CHOICES = [
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('red', 'Red'),
    ]

    account_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    city = models.ForeignKey('City', on_delete=models.SET_NULL, null=True, blank=True)
    color = models.CharField(max_length=15, choices=COLOR_CHOICES, default='green', null=True, blank=False)
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super().save(*args, **kwargs)

class Manager(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10, validators=[phone_regex], blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'phone'], name='unique_name_phone')]

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super().save(*args, **kwargs)