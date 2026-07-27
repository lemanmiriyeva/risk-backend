from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import Module


class ModuleListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        modules = Module.objects.filter(is_active=True).order_by("order")
        data = [
            {
                "title": m.title,
                "path": m.path,
                "permission": m.permission,
                "elevated_permission": m.elevated_permission,
                "elevated_path": m.elevated_path,
            }
            for m in modules
        ]
        return Response(data)