from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.utils import timezone
import shortuuid
import os

class Task(models.Model):
    TASK_TYPE_CHOICES = [
        ('CHK', 'Cheque'),
        ('SM', 'Envío de dinero'),
        ('SP', 'Envío de paquetes'),
        ('MO', 'Money Order'),
        ('NA', 'Otros'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('completed', 'Completado'),
    ]

    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='client')
    task_type = models.CharField(max_length=5, choices=TASK_TYPE_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='assigned_to')
    priority = models.CharField(max_length=10, choices=[('normal', 'Normal'), ('high', 'Alta')], default='normal')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_by')

    def log_modification(self, user, changes):      
        note_content = f"Tarea modificada: {changes}"
        TaskNote.objects.create(task=self, created_by=user, note=note_content)

    @property
    def is_past_due(self):
        if self.status == 'pending' and self.due_date:
            return timezone.now() > self.due_date
        else:
            return None

class TaskNote(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class TaskFile(models.Model):
    def upload_rename(instance, filename):
        ext = filename.split('.')[-1]
        new_filename = "%s.%s" % (shortuuid.uuid(), ext)
        return new_filename

    def validate_file_size(value):
        max_size = 2 * 1024 * 1024  # 2 MB
        if value.size > max_size:
            raise ValidationError('El archivo debe pesar menos de 2MB.')
        
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=upload_rename, validators=[FileExtensionValidator(['pdf','jpg', 'jpeg']), validate_file_size])
    name = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    @property
    def ext(self):
        root, extension = os.path.splitext(self.name)
        extension = extension.lstrip('.')
        return extension

    def __str__(self):
        return self.name