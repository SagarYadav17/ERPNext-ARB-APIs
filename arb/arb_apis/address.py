"""
Address APIs for ARB
"""

import frappe
from frappe import _

from arb.arb_apis.utils.authentication import require_jwt_auth


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def list_addresses(customer):
    """Get addresses for a customer"""
    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

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
        return {"success": True, "data": []}

    address_names = [link.parent for link in address_links]

    addresses = frappe.get_all(
        "Address",
        filters={"name": ["in", address_names], "disabled": 0},
        fields=[
            "name",
            "phone",
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

    return {"success": True, "data": addresses}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def create_address(customer, address_data):
    """Create a new address for the customer"""
    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    if not address_data:
        frappe.throw(_("address_data is required"), frappe.ValidationError)

    # Create address
    address = frappe.get_doc({"doctype": "Address", **address_data})

    # Link address to customer using Dynamic Link
    address.append("links", {"link_doctype": "Customer", "link_name": customer})

    address.insert(ignore_permissions=True)
    
    return {
        "success": True,
        "message": _("Address created successfully"),
        "address_name": address.name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def update_address(customer, address_name, address_data):
    """Update an existing address for the customer"""
    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    if not address_name:
        frappe.throw(_("address_name is required"), frappe.ValidationError)

    if not address_data:
        frappe.throw(_("address_data is required"), frappe.ValidationError)

    # Verify address exists and belongs to the customer
    address_link = frappe.db.get_value(
        "Dynamic Link",
        {
            "link_doctype": "Customer",
            "link_name": customer,
            "parenttype": "Address",
            "parent": address_name,
        },
        "parent",
    )

    if not address_link:
        frappe.throw(_("Address not found or unauthorized"), frappe.PermissionError)

    # Get and update the address
    address_doc = frappe.get_doc("Address", address_name)

    # Update allowed fields
    allowed_fields = [
        "address_title",
        "address_type",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "country",
        "pincode",
        "phone",
        "is_primary_address",
        "is_shipping_address",
        "disabled",
    ]

    for field in allowed_fields:
        if field in address_data:
            setattr(address_doc, field, address_data[field])

    address_doc.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("Address updated successfully"),
        "address_name": address_name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def delete_address(customer, address_name):
    """Delete an address for the customer"""
    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    if not address_name:
        frappe.throw(_("address_name is required"), frappe.ValidationError)

    # Verify address exists and belongs to the customer
    address_link = frappe.db.get_value(
        "Dynamic Link",
        {
            "link_doctype": "Customer",
            "link_name": customer,
            "parenttype": "Address",
            "parent": address_name,
        },
        "parent",
    )

    if not address_link:
        frappe.throw(_("Address not found or unauthorized"), frappe.PermissionError)

    # Delete the address
    frappe.delete_doc("Address", address_name, ignore_permissions=True)

    return {
        "success": True,
        "message": _("Address deleted successfully"),
    }
