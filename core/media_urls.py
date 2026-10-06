from django.conf import settings


def media_url(request, field_file):
    """
    Fayl/şəkil sahəsinin brauzerin aça biləcəyi tam ünvanı.

    Frontend backend-ə daxili ünvanla (məs. 127.0.0.1:8000) müraciət etdiyi üçün
    request.build_absolute_uri() brauzerin çata bilmədiyi ünvan qaytarır
    (ERR_CONNECTION_REFUSED). Ona görə .env-dəki BACKEND_BASE_URL (məs.
    http://10.3.15.165:8000) üstünlük təşkil edir; təyin edilməyibsə, köhnə davranış.
    """
    if not field_file:
        return None
    url = field_file.url
    base = getattr(settings, "BACKEND_BASE_URL", "")
    if base:
        return f"{base}{url}"
    return request.build_absolute_uri(url) if request else url
