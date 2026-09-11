"use strict";
// The widget renders a `multiple` select only so that Select2 puts its search
// box inside the field. Select2 itself is still initialized by the admin's own
// autocomplete.js; all we do is keep a single value, replacing the previous one
// instead of stacking. Delegated, so it also covers dynamically added inlines.
{
    const $ = django.jQuery;

    $(document).on("select2:select", "select.inline-autocomplete", function (event) {
        $(this).val([event.params.data.id]).trigger("change.select2");
    });
}
