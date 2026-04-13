from __future__ import annotations

import json
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.notification_delivery_log import NotificationDeliveryLog
from app.models.notification_endpoint import NotificationEndpoint


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def upsert_notification_endpoint(
    db: Session,
    *,
    actor: str,
    name: str,
    channel_type: str,
    target: str,
    event_filter: str = "*",
    enabled: bool = True,
    secret: str | None = None,
) -> NotificationEndpoint:
    row = db.query(NotificationEndpoint).filter(NotificationEndpoint.name == name).first()
    if row is None:
        row = NotificationEndpoint(
            id=str(uuid.uuid4()),
            name=name,
            channel_type=channel_type,
            target=target,
        )
        db.add(row)
    row.channel_type = channel_type
    row.target = target
    row.event_filter = event_filter
    row.enabled = enabled
    row.secret = secret
    row.updated_by = actor
    db.commit()
    db.refresh(row)
    return row


def list_notification_endpoints(db: Session) -> list[NotificationEndpoint]:
    return db.query(NotificationEndpoint).filter(NotificationEndpoint.enabled.is_(True)).order_by(NotificationEndpoint.name.asc()).all()


def list_notification_delivery_logs(db: Session, *, limit: int = 50) -> list[NotificationDeliveryLog]:
    return db.query(NotificationDeliveryLog).order_by(NotificationDeliveryLog.created_at.desc()).limit(max(1, min(limit, 500))).all()


def send_notification_event(db: Session, *, event_type: str, payload: dict[str, Any]) -> list[NotificationDeliveryLog]:
    deliveries: list[NotificationDeliveryLog] = []
    for endpoint in list_notification_endpoints(db):
        if not _matches_event_filter(endpoint.event_filter, event_type):
            continue
        delivery = _deliver_to_endpoint(endpoint=endpoint, event_type=event_type, payload=payload)
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        deliveries.append(delivery)
    return deliveries


def _matches_event_filter(event_filter: str | None, event_type: str) -> bool:
    if not event_filter or event_filter.strip() == "*" or event_filter.strip() == "":
        return True
    allowed = {item.strip() for item in event_filter.split(",") if item.strip()}
    return event_type in allowed


def _deliver_to_endpoint(*, endpoint: NotificationEndpoint, event_type: str, payload: dict[str, Any]) -> NotificationDeliveryLog:
    try:
        if endpoint.channel_type == "slack":
            response_text = _post_json(endpoint.target, _build_slack_payload(event_type, payload), endpoint.secret)
            return _delivery(endpoint, event_type, "delivered", payload, response_text=response_text)
        if endpoint.channel_type == "webhook":
            response_text = _post_json(endpoint.target, payload, endpoint.secret)
            return _delivery(endpoint, event_type, "delivered", payload, response_text=response_text)
        if endpoint.channel_type == "email":
            if not os.getenv("SMTP_HOST"):
                return _delivery(endpoint, event_type, "planned_only", payload, error_message="SMTP_HOST not configured")
            _send_email(endpoint.target, event_type, payload)
            return _delivery(endpoint, event_type, "delivered", payload, response_text="smtp_sent")
        return _delivery(endpoint, event_type, "rejected", payload, error_message=f"Unsupported channel_type={endpoint.channel_type}")
    except Exception as exc:
        return _delivery(endpoint, event_type, "failed", payload, error_message=str(exc))


def _build_slack_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": f"[{event_type}] render-factory notification",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{event_type}*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "```" + _json(payload)[:2500] + "```"}},
        ],
    }


def _post_json(url: str, body: dict[str, Any], secret: str | None) -> str:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Notification-Secret"] = secret
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.text[:2000]


def _send_email(to_addr: str, event_type: str, payload: dict[str, Any]) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", username or "render-factory@local")

    msg = EmailMessage()
    msg["Subject"] = f"[{event_type}] render-factory notification"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(_json(payload))

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(msg)


def _delivery(endpoint: NotificationEndpoint, event_type: str, status: str, payload: dict[str, Any], response_text: str | None = None, error_message: str | None = None) -> NotificationDeliveryLog:
    return NotificationDeliveryLog(
        id=str(uuid.uuid4()),
        event_type=event_type,
        endpoint_name=endpoint.name,
        channel_type=endpoint.channel_type,
        delivery_status=status,
        payload_json=_json(payload),
        response_text=response_text,
        error_message=error_message,
    )
