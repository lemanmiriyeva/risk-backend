import logging
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Module, SubModule, Status
from .serializers import StatusSerializer, ModuleSerializer, SubModuleSerializer
from .permissions import get_user_modules
from authentication.models import Organization

logger = logging.getLogger('colored')

MODULE_DOES_NOT_EXIST = 'Module tapılmadı.'
SUBMODULE_DOES_NOT_EXIST = 'Alt modul tapılmadı.'
MODULE_TITLE_DOESNOT_EXIST = 'Module id tapılmadı.'
USER_ACCESS_DENIED = 'İstifadəçinin girişi qadağandır.'


from .permissions import IsOrgAdmin, get_managed_organization


NO_ORGANIZATION = "İdarə etdiyiniz qurum təyin edilə bilmədi."
NOT_ELIGIBLE_MODULE = "Bu modul/alt-modul sizin qurumunuz üçün nəzərdə tutulmayıb."
USER_OUTSIDE_ORG = "Bu istifadəçi sizin qurumunuza aid deyil."


def _user_payload(user, permitted_ids):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "has_access": user.id in permitted_ids,
    }


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class ModuleOrganizationAccessView(APIView):
    """
    Superuser panelinin "Modul icazələri" bölməsi üçün - hansı modul/alt-modulun
    hansı QURUM(lar)a açıq olduğunu idarə edir (Module/SubModule.permitted_organizations).
    Yalnız superuser istifadə edə bilər - qurum admini bu səviyyəyə çıxış almır, o yalnız
    artıq öz qurumuna açılmış modullar daxilində öz işçilərinə giriş verə bilər
    (bax: OrgModuleAccessView).
    """
    permission_classes = [IsSuperUser]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, *args, **kwargs):
        organizations = [
            {"id": org.id, "title": org.title}
            for org in Organization.objects.filter(is_active=True).order_by("title")
        ]

        modules_data = []
        for module in Module.objects.all().order_by("id"):
            module_org_ids = list(module.permitted_organizations.values_list("id", flat=True))

            sub_modules_data = []
            for sub in module.sub_modules.all().order_by("id"):
                sub_modules_data.append({
                    "id": sub.id,
                    "title": sub.title,
                    "organization_ids": list(sub.permitted_organizations.values_list("id", flat=True)),
                })

            modules_data.append({
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "organization_ids": module_org_ids,
                "sub_modules": sub_modules_data,
            })

        return Response({"organizations": organizations, "modules": modules_data}, status=HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        target = request.data.get("target")
        obj_id = request.data.get("id")
        organization_id = request.data.get("organization_id")
        grant = bool(request.data.get("grant"))

        if target not in ("module", "sub_module") or not obj_id or not organization_id:
            return Response(
                {"detail": "target, id və organization_id sahələri məcburidir."}, status=HTTP_400_BAD_REQUEST
            )

        model = Module if target == "module" else SubModule
        try:
            obj = model.objects.get(id=obj_id)
        except model.DoesNotExist:
            return Response({"detail": "Modul/alt-modul tapılmadı."}, status=HTTP_404_NOT_FOUND)

        organization = Organization.objects.filter(id=organization_id).first()
        if not organization:
            return Response({"detail": "Qurum tapılmadı."}, status=HTTP_404_NOT_FOUND)

        if target == "sub_module" and grant and not obj.module.permitted_organizations.filter(id=organization.id).exists():
            return Response(
                {"detail": "Əvvəlcə qurumun əsas modula girişi açılmalıdır."}, status=HTTP_400_BAD_REQUEST
            )

        if grant:
            obj.permitted_organizations.add(organization)
            logger.info(f"{request.user} - {organization.title} üçün {obj} girişi AÇDI")
        else:
            obj.permitted_organizations.remove(organization)
            logger.info(f"{request.user} - {organization.title} üçün {obj} girişi BAĞLADI")

        return Response({"access": grant}, status=HTTP_200_OK)


class OrgModuleAccessView(APIView):
    permission_classes = [IsOrgAdmin]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, *args, **kwargs):
        organization = get_managed_organization(request)
        if not organization:
            return Response({"detail": NO_ORGANIZATION}, status=HTTP_400_BAD_REQUEST)

        org_users = list(organization.users.filter(is_active=True).order_by("firstname"))

        modules_data = []
        for module in Module.objects.filter(permitted_organizations=organization).order_by("id"):
            module_permitted_ids = set(module.permitted_users.values_list("id", flat=True))

            sub_modules_data = []
            for sub in module.sub_modules.filter(permitted_organizations=organization).order_by("id"):
                sub_permitted_ids = set(sub.permitted_users.values_list("id", flat=True))
                sub_modules_data.append({
                    "id": sub.id,
                    "title": sub.title,
                    "users": [_user_payload(u, sub_permitted_ids) for u in org_users],
                })

            modules_data.append({
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "sub_modules": sub_modules_data,
                "users": [_user_payload(u, module_permitted_ids) for u in org_users],
            })

        return Response({
            "organization": {"id": organization.id, "title": organization.title},
            "modules": modules_data,
        }, status=HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        organization = get_managed_organization(request)
        if not organization:
            return Response({"detail": NO_ORGANIZATION}, status=HTTP_400_BAD_REQUEST)

        target = request.data.get("target")
        obj_id = request.data.get("id")
        user_id = request.data.get("user_id")
        grant = bool(request.data.get("grant"))

        if target not in ("module", "sub_module") or not obj_id or not user_id:
            return Response({"detail": "target, id və user_id sahələri məcburidir."}, status=HTTP_400_BAD_REQUEST)

        model = Module if target == "module" else SubModule
        try:
            obj = model.objects.get(id=obj_id)
        except model.DoesNotExist:
            return Response({"detail": "Modul/alt-modul tapılmadı."}, status=HTTP_404_NOT_FOUND)

        if not obj.permitted_organizations.filter(id=organization.id).exists():
            logger.info(f"{request.user} - qurum əhatəsindən kənar modula cəhd: {obj}")
            return Response({"detail": NOT_ELIGIBLE_MODULE}, status=HTTP_403_FORBIDDEN)

        target_user = organization.users.filter(id=user_id).first()
        if not target_user:
            logger.info(f"{request.user} - başqa qurumun user-inə icazə vermə cəhdi: user_id={user_id}")
            return Response({"detail": USER_OUTSIDE_ORG}, status=HTTP_403_FORBIDDEN)

        if target == "sub_module" and grant and not obj.module.has_permission(target_user):
            return Response(
                {"detail": "Əvvəlcə istifadəçiyə əsas modula giriş verilməlidir."},
                status=HTTP_400_BAD_REQUEST,
            )

        if grant:
            obj.permitted_users.add(target_user)
            logger.info(f"{request.user} - {target_user.username} üçün {obj} girişi AÇDI")
        else:
            obj.permitted_users.remove(target_user)
            logger.info(f"{request.user} - {target_user.username} üçün {obj} girişi BAĞLADI")

        return Response({"access": grant}, status=HTTP_200_OK)




class ModulesRetrieveView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)
    queryset = Module.objects.all()

    def get(self, request, *args, **kwargs):
        user = request.user
        # get_user_modules() - modul icazələri üçün YEGANƏ mənbə (core/permissions.py).
        # Burada ayrıca/təkrar məntiq yazılmır ki, gələcəkdə icazə qaydaları
        # dəyişəndə iki yerdə eyni işi fərqli edib uyğunsuzluq yaranmasın.
        permitted_ids = set(get_user_modules(user).values_list('id', flat=True))

        result = []
        for module in self.queryset.order_by('id'):
            if module.id in permitted_ids:
                result.append(ModuleSerializer(module, context={'request': request}).data)
            else:
                result.append({
                    "id": module.id,
                    "title": module.title,
                })
        return Response(result)


class CheckModuleAccessView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def post(self, request, *args, **kwargs):
        module_url = request.data.get("module_url", None)
        logger.info(f"{request.user} try to access module {module_url}")
        if not module_url:
            return Response({"detail": MODULE_TITLE_DOESNOT_EXIST}, status=HTTP_400_BAD_REQUEST)

        try:
            module = Module.objects.get(url_endpoint__iexact=module_url)
        except Module.DoesNotExist:
            return Response({"detail": MODULE_DOES_NOT_EXIST}, status=HTTP_404_NOT_FOUND)

        if not module.has_permission(request.user):
            return Response({"detail": USER_ACCESS_DENIED}, status=HTTP_403_FORBIDDEN)

        return Response({"access": True}, status=HTTP_200_OK)


class CheckSubModuleAccessView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def post(self, request, *args, **kwargs):
        module_url = request.data.get("module_url", None)
        sub_module_url = request.data.get("sub_module_url", None)
        logger.info(f"{request.user} try to access sub_module {sub_module_url} under {module_url}")

        if not module_url or not sub_module_url:
            return Response({"detail": MODULE_TITLE_DOESNOT_EXIST}, status=HTTP_400_BAD_REQUEST)

        try:
            module = Module.objects.get(url_endpoint__iexact=module_url)
        except Module.DoesNotExist:
            return Response({"detail": MODULE_DOES_NOT_EXIST}, status=HTTP_404_NOT_FOUND)

        try:
            sub_module = SubModule.objects.get(module=module, url_endpoint__iexact=sub_module_url)
        except SubModule.DoesNotExist:
            return Response({"detail": SUBMODULE_DOES_NOT_EXIST}, status=HTTP_404_NOT_FOUND)

        if not sub_module.has_permission(request.user):
            return Response({"detail": USER_ACCESS_DENIED}, status=HTTP_403_FORBIDDEN)

        return Response({"access": True}, status=HTTP_200_OK)


class StatusViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ]
    authentication_classes = (JWTAuthentication,)

    queryset = Status.objects.all()
    serializer_class = StatusSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(self.serializer_class(queryset, many=True).data, status=HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"{request.user} created Invoice Status!")
            return Response(serializer.data, status=HTTP_200_OK)

        logger.error(f"{request.user} couldn't create Invoice Status!")
        return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)