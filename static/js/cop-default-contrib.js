/**
 * COP display for the profile default contribution field.
 * Visible field shows COP currency; hidden field stores a plain number.
 * Requires cop-format.js (window.formatCOP / window.parseCOP).
 */
(function () {
    function syncToHidden(wrap) {
        var hidden = wrap.querySelector('input[type="hidden"][name="default_contribution_amount"]');
        var visible = wrap.querySelector(".js-cop-default-visible");
        if (!hidden || !visible) return;
        var n = parseCOP(visible.value);
        hidden.value = n === null ? "" : String(n);
    }

    function applyFormatted(wrap) {
        var hidden = wrap.querySelector('input[type="hidden"][name="default_contribution_amount"]');
        var visible = wrap.querySelector(".js-cop-default-visible");
        if (!hidden || !visible) return;
        var raw = hidden.value.trim();
        if (!raw) { visible.value = ""; return; }
        var n = parseFloat(raw);
        if (!Number.isFinite(n)) { visible.value = ""; return; }
        visible.value = formatCOP(n);
    }

    function wire(wrap) {
        var visible = wrap.querySelector(".js-cop-default-visible");
        if (!visible || visible.dataset.copWired === "1") return;
        visible.dataset.copWired = "1";

        visible.addEventListener("focus", function () {
            var hidden = wrap.querySelector('input[type="hidden"][name="default_contribution_amount"]');
            if (!hidden) return;
            var raw = hidden.value.trim();
            if (!raw) { visible.value = ""; return; }
            var n = parseFloat(raw);
            visible.value = Number.isFinite(n) ? String(n) : "";
        });

        visible.addEventListener("blur", function () {
            syncToHidden(wrap);
            applyFormatted(wrap);
        });
    }

    function init(root) {
        var scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll("[data-cop-default-contrib]").forEach(function (wrap) {
            wire(wrap);
            applyFormatted(wrap);
        });
    }

    document.addEventListener("DOMContentLoaded", function () { init(document); });
    document.body.addEventListener("htmx:afterSwap", function (evt) { init(evt.detail.target); });
    document.body.addEventListener("htmx:configRequest", function (evt) {
        var elt = evt.detail.elt;
        var form = elt && elt.tagName === "FORM" ? elt : elt && elt.closest ? elt.closest("form") : null;
        if (!form) return;
        var wrap = form.querySelector("[data-cop-default-contrib]");
        if (wrap) syncToHidden(wrap);
    });
})();
