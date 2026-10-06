from django.core.management.base import BaseCommand
from core.models import Module, SubModule

class Command(BaseCommand):
    help = "Module/SubModule-ları code ilə yaradır (idempotent)"

    def handle(self, *args, **kwargs):
        risk_module, _ = Module.objects.update_or_create(
            code="risk",
            defaults={"title": "Risk Reyestr Sistemi", "url_endpoint": "risk"}  
        )
        SubModule.objects.update_or_create(
            module=risk_module, code="risk_register",
            defaults={"title": "Risk Reyestri", "url_endpoint": "list"}
        )
        SubModule.objects.update_or_create(
            module=risk_module, code="risk_view_table",
            defaults={"title": "Risk Cədvəli", "url_endpoint": "table"}
        )
        SubModule.objects.update_or_create(
            module=risk_module, code="risk_log",
            defaults={"title": "Risk Logları", "url_endpoint": "logs"}
        )

        # Loqlar (audit jurnalı). Kod ActivityLogViewSet.module_code ilə eyni olmalıdır.
        # Mövcud modulun adı/linki dəyişdirilməsin deyə yalnız yoxdursa yaradılır.
        Module.objects.get_or_create(
            code="activity_logs",
            defaults={"title": "Hərəkət tarixçəsi", "url_endpoint": "loqlar"}
        )

        Module.objects.update_or_create(
            code="bulletin",
            defaults={
                "title": "Elanlar lövhəsi",
                "description": "Sərəncamlar, fərmanlar, daxili qaydalar, xəbərlər və doğum günləri.",
                "url_endpoint": "elanlar",
                "is_public": True,  # sistemə daxil olan hər kəsə açıq
            }
        )

        # Təlimlər: iki alt modul - hər birinin girişi və admini AYRICA təyin olunur
        # (SubModule.permitted_users / SubModule.admin_users).
        trainings_module, _ = Module.objects.update_or_create(
            code="trainings",
            defaults={
                "title": "Təlimlər",
                "description": "Təlim videoları, quizlər və təlim statistikası.",
                "url_endpoint": "telimler",
                "is_public": True,  # sistemə daxil olan hər kəsə açıq
            }
        )
        SubModule.objects.update_or_create(
            module=trainings_module, code="training_materials",
            defaults={
                "title": "Təlim materialları",
                "description": "Təlim videolarına baxın, quizi tamamlayın və rəy bildirin.",
                "url_endpoint": "materiallar",
            }
        )
        SubModule.objects.update_or_create(
            module=trainings_module, code="training_statistics",
            defaults={
                "title": "Təlim statistikası",
                "description": "Kim hansı təlimə nə vaxt baxıb, quiz nəticələri və rəylər.",
                "url_endpoint": "statistika",
                # Təlimlər hamıya açıq olsa da, statistika yalnız icazəlilərə görünür
                "is_restricted": True,
            }
        )

        self.stdout.write(self.style.SUCCESS("Modullar seed edildi."))