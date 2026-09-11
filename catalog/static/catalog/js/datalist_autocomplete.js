"use strict";
// Refill each <datalist> from its JSON source while the user types in the field.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input.datalist-autocomplete").forEach((input) => {
        const list = document.getElementById(input.getAttribute("list"));
        const url = input.dataset.sourceUrl;
        const minLength = parseInt(input.dataset.minLength || "1", 10);
        let timer = null;
        let controller = null;

        const refresh = async () => {
            const term = input.value.trim();
            if (term.length < minLength) {
                list.replaceChildren();
                return;
            }
            if (controller) {
                controller.abort();
            }
            controller = new AbortController();
            try {
                const response = await fetch(
                    `${url}?q=${encodeURIComponent(term)}`,
                    {signal: controller.signal, headers: {"X-Requested-With": "XMLHttpRequest"}}
                );
                const data = await response.json();
                list.replaceChildren(
                    ...data.results.map((item) => {
                        const option = document.createElement("option");
                        option.value = item.text;
                        return option;
                    })
                );
            } catch (error) {
                if (error.name !== "AbortError") {
                    throw error;
                }
            }
        };

        input.addEventListener("input", () => {
            clearTimeout(timer);
            timer = setTimeout(refresh, 200);
        });
    });
});
