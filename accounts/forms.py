from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.forms.widgets import PasswordInput, TextInput
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django import forms

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=TextInput())
    password = forms.CharField(widget=PasswordInput())

class CreateUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            'username',
            'first_name', 
            'last_name', 
            'email', 
            'password1', 
            'password2', 
            'is_active',
            'is_superuser'
        ]

        labels = { 'is_superuser': 'Administrador' }

        widgets = {
            'first_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'last_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'email':forms.TextInput(attrs={'style': 'text-transform: lowercase;'}),
            'username':forms.TextInput(attrs={'style': 'text-transform: lowercase;'}),
        }  

    def clean(self):
        cleaned_data = super().clean()                

        if(cleaned_data['first_name']):
            cleaned_data['first_name'] = cleaned_data['first_name'].upper()

        if(cleaned_data['last_name']):
            cleaned_data['last_name'] = cleaned_data['last_name'].upper()

        if(cleaned_data['email']):
            cleaned_data['email'] = cleaned_data['email'].lower()

        if(cleaned_data['username']):
            cleaned_data['username'] = cleaned_data['username'].lower()

        return cleaned_data

class UpdateUserForm(UserChangeForm):    
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text="Deje en blanco este espacio si no quiere cambiar la contraseña.",
    )
    password2 = forms.CharField(
        label="Contraseña (confirmación)",
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text="Para verificar, introduzca la misma contraseña anterior.",
    )

    class Meta:
        model = User
        fields = [
           'username',
            'first_name', 
            'last_name', 
            'email', 
            'is_active',
            'is_superuser'
        ]

        labels = { 'is_superuser': 'Administrador' }

        help_texts = {'username' : 'Nombre de usuario no puede ser modificado'}

        widgets = {
            'first_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'last_name':forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'email':forms.TextInput(attrs={'style': 'text-transform: lowercase;'}),
            'username':forms.TextInput(attrs={'readonly':True}),
        }  

    def clean(self):
        cleaned_data = super().clean()                

        if(cleaned_data['first_name']):
            cleaned_data['first_name'] = cleaned_data['first_name'].upper()

        if(cleaned_data['last_name']):
            cleaned_data['last_name'] = cleaned_data['last_name'].upper()

        if(cleaned_data['email']):
            cleaned_data['email'] = cleaned_data['email'].lower()

        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password2")

        if p1 or p2:
            if p1 != p2:
                self.add_error('password', "Las dos contraseñas deben coincidir.")
            
            try:
                validate_password(p1, self.instance)
            except ValidationError as e:
                self.add_error('password', e)

        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.password = make_password(password)
        if commit:
            user.save()
        return user