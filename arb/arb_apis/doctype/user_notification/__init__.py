import frappe
from frappe import _
from arb.arb_apis.auth import require_jwt_auth


def _get_current_user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Unauthorized"), frappe.PermissionError)
    return user


def _validate_pagination(limit, offset):
    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        frappe.throw(_("Invalid pagination values"))

    if limit <= 0 or limit > 100:
        frappe.throw(_("Limit must be between 1 and 100"))

    if offset < 0:
        frappe.throw(_("Offset cannot be negative"))

    return limit, offset


def _get_user_notification(notification_id, user):
    if not notification_id:
        frappe.throw(_("Notification ID is required"))

    if not frappe.db.exists("User Notification", notification_id):
        frappe.throw(_("Notification not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("User Notification", notification_id)

    if doc.user != user:
        frappe.throw(_("You are not allowed to access this notification"), frappe.PermissionError)

    return doc


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_notifications(limit=20, offset=0):
    user = _get_current_user()
    limit, offset = _validate_pagination(limit, offset)

    names = frappe.get_all(
        "User Notification",
        filters={"user": user},
        pluck="name",
        order_by="creation desc",
        limit_start=offset,
        limit_page_length=limit
    )

    return [
        frappe.get_doc("User Notification", name).as_dict()
        for name in names
    ]


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def get_unread_count():
    user = _get_current_user()

    return frappe.db.count(
        "User Notification",
        {
            "user": user,
            "is_read": 0
        }
    )


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def mark_as_read(notification_id):
    user = _get_current_user()
    doc = _get_user_notification(notification_id, user)

    # Idempotent behavior
    if doc.is_read:
        return {"status": "already_read"}

    frappe.db.set_value(
        "User Notification",
        doc.name,
        {
            "is_read": 1,
            "read_at": frappe.utils.now()
        }
    )

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
@require_jwt_auth
def mark_all_as_read():
    user = _get_current_user()

    frappe.db.sql(
        """
        UPDATE `tabUser Notification`
        SET is_read = 1,
            read_at = NOW()
        WHERE user = %s
          AND is_read = 0
        """,
        (user,),
    )

    frappe.db.commit()
    return {"status": "success"}
