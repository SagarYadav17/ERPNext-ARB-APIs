from collections import defaultdict
import frappe


@frappe.whitelist(allow_guest=True)
def get_homepage_products():
    homepage = frappe.get_single("Homepages")
    category_map = defaultdict(dict)

    for row in homepage.category_wise_product:
        # Fetch Website Item (including route)
        website_item = frappe.db.get_value(
            "Website Item",
            row.website_item,
            [
                "name",
                "item_code",
                "web_item_name",
                "route",
                "website_image",
                "stock_uom",
                "web_long_description",
            ],
            as_dict=True,
        )

        if not website_item:
            continue

        # Fetch Item image fallback
        item_image = (
            frappe.db.get_value("Item", website_item.item_code, "image")
        )

        # Fetch selling price
        price = (
            frappe.db.get_value(
                "Item Price",
                {"item_code": website_item.item_code, "selling": 1},
                "price_list_rate",
            )
            or 0
        )

        category = row.item_group

        # Initialize category if not exists
        if category not in category_map:
            category_map[category] = {
                "name": category,
                "image": website_item.website_image,
                "products": [],
            }

        category_map[category]["products"].append(
            {
                "item_code": website_item.item_code,
                "name": website_item.web_item_name,
                "route": website_item.route,
                "product_image": item_image,
                "item_group": category,
                "price": float(price),
                "uom": website_item.stock_uom or "Nos",
                "description": website_item.web_long_description,
            }
        )

    return {"categories": list(category_map.values())}
