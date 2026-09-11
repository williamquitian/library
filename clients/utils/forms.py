from django.db.models import Model
from typing import Type
from clients.models import Country  

def get_country_choices(model: Type[Model], country_field_name: str = 'country'):
    """
    Returns a list of (id, name) tuples with:
    - Countries used in the given model's country_field_name
    - A delimiter
    - All other countries
    """
    from django.db.models import F

    used_country_ids = model.objects.values_list(f"{country_field_name}_id", flat=True).distinct()

    used_countries = Country.objects.filter(id__in=used_country_ids).order_by('name')
    all_countries = Country.objects.exclude(id__in=used_country_ids).order_by('name')

    choices = [('', '---------')]
    choices += [(c.id, c.name) for c in used_countries]

    if used_countries and all_countries:
        choices.append(('', '---------'))  # or '---- All Countries ----'

    choices += [(c.id, c.name) for c in all_countries]

    return choices