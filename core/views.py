import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Module, SubModule, Status
from .serializers import StatusSerializer, ModuleSerializer, SubModuleSerializer

logger = logging.getLogger('colored')

MODULE_DOES_NOT_EXIST = 'Module tapılmadı.'
SUBMODULE_DOES_NOT_EXIST = 'Alt modul tapılmadı.'
MODULE_TITLE_DOESNOT_EXIST = 'Module id tapılmadı.'
USER_ACCESS_DENIED = 'İstifadəçinin girişi qadağandır.'


class ModulesRetrieveView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)
    queryset = Module.objects.all()

    def get(self, request, *args, **kwargs):
        user = request.user
        permitted_ids = set(
            self.queryset.filter(permitted_users=user).values_list('id', flat=True)
        )

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