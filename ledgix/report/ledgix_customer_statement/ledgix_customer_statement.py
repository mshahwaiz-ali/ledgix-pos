# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	if not filters.get("customer"):
		return columns, [], "<div style='padding:20px;text-align:center;color:#667085'>Please select a customer to view statement.</div>", None, []

	data = get_data(filters)
	summary = get_report_summary(data)
	message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No customer statement data found for selected filters.</div>"
	return columns, data, message, None, summary


def get_columns():
	return [
		{"label":"Date","fieldname":"posting_date","fieldtype":"Date","width":120},
		{"label":"Type","fieldname":"reference_doctype","fieldtype":"Data","width":150},
		{"label":"Reference","fieldname":"reference_name","fieldtype":"Dynamic Link","options":"reference_doctype","width":145},
		{"label":"Invoice No","fieldname":"invoice_number","fieldtype":"Data","width":125},
		{"label":"Details","fieldname":"details","fieldtype":"Data","width":215},
		{"label":"Debit","fieldname":"debit","fieldtype":"Currency","width":120},
		{"label":"Credit","fieldname":"credit","fieldtype":"Currency","width":120},
		{"label":"Balance","fieldname":"balance","fieldtype":"Currency","width":125},
	]


def get_data(filters):
	opening_balance = get_opening_balance(filters)
	transactions = get_transactions(filters)
	data = []
	running_balance = opening_balance
	if opening_balance:
		data.append({
			"posting_date": filters.get("from_date"), "reference_doctype":"Opening Balance", "reference_name":"",
			"invoice_number":"", "details":"Balance before selected period",
			"debit": opening_balance if opening_balance > 0 else 0,
			"credit": abs(opening_balance) if opening_balance < 0 else 0,
			"balance": opening_balance, "is_opening":1,
		})
	for row in transactions:
		running_balance += flt(row.get("debit")) - flt(row.get("credit"))
		row["balance"] = running_balance
		data.append(row)
	return data


def _date_clause(field, filters):
	parts = []
	if filters.get("from_date"):
		parts.append(f"AND {field} >= %(from_date)s")
	if filters.get("to_date"):
		parts.append(f"AND {field} <= %(to_date)s")
	return "\n".join(parts)


def get_transactions(filters):
	sales = frappe.db.sql(f"""
		SELECT s.sale_date posting_date, 'Ledgix Sale' reference_doctype, s.name reference_name,
			s.invoice_number, CONCAT('Sale · ', IFNULL(s.sale_channel, 'Retail')) details,
			IFNULL(NULLIF(s.grand_total, 0), s.total_amount) debit, 0 credit, s.creation sort_time
		FROM `tabLedgix Sale` s
		WHERE s.docstatus=1 AND s.customer=%(customer)s {_date_clause('s.sale_date', filters)}
	""", filters, as_dict=True)

	returns = frappe.db.sql(f"""
		SELECT DATE(sr.creation) posting_date, 'Ledgix Sales Return' reference_doctype, sr.name reference_name,
			'' invoice_number, CONCAT('Return against ', IFNULL(sr.original_sale, '-')) details,
			0 debit, IFNULL(NULLIF(sr.grand_total, 0), sr.total_amount) credit, sr.creation sort_time
		FROM `tabLedgix Sales Return` sr
		LEFT JOIN `tabLedgix Sale` s ON s.name=sr.original_sale
		WHERE sr.docstatus=1 AND (s.customer=%(customer)s OR sr.customer=%(customer)s)
		{_date_clause('DATE(sr.creation)', filters)}
	""", filters, as_dict=True)

	payments = []
	if frappe.db.exists("DocType", "Ledgix Payment"):
		payments = frappe.db.sql(f"""
			SELECT DATE(p.payment_date) posting_date, 'Ledgix Payment' reference_doctype, p.name reference_name,
				'' invoice_number,
				CASE WHEN IFNULL(p.reversal_of, '')='' THEN CONCAT('Payment · ', p.payment_method)
				ELSE CONCAT('Payment reversal · ', p.payment_method) END details,
				CASE WHEN IFNULL(p.reversal_of, '')<>'' THEN IFNULL(p.amount,0) ELSE 0 END debit,
				CASE WHEN IFNULL(p.reversal_of, '')='' THEN IFNULL(p.amount,0) ELSE 0 END credit,
				p.creation sort_time
			FROM `tabLedgix Payment` p
			WHERE p.docstatus=1 AND p.customer=%(customer)s {_date_clause('DATE(p.payment_date)', filters)}
		""", filters, as_dict=True)

	rows = sales + returns + payments
	rows.sort(key=lambda row: (row.get("posting_date") or "", row.get("sort_time") or "", row.get("reference_name") or ""))
	return rows


def get_opening_balance(filters):
	if not filters.get("from_date"):
		return 0
	values = {"customer": filters.get("customer"), "from_date": filters.get("from_date")}
	sale_debit = frappe.db.sql("""
		SELECT IFNULL(SUM(IFNULL(NULLIF(grand_total,0),total_amount)),0)
		FROM `tabLedgix Sale` WHERE docstatus=1 AND customer=%(customer)s AND sale_date<%(from_date)s
	""", values)[0][0]
	return_credit = frappe.db.sql("""
		SELECT IFNULL(SUM(IFNULL(NULLIF(sr.grand_total,0),sr.total_amount)),0)
		FROM `tabLedgix Sales Return` sr LEFT JOIN `tabLedgix Sale` s ON s.name=sr.original_sale
		WHERE sr.docstatus=1 AND (s.customer=%(customer)s OR sr.customer=%(customer)s) AND DATE(sr.creation)<%(from_date)s
	""", values)[0][0]
	payment_credit = 0
	payment_reversal = 0
	if frappe.db.exists("DocType", "Ledgix Payment"):
		row = frappe.db.sql("""
			SELECT
				IFNULL(SUM(CASE WHEN IFNULL(reversal_of,'')='' THEN amount ELSE 0 END),0) credit,
				IFNULL(SUM(CASE WHEN IFNULL(reversal_of,'')<>'' THEN amount ELSE 0 END),0) reversal
			FROM `tabLedgix Payment`
			WHERE docstatus=1 AND customer=%(customer)s AND DATE(payment_date)<%(from_date)s
		""", values, as_dict=True)[0]
		payment_credit = flt(row.credit)
		payment_reversal = flt(row.reversal)
	return flt(sale_debit) + payment_reversal - flt(return_credit) - payment_credit


def get_report_summary(data):
	rows = [row for row in data if not row.get("is_opening")]
	return [
		{"value":len(rows),"label":"Transactions","datatype":"Int"},
		{"value":sum(flt(row.get("debit")) for row in rows),"label":"Debit","datatype":"Currency"},
		{"value":sum(flt(row.get("credit")) for row in rows),"label":"Credit","datatype":"Currency"},
		{"value":data[-1].get("balance") if data else 0,"label":"Closing Balance","datatype":"Currency"},
	]
