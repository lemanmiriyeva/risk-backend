from django.core.management.base import BaseCommand

from tickets import services


class Command(BaseCommand):
    help = (
        "Ticket sistemi üçün dövri işlər: SLA vaxtı keçənləri eskalasiya edir və "
        "həll edilib cavab verilməyənləri avtomatik bağlayır. Cron/Celery beat ilə saatda bir dəfə işlədin."
    )

    def handle(self, *args, **options):
        escalated = services.escalate_overdue()
        closed = services.auto_close_resolved()
        self.stdout.write(self.style.SUCCESS(f"Eskalasiya: {escalated}, avtomatik bağlanan: {closed}"))
