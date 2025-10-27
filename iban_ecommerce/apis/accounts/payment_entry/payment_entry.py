import frappe
from frappe.utils import nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

@frappe.whitelist()
def create_payment_entry(order_id=None):
    try:
        # 📥 Parse input data
        data = frappe.request.get_json()
        order_id = data.get("order_id")
        mode_of_payment = data.get("mode_of_payment")

        if not order_id or not mode_of_payment:
            return {
                "Status": "Failure",
                "Message": "Both 'order_id' and 'mode_of_payment' are required."
            }

        # 🔍 Find the Sales Order
        sales_order = frappe.db.get_value("Sales Order", {"po_no": order_id}, "name")
        if not sales_order:
            return {
                "Status": "Failure",
                "Message": f"No Sales Order found for ID: {order_id}"
            }

        # 🔍 Find the linked submitted Sales Invoice with outstanding amount
        invoice_row = frappe.db.sql("""
            SELECT si.name
            FROM `tabSales Invoice` si
            JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
            WHERE 
                sii.sales_order = %s
                AND si.docstatus = 1
                AND si.outstanding_amount > 0
            LIMIT 1
        """, (sales_order,), as_dict=True)

        if not invoice_row:
            return {
                "Status": "Failure",
                "Message": f"No Submitted Sales Invoice found linked to Sales Order {sales_order}"
            }

        invoice_name = invoice_row[0].name

        # 🧾 Create Payment Entry from the Sales Invoice
        payment_entry = get_payment_entry("Sales Invoice", invoice_name)

        # 🪙 Set missing fields
        payment_entry.mode_of_payment = mode_of_payment
        payment_entry.reference_no = invoice_name
        payment_entry.reference_date = nowdate()

        # Allow creation even if user lacks permission (for API usage)
        payment_entry.ignore_permissions = True

        # 💾 Save and submit
        payment_entry.insert()
        payment_entry.submit()

        return {
            "status": "Success",
            "payment_entry": payment_entry.name,
            "invoice": invoice_name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Create Payment Entry Error")
        return {"status": "Failure", "error": str(e)}
