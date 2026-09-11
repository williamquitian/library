from django.http import HttpResponseForbidden
from functools import wraps

def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden("Permiso denegado.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view