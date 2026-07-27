from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django_auth_ldap.backend import LDAPBackend
import logging
import ldap
from django.conf import settings
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from core.contstants import INACTIVE_ACCOUNT

logger = logging.getLogger('django_auth_ldap')

class CustomLDAPBackend(LDAPBackend):
    def get_or_build_user(self, username, ldap_user):
        user, built = super().get_or_build_user(username, ldap_user)
        if hasattr(user, 'access_id') and not isinstance(user.access_id, int) and user.access_id is not None:
            user.access_id = None
        return user, built

    def authenticate(self, request=None, username=None, password=None, **kwargs):
        # Call the parent class's authenticate method
        user = super().authenticate(request, username, password, **kwargs)

        # If user exists but is inactive, raise AuthenticationFailed
        if user and not user.is_active:
            raise AuthenticationFailed(INACTIVE_ACCOUNT)

        # If LDAP authentication succeeded but no Django user exists, create one
        if user is None:
            # Try to authenticate with LDAP directly
            try:
                # Initialize LDAP connection
                ldap_connection = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
                ldap_connection.protocol_version = ldap.VERSION3

                # Bind with service account
                ldap_connection.simple_bind_s(
                    settings.AUTH_LDAP_BIND_DN,
                    settings.AUTH_LDAP_BIND_PASSWORD
                )

                # Search for the user
                search_filter = f'(sAMAccountName={username})'
                # Get the base_dn from settings
                base_dn = settings.AUTH_LDAP_USER_SEARCH.base_dn

                result = ldap_connection.search_s(
                    base_dn,
                    ldap.SCOPE_SUBTREE,
                    search_filter,
                    ['mail', 'givenName', 'sn']
                )

                if result and len(result) > 0:
                    # User found in LDAP, now try to authenticate
                    user_dn = result[0][0]

                    try:
                        # Try to bind with user credentials
                        ldap_connection.simple_bind_s(user_dn, password)

                        # Authentication successful, create Django user
                        logger.debug(f"LDAP authentication succeeded for {username}, but no Django user exists. Creating one.")

                        # Create a new Django user
                        User = get_user_model()

                        # Extract user attributes from LDAP
                        user_attrs = self.get_user_attributes_from_ldap(result[0][1])

                        # Create the user with extracted attributes
                        user = User.objects.create_user(
                            username=username,
                            email=user_attrs.get('email', ''),
                            firstname=user_attrs.get('firstname', ''),
                            lastname=user_attrs.get('lastname', ''),
                            is_active=True
                        )

                        logger.debug(f"Created new Django user for LDAP user {username}")
                    except ldap.INVALID_CREDENTIALS:
                        # Invalid password
                        logger.debug(f"Invalid LDAP credentials for {username}")
                        pass
            except Exception as e:
                logger.error(f"LDAP error: {str(e)}")

        return user

    def get_user_attributes_from_ldap(self, ldap_attrs):
        """Extract user attributes from LDAP attributes"""
        attrs = {}

        # Map LDAP attributes to Django user model fields
        if 'mail' in ldap_attrs:
            attrs['email'] = ldap_attrs['mail'][0].decode('utf-8') if ldap_attrs['mail'] else ''

        if 'givenName' in ldap_attrs:
            attrs['firstname'] = ldap_attrs['givenName'][0].decode('utf-8') if ldap_attrs['givenName'] else ''

        if 'sn' in ldap_attrs:
            attrs['lastname'] = ldap_attrs['sn'][0].decode('utf-8') if ldap_attrs['sn'] else ''

        return attrs


class PhoneBackend(BaseBackend):
    def authenticate(self, request, phone=None, password=None, **kwargs):
        usermodel = get_user_model()
        try:
            user = usermodel.objects.get(phone_number=phone)
        except usermodel.DoesNotExist:
            return None

        # Check if user is inactive
        if not user.is_active:
            raise AuthenticationFailed(INACTIVE_ACCOUNT)

        if user.check_password(password):
            return user

    def get_user(self, user_id):
        usermodel = get_user_model()
        try:
            return usermodel.objects.get(pk=user_id)
        except usermodel.DoesNotExist:
            return None
