from django.db import models

from django.utils import timezone
# Create your models here.
class TimestampsModel(models.Model):

    @classmethod
    def get_fields(cls, fields: tuple):
        return fields.__add__(('created_at', 'updated_at'))

    created_at = models.DateTimeField(null=True, blank=True, default=timezone.now, verbose_name="yaradılma tarixi")
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True, verbose_name="dəyişdirilmə tarixi")

    class Meta:
        abstract = True
