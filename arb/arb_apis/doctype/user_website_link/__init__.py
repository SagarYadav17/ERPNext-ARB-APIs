import frappe
from frappe import _
from arb.arb_apis.utils.authentication import (
    require_jwt_auth
)
from arb.arb_apis.utils.gst import fetch_gst_details

@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_user_companies():
    """
    Fetch companies linked to logged-in user
    """

    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(_("Unauthorized"))

    links = frappe.db.get_all(
        "User Website Link",
        filters={
            "user": user,
            "is_disable": 0
        },
        fields=[
            "link_name",
            "link_document_type",
            "role_profile",
            "is_primary"
        ],
        order_by="is_primary desc, modified desc"
    )

    companies = [
        {
            "name": l.link_name,
            "type": l.link_document_type,
            "role": l.role_profile,
            "is_primary": l.is_primary
        }
        for l in links
    ]

    return {
        "status": "success",
        "companies": companies
    }

@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def set_active_company(company: str):
    """
    Set active company for logged-in user
    """

    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(_("Unauthorized"))

    # Validate company access
    link = frappe.db.exists(
        "User Website Link",
        {
            "user": user,
            "link_name": company,
            "is_disable": 0
        }
    )

    if not link:
        frappe.throw(_("You do not have access to this company"))

    # Set active company in session
    frappe.session.data["active_company"] = company

    return {
        "status": "success",
        "message": "Active company set successfully",
        "active_company": company
    }

@frappe.whitelist(allow_guest=True) 
@require_jwt_auth
def check_gst_customer(gst_no):
    user = frappe.session.user

    customer = frappe.db.get_value(
        "Customer",
        {"gstin": gst_no},
        ["name"],
        as_dict=True
    )

    # ✅ Case 1: GST exists
    if customer:
        # Create pending invite
        frappe.get_doc({
            "doctype": "User Website Link",
            "user": user,
            "link_document_type": "Customer",
            "link_name": customer.name,
            "role_profile": "User",
            "is_disable": 1
        }).insert(ignore_permissions=True)

        return {
            "status": "pending",
            "message": (
                "Your company already exists. "
                "An access request has been sent to your Company Admin."
            )
        }

    # ✅ Case 2: GST is new
    return {
        "status": "new_gst",
        "message": "GST not found. Proceed to onboarding."
    }

@frappe.whitelist(allow_guest=True) 
@require_jwt_auth
def create_gst_customer(gst_no):
    user = frappe.session.user

    # 🔹 Fetch GST data (pseudo)
    gst_data = fetch_gst_details(gst_no)

    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": gst_data["legal_name"],
        "gstin": gst_no,
        "territory": "India",
        "customer_group": "Commercial",
        "address_line1": gst_data["address"],
        "state": gst_data["state"]
    })
    customer.insert(ignore_permissions=True)

    # Link user as Admin
    frappe.get_doc({
        "doctype": "User Website Link",
        "user": user,
        "link_document_type": "Customer",
        "link_name": customer.name,
        "role_profile": "Admin",
        "is_primary": 1,
        "is_disable": 0
    }).insert(ignore_permissions=True)

    return {
        "status": "success",
        "customer": customer.name
    }

@frappe.whitelist(allow_guest=True) 
@require_jwt_auth
def check_non_gst_customer(mobile_no):
    user = frappe.session.user

    customer = frappe.db.get_value(
        "Customer",
        {"mobile_no": mobile_no, "gstin": ["is", "null"]},
        ["name"],
        as_dict=True
    )

    # ✅ Exists
    if customer:
        frappe.get_doc({
            "doctype": "User Website Link",
            "user": user,
            "link_document_type": "Customer",
            "link_name": customer.name,
            "role_profile": "User",
            "is_disable": 1
        }).insert(ignore_permissions=True)

        return {
            "status": "pending",
            "message": (
                "Your company already exists. "
                "Please contact your Company Admin to approve your access."
            )
        }

    # ❌ Not exists
    return {
        "status": "new_non_gst"
    }

@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def create_non_gst_customer(data):
    user = frappe.session.user

    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": data.company_name,
        "customer_type": "Individual",
        "mobile_no": data.mobile_no,
        "address_line1": data.address_line1,
        "city": data.city,
        "state": data.state,
        "pincode": data.pincode
    })
    customer.insert(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "User Website Link",
        "user": user,
        "link_document_type": "Customer",
        "link_name": customer.name,
        "role_profile": "Admin",
        "is_primary": 1,
        "is_disable": 0
    }).insert(ignore_permissions=True)

    return {
        "status": "success",
        "customer": customer.name
    }
