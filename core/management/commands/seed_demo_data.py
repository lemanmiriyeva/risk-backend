"""
Sistemi test/nümayiş üçün hazırlayır.

DİQQƏT: bu əmr bütün iş məlumatlarını SİLİR (risklər, inventar, loqlar,
icazələr, elanlar, təlimlər, bildirişlər, qurumlar, şöbələr, vəzifələr və
laman.bashirova-dan başqa bütün istifadəçilər). Modullar və alt modullar
saxlanılır.

İstifadə:
    python manage.py seed_demo_data --yes
    python manage.py seed_demo_data --yes --araz-password "YeniParol!2026"
"""
import copy
import os
import random
from datetime import datetime, time, timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from activity_logs.models import ActivityLog
from attendance_permissions.models import (
    AttendancePermission,
    AttendancePermissionDepartmentConfig,
    AttendancePermissionOrganizationConfig,
    LeavePeriod,
)
from authentication.models import Department, LoginAttempt, Organization, PasswordReset, Role, User
from bulletin.models import BulletinCategory, Circular, NewsPost
from core.models import Module, SubModule
from inventory.models import Inventory, InventoryNumberSequence, InventoryOwnerDepartment, InventoryOwnerPerson
from notifications.models import Notification
from operations.models import Operation, OperationApprovalStep
from risk.models import Risk, RiskLog
from trainings.models import QuizAnswer, QuizAttempt, QuizOption, QuizQuestion, Training, TrainingFeedback, TrainingProgress

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "seed_assets")

KEEP_USERNAME = "laman.bashirova"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
IPS = {"laman.bashirova": "10.20.4.37", "araz.mustafa": "10.20.4.12"}

# ---------------------------------------------------------------------------
# Qurumlar və onların şöbə / struktur bölmələri
# ---------------------------------------------------------------------------
ORGANIZATIONS = [
    {
        "key": "msn",
        "title": "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi",
        "short_name": "MSN",
        "departments": [
            ("it", "İnformasiya texnologiyaları şöbəsi", "İT", [
                ("it-cyber", "Kibertəhlükəsizlik sektoru", "KTS"),
                ("it-infra", "İnfrastruktur və şəbəkə sektoru", "İŞS"),
                ("it-soft", "Proqram təminatı və rəqəmsal həllər sektoru", "PTS"),
            ]),
            ("htes", "Hərbi-texniki əməkdaşlıq şöbəsi", "HTƏŞ", []),
            ("elm", "Elm, innovasiya və texnologiyalar şöbəsi", "EİTŞ", []),
            ("plan", "İstehsalatın planlaşdırılması və koordinasiyası şöbəsi", "İPKŞ", []),
            ("keyf", "Keyfiyyət və standartlaşdırma şöbəsi", "KSŞ", []),
            ("rejim", "Rejim və məxfilik şöbəsi", "RMŞ", []),
            ("maliyye", "Maliyyə və iqtisadiyyat şöbəsi", "MİŞ", [
                ("maliyye-muh", "Mühasibat uçotu sektoru", "MUS"),
            ]),
            ("kadr", "İnsan resursları şöbəsi", "İRŞ", []),
            ("huquq", "Hüquq şöbəsi", "HŞ", []),
            ("beynelxalq", "Beynəlxalq əlaqələr şöbəsi", "BƏŞ", []),
            ("audit", "Daxili audit şöbəsi", "DAŞ", []),
            ("ümumi", "Ümumi şöbə", "ÜŞ", []),
            ("mtt", "Maddi-texniki təminat şöbəsi", "MTTŞ", []),
            ("metbuat", "Mətbuat xidməti", "MX", []),
        ],
    },
    {
        "key": "ettkm",
        "title": "Elmi-Tədqiqat və Təcrübə-Konstruktor Mərkəzi",
        "short_name": "ETTKM",
        "departments": [
            ("ettkm-kb", "Konstruktor bürosu", "KB", []),
            ("ettkm-lab", "Sınaq laboratoriyası", "SL", []),
            ("ettkm-tex", "Texnoloji hazırlıq şöbəsi", "THŞ", []),
            ("ettkm-it", "İnformasiya texnologiyaları xidməti", "İTX", []),
        ],
    },
    {
        "key": "zavod",
        "title": "Mexaniki Emal və Montaj Zavodu",
        "short_name": "MEMZ",
        "departments": [
            ("zavod-sex", "Mexaniki emal sexi", "MES", []),
            ("zavod-tns", "Texniki nəzarət şöbəsi", "TNŞ", []),
            ("zavod-anbar", "Anbar təsərrüfatı", "AT", []),
            ("zavod-emek", "Əməyin mühafizəsi və texniki təhlükəsizlik bölməsi", "ƏMTTB", []),
        ],
    },
]

# ---------------------------------------------------------------------------
# İnventar: (açar, məhsulun adı, sahib növü, sahib, şöbə açarı - qurum üçün)
# ---------------------------------------------------------------------------
INVENTORY = [
    ("server", "Məxfi sənəd dövriyyəsi serveri — Dell PowerEdge R750", "department", "it"),
    ("mail", "Korporativ e-poçt serveri — Microsoft Exchange Server", "department", "it"),
    ("backup", "Ehtiyat surətləmə sistemi — Dell PowerProtect DD6400", "department", "it"),
    ("firewall", "Şəbəkə təhlükəsizlik divarı — FortiGate 600F", "department", "it"),
    ("switch", "Nüvə şəbəkə kommutatoru — Cisco Catalyst 9300", "department", "it"),
    ("rack", "Server şkafı və dəqiq kondisioner sistemi", "department", "it"),
    ("edms", "Elektron sənəd dövriyyəsi sistemi", "aparat", None),
    ("ups", "Kəsilməz enerji təchizatı qurğusu — APC Smart-UPS SRT 10kVA", "aparat", None),
    ("generator", "Ehtiyat dizel generatoru — 250 kVA", "aparat", None),
    ("acs", "Giriş-nəzarət sistemi (turniketlər və kart oxuyucuları)", "aparat", None),
    ("cctv", "Videomüşahidə sistemi — 64 kanallı NVR", "department", "mtt"),
    ("crypto", "Kriptoqrafik mühafizə vasitəsi (şəbəkə şifrələyicisi)", "department", "rejim"),
    ("hr", "Kadr uçotu informasiya sistemi", "department", "kadr"),
    ("acct", "Mühasibat uçotu proqram təminatı", "department", "maliyye"),
    ("printer", "Çoxfunksiyalı printer — Canon imageRUNNER ADVANCE DX C5840i", "department", "ümumi"),
    ("projector", "Lazer proyektor — Epson EB-L630U (iclas zalı)", "aparat", None),
    ("laptop", "Noutbuk — Lenovo ThinkPad T14 Gen 4", "person", "Araz Mustafa"),
    ("workstation", "İş stansiyası — HP Z4 G5", "person", "Laman Bashirova"),
    ("pdm", "Konstruktor sənədləri arxivi (CAD/PDM sistemi)", "department", "ettkm-kb"),
    ("cmm", "Koordinat ölçmə maşını (CMM) — sınaq laboratoriyası", "department", "ettkm-lab"),
    ("cnc", "Rəqəmli proqram idarəetməli (CNC) emal mərkəzi — DMG MORI DMU 65", "department", "zavod-sex"),
    ("alarm", "Anbar mühafizə siqnalizasiya sistemi", "department", "zavod-anbar"),
]
# Şəxsə və ya aparata aid inventarın qurumu
INVENTORY_ORG = {"laptop": "msn", "workstation": "msn"}

L_INFO = "«İnformasiya, informasiyalaşdırma və informasiyanın mühafizəsi haqqında» Azərbaycan Respublikasının Qanunu"
L_SECRET = "«Dövlət sirri haqqında» Azərbaycan Respublikasının Qanunu"
L_PD = "«Fərdi məlumatlar haqqında» Azərbaycan Respublikasının Qanunu"
L_ESIGN = "«Elektron imza və elektron sənəd haqqında» Azərbaycan Respublikasının Qanunu"
L_LABOR = "Azərbaycan Respublikasının Əmək Məcəlləsi"
STRATEGY = "Azərbaycan Respublikasının 2023–2027-ci illər üçün kibertəhlükəsizlik Strategiyası"
INTERNAL_POLICY = "Nazirliyin İnformasiya təhlükəsizliyi siyasəti (daxili qayda)"

# (təyinat, inventar, H, M, N, emal, qalıq risk, hüquqi əsas, beynəlxalq, milli, tezlik, insident qeydi, standartlar, yaradan)
RISKS = [
    ("Məxfi sənəd dövriyyəsi serverinə icazəsiz giriş", "server", 5, 3, 5, "prevention",
     "Çoxfaktorlu autentifikasiya və rol əsaslı giriş tətbiq edildikdən sonra qalıq risk orta səviyyədədir.",
     f"{L_SECRET}; {L_INFO}", "ISO/IEC 27001:2022 — A.5.15 Girişə nəzarət, A.8.5 Təhlükəsiz autentifikasiya",
     INTERNAL_POLICY, "Rüblük", "Uğursuz giriş cəhdləri SIEM vasitəsilə izlənilir; hadisə 1 saat ərzində Rejim və məxfilik şöbəsinə bildirilir.",
     "ISO/IEC 27002:2022; NIST SP 800-53 Rev.5 — AC-2, AC-6", "laman.bashirova"),
    ("Fişinq e-poçtları vasitəsilə hesab məlumatlarının ələ keçirilməsi", "mail", 4, 4, 4, "mitigation",
     "E-poçt filtrləri və əməkdaşların maarifləndirilməsi ilə ehtimal azaldılıb; qalıq risk orta.",
     L_INFO, "ISO/IEC 27001:2022 — A.6.3 Maarifləndirmə və təlim, A.8.7 Zərərli proqramlardan müdafiə",
     STRATEGY, "Aylıq", "Şübhəli məktublar İT şöbəsinə yönləndirilir; təsdiqlənmiş hal üzrə hesabın parolu dərhal dəyişdirilir.",
     "NIST CSF 2.0 — PR.AT; NIST SP 800-53 Rev.5 — AT-2", "araz.mustafa"),
    ("Ehtiyat surətlərin bərpa edilə bilməməsi", "backup", 5, 2, 5, "mitigation",
     "Rüblük bərpa sınaqları keçirildikdə qalıq risk aşağı səviyyədədir.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.13 Məlumatların ehtiyat surəti", INTERNAL_POLICY, "Rüblük",
     "Bərpa sınağının uğursuz nəticəsi 24 saat ərzində İT şöbəsinin direktoruna məruzə edilir.",
     "ISO 22301:2019 — Biznesin davamlılığı", "laman.bashirova"),
    ("Şəbəkə təhlükəsizlik divarının proqram təminatında aşkarlanmış boşluq", "firewall", 4, 3, 4, "prevention",
     "İstehsalçının yeniləmələri 72 saat ərzində tətbiq edilir; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.8 Texniki boşluqların idarə edilməsi, A.8.20 Şəbəkə təhlükəsizliyi",
     STRATEGY, "Aylıq", "Kritik boşluq barədə bülletenlər gündəlik izlənilir.",
     "NIST SP 800-53 Rev.5 — SI-2, SC-7", "araz.mustafa"),
    ("Konstruktor sənədlərinin (CAD/PDM) icazəsiz yayılması", "pdm", 5, 2, 5, "prevention",
     "Sənədlərin rəqəmsal su nişanı və çıxarılma nəzarəti tətbiq olunduqdan sonra qalıq risk orta.",
     f"{L_SECRET}; {L_INFO}", "ISO/IEC 27001:2022 — A.5.12 İnformasiyanın təsnifatı, A.8.12 Məlumat sızmasının qarşısının alınması",
     INTERNAL_POLICY, "Yarımillik", "Sızma şübhəsi olduqda Rejim və məxfilik şöbəsi dərhal məlumatlandırılır.",
     "AQAP 2110; ISO/IEC 27002:2022", "laman.bashirova"),
    ("CNC emal mərkəzinin idarəetmə sisteminin zərərli proqramla yoluxması", "cnc", 4, 2, 4, "mitigation",
     "İstehsalat şəbəkəsi ofis şəbəkəsindən ayrılıb; qalıq risk aşağı.",
     L_INFO, "IEC 62443 — Sənaye avtomatlaşdırma sistemlərinin təhlükəsizliyi", INTERNAL_POLICY, "Rüblük",
     "Avadanlıqda qeyri-adi davranış müşahidə edildikdə istehsal dayandırılır və İT xidmətinə məlumat verilir.",
     "IEC 62443-3-3; ISO/IEC 27001:2022 — A.8.22", "araz.mustafa"),
    ("Elektrik enerjisinin kəsilməsi nəticəsində server otağının dayanması", "ups", 4, 3, 3, "mitigation",
     "UPS və ehtiyat generator ilə 4 saatlıq fasiləsiz iş təmin edilir; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.7.11 Dəstəkləyici kommunal xidmətlər", INTERNAL_POLICY, "Yarımillik",
     "Enerji kəsilməsi monitorinq sistemi vasitəsilə növbətçi mühəndisə avtomatik bildirilir.",
     "ISO 22301:2019", "laman.bashirova"),
    ("Giriş-nəzarət kartlarının icazəsiz istifadəsi", "acs", 3, 3, 3, "mitigation",
     "Kartlar şəxsi fotoşəkillə təchiz edilib, itirilmiş kartlar dərhal bloklanır.",
     L_SECRET, "ISO/IEC 27001:2022 — A.7.2 Fiziki giriş", INTERNAL_POLICY, "Rüblük",
     "İtirilmiş kart barədə əməkdaş 2 saat ərzində Maddi-texniki təminat şöbəsinə məlumat verməlidir.",
     "ISO/IEC 27002:2022 — 7.2", "araz.mustafa"),
    ("Videomüşahidə yazılarının itirilməsi", "cctv", 3, 2, 3, "mitigation",
     "Yazılar 30 gün müddətində ikinci diskdə təkrarlanır.",
     L_INFO, "ISO/IEC 27001:2022 — A.7.4 Fiziki təhlükəsizliyin monitorinqi", INTERNAL_POLICY, "Yarımillik",
     "Disk nasazlığı barədə xəbərdarlıq avtomatik göndərilir.", "ISO/IEC 27002:2022 — 7.4", "laman.bashirova"),
    ("Kadr uçotu sistemində fərdi məlumatların qanunsuz emalı", "hr", 4, 2, 4, "prevention",
     "Giriş yalnız İnsan resursları şöbəsinin əməkdaşlarına verilib; qalıq risk aşağı.",
     f"{L_PD}; {L_LABOR}", "ISO/IEC 27001:2022 — A.5.34 Məxfilik və fərdi məlumatların qorunması",
     L_PD, "Yarımillik", "Fərdi məlumatların sızması aşkarlandıqda hüquq şöbəsi dərhal məlumatlandırılır.",
     "ISO/IEC 27701:2019", "araz.mustafa"),
    ("Xidməti noutbukun itməsi və ya oğurlanması", "laptop", 3, 2, 4, "transfer",
     "Avadanlıq sığorta ilə əhatə olunub, disk tam şifrələnib; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.1 İstifadəçi son qurğuları, A.8.24 Kriptoqrafiyanın tətbiqi",
     INTERNAL_POLICY, "İllik", "İtki halında qurğu uzaqdan bloklanır, hadisə 1 saat ərzində qeydə alınır.",
     "NIST SP 800-53 Rev.5 — MP-5, SC-28", "laman.bashirova"),
    ("Ölçmə avadanlığının kalibrləmə müddətinin keçməsi", "cmm", 3, 3, 2, "mitigation",
     "Kalibrləmə qrafiki elektron qaydada izlənilir; qalıq risk aşağı.",
     "«Ölçmələrin vəhdətinin təmin edilməsi haqqında» Azərbaycan Respublikasının Qanunu",
     "ISO/IEC 17025:2017 — Sınaq və kalibrləmə laboratoriyaları", "—", "Yarımillik",
     "Müddəti keçmiş avadanlıqla aparılan ölçmələrin nəticələri etibarsız sayılır və təkrarlanır.",
     "ISO/IEC 17025:2017; ISO 9001:2015 — 7.1.5", "araz.mustafa"),
    ("Mühasibat proqram təminatına texniki dəstəyin dayandırılması", "acct", 3, 2, 2, "acceptance",
     "Yeni versiyaya keçid 2027-ci ilin büdcəsinə daxil edilib; risk qəbul edilib.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.32 Dəyişikliklərin idarə edilməsi", "—", "İllik",
     "—", "ISO/IEC 27002:2022", "laman.bashirova"),
    ("Kriptoqrafik açarların düzgün idarə edilməməsi", "crypto", 5, 1, 5, "prevention",
     "Açarlar iki şəxsin iştirakı ilə yaradılır və seyfdə saxlanılır; qalıq risk aşağı.",
     f"{L_SECRET}; {L_ESIGN}", "ISO/IEC 27001:2022 — A.8.24 Kriptoqrafiyanın tətbiqi", INTERNAL_POLICY, "Rüblük",
     "Açarın kompromitasiyası şübhəsi olduqda açar dərhal ləğv edilir.", "NIST SP 800-57", "araz.mustafa"),
    ("Anbar mühafizə siqnalizasiyasının nasazlığı", "alarm", 4, 2, 5, "mitigation",
     "Sistem iki müstəqil kanal üzrə mühafizə postuna qoşulub; qalıq risk orta.",
     L_SECRET, "ISO/IEC 27001:2022 — A.7.4 Fiziki təhlükəsizliyin monitorinqi", INTERNAL_POLICY, "Aylıq",
     "Nasazlıq zamanı anbar sahəsinə fiziki mühafizə postu əlavə edilir.",
     "ISO 45001:2018", "laman.bashirova"),
    ("Elektron sənəd dövriyyəsi sistemində məlumatların bütövlüyünün pozulması", "edms", 4, 2, 3, "mitigation",
     "Sənədlər elektron imza ilə təsdiqlənir və dəyişikliklər jurnalda qeydə alınır.",
     L_ESIGN, "ISO/IEC 27001:2022 — A.8.15 Jurnallaşdırma", INTERNAL_POLICY, "Yarımillik",
     "Bütövlük pozuntusu aşkar edildikdə sənədin əvvəlki versiyası bərpa olunur.",
     "ISO 15489-1:2016", "araz.mustafa"),
    ("İş stansiyasında lisenziyasız proqram təminatının istifadəsi", "workstation", 2, 2, 2, "prevention",
     "Proqram quraşdırılması yalnız İT şöbəsi tərəfindən həyata keçirilir.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.19 Proqram təminatının quraşdırılması", INTERNAL_POLICY, "İllik",
     "—", "ISO/IEC 19770-1", "laman.bashirova"),
    ("Ehtiyat generatorun yanacaq ehtiyatının kifayət etməməsi", "generator", 3, 1, 3, "acceptance",
     "Yanacaq ehtiyatı aylıq yoxlanılır; risk qəbul edilib.",
     "—", "ISO 22301:2019", "—", "Aylıq", "—", "ISO 22301:2019 — 8.4", "araz.mustafa"),
]

CIRCULARS = [
    ("ferman", "Azərbaycan Respublikası Müdafiə Sənayesi Nazirliyinin yaradılması haqqında", "", (2005, 12, 16)),
    ("serencam", "2023–2027-ci illər üçün Azərbaycan Respublikasının kibertəhlükəsizlik Strategiyasının təsdiq edilməsi haqqında", "", None),
    ("emr", "İnformasiya təhlükəsizliyi siyasətinin təsdiq edilməsi haqqında", "MSN-Ə-114", -40),
    ("emr", "2026-cı il üzrə informasiya aktivlərinin risk qiymətləndirməsinin keçirilməsi haqqında", "MSN-Ə-127", -21),
    ("daxili_qayda", "Məxfi sənədlərlə iş qaydaları", "DQ-07", -60),
    ("daxili_qayda", "Parolların və hesabların idarə edilməsi qaydası", "DQ-09", -33),
    ("daxili_qayda", "Xidməti elektron poçtdan istifadə qaydaları", "DQ-11", -12),
    ("daxili_qayda", "Daşınan yaddaş qurğularından istifadə qaydası", "DQ-12", -5),
]

NEWS = [
    ("kibertehlukesizlik-ayi", "Oktyabr — Kibertəhlükəsizlik maarifləndirmə ayı",
     "Nazirlikdə kibertəhlükəsizlik üzrə maarifləndirmə ayı çərçivəsində silsilə tədbirlər başlayıb.",
     "Oktyabr ayı ərzində Nazirliyin və tabe qurumların əməkdaşları üçün fişinq hücumlarının tanınması, "
     "parol təhlükəsizliyi və məxfi məlumatların qorunması mövzularında təlimlər keçiriləcək.\n\n"
     "Təlim materialları «Təlimlər» bölməsində yerləşdirilib. Hər bir əməkdaşdan materiallara tam baxması "
     "və yekun testi tamamlaması xahiş olunur.", 1),
    ("elektron-senedler", "Elektron sənəd dövriyyəsi sisteminin yeni versiyası istifadəyə verildi",
     "Yeni versiyada elektron imza ilə təsdiqləmə və sənədlərin axtarışı təkmilləşdirilib.",
     "İnformasiya texnologiyaları şöbəsi tərəfindən elektron sənəd dövriyyəsi sisteminin yeni versiyası "
     "istifadəyə verilib. Yeniləmə ilə sənədlərin elektron imza ilə təsdiqlənməsi sürətlənib, axtarış "
     "imkanları genişləndirilib və dəyişikliklər jurnalı əlavə olunub.\n\n"
     "Sistemlə bağlı sualları İT şöbəsinə ünvanlaya bilərsiniz.", 6),
    ("risk-qiymetlendirmesi", "İnformasiya aktivlərinin illik risk qiymətləndirməsi başlayır",
     "Qiymətləndirmə Nazirlik və tabe qurumların bütün struktur bölmələrini əhatə edəcək.",
     "Nazirin müvafiq əmrinə əsasən 2026-cı il üzrə informasiya aktivlərinin risk qiymətləndirməsi "
     "keçiriləcək. Struktur bölmələrin rəhbərlərindən aktivlərin inventar siyahısını yeniləmələri və "
     "«Risk Reyestr Sistemi»ndə müvafiq qeydləri aktuallaşdırmaları xahiş olunur.", 13),
    ("telim", "Rəqəmsal bacarıqların inkişafı üzrə təlim proqramı",
     "Əməkdaşlar üçün yeni onlayn təlim materialları əlavə edildi.",
     "«Təlimlər» bölməsinə informasiya təhlükəsizliyinin əsasları, fişinq hücumlarının tanınması və məxfi "
     "sənədlərlə iş qaydaları üzrə video materiallar əlavə olunub. Hər materialdan sonra qısa test təqdim edilir.", 20),
    ("ehtiyat-suret", "Server otağında planlı profilaktika işləri aparılacaq",
     "Şənbə günü 10:00–14:00 arasında bəzi xidmətlərdə qısamüddətli fasilə ola bilər.",
     "İnfrastruktur və şəbəkə sektoru tərəfindən server otağında kəsilməz enerji təchizatı qurğularının "
     "və ehtiyat surətləmə sisteminin planlı profilaktikası aparılacaq. İş zamanı e-poçt və elektron sənəd "
     "dövriyyəsi sistemində qısamüddətli fasilələr mümkündür.", 27),
    ("sergi", "Beynəlxalq müdafiə sərgisində iştiraka hazırlıq",
     "Hərbi-texniki əməkdaşlıq şöbəsi sərgi üzrə işçi qrupunun ilk iclasını keçirib.",
     "İclasda Nazirliyin və tabe qurumların sərgidə nümayiş etdiriləcək məhsulları, stendin konsepsiyası və "
     "işçi qrupunun vəzifə bölgüsü müzakirə olunub.", 41),
]

TRAININGS = [
    ("informasiya-tehlukesizliyi", "İnformasiya təhlükəsizliyinin əsasları",
     "Məxfilik, bütövlük və əlçatanlıq prinsipləri, parol qaydaları, təmiz masa qaydası və insident barədə məlumat vermə.",
     [
         ("İnformasiya təhlükəsizliyinin üç əsas prinsipi hansılardır?",
          ["Məxfilik, bütövlük, əlçatanlıq", "Sürət, həcm, qiymət", "Parol, antivirus, şəbəkə"], 0),
         ("Parolun minimum uzunluğu neçə simvol olmalıdır?", ["6", "8", "12"], 2),
         ("İş yerindən ayrılarkən nə etməlisiniz?",
          ["Monitoru söndürməliyəm", "Ekranı kilidləməliyəm (Win + L)", "Heç nə"], 1),
         ("Şübhəli hal aşkar etdikdə ilk addım nədir?",
          ["Kompüteri sıfırlamaq", "İT şöbəsinə dərhal müraciət etmək", "Həmkarlara yazmaq"], 1),
     ]),
    ("fisinq-hucumlari", "Fişinq hücumlarının tanınması",
     "Saxta e-poçt və mesajların əlamətləri, şübhəli məktubla qarşılaşdıqda atılmalı addımlar.",
     [
         ("Fişinq məktubunun tipik əlaməti hansıdır?",
          ["Rəsmi imza", "Təcili tələb və ya hədə", "Qısa mətn"], 1),
         ("Şübhəli qoşma ilə nə etmək lazımdır?",
          ["Açıb yoxlamaq", "Həmkara göndərmək", "Açmadan İT şöbəsinə yönləndirmək"], 2),
         ("İT şöbəsi parolunuzu e-poçtla soruşa bilərmi?", ["Bəli", "Xeyr", "Yalnız rəhbər icazə verərsə"], 1),
     ]),
    ("mexfi-senedler", "Məxfi sənədlərlə iş qaydaları",
     "Məxfilik dərəcələri, sənədlərin qeydiyyatı, saxlanması, daşınması və məhv edilməsi qaydaları.",
     [
         ("Hansı məxfilik dərəcəsi mövcud deyil?", ["Tam məxfi", "Xüsusi əhəmiyyətli", "Yarı məxfi"], 2),
         ("Məxfi sənədlər harada saxlanılır?", ["Masanın siyirməsində", "Möhürlənmiş seyfdə", "Ümumi qovluqda"], 1),
         ("Məxfi sənədlərin məhv edilməsi necə rəsmiləşdirilir?",
          ["Komissiya aktı ilə", "Şifahi razılıqla", "Rəsmiləşdirilmir"], 0),
     ]),
]

MODULE_DESCRIPTIONS = {
    "risk": "İnformasiya aktivləri üzrə risklərin qiymətləndirilməsi, emalı və monitorinqi.",
    "activity_logs": "İstifadəçi fəaliyyətinin və sistem hadisələrinin audit jurnalı.",
    "admin": "İstifadəçilər, qurumlar, şöbə və struktur bölmələr, vəzifələr və modul icazələri.",
    "inventory": "İnformasiya aktivlərinin və avadanlığın uçotu.",
    "icazeler": "İş saatı ərzində çıxış icazələri: sorğu, təsdiq və tarixçə.",
    "operations": "Bütün modullar üzrə əməliyyatların və təsdiq axınlarının vahid reyestri.",
}
SUB_MODULE_DESCRIPTIONS = {
    "risk_register": "Risklərin siyahısı, əlavə edilməsi və redaktəsi.",
    "risk_view_table": "Bütün risk qeydlərinin cədvəl görünüşü və Excel-ə ixracı.",
    "risk_log": "Risk qeydləri üzrə dəyişikliklərin tarixçəsi.",
}


class Command(BaseCommand):
    help = "Bütün iş məlumatlarını sıfırlayır və sistemi rəsmi test məlumatları ilə doldurur."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Silinməni təsdiqləyir.")
        parser.add_argument("--araz-password", default="Araz@MIS2026", help="araz.mustafa üçün ilkin parol.")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError(
                "Bu əmr bütün məlumatları silir. Davam etmək üçün: python manage.py seed_demo_data --yes"
            )
        laman = User.objects.filter(username=KEEP_USERNAME).first()
        if not laman:
            raise CommandError(f"'{KEEP_USERNAME}' istifadəçisi tapılmadı.")

        self.rng = random.Random(2026)
        self.now = timezone.localtime()

        with transaction.atomic():
            self._wipe(laman)
            orgs, deps = self._structure()
            laman, araz = self._users(laman, orgs, deps, options["araz_password"])
            self._modules(laman, araz)
            invs = self._inventory(orgs, deps, laman, araz)
            self._risks(invs, laman, araz)
            self._attendance(orgs, deps, laman, araz)
            self._bulletin(laman, araz)
            self._trainings(laman, araz)
            self._activity_logs(laman, araz)
            self._notifications(laman, araz)

        self.stdout.write(self.style.SUCCESS(
            "Hazırdır. Qurum: {}, şöbə/bölmə: {}, inventar: {}, risk: {}, loq: {}, elan: {}, təlim: {}.".format(
                Organization.objects.count(), Department.objects.count(), Inventory.objects.count(),
                Risk.objects.count(), ActivityLog.objects.count(),
                Circular.objects.count() + NewsPost.objects.count(), Training.objects.count(),
            )
        ))
        self.stdout.write(f"araz.mustafa parolu: {options['araz_password']}")

    # ------------------------------------------------------------------ köməkçilər
    def at(self, days_ago, hour, minute=0):
        """Bakı vaxtı ilə 'days_ago' gün əvvəl, göstərilən saatda."""
        day = (self.now - timedelta(days=days_ago)).date()
        return timezone.make_aware(datetime.combine(day, time(hour, minute)))

    def workdays(self, count):
        """Bu gündən geriyə doğru son 'count' iş günü (ən köhnədən yeniyə)."""
        result, d = [], 0
        while len(result) < count:
            if (self.now - timedelta(days=d)).weekday() < 5:
                result.append(d)
            d += 1
        return list(reversed(result))

    # ------------------------------------------------------------------ silmə
    def _wipe(self, laman):
        self.stdout.write("Köhnə məlumatlar silinir...")
        Notification.objects.all().delete()
        OperationApprovalStep.objects.all().delete()
        Operation.objects.all().delete()
        ActivityLog.objects.all().delete()
        RiskLog.objects.all().delete()
        Risk.objects.all().delete()
        Inventory.objects.all().delete()
        InventoryOwnerPerson.objects.all().delete()
        InventoryOwnerDepartment.objects.all().delete()
        InventoryNumberSequence.objects.all().delete()
        LeavePeriod.objects.all().delete()
        AttendancePermission.objects.all().delete()
        AttendancePermissionDepartmentConfig.objects.all().delete()
        AttendancePermissionOrganizationConfig.objects.all().delete()
        # Fayllar diskdən də silinir ki, əmr təkrar işlədildikdə köhnə video/şəkillər yığılmasın
        for post in NewsPost.objects.exclude(image=""):
            post.image.delete(save=False)
        for circular in Circular.objects.exclude(file=""):
            circular.file.delete(save=False)
        for training in Training.objects.all():
            training.video.delete(save=False)
            if training.thumbnail:
                training.thumbnail.delete(save=False)
        Circular.objects.all().delete()
        NewsPost.objects.all().delete()
        QuizAnswer.objects.all().delete()
        QuizAttempt.objects.all().delete()
        TrainingFeedback.objects.all().delete()
        TrainingProgress.objects.all().delete()
        Training.objects.all().delete()
        LogEntry.objects.all().delete()
        PasswordReset.objects.all().delete()
        LoginAttempt.objects.all().delete()
        User.objects.exclude(pk=laman.pk).delete()
        laman.role = None
        laman.department = None
        laman.organization = None
        laman.save()
        Role.objects.all().delete()
        Department.objects.all().delete()
        Organization.objects.all().delete()
        # Risklərin silinməsi siqnal vasitəsilə "Sildi" əməliyyatları yaradır - onları da təmizləyirik
        OperationApprovalStep.objects.all().delete()
        Operation.objects.all().delete()

    # ------------------------------------------------------------------ struktur
    def _structure(self):
        orgs, deps = {}, {}
        order = 1
        for o in ORGANIZATIONS:
            org = Organization.objects.create(title=o["title"], short_name=o["short_name"])
            orgs[o["key"]] = org
            for key, title, short, children in o["departments"]:
                dep = Department.objects.create(
                    title=title, shortname=short, organization=org, order=order,
                    unique_code=f"{o['short_name']}-{short}",
                )
                order += 1
                deps[key] = dep
                is_it = key == "it"
                Role.objects.create(title="Direktor" if is_it else "Şöbə müdiri", department=dep,
                                    is_manager_role=True, order=3)
                Role.objects.create(title="Baş mütəxəssis", department=dep, order=6)
                Role.objects.create(title="Aparıcı mütəxəssis", department=dep, order=7)
                Role.objects.create(title="Mütəxəssis", department=dep, order=8)
                for c_key, c_title, c_short in children:
                    child = Department.objects.create(
                        title=c_title, shortname=c_short, organization=org, parent=dep, order=order,
                        unique_code=f"{o['short_name']}-{c_short}",
                    )
                    order += 1
                    deps[c_key] = child
                    Role.objects.create(title="Sektor müdiri", department=child, is_manager_role=True, order=5)
                    Role.objects.create(title="Baş mütəxəssis", department=child, order=6)
                    Role.objects.create(title="Aparıcı mütəxəssis", department=child, order=7)
        return orgs, deps

    # ------------------------------------------------------------------ istifadəçilər
    def _users(self, laman, orgs, deps, araz_password):
        it, msn = deps["it"], orgs["msn"]
        laman.firstname = laman.firstname or "Laman"
        laman.lastname = laman.lastname or "Bashirova"
        laman.organization = msn
        laman.department = it
        laman.role = Role.objects.get(department=it, title="Aparıcı mütəxəssis")
        laman.is_superuser = True
        laman.is_staff = True
        laman.is_active = True
        laman.is_approved = True
        laman.is_org_admin = False
        laman.is_apparatus_head = False
        laman.save()

        araz = User.objects.create_user(
            username="araz.mustafa", email="araz.mustafa@mdi.gov.az", password=araz_password,
            firstname="Araz", lastname="Mustafa", gender="male",
            organization=msn, department=it, role=Role.objects.get(department=it, title="Direktor"),
            is_approved=True, birth_date=(self.now + timedelta(days=3)).date().replace(year=1986),
            work_phone_number="1101",
        )
        # İT şöbəsinin rəhbəri - araz.mustafa (laman.bashirova şöbə müdiri DEYİL)
        it.manager = araz
        it.save(update_fields=["manager"])
        return laman, araz

    # ------------------------------------------------------------------ modullar
    def _modules(self, laman, araz):
        for code, text in MODULE_DESCRIPTIONS.items():
            Module.objects.filter(code=code, description__in=["", None]).update(description=text)
        for code, text in SUB_MODULE_DESCRIPTIONS.items():
            SubModule.objects.filter(code=code, description__in=["", None]).update(description=text)
        SubModule.objects.filter(code="config").update(
            title="Konfiqurasiya",
            description="Aparat rəhbəri və şöbə müdirləri üzrə təsdiq axınının tənzimlənməsi.",
        )
        # araz.mustafa: İT şöbəsinin direktoru kimi iş modullarına girişi
        for code in ("risk", "inventory", "icazeler", "operations", "bulletin", "trainings", "activity_logs"):
            module = Module.objects.filter(code=code).first()
            if module:
                module.permitted_users.add(araz)
        for code in ("risk_register", "risk_view_table", "risk_log", "training_materials", "training_statistics"):
            sub = SubModule.objects.filter(code=code).first()
            if sub:
                sub.permitted_users.add(araz)
        trainings = Module.objects.filter(code="trainings").first()
        if trainings:
            trainings.admin_users.add(araz)

    # ------------------------------------------------------------------ inventar
    def _inventory(self, orgs, deps, laman, araz):
        invs = {}
        days = 75
        for key, name, owner_type, owner in INVENTORY:
            kwargs = {"product_name": name, "owner_type": owner_type}
            if owner_type == "department":
                kwargs["owner_department"], _ = InventoryOwnerDepartment.objects.get_or_create(name=deps[owner].title)
            elif owner_type == "person":
                kwargs["owner_person"], _ = InventoryOwnerPerson.objects.get_or_create(full_name=owner)
            creator = laman if len(invs) % 3 else araz
            inv = Inventory.objects.create(created_by=creator, updated_by=creator, **kwargs)
            created = self.at(days, 10 + len(invs) % 6, 5 + (len(invs) * 7) % 50)
            Inventory.objects.filter(pk=inv.pk).update(created_at=created, updated_at=created)
            days -= 2
            if owner_type == "department":
                inv._org = deps[owner].organization
            else:
                inv._org = orgs[INVENTORY_ORG.get(key, "msn")]
            invs[key] = inv
        return invs

    # ------------------------------------------------------------------ risklər
    def _risks(self, invs, laman, araz):
        from risk import services as risk_services

        users = {"laman.bashirova": laman, "araz.mustafa": araz}
        risk_ct = ContentType.objects.get_for_model(Risk)
        days = 44
        for idx, row in enumerate(RISKS):
            (designation, inv_key, h, m, n, treatment, residual, legal, intl, national,
             freq, incident, standards, creator_name) = row
            creator = users[creator_name]
            inv = invs[inv_key]
            risk = Risk.objects.create(
                designation=designation, inventory=inv, organization=inv._org,
                asset_value=h, probability=m, impact=n, treatment_option=treatment,
                residual_risk=residual, legal_basis=legal, international_framework=intl,
                national_legal_reference=national, update_frequency=freq,
                incident_notification_notes=incident, standard_references=standards,
                created_by=creator, updated_by=creator,
            )
            created = self.at(days, 10 + idx % 7, (idx * 13) % 60)
            risk_services.log_created(risk, creator)
            RiskLog.objects.filter(risk=risk).update(timestamp=created, ip_address=IPS[creator.username], user_agent=UA)
            Operation.objects.filter(content_type=risk_ct, object_id=risk.pk).update(
                created_at=created, updated_at=created, ip_address=IPS[creator.username], user_agent=UA)
            final_time = created

            # Bəzi risklər sonradan yenidən qiymətləndirilib
            if idx % 4 == 1:
                editor = araz if creator == laman else laman
                old = copy.copy(risk)
                risk.probability = max(1, risk.probability - 1)
                risk.residual_risk = residual + " Əlavə nəzarət tədbirləri tətbiq edilib."
                risk.updated_by = editor
                risk.save()
                risk_services.log_updated(old, risk, editor)
                edited = created + timedelta(days=3, hours=2)
                RiskLog.objects.filter(risk=risk, action_type=RiskLog.ACTION_UPDATED).update(
                    timestamp=edited, ip_address=IPS[editor.username], user_agent=UA)
                Operation.objects.filter(content_type=risk_ct, object_id=risk.pk, action=Operation.ACTION_UPDATED).update(
                    created_at=edited, updated_at=edited, ip_address=IPS[editor.username], user_agent=UA)
                final_time = edited
            Risk.objects.filter(pk=risk.pk).update(created_at=created, updated_at=final_time)
            days -= 2

        # Excel ixracı və siyahıya baxış qeydləri
        for d, user in ((9, laman), (4, araz), (1, laman)):
            risk_services.log_viewed_list(user, Risk.objects.count())
            RiskLog.objects.filter(timestamp__gte=self.now - timedelta(minutes=5)).update(
                timestamp=self.at(d, 11, 20), ip_address=IPS[user.username], user_agent=UA)
        risk_services.log_exported(laman, "risk_list", Risk.objects.count())
        RiskLog.objects.filter(action_type=RiskLog.ACTION_EXPORTED).update(
            timestamp=self.at(1, 11, 26), ip_address=IPS[laman.username], user_agent=UA)

    # ------------------------------------------------------------------ icazələr
    def _attendance(self, orgs, deps, laman, araz):
        msn = orgs["msn"]
        # Test mühitində ayrıca Aparat rəhbəri yoxdur: sorğunu şöbə müdirinin təsdiqi yekunlaşdırır.
        for org in orgs.values():
            AttendancePermissionOrganizationConfig.objects.create(organization=org, apparatus_head_enabled=False)
        for dep in deps.values():
            AttendancePermissionDepartmentConfig.objects.create(
                organization=dep.organization, department=dep, manager_enabled=True,
            )

        ap_ct = ContentType.objects.get_for_model(AttendancePermission)
        rows = [
            # (gün əvvəl, başlama, bitmə, yer, səbəb, status, rəy)
            (18, time(11, 0), time(13, 0), "Dövlət Xidmətlər Agentliyi (ASAN xidmət)", "Şəxsiyyət vəsiqəsinin yenilənməsi", "approved", "Razıyam."),
            (11, time(15, 30), time(17, 0), "Rəqəmsal İnkişaf və Nəqliyyat Nazirliyi", "Elektron imza sertifikatının yenilənməsi üzrə görüş", "approved", "Təsdiq edirəm."),
            (6, time(9, 0), time(10, 30), "Poliklinika", "Tibbi müayinə", "rejected", "Həmin saatda şöbənin iclası planlaşdırılıb, başqa vaxt seçin."),
            (-1, time(14, 0), time(16, 0), "Bakı Dövlət Universiteti", "Kibertəhlükəsizlik üzrə seminarda iştirak", "pending", ""),
        ]
        for days_ago, start, end, location, reason, status, comment in rows:
            created = self.at(max(days_ago, 0) + 2, 9, 40)
            perm = AttendancePermission.objects.create(
                user=laman, date=(self.now - timedelta(days=days_ago)).date(),
                start_time=start, end_time=end, location=location, reason=reason,
            )
            if status != "pending":
                reviewed = created + timedelta(hours=1, minutes=15)
                perm.department_reviewed_by = araz
                perm.department_reviewed_at = reviewed
                perm.department_review_comment = comment
                perm.reviewed_by = araz
                perm.reviewed_at = reviewed
                perm.review_comment = comment if status == "rejected" else (
                    "Şöbə müdiri tərəfindən təsdiqləndi. Aparat rəhbəri mərhələsi konfiqurasiyada deaktiv edilib."
                )
                perm.status = AttendancePermission.STATUS_APPROVED if status == "approved" else AttendancePermission.STATUS_REJECTED
                perm.save()
            AttendancePermission.objects.filter(pk=perm.pk).update(created_at=created, updated_at=created)
            ops = Operation.objects.filter(content_type=ap_ct, object_id=perm.pk)
            ops.update(created_at=created, updated_at=created, ip_address=IPS["laman.bashirova"], user_agent=UA)
            OperationApprovalStep.objects.filter(operation__in=ops).update(created_at=created, updated_at=created)

    # ------------------------------------------------------------------ elanlar
    def _bulletin(self, laman, araz):
        cats = {
            "ferman": ("Fərman", "Fərmanlar", "gavel", 1),
            "serencam": ("Sərəncam", "Sərəncamlar", "assignment", 2),
            "emr": ("Əmr", "Əmrlər", "description", 3),
            "daxili_qayda": ("Daxili qayda", "Daxili qaydalar", "rule", 4),
        }
        for key, (label, plural, icon, order) in cats.items():
            BulletinCategory.objects.get_or_create(
                key=key, defaults={"label": label, "plural_label": plural, "icon": icon, "order": order},
            )
        for i, (key, title, number, when) in enumerate(CIRCULARS):
            if isinstance(when, tuple):
                doc_date = datetime(*when).date()
            elif isinstance(when, int):
                doc_date = (self.now + timedelta(days=when)).date()
            else:
                doc_date = None
            c = Circular.objects.create(
                category=BulletinCategory.objects.get(key=key), title=title, number=number,
                document_date=doc_date, created_by=laman if i % 2 else araz,
            )
            ts = self.at(abs(when) if isinstance(when, int) else 50, 12, 10)
            Circular.objects.filter(pk=c.pk).update(created_at=ts, updated_at=ts)

        for i, (slug, title, summary, body, days_ago) in enumerate(NEWS):
            published = self.at(days_ago, 10, 30)
            post = NewsPost(title=title, summary=summary, body=body, published_at=published,
                            created_by=laman if i % 2 == 0 else araz)
            with open(os.path.join(ASSETS, "news", f"{slug}.jpg"), "rb") as fh:
                post.image.save(f"{slug}.jpg", File(fh), save=False)
            post.save()
            NewsPost.objects.filter(pk=post.pk).update(created_at=published, updated_at=published)

    # ------------------------------------------------------------------ təlimlər
    def _trainings(self, laman, araz):
        trainings = []
        for i, (slug, title, description, questions) in enumerate(TRAININGS):
            t = Training(title=title, description=description, duration_seconds=45, pass_percent=60, created_by=araz)
            with open(os.path.join(ASSETS, "videos", f"{slug}.mp4"), "rb") as fh:
                t.video.save(f"{slug}.mp4", File(fh), save=False)
            with open(os.path.join(ASSETS, "thumbnails", f"{slug}.jpg"), "rb") as fh:
                t.thumbnail.save(f"{slug}.jpg", File(fh), save=False)
            t.save()
            created = self.at(22 - i * 3, 10, 0)
            Training.objects.filter(pk=t.pk).update(created_at=created, updated_at=created)
            for q_idx, (text, options, correct) in enumerate(questions):
                q = QuizQuestion.objects.create(training=t, text=text, order=q_idx)
                for o_idx, opt in enumerate(options):
                    QuizOption.objects.create(question=q, text=opt, is_correct=o_idx == correct, order=o_idx)
            trainings.append(t)

        def complete(user, training, days_ago, wrong=(), rating=None, comment=""):
            started = self.at(days_ago, 14, 5)
            done = started + timedelta(seconds=training.duration_seconds + 20)
            TrainingProgress.objects.create(
                user=user, training=training, status=TrainingProgress.STATUS_COMPLETED,
                max_position=training.duration_seconds, session_started_at=started, last_heartbeat_at=done,
                attempts_count=1, first_started_at=started, completed_at=done,
            )
            questions = list(training.quiz_questions.all().order_by("order"))
            attempt = QuizAttempt.objects.create(user=user, training=training, submitted_at=done + timedelta(minutes=2))
            correct_count = 0
            for q_idx, q in enumerate(questions):
                options = list(q.options.all().order_by("order"))
                right = next(o for o in options if o.is_correct)
                chosen = next(o for o in options if not o.is_correct) if q_idx in wrong else right
                ok = chosen.pk == right.pk
                correct_count += ok
                QuizAnswer.objects.create(
                    attempt=attempt, question=q, selected_option=chosen, question_text=q.text,
                    selected_text=chosen.text, correct_text=right.text, is_correct=ok,
                )
            attempt.correct_count = correct_count
            attempt.total_count = len(questions)
            attempt.percent = round(100 * correct_count / max(1, len(questions)))
            attempt.passed = attempt.percent >= training.pass_percent
            attempt.save()
            if rating:
                fb = TrainingFeedback.objects.create(user=user, training=training, rating=rating, comment=comment)
                TrainingFeedback.objects.filter(pk=fb.pk).update(created_at=done + timedelta(minutes=4), updated_at=done + timedelta(minutes=4))

        complete(laman, trainings[0], 19, rating=5, comment="Material qısa və aydındır, praktik nümunələr faydalı oldu.")
        complete(laman, trainings[1], 8, wrong=(2,), rating=4, comment="Nümunə məktubların ekran görüntüləri əlavə edilsə, daha yaxşı olardı.")
        complete(araz, trainings[0], 18, rating=5, comment="Yeni əməkdaşlar üçün mütləq tövsiyə edirəm.")
        complete(araz, trainings[2], 5, wrong=(1,), rating=4)
        started = self.at(2, 16, 10)
        TrainingProgress.objects.create(
            user=araz, training=trainings[1], status=TrainingProgress.STATUS_IN_PROGRESS,
            max_position=21, session_started_at=started, last_heartbeat_at=started + timedelta(seconds=21),
            attempts_count=1, first_started_at=started,
        )

    # ------------------------------------------------------------------ loqlar
    def _activity_logs(self, laman, araz):
        visits = {
            "laman.bashirova": [
                ("risk", "Risk Reyestri", "/api/risk/"),
                ("inventory", "İnventar Uçotu", "/api/inventory/"),
                ("activity_logs", "Loqlar", "/api/activity-logs/"),
                ("authentication", "İstifadəçi idarəetməsi", "/api/authentication/organization/users/"),
                ("bulletin", "Elanlar lövhəsi", "/api/bulletin/dashboard/"),
                ("trainings", "Təlimlər", "/api/trainings/materials/"),
                ("operations", "Əməliyyatlar", "/api/operations/"),
            ],
            "araz.mustafa": [
                ("attendance_permissions", "İcazələr", "/api/attendance-permissions/"),
                ("risk", "Risk Reyestri", "/api/risk/"),
                ("inventory", "İnventar Uçotu", "/api/inventory/"),
                ("bulletin", "Elanlar lövhəsi", "/api/bulletin/dashboard/"),
                ("trainings", "Təlimlər", "/api/trainings/materials/"),
            ],
        }
        entries = []

        def add(user, ts, action, description, module=("", ""), path="", method="", status=None, obj=""):
            entries.append((ts, ActivityLog(
                user=user, user_username_snapshot=user.username, action_type=action,
                module_code=module[0], module_title=module[1], description=description, object_repr=obj,
                request_method=method, request_path=path, status_code=status,
                ip_address=IPS[user.username], user_agent=UA,
            )))

        for d in self.workdays(22):
            for user, start_h in ((laman, 9), (araz, 9)):
                if self.rng.random() < 0.12 and d != 0:
                    continue  # məzuniyyət / ezamiyyət günü
                login = self.at(d, start_h, self.rng.randint(0, 25))
                add(user, login, ActivityLog.ACTION_LOGIN, f"{user.username} sistemə daxil oldu",
                    path="/api/authentication/token/", method="POST", status=200)
                ts = login
                for code, title, path in self.rng.sample(visits[user.username], k=self.rng.randint(2, 4)):
                    ts += timedelta(minutes=self.rng.randint(4, 70))
                    add(user, ts, ActivityLog.ACTION_VIEWED, f"{title} moduluna daxil oldu", (code, title), path, "GET", 200)
                if d != 0:
                    out = self.at(d, 18, self.rng.randint(0, 20))
                    add(user, out, ActivityLog.ACTION_LOGOUT, f"{user.username} sistemdən çıxış etdi",
                        path="/api/authentication/logout/", method="POST", status=200)

        # Yaratma / redaktə qeydləri - real obyektlərlə uyğun
        for risk in Risk.objects.select_related("created_by"):
            user = risk.created_by
            add(user, risk.created_at, ActivityLog.ACTION_CREATED,
                f"Risk Reyestri modulunda \"{risk.designation}\" adlı qeydi yaratdı",
                ("risk", "Risk Reyestri"), "/api/risk/", "POST", 201, risk.designation)
            if risk.updated_by_id and risk.updated_at - risk.created_at > timedelta(hours=1):
                add(risk.updated_by, risk.updated_at, ActivityLog.ACTION_UPDATED,
                    f"Risk Reyestri modulunda \"{risk.designation}\" adlı qeydi redaktə etdi",
                    ("risk", "Risk Reyestri"), f"/api/risk/{risk.pk}/", "PATCH", 200, risk.designation)
        for inv in Inventory.objects.select_related("created_by"):
            add(inv.created_by, inv.created_at, ActivityLog.ACTION_CREATED,
                f"İnventar Uçotu modulunda \"{inv.product_name}\" adlı qeydi yaratdı",
                ("inventory", "İnventar Uçotu"), "/api/inventory/", "POST", 201, inv.product_name)
        for post in NewsPost.objects.select_related("created_by"):
            add(post.created_by, post.published_at, ActivityLog.ACTION_CREATED,
                f"Elanlar lövhəsi modulunda \"{post.title}\" adlı qeydi yaratdı",
                ("bulletin", "Elanlar lövhəsi"), "/api/bulletin/news/", "POST", 201, post.title)
        for t in Training.objects.all():
            add(araz, t.created_at, ActivityLog.ACTION_CREATED,
                f"Təlimlər modulunda \"{t.title}\" adlı qeydi yaratdı",
                ("trainings", "Təlimlər"), "/api/trainings/materials/", "POST", 201, t.title)
        for perm in AttendancePermission.objects.all():
            add(laman, perm.created_at, ActivityLog.ACTION_CREATED,
                f"İcazələr modulunda \"{perm}\" adlı qeydi yaratdı",
                ("attendance_permissions", "İcazələr"), "/api/attendance-permissions/", "POST", 201, str(perm))
            if perm.reviewed_at:
                add(araz, perm.reviewed_at, ActivityLog.ACTION_UPDATED,
                    f"İcazələr modulunda \"{perm}\" adlı qeydi redaktə etdi",
                    ("attendance_permissions", "İcazələr"), f"/api/attendance-permissions/{perm.pk}/review/", "POST", 200, str(perm))
        add(laman, self.at(1, 11, 26), ActivityLog.ACTION_EXPORTED, "Risk Reyestri modulunda Excel-ə ixrac etdi",
            ("risk", "Risk Reyestri"), "/api/risk/export/", "GET", 200)

        for ts, entry in sorted(entries, key=lambda x: x[0]):
            if ts > self.now:
                continue
            entry.save()
            ActivityLog.objects.filter(pk=entry.pk).update(timestamp=ts)

    # ------------------------------------------------------------------ bildirişlər
    def _notifications(self, laman, araz):
        rows = []
        for perm in AttendancePermission.objects.all():
            rows.append((araz, Notification.TYPE_ATTENDANCE_PERMISSION_NEW, "Yeni icazə sorğusu",
                         f"Laman Bashirova {perm.date:%d.%m.%Y} tarixi üçün icazə sorğusu göndərdi.",
                         perm.created_at, perm.status != AttendancePermission.STATUS_PENDING, perm.pk))
            if perm.status == AttendancePermission.STATUS_APPROVED:
                rows.append((laman, Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED, "İcazə sorğunuz təsdiqləndi",
                             f"{perm.date:%d.%m.%Y} tarixli icazə sorğunuz Araz Mustafa tərəfindən təsdiqləndi.",
                             perm.reviewed_at, True, perm.pk))
            elif perm.status == AttendancePermission.STATUS_REJECTED:
                rows.append((laman, Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED, "İcazə sorğunuz rədd edildi",
                             f"{perm.date:%d.%m.%Y} tarixli sorğu: {perm.review_comment}",
                             perm.reviewed_at, False, perm.pk))
        for user in (laman, araz):
            rows.append((user, Notification.TYPE_OTHER, "Yeni təlim materialı",
                         "«Məxfi sənədlərlə iş qaydaları» təlimi əlavə edildi.",
                         Training.objects.order_by("-created_at").first().created_at, user == araz, None))
        for user, ntype, title, body, ts, is_read, obj_id in rows:
            n = Notification.objects.create(
                recipient=user, notification_type=ntype, title=title, body=body,
                link="/icazeler" if obj_id else "/telimler/materiallar",
                related_app="attendance_permissions" if obj_id else "trainings",
                related_object_id=obj_id, is_read=is_read, read_at=ts + timedelta(hours=2) if is_read else None,
                created_at=ts,
            )
            Notification.objects.filter(pk=n.pk).update(created_at=ts, updated_at=ts)
