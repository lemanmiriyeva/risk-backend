from django_auth_ldap.backend import populate_user
from django.dispatch import receiver
from django.db.models.signals import m2m_changed
from .models import User


@receiver(populate_user)
def set_defaults_for_new_user(sender, user, ldap_user, **kwargs):
    if not user.pk:  
        user.is_active = True     
        user.is_approved = False   


@receiver(m2m_changed, sender=User.groups.through)
def auto_approve_on_users_group(sender, instance, action, pk_set, **kwargs):
    if action != "post_add":
        return
    if instance.groups.filter(name="Users").exists():
        if instance.two_fa_confirmed and not instance.is_approved:
            instance.is_approved = True
            instance.save(update_fields=["is_approved"])