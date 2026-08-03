import json
import logging

from .models import ActivityLog
from .services import get_client_ip, resolve_module, sanitize_body, humanize_changes
from datetime import timedelta
from django.utils import timezone

DEDUPE_WINDOW_SECONDS = 10
logger = logging.getLogger('colored')

METHOD_ACTION_MAP = {
    'GET': ActivityLog.ACTION_VIEWED,
    'POST': ActivityLog.ACTION_CREATED,
    'PUT': ActivityLog.ACTION_UPDATED,
    'PATCH': ActivityLog.ACTION_UPDATED,
    'DELETE': ActivityLog.ACTION_DELETED,
}

ACTION_VERBS = {
    ActivityLog.ACTION_VIEWED: 'baxdı',
    ActivityLog.ACTION_CREATED: 'yaratdı',
    ActivityLog.ACTION_UPDATED: 'redaktə etdi',
    ActivityLog.ACTION_DELETED: 'sildi',
}

IGNORED_PREFIXES = (
    '/api/activity-logs',
    '/api/authentication/token',
    '/api/authentication/user/logout',
    '/api/schema',
    '/api/docs',
    '/api/modules',
    '/static/',
    '/media/',
    '/admin/',
)


def is_module_root(path: str) -> bool:
    trimmed = path.rstrip('/')
    last_part = trimmed.split('/')[-1] if trimmed else ''
    return not last_part.isdigit()


def extract_object_repr(response, action_type):
    if action_type not in (ActivityLog.ACTION_CREATED, ActivityLog.ACTION_UPDATED):
        return ''
    data = getattr(response, 'data', None)
    if not isinstance(data, dict):
        return ''
    for key in ('designation', 'product_name', 'title', 'name', 'risk_name', 'label'):
        value = data.get(key)
        if value:
            return str(value)
    if data.get('id'):
        return f"#{data['id']}"
    return ''

def build_description(module_title, action_type, path, object_repr, status_code):
    module_label = module_title or 'sistem'
    verb = ACTION_VERBS.get(action_type, 'əməliyyat etdi')

    if action_type == ActivityLog.ACTION_VIEWED and is_module_root(path):
        description = f"{module_label} moduluna daxil oldu"
    elif object_repr:
        description = f"{module_label} modulunda \"{object_repr}\" adlı qeydi {verb}"
    else:
        description = f"{module_label} modulunda {verb}"

    if status_code and status_code >= 400:
        description += f" (uğursuz oldu)"

    return description


class ActivityLogMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH'):
            try:
                _ = request.body
            except Exception:
                pass

        response = self.get_response(request)
        try:
            self._log(request, response)
        except Exception as e:
            logger.error(f"ActivityLogMiddleware - loq yazıla bilmədi: {str(e)}")
        return response

    def _log(self, request, response):
        path = request.path

        if not path.startswith('/api/'):
            return
        if any(path.startswith(p) for p in IGNORED_PREFIXES):
            return

        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return

        status_code = getattr(response, 'status_code', None)

        module_code, module_title = resolve_module(path)
        action_type = METHOD_ACTION_MAP.get(request.method, ActivityLog.ACTION_OTHER)

        if action_type == ActivityLog.ACTION_VIEWED and is_module_root(path):
            recent_cutoff = timezone.now() - timedelta(seconds=DEDUPE_WINDOW_SECONDS)
            already_logged = ActivityLog.objects.filter(
                user=user,
                module_code=module_code,
                action_type=ActivityLog.ACTION_VIEWED,
                timestamp__gte=recent_cutoff,
            ).exists()
            if already_logged:
                return

        changes = None
        if request.method in ('POST', 'PUT', 'PATCH'):
            body = getattr(request, 'data', None) or getattr(request, 'POST', None)
            if body:
                try:
                    changes = sanitize_body(dict(body))
                except Exception:
                    changes = None
            if not changes:
                try:
                    raw = request.body
                    if raw:
                        changes = sanitize_body(json.loads(raw.decode('utf-8')))
                except Exception:
                    changes = None
            if changes:
                changes = humanize_changes(changes)

        object_repr = extract_object_repr(response, action_type)
        description = build_description(module_title, action_type, path, object_repr, status_code)

        username = getattr(user, 'username', '')

        ActivityLog.objects.create(
            user=user,
            user_username_snapshot=username,
            action_type=action_type,
            module_code=module_code,
            module_title=module_title,
            description=description,
            object_repr=object_repr,
            changes=changes,
            request_method=request.method,
            request_path=path,
            status_code=status_code,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        logger.info(
            f"[LOQ] {username or 'anonim'} - {dict(ActivityLog.ACTION_CHOICES).get(action_type, action_type)} "
            f"- modul={module_title or module_code or '-'} - {description} - ip={get_client_ip(request)}"
        )