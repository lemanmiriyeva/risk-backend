from datetime import timedelta

from django.db import models
from django.utils import timezone

from core.models import TimestampsModel

# Prioritetə görə SLA (saat): (ilk cavab müddəti, həll müddəti)
SLA_HOURS = {
    'critical': (1, 4),
    'high': (4, 8),
    'medium': (8, 24),
    'low': (24, 72),
}


class TicketCategory(TimestampsModel):
    title = models.CharField(max_length=120, verbose_name="Kateqoriya adı")
    code = models.SlugField(max_length=64, unique=True, verbose_name="Kod")
    description = models.CharField(max_length=300, blank=True, default='', verbose_name="Təsvir")
    color = models.CharField(max_length=9, default='#0A6CC2', verbose_name="Rəng")
    default_department = models.ForeignKey(
        'authentication.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ticket_categories', verbose_name="Defolt şöbə",
        help_text="Müraciətçi şöbə seçməsə, bu kateqoriyadakı müraciətlər avtomatik bu şöbəyə yönləndirilir.",
    )
    default_priority = models.CharField(max_length=16, default='medium', verbose_name="Defolt prioritet")
    is_active = models.BooleanField(default=True, verbose_name="Aktivdir")
    order = models.PositiveIntegerField(default=10, verbose_name="Sıra")

    class Meta:
        ordering = ('order', 'title')
        verbose_name = "Müraciət kateqoriyası"
        verbose_name_plural = "Müraciət kateqoriyaları"

    def __str__(self):
        return self.title


class Ticket(TimestampsModel):
    STATUS_NEW = 'new'
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING = 'waiting'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Yeni'),
        (STATUS_OPEN, 'Qəbul edildi'),
        (STATUS_IN_PROGRESS, 'İcradadır'),
        (STATUS_WAITING, 'Cavab gözlənilir'),
        (STATUS_RESOLVED, 'Həll edildi'),
        (STATUS_CLOSED, 'Bağlandı'),
        (STATUS_CANCELED, 'Ləğv edildi'),
    ]
    ACTIVE_STATUSES = (STATUS_NEW, STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_WAITING)
    FINAL_STATUSES = (STATUS_CLOSED, STATUS_CANCELED)

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Aşağı'),
        (PRIORITY_MEDIUM, 'Orta'),
        (PRIORITY_HIGH, 'Yüksək'),
        (PRIORITY_CRITICAL, 'Kritik'),
    ]

    TYPE_INCIDENT = 'incident'
    TYPE_REQUEST = 'request'
    TYPE_QUESTION = 'question'
    TYPE_SUGGESTION = 'suggestion'
    TYPE_CHOICES = [
        (TYPE_INCIDENT, 'Problem / nasazlıq'),
        (TYPE_REQUEST, 'Xidmət sorğusu'),
        (TYPE_QUESTION, 'Sual'),
        (TYPE_SUGGESTION, 'Təklif'),
    ]

    title = models.CharField(max_length=200, verbose_name="Mövzu")
    description = models.TextField(verbose_name="Təsvir")
    ticket_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_INCIDENT, verbose_name="Növ")
    category = models.ForeignKey(
        TicketCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets', verbose_name="Kateqoriya",
    )
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, verbose_name="Prioritet")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Status", db_index=True)

    requester = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True,
        related_name='requested_tickets', verbose_name="Müraciətçi",
    )
    requester_department = models.ForeignKey(
        'authentication.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Müraciətçinin şöbəsi",
    )
    organization = models.ForeignKey(
        'authentication.Organization', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets', verbose_name="Qurum",
    )
    assignee = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tickets', verbose_name="Cavabdeh icraçı",
    )
    departments = models.ManyToManyField(
        'authentication.Department', through='TicketDepartment',
        related_name='tickets', verbose_name="Təyin olunan şöbələr",
    )
    watchers = models.ManyToManyField(
        'authentication.User', related_name='watched_tickets', blank=True, verbose_name="İzləyənlər",
    )
    tags = models.JSONField(default=list, blank=True, verbose_name="Etiketlər")

    # SLA
    first_response_due_at = models.DateTimeField(null=True, blank=True, verbose_name="İlk cavab müddəti")
    due_at = models.DateTimeField(null=True, blank=True, verbose_name="Həll müddəti (SLA)")
    first_response_at = models.DateTimeField(null=True, blank=True, verbose_name="İlk cavab tarixi")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Həll tarixi")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Bağlanma tarixi")
    escalated_at = models.DateTimeField(null=True, blank=True, verbose_name="Eskalasiya tarixi")
    reopen_count = models.PositiveSmallIntegerField(default=0, verbose_name="Yenidən açılma sayı")
    last_activity_at = models.DateTimeField(default=timezone.now, verbose_name="Son fəaliyyət")

    # Məmnuniyyət
    rating = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Qiymət (1-5)")
    rating_comment = models.CharField(max_length=500, blank=True, default='', verbose_name="Qiymət rəyi")

    class Meta:
        ordering = ('-created_at',)
        verbose_name = "Müraciət"
        verbose_name_plural = "Müraciətlər"
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['due_at']),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def number(self):
        return f"TKT-{self.pk:05d}" if self.pk else "TKT-?????"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_overdue(self):
        return bool(self.due_at and self.is_active and self.due_at < timezone.now())

    @property
    def first_response_overdue(self):
        return bool(
            self.first_response_due_at and not self.first_response_at
            and self.is_active and self.first_response_due_at < timezone.now()
        )

    def apply_sla(self, start=None):
        """Prioritetə uyğun SLA müddətlərini hesablayır (start - yaradılma anı)."""
        start = start or self.created_at or timezone.now()
        first, resolve = SLA_HOURS.get(self.priority, SLA_HOURS['medium'])
        self.first_response_due_at = start + timedelta(hours=first)
        self.due_at = start + timedelta(hours=resolve)


class TicketDepartment(TimestampsModel):
    """Müraciətin bir şöbəyə təyinatı. Bir müraciət bir neçə şöbəyə təyin oluna bilər,
    hər şöbənin öz icraçısı və öz icra statusu var."""

    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Gözləyir'),
        (STATUS_IN_PROGRESS, 'İcradadır'),
        (STATUS_DONE, 'Tamamlandı'),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='department_links')
    department = models.ForeignKey(
        'authentication.Department', on_delete=models.CASCADE, related_name='ticket_links', verbose_name="Şöbə",
    )
    assignee = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ticket_department_assignments', verbose_name="Şöbə daxili icraçı",
    )
    is_primary = models.BooleanField(default=False, verbose_name="Əsas şöbə")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Şöbənin statusu")
    note = models.CharField(max_length=500, blank=True, default='', verbose_name="Qeyd")
    assigned_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Təyin edən",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('ticket', 'department')
        ordering = ('-is_primary', 'id')
        verbose_name = "Müraciət - şöbə təyinatı"
        verbose_name_plural = "Müraciət - şöbə təyinatları"

    def __str__(self):
        return f"{self.ticket.number} -> {self.department}"


class TicketComment(TimestampsModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, related_name='ticket_comments',
    )
    body = models.TextField(verbose_name="Mətn")
    is_internal = models.BooleanField(
        default=False, verbose_name="Daxili qeyd",
        help_text="Daxili qeydlər müraciətçiyə göstərilmir - yalnız şöbə əməkdaşları görür.",
    )

    class Meta:
        ordering = ('created_at', 'id')
        verbose_name = "Müraciət şərhi"
        verbose_name_plural = "Müraciət şərhləri"

    def __str__(self):
        return f"{self.ticket.number} / {self.author}"


def ticket_upload_path(instance, filename):
    now = timezone.now()
    return f"tickets/{now:%Y/%m}/{instance.ticket_id}/{filename}"


class TicketAttachment(TimestampsModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    comment = models.ForeignKey(
        TicketComment, on_delete=models.CASCADE, null=True, blank=True, related_name='attachments',
    )
    file = models.FileField(upload_to=ticket_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True, default='')
    uploaded_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, related_name='+',
    )
    is_internal = models.BooleanField(default=False)

    class Meta:
        ordering = ('created_at', 'id')
        verbose_name = "Müraciət faylı"
        verbose_name_plural = "Müraciət faylları"

    def __str__(self):
        return self.original_name


class TicketActivity(models.Model):
    """Müraciətin dəyişiklik tarixçəsi (audit timeline)."""

    A_CREATED = 'created'
    A_STATUS = 'status_changed'
    A_PRIORITY = 'priority_changed'
    A_CATEGORY = 'category_changed'
    A_UPDATED = 'updated'
    A_ASSIGNEE = 'assignee_changed'
    A_DEPT_ADDED = 'department_added'
    A_DEPT_REMOVED = 'department_removed'
    A_DEPT_STATUS = 'department_status'
    A_COMMENT = 'commented'
    A_ATTACHMENT = 'attachment_added'
    A_REOPENED = 'reopened'
    A_RATED = 'rated'
    A_ESCALATED = 'escalated'
    A_WATCHER = 'watcher_changed'

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    action = models.CharField(max_length=32)
    data = models.JSONField(default=dict, blank=True)
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('created_at', 'id')
        verbose_name = "Müraciət tarixçəsi"
        verbose_name_plural = "Müraciət tarixçəsi"
