// Copyright (c) 2026, ACOM and contributors
// For license information, please see license.txt

frappe.query_reports["Product Profitability Analytics"] = {
    filters: [
        {
            fieldname: "channel",
            label: __("Sales Channel"),
            fieldtype: "Select",
            options: "\nDROPSHIP\nAFFILIATE",
            default: ""
        },
        {
            fieldname: "date_from",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "date_to",
            label: __("To Date"),
            fieldtype: "Date"
        }
    ]
};
