from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import auth
from django.contrib import messages
from django.http import HttpResponse
from .forms import CreateUserForm, UpdateUserForm, LoginForm
from .decorators import superuser_required
from django.contrib.auth.models import Permission

@login_required
def home(request):
    if request.user.is_authenticated:
        return redirect('clients-list')
    return redirect('login')

def login(request):
    if request.user.is_authenticated:
       return redirect('clients-list')
    
    form = LoginForm()
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)            
            if user is not None:
                auth.login(request, user)
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                else:
                    return redirect('clients-list')
            
    context = {'form':form}
    return render(request, 'accounts/tmpl_login.html', context=context)

def logout(request):
    auth.logout(request)
    return redirect("accounts-login")

@superuser_required
def list(request):
    User = get_user_model()
    users = User.objects.all()
    return render(request, 'accounts/tmpl_list.html', context={'users':users, 'app_name':first_url_segment(request)})

@superuser_required
def new(request):    
    if request.method == "POST":
        form = CreateUserForm( request.POST )
        if form.is_valid():
            user = form.save()
            permission = Permission.objects.get(name='Can add company')
            user.user_permissions.add(permission)
            permission = Permission.objects.get(name='Can add profession')
            user.user_permissions.add(permission)
            messages.success(request, "Usuario creado con exito!")
            return redirect('accounts-list')
    else:
        form = CreateUserForm()
    
    return render (request, 'accounts/tmpl_new.html', context={'form':form, 'app_name':first_url_segment(request)})

@superuser_required
def update(request, pk):
    User = get_user_model()
    user = get_object_or_404(User, pk = pk)
    
    if request.method == "POST":
        form = UpdateUserForm( request.POST, instance=user )
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario modificado con exito!")
            return redirect('accounts-list')
    else:
        form = UpdateUserForm(instance=user)
    
    return render (request, 'accounts/tmpl_update.html', context={'form':form, 'app_name':first_url_segment(request)})

@login_required
def password_update(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            #update_session_auth_hash(request, user)  # Keeps the user logged in
            messages.success(request, "Contraseña modificada!")
            return redirect('clients-list')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'accounts/tmpl_change_pw.html', {'form': form})  

def first_url_segment(request):
    path = request.path.strip("/").split("/")
    return path[0] if path else ""