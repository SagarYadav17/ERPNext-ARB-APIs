"""
JWT Authentication API for ARB
"""

import frappe
from frappe import _

from arb.arb_apis.utils.authentication import require_jwt_auth


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def list_addresses():
    """Get addresses of the authenticated user"""
    user_email = frappe.session.user

    if not user_email:
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    # Get customer for the user via Contact
    customer = _get_customer_from_email(user_email)
    if not customer:
        return []

    # Get all addresses linked to this customer
    address_links = frappe.get_all(
        "Dynamic Link",
        filters={
            "link_doctype": "Customer",
            "link_name": customer,
            "parenttype": "Address",
        },
        fields=["parent"],
    )

    if not address_links:
        return []

    address_names = [link.parent for link in address_links]

    return frappe.get_all(
        "Address",
        filters={"name": ["in", address_names], "disabled": 0},
        fields=[
            "name",
            "address_title",
            "address_type",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "pincode",
            "is_primary_address",
            "is_shipping_address",
        ],
        order_by="modified desc",
    )


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def create_address():
    """Create a new address for the authenticated user"""
    user_email = frappe.session.user
    if not user_email:
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    # Get or create customer for the user
    customer = _get_or_create_customer(user_email)

    # Create address
    address_data = frappe.local.form_dict.data
    address = frappe.get_doc({"doctype": "Address", **address_data})

    # Link address to customer using Dynamic Link
    address.append("links", {"link_doctype": "Customer", "link_name": customer})

    address.insert(ignore_permissions=True)
    return address.name


def _get_customer_from_email(email):
    """Get customer linked to the email via Contact"""
    # First, try to find a contact with this email
    contact = frappe.db.get_value("Contact", {"email_id": email}, "name")
    if not contact:
        return None

    # Get customer linked to this contact
    customer_link = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Customer", "parent": contact, "parenttype": "Contact"},
        "link_name",
    )
    return customer_link


def _get_or_create_customer(email):
    """Get or create customer for the given email"""
    # Try to find existing customer
    customer = _get_customer_from_email(email)
    if customer:
        return customer

    # Extract name from email
    customer_name = email.split("@")[0].replace(".", " ").title()

    # Create new customer
    customer_doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Individual",
            "customer_group": frappe.db.get_single_value(
                "Selling Settings", "customer_group"
            )
            or "Individual",
            "territory": frappe.db.get_single_value("Selling Settings", "territory")
            or "All Territories",
        }
    )
    customer_doc.insert(ignore_permissions=True)

    # Create contact and link to customer
    contact_doc = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": customer_name,
            "email_id": email,
            "status": "Passive",
        }
    )
    contact_doc.append(
        "links", {"link_doctype": "Customer", "link_name": customer_doc.name}
    )
    contact_doc.append("email_ids", {"email_id": email, "is_primary": 1})
    contact_doc.insert(ignore_permissions=True)

    return customer_doc.name
