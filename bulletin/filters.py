import django_filters

from .models import Circular, NewsPost


class CircularFilterSet(django_filters.FilterSet):
    # Qəsdən ChoiceFilter yox - `category` artıq FK-dır və dinamikdir, sərt
    # `choices` siyahısı yoxdur. Slug (`?category=ferman`) ilə süzgəcləmək
    # üçün sadə CharFilter kifayətdir; bu həm də əvvəlki
    # "'super' object has no attribute '_set_choices'" xətasının mənbəyini
    # (django-filter-in ChoiceField-i) tamamilə aradan qaldırır.
    category = django_filters.CharFilter(field_name="category__key")

    class Meta:
        model = Circular
        fields = ["category", "is_active", "organization"]


class NewsPostFilterSet(django_filters.FilterSet):
    class Meta:
        model = NewsPost
        fields = ["is_active", "organization"]