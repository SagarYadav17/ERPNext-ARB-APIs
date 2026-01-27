"""
Cart APIs using Quick Order doctype
"""

import frappe
from frappe import _

from arb.arb_apis.utils.authentication import require_jwt_auth
from pprint import pprint


def _get_customer_from_email(email):
    """Get customer linked to the email via Contact"""
    contact = frappe.db.get_value("Contact", {"email_id": email}, "name")
    if not contact:
        return None

    customer_link = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Customer", "parent": contact, "parenttype": "Contact"},
        "link_name",
    )
    return customer_link


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

    # Create a new Quick Order (cart) — shipping_process is required
    if not shipping_process:
        frappe.throw(_("Shipping Process is required to create a cart"), frappe.ValidationError)

    cart = frappe.get_doc(
        {
            "doctype": "Quick Order",
            "customer": customer,
            "date": frappe.utils.now(),
            "shipping_process": shipping_process,
        }
    )
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
def add_to_cart(item_code, qty=1, shipping_address=None, billing_address=None):
    """Add item to cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    # Get or create cart
    cart = _get_existing_cart(customer)
    if not cart:
        # Fetch default shipping process from database
        default_shipping_process = frappe.db.get_value("Store Link Shipping Process", {}, "name")

        if not default_shipping_process:
            frappe.throw(_("No Shipping Process available"), frappe.ValidationError)

        # Create new cart with fetched shipping_process
        cart = _get_or_create_cart(
            customer,
            shipping_process=default_shipping_process,
            shipping_address=shipping_address,
            billing_address=billing_address,
        )

    # Fetch item details from Website Item
    website_item = frappe.db.get_value(
        "Website Item",
        {"item_code": item_code},
        ["item_code", "web_item_name", "stock_uom", "published"],
        as_dict=True,
    )

    if not website_item or not website_item.published:
        frappe.throw(_("Item not available"), frappe.ValidationError)

    # Check if item already exists in cart
    existing_item = None
    for item in cart.table_effn:
        if item.item_code == item_code:
            existing_item = item
            break

    if existing_item:
        # Update quantity
        existing_item.qty = float(existing_item.qty or 0) + float(qty)
    else:
        # Add new item
        cart.append(
            "table_effn",
            {
                "item_code": website_item.item_code,
                "item_name": website_item.web_item_name,
                "qty": float(qty),
                "uom": website_item.stock_uom,
            },
        )

    cart.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("Item added to cart"),
        "cart_id": cart.name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_cart():
    """Get cart items"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)
    customer = _get_customer_from_email(user_email)
    if not customer:
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
                "item_name": (website_item.web_item_name if website_item else item.item_name),
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
def set_cart_shipping(shipping_process):
    """Set shipping process on the user's cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    # Validate shipping process exists
    if not frappe.db.exists("Store Link Shipping Process", shipping_process):
        frappe.throw(_("Invalid Shipping Process"), frappe.ValidationError)

    # Get or create cart requiring shipping_process if new
    existing_cart_name = frappe.db.get_value("Quick Order", {"customer": customer, "docstatus": 0}, "name")
    if existing_cart_name:
        cart = frappe.get_doc("Quick Order", existing_cart_name)
    else:
        cart = _get_or_create_cart(customer, shipping_process=shipping_process)

    cart.shipping_process = shipping_process
    cart.save(ignore_permissions=True)
    return {
        "success": True,
        "message": _("Shipping details updated"),
        "cart_id": cart.name,
    }


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def update_cart_item(item_name, qty):
    """Update cart item quantity"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    cart = _get_existing_cart(customer)
    if not cart:
        frappe.throw(_("Cart not found"), frappe.ValidationError)

    # Find and update the item
    item_found = False
    for item in cart.table_effn:
        if item.name == item_name:
            item.qty = float(qty)
            item_found = True
            break

    if not item_found:
        frappe.throw(_("Item not found in cart"), frappe.ValidationError)

    cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Cart item updated")}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def remove_from_cart(item_name):
    """Remove item from cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    cart = _get_existing_cart(customer)
    if not cart:
        frappe.throw(_("Cart not found"), frappe.ValidationError)

    # Find and remove the item
    item_to_remove = None
    for item in cart.table_effn:
        if item.name == item_name:
            item_to_remove = item
            break

    if item_to_remove:
        cart.remove(item_to_remove)
        cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Item removed from cart")}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def clear_cart():
    """Clear all items from cart"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
        frappe.throw(_("Customer not found"), frappe.ValidationError)

    cart = _get_existing_cart(customer)
    if not cart:
        frappe.throw(_("Cart not found"), frappe.ValidationError)

    # Clear all items
    cart.table_effn = []
    cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Cart cleared")}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def update_cart_addresses(shipping_address=None, billing_address=None):
    """Update cart shipping and billing addresses"""
    user_email = frappe.session.user
    if not user_email or user_email == "Guest":
        frappe.throw(_("Unauthorized"), frappe.Unauthorized)

    customer = _get_customer_from_email(user_email)
    if not customer:
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
        frappe.throw(_("Invalid Shipping Address for this customer"), frappe.PermissionError)
    if billing_address and not _validate_address(billing_address):
        frappe.throw(_("Invalid Billing Address for this customer"), frappe.PermissionError)

    if shipping_address:
        cart.shipping_address = shipping_address
    if billing_address:
        cart.billing_address = billing_address

    cart.save(ignore_permissions=True)

    return {"success": True, "message": _("Cart addresses updated")}
