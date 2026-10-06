"""
Müdafiə Sənayesi Nazirliyi Aparatının struktur bölmələri və əməkdaşları
("Mail və telefon siyahısı" əsasında). seed_demo_data əmri tərəfindən istifadə olunur.

DİQQƏT: əməkdaşların şəxsi məlumatları (ad, e-poçt, daxili nömrə) var - repozitoriya
yalnız daxili istifadə üçün olmalıdır.

E-poçtu olmayan əməkdaşlar (Nazir, Vəfa Məmmədova, Mayis Mirzəyev, Nigar Rəsulzadə)
istifadəçi kimi yaradılmır - istifadəçi adı və e-poçt sistemdə məcburidir.
"""

ORGANIZATION = {
    "title": "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi",
    "short_name": "MSN",
    "authorized_person_name": "Mustafayev Vüqar Valeh oğlu",
    "authorized_person_position": "Nazir",
}

# (kod, ad, valideyn kodu)
DEPARTMENTS = [
    ("1", "Rəhbərlik", None),
    ("2", "Müdafiə sənayesi siyasəti şöbəsi", None),
    ("2.1", "Strateji planlama və inkişaf sektoru", "2"),
    ("2.2", "Statistik təhlil və rəqəmsallaşma sektoru", "2"),
    ("3", "Sənayenin tənzimlənməsi şöbəsi", None),
    ("3.1", "Lisenziyalaşdırma sektoru", "3"),
    ("3.2", "İdxal və ixrac əməliyyatlarına nəzarət sektoru", "3"),
    ("4", "Sənayenin koordinasiyası və texnoloji nəzarət şöbəsi", None),
    ("4.1", "Dövlət müdafiə sifarişlərinə nəzarət sektoru", "4"),
    ("4.2", "Təcrübi konstruktor və texnoloji işlərinin təşkili və icrasına nəzarət sektoru", "4"),
    ("5", "Layihələrin idarə edilməsi və innovasiyalar şöbəsi", None),
    ("5.1", "İnvestisiya layihələrinin hazırlanması və monitorinqi sektoru", "5"),
    ("5.2", "Elmi-tədqiqat işlərinə dəstək və innovasiyalar sektoru", "5"),
    ("6", "Beynəlxalq əlaqələr şöbəsi", None),
    ("6.1", "Cənubi və Şərqi Asiya ölkələri ilə əməkdaşlıq sektoru", "6"),
    ("6.2", "Avropa və Mərkəzi Asiya ölkələri ilə əməkdaşlıq sektoru", "6"),
    ("6.3", "Orta Şərq və Afrika ölkələri ilə əməkdaşlıq sektoru", "6"),
    ("6.4", "NATO və Cənubi Amerika ölkələri ilə əməkdaşlıq sektoru", "6"),
    ("14", "Protokol xidməti sektoru", "6"),
    ("7", "Maliyyə və hesabatlılıq şöbəsi", None),
    ("7.1", "Mühasibat uçotu sektoru", "7"),
    ("7.2", "Dövlət əmlakının uçotu və idarə edilməsi sektoru", "7"),
    ("7.3", "Büdcə və hesabatlılıq sektoru", "7"),
    ("7.4", "Təsərrüfat və təchizat sektoru", "7"),
    ("8", "Hüquq şöbəsi", None),
    ("8.1", "Hüquqi təminat sektoru", "8"),
    ("8.2", "Normativ aktlarla iş sektoru", "8"),
    ("9", "İnsan resurslarının idarə edilməsi şöbəsi", None),
    ("9.1", "Dövlət qulluğu və kadr məsələləri sektoru", "9"),
    ("9.2", "Əmək məhsuldarlığı və kadrların inkişafı sektoru", "9"),
    ("10", "Ümumi şöbə", None),
    ("10.1", "Sənədlərlə iş və müraciətlər sektoru", "10"),
    ("10.2", "İcraya nəzarət sektoru", "10"),
    ("11", "İnformasiya texnologiyaları şöbəsi", None),
    ("11.1", "Proqram təminatı sektoru", "11"),
    ("11.2", "Şəbəkə idarə edilməsi və texniki dəstək sektoru", "11"),
    ("12", "Dövlət sirrinin mühafizəsi və səfərbərlik şöbəsi", None),
    ("12.1", "Dövlət sirrinin mühafizəsi sektoru", "12"),
    ("12.2", "Səfərbərlik hazırlığı sektoru", "12"),
    ("15", "Mətbuat xidməti sektoru", None),
]

EZAM_SENAYECIHAZ = "Ezam – CİHAZ İSTEHSALAT BİRLİYİ MMC-nin «Sənayecihaz» Elmi-İstehsalat Müəssisəsi"

# (bölmə kodu, vəzifə, soyad, ad, cins, e-poçt, IP telefon)
STAFF = [
    ("1", "Nazirin müavini", "Baxışov", "Mehman", "male", "m.baxhisov@mdi.gov.az", "1010"),
    ("1", "Nazirin müavini", "Əzimov", "Hidayət", "male", "hidayat.azimov@mdi.gov.az", "1020"),
    ("1", "Aparatın rəhbəri", "Ağabalayev", "Samir", "male", "samir.aghabalayev@mdi.gov.az", "1040"),
    ("1", "Nazirin müşaviri", "Mirzəyev", "Tariyel", "male", "tariyel.mirzayev@mdi.gov.az", "1008"),
    ("1", "Nazirin müşaviri", "Əliyev", "Əlibaba", "male", "aliev.a@mdi.gov.az", None),
    ("1", "Nazirin müşaviri", "Babayev", "Arif", "male", "arif.babayev@mdi.gov.az", "1007"),
    ("1", "Ezam", "Sadıxova", "Validə", "female", "komekci.v@mdi.gov.az", "1005"),
    ("1", "Ezam", "Əliyev", "Rüstəm", "male", "r.aliyev@mdi.gov.az", "1006"),
    ("1", "Ezam", "Nəsirli", "Şəhriyar", "male", "nasirli.shahriyar@mdi.gov.az", "1021"),
    ("1", "Böyük mütəxəssis - katibə-stenoqrafçı", "Fətəliyeva", "Nailə", "female", "naila.fataliyeva@mdi.gov.az", "1041"),

    ("3", "Şöbə müdiri", "Ömərli", "Ceyhun", "male", "jeyhun.omarli@mdi.gov.az", "1300"),
    ("3.2", "Baş məsləhətçi", "Bərxudarova", "Aygün", "female", "aygun.barkhudarova@mdi.gov.az", "1302"),
    ("3.2", None, "İsmayılov", "Nəbi", "male", "nabi.ismayilov@mdi.gov.az", "1304"),

    ("4.1", "Baş məsləhətçi", "Musayev", "Vaqif", "male", "vagif.musayev@mdi.gov.az", "1404"),
    ("4", "Ezam", "Əliyev", "Məmmədsaleh", "male", "mammadsaleh.aliyev@mdi.gov.az", None),
    ("4", "Ezam", "Kərimov", "Əsəd", "male", "asad.karimov@mdi.gov.az", None),
    ("4", "Baş məsləhətçi", "Əliyev", "Müşfiq", "male", "mushfiq.aliyev@mdi.gov.az", None),

    ("6", "Şöbə müdiri", "Rzayeva", "Gülsüm", "female", "gulsum.rzayeva@mdi.gov.az", "1600"),
    ("6.3", "Baş məsləhətçi", "Süleymanova", "Ülkər", "female", "ulkar.suleymanova@mdi.gov.az", "1605"),
    ("6.3", "Məsləhətçi", "Mərdanov", "Elnur", "male", "elnur.mardanov@mdi.gov.az", None),
    ("6.3", "Ezam – «İqlim Elmi-İstehsalat Müəssisəsi» MMC, beynəlxalq əlaqələr üzrə məsləhətçi",
     "Qəhrəmanov", "Nazim", "male", "nazim.gahramanov@mdi.gov.az", "1604"),
    ("14", "Böyük məsləhətçi", "Quliyev", "Toğrul", "male", "toghrul.guliyev@mdi.gov.az", "1606"),
    ("14", None, "Həsənova", "Aysel", "female", "aysel.hasanova@mdi.gov.az", "1607"),
    ("14", None, "Məmmədova", "Aytən", "female", "aytan.mammadova@mdi.gov.az", None),

    ("7", "Şöbə müdiri", "Dadaşov", "Anar", "male", "anar.dadashov@mdi.gov.az", "1700"),
    ("7.1", "Müavin", "Mustafayeva", "Səbinə", "female", "sabina.mustafayeva@mdi.gov.az", "1701"),
    ("7.1", "Məsləhətçi", "Süleymanlı", "Tural", "male", "tural.suleymanli@mdi.gov.az", "1708"),
    ("7.2", "Böyük məsləhətçi", "Mikayılov", "Ülvi", "male", "ulvi.mikailov@mdi.gov.az", None),
    ("7.2", "Sektor müdiri", "Abıyev", "Əmin", "male", "amin.abiyev@mdi.gov.az", "1702"),
    ("7.3", "Sektor müdiri", "Şəmiyeva", "İlahə", "female", "ilaha.shamiyeva@mdi.gov.az", "1704"),
    ("7.3", "Baş məsləhətçi", "Əbdürrəhmanova", "Pərvanə", "female", "parvana.abdurrahmanova@mdi.gov.az", "1705"),
    ("7.4", "Məsləhətçi", "Nəsibov", "Amil", "male", "amil.nasibov@mdi.gov.az", None),
    ("7.4", "Ezam", "İlyaşina", "Anna", "female", "anna.elyashina@mdi.gov.az", "1707"),
    ("7.4", "Ezam", "Abdulla", "Elvin", "male", "elvin.abdulla@mdi.gov.az", "1706"),

    ("8", "Şöbə müdirinin müavini", "Qafarova", "Züleyxa", "female", "zuleykha.gafarova@mdi.gov.az", "1801"),
    ("8.1", "Şöbə müdirinin müavini", "Zeynalova", "Vəfa", "female", "vafa.zeynalova@mdi.gov.az", "1802"),
    ("8.1", "Baş məsləhətçi", "Qədimquliyeva", "Günel", "female", "gunel.gadimguliyeva@mdi.gov.az", "1803"),
    ("8.1", "Baş məsləhətçi", "Xasayeva", "Günel", "female", "gunel.xasayeva@mdi.gov.az", "1804"),
    ("8.1", "Böyük məsləhətçi", "Süleymanlı", "Sinayə", "female", "sinaya.suleymanli@mdi.gov.az", None),
    ("8.1", "Sektor müdiri", "Osmanova", "Nəzifə", "female", "nazifa.osmanova@mdi.gov.az", "1805"),

    ("9", "Şöbə müdiri", "Aslanov", "Azad", "male", "azad.aslanov@mdi.gov.az", "1900"),
    ("9.1", "Böyük məsləhətçi", "Babayeva", "Kəmalə", "female", "kamala.babayeva@mdi.gov.az", "1903"),
    ("9.1", "Sektor müdiri", "Cəfərli", "Süsən", "female", "susan.jafarli@mdi.gov.az", "1901"),
    ("9.1", "Məsləhətçi", "Bayramlı", "İlkin", "male", "ilkin.bayramli@mdi.gov.az", "1904"),
    ("9.2", "Məsləhətçi", "Məmmədova", "Nigar", "female", "nigar.mammadova@mdi.gov.az", None),
    ("9.2", "Ezam", "Həsənov", "Cavid", "male", "javid.hasanov@mdi.gov.az", None),

    ("10", "Şöbə müdiri", "Əhmədov", "Rövşən", "male", "rovshan.ahmadov@mdi.gov.az", "2000"),
    ("10.1", "Böyük məsləhətçi", "Fətullabəyli", "Aytən", "female", "aytan.fatullabayli@mdi.gov.az", "2006"),
    ("10.1", "Sektor müdiri", "İbrahimova", "Aynurə", "female", "aynura.ibrahimova@mdi.gov.az", "2001"),
    ("10.1", "Baş məsləhətçi", "Rüstəmova", "Həcər", "female", "hajar.rustamova@mdi.gov.az", "2003"),
    ("10.2", "Şöbə müdiri", "Sadıqov", "Tofiq", "male", "tofig.sadigov@mdi.gov.az", "2002"),
    ("10.2", "Aparıcı məsləhətçi", "Əliyeva", "Nigar", "female", "nigar.aliyeva@mdi.gov.az", "2004"),
    ("10.2", "Baş məsləhətçi", "Binyətova", "Arzu", "female", "arzu.binyatova@mdi.gov.az", "2005"),

    ("11", "Şöbə müdiri", "Mustafa", "Araz", "male", "araz.mustafa@mdi.gov.az", "1100"),
    ("11.1", EZAM_SENAYECIHAZ, "Şükürov", "Azər", "male", "azer.shukurov@mdi.gov.az", "1104"),
    ("11.1", EZAM_SENAYECIHAZ, "Bəşirova", "Ləman", "female", "laman.bashirova@mdi.gov.az", "1107"),
    ("11.1", "Sektor müdiri", "Həsənov", "Elnur", "male", "elnur.hasanov@mdi.gov.az", "1101"),
    ("11.1", EZAM_SENAYECIHAZ, "Paşayeva", "Məleykə", "female", "maleyka.pashayeva@mdi.gov.az", "1105"),
    ("11.1", EZAM_SENAYECIHAZ, "Rüstəmli", "Cavid", "male", "javid.rustamli@mdi.gov.az", "1102"),
    ("11.2", "Aparıcı məsləhətçi", "İbrahimov", "Elvin", "male", "elvin.ibrahimov@mdi.gov.az", "1103"),

    ("12", "Şöbə müdiri", "Əsədov", "Vüqar", "male", "vugar.asadov@mdi.gov.az", "2100"),
    ("12.1", "Baş məsləhətçi", "Kərimova", "Gülnarə", "female", "gulnara.karimova@mdi.gov.az", "2102"),
    ("12.1", "Baş məsləhətçi", "Rəhimova", "Gülnar", "female", "gulnar.rahimova@mdi.gov.az", "2103"),
    ("12.1", "Baş məsləhətçi", "Məmmədov", "Akif", "male", "akif.mammadov@mdi.gov.az", "2101"),
    ("12.2", "Aparıcı məsləhətçi", "Mirişov", "Ehtiram", "male", "ehtiram.mirishov@mdi.gov.az", "2104"),
    ("12.2", "Baş məsləhətçi", "Ağayev", "Qəzənfər", "male", "gazanfar.aghayev@mdi.gov.az", "2105"),
    ("12.2", "Böyük məsləhətçi", "Əfəndiyev", "Sozalı", "male", "sozali.afandiyev@mdi.gov.az", None),
    ("12.2", "Şöbə müdirinin müavini", "Ömərov", "Xəqani", "male", "khagani.omarov@mdi.gov.az", None),

    ("15", "Sektor müdiri", "Akmedova", "Narmin", "female", "narmin.akhmedova@mdi.gov.az", "2300"),
    ("15", "Baş məsləhətçi", "Mamedova", "Ayişən", "female", "ayishan.mamedova@mdi.gov.az", "2301"),
    ("15", "Aparıcı məsləhətçi", "Aslanov", "Elgün", "male", "elgun.aslanov@mdi.gov.az", "2303"),
    ("15", "Aparıcı məsləhətçi", "Bağırova", "Ləman", "female", "laman.baghirova@mdi.gov.az", "2302"),

    (None, "Baş mütəxəssis - sürücü", "Həsənov", "Orxan", "male", "orkhan.hasanov@mdi.gov.az", "1011"),
]

SUPERUSERS = {"laman.bashirova", "araz.mustafa"}
APPARATUS_HEAD = "samir.aghabalayev"

# Vəzifə sırası (Role.order) - icazə axını buna görə müəyyən olunur:
# 1 - avtomatik təsdiq, 2 - Aparat rəhbəri, 2..4 - yalnız Aparat rəhbəri təsdiqləyir, 5+ - tam axın
ROLE_ORDER = {
    "Aparatın rəhbəri": 2,
    "Nazirin müavini": 3,
    "Şöbə müdiri": 3,
    "Nazirin müşaviri": 4,
    "Şöbə müdirinin müavini": 5,
    "Müavin": 5,
    "Sektor müdiri": 5,
    "Baş məsləhətçi": 6,
    "Böyük məsləhətçi": 7,
    "Aparıcı məsləhətçi": 8,
    "Məsləhətçi": 9,
}
MANAGER_ROLES = {"Şöbə müdiri", "Sektor müdiri"}
