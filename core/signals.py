from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import Module, SubModule


def _reject_ineligible_users(sender, instance, action, pk_set, model, **kwargs):
    """
    Module/SubModule.permitted_users-ə user əlavə edilərkən çağırılır.
    Əgər instance-ın permitted_organizations-ı doludursa, yalnız o qurum(lar)ın
    işçiləri əlavə oluna bilər - başqa qurumun user-i əlavə edilməyə çalışılarsa xəta verilir.
    """
    if action != "pre_add" or not pk_set:
        return

    if not instance.permitted_organizations.exists():
        return

    ineligible = model.objects.filter(pk__in=pk_set).exclude(
        organization_id__in=instance.permitted_organizations.values_list("id", flat=True)
    )
    if ineligible.exists():
        usernames = ", ".join(ineligible.values_list("username", flat=True))
        raise ValidationError(
            f"Bu modul/alt-modul üçün icazəli qurumlara aid olmayan istifadəçi(lər) "
            f"əlavə edilə bilməz: {usernames}. Əvvəlcə həmin user-in qurumunu "
            f"'İcazəli qurumlar' siyahısına əlavə edin, ya da başqa user seçin."
        )


@receiver(m2m_changed, sender=Module.permitted_users.through)
def validate_module_permitted_users(sender, instance, action, pk_set, model=None, **kwargs):
    from authentication.models import User
    _reject_ineligible_users(sender, instance, action, pk_set, User, **kwargs)

@receiver(m2m_changed, sender=SubModule.permitted_users.through)
def validate_sub_module_permitted_users(sender, instance, action, pk_set, **kwargs):
    from authentication.models import User
    kwargs.pop("model", None)
    _reject_ineligible_users(sender, instance, action, pk_set, User, **kwargs)