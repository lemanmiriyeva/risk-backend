import logging
import pyotp
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework.generics import RetrieveAPIView
from rest_framework.status import HTTP_403_FORBIDDEN, \
    HTTP_401_UNAUTHORIZED, HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_201_CREATED
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from python_ipware import IpWare
from django.shortcuts import get_object_or_404
from core.contstants import INVALID_CREDENTIALS, USER_LOCKED
from core.permissions import user_has_any_module_access
from activity_logs import services as activity_log_services
from .models import User, Department, LoginAttempt, PasswordReset, Role
from .serializers import UserSerializer, DepartmentListSerializer, PasswordResetRequestSerializer, \
    OrganizationDetailSerializer, RoleSerializer, TwoFAResetRequestSerializer, UserProfileUpdateSerializer

ipw = IpWare()

MAX_ATTEMPTS = 3
LOCKOUT_TIME = 300

NO_SYSTEM_ACCESS = "Bu sistemə giriş icazəniz yoxdur. Zəhmət olmasa sistem administratoru ilə əlaqə saxlayın."

logger = logging.getLogger('colored')

from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


def _find_active_user(identifier):
    """
    identifier - istifadəçi adı VƏ YA email ola bilər (login, şifrə sıfırlama və
    2FA sıfırlama sorğularının hamısında istifadəçi bu iki üsuldan biri ilə
    özünü təqdim edə bilir).
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    return User.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier), is_active=True
    ).first()


class UsersView(APIView):
    def get(self, request):
        department_id = request.query_params.get('department', None)
        search = request.query_params.get('search', '').strip()

        logger.info(f"UsersView.get çağırıldı - department={department_id}, search='{search}'")

        if department_id:
            users_qs = User.objects.filter(Q(department__id=department_id)
                    & Q(is_active=True))
        else:
            users_qs = User.objects.filter(is_active=True).all()

        if search:
            terms = search.split()
            if len(terms) == 1:
                term = terms[0]
                users_qs = users_qs.filter(
                    Q(firstname__icontains=term)
                    | Q(lastname__icontains=term)
                    | Q(phone_number__icontains=term)
                )
            else:
                t0, t1 = terms[0], terms[1]
                q_filter = (
                    Q(firstname__icontains=t0, lastname__icontains=t1)
                    | Q(firstname__icontains=t1, lastname__icontains=t0)
                )
                for term in terms:
                    q_filter |= Q(firstname__icontains=term)
                    q_filter |= Q(lastname__icontains=term)
                    q_filter |= Q(phone_number__icontains=term)
                users_qs = users_qs.filter(q_filter)

        users_qs = users_qs.order_by('firstname')

        if not users_qs.exists():
            logger.info(f"UsersView.get - nəticə tapılmadı (department={department_id}, search='{search}')")
            return Response(status=status.HTTP_404_NOT_FOUND)

        logger.info(f"UsersView.get - {users_qs.count()} istifadəçi tapıldı")
        users = UserSerializer(users_qs, many=True)
        return Response(users.data)


class DepartmentListView(APIView):
    def get(self, request):
        logger.info("DepartmentListView.get çağırıldı")
        departments = Department.objects.filter(parent__isnull=True)\
            .order_by('title')\
            .prefetch_related("children", "manager")
        serializer = DepartmentListSerializer(departments, many=True)
        logger.info(f"DepartmentListView.get - {departments.count()} şöbə qaytarıldı")
        return Response(serializer.data)


class UserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        user = request.user

        if user.two_fa_confirmed:
            should_be_approved = user_has_any_module_access(user)
            if user.is_approved != should_be_approved:
                user.is_approved = should_be_approved
                user.save(update_fields=["is_approved"])

        logger.info(f"UserView.get - {user.username} öz məlumatını sorğuladı")
        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        """
        Şəxsi kabinet - istifadəçi öz məlumatlarını (ad, soyad, telefon, doğum tarixi,
        cinsiyyət) özü yeniləyə bilər. username, email, fin_kod və qurumla bağlı heç bir
        sahə bu endpoint-dən dəyişdirilə bilməz (UserProfileUpdateSerializer-in fields
        siyahısı ilə məhdudlaşdırılıb).
        """
        user = request.user
        serializer = UserProfileUpdateSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"UserView.patch - {user.username} öz profilini yenilədi")
        return Response(UserSerializer(user, context={"request": request}).data, status=status.HTTP_200_OK)


class UserDetailView(APIView):
    def get(self, request, id):
        logger.info(f"UserDetailView.get - id={id} sorğulandı")
        user = get_object_or_404(User, id=id)
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    def post(self, request):
        refresh = request.data.get("refresh")
        try:
            token = RefreshToken(refresh.get('value'))
            token.blacklist()
            logger.info(f'{request.user.username} logged out!')
            try:
                activity_log_services.log_logout(request.user, request=request)
            except Exception as e:
                logger.error(f"LogoutView - çıxış loqu yazıla bilmədi ({request.user.username}): {str(e)}")
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            logger.error(f"LogoutView - token xətası ({request.user.username}): {str(e)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"LogoutView - gözlənilməz xəta ({request.user.username}): {str(e)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)


GENERIC_RESET_MESSAGE = (
    "Sorğunuz qəbul olundu. Əgər daxil etdiyiniz istifadəçi adı sistemdə mövcuddursa, "
    "e-poçt ünvanınıza bir dəfəlik kod göndərildi."
)
RESET_CODE_INVALID_MESSAGE = "Kod yanlışdır və ya vaxtı bitib. Zəhmət olmasa yenidən sorğu göndərin."
RESET_CODE_TTL_MINUTES = 15

# Qarışıq düşə biləcək simvollar (0/O, 1/l/I) çıxarılıb - göndərilən şifrəni yazmaq asan olsun deyə.
PASSWORD_CHARS = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"
RESET_CODE_CHARS = "0123456789"
NO_EMAIL = "İstifadəçinin email ünvanı olmadığı üçün şifrə göndərilə bilmədi."


def _generate_password(length=10):
    return get_random_string(length, allowed_chars=PASSWORD_CHARS)


def _send_new_password_email(user, password, is_new_account):
    if not user.email:
        raise ValueError(NO_EMAIL)

    subject = "Hesabınız yaradıldı" if is_new_account else "Şifrəniz yeniləndi"
    intro = (
        "Risk idarəetmə sistemində sizin üçün hesab yaradıldı."
        if is_new_account else
        "Admin tərəfindən hesabınızın şifrəsi yeniləndi."
    )
    body = (
        f"{intro}\n\n"
        f"İstifadəçi adı: {user.username}\n"
        f"Yeni şifrə: {password}\n\n"
        f"Təhlükəsizlik baxımından, sistemə daxil olduqdan sonra bu şifrəni dəyişdirməyiniz tövsiyə olunur."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _send_reset_code_email(user, code):
    if not user.email:
        raise ValueError(NO_EMAIL)

    subject = "Şifrə sıfırlama kodu"
    body = (
        f"Salam {user.name or user.username},\n\n"
        f"Şifrənizi sıfırlamaq üçün bir dəfəlik kod:\n\n"
        f"{code}\n\n"
        f"Bu kod {RESET_CODE_TTL_MINUTES} dəqiqə ərzində etibarlıdır. Kodu sistemdəki "
        f"\"Şifrəni təyin et\" səhifəsində daxil edərək özünüz üçün yeni şifrə seçə bilərsiniz.\n\n"
        f"Əgər bu sorğunu siz göndərməmisinizsə, bu maili nəzərə almayın."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )


class RequestPasswordResetView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"].strip()
        logger.info(f"RequestPasswordResetView.post - şifrə sıfırlama sorğusu: {username}")

        user = _find_active_user(username)

        if user:
            try:
                self._send_code(user)
            except Exception as e:
                logger.error(f"RequestPasswordResetView.post - {username} üçün kod xətası: {str(e)}")
        else:
            logger.info(f"RequestPasswordResetView.post - {username} tapılmadı")

        return Response({"detail": GENERIC_RESET_MESSAGE}, status=HTTP_200_OK)

    def _send_code(self, user):
        if not user.email:
            logger.error(f"RequestPasswordResetView._send_code - {user.username} üçün email ünvanı yoxdur")
            return

        code = get_random_string(6, allowed_chars=RESET_CODE_CHARS)

        PasswordReset.objects.filter(email=user.email, active=True).update(active=False)
        PasswordReset.objects.create(email=user.email, token=code)

        _send_reset_code_email(user, code)
        logger.info(f"RequestPasswordResetView._send_code - {user.username} üçün kod mail ilə göndərildi")


class ConfirmPasswordResetSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=20)
    new_password = serializers.CharField(min_length=8, max_length=128)


class ConfirmPasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ConfirmPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"].strip()
        code = serializer.validated_data["code"].strip()
        new_password = serializer.validated_data["new_password"]

        user = _find_active_user(username)
        if not user:
            logger.info(f"ConfirmPasswordResetView.post - {username} tapılmadı")
            return Response({"detail": RESET_CODE_INVALID_MESSAGE}, status=HTTP_400_BAD_REQUEST)

        cutoff = timezone.now() - timedelta(minutes=RESET_CODE_TTL_MINUTES)
        reset_record = PasswordReset.objects.filter(
            email=user.email, token=code, active=True, created_at__gte=cutoff,
        ).order_by("-created_at").first()

        if not reset_record:
            logger.info(f"ConfirmPasswordResetView.post - {username} üçün kod yanlış/vaxtı bitib")
            return Response({"detail": RESET_CODE_INVALID_MESSAGE}, status=HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        PasswordReset.objects.filter(email=user.email, active=True).update(active=False)

        logger.info(f"ConfirmPasswordResetView.post - {username} öz şifrəsini uğurla yenilədi")
        return Response({"detail": "Şifrəniz uğurla yeniləndi. İndi yeni şifrənizlə daxil ola bilərsiniz."}, status=HTTP_200_OK)
        logger.info(f"RequestPasswordResetView._reset_and_send - {user.username} üçün yeni şifrə mail ilə göndərildi")


TWO_FA_RESET_MESSAGE = (
    "Sorğunuz qəbul olundu. Məlumatlarınız doğrudursa, 2FA sıfırlanıb və e-poçt ünvanınıza "
    "bildiriş göndərildi. Növbəti daxilolma zamanı sistem sizə yeni QR kod göstərəcək."
)


def _send_2fa_reset_email(user):
    if not user.email:
        raise ValueError(NO_EMAIL)

    subject = "İki mərhələli autentifikasiya (2FA) sıfırlandı"
    body = (
        f"Salam {user.name or user.username},\n\n"
        f"Hesabınız üzrə iki mərhələli autentifikasiya (2FA) sıfırlanıb, çünki autentifikasiya "
        f"tətbiqinə girişinizin olmadığı bildirilib.\n\n"
        f"Növbəti dəfə sistemə daxil olarkən sizə yeni QR kod təqdim ediləcək - onu "
        f"autentifikasiya tətbiqinizlə (Google Authenticator, Microsoft Authenticator və s.) "
        f"yenidən skan etməlisiniz.\n\n"
        f"Əgər bu sorğunu siz göndərməmisinizsə, dərhal sistem administratoru ilə əlaqə saxlayın."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )


class RequestTwoFAResetView(APIView):
    """
    Login səhifəsindəki 2FA addımında istifadəçi "Administrator ilə əlaqə" düyməsini
    basdıqda çağırılır (authenticator tətbiqi silinib / telefon dəyişilib itirilib halları
    üçün). Təhlükəsizlik baxımından yalnız username YOX, həm də şifrə təkrar yoxlanılır ki,
    sorğunu yalnız hesabın həqiqi sahibi göndərə bilsin - əks halda bu endpoint 2FA-nı
    bypass etmək üçün istismar oluna bilərdi.

    Uğurlu olduqda: two_fa_secret və two_fa_confirmed sıfırlanır (belə ki, növbəti girişdə
    TwoFASetupView yeni sirr/QR yaradır) və istifadəçiyə məlumatlandırıcı mail göndərilir.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = TwoFAResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        logger.info(f"RequestTwoFAResetView.post - 2FA sıfırlama sorğusu: {username}")

        user = _find_active_user(username)

        if user and user.check_password(password):
            try:
                self._reset_and_notify(user)
            except Exception as e:
                logger.error(f"RequestTwoFAResetView.post - {username} üçün xəta: {str(e)}")
        else:
            logger.info(f"RequestTwoFAResetView.post - {username} üçün yanlış istifadəçi adı/şifrə")

        # İstifadəçi/şifrə mövcudluğunu ifşa etməmək üçün həmişə eyni cavab qaytarılır
        return Response({"detail": TWO_FA_RESET_MESSAGE}, status=HTTP_200_OK)

    def _reset_and_notify(self, user):
        user.two_fa_secret = None
        user.two_fa_confirmed = False
        user.save(update_fields=["two_fa_secret", "two_fa_confirmed"])
        _send_2fa_reset_email(user)
        logger.info(f"RequestTwoFAResetView._reset_and_notify - {user.username} üçün 2FA sıfırlandı")


class GroupMeta:
    verbose_name = 'Vəzifə'
    verbose_name_plural = 'Vəzifələr'


class AzTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    SimpleJWT-nin default 'No active account found with the given credentials' mesajını
    (username/şifrə heç bir backend-də uyğun gəlmədikdə, authenticate() None qaytardıqda atılır)
    Azərbaycan dilinə çevirir.
    """
    default_error_messages = {
        "no_active_account": INVALID_CREDENTIALS,
    }


class LoginView(TokenObtainPairView):
    serializer_class = AzTokenObtainPairSerializer

    def _authenticate_and_authorize(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        if user.two_fa_confirmed:
            code = request.data.get('code')
            if not code:
                return Response(
                    {'detail': 'Autentifikasiya tətbiqindəki 6 rəqəmli kodu daxil edin.', 'two_fa_required': True},
                    status=HTTP_401_UNAUTHORIZED,
                )
            totp = pyotp.totp.TOTP(user.two_fa_secret)
            if not totp.verify(code, valid_window=1):
                logger.info(f'{user.username} - 2FA kodu yanlış daxil edildi')
                raise PermissionDenied('2FA kodu yanlışdır.')

        if user.two_fa_confirmed:
            should_be_approved = user_has_any_module_access(user)
            if user.is_approved != should_be_approved:
                user.is_approved = should_be_approved
                user.save(update_fields=["is_approved"])

            if not should_be_approved:
                logger.info(f'{user.username} - heç bir modula icazəsi olmadığı üçün giriş rədd edildi')
                raise PermissionDenied(NO_SYSTEM_ACCESS)

        data = dict(serializer.validated_data)

        logger.info(f'{user.username} uğurla daxil oldu')
        try:
            activity_log_services.log_login(user, request=request)
        except Exception as e:
            logger.error(f"LoginView - giriş loqu yazıla bilmədi ({user.username}): {str(e)}")
        return Response(data, status=status.HTTP_200_OK)

    @staticmethod
    def _extract_auth_failed_message(e: AuthenticationFailed) -> str:
        """AuthenticationFailed.detail həm sadə string, həm də (simplejwt-də) dict ola bilər - hər ikisini idarə edir."""
        detail = e.detail
        if isinstance(detail, dict):
            return str(detail.get("detail", INVALID_CREDENTIALS))
        return str(detail)

    @staticmethod
    def _is_ldap_lock(e: AuthenticationFailed) -> bool:
        """LDAP-da bloklanma/deaktivlik səbəbiylə atılan xətanı digər AuthenticationFailed-lərdən ayırır."""
        detail = e.detail
        code = getattr(detail, "code", None) if not isinstance(detail, dict) else detail.get("code")
        return code == "ldap_lock"

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        logger.info(f"LoginView.post - giriş cəhdi: {username}")

        try:
            attempt = LoginAttempt.objects.get(username__exact=username)
            if attempt.locked:
                logger.info(f"LoginView.post - {username} kilidlənib, giriş rədd edildi")
                return Response({'detail': USER_LOCKED}, status=HTTP_403_FORBIDDEN)
            else:
                try:
                    res = self._authenticate_and_authorize(request, *args, **kwargs)
                    attempt.fails = 0
                    attempt.save()
                    return res
                except PermissionDenied as e:
                    logger.info(f"LoginView.post - {username} üçün icazə rədd edildi: {str(e)}")
                    return Response({'detail': str(e)}, status=HTTP_403_FORBIDDEN)
                except AuthenticationFailed as e:
                    message = self._extract_auth_failed_message(e)
                    if self._is_ldap_lock(e):
                        # LDAP-da bloklanıbsa, bunu lokal sistemdə də əks etdiririk ki, hər giriş
                        # cəhdində yenidən LDAP-a sorğu göndərməyə ehtiyac qalmasın.
                        attempt.locked = True
                        attempt.save()
                        logger.warning(f"LoginView.post - {username} LDAP-da bloklandığı üçün sistemdə də kilidləndi")
                        return Response({'detail': message}, status=HTTP_403_FORBIDDEN)
                    attempt.fails += 1
                    attempt.save()
                    logger.info(f"LoginView.post - {username} üçün autentifikasiya xətası: {message}")
                    return Response({'detail': message}, status=HTTP_401_UNAUTHORIZED)
                except Exception as e:
                    logger.error(f"Login failed for {username}: {str(e)}")
                    attempt.fails += 1
                    attempt.save()
                    logger.info(f"LoginView.post - {username} üçün fails sayı: {attempt.fails}")
                    return Response({'detail': INVALID_CREDENTIALS}, status=HTTP_401_UNAUTHORIZED)

        except LoginAttempt.DoesNotExist:
            try:
                res = self._authenticate_and_authorize(request, *args, **kwargs)
                LoginAttempt.objects.create(username=username)
                return res
            except PermissionDenied as e:
                logger.info(f"LoginView.post - {username} üçün icazə rədd edildi: {str(e)}")
                return Response({'detail': str(e)}, status=HTTP_403_FORBIDDEN)
            except AuthenticationFailed as e:
                message = self._extract_auth_failed_message(e)
                if self._is_ldap_lock(e):
                    LoginAttempt.objects.create(username=username, locked=True)
                    logger.warning(f"LoginView.post - {username} LDAP-da bloklandığı üçün sistemdə də kilidləndi")
                    return Response({'detail': message}, status=HTTP_403_FORBIDDEN)
                LoginAttempt.objects.create(username=username, fails=1)
                logger.info(f"LoginView.post - {username} üçün autentifikasiya xətası: {message}")
                return Response({'detail': message}, status=HTTP_401_UNAUTHORIZED)
            except Exception as e:
                logger.error(f"Login failed for new user {username}: {str(e)}")
                LoginAttempt.objects.create(username=username, fails=1)
                return Response({'detail': INVALID_CREDENTIALS}, status=HTTP_401_UNAUTHORIZED)


class DepartmentDetailAPIView(RetrieveAPIView):
    queryset = Department.objects.prefetch_related("children", "children__manager", "manager", "curator")
    serializer_class = DepartmentListSerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        logger.info(f"DepartmentDetailAPIView.retrieve - id={kwargs.get('id')} sorğulandı")
        return super().retrieve(request, *args, **kwargs)


Group.add_to_class('Meta', GroupMeta)



from core.permissions import IsOrgAdmin, get_managed_organization, get_scoped_user
from .models import User, Organization
from .serializers import OrgUserSerializer, OrganizationSerializer

NO_ORGANIZATION = "İdarə etdiyiniz qurum təyin edilə bilmədi."
USER_OUTSIDE_ORG = "Bu istifadəçi sizin qurumunuza aid deyil."


class OrganizationListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"detail": "İcazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)

        organizations = Organization.objects.all().order_by("title")
        return Response(OrganizationSerializer(organizations, many=True).data, status=HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"detail": "İcazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)

        serializer = OrganizationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)
        organization = serializer.save()

        logger.info(f"{request.user.username} - yeni qurum yaratdı: {organization.title}")
        return Response(OrganizationSerializer(organization).data, status=HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    permission_classes = [IsOrgAdmin]
    authentication_classes = (JWTAuthentication,)

    def _get_organization(self, request, id):
        requester = request.user
        organization = Organization.objects.filter(id=id).first()
        if not organization:
            return None, Response({"detail": "Qurum tapılmadı."}, status=HTTP_404_NOT_FOUND)

        if requester.is_superuser:
            return organization, None

        if requester.is_org_admin:
            if requester.organization_id != organization.id:
                return None, Response({"detail": "Bu qurum sizə aid deyil."}, status=HTTP_403_FORBIDDEN)
            return organization, None

        return None, Response({"detail": "İcazəniz yoxdur."}, status=HTTP_403_FORBIDDEN)

    def get(self, request, id, *args, **kwargs):
        organization, error = self._get_organization(request, id)
        if error:
            return error
        return Response(OrganizationDetailSerializer(organization).data, status=HTTP_200_OK)

    def patch(self, request, id, *args, **kwargs):
        organization, error = self._get_organization(request, id)
        if error:
            return error

        data = {k: v for k, v in request.data.items()}
        if not request.user.is_superuser:
            # Qurum admini öz qurumunu deaktiv/aktiv edə bilməz - yalnız root.
            data.pop("is_active", None)

        serializer = OrganizationSerializer(organization, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()

        logger.info(f"{request.user.username} - {organization.title} qurumunun məlumatlarını yenilədi")
        return Response(OrganizationSerializer(organization).data, status=HTTP_200_OK)


class OrgUsersView(APIView):
    permission_classes = [IsOrgAdmin]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, *args, **kwargs):
        requester = request.user
        org_id = request.query_params.get("organization")

        if requester.is_superuser and not org_id:
            users = User.objects.all().select_related("organization").order_by("organization__title", "firstname")
            return Response(OrgUserSerializer(users, many=True).data, status=HTTP_200_OK)

        organization = get_managed_organization(request)
        if not organization:
            return Response({"detail": NO_ORGANIZATION}, status=HTTP_400_BAD_REQUEST)

        users = organization.users.all().order_by("firstname")
        return Response(OrgUserSerializer(users, many=True).data, status=HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        organization = get_managed_organization(request)
        if not organization:
            return Response({"detail": NO_ORGANIZATION}, status=HTTP_400_BAD_REQUEST)

        serializer = OrgUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        user = serializer.save(organization=organization)
        password = _generate_password()
        user.set_password(password)
        user.save()

        warning = None
        try:
            _send_new_password_email(user, password, is_new_account=True)
        except Exception as e:
            logger.error(f"OrgUsersView.post - {user.username} üçün mail göndərilmədi: {str(e)}")
            warning = "İstifadəçi yaradıldı, lakin giriş məlumatları mail ilə göndərilmədi (email ünvanını yoxlayın)."

        logger.info(f"{request.user.username} - {organization.title} qurumuna yeni user yaratdı: {user.username}")
        data = OrgUserSerializer(user).data
        if warning:
            data["_warning"] = warning
        return Response(data, status=HTTP_201_CREATED)


class OrgUserDetailView(APIView):
    permission_classes = [IsOrgAdmin]
    authentication_classes = (JWTAuthentication,)

    def get(self, request, id, *args, **kwargs):
        user, error = get_scoped_user(request, id)
        if error:
            return error
        return Response(OrgUserSerializer(user).data, status=HTTP_200_OK)

    def patch(self, request, id, *args, **kwargs):
        user, error = get_scoped_user(request, id)
        if error:
            return error

        # organization və password bu endpoint-dən dəyişdirilə bilməz
        # (qurumlar arası köçürmə qadağandır; şifrə üçün reset-password action-ı istifadə olunur)
        data = {k: v for k, v in request.data.items() if k not in ("organization", "password")}
        serializer = OrgUserSerializer(user, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()

        logger.info(f"{request.user.username} - {user.username} istifadəçisini yenilədi")
        return Response(OrgUserSerializer(user).data, status=HTTP_200_OK)


class ResetOrgUserPasswordView(APIView):
    permission_classes = [IsOrgAdmin]
    authentication_classes = (JWTAuthentication,)

    def post(self, request, id, *args, **kwargs):
        user, error = get_scoped_user(request, id)
        if error:
            return error

        if not user.email:
            return Response({"detail": NO_EMAIL}, status=HTTP_400_BAD_REQUEST)

        password = _generate_password()
        user.set_password(password)
        user.save()

        try:
            _send_new_password_email(user, password, is_new_account=False)
        except Exception as e:
            logger.error(f"ResetOrgUserPasswordView.post - {user.username} üçün mail göndərilmədi: {str(e)}")
            return Response(
                {"detail": "Şifrə yeniləndi, lakin mail göndərilə bilmədi. Email ünvanını yoxlayın."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        logger.info(f"{request.user.username} - {user.username} üçün yeni şifrə yaradıb mail ilə göndərdi")
        return Response({"detail": "Yeni şifrə istifadəçinin email ünvanına göndərildi."}, status=HTTP_200_OK)


class RoleListView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (JWTAuthentication,)

    def get(self, request):
        roles = Role.objects.all().order_by('order')
        return Response(RoleSerializer(roles, many=True).data, status=HTTP_200_OK)