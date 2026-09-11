from django import forms
from django.contrib.admin.widgets import AutocompleteSelect


class AutocompleteSelectInline(AutocompleteSelect):
    """Django's own autocomplete, but you type inside the field itself.

    Select2 only puts its search box in the field when the underlying <select>
    is `multiple` (that is why the admin's many-to-many autocomplete already
    behaves this way). So we render the foreign key as a multiple select and let
    a few lines of JS keep exactly one selection: picking a new value replaces
    the old one.

    `Select.value_from_datadict()` still returns a single value, so a plain
    ModelChoiceField / ForeignKey keeps working unchanged.
    """

    allow_multiple_selected = True

    def __init__(self, *args, placeholder="Type to search…", **kwargs):
        self.placeholder = placeholder
        super().__init__(*args, **kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        # Keep `admin-autocomplete` so the admin's own autocomplete.js
        # initializes Select2 and its CSS applies; the extra class is only a
        # hook for the "keep one value" handler.
        attrs["class"] += " inline-autocomplete"
        attrs["data-placeholder"] = self.placeholder
        # An empty `multiple` select has no intrinsic width, so Select2's
        # width: "resolve" would collapse the box; match the admin's 20em.
        attrs.setdefault("data-width", "20em")
        return attrs

    def value_from_datadict(self, data, files, name):
        """Collapse the `multiple` select back to a single value."""
        value = super().value_from_datadict(data, files, name)
        if isinstance(value, (list, tuple)):
            return value[-1] if value else None
        return value

    @property
    def media(self):
        # Append to the admin's ordered list: our script needs jQuery to have
        # loaded first, and plain Media merging would not guarantee the order.
        base = super().media
        return forms.Media(
            css=base._css, js=[*base._js, "catalog/js/inline_autocomplete.js"]
        )


class DatalistInput(forms.TextInput):
    """No Select2 at all: a plain <input list="..."> plus a <datalist>.

    The browser draws the suggestions under the field you are already typing in.
    A small script refills the <datalist> from a JSON view as you type, so it
    works with big tables and needs no staff permissions.
    """

    template_name = "catalog/widgets/datalist.html"

    def __init__(self, source_url, attrs=None, min_length=1):
        self.source_url = source_url
        self.min_length = min_length
        super().__init__(attrs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs["list"] = "%s__list" % attrs.get("id", "datalist")
        attrs["autocomplete"] = "off"
        attrs["data-source-url"] = str(self.source_url)
        attrs["data-min-length"] = self.min_length
        attrs["class"] = ("%s datalist-autocomplete" % attrs.get("class", "")).strip()
        return attrs

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["list_id"] = context["widget"]["attrs"]["list"]
        return context

    @property
    def media(self):
        return forms.Media(js=["catalog/js/datalist_autocomplete.js"])
