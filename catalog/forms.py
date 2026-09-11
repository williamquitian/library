from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.urls import reverse_lazy

from .fields import ModelLookupField
from .models import Author, Book, Publisher
from .widgets import AutocompleteSelectInline, DatalistInput


class BookForm(forms.ModelForm):
    """Regular (non-admin) ModelForm reusing Django's built-in autocomplete widget.

    AutocompleteSelect talks to the admin's `admin:autocomplete` endpoint, so the
    target models must be registered with `search_fields` (see catalog/admin.py)
    and the user must be staff with view permission on them.

    Select2 renders a single select with its search box *inside the dropdown*.
    """

    class Meta:
        model = Book
        fields = ["title", "author", "publisher", "published"]
        widgets = {
            "author": AutocompleteSelect(
                Book._meta.get_field("author"), admin.site, attrs={"data-width": "100%"}
            ),
            "publisher": AutocompleteSelect(
                Book._meta.get_field("publisher"), admin.site, attrs={"data-width": "100%"}
            ),
        }


class BookInlineSearchForm(BookForm):
    """Same endpoint and widget family, but you type in the field itself."""

    class Meta(BookForm.Meta):
        widgets = {
            "author": AutocompleteSelectInline(
                Book._meta.get_field("author"),
                admin.site,
                attrs={"data-width": "100%"},
                placeholder="Type an author’s name…",
            ),
            "publisher": AutocompleteSelectInline(
                Book._meta.get_field("publisher"),
                admin.site,
                attrs={"data-width": "100%"},
                placeholder="Type a publisher…",
            ),
        }


class BookDatalistForm(forms.ModelForm):
    """No Select2, no admin permissions: <input list> + <datalist>."""

    author = ModelLookupField(
        queryset=Author.objects.all(),
        widget=DatalistInput(reverse_lazy("catalog:model_search", args=["author"])),
    )
    publisher = ModelLookupField(
        queryset=Publisher.objects.all(),
        required=False,
        widget=DatalistInput(reverse_lazy("catalog:model_search", args=["publisher"])),
    )

    class Meta:
        model = Book
        fields = ["title", "author", "publisher", "published"]
