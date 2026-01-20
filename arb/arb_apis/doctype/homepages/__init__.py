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
            ["name", "item_code", "web_item_name", "website_image", "stock_uom", "web_long_description"],
            as_dict=True,
        )

        if not website_item:
            continue

        # Fetch selling price using the linked item code
        price = (
            frappe.db.get_value(
                "Item Price", {"item_code": website_item.item_code, "selling": 1}, "price_list_rate"
            )
            or 0
        )

        # Product item_group is the homepage section name
        product_group = row.item_group

        category_map[row.item_group].append(
            {
                "item_code": website_item.item_code,
                "name": website_item.web_item_name,
                "image": website_item.website_image or "/placeholder-product.jpg",
                "item_group": product_group,
                "price": float(price),
                "uom": website_item.stock_uom or "Nos",
                "description": website_item.web_long_description or "",
            }
        )

    categories = [{"name": category, "products": products} for category, products in category_map.items()]

    return {"message": {"header": header, "categories": categories}}
