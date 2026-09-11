from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.forms import ModelChoiceField


class ModelLookupField(ModelChoiceField):
    """ModelChoiceField whose HTML value is the typed label, not the primary key.

    Used with DatalistInput: the user types (and the browser suggests) the
    object's name, and the field turns that text back into the instance.
    """

    default_error_messages = {
        "invalid_choice": "“%(value)s” is not in the list. Pick one of the suggestions.",
    }

    def __init__(self, *args, lookup_field="name", **kwargs):
        self.lookup_field = lookup_field
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if hasattr(value, "_meta"):
            return self.label_from_instance(value)
        if value not in self.empty_values:
            try:
                obj = self.queryset.filter(pk=value).first()
            except (ValueError, TypeError, ValidationError):
                return value  # Re-displaying the raw text after a failed submit.
            if obj is not None:
                return self.label_from_instance(obj)
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return self.queryset.get(**{"%s__iexact" % self.lookup_field: str(value).strip()})
        except (self.queryset.model.DoesNotExist, MultipleObjectsReturned):
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )
