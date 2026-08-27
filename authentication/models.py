from django.db import models
from django.contrib.auth.models import UserManager, AbstractBaseUser, PermissionsMixin, Group, GroupManager, Permission
from django.utils import timezone
from core.models import TimestampsModel
from django.core.validators import FileExtensionValidator
from django.contrib.auth.hashers import make_password


class CustomUserManager(UserManager):
    def _create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("İstifadəçi adı boş ola bilməz")

        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self.db)
        return user

    def create_user(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(username, email, password, **extra_fields)


class SpecialPermission(models.Model):
    name = models.CharField(max_length=255)
    codename = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Xüsusi icazə"
        verbose_name_plural = "Xüsusi icazələr"

    def __str__(self):
        return f'{self.name} | {self.codename}'


class Organization(TimestampsModel):
    title = models.CharField(max_length=255, verbose_name="Qurumun adı")
    short_name = models.CharField(max_length=64, blank=True, default="", verbose_name="Qısaltma")
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")
    authorized_person_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Səlahiyyətli şəxsin adı"
    )
    authorized_person_position = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Səlahiyyətli şəxsin vəzifəsi"
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Qurum"
        verbose_name_plural = "Qurumlar"
        ordering = ["title"]

    @property
    def employee_count(self):
        return self.users.count()


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(unique=True, max_length=13, verbose_name='Telefon nömrəsi', null=True, blank=True)
    fin_kod = models.CharField(
        max_length=7, null=True, blank=True, verbose_name="FIN kod"
    )
    image = models.ImageField(
        upload_to='user_images/',
        null=True,
        blank=True,
        verbose_name='Şəkil',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    username = models.CharField(max_length=128, unique=True, verbose_name='İstifadəçi adı')
    email = models.EmailField(max_length=128, unique=True, verbose_name='İstifadəçi emaili')
    firstname = models.CharField(max_length=128, blank=True, default='', verbose_name='Adı')
    lastname = models.CharField(max_length=128, blank=True, default='', verbose_name='Soyadı')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Doğum tarixi')
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=True)
    role = models.ForeignKey("Role", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vəzifə")
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Departament/Şöbə")
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="Qurum"
    )
    is_org_admin = models.BooleanField(
        default=False, verbose_name="Qurum admini",
        help_text=(
            "Bu user öz qurumunun (organization sahəsində göstərilən) daxilində "
            "istifadəçiləri idarə edə, və qurumuna aid modul/alt-modullara hansı "
            "işçilərin çıxışı olacağını təyin edə bilər. Başqa qurumun datasına "
            "və ya user-lərinə çıxışı yoxdur."
        )
    )
    is_apparatus_head = models.BooleanField(
        default=False,
        verbose_name="Aparat rəhbəri",
        help_text=(
            "Bu user öz qurumunun (organization) BÜTÜN əməkdaşlarının icazə sorğularını "
            "görə və HƏR KƏSİN (şöbə müdirləri daxil) sorğusunu təsdiq/rədd edə bilər. "
            "Özü icazə sorğusu yarada bilməz. Konkret vəzifə adından asılı deyil "
            "(Direktor, Aparat rəhbəri və s. ola bilər) - buna görə ayrıca sahədir."
        ),
    )
    special_permissions = models.ManyToManyField(
        SpecialPermission,
        verbose_name="Xüsusi icazələr",
        blank=True,
    )
    join_date = models.DateTimeField(default=timezone.now, verbose_name="Qeydiyyat tarixi")
    update_date = models.DateTimeField(default=timezone.now, verbose_name="Son düzəliş tarixi")
    GENDER_CHOICES = [
        ('male', 'Kişi'),
        ('female', 'Qadın'),
    ]

    two_fa_secret = models.CharField(max_length=32, null=True, blank=True, verbose_name="2FA sirri")
    two_fa_confirmed = models.BooleanField(default=False, verbose_name="2FA təsdiqlənib")
    is_approved = models.BooleanField(default=False, verbose_name="Admin tərəfindən təsdiqlənib")

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        verbose_name="Cinsiyyət"
    )
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ["email", "firstname", "lastname"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.id:
            self.join_date = timezone.now()
        self.update_date = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ('id',)
        verbose_name = 'Istifadəçi'
        verbose_name_plural = 'Istifadəçilər'
        permissions = [
            ('view_permissions_section', 'Can view permissions section in UserAdmin'),
        ]

    @property
    def name(self):
        return "{} {}".format(self.firstname, self.lastname)

    def get_short_name(self):
        return "{}. {} ({})".format(self.firstname[0] if self.firstname else "", self.lastname if self.lastname else "",
                                    self.department.shortname if self.department else None)


class Department(TimestampsModel):
    title = models.CharField(max_length=255, verbose_name="Departamentin adı")
    shortname = models.CharField(max_length=255, default="", verbose_name="Adın qısaltması")
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.CASCADE, null=True, blank=True,
        related_name="departments", verbose_name="Qurum",
        help_text=(
            "Bu departamentin aid olduğu qurum. Alt (child) departamentlər üçün bu sahə "
            "avtomatik olaraq valideyn departamentin qurumu ilə eyniləşdirilir."
        ),
    )
    parent = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='children',)
    manager = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='managed_departments')

    order = models.PositiveIntegerField(default=2, verbose_name="Sıra")
    unique_code = models.CharField(max_length=64, verbose_name="Departamentin unikal kodu", null=True, blank=True,)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']
        verbose_name = "Departament"
        verbose_name_plural = "Departamentlər"

    def save(self, *args, **kwargs):
        # Child departament həmişə valideyninin qurumuna aid olur (data uyğunsuzluğunun qarşısını almaq üçün).
        if self.parent_id and self.parent.organization_id:
            self.organization_id = self.parent.organization_id
        super().save(*args, **kwargs)


class Role(TimestampsModel):
    title = models.CharField(max_length=255, blank=True, verbose_name="Vəzifə")
    department = models.ForeignKey(
        'Department', on_delete=models.CASCADE, null=True, blank=True, related_name='roles',
        verbose_name="Departament",
        help_text="Bu vəzifənin aid olduğu departament (və dolayısı ilə qurum).",
    )
    is_manager_role = models.BooleanField(
        default=False,
        verbose_name="Şöbə rəhbəri səlahiyyəti",
        help_text=(
            "Bu vəzifədə olan istifadəçilər öz departamentlərindəki əməkdaşların "
            "icazə sorğularını görə və təsdiq/rədd edə bilər."
        ),
    )
    parent = models.ForeignKey('Role', on_delete=models.SET_NULL, null=True, blank=True, related_name='children',)
    order = models.PositiveIntegerField(default=99, verbose_name="Sıralama")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Vəzifə'
        verbose_name_plural = 'Vəzifələr'

    @property
    def organization_id(self):
        return self.department.organization_id if self.department_id else None


class PasswordReset(models.Model):
    email = models.EmailField(verbose_name="Elektron poçt")
    token = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Şifrə yeniləməsi'
        verbose_name_plural = 'Şifrə yeniləmələri'

    def __str__(self):
        return self.email


class LoginAttempt(models.Model):
    username = models.CharField(max_length=255)
    ip = models.CharField(null=True, blank=True, max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    fails = models.IntegerField(default=0)
    locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Giriş cəhdi"
        verbose_name_plural = "Giriş cəhdləri"

    def __str__(self):
        return self.username