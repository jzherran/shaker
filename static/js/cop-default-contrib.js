/**
 * Colombian peso (COP) display for the profile default contribution field.
 * Visible field shows es-CO currency; hidden field stores a plain number for the API.
 */
(function () {
    var copFmt = new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
    });

    function formatCOP(n) {
        if (n === null || n === undefined || n === "") return "";
        var num = Number(n);
        if (!Number.isFinite(num)) return "";
        return copFmt.format(num);
    }

    function parseCOP(input) {
        if (input == null) return null;
        var s = String(input).trim();
        if (!s) return null;
        s = s.replace(/\$/g, "").replace(/\u00a0/g, " ").replace(/\s/g, "").replace(/COP/gi, "").trim();
        if (!s) return null;
        var hasComma = s.indexOf(",") >= 0;
        if (hasComma) {
            s = s.replace(/\./g, "").replace(",", ".");
        } else {
            var parts = s.split(".");
            if (parts.length > 2) {
                s = parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
            } else if (parts.length === 2 && parts[1].length <= 2) {
                s = parts[0] + "." + parts[1];
            } else {
                s = s.replace(/\./g, "");
            }
        }
        var n = parseFloat(s);
        return Number.isFinite(n) ? n : null;
    }

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
        if (!raw) {
            visible.value = "";
            return;
        }
        var n = parseFloat(raw);
        if (!Number.isFinite(n)) {
            visible.value = "";
            return;
        }
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
            if (!raw) {
                visible.value = "";
                return;
            }
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

    document.addEventListener("DOMContentLoaded", function () {
        init(document);
    });

    document.body.addEventListener("htmx:afterSwap", function (evt) {
        init(evt.detail.target);
    });

    document.body.addEventListener("htmx:configRequest", function (evt) {
        var elt = evt.detail.elt;
        var form = elt && elt.tagName === "FORM" ? elt : elt && elt.closest ? elt.closest("form") : null;
        if (!form) return;
        var wrap = form.querySelector("[data-cop-default-contrib]");
        if (wrap) syncToHidden(wrap);
    });
})();
