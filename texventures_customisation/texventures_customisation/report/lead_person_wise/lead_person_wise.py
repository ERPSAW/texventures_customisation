# Copyright (c) 2026, SAW India and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, getdate, today

# =========================================================
# EXECUTE
# =========================================================

def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_report_data(filters)

	return columns, data


# =========================================================
# COLUMNS
# =========================================================

def get_columns():
	return [
		{
			"label": "Lead Person",
			"fieldname": "lead_person",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Sales Person",
			"fieldname": "sales_person",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Party",
			"fieldname": "party",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": "Invoice No",
			"fieldname": "invoice_no",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 150,
		},
		{
			"label": "Invoice Date",
			"fieldname": "invoice_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": "Bill Amount",
			"fieldname": "bill_amt",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Part Payment",
			"fieldname": "part_payment",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Balance",
			"fieldname": "balance",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Balance Total",
			"fieldname": "balance_total",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Due Date",
			"fieldname": "due_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": "Due Days",
			"fieldname": "due_days",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": "Payment Term Days",
			"fieldname": "payment_term_days",
			"fieldtype": "Int",
			"width": 140,
		},
	]


# =========================================================
# GET REPORT DATA
# =========================================================

def get_report_data(filters):

	# =====================================================
	# CONDITIONS
	# =====================================================

	conditions = """
		si.docstatus = 1
		AND si.is_return = 0
		AND si.outstanding_amount > 0
	"""

	values = {}

	# =====================================================
	# COMPANY FILTER
	# =====================================================

	if filters.get("company"):
		conditions += """
			AND si.company = %(company)s
		"""
		values["company"] = filters["company"]

	# =====================================================
	# SALES INVOICE FILTER
	# =====================================================

	if filters.get("sales_invoice"):
		conditions += """
			AND si.name = %(sales_invoice)s
		"""
		values["sales_invoice"] = filters["sales_invoice"]

	# =====================================================
	# TERRITORY FILTER
	# =====================================================

	if filters.get("territory"):
		conditions += """
			AND si.territory = %(territory)s
		"""
		values["territory"] = filters["territory"]

	# =====================================================
	# CUSTOMER FILTER
	# =====================================================

	if filters.get("customer"):
		conditions += """
			AND si.customer = %(customer)s
		"""
		values["customer"] = filters["customer"]

	# =====================================================
	# LEAD PERSON FILTER
	# =====================================================

	if filters.get("lead_person"):

		conditions += """
			AND si.sales_partner = %(lead_person)s
		"""
		values["lead_person"] = filters["lead_person"]

	# =====================================================
	# SALES PERSON FILTER
	# =====================================================

	if filters.get("sales_person"):

		if filters["sales_person"] == "Undefined":
			conditions += """
				AND (
					st.sales_person IS NULL
					OR TRIM(st.sales_person) = ''
				)
			"""
		else:
			conditions += """
				AND st.sales_person = %(sales_person)s
			"""
			values["sales_person"] = filters["sales_person"]

	# =====================================================
	# FETCH SALES INVOICES
	# =====================================================

	invoices = frappe.db.sql(
		f"""
		SELECT
			si.name AS invoice_no,
			si.posting_date AS invoice_date,
			si.customer,
			si.sales_partner,
			si.grand_total AS grand_total,
			si.outstanding_amount,

			COALESCE(
				NULLIF(TRIM(st.sales_person), ''),
				'Undefined'
			) AS sales_person,

			COALESCE(
				si.due_date,
				si.posting_date
			) AS due_date

		FROM `tabSales Invoice` si

		LEFT JOIN `tabSales Team` st
			ON st.parent = si.name
			AND st.parenttype = 'Sales Invoice'

		WHERE {conditions}

		ORDER BY
			CASE
				WHEN st.sales_person IS NULL
					OR TRIM(st.sales_person) = ''
				THEN 1
				ELSE 0
			END,
			st.sales_person,
			si.customer,
			si.posting_date,
			si.name
		""",
		values,
		as_dict=1,
	)

	# =====================================================
	# BUILD HIERARCHY
	#
	# Lead Person
	#     Sales Person
	#         Customer
	#             Invoice
	# =====================================================

	hierarchy = {}

	for row in invoices:

		# -------------------------------------------------
		# SALES PERSON
		# -------------------------------------------------

		sales_person = (row.sales_person or "").strip()

		if not sales_person:
			sales_person = "Undefined"

		# -------------------------------------------------
		# LEAD PERSON
		# -------------------------------------------------

		# Lead Person comes directly from Sales Invoice.sales_partner.
		lead_person = (row.sales_partner or "").strip()

		if not lead_person:
			lead_person = "Undefined"

		# -------------------------------------------------
		# CUSTOMER
		# -------------------------------------------------

		customer = (row.customer or "").strip()

		if not customer:
			customer = "Undefined"

		# -------------------------------------------------
		# CREATE LEAD PERSON
		# -------------------------------------------------

		if lead_person not in hierarchy:
			hierarchy[lead_person] = {}

		# -------------------------------------------------
		# CREATE SALES PERSON
		# -------------------------------------------------

		if sales_person not in hierarchy[lead_person]:
			hierarchy[lead_person][sales_person] = {}

		# -------------------------------------------------
		# CREATE CUSTOMER
		# -------------------------------------------------

		if customer not in hierarchy[lead_person][sales_person]:
			hierarchy[lead_person][sales_person][customer] = []

		# -------------------------------------------------
		# ADD INVOICE
		# -------------------------------------------------

		hierarchy[lead_person][sales_person][customer].append(row)

	# =====================================================
	# REPORT DATA
	# =====================================================

	data = []

	# =====================================================
	# OVERALL TOTALS
	# =====================================================

	overall_bill = 0
	overall_part_payment = 0
	overall_balance = 0

	# =====================================================
	# LEAD PERSON LOOP
	# =====================================================

	for lead_person in sorted(hierarchy):

		# -------------------------------------------------
		# LEAD TOTALS
		# -------------------------------------------------

		lead_bill = 0
		lead_part_payment = 0
		lead_balance = 0

		# -------------------------------------------------
		# CALCULATE LEAD TOTALS
		# -------------------------------------------------

		for sales_person in hierarchy[lead_person]:

			for customer in hierarchy[lead_person][sales_person]:

				for invoice in hierarchy[
					lead_person
				][sales_person][customer]:

					bill_amt = invoice.grand_total or 0

					balance = invoice.outstanding_amount or 0

					part_payment = bill_amt - balance

					if part_payment < 0:
						part_payment = 0

					lead_bill += bill_amt
					lead_part_payment += part_payment
					lead_balance += balance

		# =================================================
		# LEAD PERSON ROW
		# =================================================

		data.append(
			{
				"lead_person": lead_person,
				"indent": 0,
				"is_group": 1,
				"row_type": "Lead Person",
			}
		)

		# =================================================
		# SALES PERSON LOOP
		# =================================================

		for sales_person in sorted(hierarchy[lead_person]):

			# -------------------------------------------------
			# SALES PERSON TOTALS
			# -------------------------------------------------

			broker_bill = 0
			broker_part_payment = 0
			broker_balance = 0

			# -------------------------------------------------
			# CALCULATE SALES PERSON TOTALS
			# -------------------------------------------------

			for customer in hierarchy[lead_person][sales_person]:

				for invoice in hierarchy[
					lead_person
				][sales_person][customer]:

					bill_amt = invoice.grand_total or 0

					balance = invoice.outstanding_amount or 0

					part_payment = bill_amt - balance

					if part_payment < 0:
						part_payment = 0

					broker_bill += bill_amt
					broker_part_payment += part_payment
					broker_balance += balance

			# =================================================
			# SALES PERSON ROW
			# =================================================

			data.append(
				{
					"sales_person": sales_person,
					"indent": 1,
					"is_group": 1,
					"row_type": "Sales Person",
				}
			)

			# =================================================
			# CUSTOMER LOOP
			# =================================================

			for customer in sorted(
				hierarchy[lead_person][sales_person]
			):

				# -------------------------------------------------
				# CUSTOMER TOTALS
				# -------------------------------------------------

				customer_bill = 0
				customer_part_payment = 0
				customer_balance = 0

				# -------------------------------------------------
				# RUNNING BALANCE
				#
				# Resets for every customer.
				# -------------------------------------------------

				running_balance = 0

				# -------------------------------------------------
				# CALCULATE CUSTOMER TOTALS
				# -------------------------------------------------

				for invoice in hierarchy[
					lead_person
				][sales_person][customer]:

					bill_amt = invoice.grand_total or 0

					balance = invoice.outstanding_amount or 0

					part_payment = bill_amt - balance

					if part_payment < 0:
						part_payment = 0

					customer_bill += bill_amt
					customer_part_payment += part_payment
					customer_balance += balance

				# =================================================
				# CUSTOMER / PARTY ROW
				# =================================================

				data.append(
					{
						"party": customer,
						"indent": 2,
						"is_group": 1,
						"row_type": "Customer",
					}
				)

				# =================================================
				# INVOICE LOOP
				# =================================================

				for invoice in hierarchy[
					lead_person
				][sales_person][customer]:

					# -------------------------------------------------
					# AMOUNTS
					# -------------------------------------------------

					bill_amt = invoice.grand_total or 0

					balance = invoice.outstanding_amount or 0

					part_payment = bill_amt - balance

					if part_payment < 0:
						part_payment = 0

					# -------------------------------------------------
					# CUSTOMER RUNNING BALANCE
					#
					# Invoice 1 = 10,000 -> 10,000
					# Invoice 2 =  5,000 -> 15,000
					# Invoice 3 =  2,000 -> 17,000
					#
					# New customer starts from 0.
					# -------------------------------------------------

					running_balance += balance

					# =================================================
					# DUE DAYS
					# =================================================

					due_date = getdate(invoice.due_date)

					today_date = getdate(today())

					due_days = date_diff(
						today_date,
						due_date
					)

					if due_days < 0:
						due_days = 0

					# =================================================
					# PAYMENT TERM DAYS
					# =================================================

					payment_term_days = date_diff(
						due_date,
						getdate(invoice.invoice_date)
					)

					if payment_term_days < 0:
						payment_term_days = 0

					# =================================================
					# INVOICE ROW
					# =================================================

					data.append(
						{
							"invoice_no": invoice.invoice_no,
							"invoice_date": invoice.invoice_date,
							"bill_amt": bill_amt,
							"part_payment": part_payment,
							"balance": balance,
							"balance_total": running_balance,
							"due_date": due_date,
							"due_days": due_days,
							"payment_term_days": payment_term_days,
							"indent": 3,
							"is_group": 0,
							"row_type": "Invoice",
						}
					)

				# =================================================
				# CUSTOMER TOTAL
				# =================================================

				data.append(
					{
						"party": "Total",
						"bill_amt": customer_bill,
						"part_payment": customer_part_payment,
						"balance": customer_balance,
						"balance_total": customer_balance,
						"indent": 2,
						"is_group": 0,
						"row_type": "Customer Total",
					}
				)

			# =================================================
			# SALES PERSON GRAND TOTAL
			# =================================================

			data.append(
				{
					"sales_person": "Grand Total",
					"bill_amt": broker_bill,
					"part_payment": broker_part_payment,
					"balance": broker_balance,
					"balance_total": broker_balance,
					"indent": 1,
					"is_group": 0,
					"row_type": "Sales Person Total",
				}
			)

		# =================================================
		# LEAD PERSON GRAND TOTAL
		# =================================================

		data.append(
			{
				"lead_person": "Grand Total",
				"bill_amt": lead_bill,
				"part_payment": lead_part_payment,
				"balance": lead_balance,
				"balance_total": lead_balance,
				"indent": 0,
				"is_group": 0,
				"row_type": "Lead Person Total",
			}
		)

		# =================================================
		# OVERALL TOTAL
		# =================================================

		overall_bill += lead_bill
		overall_part_payment += lead_part_payment
		overall_balance += lead_balance

	# =====================================================
	# OVERALL GRAND TOTAL
	# =====================================================

	data.append(
		{
			"lead_person": "Overall Grand Total",
			"bill_amt": overall_bill,
			"part_payment": overall_part_payment,
			"balance": overall_balance,
			"balance_total": overall_balance,
			"indent": 0,
			"is_group": 0,
			"row_type": "Grand Total",
		}
	)

	return data
