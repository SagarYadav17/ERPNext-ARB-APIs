import frappe
import requests

def fetch_gst_details(gst_no):
    """
    Fetch GST details from external API
    Replace API URL & headers with your provider
    """

    # 🔐 Example config (store in Site Config / Doctype)
    api_url = frappe.conf.get("gst_api_url")
    api_key = frappe.conf.get("gst_api_key")

    if not api_url or not api_key:
        frappe.throw("GST API not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.get(
        f"{api_url}/{gst_no}",
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        frappe.throw("Failed to fetch GST details")

    data = response.json()

    return {
        "legal_name": data.get("legal_name"),
        "trade_name": data.get("trade_name"),
        "address": data.get("principal_place", {}).get("address"),
        "state": data.get("state"),
        "status": data.get("status")
    }
