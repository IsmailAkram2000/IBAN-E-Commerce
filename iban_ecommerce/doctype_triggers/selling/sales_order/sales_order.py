import frappe
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def before_insert(doc, method=None):
    pass
@frappe.whitelist()
def after_insert(doc, method=None):
    pass
@frappe.whitelist()
def onload(doc, method=None):
    pass
@frappe.whitelist()
def before_validate(doc, method=None):
    pass
@frappe.whitelist()
def validate(doc, method=None):
    pass
@frappe.whitelist()
def on_submit(doc, method=None):
    pass
@frappe.whitelist()
def on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def before_save(doc, method=None):
    pass
@frappe.whitelist()
def before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def on_update(doc, method=None):
    pass

def create_sales_invoice(sales_order):
    try:
        invoice = get_mapped_doc(
            "Sales Order",
            sales_order.name,
            {
                "Sales Order": {
                    "doctype": "Sales Invoice",
                    "field_map": {
                        "name": "sales_order",
                        "transaction_date": "posting_date",
                    },
                    "validation": {
                        "docstatus": ["=", 1],
                    },
                },
                "Sales Order Item": {
                    "doctype": "Sales Invoice Item",
                    "field_map": {
                        "name": "so_detail",
                        "parent": "sales_order",
                        "sales_order": "sales_order",
                    },
                },
            },
            target_doc=None,
        )

        # Set mandatory values
        invoice.due_date = frappe.utils.nowdate()
        invoice.update_stock = 1
        invoice.is_pos = 1

        # Collect unique (account_head, rate) pairs from Item Tax Templates
        tax_map = set()
        
        for row in invoice.items:
            item_tax_template = row.item_tax_template = frappe.get_value("Item Tax", {
                "parent": row.item_code,
            }, "item_tax_template") or "الضريبة القياسية %15 - ذهول"
            row.item_tax_template = item_tax_template 

            if item_tax_template:
                taxes = frappe.get_all(
                    "Item Tax Template Detail",
                    filters={"parent": item_tax_template},
                    fields=["tax_type", "tax_rate"],
                )
                for t in taxes:
                    tax_map.add((t.tax_type, float(t.tax_rate)))

        # Add unique tax rows to invoice
        for tax_type, tax_rate in tax_map:
            invoice.append("taxes", {
                "charge_type": "On Net Total",
                "account_head": tax_type,
                "rate": tax_rate,
                "description": tax_type,
            })

        invoice.set_missing_values()
        invoice.calculate_taxes_and_totals()

        mode_of_payment = sales_order.custom_mode_of_payment
        account = frappe.get_value('Mode of Payment Account', {
            "parent": mode_of_payment,
            "company": sales_order.company,
        }, "default_account")

        if mode_of_payment:
            invoice.append("payments", {
                "mode_of_payment": mode_of_payment,
                "account": account,
                "amount": max(invoice.grand_total or 0, invoice.rounded_total or 0)
            })
        
        invoice.ignore_permissions = True
        invoice.insert()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Create Sales Invoice Error")