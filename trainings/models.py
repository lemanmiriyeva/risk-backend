from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from authentication.models import User

VIDEO_EXTENSIONS = ["mp4", "webm", "ogg", "ogv", "m4v", "mov"]


class Training(models.Model):
    """
    Təlim materialı (video). "Təlim materialları" alt modulunun admini yükləyir.

    `organization` boş (null) olarsa təlim BÜTÜN qurumlara aiddir, əks halda
    yalnız həmin qurumun işçilərinə göstərilir (bulletin app-ı ilə eyni qayda).
    """

    title = models.CharField(max_length=255, verbose_name="Başlıq")
    description = models.TextField(blank=True, default="", verbose_name="Təsvir")
    video = models.FileField(
        upload_to="trainings/videos/%Y/%m/",
        validators=[FileExtensionValidator(allowed_extensions=VIDEO_EXTENSIONS)],
        verbose_name="Video",
    )
    thumbnail = models.ImageField(
        upload_to="trainings/thumbnails/%Y/%m/", null=True, blank=True, verbose_name="Örtük şəkli",
    )
    duration_seconds = models.PositiveIntegerField(
        default=0, verbose_name="Videonun müddəti (saniyə)",
        help_text="Yükləmə zamanı brauzer avtomatik təyin edir. Baxışın sona çatdığını yoxlamaq üçün istifadə olunur.",
    )
    pass_percent = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Keçid balı (%)",
        help_text="Quiz nəticəsi bu faizə bərabər və ya yuxarı olduqda 'keçdi' sayılır.",
    )
    organization = models.ForeignKey(
        "authentication.Organization", on_delete=models.CASCADE, related_name="trainings",
        null=True, blank=True, verbose_name="Qurum",
        help_text="Boş buraxılsa, təlim BÜTÜN qurumların işçilərinə görünür.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_trainings", verbose_name="Yükləyən",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Təlim materialı"
        verbose_name_plural = "Təlim materialları"

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    """Təlimin (videonun) sonunda açılan quiz sualı. Tək düzgün cavablıdır."""

    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name="quiz_questions", verbose_name="Təlim",
    )
    text = models.TextField(verbose_name="Sual")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıra")

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Quiz sualı"
        verbose_name_plural = "Quiz sualları"

    def __str__(self):
        return self.text[:80]


class QuizOption(models.Model):
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="options", verbose_name="Sual",
    )
    text = models.CharField(max_length=500, verbose_name="Cavab variantı")
    is_correct = models.BooleanField(default=False, verbose_name="Düzgün cavabdır")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıra")

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Cavab variantı"
        verbose_name_plural = "Cavab variantları"

    def __str__(self):
        return self.text[:80]


class TrainingProgress(models.Model):
    """
    İstifadəçinin bir təlim videosuna baxış vəziyyəti.

    Video YALNIZ sonuna qədər baxıldıqda `completed` olur. Səhifədən yarımçıq
    çıxan istifadəçi baxmamış sayılır: növbəti dəfə video açılanda (`start`)
    irəliləyiş sıfırlanır və video yenidən əvvəldən izlənməlidir.

    `max_position` server tərəfində real vaxtla məhdudlaşdırılır (bax:
    views.TrainingViewSet.progress) - videonu irəli çəkib və ya API-ni birbaşa
    çağırıb "baxılmış" etmək mümkün deyil.
    """

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, "Yarımçıq"),
        (STATUS_COMPLETED, "Tam baxılıb"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="training_progress", verbose_name="İstifadəçi",
    )
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name="progress_records", verbose_name="Təlim",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS, verbose_name="Status",
    )
    max_position = models.FloatField(default=0, verbose_name="Cari sessiyada baxılan ən uzaq an (san.)")
    session_started_at = models.DateTimeField(null=True, blank=True, verbose_name="Cari sessiyanın başlanğıcı")
    last_heartbeat_at = models.DateTimeField(null=True, blank=True, verbose_name="Son aktivlik")
    attempts_count = models.PositiveIntegerField(default=0, verbose_name="Baxışa başlama sayı")
    first_started_at = models.DateTimeField(default=timezone.now, verbose_name="İlk baxış tarixi")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tam baxılma tarixi")

    class Meta:
        ordering = ("-last_heartbeat_at",)
        verbose_name = "Baxış qeydi"
        verbose_name_plural = "Baxış qeydləri"
        constraints = [
            models.UniqueConstraint(fields=["user", "training"], name="uniq_training_progress_user"),
        ]

    def __str__(self):
        return f"{self.user} — {self.training} ({self.get_status_display()})"

    @property
    def is_completed(self):
        return self.status == self.STATUS_COMPLETED


class QuizAttempt(models.Model):
    """
    İstifadəçinin quiz-i TƏSDİQLƏDİYİ (göndərdiyi) cəhd. Yalnız göndərildikdən
    sonra yaradılır - yarımçıq doldurulan quiz heç yerdə saxlanılmır.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="quiz_attempts", verbose_name="İstifadəçi",
    )
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name="quiz_attempts", verbose_name="Təlim",
    )
    correct_count = models.PositiveIntegerField(default=0, verbose_name="Düzgün cavab sayı")
    total_count = models.PositiveIntegerField(default=0, verbose_name="Sual sayı")
    percent = models.PositiveSmallIntegerField(default=0, verbose_name="Nəticə (%)")
    passed = models.BooleanField(default=False, verbose_name="Keçdi")
    submitted_at = models.DateTimeField(default=timezone.now, verbose_name="Təsdiqlənmə tarixi")

    class Meta:
        ordering = ("-submitted_at",)
        verbose_name = "Quiz nəticəsi"
        verbose_name_plural = "Quiz nəticələri"

    def __str__(self):
        return f"{self.user} — {self.training}: {self.percent}%"


class QuizAnswer(models.Model):
    """
    Cəhd daxilində bir sualın cavabı. Sual/cavab mətnləri SNAPSHOT kimi
    saxlanılır ki, admin quiz-i sonradan redaktə etsə də köhnə nəticələr
    olduğu kimi qalsın.
    """

    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(QuizQuestion, on_delete=models.SET_NULL, null=True, blank=True)
    selected_option = models.ForeignKey(QuizOption, on_delete=models.SET_NULL, null=True, blank=True)
    question_text = models.TextField(verbose_name="Sual")
    selected_text = models.CharField(max_length=500, blank=True, default="", verbose_name="Seçilmiş cavab")
    correct_text = models.CharField(max_length=500, blank=True, default="", verbose_name="Düzgün cavab")
    is_correct = models.BooleanField(default=False, verbose_name="Düzgündür")

    class Meta:
        ordering = ("id",)
        verbose_name = "Quiz cavabı"
        verbose_name_plural = "Quiz cavabları"


class TrainingFeedback(models.Model):
    """İstifadəçinin təlim haqqında rəyi (1-5 qiymət + şərh). Hər istifadəçidən bir rəy."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="training_feedback", verbose_name="İstifadəçi",
    )
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name="feedback", verbose_name="Təlim",
    )
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Qiymət (1-5)",
    )
    comment = models.TextField(blank=True, default="", verbose_name="Rəy")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "Təlim rəyi"
        verbose_name_plural = "Təlim rəyləri"
        constraints = [
            models.UniqueConstraint(fields=["user", "training"], name="uniq_training_feedback_user"),
        ]

    def __str__(self):
        return f"{self.user} — {self.training}"
