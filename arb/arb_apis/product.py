import frappe


@frappe.whitelist(allow_guest=True)
def get_detail(item_code):
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
        {"label": spec.label, "description": spec.description}
        for spec in website_item.website_specifications
    ]

    # Fetch variants if the item has variants
    variants = []
    item = frappe.get_cached_doc("Item", website_item.item_code)
    
    # Get main product image with fallback
    product_image = website_item.website_image or item.image or ""

    if item.has_variants:
        # Get all variant items
        variant_items = frappe.get_all(
            "Item",
            filters={"variant_of": website_item.item_code, "disabled": 0},
            fields=["name", "item_code", "item_name"],
        )

        for variant in variant_items:
            # Check if variant is published on website
            variant_website_item = frappe.db.get_value(
                "Website Item",
                {"item_code": variant.item_code},
                ["name", "published", "website_image"],
                as_dict=True,
            )

            if variant_website_item and variant_website_item.published:
                # Get variant price
                variant_price = (
                    frappe.db.get_value(
                        "Item Price",
                        {"item_code": variant.item_code, "selling": 1},
                        "price_list_rate",
                    )
                    or 0
                )

                # Get variant attributes
                attributes = frappe.get_all(
                    "Item Variant Attribute",
                    filters={"parent": variant.item_code},
                    fields=["attribute", "attribute_value"],
                )
                
                # Get variant image with fallback
                variant_image = variant_website_item.website_image
                if not variant_image:
                    variant_image = frappe.db.get_value("Item", variant.item_code, "image") or ""

                variants.append(
                    {
                        "item_code": variant.item_code,
                        "item_name": variant.item_name,
                        "price": float(variant_price),
                        "image": variant_image,
                        "attributes": [
                            {"attribute": attr.attribute, "value": attr.attribute_value}
                            for attr in attributes
                        ],
                    }
                )

    data = {
        "item_code": website_item.item_code,
        "name": website_item.web_item_name,
        "image": product_image,
        "item_group": website_item.item_group or "",
        "price": float(price),
        "uom": website_item.stock_uom or "Nos",
        "short_description": website_item.short_description or "",
        "description": website_item.web_long_description or "",
        "highlights": highlights,
        "has_variants": item.has_variants,
        "variants": variants,
    }

    return {"success": True, "data": data}
