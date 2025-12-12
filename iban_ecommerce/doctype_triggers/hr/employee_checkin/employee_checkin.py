import frappe
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def before_insert(doc, method=None):
    pass

@frappe.whitelist()
def after_insert(doc, method=None):
    # Update log Type (IN - Out) For Current Employee
    update_log_type(doc)

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

def update_log_type(doc):
    # Clear all log_type values for today's checkins of this employee
    frappe.db.sql("""
        UPDATE `tabEmployee Checkin`
        SET log_type = NULL
        WHERE 
            employee = %s
            AND DATE(time) = DATE(%s)
    """, (doc.employee, doc.time))

    # Get all checkins for today sorted by time
    checkins = frappe.db.sql("""
        SELECT name
        FROM `tabEmployee Checkin`
        WHERE 
            employee = %s 
            AND DATE(time) = DATE(%s)
        ORDER BY time ASC
    """, (doc.employee, doc.time), as_dict=True)

    if not checkins:
        return

    # First checkin → IN
    frappe.db.set_value("Employee Checkin", checkins[0].name, "log_type", "IN")

    # If more than one → last checkin → OUT
    if len(checkins) > 1:
        frappe.db.set_value("Employee Checkin", checkins[-1].name, "log_type", "OUT")

