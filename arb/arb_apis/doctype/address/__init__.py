import frappe

@frappe.whitelist(allow_guest=True)
def create_address(data):
    """
    data: dict containing address fields
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    address = frappe.new_doc("Address")
    address.update(data)
    address.insert(ignore_permissions=True)

    return {
        "status": "success",
        "message": "Address created successfully",
        "name": address.name
    }

@frappe.whitelist(allow_guest=True)
def get_address(name=None):
    if not name:
        frappe.throw("Address name is required")

    if not frappe.db.exists("Address", name):
        frappe.throw("Address not found")

    return frappe.get_doc("Address", name)

@frappe.whitelist(allow_guest=True)
def list_addresses(filters=None, fields=None, limit=20, offset=0):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)

    if isinstance(fields, str):
        fields = frappe.parse_json(fields)

    if not fields:
        fields = [
            "name",
            "address_title",
            "address_type",
            "city",
            "state",
            "country",
            "pincode",
            "is_primary_address",
            "is_shipping_address",
            "disabled"
        ]

    return frappe.get_all(
        "Address",
        filters=filters,
        fields=fields,
        limit_start=offset,
        limit_page_length=limit,
        order_by="modified desc"
    )

@frappe.whitelist(allow_guest=True)
def update_address(name, data):
    if isinstance(data, str):
        data = frappe.parse_json(data)

    if not frappe.db.exists("Address", name):
        frappe.throw("Address not found")

    address = frappe.get_doc("Address", name)
    address.update(data)
    address.save(ignore_permissions=True)

    return {
        "status": "success",
        "message": "Address updated successfully"
    }

@frappe.whitelist(allow_guest=True)
def delete_address(name):
    if not frappe.db.exists("Address", name):
        frappe.throw("Address not found")

    frappe.delete_doc("Address", name, ignore_permissions=True)

    return {
        "status": "success",
        "message": "Address deleted successfully"
    }

@frappe.whitelist(allow_guest=True)
def link_address(address_name, link_doctype, link_name):
    address = frappe.get_doc("Address", address_name)

    address.append("links", {
        "link_doctype": link_doctype,
        "link_name": link_name
    })

    address.save(ignore_permissions=True)

    return {
        "status": "success",
        "message": f"Address linked with {link_doctype} {link_name}"
    }
