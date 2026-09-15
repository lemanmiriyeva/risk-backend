import logging

from django.db.models import Q
from django.db.models.functions import ExtractDay, ExtractMonth
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from .filters import CircularFilterSet, NewsPostFilterSet
from .mixins import BulletinOrgScopedMixin
from .models import Circular, NewsPost
from .permissions import BulletinEditorPermission
from .serializers import BirthdayUserSerializer, CircularSerializer, NewsPostSerializer

logger = logging.getLogger('colored')

BULLETIN_MODULE_CODE = "bulletin"


class CircularViewSet(BulletinOrgScopedMixin, viewsets.ModelViewSet):
    """Sərəncamlar / Fərmanlar / Daxili qaydalar."""

    queryset = Circular.objects.select_related("organization", "created_by").filter(is_active=True)
    serializer_class = CircularSerializer
    permission_classes = [BulletinEditorPermission]
    module_code = BULLETIN_MODULE_CODE

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CircularFilterSet
    search_fields = ["title", "number"]
    ordering_fields = ["document_date", "created_at"]
    ordering = ["-document_date", "-created_at"]


class NewsPostViewSet(BulletinOrgScopedMixin, viewsets.ModelViewSet):
    """Xəbərlər lövhəsi."""

    queryset = NewsPost.objects.select_related("organization", "created_by").filter(is_active=True)
    serializer_class = NewsPostSerializer
    permission_classes = [BulletinEditorPermission]
    module_code = BULLETIN_MODULE_CODE

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NewsPostFilterSet
    search_fields = ["title", "summary", "body"]
    ordering_fields = ["published_at", "created_at"]
    ordering = ["-published_at"]


def _scoped_users(user):
    """Superuser - bütün aktiv işçilər; digərləri - öz qurumunun işçiləri."""
    qs = User.objects.filter(is_active=True, birth_date__isnull=False)
    if user.is_superuser:
        return qs
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return qs.none()
    return qs.filter(organization_id=org_id)


def _birthdays_this_month(user, today):
    qs = (
        _scoped_users(user)
        .annotate(birth_month=ExtractMonth("birth_date"), birth_day=ExtractDay("birth_date"))
        .filter(birth_month=today.month)
        .select_related("department", "role")
        .order_by("birth_day", "firstname", "lastname")
    )
    return list(qs)


class BirthdaysView(APIView):
    """
    Bu ay doğum günü olan (eyni qurumdan - superuser üçün bütün qurumlar)
    əməkdaşların siyahısı, günə görə sıralanmış.
    """

    module_code = BULLETIN_MODULE_CODE
    permission_classes = [BulletinEditorPermission]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        users = _birthdays_this_month(request.user, today)
        serializer = BirthdayUserSerializer(users, many=True, context={"request": request, "today": today})
        return Response(serializer.data)


class BulletinDashboardView(APIView):
    """
    Baş lövhə üçün tək çağırışda bütün datanı qaytarır:
    sol sütun (sərəncam/fərman/daxili qayda, kateqoriyalara görə qruplaşdırılmış),
    orta sütun (son xəbərlər), sağ sütun (bu ay doğum günü olanlar).
    """

    module_code = BULLETIN_MODULE_CODE
    permission_classes = [BulletinEditorPermission]

    CIRCULARS_LIMIT_PER_CATEGORY = 8
    NEWS_LIMIT = 12

    def get(self, request, *args, **kwargs):
        user = request.user
        today = timezone.localdate()

        if user.is_superuser:
            org_scope = Q()
        else:
            org_scope = Q(organization_id=getattr(user, "organization_id", None)) | Q(organization__isnull=True)

        circulars_qs = Circular.objects.select_related("organization", "created_by").filter(
            is_active=True
        ).filter(org_scope)

        circulars_by_category = {}
        for category, _label in Circular.CATEGORY_CHOICES:
            items = circulars_qs.filter(category=category)[: self.CIRCULARS_LIMIT_PER_CATEGORY]
            circulars_by_category[category] = CircularSerializer(
                items, many=True, context={"request": request}
            ).data

        news_qs = NewsPost.objects.select_related("organization", "created_by").filter(
            is_active=True
        ).filter(org_scope)[: self.NEWS_LIMIT]

        birthdays = _birthdays_this_month(user, today)

        return Response({
            "circulars": circulars_by_category,
            "news": NewsPostSerializer(news_qs, many=True, context={"request": request}).data,
            "birthdays": BirthdayUserSerializer(
                birthdays, many=True, context={"request": request, "today": today}
            ).data,
        })