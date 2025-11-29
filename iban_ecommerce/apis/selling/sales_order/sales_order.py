import requests
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from iban_ecommerce.doctype_triggers.selling.sales_order.sales_order import create_sales_invoice

# 🌍 Base URL of your ERPNext/Frappe site
BASE_URL = "http://localhost:8000"
API_KEY = ""
API_SECRET = ""

@frappe.whitelist()
def create_sales_order():
    # 🔒 Ensure custom field exists before proceeding
    ensure_missing_fields()

    # 📥 Get JSON body from API request
    data = frappe.request.get_json()

    # ✅ Validate required fields
    validate_required_fields(data, ["customer", "set_warehouse", "items"])
    if not data.get("items") or not isinstance(data["items"], list):
        frappe.throw("Items list is required and must contain at least one item")
    for item in data["items"]:
        validate_required_fields(item, ["item_code", "qty", "rate"])

    # 🔎 Validate or create related documents
    data["items"] = validate_items(data["items"])

    # 📝 Ensure the correct doctype
    data["doctype"] = "Sales Order"

    # 📄 Create Sales Order document
    so_doc = frappe.get_doc(data)

    # if so_doc.custom_shipping_company:
    #     so_doc.custom_shipping_amount = frappe.get_value('Shipping Company', 'so_doc.custom_shipping_company', 'amount')

    # 🔢 Recalculate taxes and totals
    so_doc.run_method("set_missing_values")
    so_doc.run_method("set_taxes")

    # ✅ Fix missing ETA tax fields
    for tax in so_doc.taxes:
        if not tax.eta_tax_type:
            tax.eta_tax_type = "T1"  
        if not tax.eta_tax_sub_type:
            tax.eta_tax_sub_type = "V001" 

    so_doc.run_method("calculate_taxes_and_totals")

    so_doc.insert(ignore_permissions=True)

    # 🚀 Optionally submit if flag provided
    if data.get('is_submittable'):
        so_doc.submit()

    frappe.db.commit()

    if data.get('is_submittable'):
        create_sales_invoice(so_doc)

    # 📤 Return the inserted Sales Order as dictionary
    return so_doc.as_dict()


def validate_required_fields(data, fields):
    # ❗ Check if required fields exist, throw error if missing
    for field in fields:
        if not data.get(field):
            frappe.throw(f"Missing required field: {field}")


def validate_customer(customer):
    # 👤 Check if customer exists, else create new one
    existing_customer = frappe.get_value("Customer", {"customer_name": customer}, "name")
    if not existing_customer:
        existing_customer = frappe.get_value("Customer", {"name": customer}, "name")
    if existing_customer:
        return existing_customer

    customer_doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer,
        "customer_type": "Individual"
    })
    customer_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return customer_doc.name


def validate_warehouse(warehouse):
    # 🏢 Check if warehouse exists, else create new one
    existing_warehouse = frappe.get_value("Warehouse", {"warehouse_name": warehouse}, "name")
    if not existing_warehouse:
        existing_warehouse = frappe.get_value("Warehouse", {"name": warehouse}, "name")
    if existing_warehouse:
        return existing_warehouse

    warehouse_doc = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": warehouse,
    })
    warehouse_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return warehouse_doc.name


def validate_items(items):
    # 📦 Validate each item and it's details
    validated_items = []
    for item in items:
        item["item_code"] = validate_item(item)
        item['price_list_rate'] = item.get('rate', 0) or 0  # 💲 Ensure price field is set
        validated_items.append(item)
    return validated_items


def validate_item_group(item_group):
    # 🗂️ Check if item group exists, else create new one
    if not item_group:
        return "All Item Groups"

    existing_item_group = frappe.get_value("Item Group", {"item_group_name": item_group}, "name")
    if not existing_item_group:
        existing_item_group = frappe.get_value("Item Group", {"name": item_group}, "name")
    if existing_item_group:
        return existing_item_group

    item_group_doc = frappe.get_doc({
        "doctype": "Item Group",
        "item_group_name": item_group,
        "parent_item_group": "All Item Groups",
        "is_group": 0
    })
    item_group_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return item_group_doc.name


def validate_item(item_data):
    # 🛒 Check if item exists, else create new one
    item_code = item_data.get("item_code")
    item_group = item_data.get("item_group") or "اونلاين"

    existing_item = frappe.get_value("Item", {"item_code": item_code}, "name")
    if not existing_item:
        existing_item = frappe.get_value("Item", {"name": item_code}, "name")
    if not existing_item:
        existing_item = frappe.get_value("Item", {"item_name": item_code}, "name")
    if not existing_item:
        existing_item = frappe.get_value("Item", {"custom_item_id": item_code}, "name")
    if existing_item:
        return existing_item

    item_doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "item_group": item_group,
        "stock_uom": "Nos",
        "is_stock_item": 1,
    })
    
    item_doc.insert(ignore_permissions=True)
    item_doc.append("taxes", {
        "item_tax_template": "الضريبة القياسية %15 - ذهول",
    })
    item_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return item_doc.name


@frappe.whitelist()
def submit_sales_order(order_id):
    try:
        # Fetch the Sales Order using the po_no field
        so_doc = frappe.get_doc('Sales Order', {"po_no": order_id})

        if not so_doc:
            return f"No Sales Order found with PO No: {order_id}"

        # Check if it's already submitted
        if so_doc.docstatus == 0:
            so_doc.submit()
            frappe.db.commit()

            create_sales_invoice(so_doc)

        return {
            "status": "success",
            "message": f"Sales Order {so_doc.name} has been successfully submitted."
        }

    except frappe.DoesNotExistError:
        frappe.log_error(f"Sales Order not found for PO No: {order_id}", "submit_sales_order")
        return {
            "status": "error",
            "message": f"No Sales Order found with PO No: {order_id}"
        }

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="submit_sales_order failed")
        return {
            "status": "error",
            "message": f"An error occurred while submitting Sales Order: {str(e)}"
        }


@frappe.whitelist()
def cancel_sales_order(order_id):
    # lookup sales order by PO number
    so = frappe.get_doc("Sales Order", {"po_no": order_id})
    if not so:
        return f"No Sales Order found for PO No: {order_id}"

    cancelled_invoices = []
    cancelled_payments = []
    errors = []

    # find all Sales Invoices that reference this Sales Order in Sales Invoice Item
    invoice_rows = frappe.db.sql("""
        SELECT DISTINCT sii.parent AS invoice_name
        FROM `tabSales Invoice Item` AS sii
        WHERE sii.sales_order = %s
    """, (so.name,), as_dict=True)

    invoice_names = [r.invoice_name for r in invoice_rows]

    # Cancel related Payment Entries first (those linked to each invoice)
    for inv_name in invoice_names:
        try:
            # find Payment Entries that reference this invoice
            payment_rows = frappe.db.sql("""
                SELECT DISTINCT per.parent AS payment_name
                FROM `tabPayment Entry Reference` AS per
                WHERE 
                    per.reference_name = %s
                    AND per.reference_doctype = 'Sales Invoice'
            """, (inv_name,), as_dict=True)

            for prow in payment_rows:
                pe_name = prow.payment_name
                try:
                    pe = frappe.get_doc("Payment Entry", pe_name)
                    if pe.docstatus == 1:
                        pe.cancel()
                        frappe.db.commit()
                        cancelled_payments.append(pe_name)
                except Exception as e:
                    errors.append(f"Payment Entry {pe_name} cancel error: {e}")
        except Exception as e:
            errors.append(f"Error finding payments for invoice {inv_name}: {e}")

    # Cancel the Sales Invoices
    for inv_name in invoice_names:
        try:
            invoice = frappe.get_doc("Sales Invoice", inv_name)
            
            # reload to avoid concurrency issue
            invoice.reload()
            
            if invoice.docstatus == 1:
                invoice.cancel()
                frappe.db.commit()
                cancelled_invoices.append(inv_name)
        except Exception as e:
            errors.append(f"Sales Invoice {inv_name} cancel error: {e}")

    # Finally cancel the Sales Order itself
    try:
        # reload to avoid concurrency issue
        so.reload()

        if so.docstatus == 1:
            so.cancel()
            frappe.db.commit()
        else:
            pass
    except Exception as e:
        errors.append(f"Sales Order {so.name} cancel error: {e}")

    return {
        "status": "Success" if not errors else "Failure",
        "sales_order": so.name,
        "cancelled_invoices": cancelled_invoices,
        "cancelled_payments": cancelled_payments,
        "errors": errors,
    }


def ensure_missing_fields():
    # Create custom field 'mode_of_payment' in Sales Order if it doesn't exist.
    if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "custom_mode_of_payment"}):
        create_custom_field(
            "Sales Order",
            {
                "fieldname": "custom_mode_of_payment",
                "label": "Mode of Payment",
                "fieldtype": "Link",
                "options": "Mode of Payment",
                "insert_after": "payment_terms_template",
                "reqd": 0,
                "hidden": 1,
            }
        )
    if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "custom_shipping_company"}):
        create_custom_field(
            "Sales Order",
            {
                "fieldname": "custom_shipping_company",
                "label": "Shipping Company",
                "fieldtype": "Link",
                "options": "Shipping Company",
                "insert_after": "payment_terms_template",
                "reqd": 0,
                "hidden": 1,
            }
        )
    if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "custom_shipping_amount"}):
        create_custom_field(
            "Sales Order",
            {
                "fieldname": "custom_shipping_amount",
                "label": "Shipping Amount",
                "fieldtype": "Float",
                "insert_after": "payment_terms_template",
                "reqd": 0,
                "hidden": 1,
            }
        )
    frappe.db.commit()