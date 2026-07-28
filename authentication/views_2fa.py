import pyotp
import qrcode
import io
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.permissions import get_module_permissions


class TwoFASetupView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        user = request.user
        if user.two_fa_confirmed:
            module_perms = get_module_permissions(user)
            new_is_approved = bool(module_perms)
            if user.is_approved != new_is_approved:
                user.is_approved = new_is_approved
                user.save(update_fields=["is_approved"])

            return Response({
                "detail": "2FA artıq təsdiqlənib",
                "is_approved": user.is_approved,
                "permissions": module_perms,
            }, status=status.HTTP_200_OK)

        if not user.two_fa_secret:
            user.two_fa_secret = pyotp.random_base32()
            user.save(update_fields=["two_fa_secret"])

        totp = pyotp.totp.TOTP(user.two_fa_secret)
        uri = totp.provisioning_uri(name=user.username, issuer_name="Risk Reyestri Sistemi")

        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_base64 = base64.b64encode(buf.getvalue()).decode()

        return Response({
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "secret": user.two_fa_secret,
        })


class TwoFAVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def post(self, request):
        user = request.user
        code = request.data.get("code")

        if not user.two_fa_secret:
            return Response({"detail": "Əvvəlcə 2FA qurulmalıdır"}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.totp.TOTP(user.two_fa_secret)
        if not totp.verify(code, valid_window=1):
            return Response({"detail": "Kod yanlışdır"}, status=status.HTTP_400_BAD_REQUEST)

        user.two_fa_confirmed = True

        module_perms = get_module_permissions(user)
        user.is_approved = bool(module_perms)
        user.save(update_fields=["two_fa_confirmed", "is_approved"])

        return Response({
            "detail": "2FA təsdiqləndi",
            "is_approved": user.is_approved,
            "is_superuser": user.is_superuser,
            "permissions": module_perms,
        })