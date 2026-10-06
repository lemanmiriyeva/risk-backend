"""
Sistemi test/nümayiş üçün hazırlayır.

DİQQƏT: bu əmr bütün iş məlumatlarını SİLİR (risklər, inventar, hərəkət tarixçəsi,
icazələr, elanlar, təlimlər, bildirişlər, qurumlar, şöbələr, vəzifələr və
istifadəçilər) və Nazirlik Aparatının real strukturu və əməkdaşları ilə yenidən
doldurur (bax: _msn_staff.py). laman.bashirova hesabı (parolu və 2FA ilə) saxlanılır.
Modullar saxlanılır, «İkinci Modul» silinir.

İstifadə:
    python manage.py seed_demo_data --yes
    python manage.py seed_demo_data --yes --araz-password "YeniParol!2026"

Əməkdaşlar LDAP vasitəsilə domen parolu ilə daxil olur - onlar üçün lokal parol
təyin edilmir. araz.mustafa üçün LDAP olmayan mühitdə yoxlamaq məqsədilə lokal
parol qoyulur.
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
from attendance_permissions.permissions import get_department_manager
from authentication.models import Department, LoginAttempt, Organization, PasswordReset, Role, User
from bulletin.models import BulletinCategory, Circular, NewsPost
from core.models import Module, SubModule
from inventory.models import Inventory, InventoryNumberSequence, InventoryOwnerDepartment, InventoryOwnerPerson
from notifications.models import Notification
from operations.models import Operation, OperationApprovalStep
from risk.models import Risk, RiskLog
from trainings.models import QuizAnswer, QuizAttempt, QuizOption, QuizQuestion, Training, TrainingFeedback, TrainingProgress

from ._msn_staff import (
    APPARATUS_HEAD, DEPARTMENTS, MANAGER_ROLES, ORGANIZATION, ROLE_ORDER, STAFF, SUPERUSERS,
)

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "seed_assets")

KEEP_USERNAME = "laman.bashirova"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
LOG_TITLE = "Hərəkət tarixçəsi"

# Test məlumatlarında aktiv istifadəçilər (loqlar, risklər, inventar və s. bunların adından)
ACTIVE_USERS = [
    "laman.bashirova", "araz.mustafa", "elnur.hasanov", "elvin.ibrahimov", "azer.shukurov",
    "gulnara.karimova", "ulvi.mikailov", "narmin.akhmedova", "aynura.ibrahimova", "azad.aslanov",
]

# ---------------------------------------------------------------------------
# İnventar: (açar, məhsulun adı, sahib növü, sahib - bölmə kodu və ya şəxsin istifadəçi adı)
# ---------------------------------------------------------------------------
INVENTORY = [
    ("server", "Məxfi sənəd dövriyyəsi serveri — Dell PowerEdge R750", "department", "11"),
    ("mail", "Korporativ e-poçt serveri — Microsoft Exchange Server", "department", "11.2"),
    ("backup", "Ehtiyat surətləmə sistemi — Dell PowerProtect DD6400", "department", "11.2"),
    ("firewall", "Şəbəkə təhlükəsizlik divarı — FortiGate 600F", "department", "11.2"),
    ("switch", "Nüvə şəbəkə kommutatoru — Cisco Catalyst 9300", "department", "11.2"),
    ("rack", "Server şkafı və dəqiq kondisioner sistemi", "department", "11.2"),
    ("edms", "Elektron sənəd dövriyyəsi sistemi", "aparat", None),
    ("ups", "Kəsilməz enerji təchizatı qurğusu — APC Smart-UPS SRT 10kVA", "aparat", None),
    ("generator", "Ehtiyat dizel generatoru — 250 kVA", "aparat", None),
    ("acs", "Giriş-nəzarət sistemi (turniketlər və kart oxuyucuları)", "aparat", None),
    ("cctv", "Videomüşahidə sistemi — 64 kanallı NVR", "department", "7.4"),
    ("crypto", "Kriptoqrafik mühafizə vasitəsi (şəbəkə şifrələyicisi)", "department", "12.1"),
    ("alarm", "Arxiv otağının mühafizə siqnalizasiya sistemi", "department", "12.1"),
    ("hr", "Kadr uçotu informasiya sistemi", "department", "9"),
    ("acct", "Mühasibat uçotu proqram təminatı", "department", "7.1"),
    ("dms", "Dövlət müdafiə sifarişlərinin monitorinqi məlumat bazası", "department", "4.1"),
    ("pdm", "Konstruktor sənədləri arxivi (CAD/PDM sistemi)", "department", "4.2"),
    ("eximp", "İdxal-ixrac əməliyyatlarının elektron uçotu sistemi", "department", "3.2"),
    ("printer", "Çoxfunksiyalı printer — Canon imageRUNNER ADVANCE DX C5840i", "department", "10.1"),
    ("projector", "Lazer proyektor — Epson EB-L630U (iclas zalı)", "aparat", None),
    ("laptop", "Noutbuk — Lenovo ThinkPad T14 Gen 4", "person", "araz.mustafa"),
    ("workstation", "İş stansiyası — HP Z4 G5", "person", "laman.bashirova"),
]

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
     INTERNAL_POLICY, "Rüblük", "Uğursuz giriş cəhdləri SIEM vasitəsilə izlənilir; hadisə 1 saat ərzində Dövlət sirrinin mühafizəsi sektoruna bildirilir.",
     "ISO/IEC 27002:2022; NIST SP 800-53 Rev.5 — AC-2, AC-6", "laman.bashirova"),
    ("Fişinq e-poçtları vasitəsilə hesab məlumatlarının ələ keçirilməsi", "mail", 4, 4, 4, "mitigation",
     "E-poçt filtrləri və əməkdaşların maarifləndirilməsi ilə ehtimal azaldılıb; qalıq risk orta.",
     L_INFO, "ISO/IEC 27001:2022 — A.6.3 Maarifləndirmə və təlim, A.8.7 Zərərli proqramlardan müdafiə",
     STRATEGY, "Aylıq", "Şübhəli məktublar İT şöbəsinə yönləndirilir; təsdiqlənmiş hal üzrə hesabın parolu dərhal dəyişdirilir.",
     "NIST CSF 2.0 — PR.AT; NIST SP 800-53 Rev.5 — AT-2", "araz.mustafa"),
    ("Ehtiyat surətlərin bərpa edilə bilməməsi", "backup", 5, 2, 5, "mitigation",
     "Rüblük bərpa sınaqları keçirildikdə qalıq risk aşağı səviyyədədir.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.13 Məlumatların ehtiyat surəti", INTERNAL_POLICY, "Rüblük",
     "Bərpa sınağının uğursuz nəticəsi 24 saat ərzində İT şöbəsinin müdirinə məruzə edilir.",
     "ISO 22301:2019 — Biznesin davamlılığı", "laman.bashirova"),
    ("Şəbəkə təhlükəsizlik divarının proqram təminatında aşkarlanmış boşluq", "firewall", 4, 3, 4, "prevention",
     "İstehsalçının yeniləmələri 72 saat ərzində tətbiq edilir; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.8 Texniki boşluqların idarə edilməsi, A.8.20 Şəbəkə təhlükəsizliyi",
     STRATEGY, "Aylıq", "Kritik boşluq barədə bülletenlər gündəlik izlənilir.",
     "NIST SP 800-53 Rev.5 — SI-2, SC-7", "araz.mustafa"),
    ("Konstruktor sənədlərinin (CAD/PDM) icazəsiz yayılması", "pdm", 5, 2, 5, "prevention",
     "Sənədlərin rəqəmsal su nişanı və çıxarılma nəzarəti tətbiq olunduqdan sonra qalıq risk orta.",
     f"{L_SECRET}; {L_INFO}", "ISO/IEC 27001:2022 — A.5.12 İnformasiyanın təsnifatı, A.8.12 Məlumat sızmasının qarşısının alınması",
     INTERNAL_POLICY, "Yarımillik", "Sızma şübhəsi olduqda Dövlət sirrinin mühafizəsi sektoru dərhal məlumatlandırılır.",
     "AQAP 2110; ISO/IEC 27002:2022", "laman.bashirova"),
    ("Dövlət müdafiə sifarişləri üzrə məxfi məlumatların sızması", "dms", 5, 2, 5, "prevention",
     "Məlumat bazasına giriş yalnız sektor əməkdaşlarına verilib və bütün sorğular jurnallaşdırılır; qalıq risk orta.",
     f"{L_SECRET}; {L_INFO}", "ISO/IEC 27001:2022 — A.5.12 İnformasiyanın təsnifatı, A.8.15 Jurnallaşdırma",
     INTERNAL_POLICY, "Rüblük", "Sızma şübhəsi olduqda Dövlət sirrinin mühafizəsi və səfərbərlik şöbəsi dərhal məlumatlandırılır.",
     "NIST SP 800-53 Rev.5 — AC-3, AU-6", "araz.mustafa"),
    ("Elektrik enerjisinin kəsilməsi nəticəsində server otağının dayanması", "ups", 4, 3, 3, "mitigation",
     "UPS və ehtiyat generator ilə 4 saatlıq fasiləsiz iş təmin edilir; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.7.11 Dəstəkləyici kommunal xidmətlər", INTERNAL_POLICY, "Yarımillik",
     "Enerji kəsilməsi monitorinq sistemi vasitəsilə növbətçi mühəndisə avtomatik bildirilir.",
     "ISO 22301:2019", "laman.bashirova"),
    ("Giriş-nəzarət kartlarının icazəsiz istifadəsi", "acs", 3, 3, 3, "mitigation",
     "Kartlar şəxsi fotoşəkillə təchiz edilib, itirilmiş kartlar dərhal bloklanır.",
     L_SECRET, "ISO/IEC 27001:2022 — A.7.2 Fiziki giriş", INTERNAL_POLICY, "Rüblük",
     "İtirilmiş kart barədə əməkdaş 2 saat ərzində Təsərrüfat və təchizat sektoruna məlumat verməlidir.",
     "ISO/IEC 27002:2022 — 7.2", "araz.mustafa"),
    ("Videomüşahidə yazılarının itirilməsi", "cctv", 3, 2, 3, "mitigation",
     "Yazılar 30 gün müddətində ikinci diskdə təkrarlanır.",
     L_INFO, "ISO/IEC 27001:2022 — A.7.4 Fiziki təhlükəsizliyin monitorinqi", INTERNAL_POLICY, "Yarımillik",
     "Disk nasazlığı barədə xəbərdarlıq avtomatik göndərilir.", "ISO/IEC 27002:2022 — 7.4", "laman.bashirova"),
    ("Kadr uçotu sistemində fərdi məlumatların qanunsuz emalı", "hr", 4, 2, 4, "prevention",
     "Giriş yalnız İnsan resurslarının idarə edilməsi şöbəsinin əməkdaşlarına verilib; qalıq risk aşağı.",
     f"{L_PD}; {L_LABOR}", "ISO/IEC 27001:2022 — A.5.34 Məxfilik və fərdi məlumatların qorunması",
     L_PD, "Yarımillik", "Fərdi məlumatların sızması aşkarlandıqda hüquq şöbəsi dərhal məlumatlandırılır.",
     "ISO/IEC 27701:2019", "araz.mustafa"),
    ("Xidməti noutbukun itməsi və ya oğurlanması", "laptop", 3, 2, 4, "transfer",
     "Avadanlıq sığorta ilə əhatə olunub, disk tam şifrələnib; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.1 İstifadəçi son qurğuları, A.8.24 Kriptoqrafiyanın tətbiqi",
     INTERNAL_POLICY, "İllik", "İtki halında qurğu uzaqdan bloklanır, hadisə 1 saat ərzində qeydə alınır.",
     "NIST SP 800-53 Rev.5 — MP-5, SC-28", "laman.bashirova"),
    ("İdxal-ixrac əməliyyatları üzrə məlumatların icazəsiz dəyişdirilməsi", "eximp", 4, 2, 4, "prevention",
     "Dəyişikliklər iki mərhələli təsdiqlə aparılır və tarixçəsi saxlanılır; qalıq risk aşağı.",
     L_INFO, "ISO/IEC 27001:2022 — A.5.15 Girişə nəzarət, A.8.15 Jurnallaşdırma", INTERNAL_POLICY, "Rüblük",
     "Uyğunsuzluq aşkar edildikdə sənəd dövriyyəsi dayandırılır və Sənayenin tənzimlənməsi şöbəsinə məlumat verilir.",
     "ISO/IEC 27002:2022 — 5.15, 8.15", "araz.mustafa"),
    ("Mühasibat proqram təminatına texniki dəstəyin dayandırılması", "acct", 3, 2, 2, "acceptance",
     "Yeni versiyaya keçid 2027-ci ilin büdcəsinə daxil edilib; risk qəbul edilib.",
     L_INFO, "ISO/IEC 27001:2022 — A.8.32 Dəyişikliklərin idarə edilməsi", "—", "İllik",
     "—", "ISO/IEC 27002:2022", "laman.bashirova"),
    ("Kriptoqrafik açarların düzgün idarə edilməməsi", "crypto", 5, 1, 5, "prevention",
     "Açarlar iki şəxsin iştirakı ilə yaradılır və seyfdə saxlanılır; qalıq risk aşağı.",
     f"{L_SECRET}; {L_ESIGN}", "ISO/IEC 27001:2022 — A.8.24 Kriptoqrafiyanın tətbiqi", INTERNAL_POLICY, "Rüblük",
     "Açarın kompromitasiyası şübhəsi olduqda açar dərhal ləğv edilir.", "NIST SP 800-57", "araz.mustafa"),
    ("Arxiv otağının mühafizə siqnalizasiyasının nasazlığı", "alarm", 4, 2, 5, "mitigation",
     "Sistem iki müstəqil kanal üzrə mühafizə postuna qoşulub; qalıq risk orta.",
     L_SECRET, "ISO/IEC 27001:2022 — A.7.4 Fiziki təhlükəsizliyin monitorinqi", INTERNAL_POLICY, "Aylıq",
     "Nasazlıq zamanı arxiv otağına fiziki mühafizə postu təyin edilir.",
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
     "Şəbəkə idarə edilməsi və texniki dəstək sektoru tərəfindən server otağında kəsilməz enerji təchizatı qurğularının "
     "və ehtiyat surətləmə sisteminin planlı profilaktikası aparılacaq. İş zamanı e-poçt və elektron sənəd "
     "dövriyyəsi sistemində qısamüddətli fasilələr mümkündür.", 27),
    ("sergi", "Beynəlxalq müdafiə sərgisində iştiraka hazırlıq",
     "Beynəlxalq əlaqələr şöbəsi sərgi üzrə işçi qrupunun ilk iclasını keçirib.",
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
    "activity_logs": "İstifadəçi fəaliyyətinin və sistem hadisələrinin tarixçəsi.",
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

# İcazə sorğuları: (istifadəçi, gün əvvəl, başlama, bitmə, yer, səbəb, nəticə, rəy)
#   nəticə: approved | rejected | awaiting | pending
PERMISSIONS = [
    ("elvin.ibrahimov", 16, time(11, 0), time(13, 0), "Dövlət Xidmətlər Agentliyi (ASAN xidmət)",
     "Şəxsiyyət vəsiqəsinin yenilənməsi", "approved", "Razıyam."),
    ("tural.suleymanli", 12, time(15, 30), time(17, 0), "Dövlət Xəzinədarlıq Agentliyi",
     "Hesabatların təqdim edilməsi", "approved", "Təsdiq edirəm."),
    ("kamala.babayeva", 7, time(9, 0), time(10, 30), "Poliklinika", "Tibbi müayinə", "rejected",
     "Həmin saatda sektorun iclası planlaşdırılıb, başqa vaxt seçin."),
    ("gulsum.rzayeva", 5, time(14, 0), time(16, 0), "Xarici İşlər Nazirliyi",
     "Rəsmi nümayəndə heyətinin qəbulu ilə bağlı görüş", "approved", "Razıyam."),
    ("aygun.barkhudarova", 1, time(10, 0), time(12, 0), "Dövlət Gömrük Komitəsi",
     "İxrac sənədlərinin razılaşdırılması", "awaiting", "Razıyam."),
    ("elvin.ibrahimov", -1, time(14, 0), time(16, 0), "Bakı Dövlət Universiteti",
     "Kibertəhlükəsizlik üzrə seminarda iştirak", "pending", ""),
    ("javid.rustamli", -2, time(16, 0), time(18, 0), "Rəqəmsal İnkişaf və Nəqliyyat Nazirliyi",
     "Elektron imza sertifikatının yenilənməsi", "pending", ""),
]


class Command(BaseCommand):
    help = "Bütün iş məlumatlarını sıfırlayır və sistemi Nazirlik Aparatının strukturu ilə doldurur."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Silinməni təsdiqləyir.")
        parser.add_argument("--araz-password", default="Araz@MIS2026",
                            help="araz.mustafa üçün lokal parol (LDAP olmayan mühit üçün).")

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
            self.org, self.deps = self._structure()
            self.users = self._users(laman, options["araz_password"])
            self._attendance_config()
            self._modules()
            invs = self._inventory()
            self._risks(invs)
            self._attendance()
            self._bulletin()
            self._trainings()
            self._activity_logs()
            self._notifications()

        self.stdout.write(self.style.SUCCESS(
            "Hazırdır. İstifadəçi: {}, şöbə/bölmə: {}, inventar: {}, risk: {}, hərəkət: {}, elan: {}, təlim: {}.".format(
                User.objects.count(), Department.objects.count(), Inventory.objects.count(),
                Risk.objects.count(), ActivityLog.objects.count(),
                Circular.objects.count() + NewsPost.objects.count(), Training.objects.count(),
            )
        ))
        self.stdout.write(f"araz.mustafa lokal parolu: {options['araz_password']}")

    # ------------------------------------------------------------------ köməkçilər
    def u(self, username):
        return self.users[username]

    def ip(self, user):
        return f"10.20.{4 + user.pk % 9}.{20 + user.pk % 200}"

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
        # Risklərin silinməsi siqnal vasitəsilə "Sildi" əməliyyatları yaradır - hamısı təmizlənir
        OperationApprovalStep.objects.all().delete()
        Operation.objects.all().delete()

    # ------------------------------------------------------------------ struktur
    def _structure(self):
        org = Organization.objects.create(**ORGANIZATION)
        deps = {}
        for order, (code, title, parent) in enumerate(DEPARTMENTS, start=1):
            deps[code] = Department.objects.create(
                title=title, shortname=code, organization=org, order=order,
                parent=deps[parent] if parent else None, unique_code=f"MSN-{code}",
            )
        return org, deps

    def _role(self, title, department):
        role, _ = Role.objects.get_or_create(
            title=title, department=department,
            defaults={"order": ROLE_ORDER.get(title, 10), "is_manager_role": title in MANAGER_ROLES},
        )
        return role

    # ------------------------------------------------------------------ istifadəçilər
    def _users(self, laman, araz_password):
        users = {}
        for dep_code, role_title, lastname, firstname, gender, email, phone in STAFF:
            username = email.split("@")[0]
            department = self.deps[dep_code] if dep_code else None
            role = self._role(role_title, department) if role_title else None
            fields = dict(
                email=email, firstname=firstname, lastname=lastname, gender=gender,
                organization=self.org, department=department, role=role,
                work_phone_number=phone, is_approved=True, is_active=True,
                is_superuser=username in SUPERUSERS, is_staff=True,
                is_apparatus_head=username == APPARATUS_HEAD, is_org_admin=False,
            )
            if username == laman.username:
                for key, value in fields.items():
                    setattr(laman, key, value)
                laman.save()
                user = laman
            else:
                user = User.objects.create_user(username=username, password=None, **fields)
                if username == "araz.mustafa" and araz_password:
                    user.set_password(araz_password)
                    user.save(update_fields=["password"])
            users[username] = user

        # Şöbə / sektor rəhbərləri (Department.manager)
        for user in users.values():
            if user.role and user.role.title in MANAGER_ROLES and user.department and not user.department.manager_id:
                user.department.manager = user
                user.department.save(update_fields=["manager"])
        return users

    # ------------------------------------------------------------------ icazə konfiqurasiyası
    def _attendance_config(self):
        AttendancePermissionOrganizationConfig.objects.create(
            organization=self.org, apparatus_head_enabled=True, apparatus_head=self.u(APPARATUS_HEAD),
        )
        for dep in self.deps.values():
            dep.refresh_from_db()
            has_manager = get_department_manager(dep) is not None
            AttendancePermissionDepartmentConfig.objects.create(
                organization=self.org, department=dep, manager_enabled=has_manager,
                no_manager_fallback=(AttendancePermissionDepartmentConfig.FALLBACK_REPLACEMENT if has_manager
                                     else AttendancePermissionDepartmentConfig.FALLBACK_APPARATUS),
            )

    # ------------------------------------------------------------------ modullar
    def _modules(self):
        Module.objects.filter(code="ikinci_modul").delete()
        Module.objects.filter(code="activity_logs").update(title=LOG_TITLE)
        for code, text in MODULE_DESCRIPTIONS.items():
            Module.objects.filter(code=code, description__in=["", None]).update(description=text)
        for code, text in SUB_MODULE_DESCRIPTIONS.items():
            SubModule.objects.filter(code=code, description__in=["", None]).update(description=text)
        SubModule.objects.filter(code="config").update(
            title="Konfiqurasiya",
            description="Aparat rəhbəri və şöbə müdirləri üzrə təsdiq axınının tənzimlənməsi.",
        )

        # Bütün modullar və alt modullar Nazirliyə açılır («Qurum girişləri»)
        for module in Module.objects.all():
            module.permitted_organizations.add(self.org)
        for sub in SubModule.objects.all():
            sub.permitted_organizations.add(self.org)

        everyone = [u for u in self.users.values() if not u.is_superuser]
        by_dep = lambda *codes: [u for u in everyone if u.department and (
            u.department.shortname in codes or (u.department.parent_id and u.department.parent.shortname in codes))]

        def grant(code, users, admins=(), sub=False):
            model = SubModule if sub else Module
            obj = model.objects.filter(code=code).first()
            if not obj:
                return
            obj.permitted_users.add(*users)
            if admins:
                obj.admin_users.add(*admins)

        # Hamı üçün: icazələr, elanlar lövhəsi, təlim materialları
        grant("icazeler", everyone)
        grant("bulletin", everyone, admins=by_dep("15") + [self.u("aynura.ibrahimova")])
        grant("trainings", everyone, admins=[self.u("nigar.mammadova")])
        grant("training_materials", everyone, sub=True)
        grant("training_statistics", [self.u("azad.aslanov"), self.u("nigar.mammadova")],
              admins=[self.u("azad.aslanov")], sub=True)
        # Risklər: İT və Dövlət sirrinin mühafizəsi şöbələri
        risk_users = by_dep("11", "12")
        grant("risk", risk_users)
        for code in ("risk_register", "risk_view_table", "risk_log"):
            grant(code, risk_users, sub=True)
        # İnventar: İT şöbəsi və Dövlət əmlakının uçotu sektoru
        grant("inventory", by_dep("11", "7.2"))

    # ------------------------------------------------------------------ inventar
    def _inventory(self):
        invs = {}
        days = 75
        creators = [self.u("ulvi.mikailov"), self.u("elvin.ibrahimov"), self.u("araz.mustafa")]
        for idx, (key, name, owner_type, owner) in enumerate(INVENTORY):
            kwargs = {"product_name": name, "owner_type": owner_type}
            if owner_type == "department":
                kwargs["owner_department"], _ = InventoryOwnerDepartment.objects.get_or_create(name=self.deps[owner].title)
            elif owner_type == "person":
                kwargs["owner_person"], _ = InventoryOwnerPerson.objects.get_or_create(full_name=self.u(owner).name)
            creator = creators[idx % len(creators)]
            inv = Inventory.objects.create(created_by=creator, updated_by=creator, **kwargs)
            created = self.at(days, 10 + idx % 6, 5 + (idx * 7) % 50)
            Inventory.objects.filter(pk=inv.pk).update(created_at=created, updated_at=created)
            days -= 2
            invs[key] = inv
        return invs

    # ------------------------------------------------------------------ risklər
    def _risks(self, invs):
        from risk import services as risk_services

        creators = [self.u(n) for n in ("laman.bashirova", "elnur.hasanov", "araz.mustafa", "elvin.ibrahimov", "gulnara.karimova")]
        risk_ct = ContentType.objects.get_for_model(Risk)
        days = 44
        for idx, row in enumerate(RISKS):
            (designation, inv_key, h, m, n, treatment, residual, legal, intl, national,
             freq, incident, standards, _creator) = row
            creator = creators[idx % len(creators)]
            inv = invs[inv_key]
            risk = Risk.objects.create(
                designation=designation, inventory=inv, organization=self.org,
                asset_value=h, probability=m, impact=n, treatment_option=treatment,
                residual_risk=residual, legal_basis=legal, international_framework=intl,
                national_legal_reference=national, update_frequency=freq,
                incident_notification_notes=incident, standard_references=standards,
                created_by=creator, updated_by=creator,
            )
            created = self.at(days, 10 + idx % 7, (idx * 13) % 60)
            risk_services.log_created(risk, creator)
            RiskLog.objects.filter(risk=risk).update(timestamp=created, ip_address=self.ip(creator), user_agent=UA)
            Operation.objects.filter(content_type=risk_ct, object_id=risk.pk).update(
                created_at=created, updated_at=created, ip_address=self.ip(creator), user_agent=UA)
            final_time = created

            # Bəzi risklər sonradan yenidən qiymətləndirilib
            if idx % 4 == 1:
                editor = self.u("araz.mustafa") if creator.username != "araz.mustafa" else self.u("laman.bashirova")
                old = copy.copy(risk)
                risk.probability = max(1, risk.probability - 1)
                risk.residual_risk = residual + " Əlavə nəzarət tədbirləri tətbiq edilib."
                risk.updated_by = editor
                risk.save()
                risk_services.log_updated(old, risk, editor)
                edited = created + timedelta(days=3, hours=2)
                RiskLog.objects.filter(risk=risk, action_type=RiskLog.ACTION_UPDATED).update(
                    timestamp=edited, ip_address=self.ip(editor), user_agent=UA)
                Operation.objects.filter(content_type=risk_ct, object_id=risk.pk, action=Operation.ACTION_UPDATED).update(
                    created_at=edited, updated_at=edited, ip_address=self.ip(editor), user_agent=UA)
                final_time = edited
            Risk.objects.filter(pk=risk.pk).update(created_at=created, updated_at=final_time)
            days -= 2

        # Siyahıya baxış və Excel ixracı qeydləri
        for d, name in ((9, "laman.bashirova"), (4, "araz.mustafa"), (1, "gulnara.karimova")):
            user = self.u(name)
            risk_services.log_viewed_list(user, Risk.objects.count())
            RiskLog.objects.filter(timestamp__gte=self.now - timedelta(minutes=5)).update(
                timestamp=self.at(d, 11, 20), ip_address=self.ip(user), user_agent=UA)
        laman = self.u("laman.bashirova")
        risk_services.log_exported(laman, "risk_list", Risk.objects.count())
        RiskLog.objects.filter(action_type=RiskLog.ACTION_EXPORTED).update(
            timestamp=self.at(1, 11, 26), ip_address=self.ip(laman), user_agent=UA)

    # ------------------------------------------------------------------ icazələr
    def _attendance(self):
        apparatus = self.u(APPARATUS_HEAD)
        ap_ct = ContentType.objects.get_for_model(AttendancePermission)
        self.permission_events = []
        for username, days_ago, start, end, location, reason, outcome, comment in PERMISSIONS:
            user = self.u(username)
            created = self.at(max(days_ago, 0) + 2, 9, 40)
            perm = AttendancePermission.objects.create(
                user=user, date=(self.now - timedelta(days=days_ago)).date(),
                start_time=start, end_time=end, location=location, reason=reason,
            )
            op = Operation.objects.filter(content_type=ap_ct, object_id=perm.pk).first()
            two_step = (op.total_steps or 0) == 2
            manager = get_department_manager(user.department) if two_step else None
            stage1 = created + timedelta(hours=1, minutes=10)
            stage2 = stage1 + timedelta(hours=2, minutes=5)

            if outcome == "pending":
                self.permission_events.append((perm, manager or apparatus, None))
            elif outcome == "awaiting":
                perm.department_reviewed_by, perm.department_reviewed_at = manager, stage1
                perm.department_review_comment = comment
                perm.status = AttendancePermission.STATUS_AWAITING_APPARATUS
                perm.save()
                self.permission_events.append((perm, manager, stage1))
            elif outcome == "rejected":
                reviewer = manager or apparatus
                if two_step:
                    perm.department_reviewed_by, perm.department_reviewed_at = reviewer, stage1
                    perm.department_review_comment = comment
                perm.reviewed_by, perm.reviewed_at, perm.review_comment = reviewer, stage1, comment
                perm.status = AttendancePermission.STATUS_REJECTED
                perm.save()
                self.permission_events.append((perm, reviewer, stage1))
            else:  # approved
                if two_step:
                    perm.department_reviewed_by, perm.department_reviewed_at = manager, stage1
                    perm.department_review_comment = comment
                    perm.status = AttendancePermission.STATUS_AWAITING_APPARATUS
                    perm.save()
                    self.permission_events.append((perm, manager, stage1))
                perm.reviewed_by, perm.reviewed_at, perm.review_comment = apparatus, stage2, "Təsdiq edirəm."
                perm.status = AttendancePermission.STATUS_APPROVED
                perm.save()
                self.permission_events.append((perm, apparatus, stage2))

            AttendancePermission.objects.filter(pk=perm.pk).update(created_at=created, updated_at=created)
            ops = Operation.objects.filter(content_type=ap_ct, object_id=perm.pk)
            ops.update(created_at=created, updated_at=created, ip_address=self.ip(user), user_agent=UA)
            OperationApprovalStep.objects.filter(operation__in=ops).update(created_at=created, updated_at=created)
            for step in OperationApprovalStep.objects.filter(operation__in=ops, reviewed_at__isnull=False):
                step.reviewed_at = stage1 if step.step_number == 1 and two_step else (
                    stage2 if outcome == "approved" else stage1)
                step.save(update_fields=["reviewed_at"])

    # ------------------------------------------------------------------ elanlar
    def _bulletin(self):
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
        doc_authors = [self.u("aynura.ibrahimova"), self.u("hajar.rustamova")]
        for i, (key, title, number, when) in enumerate(CIRCULARS):
            if isinstance(when, tuple):
                doc_date = datetime(*when).date()
            elif isinstance(when, int):
                doc_date = (self.now + timedelta(days=when)).date()
            else:
                doc_date = None
            c = Circular.objects.create(
                category=BulletinCategory.objects.get(key=key), title=title, number=number,
                document_date=doc_date, created_by=doc_authors[i % 2],
            )
            ts = self.at(abs(when) if isinstance(when, int) else 50, 12, 10)
            Circular.objects.filter(pk=c.pk).update(created_at=ts, updated_at=ts)

        news_authors = [self.u("narmin.akhmedova"), self.u("ayishan.mamedova")]
        for i, (slug, title, summary, body, days_ago) in enumerate(NEWS):
            published = self.at(days_ago, 10, 30)
            post = NewsPost(title=title, summary=summary, body=body, published_at=published,
                            created_by=news_authors[i % 2])
            with open(os.path.join(ASSETS, "news", f"{slug}.jpg"), "rb") as fh:
                post.image.save(f"{slug}.jpg", File(fh), save=False)
            post.save()
            NewsPost.objects.filter(pk=post.pk).update(created_at=published, updated_at=published)

    # ------------------------------------------------------------------ təlimlər
    def _trainings(self):
        author = self.u("nigar.mammadova")
        trainings = []
        for i, (slug, title, description, questions) in enumerate(TRAININGS):
            t = Training(title=title, description=description, duration_seconds=45, pass_percent=60, created_by=author)
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

        def complete(username, training, days_ago, wrong=(), rating=None, comment=""):
            user = self.u(username)
            started = self.at(days_ago, 14, 5 + len(username) % 40)
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
                ts = done + timedelta(minutes=4)
                TrainingFeedback.objects.filter(pk=fb.pk).update(created_at=ts, updated_at=ts)

        def partial(username, training, days_ago, seconds):
            started = self.at(days_ago, 16, 10)
            TrainingProgress.objects.create(
                user=self.u(username), training=training, status=TrainingProgress.STATUS_IN_PROGRESS,
                max_position=seconds, session_started_at=started, last_heartbeat_at=started + timedelta(seconds=seconds),
                attempts_count=1, first_started_at=started,
            )

        t1, t2, t3 = trainings
        complete("laman.bashirova", t1, 19, rating=5, comment="Material qısa və aydındır.")
        complete("araz.mustafa", t1, 18, rating=5)
        complete("elvin.ibrahimov", t1, 17, wrong=(1,), rating=4)
        complete("elnur.hasanov", t1, 16)
        complete("kamala.babayeva", t1, 15, rating=4)
        complete("gulnara.karimova", t3, 10, rating=5)
        complete("akif.mammadov", t3, 9, wrong=(2,))
        complete("laman.bashirova", t2, 8, wrong=(2,), rating=4)
        complete("azer.shukurov", t2, 6)
        complete("ilkin.bayramli", t2, 4, wrong=(0, 1))
        partial("araz.mustafa", t2, 2, 21)
        partial("tural.suleymanli", t1, 3, 12)
        partial("aytan.fatullabayli", t3, 1, 30)

    # ------------------------------------------------------------------ hərəkət tarixçəsi
    def _activity_logs(self):
        modules = {
            "risk": ("risk", "Risk Reyestri", "/api/risk/"),
            "inventory": ("inventory", "İnventar Uçotu", "/api/inventory/"),
            "logs": ("activity_logs", LOG_TITLE, "/api/activity-logs/"),
            "auth": ("authentication", "İstifadəçi idarəetməsi", "/api/authentication/organization/users/"),
            "bulletin": ("bulletin", "Elanlar lövhəsi", "/api/bulletin/dashboard/"),
            "trainings": ("trainings", "Təlimlər", "/api/trainings/materials/"),
            "operations": ("operations", "Əməliyyatlar", "/api/operations/"),
            "permissions": ("attendance_permissions", "İcazələr", "/api/attendance-permissions/"),
        }
        visits = {
            "laman.bashirova": ["risk", "inventory", "logs", "auth", "bulletin", "trainings", "operations"],
            "araz.mustafa": ["permissions", "risk", "inventory", "logs", "bulletin", "operations"],
            "elnur.hasanov": ["risk", "inventory", "bulletin", "trainings", "permissions"],
            "elvin.ibrahimov": ["risk", "inventory", "permissions", "bulletin"],
            "azer.shukurov": ["risk", "bulletin", "trainings"],
            "gulnara.karimova": ["risk", "bulletin", "permissions"],
            "ulvi.mikailov": ["inventory", "bulletin", "permissions"],
            "narmin.akhmedova": ["bulletin", "permissions", "trainings"],
            "aynura.ibrahimova": ["bulletin", "permissions"],
            "azad.aslanov": ["trainings", "permissions", "bulletin"],
        }
        entries = []

        def add(user, ts, action, description, module=("", "", ""), method="", status=None, obj="", path=None):
            entries.append((ts, ActivityLog(
                user=user, user_username_snapshot=user.username, action_type=action,
                module_code=module[0], module_title=module[1], description=description, object_repr=obj,
                request_method=method, request_path=path or module[2], status_code=status,
                ip_address=self.ip(user), user_agent=UA,
            )))

        for d in self.workdays(22):
            for username in ACTIVE_USERS:
                user = self.u(username)
                if self.rng.random() < 0.15 and d != 0:
                    continue  # məzuniyyət / ezamiyyət günü
                login = self.at(d, 9, self.rng.randint(0, 40))
                add(user, login, ActivityLog.ACTION_LOGIN, f"{user.username} sistemə daxil oldu",
                    method="POST", status=200, path="/api/authentication/token/")
                ts = login
                choices = visits[username]
                for key in self.rng.sample(choices, k=min(len(choices), self.rng.randint(1, 3))):
                    ts += timedelta(minutes=self.rng.randint(4, 90))
                    m = modules[key]
                    add(user, ts, ActivityLog.ACTION_VIEWED, f"{m[1]} moduluna daxil oldu", m, "GET", 200)
                if d != 0:
                    out = self.at(d, 18, self.rng.randint(0, 25))
                    add(user, out, ActivityLog.ACTION_LOGOUT, f"{user.username} sistemdən çıxış etdi",
                        method="POST", status=200, path="/api/authentication/logout/")

        # Yaratma / redaktə qeydləri - real obyektlərlə uyğun
        for risk in Risk.objects.select_related("created_by", "updated_by"):
            add(risk.created_by, risk.created_at, ActivityLog.ACTION_CREATED,
                f"Risk Reyestri modulunda \"{risk.designation}\" adlı qeydi yaratdı",
                modules["risk"], "POST", 201, risk.designation)
            if risk.updated_by_id and risk.updated_at - risk.created_at > timedelta(hours=1):
                add(risk.updated_by, risk.updated_at, ActivityLog.ACTION_UPDATED,
                    f"Risk Reyestri modulunda \"{risk.designation}\" adlı qeydi redaktə etdi",
                    modules["risk"], "PATCH", 200, risk.designation, path=f"/api/risk/{risk.pk}/")
        for inv in Inventory.objects.select_related("created_by"):
            add(inv.created_by, inv.created_at, ActivityLog.ACTION_CREATED,
                f"İnventar Uçotu modulunda \"{inv.product_name}\" adlı qeydi yaratdı",
                modules["inventory"], "POST", 201, inv.product_name)
        for post in NewsPost.objects.select_related("created_by"):
            add(post.created_by, post.published_at, ActivityLog.ACTION_CREATED,
                f"Elanlar lövhəsi modulunda \"{post.title}\" adlı qeydi yaratdı",
                modules["bulletin"], "POST", 201, post.title, path="/api/bulletin/news/")
        for t in Training.objects.select_related("created_by"):
            add(t.created_by, t.created_at, ActivityLog.ACTION_CREATED,
                f"Təlimlər modulunda \"{t.title}\" adlı qeydi yaratdı",
                modules["trainings"], "POST", 201, t.title)
        for perm in AttendancePermission.objects.select_related("user"):
            add(perm.user, perm.created_at, ActivityLog.ACTION_CREATED,
                f"İcazələr modulunda \"{perm}\" adlı qeydi yaratdı",
                modules["permissions"], "POST", 201, str(perm))
        for perm, reviewer, ts in self.permission_events:
            if ts:
                add(reviewer, ts, ActivityLog.ACTION_UPDATED,
                    f"İcazələr modulunda \"{perm}\" adlı qeydi redaktə etdi",
                    modules["permissions"], "POST", 200, str(perm),
                    path=f"/api/attendance-permissions/{perm.pk}/review/")
        laman = self.u("laman.bashirova")
        add(laman, self.at(1, 11, 26), ActivityLog.ACTION_EXPORTED, "Risk Reyestri modulunda Excel-ə ixrac etdi",
            modules["risk"], "GET", 200, path="/api/risk/export/")

        for ts, entry in sorted(entries, key=lambda x: x[0]):
            if ts > self.now:
                continue
            entry.save()
            ActivityLog.objects.filter(pk=entry.pk).update(timestamp=ts)

    # ------------------------------------------------------------------ bildirişlər
    def _notifications(self):
        rows = []
        for perm, reviewer, ts in self.permission_events:
            perm.refresh_from_db()
            name = perm.user.name
            if ts is None:
                rows.append((reviewer, Notification.TYPE_ATTENDANCE_PERMISSION_NEW, "Yeni icazə sorğusu",
                             f"{name} {perm.date:%d.%m.%Y} tarixi üçün icazə sorğusu göndərdi.",
                             perm.created_at, False, perm.pk))
                continue
            rows.append((reviewer, Notification.TYPE_ATTENDANCE_PERMISSION_NEW, "Yeni icazə sorğusu",
                         f"{name} {perm.date:%d.%m.%Y} tarixi üçün icazə sorğusu göndərdi.",
                         ts - timedelta(hours=1), True, perm.pk))
            if perm.status == AttendancePermission.STATUS_APPROVED and reviewer == perm.reviewed_by:
                rows.append((perm.user, Notification.TYPE_ATTENDANCE_PERMISSION_APPROVED, "İcazə sorğunuz təsdiqləndi",
                             f"{perm.date:%d.%m.%Y} tarixli icazə sorğunuz təsdiqləndi.", ts, True, perm.pk))
            elif perm.status == AttendancePermission.STATUS_REJECTED:
                rows.append((perm.user, Notification.TYPE_ATTENDANCE_PERMISSION_REJECTED, "İcazə sorğunuz rədd edildi",
                             f"{perm.date:%d.%m.%Y} tarixli sorğu: {perm.review_comment}", ts, False, perm.pk))
            elif perm.status == AttendancePermission.STATUS_AWAITING_APPARATUS:
                rows.append((self.u(APPARATUS_HEAD), Notification.TYPE_ATTENDANCE_PERMISSION_DEPT_APPROVED,
                             "Təsdiq gözləyən icazə sorğusu",
                             f"{name} - {perm.date:%d.%m.%Y} tarixli sorğu şöbə müdiri tərəfindən təsdiqlənib.",
                             ts, False, perm.pk))
        latest = Training.objects.order_by("-created_at").first()
        for name in ("laman.bashirova", "araz.mustafa"):
            rows.append((self.u(name), Notification.TYPE_OTHER, "Yeni təlim materialı",
                         f"«{latest.title}» təlimi əlavə edildi.", latest.created_at, name == "araz.mustafa", None))
        for user, ntype, title, body, ts, is_read, obj_id in rows:
            n = Notification.objects.create(
                recipient=user, notification_type=ntype, title=title, body=body,
                link="/icazeler" if obj_id else "/telimler/materiallar",
                related_app="attendance_permissions" if obj_id else "trainings",
                related_object_id=obj_id, is_read=is_read, read_at=ts + timedelta(hours=2) if is_read else None,
                created_at=ts,
            )
            Notification.objects.filter(pk=n.pk).update(created_at=ts, updated_at=ts)
