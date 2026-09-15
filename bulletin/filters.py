import django_filters

from .models import Circular, NewsPost


class CircularFilterSet(django_filters.FilterSet):
    category = django_filters.ChoiceFilter(choices=Circular.CATEGORY_CHOICES)

    class Meta:
        model = Circular
        fields = ["category", "is_active", "organization"]


class NewsPostFilterSet(django_filters.FilterSet):
    class Meta:
        model = NewsPost
        fields = ["is_active", "organization"]