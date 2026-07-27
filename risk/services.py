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


def log_created(instance, user, request=None):
    RiskLog.objects.create(
        risk=instance,
        risk_id_ref=instance.id,
        risk_designation=instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        action_type=RiskLog.ACTION_CREATED,
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

    if not changes:
        return  # heç nə dəyişməyibsə, loq yazma

    RiskLog.objects.create(
        risk=new_instance,
        risk_id_ref=new_instance.id,
        risk_designation=new_instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        action_type=RiskLog.ACTION_UPDATED,
        changes=changes,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_deleted(instance, user, request=None):
    from .serializers import RiskSerializer
    RiskLog.objects.create(
        risk=None,  # obyekt silinəcək, FK saxlamaq mənasız
        risk_id_ref=instance.id,
        risk_designation=instance.designation,
        user=user,
        user_username_snapshot=user.username if user else '',
        action_type=RiskLog.ACTION_DELETED,
        risk_snapshot=RiskSerializer(instance).data,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def log_exported(user, export_type, row_count, filters=None, request=None):
    label = EXPORT_TYPE_LABELS.get(export_type, export_type)
    RiskLog.objects.create(
        risk=None,               # export konkret bir riskə bağlı deyil
        risk_id_ref=0,
        risk_designation=f"Excel ixracı — {label}",
        user=user,
        user_username_snapshot=user.username if user else '',
        action_type=RiskLog.ACTION_EXPORTED,
        changes={
            'row_count': {'old': None, 'new': row_count},
            'filters': {'old': None, 'new': filters or {}},
        },
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )