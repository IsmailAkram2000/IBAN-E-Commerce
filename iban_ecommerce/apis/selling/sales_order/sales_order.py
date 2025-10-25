import requests
import frappe

# 🌍 Base URL of your ERPNext/Frappe site
BASE_URL = "http://localhost:8000"
API_KEY = ""
API_SECRET = ""

@frappe.whitelist(allow_guest=True)
def test_endpoint():    
    # 📄 Step 1: Prepare headers for authentication
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {API_KEY}:{API_SECRET}"  # Change with your site api key and secret
    }

    # 🛒 Step 2: Define Sales Order payload (sales order body)
    sales_order_payload = {
        "is_submittable": 1,  
        "customer": "E-Commerce",  
        "transaction_date": "2025-09-15", 
        "delivery_date": "2025-09-15",    
        "set_warehouse": "Finished Goods - ESD",
        "items": [
            {
                "item_code": "SKU005", 
                "item_name": "T-shirt", 
                "description": "T-shirt", 
                "item_group": "Demo Item Group", 
                "qty": 1,   
                "rate": 800,
                "amount": 800
            }
        ]
    }

    # 📡 Step 3: Send POST request to create Sales Order
    so_res = requests.post(
        f"{BASE_URL}/api/method/iban_ecommerce.apis.selling.sales_order.sales_order.create_sales_order",
        json=sales_order_payload,
        headers=headers,
    )

    # 📤 Step 4: Return response JSON
    return so_res.json()


@frappe.whitelist()
def login(usr, pwd):
    # 📡 Send login request with username + password
    login_res = requests.post(
        f"{BASE_URL}/api/method/login",
        json={
            "usr": usr,
            "pwd": pwd
        }
    )

    # ✅ Check if login succeeded
    if login_res.status_code != 200:
        frappe.throw(f"Login request failed.")

    # 🍪 Extract session ID (sid) from cookies
    sid = login_res.cookies.get("sid")

    if not sid:
        # ❌ No sid returned → invalid login
        frappe.throw("Invalid credentials or login failed!")

    # 🔑 Return sid for authentication
    return sid


@frappe.whitelist()
def create_sales_order():
    # 📥 Get JSON body from API request
    data = frappe.request.get_json()

    # ✅ Validate required fields
    validate_required_fields(data, ["customer", "set_warehouse", "items"])
    if not data.get("items") or not isinstance(data["items"], list):
        frappe.throw("Items list is required and must contain at least one item")
    for item in data["items"]:
        validate_required_fields(item, ["item_code", "qty", "rate"])

    # 🔎 Validate or create related documents
    data["customer"] = validate_customer(data["customer"])
    data["set_warehouse"] = validate_warehouse(data["set_warehouse"])
    data["items"] = validate_items(data["items"])

    # 📝 Ensure the correct doctype
    data["doctype"] = "Sales Order"

    # 📄 Create Sales Order document
    so_doc = frappe.get_doc(data)

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
        item["item_group"] = validate_item_group(item.get("item_group"))
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
    item_group = item_data.get("item_group") or "All Item Groups"

    existing_item = frappe.get_value("Item", {"item_code": item_code}, "name")
    if not existing_item:
        existing_item = frappe.get_value("Item", {"name": item_code}, "name")
    if existing_item:
        return existing_item

    item_doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "item_group": item_group,
        "stock_uom": "Nos",
        "is_stock_item": 1
    })
    item_doc.insert(ignore_permissions=True)
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
