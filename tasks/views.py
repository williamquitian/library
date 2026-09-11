from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from accounts.views import first_url_segment
from .forms import MultiTaskForm, TaskNoteForm, TaskFileForm, TasksFilterForm, UpdateTaskForm
from .models import Task, TaskFile
from django.contrib import messages
from django.http import JsonResponse
from django.utils.timezone import localtime
import pytz
from django.utils.text import Truncator
from django.db.models.functions import Concat
from django.db.models import Value


@login_required
def list(request):
    listForm = TasksFilterForm()
    return render(request, 'tasks/tmpl_list.html',{'form':listForm})

@login_required
def list_ajax(request):
    draw = int(request.POST.get("draw", 1))  
    start = int(request.POST.get("start", 0))  
    length = int(request.POST.get("length", 10))  

    qs = Task.objects.annotate(
        full_name=Concat('client__first_name', Value(' '), 'client__last_name')
    )

    if request.POST.get("client"):
        qs = qs.filter(full_name__icontains=request.POST.get("client"))
    
    if request.POST.get("task"):
        task = request.POST.get("task").replace("T","")
        qs = qs.filter(id=task)
    
    if request.POST.get("status"):
        qs = qs.filter(status=request.POST.get("status"))
    
    if request.POST.get("priority"):
        qs = qs.filter(priority=request.POST.get("priority"))

    if request.POST.get("task_type"):
        qs = qs.filter(task_type=request.POST.get("task_type"))

    if request.POST.get("assigned_to"):
        qs = qs.filter(assigned_to=request.POST.get("assigned_to"))

    columns = ["id", "status", "priority", "task_type", "client", "assigned_to", "due_date", "description"]

    order_col_index = request.POST.get("order[0][column]", 0)
    order_col = columns[int(order_col_index)]
    order_dir = request.POST.get("order[0][dir]", "asc")
    if order_dir == "desc":
        order_col = f"-{order_col}"
    qs = qs.order_by(order_col)

    paginator = Paginator(qs, length)
    page_number = (start // length) + 1
    page_obj = paginator.get_page(page_number)

    data = [
        {
            "id": obj.id, 
            "link": f"T{obj.id:06d}", 
            "client": str(obj.client), 
            "task_type":obj.get_task_type_display(),
            "description":Truncator(obj.description).words(4, truncate=' ...'),
            "due_date":  utc_to_local(obj.due_date).strftime('%m/%d/%Y %I:%M %p'),
            "status":obj.get_status_display(),
            "assigned_to":obj.assigned_to.username if obj.assigned_to else "Todos",
            "priority":obj.get_priority_display(),
            "is_past_due":obj.is_past_due,
        }
        for obj in page_obj.object_list
    ]

    return JsonResponse({
        "draw": draw,
        "recordsTotal": Task.objects.count(),
        "recordsFiltered": qs.count(),
        "data": data,
    })

@login_required
def create(request):
    if request.method == 'POST':
        form = MultiTaskForm(request.POST)
        if form.is_valid():
            clients = form.cleaned_data['clients']
            task_data = {
                'task_type': form.cleaned_data['task_type'],
                'description': form.cleaned_data['description'],
                'due_date': form.cleaned_data['due_date'],
                'priority': form.cleaned_data['priority'],
                'assigned_to': form.cleaned_data['assigned_to'],
            }
            
            for client in clients:
                task = Task.objects.create(client = client, created_by=request.user, **task_data)
            messages.success(request, f"{len(clients)} Tarea(s) guardada(s) con exito!")
            return redirect('task-detail', pk=task.id)  
    else:
        form = MultiTaskForm()

    return render(request, 'tasks/tmpl_create.html', {'form': form, 'app_name':first_url_segment(request)})

@login_required
def detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    note_form = TaskNoteForm()
    file_form = TaskFileForm()
    task_form = UpdateTaskForm(instance = task)
    
    if request.method == 'POST':
        if 'add_note' in request.POST:
            note_form = TaskNoteForm(request.POST)
            if note_form.is_valid():
                note = note_form.save(commit=False)
                note.task = task
                note.created_by = request.user
                note.save()
                messages.success(request, "Nota agregada con exito!")
                return redirect('task-detail', pk=pk)

        elif 'add_file' in request.POST:
            file_form = TaskFileForm(request.POST, request.FILES)
            if file_form.is_valid():
                task_file = file_form.save(commit=False)
                task_file.task = task
                task_file.created_by = request.user
                task_file.name = request.FILES["file"]
                task_file.save()
                messages.success(request, "Documento agregado con exito!")
                return redirect('task-detail', pk=pk)     

        elif 'update_task' in request.POST:
            task_form = UpdateTaskForm(request.POST, instance=task)
            if task_form.is_valid():
                
                changes = ""
                for field in task_form.changed_data:
                    if field == 'due_date':
                        old_value = utc_to_local(task_form.initial[field]).strftime('%m/%d/%Y %I:%M %p')
                        new_value = task_form.cleaned_data[field].strftime('%m/%d/%Y %I:%M %p')
                    
                    if field == 'status':
                        old_value = dict(task_form.fields[field].choices).get(task_form.initial[field]) 
                        new_value = dict(task_form.fields[field].choices).get(task_form.cleaned_data[field]) 

                    changes = changes + f"({task_form.fields[field].label}: {old_value} -> {new_value}) "

                task_form.save()
                if changes:
                    task.log_modification(request.user, changes)
                messages.success(request, "Tarea actializada con exito!")
                return redirect('task-detail', pk=pk)            

    context = {
        'task': task,
        'note_form': note_form,
        'file_form': file_form,
        'task_form': task_form,
    }
    return render(request, 'tasks/tmpl_detail.html', context)

@login_required
def view_file(request, pk):
    doc = TaskFile.objects.get(id = pk)
    return render(request, 'tasks/view_file.html', {'doc' : doc})
    
def utc_to_local(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:  # naive datetime
        # explicitly mark it as UTC
        dt = dt.replace(tzinfo=pytz.UTC)

    return localtime(dt)