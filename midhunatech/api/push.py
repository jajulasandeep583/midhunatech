# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
Web Push notifications for the PWA (self-hosted, VAPID — no Firebase).

Flow:
  - Profile → "Enable notifications" registers a push service worker and
    POSTs the browser subscription here (subscribe/unsubscribe).
  - hooks.doc_events: a new Workflow Action (someone must approve a doc) or
    Notification Log (mention/assignment/alert) triggers a push to every
    subscribed device of the target users.
  - Tapping the notification deep-links into the app
    (/midhunatech/m/approvals?open=Doctype|Name).

VAPID keys are generated once per site and stored in site_config.json
(mt_vapid_public_key / mt_vapid_private_key).
"""

import base64
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

_VAPID_SUB = "mailto:aimidhunatech@gmail.com"


# ── VAPID keys ────────────────────────────────────────────────────────────────

def _get_or_create_keys():
    pub = frappe.conf.get("mt_vapid_public_key")
    priv = frappe.conf.get("mt_vapid_private_key")
    if pub and priv:
        return pub, priv

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    priv = base64.urlsafe_b64encode(
        key.private_numbers().private_value.to_bytes(32, "big")
    ).decode().rstrip("=")
    pub = base64.urlsafe_b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    ).decode().rstrip("=")

    from frappe.installer import update_site_config
    update_site_config("mt_vapid_public_key", pub)
    update_site_config("mt_vapid_private_key", priv)
    return pub, priv


@frappe.whitelist()
def get_vapid_public_key():
    """Public application-server key for PushManager.subscribe()."""
    pub, _priv = _get_or_create_keys()
    return pub


# ── subscription management ──────────────────────────────────────────────────

@frappe.whitelist()
def subscribe(subscription, user_agent=None):
    """Store this browser's push subscription for the logged-in user."""
    if isinstance(subscription, str):
        subscription = json.loads(subscription)
    endpoint = (subscription or {}).get("endpoint")
    keys = (subscription or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        frappe.throw(_("Invalid push subscription"))

    existing = frappe.get_all(
        "Midhunatech Push Subscription",
        filters={"endpoint": endpoint}, pluck="name", limit_page_length=1,
    )
    if existing:
        doc = frappe.get_doc("Midhunatech Push Subscription", existing[0])
    else:
        doc = frappe.new_doc("Midhunatech Push Subscription")
        doc.endpoint = endpoint
    doc.user = frappe.session.user
    doc.p256dh = keys["p256dh"]
    doc.auth = keys["auth"]
    doc.user_agent = (user_agent or frappe.get_request_header("User-Agent") or "")[:200]
    doc.last_used = now_datetime()
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def unsubscribe(endpoint):
    for name in frappe.get_all(
        "Midhunatech Push Subscription",
        filters={"endpoint": endpoint, "user": frappe.session.user},
        pluck="name",
    ):
        frappe.delete_doc("Midhunatech Push Subscription", name,
                          ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_status():
    """Does the current user have any subscription? (UI toggle state)"""
    n = frappe.db.count("Midhunatech Push Subscription", {"user": frappe.session.user})
    return {"subscribed": int(n or 0) > 0}


# ── sending ───────────────────────────────────────────────────────────────────

def send_to_users(users, title, body, url=None, tag=None):
    """Push to every device of `users`. Runs in a background job."""
    users = [u for u in set(users or []) if u and u not in ("Guest",)]
    if not users:
        return
    subs = frappe.get_all(
        "Midhunatech Push Subscription",
        filters={"user": ["in", users]},
        fields=["name", "endpoint", "p256dh", "auth"],
    )
    if not subs:
        return

    pub, priv = _get_or_create_keys()
    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/midhunatech/home",
        "tag": tag or "midhunatech",
    })

    from pywebpush import WebPushException, webpush

    for s in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": s.endpoint,
                    "keys": {"p256dh": s.p256dh, "auth": s.auth},
                },
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": _VAPID_SUB},
                ttl=86400,
            )
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):  # subscription expired / revoked
                frappe.delete_doc("Midhunatech Push Subscription", s.name,
                                  ignore_permissions=True, force=True)
            else:
                frappe.log_error(f"webpush failed ({code}): {e}", "Midhunatech Push")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Midhunatech Push")
    frappe.db.commit()


def _enqueue_send(users, title, body, url=None, tag=None):
    frappe.enqueue(
        "midhunatech.api.push.send_to_users",
        queue="short", enqueue_after_commit=True,
        users=list(users), title=title, body=body, url=url, tag=tag,
    )


# ── hooks (doc_events) ───────────────────────────────────────────────────────

def notify_workflow_action(doc, method=None):
    """A Workflow Action was created → tell everyone who can approve.
    Never raises — a push failure must not block the workflow."""
    try:
        if (doc.get("status") or "Open") != "Open":
            return
        users = set()
        if doc.get("user"):
            users.add(doc.user)
        roles = [r.role for r in (doc.get("permitted_roles") or []) if r.get("role")]
        if roles:
            users.update(frappe.get_all(
                "Has Role",
                filters={"role": ["in", roles], "parenttype": "User"},
                pluck="parent", distinct=True,
            ))
        users.discard(frappe.session.user)  # not the person who acted
        if not users:
            return
        ref_dt, ref_name = doc.get("reference_doctype"), doc.get("reference_name")
        state = doc.get("workflow_state") or ""
        _enqueue_send(
            users,
            title=_("Approval required"),
            body=f"{ref_dt} {ref_name}" + (f" — {state}" if state else ""),
            url=f"/midhunatech/m/approvals?open={ref_dt}|{ref_name}",
            tag=f"wf:{ref_dt}:{ref_name}",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Midhunatech Push (workflow)")


def notify_notification_log(doc, method=None):
    """Mirror Frappe in-app notifications (mentions, assignments, alerts)
    as push notifications. Never raises."""
    try:
        user = doc.get("for_user")
        if not user or user == frappe.session.user:
            return
        from frappe.utils import strip_html_tags
        subject = strip_html_tags(doc.get("subject") or "").strip() or _("Notification")
        body = strip_html_tags(doc.get("email_content") or "").strip()[:200]
        _enqueue_send(
            [user],
            title=subject[:120],
            body=body,
            url="/midhunatech/notifications",
            tag=f"nl:{doc.name}",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Midhunatech Push (notification)")
