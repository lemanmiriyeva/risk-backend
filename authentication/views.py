import logging
import pyotp
from django.contrib.auth.models import Group
from rest_framework.generics import RetrieveAPIView
from rest_framework.status import HTTP_403_FORBIDDEN, \
    HTTP_401_UNAUTHORIZED
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from python_ipware import IpWare
from django.shortcuts import get_object_or_404
from core.contstants import INVALID_CREDENTIALS, USER_LOCKED
from .models import User, Department, LoginAttempt
from .serializers import UserSerializer, DepartmentListSerializer
from risk.permissions import user_has_any_risk_access

ipw = IpWare()

MAX_ATTEMPTS = 3
LOCKOUT_TIME = 300

NO_SYSTEM_ACCESS = "Bu sistemə giriş icazəniz yoxdur. Zəhmət olmasa sistem administratoru ilə əlaqə saxlayın."

logger = logging.getLogger('colored')

from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class UsersView(APIView):
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (JWTAuthentication,)

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
    # permission_classes = [IsAuthenticated]

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
        logger.info(f"UserView.get - {user.username} öz məlumatını sorğuladı")
        serializer = UserSerializer(user)
        return Response(serializer.data)


class UserDetailView(APIView):
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (JWTAuthentication,)

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
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            logger.error(f"LogoutView - token xətası ({request.user.username}): {str(e)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"LogoutView - gözlənilməz xəta ({request.user.username}): {str(e)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)


class GroupMeta:
    verbose_name = 'Vəzifə'
    verbose_name_plural = 'Vəzifələr'


class LoginView(TokenObtainPairView):

    def _authenticate_and_authorize(self, request, *args, **kwargs):
        # 1. Serializer-i işlədirik
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user

        # 2. 2FA yoxlaması - quraşdırma tamamlanıbsa, HƏR giriş cəhdində kod tələb olunur
        if user.two_fa_confirmed:
            code = request.data.get('code')
            if not code:
                # Şifrə düzgündür, amma hələ 2FA kodu göndərilməyib -
                # frontend bunu görüb kod input sahəsini göstərəcək
                return Response(
                    {'detail': 'Autentifikasiya tətbiqindəki 6 rəqəmli kodu daxil edin.', 'two_fa_required': True},
                    status=HTTP_401_UNAUTHORIZED,
                )
            totp = pyotp.totp.TOTP(user.two_fa_secret)
            if not totp.verify(code, valid_window=1):
                logger.info(f'{user.username} - 2FA kodu yanlış daxil edildi')
                raise PermissionDenied('2FA kodu yanlışdır.')

        # 3. İcazə yoxlaması
        # Yalnız 2FA-nı quraşdırmış VƏ admin tərəfindən təsdiqlənmiş istifadəçilər üçün
        # modul girişi tələb olunur. Əks halda hələ onboarding mərhələsində olan
        # (2FA quraşdırılmamış / təsdiq gözləyən) istifadəçilər sistemə heç girə bilməzdi.
        if user.two_fa_confirmed and user.is_approved and not user_has_any_risk_access(user):
            logger.info(f'{user.username} - heç bir modula icazəsi olmadığı üçün giriş rədd edildi')
            raise PermissionDenied(NO_SYSTEM_ACCESS)

        # 4. MÜHÜM DƏYİŞİKLİK: validated_data-nı sadə dictionary-ə çeviririk
        data = dict(serializer.validated_data)

        logger.info(f'{user.username} uğurla daxil oldu')
        return Response(data, status=status.HTTP_200_OK)

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