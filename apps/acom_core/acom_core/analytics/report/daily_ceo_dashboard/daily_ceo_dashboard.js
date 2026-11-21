// Copyright (c) 2026, ACOM and contributors
// For license information, please see license.txt

frappe.query_reports["Daily CEO Dashboard"] = {
    filters: [
        {
            fieldname: "period",
            label: __("Period"),
            fieldtype: "Select",
            options: "today\nall_time\ncustom",
            default: "today"
        },
        {
            fieldname: "date_from",
            label: __("From Date"),
            fieldtype: "Date",
            depends_on: "eval:doc.period=='custom'"
        },
        {
            fieldname: "date_to",
            label: __("To Date"),
            fieldtype: "Date",
            depends_on: "eval:doc.period=='custom'"
        }
    ]
};
