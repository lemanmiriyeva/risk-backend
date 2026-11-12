from django.db import migrations

DEFAULT_CATEGORIES = [
    # (code, title, color, default_priority, order)
    ("it-support", "İT dəstəyi", "#0A6CC2", "medium", 10),
    ("security", "İnformasiya təhlükəsizliyi", "#C42F3D", "high", 20),
    ("facilities", "Təsərrüfat / infrastruktur", "#B4690E", "medium", 30),
    ("hr", "Kadr məsələləri", "#6B4FB5", "low", 40),
    ("access", "Giriş / icazə sorğusu", "#0E8A9A", "medium", 50),
    ("other", "Digər", "#475569", "low", 90),
]


def forwards(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    TicketCategory = apps.get_model("tickets", "TicketCategory")
    # Müraciətlər sistemə daxil olan hər kəsə açıqdır; idarəetmə (kateqoriya və s.)
    # Module.admin_users-a əlavə olunan adminlərə verilir.
    Module.objects.update_or_create(
        code="tickets",
        defaults={
            "title": "Müraciətlər",
            "description": "Problem və sorğuları şöbələrə təyin edərək izləyin (ticket sistemi).",
            "url_endpoint": "muracietler",
            "is_public": True,
        },
    )
    for code, title, color, prio, order in DEFAULT_CATEGORIES:
        TicketCategory.objects.get_or_create(
            code=code,
            defaults={"title": title, "color": color, "default_priority": prio, "order": order},
        )


def backwards(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    Module.objects.filter(code="tickets").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_hamiya_acig_moduller"),
        ("tickets", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
