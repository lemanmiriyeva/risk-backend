from .models import RiskLog

TRACKED_FIELDS = [
    'designation', 'legal_basis', 'international_framework', 'national_legal_reference',
    'asset_value', 'probability', 'impact', 'treatment_option', 'residual_risk',
    'update_frequency', 'incident_notification_notes', 'standard_references',
]

FIELD_LABELS = {
    'designation': 'Təyinat',
    'legal_basis': 'Hüquqi əsas',
    'international_framework': 'Beynəlxalq çərçivələr / Çərçivə istinadı',
    'national_legal_reference': 'Milli hüquqi istinad',
    'asset_value': 'Aktivin dəyəri (H)',
    'probability': 'Ehtimal (M)',
    'impact': 'Təsir (N)',
    'treatment_option': 'Emal variantı (Q)',
    'residual_risk': 'Qalıq risk (T)',
    'update_frequency': 'Yenilənmə tarixi/tezliyi',
    'incident_notification_notes': 'İnsident bildirişi qeydləri',
    'standard_references': 'Standartlara istinadlar',
    'inventory': 'Əlaqəli inventar',
}

EXPORT_TYPE_LABELS = {
    'risk_list': 'Risk Reyestri',
    'risk_logs': 'Risk Tarixçəsi',
}


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _resolve_organization(user, instance=None):
    if instance is not None:
        org = getattr(instance, "organization", None)
        if org is not None:
            return org
    return getattr(user, "organization", None)


def _inventory_repr(instance):
    inv = getattr(instance, "inventory", None)
    if not inv:
        return None
    return f"{inv.inventory_number} — {inv.product_name}"


def log_created(instance, user, request=None):
    RiskLog.objects.create(
        risk=instance,
        risk_id_ref=instance.id,
        risk_designation=instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user, instance),
        action_type=RiskLog.ACTION_CREATED,
        changes={'inventory': {'old': None, 'new': _inventory_repr(instance)}},
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_updated(old_instance, new_instance, user, request=None):
    changes = {}
    for field in TRACKED_FIELDS:
        old_val = getattr(old_instance, field)
        new_val = getattr(new_instance, field)
        if old_val != new_val:
            changes[field] = {"old": old_val, "new": new_val}

    # inventory FK-dır, TRACKED_FIELDS-dən ayrıca yoxlanılır
    old_inventory_id = getattr(old_instance, 'inventory_id', None)
    new_inventory_id = getattr(new_instance, 'inventory_id', None)
    if old_inventory_id != new_inventory_id:
        changes['inventory'] = {
            'old': _inventory_repr(old_instance),
            'new': _inventory_repr(new_instance),
        }

    if not changes:
        return  # heç nə dəyişməyibsə, loq yazma

    RiskLog.objects.create(
        risk=new_instance,
        risk_id_ref=new_instance.id,
        risk_designation=new_instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user, new_instance),
        action_type=RiskLog.ACTION_UPDATED,
        changes=changes,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_deleted(instance, user, request=None):
    from .serializers import RiskSerializer
    RiskLog.objects.create(
        risk=None,
        risk_id_ref=instance.id,
        risk_designation=instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user, instance),
        action_type=RiskLog.ACTION_DELETED,
        risk_snapshot=RiskSerializer(instance).data,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_exported(user, export_type, row_count, filters=None, request=None):
    label = EXPORT_TYPE_LABELS.get(export_type, export_type)
    RiskLog.objects.create(
        risk=None,
        risk_id_ref=0,
        risk_designation=f"Excel ixracı — {label}",
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user),
        action_type=RiskLog.ACTION_EXPORTED,
        changes={
            'row_count': {'old': None, 'new': row_count},
            'filters': {'old': None, 'new': filters or {}},
        },
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_viewed_list(user, row_count, filters=None, request=None):
    RiskLog.objects.create(
        risk=None,
        risk_id_ref=0,
        risk_designation=f"Risk Reyestri siyahısına baxıldı ({row_count} sətir)",
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user),
        action_type=RiskLog.ACTION_VIEWED,
        changes={'row_count': {'old': None, 'new': row_count}, 'filters': {'old': None, 'new': filters or {}}},
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_viewed_detail(instance, user, request=None):
    RiskLog.objects.create(
        risk=instance,
        risk_id_ref=instance.id,
        risk_designation=instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        organization=_resolve_organization(user, instance),
        action_type=RiskLog.ACTION_VIEWED,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )