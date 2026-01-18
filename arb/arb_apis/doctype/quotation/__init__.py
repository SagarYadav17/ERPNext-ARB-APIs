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
def create_quotation():
	try:
		data = frappe.parse_json(frappe.form_dict)

		required_fields = ["customer_name", "customer_email", "items", "company"]
		for f in required_fields:
			if not data.get(f):
				frappe.throw(f"Missing required field: {f}")

		# -------------------------
		# Customer
		# -------------------------
		customer = ensure_customer_exists(data)

		# -------------------------
		# Company (SOURCE OF TRUTH)
		# -------------------------
		company = frappe.get_doc("Company", data["company"])

		quotation = frappe.new_doc("Quotation")
		quotation.quotation_to = "Customer"
		quotation.party_name = customer.name
		quotation.customer_name = customer.customer_name
		quotation.contact_email = data["customer_email"]

		quotation.company = company.name
		quotation.currency = company.default_currency

		quotation.selling_price_list = "Standard Selling"
		quotation.price_list_currency = quotation.currency
		quotation.plc_conversion_rate = 1
		quotation.conversion_rate = 1

		quotation.transaction_date = data.get("created_date") or nowdate()
		quotation.valid_till = data.get("valid_until") or add_days(nowdate(), 15)
		quotation.order_type = "Sales"

		# -------------------------
		# Items
		# -------------------------
		for item in data["items"]:
			qty = flt(item.get("quantity", 1))
			rate = flt(item.get("unit_price", 0))
			quotation.append(
				"items",
				{
					"item_code": get_or_create_item(item),
					"item_name": item.get("product_name"),
					"description": item.get("variant", ""),
					"qty": qty,
					"rate": rate,
					"amount": qty * rate,
					"uom": "Nos",
					"conversion_factor": 1,
					"image": item.get("image", ""),
				},
			)

		# -------------------------
		# GST via Tax Template
		# -------------------------
		tax_template = get_tax_template(company.name)
		if tax_template:
			quotation.taxes_and_charges = tax_template
			quotation.tax_category = "Output GST"

		quotation.notes = data.get("notes", "")
		quotation.terms = data.get("terms", "")

		quotation.insert(ignore_permissions=True)

		if data.get("status") in ["sent", "approved", "paid"]:
			quotation.calculate_taxes_and_totals()
			quotation.submit()

		return {
			"success": True,
			"data": {
				"id": quotation.name,
				"quotationNumber": quotation.name,
				"status": get_react_status(quotation.status),
				"createdDate": quotation.transaction_date,
				"validUntil": quotation.valid_till,
			},
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Quotation Failed")
		return {"success": False, "error": str(e)}


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

		# -------------------------
		# ✅ SAFE TOTALS (CRITICAL FIX)
		# -------------------------
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
			"total": total,  # ✅ NEVER 0 (draft-safe)
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


@frappe.whitelist(allow_guest=True)
def get_companies():
	companies = frappe.get_all("Company", fields=["name", "company_name", "default_currency"])

	return {"success": True, "data": companies}


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


@frappe.whitelist()
def record_payment(quotation_id, payment_method, amount=None, transaction_id=None, notes=None):
	"""
	Record payment for quotation
	"""
	try:
		quotation = frappe.get_doc("Quotation", quotation_id)

		if not quotation:
			return {"success": False, "error": "Quotation not found"}

		# Check if quotation is approved
		if quotation.status != "Ordered":
			return {"success": False, "error": "Only approved quotations can be paid"}

		# Create Payment Entry
		payment_entry = frappe.new_doc("Payment Entry")
		payment_entry.payment_type = "Receive"
		payment_entry.party_type = "Customer"
		payment_entry.party = quotation.party_name
		payment_entry.paid_from = get_default_cash_or_bank_account(quotation.company)
		payment_entry.paid_to = get_default_cash_or_bank_account(quotation.company)
		payment_entry.paid_amount = amount or quotation.grand_total
		payment_entry.received_amount = amount or quotation.grand_total
		payment_entry.reference_no = transaction_id or frappe.generate_hash(length=12)
		payment_entry.reference_date = nowdate()
		payment_entry.mode_of_payment = payment_method
		payment_entry.company = quotation.company
		payment_entry.posting_date = nowdate()

		# Link to quotation
		payment_entry.append(
			"references",
			{
				"reference_doctype": "Quotation",
				"reference_name": quotation.name,
				"total_amount": quotation.grand_total,
				"outstanding_amount": 0,
				"allocated_amount": amount or quotation.grand_total,
			},
		)

		# Save and submit payment
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()

		# Update quotation with payment details
		quotation.db_set("status", "Ordered")

		# Add custom field for payment (if you added payment_method field)
		if frappe.db.exists("Custom Field", {"dt": "Quotation", "fieldname": "payment_method"}):
			quotation.db_set("payment_method", payment_method)

		if frappe.db.exists("Custom Field", {"dt": "Quotation", "fieldname": "paid_date"}):
			quotation.db_set("paid_date", nowdate())

		# Add comment
		quotation.add_comment(
			"Comment",
			f"Payment received via {payment_method}. Amount: {amount or quotation.grand_total}. Transaction ID: {transaction_id}",
		)

		return {
			"success": True,
			"message": "Payment recorded successfully",
			"payment_entry": payment_entry.name,
			"quotation_status": get_react_status("paid"),
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Record Payment Failed")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def convert_to_sales_order(quotation_id):
	"""
	Convert quotation to sales order
	"""
	try:
		quotation = frappe.get_doc("Quotation", quotation_id)

		if not quotation:
			return {"success": False, "error": "Quotation not found"}

		# Map quotation to sales order
		sales_order = get_mapped_doc(
			"Quotation",
			quotation_id,
			{
				"Quotation": {
					"doctype": "Sales Order",
					"field_map": {
						"name": "quotation",
						"party_name": "customer",
						"valid_till": "delivery_date",
					},
				},
				"Quotation Item": {
					"doctype": "Sales Order Item",
					"field_map": {
						"parent": "prevdoc_docname",
						"parenttype": "prevdoc_doctype",
					},
				},
			},
		)

		# Set additional fields
		sales_order.transaction_date = nowdate()
		sales_order.delivery_date = quotation.valid_till or add_days(nowdate(), 7)
		sales_order.status = "Draft"

		# Save and submit
		sales_order.insert(ignore_permissions=True)
		sales_order.submit()

		# Update quotation status
		quotation.db_set("status", "Ordered")
		quotation.add_comment("Comment", f"Converted to Sales Order: {sales_order.name}")

		return {
			"success": True,
			"message": "Converted to Sales Order successfully",
			"sales_order": sales_order.name,
			"quotation_status": get_react_status("approved"),
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Convert to Sales Order Failed")
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


@frappe.whitelist(allow_guest=True)
def delete_quotation(quotation_id):
	"""
	Delete a quotation (only if draft or expired)
	"""
	try:
		quotation = frappe.get_doc("Quotation", quotation_id)

		if not quotation:
			return {"success": False, "error": "Quotation not found"}

		# Check if can be deleted
		allowed_statuses = ["Draft", "Expired", "Lost", "Cancelled"]
		if quotation.status not in allowed_statuses:
			return {
				"success": False,
				"error": f"Cannot delete quotation with status: {quotation.status}",
			}

		# Cancel if submitted
		if quotation.docstatus == 1:
			quotation.cancel()

		# Delete
		quotation_name = quotation.name
		frappe.delete_doc("Quotation", quotation_id, ignore_permissions=True)

		return {
			"success": True,
			"message": f"Quotation {quotation_name} deleted successfully",
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Quotation Failed")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_quotation_stats():
	"""
	Get quotation statistics
	"""
	try:
		# Get counts by status
		status_counts = frappe.db.sql(
			"""
            SELECT
                status,
                COUNT(*) as count,
                SUM(grand_total) as total_amount
            FROM `tabQuotation`
            WHERE docstatus < 2
            GROUP BY status
        """,
			as_dict=True,
		)

		# Get monthly trend
		monthly_trend = frappe.db.sql(
			"""
            SELECT
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                COUNT(*) as count,
                SUM(grand_total) as amount
            FROM `tabQuotation`
            WHERE transaction_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            AND docstatus < 2
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month DESC
            LIMIT 6
        """,
			as_dict=True,
		)

		# Get top customers
		top_customers = frappe.db.sql(
			"""
            SELECT
                customer_name,
                COUNT(*) as quotation_count,
                SUM(grand_total) as total_amount
            FROM `tabQuotation`
            WHERE docstatus < 2
            GROUP BY customer_name
            ORDER BY total_amount DESC
            LIMIT 5
        """,
			as_dict=True,
		)

		# Map status for React
		status_map_erp_to_react = {
			"Draft": "draft",
			"Submitted": "sent",
			"Ordered": "approved",
			"Lost": "rejected",
			"Expired": "expired",
			"Cancelled": "rejected",
		}

		formatted_counts = {}
		for stat in status_counts:
			react_status = status_map_erp_to_react.get(stat.status, "draft")
			formatted_counts[react_status] = {
				"count": stat.count,
				"total_amount": stat.total_amount or 0,
			}

		return {
			"success": True,
			"data": {
				"status_counts": formatted_counts,
				"monthly_trend": monthly_trend,
				"top_customers": top_customers,
				"total_quotations": sum([s.count for s in status_counts]),
				"total_amount": sum([s.total_amount or 0 for s in status_counts]),
			},
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Quotation Stats Failed")
		return {"success": False, "error": str(e)}


# Helper Functions


def ensure_customer_exists(data):
	"""
	Ensure customer exists, create if not
	"""
	customer_name = data.get("customer_name")

	# Check if customer exists
	customer = frappe.db.exists("Customer", {"customer_name": customer_name})

	if customer:
		return frappe.get_doc("Customer", customer)

	# Create new customer
	customer = frappe.new_doc("Customer")
	customer.customer_name = customer_name
	customer.customer_type = "Company" if data.get("customer_company") else "Individual"
	customer.customer_group = "Commercial"
	customer.customer_company_name = data.get("customer_company", "")  # Store directly
	customer.territory = "India"
	customer.mobile_no = data.get("customer_phone", "")
	customer.email_id = data.get("customer_email", "")
	customer.tax_id = data.get("customer_gst", "")

	# Create address
	if data.get("customer_company"):
		address = frappe.new_doc("Address")
		address.address_title = customer_name
		address.address_type = "Office"
		address.address_line1 = data.get("customer_company", "")
		address.city = "Mumbai"
		address.country = "India"
		address.is_primary_address = 1
		address.is_shipping_address = 1
		address.insert(ignore_permissions=True)

		# Link address to customer
		customer.customer_primary_address = address.name

	customer.insert(ignore_permissions=True)

	return customer


@frappe.whitelist(allow_guest=True)
def get_or_create_item(item_data=None):
	if not item_data:
		frappe.throw("item_data is required")

	if isinstance(item_data, str):
		item_data = frappe.parse_json(item_data)

	item_code = item_data.get("product_id")
	if not item_code:
		frappe.throw("product_id is required")

	if frappe.db.exists("Item", {"item_code": item_code}):
		return item_code

	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = item_data.get("product_name", item_code)
	item.description = item_data.get("variant", "")
	item.item_group = "Products"
	item.stock_uom = "Nos"
	item.is_stock_item = 1
	item.image = item_data.get("image", "")

	# ❌ DO NOT SET standard_rate here
	item.insert(ignore_permissions=True)

	return item_code


def get_tax_template(company):
	"""
	Get GST tax template for company
	"""
	template = frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": company, "title": "GST"}, "name"
	)
	return template


def get_default_cash_or_bank_account(company):
	"""
	Get default cash or bank account for company
	"""
	account = frappe.db.get_value(
		"Account", {"company": company, "account_type": "Bank", "is_group": 0}, "name"
	)
	if not account:
		account = frappe.db.get_value(
			"Account",
			{"company": company, "account_type": "Cash", "is_group": 0},
			"name",
		)
	return account or ""


def get_item_image(item_code):
	"""
	Get item image URL
	"""
	image = frappe.db.get_value("Item", item_code, "image")
	return image or ""


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
