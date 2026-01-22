from collections import defaultdict
import frappe

@frappe.whitelist(allow_guest=True)
def get_homepage_data():
    homepage = frappe.get_single("Homepages")

    # Header Images
    header = [{"idx": row.idx, "image": row.image, "alt_text": row.alt_text} for row in homepage.header]

    category_map = defaultdict(list)

    for row in homepage.category_wise_product:
        # Fetch website item details
        website_item = frappe.db.get_value(
            "Website Item",
            row.website_item,
            [
                "name",
                "item_code",
                "web_item_name",
                "website_image",
                "stock_uom",
                "web_long_description",
            ],
            as_dict=True,
        )

        if not website_item:
            continue

        # Fetch selling price using the linked item code
        price = (
            frappe.db.get_value(
                "Item Price",
                {"item_code": website_item.item_code, "selling": 1},
                "price_list_rate",
            )
            or 0
        )

        # Product item_group is the homepage section name
        product_group = row.item_group

        category_map[row.item_group].append(
            {
                "item_code": website_item.item_code,
                "name": website_item.web_item_name,
                "image": website_item.website_image,
                "item_group": product_group,
                "price": float(price),
                "uom": website_item.stock_uom or "Nos",
                "description": website_item.web_long_description or "",
            }
        )

    categories = [{"name": category, "products": products} for category, products in category_map.items()]

    return {"message": {"header": header, "categories": categories}}


@frappe.whitelist(allow_guest=True)
def search_website_items(query="", item_group=""):
    """Search for items in Website Item doctype"""
    if not query:
        return {"success": False, "data": []}

    page_size = 20

    # Build filters
    filters = {
        "or_filters": [
            ["web_item_name", "like", f"%{query}%"],
            ["item_code", "like", f"%{query}%"],
        ]
    }

    # Add item_group filter if provided
    if item_group:
        filters["item_group"] = item_group

    # Search in Website Item doctype by name or item code
    website_items = frappe.get_all(
        "Website Item",
        or_filters=filters.get("or_filters"),
        filters={"item_group": item_group} if item_group else None,
        fields=[
            "name",
            "item_code",
            "web_item_name",
            "website_image",
            "stock_uom",
            "web_long_description",
            "item_group",
            "short_description",
        ],
        page_length=page_size,
        order_by="modified desc",
    )

    # Add pricing information for each item
    products = []
    for item in website_items:
        product_image = frappe.db.get_value(
            "Item",
            item.item_code,
            "image"
        )

        price = (
            frappe.db.get_value(
                "Item Price",
                {"item_code": item.item_code, "selling": 1},
                "price_list_rate",
            )
            or 0
        )

        products.append(
            {
                "item_code": item.item_code,
                "name": item.web_item_name,
                "image": item.website_image,
                "product_image": product_image,  
                "item_group": item.item_group or "",
                "price": float(price),
                "uom": item.stock_uom or "Nos",
                "short_description": item.short_description or "",
            }
        )

    return {
        "success": True,
        "data": products,
    }


@frappe.whitelist(allow_guest=True)
def get_product_detail(item_code):
    """Product Detail Page data from Website Item"""
    if not item_code:
        return {"success": False, "error": "Item code is required"}

    # Fetch Website Item doc to include specifications table
    try:
        website_item = frappe.get_doc("Website Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return {"success": False, "error": "Item not found"}

    # Ensure item is published
    if not getattr(website_item, "published", 0):
        return {"success": False, "error": "Item not published"}

    # --- IMAGE LOGIC CHANGES ---
    # 1. Product image comes from the Item doctype
    product_image = frappe.db.get_value("Item", website_item.item_code, "image")

    # 2. Item Group image comes from the Website Item (using the website_image field)
    item_group_image = website_item.website_image
    # ---------------------------

    # Pricing
    price = (
        frappe.db.get_value(
            "Item Price",
            {"item_code": website_item.item_code, "selling": 1},
            "price_list_rate",
        )
        or 0
    )

    # Product highlights from Website Specifications table
    highlights = [
        {"label": spec.label, "description": spec.description} for spec in website_item.website_specifications
    ]

    data = {
        "item_code": website_item.item_code,
        "name": website_item.web_item_name,
        "product_image": product_image,               
        "image": item_group_image, 
        "item_group": website_item.item_group or "",
        "price": float(price),
        "uom": website_item.stock_uom or "Nos",
        "short_description": website_item.short_description or "",
        "description": website_item.web_long_description or "",
        "highlights": highlights,
    }

    return {"success": True, "data": data}
