/**
 * Global COP (Colombian Peso) formatting utilities.
 * Produces es-CO style: $ 1.234,56
 */
(function () {
    var fmt = new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
    });

    window.formatCOP = function (n) {
        if (n === null || n === undefined || n === "") return "$ 0";
        var num = Number(n);
        if (!Number.isFinite(num)) return "$ 0";
        return fmt.format(num);
    };

    window.parseCOP = function (input) {
        if (input == null) return null;
        var s = String(input).trim();
        if (!s) return null;
        s = s.replace(/\$/g, "").replace(/\u00a0/g, " ").replace(/\s/g, "")
             .replace(/COP/gi, "").trim();
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
        var num = parseFloat(s);
        return Number.isFinite(num) ? num : null;
    };
})();
