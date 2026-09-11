from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from .forms import BookDatalistForm, BookForm, BookInlineSearchForm
from .models import Author, Book, Publisher

SEARCHABLE = {"author": (Author, "name"), "publisher": (Publisher, "name")}


def _book_page(request, form_class, url_name, page_title, intro):
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            form.save()
            return redirect(url_name)
    else:
        form = form_class()

    return render(
        request,
        "catalog/book_form.html",
        {
            "form": form,
            "page_title": page_title,
            "intro": intro,
            "books": Book.objects.select_related("author", "publisher")[:10],
        },
    )


@staff_member_required
def book_create(request):
    """Default: Django's autocomplete with the search box inside the field."""
    return _book_page(
        request,
        BookInlineSearchForm,
        "catalog:book_create",
        "Add a book",
        "Django's admin autocomplete endpoint with "
        "<code>AutocompleteSelectInline</code>: just start typing where the "
        "value goes — no second search box.",
    )


@staff_member_required
def book_create_dropdown(request):
    """Kept for comparison: stock AutocompleteSelect, search inside the dropdown."""
    return _book_page(
        request,
        BookForm,
        "catalog:book_create_dropdown",
        "Add a book — stock dropdown search",
        "Django's stock <code>AutocompleteSelect</code>, for comparison. Click "
        "the field and a separate search box opens inside the dropdown.",
    )


def book_create_datalist(request):
    """No Select2 and no staff permission: <input list> + <datalist>."""
    return _book_page(
        request,
        BookDatalistForm,
        "catalog:book_create_datalist",
        "Add a book — native datalist",
        "Plain HTML <code>&lt;input list&gt;</code> backed by a small JSON view. "
        "You type in the field and the browser shows its own suggestions. Works "
        "for anonymous users.",
    )


def model_search(request, model_name):
    """Small public JSON endpoint feeding the <datalist> version."""
    try:
        model, field = SEARCHABLE[model_name]
    except KeyError:
        raise Http404("Not searchable")

    term = request.GET.get("q", "").strip()
    queryset = model.objects.all()
    if term:
        queryset = queryset.filter(**{"%s__icontains" % field: term})
    return JsonResponse(
        {
            "results": [
                {"id": obj.pk, "text": getattr(obj, field)}
                for obj in queryset[:20]
            ]
        }
    )
