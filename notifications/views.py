import logging
from datetime import timedelta

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger("colored")

PERIOD_CHOICES = ("today", "week", "month")


def _apply_period_filter(queryset, period):
    """period: 'today' | 'week' | 'month' - hamısı 'indidən geriyə' məntiqi ilə işləyir."""
    if period not in PERIOD_CHOICES:
        return queryset
    now = timezone.now()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    else:  # month
        since = now - timedelta(days=30)
    return queryset.filter(created_at__gte=since)


class NotificationListView(APIView):
    """
    GET /api/notifications/                       -> son bildirişlər (paginasiya olmadan, son 50) - header zəngi üçün
    GET /api/notifications/?unread=1               -> yalnız oxunmamışlar
    GET /api/notifications/?period=today|week|month -> tarix filtri
    GET /api/notifications/?page=1&page_size=20     -> tam bildirişlər səhifəsi üçün paginasiya olunmuş nəticə
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user)

        if request.query_params.get("unread") == "1":
            queryset = queryset.filter(is_read=False)

        period = request.query_params.get("period")
        queryset = _apply_period_filter(queryset, period)

        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

        page_param = request.query_params.get("page")
        if page_param:
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
            paginator = Paginator(queryset, page_size)
            page = paginator.get_page(page_param)
            serializer = NotificationSerializer(page.object_list, many=True)
            return Response({
                "results": serializer.data,
                "unread_count": unread_count,
                "count": paginator.count,
                "page": page.number,
                "num_pages": paginator.num_pages,
                "has_next": page.has_next(),
            }, status=HTTP_200_OK)

        # page param verilməyibsə - köhnə davranış (header zəngi üçün son 50)
        queryset = queryset[:50]
        serializer = NotificationSerializer(queryset, many=True)
        return Response({"results": serializer.data, "unread_count": unread_count}, status=HTTP_200_OK)


class NotificationUnreadCountView(APIView):
    """Header-dəki zəng ikonunun üstündəki rəqəmi tez-tez sorğulamaq üçün yüngül endpoint."""
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": count}, status=HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def patch(self, request, id):
        instance = get_object_or_404(Notification, id=id)
        if instance.recipient_id != request.user.id:
            return Response({"detail": "Bu bildiriş sizə aid deyil."}, status=HTTP_403_FORBIDDEN)

        if not instance.is_read:
            instance.is_read = True
            instance.read_at = timezone.now()
            instance.save(update_fields=["is_read", "read_at"])

        return Response(NotificationSerializer(instance).data, status=HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def patch(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=now,
        )
        logger.info(f"NotificationMarkAllReadView.patch - {request.user.username} {updated} bildirişi oxundu etdi")
        return Response({"updated": updated}, status=HTTP_200_OK)