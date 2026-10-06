from django.db import migrations

# Elanlar lövhəsi və Təlimlər sistemə daxil olan hər kəsə açıqdır.
# Təlim statistikası isə "məhdud" alt moduldur - yalnız icazə verilmiş şəxslər görür.
PUBLIC_MODULES = ("bulletin", "trainings")
RESTRICTED_SUB_MODULES = ("training_statistics",)


def forwards(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    SubModule = apps.get_model("core", "SubModule")
    Module.objects.filter(code__in=PUBLIC_MODULES).update(is_public=True)
    SubModule.objects.filter(code__in=RESTRICTED_SUB_MODULES).update(is_restricted=True)


def backwards(apps, schema_editor):
    SubModule = apps.get_model("core", "SubModule")
    SubModule.objects.filter(code__in=RESTRICTED_SUB_MODULES).update(is_restricted=False)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_submodule_is_restricted"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
