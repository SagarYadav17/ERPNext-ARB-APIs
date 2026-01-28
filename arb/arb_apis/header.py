import frappe


def build_tree(item_groups, parent_name, included_items=None):
    """Recursively build hierarchical tree from flat list"""
    if included_items is None:
        included_items = set()

    tree = []
    for group in item_groups:
        if group.get("parent_item_group") == parent_name:
            included_items.add(group.get("name"))
            node = {
                "name": group.get("name"),
                "route": group.get("route"),
                "children": build_tree(item_groups, group.get("name"), included_items),
            }
            tree.append(node)
    return tree


@frappe.whitelist(allow_guest=True)
def get_item_groups():
    """Get available item groups in hierarchical structure"""
    # Fetch all item groups with parent information
    item_groups = frappe.get_all(
        "Item Group",
        filters={"show_in_website": 1},
        fields=["name", "parent_item_group", "is_group", "route"],
        order_by="name asc",
    )

    # Track which items are included in the tree
    included_items = set()

    # Build tree with only root-level groups (is_group=1, parent="All Item Groups")
    tree = []
    for group in item_groups:
        if (
            group.get("parent_item_group") == "All Item Groups"
            and group.get("is_group") == 1
        ):
            included_items.add(group.get("name"))
            node = {
                "name": group.get("name"),
                "route": group.get("route"),
                "children": build_tree(item_groups, group.get("name"), included_items),
            }
            tree.append(node)

    # Find orphaned non-group items (is_group=0 and not in tree, parent="All Item Groups")
    orphaned_items = []
    for group in item_groups:
        if (
            group.get("is_group") == 0
            and group.get("name") not in included_items
            and group.get("parent_item_group") == "All Item Groups"
        ):
            orphaned_items.append(
                {
                    "name": group.get("name"),
                    "route": group.get("route"),
                    "children": [],
                }
            )

    # Add "Other" group if there are orphaned items
    if orphaned_items:
        tree.append(
            {
                "name": "Other",
                "route": "other",
                "children": orphaned_items,
            }
        )

    # Return root level (children of "All Item Groups")
    return {"success": True, "data": tree}
