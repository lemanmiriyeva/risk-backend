import random
from django.db import models
from authentication.models import User


class InventoryOwnerPerson(models.Model):
    full_name = models.CharField(max_length=255, unique=True, verbose_name="Ad Soyad")

    class Meta:
        ordering = ('full_name',)
        verbose_name = "İnventar sahibi (şəxs)"
        verbose_name_plural = "İnventar sahibləri (şəxslər)"

    def __str__(self):
        return self.full_name


class InventoryOwnerDepartment(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Departament adı")

    class Meta:
        ordering = ('name',)
        verbose_name = "İnventar sahibi (departament)"
        verbose_name_plural = "İnventar sahibləri (departamentlər)"

    def __str__(self):
        return self.name


class Inventory(models.Model):
    OWNER_PERSON = 'person'
    OWNER_DEPARTMENT = 'department'
    OWNER_APPARATUS = 'aparat'
    OWNER_TYPE_CHOICES = [
        (OWNER_PERSON, 'Şəxs'),
        (OWNER_DEPARTMENT, 'Departament'),
        (OWNER_APPARATUS, 'Aparat (hamı üçün)'),
    ]

    product_name = models.CharField(max_length=255, verbose_name="Məhsulun adı")
    inventory_number = models.CharField(
        max_length=20, unique=True, editable=False, verbose_name="İnventar nömrəsi"
    )

    owner_type = models.CharField(max_length=20, choices=OWNER_TYPE_CHOICES, verbose_name="Sahib növü")
    owner_person = models.ForeignKey(
        InventoryOwnerPerson, on_delete=models.PROTECT, null=True, blank=True,
        related_name='inventories', verbose_name="Sahib (şəxs)"
    )
    owner_department = models.ForeignKey(
        InventoryOwnerDepartment, on_delete=models.PROTECT, null=True, blank=True,
        related_name='inventories', verbose_name="Sahib (departament)"
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_inventories', verbose_name="Yaradan"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_inventories', verbose_name="Son dəyişikliyi edən"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaradılma tarixi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son dəyişiklik tarixi")

    class Meta:
        ordering = ('-created_at',)
        verbose_name = "İnventar"
        verbose_name_plural = "İnventarlar"

    def __str__(self):
        return f"{self.inventory_number} — {self.product_name}"

    @property
    def owner_display(self):
        if self.owner_type == self.OWNER_PERSON and self.owner_person:
            return self.owner_person.full_name
        if self.owner_type == self.OWNER_DEPARTMENT and self.owner_department:
            return self.owner_department.name
        if self.owner_type == self.OWNER_APPARATUS:
            return "Aparat (hamı üçün)"
        return "—"

    @staticmethod
    def generate_inventory_number():
        while True:
            candidate = f"IS{random.randint(0, 9999):04d}"
            if not Inventory.objects.filter(inventory_number=candidate).exists():
                return candidate

    def save(self, *args, **kwargs):
        if not self.inventory_number:
            self.inventory_number = self.generate_inventory_number()
        super().save(*args, **kwargs)