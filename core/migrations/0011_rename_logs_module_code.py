from django.db import migrations

# "Loqlar" modulu bəzi bazalarda əl ilə `code="logs"` kimi yaradılıb, halbuki
# ActivityLogViewSet `module_code = "activity_logs"` gözləyir. Kod uyğun
# gəlmədikdə ModuleAccessPermission modulu tapmır və hamıya (superuser daxil)
# 403 qaytarır. Bu miqrasiya köhnə kodu düzgün koda çevirir.
OLD_CODE = "logs"
NEW_CODE = "activity_logs"


def forwards(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    if Module.objects.filter(code=NEW_CODE).exists():
        return
    Module.objects.filter(code=OLD_CODE).update(code=NEW_CODE)


def backwards(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    if Module.objects.filter(code=OLD_CODE).exists():
        return
    Module.objects.filter(code=NEW_CODE).update(code=OLD_CODE)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_submodule_admin_users"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
