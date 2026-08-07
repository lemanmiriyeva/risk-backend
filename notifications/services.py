import logging

from .models import Notification

logger = logging.getLogger("colored")


def notify(recipient, title, body="", notification_type=Notification.TYPE_OTHER,
           link="", related_app="", related_object_id=None):
    """
    Bir istifadəçiyə in-app bildiriş yaradır. recipient None-dursa (məs. hələ heç kim
    təyin olunmayıb - direktor/aparat rəhbəri yoxdursa) sakitcə heç nə etmir.
    """
    if not recipient:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        body=body,
        notification_type=notification_type,
        link=link,
        related_app=related_app,
        related_object_id=related_object_id,
    )
    logger.info(f"[BİLDİRİŞ] {recipient.username} <- {title}")
    return notification


def notify_many(recipients, **kwargs):
    """Eyni bildirişi bir neçə istifadəçiyə (məs. superuser-lərə) göndərmək üçün."""
    created = []
    seen_ids = set()
    for user in recipients:
        if not user or user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        created.append(notify(user, **kwargs))
    return created