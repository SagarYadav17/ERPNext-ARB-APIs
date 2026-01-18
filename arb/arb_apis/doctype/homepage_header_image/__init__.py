import frappe


@frappe.whitelist(allow_guest=True)
def get_homepage_header():
	homepage = frappe.get_single("Homepages")

	header = [{"idx": row.idx, "image": row.image, "alt_text": row.alt_text} for row in homepage.header]

	return {"header": header}
