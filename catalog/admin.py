from django.contrib import admin

from .models import Author, Book, Publisher
from .widgets import AutocompleteSelectInline


class InlineAutocompleteMixin:
    """Make `autocomplete_fields` search inside the field instead of the dropdown."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if "widget" not in kwargs and db_field.name in self.get_autocomplete_fields(request):
            kwargs["widget"] = AutocompleteSelectInline(
                db_field, self.admin_site, using=kwargs.get("using")
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    # search_fields is what makes Author usable as an autocomplete target:
    # the admin autocomplete endpoint searches these fields.
    search_fields = ["name", "country"]
    list_display = ["name", "country"]


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Book)
class BookAdmin(InlineAutocompleteMixin, admin.ModelAdmin):
    # Built-in Select2 autocomplete for the foreign keys (no third-party package).
    autocomplete_fields = ["author", "publisher"]
    list_display = ["title", "author", "publisher", "published"]
    list_select_related = ["author", "publisher"]
    search_fields = ["title"]
