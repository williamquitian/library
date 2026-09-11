from django import forms
from .models import Task, TaskNote, TaskFile
from clients.models import Client
from django.contrib.auth import get_user_model
from django_select2.forms import ModelSelect2MultipleWidget
from bootstrap_datepicker_plus.widgets import DateTimePickerInput

User = get_user_model()  

class MultiTaskForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.exclude(id=1),
        empty_label="Todos los usuarios",
        required=False,
        label="Asignada a"
    )

    clients = forms.ModelMultipleChoiceField(
        queryset=Client.objects.all(),
        label="Cliente(s)",
        widget=ModelSelect2MultipleWidget(
            model=Client,             
            search_fields=['first_name__icontains', 'last_name__icontains']
        )
    )

    class Meta:
        model = Task
        fields =  ['task_type','due_date','assigned_to','priority','description']
        labels = {
            'task_type' : 'Tipo de tarea',
            'due_date' : 'Fecha de vencimiento',
            'priority' : 'Prioridad',
            'description' : 'Descripción',
        } 
        widgets = {
            'due_date': DateTimePickerInput(options={"format": "MM/DD/YYYY hh:mm a","showTodayButton": True}),
            'description': forms.Textarea(attrs={'rows':4}),
        }

class TaskNoteForm(forms.ModelForm):
    class Meta:
        model = TaskNote
        fields = ['note']
        labels = {'note' : 'Nueva nota' } 
        widgets = {
            'note': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class TaskFileForm(forms.ModelForm):
    class Meta:
        model = TaskFile
        fields = ['file']
        labels = {'file' : '' }
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class TasksFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=list(Task._meta.get_field("status").choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control form-control-sm"})
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.exclude(id=1),
        required=False,
        empty_label="",
        widget=forms.Select(attrs={"class": "form-control form-control-sm"})
    )
    priority = forms.ChoiceField(
        choices= [("", "")] + list(Task._meta.get_field("priority").choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control form-control-sm"})
    )
    task_type = forms.ChoiceField(
        choices= [("", "")] + list(Task._meta.get_field("task_type").choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control form-control-sm"})
    )

class UpdateTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields =  ['status', 'due_date']
        labels = {
            'status' : 'Estado',
            'due_date' : 'Fecha de vencimiento',
        } 
        widgets = {
            'due_date': DateTimePickerInput(options={"format": "MM/DD/YYYY hh:mm a","showTodayButton": True})
        }