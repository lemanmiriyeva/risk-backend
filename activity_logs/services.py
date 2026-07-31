import logging

from .models import ActivityLog

logger = logging.getLogger('colored')

# Path prefix -> (module_code, module_title) uyğunlaşdırması.
# Yeni modul əlavə olunanda bura bir sətir əlavə etmək kifayətdir ki,
# həmin modulun sorğuları da loqda düzgün modul adı ilə görünsün.
MODULE_PREFIX_MAP = {
    'risk': ('risk', 'Risk Reyestri'),
    'authentication': ('authentication', 'İstifadəçi idarəetməsi'),
    'organization': ('authentication', 'İstifadəçi idarəetməsi'),
    'departments': ('authentication', 'İstifadəçi idarəetməsi'),
    'roles': ('authentication', 'İstifadəçi idarəetməsi'),
    'modules': ('core', 'Modullar'),
    'status': ('core', 'Statuslar'),
    'activity-logs': ('activity_logs', 'Loqlar'),
}

SENSITIVE_FIELDS = {'password', 'password1', 'password2', 'new_password', 'old_password', 'code', 'refresh', 'access'}


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def resolve_module(path: str):
    """
    '/api/risk/5/' kimi bir path-dan modul kodunu/adını çıxarır.
    Uyğunluq tapılmasa boş dəyərlər qaytarılır.
    """
    parts = [p for p in path.split('/') if p]
    # gözlənilən struktur: api/<module-prefix>/...
    if len(parts) >= 2 and parts[0] == 'api':
        prefix = parts[1]
        if prefix in MODULE_PREFIX_MAP:
            return MODULE_PREFIX_MAP[prefix]
    return '', ''


def sanitize_body(data):
    """Log-a düşməzdən əvvəl şifrə/token kimi həssas sahələri gizlədir."""
    if not isinstance(data, dict):
        return data
    cleaned = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            cleaned[key] = '***'
        else:
            cleaned[key] = value
    return cleaned


def log_event(
    user,
    action_type,
    module_code='',
    module_title='',
    sub_module_title='',
    description='',
    object_repr='',
    changes=None,
    request=None,
    request_method='',
    request_path='',
    status_code=None,
):
    """
    Sayt üzrə bir fəaliyyəti həm verilənlər bazasına (ActivityLog),
    həm də 'colored' logger vasitəsilə logs/app.log-a yazır.
    """
    username = getattr(user, 'username', '') or ''

    entry = ActivityLog.objects.create(
        user=user if (user and getattr(user, 'is_authenticated', False)) else None,
        user_username_snapshot=username,
        action_type=action_type,
        module_code=module_code,
        module_title=module_title,
        sub_module_title=sub_module_title,
        description=description,
        object_repr=object_repr,
        changes=changes,
        request_method=request_method or (request.method if request else ''),
        request_path=request_path or (request.path if request else ''),
        status_code=status_code,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )

    logger.info(
        f"[LOQ] {username or 'anonim'} - {entry.get_action_type_display()} "
        f"- modul={module_title or module_code or '-'} "
        f"- {description or entry.request_path}"
    )
    return entry


def log_login(user, request=None):
    return log_event(
        user=user,
        action_type=ActivityLog.ACTION_LOGIN,
        description=f"{getattr(user, 'username', '')} sistemə daxil oldu",
        request=request,
    )


def log_logout(user, request=None):
    return log_event(
        user=user,
        action_type=ActivityLog.ACTION_LOGOUT,
        description=f"{getattr(user, 'username', '')} sistemdən çıxış etdi",
        request=request,
    )