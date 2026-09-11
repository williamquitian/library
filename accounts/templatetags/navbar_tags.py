from django import template
from tasks.models import Task
from clients.models import ReturnedCheck

register = template.Library()

@register.simple_tag
def open_tasks():
    tasks_badge = Task.objects.filter(status='pending')
    return tasks_badge.count()

@register.simple_tag
def open_check_returns():
    returns = ReturnedCheck.objects.filter(
                status__in=ReturnedCheck.OPEN_STATUSES
            )
    if returns.count() > 0:
        return returns.count() 
    else :
        return ""