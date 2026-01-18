import frappe


@frappe.whitelist(allow_guest=True)
def get_tracking_keys():
	doc = frappe.get_single("Tracking Settings")
	return {"ga_id": doc.ga_id, "meta_pixel_id": doc.meta_pixel_id, "enable_tracking": doc.enable_tracking}
