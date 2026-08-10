import logging
import re

from django_auth_ldap.backend import populate_user, ldap_error
from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from .models import User

logger = logging.getLogger("colored")


# @receiver(populate_user)
# def set_defaults_for_new_user(sender, user, ldap_user, **kwargs):
#     if not user.pk:
#         user.is_active = True
#         user.is_approved = False


# @receiver(m2m_changed, sender=User.groups.through)
# def auto_approve_on_users_group(sender, instance, action, pk_set, **kwargs):
#     if action != "post_add":
#         return
#     if instance.groups.filter(name="Users").exists():
#         if instance.two_fa_confirmed and not instance.is_approved:
#             instance.is_approved = True
#             instance.save(update_fields=["is_approved"])


# Active Directory-nin "AcceptSecurityContext error, data XXX" sub-kodları.
# Mənbə: Microsoft-un rəsmi LDAP bind xəta kodları sənədləşməsi.
LDAP_LOCK_CODES = {
    "775": "Hesabınız Active Directory-də çox sayda səhv giriş cəhdindən sonra bloklanıb. Zəhmət olmasa admin ilə əlaqə saxlayın.",
    "533": "Hesabınız Active Directory-də deaktiv edilib. Zəhmət olmasa admin ilə əlaqə saxlayın.",
    "701": "Hesabınızın Active Directory-də müddəti bitib. Zəhmət olmasa admin ilə əlaqə saxlayın.",
}
LDAP_PASSWORD_CODES = {
    "532": "Şifrənizin müddəti bitib. Zəhmət olmasa şifrənizi yeniləyin.",
    "773": "İlk girişdə şifrənizi dəyişməlisiniz. Zəhmət olmasa admin ilə əlaqə saxlayın.",
}


@receiver(ldap_error)
def handle_ldap_error(sender, context, user, request, exception, **kwargs):
    """
    django_auth_ldap istifadəçi/şifrə bind edərkən LDAPError alsa bu siqnalı göndərir.
    Aktiv Directory-nin blok/deaktiv/müddət bitmə səbəbini konkret mesaja çeviririk ki,
    istifadəçi "yanlış şifrə" əvəzinə əsl səbəbi görsün. Burada raise olunan exception
    django_auth_ldap tərəfindən udulmur - birbaşa çağıran view-a qədər ötürülür.
    """
    if context != "authenticate":
        return

    info = ""
    try:
        args0 = exception.args[0] if exception.args else {}
        if isinstance(args0, dict):
            info = args0.get("info", "") or args0.get("desc", "")
    except Exception:
        pass

    match = re.search(r"data (\d+)", info)
    if not match:
        return
    code = match.group(1)

    if code in LDAP_LOCK_CODES:
        logger.warning(f"[LDAP] Hesab bloklanıb (kod={code}): {info}")
        raise AuthenticationFailed(LDAP_LOCK_CODES[code], code="ldap_lock")

    if code in LDAP_PASSWORD_CODES:
        logger.warning(f"[LDAP] Şifrə problemi (kod={code}): {info}")
        raise AuthenticationFailed(LDAP_PASSWORD_CODES[code], code="ldap_password_issue")