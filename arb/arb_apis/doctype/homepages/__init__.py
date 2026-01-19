from collections import defaultdict

import frappe


@frappe.whitelist(allow_guest=True)
def get_homepage_data():
    homepage = frappe.get_single("Homepages")

    # Header Images
    header = [{"idx": row.idx, "image": row.image, "alt_text": row.alt_text} for row in homepage.header]

    category_map = defaultdict(list)

    for row in homepage.category_wise_product:
        # Fetch item details
        item = frappe.db.get_value(
            "Item",
            row.website_item,
            ["name", "item_name", "image", "stock_uom", "description"],
            as_dict=True,
        )

        if not item:
            continue

        # Fetch selling price
        price = (
            frappe.db.get_value("Item Price", {"item_code": item.name, "selling": 1}, "price_list_rate") or 0
        )

        # Product item_group must be homepage section name
        product_group = row.item_group

        category_map[row.item_group].append(
            {
                "item_code": item.name,
                "name": item.item_name,
                "image": item.image or "/placeholder-product.jpg",
                "item_group": product_group,
                "price": float(price),
                "uom": item.stock_uom or "Nos",
                "description": item.description or "",
            }
        )

    categories = [{"name": category, "products": products} for category, products in category_map.items()]

    return {"message": {"header": header, "categories": categories}}
