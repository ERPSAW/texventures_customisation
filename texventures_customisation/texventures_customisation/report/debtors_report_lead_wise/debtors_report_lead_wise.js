// Copyright (c) 2026, SAWIndia and contributors
// For license information, please see license.txt

frappe.query_reports["Debtors Report Lead wise"] = {
	filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company")
        },
        {
            fieldname: "sales_invoice",
            label: __("Sales Invoice"),
            fieldtype: "Link",
            options: "Sales Invoice",
			get_query: function () {
				return {
					filters: {
						"docstatus": 1,
						"is_return": 0,
						"outstanding_amount": [">", 0]
					}
				}
			}
        },
        {
            fieldname: "lead_person",
            label: __("Lead Person"),
            fieldtype: "Link",
            options: "Sales Partner"
        },
        {
            fieldname: "sales_person",
            label: __("Sales Person"),
            fieldtype: "Link",
            options: "Sales Person"
        },
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory"
		},
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) {
            return value;
        }

        /*
         * GRAND TOTAL
         */
        if (
            data.party || data.sales_person || data.lead_person
        ) {
            return `<b>${value}</b>`;
        }

        if (data.due_days > data.payment_term_days && column.fieldname === "due_days") {
			value = `<span style="color: red; font-weight: bold;">${value}</span>`;
		} else if (data.due_days <= data.payment_term_days && column.fieldname === "due_days") {
			value = `<span style="color: green; font-weight: bold;">${value}</span>`;
		}

        return value;
    }
};
