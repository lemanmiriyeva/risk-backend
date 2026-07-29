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

        Module.objects.update_or_create(
            code="ikinci_modul",
            defaults={"title": "İkinci Modul", "url_endpoint": "ikinci-modul"}
        )

        self.stdout.write(self.style.SUCCESS("Modullar seed edildi."))