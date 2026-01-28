import frappe


@frappe.whitelist(allow_guest=True)
def get_detail(route=None, item_code=None):
    """Product Detail Page data from Website Item (Route based)"""

    if not route and not item_code:
        return {"success": False, "error": "route or item_code is required"}

    # Fetch Website Item using route OR item_code
    try:
        if route:
            website_item = frappe.get_doc("Website Item", {"route": route})
        else:
            website_item = frappe.get_doc("Website Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return {"success": False, "error": "Item not found"}

    # Ensure item is published
    if not getattr(website_item, "published", 0):
        return {"success": False, "error": "Item not published"}

    # Fetch Item master
    item = frappe.get_cached_doc("Item", website_item.item_code)

    # Pricing (selling price)
    price = (
        frappe.db.get_value(
            "Item Price",
            {"item_code": website_item.item_code, "selling": 1},
            "price_list_rate",
        )
        or 0
    )

    # Product highlights
    highlights = [
        {
            "label": spec.label,
            "description": spec.description,
        }
        for spec in website_item.website_specifications
    ]

    # Main product image fallback
    product_image = frappe.db.get_value("Item", website_item.item_code, "image") or ""

    variants = []

    # Fetch variants
    if item.has_variants:
        variant_items = frappe.get_all(
            "Item",
            filters={
                "variant_of": website_item.item_code,
                "disabled": 0,
            },
            fields=["name", "item_code", "item_name"],
        )

        for variant in variant_items:
            # Check if variant is published on website
            variant_website_item = frappe.db.get_value(
                "Website Item",
                {
                    "item_code": variant.item_code,
                    "published": 1,
                },
                ["website_image"],
                as_dict=True,
            )

            if not variant_website_item:
                continue

            # Variant price
            variant_price = (
                frappe.db.get_value(
                    "Item Price",
                    {"item_code": variant.item_code, "selling": 1},
                    "price_list_rate",
                )
                or 0
            )

            # Variant attributes (parent = Item.name)
            attributes = frappe.get_all(
                "Item Variant Attribute",
                filters={"parent": variant.name},
                fields=["attribute", "attribute_value"],
            )

            # Variant image fallback
            variant_image = (
                variant_website_item.website_image
                or frappe.db.get_value("Item", variant.name, "image")
                or ""
            )

            variants.append(
                {
                    "item_code": variant.item_code,
                    "item_name": variant.item_name,
                    "price": float(variant_price),
                    "image": variant_image,
                    "attributes": [
                        {
                            "attribute": attr.attribute,
                            "value": attr.attribute_value,
                        }
                        for attr in attributes
                    ],
                }
            )

    # Documents
    documents = frappe.db.get_all(
        "Document Table",
        filters={"parenttype": "Website Item", "parent": website_item.name},
        fields=["document", "description", "heading"],
        order_by="idx asc",
    )

    for item in documents:
        item.document = frappe.utils.get_url(item.document)

    return {
        "success": True,
        "data": {
            "item_code": website_item.item_code,
            "name": website_item.web_item_name,
            "route": website_item.route or "",
            "image": product_image,
            "item_group": website_item.item_group or "",
            "price": float(price),
            "uom": website_item.stock_uom or "Nos",
            "short_description": website_item.short_description or "",
            "description": website_item.web_long_description or "",
            "highlights": highlights,
            "has_variants": item.has_variants,
            "variants": variants,
            "moq": item.custom_sales_moq,
            "documents": documents,
        },
    }
