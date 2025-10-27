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
    # Create Sales Invoice
    create_sales_invoice(doc)

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
        invoice.ignore_permissions = True
        invoice.insert()
        invoice.submit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Create Sales Invoice Error")