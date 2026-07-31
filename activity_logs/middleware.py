import json
import logging

from .models import ActivityLog
from .services import get_client_ip, resolve_module, sanitize_body

logger = logging.getLogger('colored')

METHOD_ACTION_MAP = {
    'GET': ActivityLog.ACTION_VIEWED,
    'POST': ActivityLog.ACTION_CREATED,
    'PUT': ActivityLog.ACTION_UPDATED,
    'PATCH': ActivityLog.ACTION_UPDATED,
    'DELETE': ActivityLog.ACTION_DELETED,
}

# Bu path-lar avtomatik loglanmır (özü loq baxışı, statik fayllar, admin, doc-lar və s.)
IGNORED_PREFIXES = (
    '/api/activity-logs',
    '/api/authentication/token',
    '/api/authentication/user/logout',
    '/api/schema',
    '/api/docs',
    '/static/',
    '/media/',
    '/admin/',
)


class ActivityLogMiddleware:
    """
    Saytın bütün API sorğularını avtomatik izləyir:
      - hansı istifadəçi
      - hansı modula girdi/hansı əməliyyatı etdi (GET=baxış, POST=yaratma,
        PUT/PATCH=dəyişiklik, DELETE=silmə)
      - harada (URL) və nə vaxt

    Login/logout kimi xüsusi hallar authentication/views.py-dan
    activity_logs.services.log_login / log_logout ilə ayrıca loglanır
    (çünki login anında request.user hələ təyin olunmayıb).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH'):
            # request.body-ni əvvəlcədən oxuyub keşləyirik ki, DRF parser stream-i
            # oxuduqdan sonra da (view işini bitirdikdən sonra) bu body-ə giriş
            # mümkün olsun. Əks halda 'you cannot access body after reading
            # from request's data stream' xətası yaranır.
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

        # Uğursuz sorğuları da qeyd edirik, amma statusu ilə birgə ki, fərqləndirilə bilsin
        status_code = getattr(response, 'status_code', None)

        module_code, module_title = resolve_module(path)
        action_type = METHOD_ACTION_MAP.get(request.method, ActivityLog.ACTION_OTHER)

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

        description = f"{request.method} {path}"
        if status_code and status_code >= 400:
            description += f" (uğursuz, status={status_code})"

        username = getattr(user, 'username', '')

        ActivityLog.objects.create(
            user=user,
            user_username_snapshot=username,
            action_type=action_type,
            module_code=module_code,
            module_title=module_title,
            description=description,
            changes=changes,
            request_method=request.method,
            request_path=path,
            status_code=status_code,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        logger.info(
            f"[LOQ] {username or 'anonim'} - {dict(ActivityLog.ACTION_CHOICES).get(action_type, action_type)} "
            f"- modul={module_title or module_code or '-'} - {description}"
        )