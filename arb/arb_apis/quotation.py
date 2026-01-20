import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate


def resolve_totals(doc):
    subtotal = flt(doc.net_total)
    total = flt(doc.grand_total) or flt(doc.rounded_total)
    gst = total - subtotal
    return subtotal, gst, total


@frappe.whitelist(allow_guest=True)
def get_quotations(filters=None, page=1, page_size=20):
    try:
        page = cint(page)
        page_size = cint(page_size)
        start = (page - 1) * page_size

        quotations = frappe.get_all(
            "Quotation",
            fields=[
                "name",
                "party_name",
                "contact_email",
                "transaction_date",
                "valid_till",
                "net_total",
                "grand_total",
                "rounded_total",
                "status",
                "company",
            ],
            start=start,
            page_length=page_size,
            order_by="modified desc",
        )

        data = []

        for q in quotations:
            customer = frappe.get_doc("Customer", q.party_name)
            company = frappe.get_doc("Company", q.company)

            # ✅ SAFE TOTALS
            subtotal = flt(q.net_total)
            total = flt(q.grand_total) or flt(q.rounded_total)
            gst = total - subtotal

            items = frappe.get_all(
                "Quotation Item",
                filters={"parent": q.name},
                fields=[
                    "item_code as productId",
                    "item_name as productName",
                    "qty as quantity",
                    "rate as unitPrice",
                    "amount as totalPrice",
                    "image",
                ],
            )

            data.append(
                {
                    "id": q.name,
                    "quotationNumber": q.name,
                    "customerName": customer.customer_name,
                    "customerEmail": q.contact_email or "",
                    "customerPhone": customer.mobile_no or "",
                    "customerGST": customer.tax_id or "",
                    "company": {
                        "name": company.company_name,
                        "gst": company.tax_id,
                        "currency": company.default_currency,
                    },
                    "items": items,
                    "subtotal": subtotal,
                    "gst": gst,
                    "total": total,  # ✅ NEVER ZERO
                    "status": get_react_status(q.status),
                    "createdDate": q.transaction_date,
                    "validUntil": q.valid_till,
                }
            )

        return {"success": True, "data": data}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Quotations Failed")
        return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_quotation_details(quotation_id):
    try:
        quotation = frappe.get_doc("Quotation", quotation_id)

        if not quotation:
            frappe.throw(_("Quotation not found"))

        # -------------------------
        # Items
        # -------------------------
        items = []
        for item in quotation.items:
            items.append(
                {
                    "productId": item.item_code,
                    "productName": item.item_name,
                    "variant": item.description,
                    "quantity": item.qty,
                    "unitPrice": item.rate,
                    "totalPrice": item.amount,
                    "image": item.image or get_item_image(item.item_code),
                }
            )

        # -------------------------
        # Customer
        # -------------------------
        customer = frappe.get_doc("Customer", quotation.party_name)

        # -------------------------
        # Company (SOURCE OF TRUTH)
        # -------------------------
        company = frappe.get_doc("Company", quotation.company)

        subtotal, gst, total = resolve_totals(quotation)

        # -------------------------
        # Response
        # -------------------------
        response = {
            "id": quotation.name,
            "quotationNumber": quotation.name,
            "customerName": customer.customer_name,
            "customerEmail": quotation.contact_email or "",
            "customerPhone": customer.mobile_no or "",
            "customerGST": customer.tax_id or "",
            "company": {
                "name": company.company_name,
                "gst": company.tax_id,
                "currency": company.default_currency,
                "email": company.email or "",
                "phone": company.phone_no or "",
            },
            "items": items,
            "subtotal": subtotal,
            "gst": gst,
            "total": total,
            "status": get_react_status(quotation.status),
            "createdDate": quotation.transaction_date.strftime("%Y-%m-%d"),
            "validUntil": (quotation.valid_till.strftime("%Y-%m-%d") if quotation.valid_till else ""),
            "notes": quotation.notes or "",
            "terms": quotation.terms or "",
        }

        return {"success": True, "data": response}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Quotation Details Failed")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_quotation_status(quotation_id, status, notes=None):
    """
    Update quotation status
    """
    try:
        quotation = frappe.get_doc("Quotation", quotation_id)

        if not quotation:
            return {"success": False, "error": "Quotation not found"}

        # Map React status to ERPNext status
        status_map = {
            "draft": "Draft",
            "sent": "Submitted",
            "approved": "Ordered",
            "rejected": "Lost",
            "expired": "Expired",
            "paid": "Ordered",
        }

        erp_status = status_map.get(status)
        if not erp_status:
            return {"success": False, "error": f"Invalid status: {status}"}

        # Update status
        old_status = quotation.status
        quotation.status = erp_status

        # Add status change notes
        if notes:
            quotation.add_comment("Comment", f"Status changed from {old_status} to {erp_status}: {notes}")

        # Submit if status is sent/approved/paid
        if status in ["sent", "approved", "paid"] and quotation.docstatus == 0:
            quotation.submit()

        # Save changes
        quotation.save(ignore_permissions=True)

        # If converting to order
        if status == "approved":
            order = convert_to_order(quotation)
            return {
                "success": True,
                "message": f"Quotation {status} and converted to order {order.name}",
                "order_number": order.name,
                "quotation_status": get_react_status(quotation.status),
            }

        return {
            "success": True,
            "message": f"Quotation status updated to {status}",
            "quotation_status": get_react_status(quotation.status),
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Quotation Status Failed")
        return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def edit_quotation():
    try:
        data = frappe.form_dict

        # If JSON string is sent
        if isinstance(data, str):
            data = json.loads(data)

        required_fields = ["quotation_id", "quotation_number"]
        for field in required_fields:
            if not data.get(field):
                return {"success": False, "error": f"Missing required field: {field}"}

        # Get the quotation
        quotation_id = data.get("quotation_id")
        quotation = frappe.get_doc("Quotation", quotation_id)

        # Update fields if provided
        if "status" in data:
            # Map frontend status to backend status
            status_map = {
                "draft": "Draft",
                "sent": "Submitted",
                "approved": "Ordered",
                "rejected": "Lost",
                "expired": "Expired",
                "paid": "Paid",
            }
            backend_status = status_map.get(data["status"], "Draft")
            quotation.status = backend_status

            # Submit or cancel based on status
            if data["status"] in ["sent", "approved", "paid"] and quotation.docstatus == 0:
                quotation.submit()
            elif data["status"] in ["draft", "rejected", "expired"] and quotation.docstatus == 1:
                quotation.cancel()

        # Update other fields
        update_fields = [
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_company",
            "customer_gst",
            "notes",
            "terms",
            "valid_until",
        ]

        for field in update_fields:
            if field in data and data[field] is not None:
                if hasattr(quotation, field):
                    setattr(quotation, field, data[field])
                elif field == "customer_gst":
                    # Handle GST field specially
                    quotation.tax_id = data[field]

        # Save the changes
        quotation.save(ignore_permissions=True)

        # Return updated quotation
        return {
            "success": True,
            "message": "Quotation updated successfully",
            "quotation_number": quotation.name,
            "quotation_id": quotation.name,
            "data": {
                "id": quotation.name,
                "quotationNumber": quotation.name,
                "customerName": quotation.customer_name,
                "customerEmail": data.get("customer_email", ""),
                "customerPhone": data.get("customer_phone", ""),
                "customerCompany": data.get("customer_company", ""),
                "customerGST": data.get("customer_gst", ""),
                "subtotal": quotation.net_total,
                "gst": data.get("gst", 0),
                "total": quotation.grand_total,
                "status": get_react_status(quotation.status),
                "createdDate": quotation.transaction_date,
                "validUntil": quotation.valid_till,
                "terms": quotation.terms,
            },
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Quotation Edit Failed")
        return {"success": False, "error": str(e)}


def get_item_image(item_code):
    """
    Get item image URL from Website Item
    """
    # First try to get the website item image
    website_item_image = frappe.db.get_value("Website Item", {"item_code": item_code}, "website_image")

    # Fallback to Item image if Website Item doesn't exist
    if not website_item_image:
        website_item_image = frappe.db.get_value("Item", item_code, "image")

    return website_item_image or ""


def get_react_status(erp_status):
    """
    Convert ERPNext status to React status
    """
    status_map = {
        "Draft": "draft",
        "Submitted": "sent",
        "Open": "sent",
        "Replied": "sent",
        "Partially Ordered": "approved",
        "Ordered": "approved",
        "Lost": "rejected",
        "Cancelled": "rejected",
        "Expired": "expired",
    }
    return status_map.get(erp_status, "draft")


def convert_to_order(quotation):
    """
    Convert quotation to sales order internally
    """
    # This is a simplified version
    # You might want to use the built-in make_sales_order function
    from erpnext.selling.doctype.quotation.quotation import make_sales_order

    sales_order = make_sales_order(quotation.name)
    sales_order.insert(ignore_permissions=True)
    sales_order.submit()

    return sales_order
