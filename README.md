# Django autocomplete demo

A minimal Django project showing the **autocomplete that ships with Django itself**
(`ModelAdmin.autocomplete_fields` / `django.contrib.admin.widgets.AutocompleteSelect`,
backed by the admin's `admin:autocomplete` JSON endpoint and the bundled Select2).
No third-party packages.

The app defaults to typing **inside the field** rather than in a separate search box
inside the dropdown — see below.

## Run

```bash
.venv/bin/python manage.py runserver 8010
```

- `/books/add/` — the standalone page (type in the field).
- `/admin/catalog/book/add/` — the admin form, same behaviour.
- `/books/add/dropdown/` — comparison: Django's stock `AutocompleteSelect`.
- `/books/add/datalist/` — comparison: native `<input list>` + `<datalist>`, public.
- Login: `admin` / `admin` (created locally, dev only)

Sample data: `.venv/bin/python manage.py seed_catalog`
Tests: `.venv/bin/python manage.py test catalog` (14 tests)

## How it works

1. `catalog/admin.py` — `AuthorAdmin`/`PublisherAdmin` declare `search_fields`.
   That is what makes a model a valid autocomplete *target*: the admin endpoint
   `/admin/autocomplete/` searches exactly those fields.
2. `BookAdmin.autocomplete_fields = ["author", "publisher"]` turns those foreign
   keys into searchable Select2 boxes.
3. `catalog/forms.py` — `BookForm`/`BookInlineSearchForm` reuse the same widgets on
   a plain `ModelForm` outside the admin.
4. `catalog/templates/catalog/book_form.html` renders `{{ form.media }}`, which pulls
   in jQuery, Select2 and `admin/js/autocomplete.js` from the admin's static files.

## Typing in the field instead of in the dropdown

Select2 only renders its search box *inside the selection* when the underlying
`<select>` is `multiple` — which is why the admin's many-to-many autocomplete already
behaves that way and the single foreign key one does not.

`AutocompleteSelectInline` ([catalog/widgets.py](catalog/widgets.py)) is the whole
trick, and it changes three things on Django's `AutocompleteSelect`:

| Override | Why |
| --- | --- |
| `allow_multiple_selected = True` | Renders `<select multiple>`, so Select2 puts the search box in the field. |
| `value_from_datadict()` | `ChoiceWidget` returns a *list* for multiple selects; collapse it back to one value so a plain `ModelChoiceField` / `ForeignKey` keeps working. |
| `build_attrs()` | Adds an `inline-autocomplete` hook class and a default `data-width` (an empty `multiple` select has no intrinsic width, so Select2's `width: "resolve"` would collapse the box). |

The stock `admin-autocomplete` class is deliberately kept, so **Select2 is still
initialized by the admin's own `autocomplete.js` and the admin's CSS still applies**.
The only custom script,
[inline_autocomplete.js](catalog/static/catalog/js/inline_autocomplete.js), is a single
delegated handler that keeps one value: selecting a new author replaces the previous
one instead of stacking (and, being delegated, it also covers admin inlines added
dynamically).

To use it in the admin, `InlineAutocompleteMixin` in [catalog/admin.py](catalog/admin.py)
passes the widget from `formfield_for_foreignkey()` — the `+ Add another` related-widget
links keep working, since the admin wraps whatever widget it is given.

Trade-off: the chosen value shows as a removable Select2 chip (`× Toni Morrison`)
instead of plain text. If you want a plain single-line input with no chip, the
alternative is a custom Select2 `selectionAdapter` decorated with
`select2/selection/search` — noticeably more JS, and not implemented here.

The `/books/add/datalist/` page keeps the other approach around for comparison: a
native `<input list>` + `<datalist>` ([DatalistInput](catalog/widgets.py) +
[ModelLookupField](catalog/fields.py)) with no JS library and no admin permissions.

## Note on permissions

`/admin/autocomplete/` requires a **staff** user with view permission on the target
model, so the Select2 pages are wrapped in `@staff_member_required`. The datalist page
shows the alternative: its own public JSON view (`catalog:model_search`), which is what
you would also point a Select2 widget at for an anonymous-facing form.
