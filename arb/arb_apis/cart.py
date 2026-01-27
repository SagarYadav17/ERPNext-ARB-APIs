"""
Cart APIs using Quick Order doctype
"""

import frappe
from frappe import _

from arb.arb_apis.utils.authentication import require_jwt_auth


def _get_existing_cart(customer):
    """Fetch existing draft cart for customer or None."""
    existing_cart = frappe.db.get_value(
        "Quick Order",
        {"customer": customer, "docstatus": 0},
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Quick Order", existing_cart) if existing_cart else None


def _get_or_create_cart(
    customer,
    shipping_process=None,
    shipping_address=None,
    billing_address=None,
    items=None,
):
    """Get or create a cart (Quick Order) for the customer.

    When creating a new cart, `shipping_process` is required by the DocType and must be provided.
    Optionally sets `shipping_address` and `billing_address` if provided.
    """
    # Check if there's an existing draft Quick Order for this customer
    existing_cart = frappe.db.get_value(
        "Quick Order",
        {"customer": customer, "docstatus": 0},
        "name",
        order_by="modified desc",
    )

    if existing_cart:
        return frappe.get_doc("Quick Order", existing_cart)

    # Create a new Quick Order (cart) — shipping_process and at least one item are required
    if not shipping_process:
        frappe.throw(
            _("Shipping Process is required to create a cart"), frappe.ValidationError
        )

    if not items:
        frappe.throw(
            _("At least one item with qty > 0 is required to create a cart"),
            frappe.ValidationError,
        )

    available_warehouse = frappe.db.get_value("Available Warehouse", {}, "name")
    if not available_warehouse:
        frappe.throw(
            _("No Available Warehouse found to create cart"), frappe.ValidationError
        )

    cart = frappe.get_doc(
        {
            "doctype": "Quick Order",
            "customer": customer,
            "date": frappe.utils.now(),
            "shipping_process": shipping_process,
            "warehouse": available_warehouse,
            "custom_quick_order_to": customer,
        }
    )

    # Seed mandatory child table rows
    for item in items:
        cart.append("table_effn", item)

    if shipping_address:
        cart.shipping_address = shipping_address
    if billing_address:
        cart.billing_address = billing_address
    cart.insert(ignore_permissions=True)
    return cart


@frappe.whitelist(allow_guest=True)
def get_shipping_processes():
    """Get available shipping processes"""
    shipping_processes = frappe.get_all(
        "Store Link Shipping Process",
        fields=["name", "shipping_process"],
        order_by="modified desc",
    )
    return {"success": True, "data": shipping_processes}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def update_cart_items(customer, items, shipping_address=None, billing_address=None):
    """Update cart items (add, update, or remove).

    Args:
        customer: Customer name (mandatory)
        items: List of dicts with 'item_code' and 'qty'. If qty=0, item is removed.
        shipping_address: Optional shipping address
        billing_address: Optional billing address

    Example:
        items = [
            {"item_code": "ITEM-001", "qty": 5},  # Add or update
            {"item_code": "ITEM-002", "qty": 0}   # Remove
        ]
    """
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    # Normalize to list
    if not isinstance(items, list):
        items = [items]

    if not items:
        frappe.throw(_("At least one item is required"), frappe.ValidationError)

    # Pre-validate item payloads and fetch item master data once
    normalized_items = []
    item_details_cache = {}

    for item_update in items:
        item_code = (item_update or {}).get("item_code")
        qty = float((item_update or {}).get("qty", 0))

        if not item_code:
            frappe.throw(_("item_code is required"), frappe.ValidationError)

        if qty < 0:
            frappe.throw(_("qty cannot be negative"), frappe.ValidationError)

        # Cache website item details when needed (only for qty > 0)
        if qty > 0 and item_code not in item_details_cache:
            website_item = frappe.db.get_value(
                "Website Item",
                {"item_code": item_code},
                ["item_code", "web_item_name", "stock_uom", "published"],
                as_dict=True,
            )

            if not website_item or not website_item.published:
                frappe.throw(
                    _(f"Item {item_code} not available"), frappe.ValidationError
                )
            item_details_cache[item_code] = website_item

        normalized_items.append({"item_code": item_code, "qty": qty})

    cart = _get_existing_cart(customer)

    # If no cart exists, create one with the initial child rows to satisfy mandatory table
    if not cart:
        # Require at least one item with qty > 0 to create a new cart
        creation_rows = []
        for entry in normalized_items:
            if entry["qty"] > 0:
                details = item_details_cache.get(entry["item_code"])
                creation_rows.append(
                    {
                        "item_code": details.item_code,
                        "item_name": details.web_item_name,
                        "qty": entry["qty"],
                        "uom": details.stock_uom,
                    }
                )

        if not creation_rows:
            frappe.throw(
                _("At least one item with qty > 0 is required to create a cart"),
                frappe.ValidationError,
            )

        default_shipping_process = frappe.db.get_value(
            "Store Link Shipping Process", {}, "name"
        )

        if not default_shipping_process:
            frappe.throw(_("No Shipping Process available"), frappe.ValidationError)

        cart = _get_or_create_cart(
            customer,
            shipping_process=default_shipping_process,
            shipping_address=shipping_address,
            billing_address=billing_address,
            items=creation_rows,
        )
    else:
        # Process updates on existing cart
        for entry in normalized_items:
            item_code = entry["item_code"]
            qty = entry["qty"]

            existing_item = None
            for item in cart.table_effn:
                if item.item_code == item_code:
                    existing_item = item
                    break

            if qty == 0:
                if existing_item:
                    cart.remove(existing_item)
            else:
                if existing_item:
                    existing_item.qty = qty
                else:
                    details = item_details_cache[item_code]
                    cart.append(
                        "table_effn",
                        {
                            "item_code": details.item_code,
                            "item_name": details.web_item_name,
                            "qty": qty,
                            "uom": details.stock_uom,
                        },
                    )

        # Update addresses if provided
        if shipping_address:
            cart.shipping_address = shipping_address
        if billing_address:
            cart.billing_address = billing_address

        cart.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("Cart updated"),
        "cart_id": cart.name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_cart(customer):
    """Get cart items for a customer"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        return {"success": True, "data": {"items": [], "total": 0}}

    cart = _get_existing_cart(customer)
    if not cart:
        return {
            "success": True,
            "data": {
                "items": [],
                "total": 0,
                "shipping_address": None,
                "billing_address": None,
                "shipping_process": None,
            },
        }

    items = []
    total = 0

    for item in cart.table_effn:
        # Fetch website item image
        website_item = frappe.db.get_value(
            "Website Item",
            {"item_code": item.item_code},
            ["website_image", "web_item_name"],
            as_dict=True,
        )

        # Fetch price
        price = (
            frappe.db.get_value(
                "Item Price",
                {"item_code": item.item_code, "selling": 1},
                "price_list_rate",
            )
            or 0
        )

        item_total = float(price) * float(item.qty or 0)
        total += item_total

        items.append(
            {
                "name": item.name,
                "item_code": item.item_code,
                "item_name": (
                    website_item.web_item_name if website_item else item.item_name
                ),
                "qty": float(item.qty or 0),
                "uom": item.uom,
                "price": float(price),
                "total": item_total,
                "image": website_item.website_image if website_item else None,
            }
        )

    return {
        "success": True,
        "data": {
            "cart_id": cart.name,
            "items": items,
            "total": total,
            "shipping_address": cart.shipping_address,
            "billing_address": cart.billing_address,
            "shipping_process": cart.shipping_process,
        },
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def set_cart_shipping(customer, shipping_process):
    """Set shipping process on the customer's cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    if not frappe.db.exists("Store Link Shipping Process", shipping_process):
        frappe.throw(_("Invalid Shipping Process"), frappe.ValidationError)

    existing_cart_name = frappe.db.get_value(
        "Quick Order", {"customer": customer, "docstatus": 0}, "name"
    )
    if not existing_cart_name:
        frappe.throw(_("Cart not found for this customer"), frappe.ValidationError)

    cart = frappe.get_doc("Quick Order", existing_cart_name)

    cart.shipping_process = shipping_process
    cart.save(ignore_permissions=True)
    return {
        "success": True,
        "message": _("Shipping details updated"),
        "cart_id": cart.name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def clear_cart(customer):
    """Clear all items from cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    cart = _get_existing_cart(customer)
    if not cart:
        frappe.throw(_("Cart not found"), frappe.ValidationError)

    cart.table_effn = []
    cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Cart cleared")}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def update_cart_addresses(customer, shipping_address=None, billing_address=None):
    """Update cart shipping and billing addresses"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    if not customer:
        frappe.throw(_("customer is required"), frappe.ValidationError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    cart = _get_existing_cart(customer)
    if not cart:
        frappe.throw(_("Cart not found"), frappe.ValidationError)

    # Validate provided addresses belong to this customer via Dynamic Link
    def _validate_address(addr):
        if not addr:
            return True
        return frappe.db.exists(
            "Dynamic Link",
            {
                "link_doctype": "Customer",
                "link_name": customer,
                "parenttype": "Address",
                "parent": addr,
            },
        )

    if shipping_address and not _validate_address(shipping_address):
        frappe.throw(
            _("Invalid Shipping Address for this customer"), frappe.PermissionError
        )
    if billing_address and not _validate_address(billing_address):
        frappe.throw(
            _("Invalid Billing Address for this customer"), frappe.PermissionError
        )

    if shipping_address:
        cart.shipping_address = shipping_address
    if billing_address:
        cart.billing_address = billing_address

    cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Cart addresses updated")}
