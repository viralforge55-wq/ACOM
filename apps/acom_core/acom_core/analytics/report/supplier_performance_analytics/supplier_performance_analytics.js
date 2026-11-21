// Copyright (c) 2026, ACOM and contributors
// For license information, please see license.txt

frappe.query_reports["Supplier Performance Analytics"] = {
    filters: [
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier"
        }
    ]
};
