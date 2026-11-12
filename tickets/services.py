"""Ticket sisteminin iş məntiqi: icazələr, status axını, təyinat, bildirişlər."""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from authentication.models import Department, User
from core.models import Module
from notifications.models import Notification
from notifications.services import notify

from .models import (
    Ticket, TicketActivity, TicketAssignee, TicketAttachment, TicketComment, TicketDepartment,
)

logger = logging.getLogger('colored')

MODULE_CODE = 'tickets'
REOPEN_WINDOW_DAYS = 7
AUTO_CLOSE_AFTER_DAYS = 3

S = Ticket

# İcraçı (şöbə əməkdaşı / admin) üçün icazə verilən status keçidləri.
AGENT_TRANSITIONS = {
    S.STATUS_NEW: [S.STATUS_OPEN, S.STATUS_IN_PROGRESS, S.STATUS_WAITING, S.STATUS_RESOLVED, S.STATUS_CANCELED],
    S.STATUS_OPEN: [S.STATUS_IN_PROGRESS, S.STATUS_WAITING, S.STATUS_RESOLVED, S.STATUS_CANCELED],
    S.STATUS_IN_PROGRESS: [S.STATUS_OPEN, S.STATUS_WAITING, S.STATUS_RESOLVED, S.STATUS_CANCELED],
    S.STATUS_WAITING: [S.STATUS_OPEN, S.STATUS_IN_PROGRESS, S.STATUS_RESOLVED, S.STATUS_CANCELED],
    S.STATUS_RESOLVED: [S.STATUS_IN_PROGRESS, S.STATUS_CLOSED],
    S.STATUS_CLOSED: [],
    S.STATUS_CANCELED: [],
}
# Müraciətçi üçün
REQUESTER_TRANSITIONS = {
    S.STATUS_NEW: [S.STATUS_CANCELED],
    S.STATUS_OPEN: [S.STATUS_CANCELED],
    S.STATUS_IN_PROGRESS: [S.STATUS_CANCELED],
    S.STATUS_WAITING: [S.STATUS_CANCELED, S.STATUS_IN_PROGRESS],
    S.STATUS_RESOLVED: [S.STATUS_CLOSED, S.STATUS_IN_PROGRESS],
    S.STATUS_CLOSED: [S.STATUS_IN_PROGRESS],   # yenidən açma (REOPEN_WINDOW_DAYS ərzində)
    S.STATUS_CANCELED: [],
}


# --------------------------------------------------------------------------- icazələr

def is_ticket_admin(user):
    """Superuser və ya 'tickets' modulunun admini - bütün müraciətləri idarə edə bilər."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return Module.objects.filter(code=MODULE_CODE, admin_users=user).exists()


def user_department_ids(user):
    """İstifadəçinin şöbəsi + rəhbəri olduğu şöbələr və onların alt şöbələri."""
    ids = set()
    if user.department_id:
        ids.add(user.department_id)
    managed = list(Department.objects.filter(manager=user).values_list('id', flat=True))
    ids.update(managed)
    if managed:
        ids.update(Department.objects.filter(parent_id__in=managed).values_list('id', flat=True))
    return ids


def visible_queryset(user, qs=None):
    qs = qs if qs is not None else Ticket.objects.all()
    if not user or not user.is_authenticated:
        return qs.none()
    if user.is_superuser:
        return qs
    if is_ticket_admin(user):
        if user.organization_id:
            return qs.filter(Q(organization_id=user.organization_id) | Q(organization__isnull=True))
        return qs
    dept_ids = user_department_ids(user)
    cond = (
        Q(requester=user) | Q(watchers=user) | Q(assignee=user)
        | Q(assignee_links__user=user) | Q(department_links__assignee=user)
    )
    if dept_ids:
        cond |= Q(department_links__department_id__in=dept_ids)
    return qs.filter(cond).distinct()


def is_requester(ticket, user):
    return ticket.requester_id == user.id


def is_agent(ticket, user):
    """Müraciət üzərində işləmə (status, daxili qeyd, təyinat) səlahiyyəti."""
    if is_ticket_admin(user):
        return True
    if ticket.assignee_id == user.id or ticket.assignee_links.filter(user_id=user.id).exists():
        return True
    links = ticket.department_links.all()
    dept_ids = user_department_ids(user)
    return any(l.assignee_id == user.id or l.department_id in dept_ids for l in links)


def can_view(ticket, user):
    return (
        is_requester(ticket, user) or is_agent(ticket, user)
        or ticket.watchers.filter(id=user.id).exists()
    )


def can_assign(ticket, user):
    """Şöbələri dəyişmək: admin, müraciətçi (yalnız 'new' statusunda) və ya təyin olunmuş şöbənin əməkdaşı."""
    if is_ticket_admin(user):
        return True
    if is_agent(ticket, user):
        return True
    return is_requester(ticket, user) and ticket.status == S.STATUS_NEW


def allowed_transitions(ticket, user):
    result = set()
    if is_agent(ticket, user):
        result.update(AGENT_TRANSITIONS.get(ticket.status, []))
    if is_requester(ticket, user):
        for st in REQUESTER_TRANSITIONS.get(ticket.status, []):
            if ticket.status == S.STATUS_CLOSED and not _within_reopen_window(ticket):
                continue
            result.add(st)
    # Bağlanmış müraciəti yalnız admin də yenidən aça bilər
    if ticket.status == S.STATUS_CLOSED and is_ticket_admin(user) and _within_reopen_window(ticket):
        result.add(S.STATUS_IN_PROGRESS)
    order = [c[0] for c in S.STATUS_CHOICES]
    return sorted(result, key=order.index)


def _within_reopen_window(ticket):
    return bool(ticket.closed_at and ticket.closed_at > timezone.now() - timedelta(days=REOPEN_WINDOW_DAYS))


# --------------------------------------------------------------------------- tarixçə və bildiriş

def log_activity(ticket, actor, action, data=None, is_internal=False):
    ticket.last_activity_at = timezone.now()
    Ticket.objects.filter(pk=ticket.pk).update(last_activity_at=ticket.last_activity_at)
    return TicketActivity.objects.create(
        ticket=ticket, actor=actor, action=action, data=data or {}, is_internal=is_internal,
    )


def _department_recipients(department):
    if department.manager_id and department.manager.is_active:
        return [department.manager]
    return list(User.objects.filter(department=department, is_active=True, is_approved=True)[:15])


def ticket_link(ticket):
    return f"/muracietler/{ticket.pk}"


def notify_users(ticket, users, title, body='', actor=None, ntype=Notification.TYPE_TICKET_UPDATE):
    seen = set()
    for u in users:
        if not u or u.id in seen or (actor and u.id == actor.id) or not u.is_active:
            continue
        seen.add(u.id)
        notify(
            u, title=title[:255], body=body[:500], notification_type=ntype,
            link=ticket_link(ticket), related_app='tickets', related_object_id=ticket.pk,
        )


def assignee_users(ticket):
    return [r.user for r in ticket.assignee_links.select_related('user')]


def ticket_participants(ticket, include_internal=True):
    """Müraciətlə bağlı bütün tərəflər (müraciətçi, icraçılar, izləyənlər)."""
    users = [ticket.requester] + assignee_users(ticket)
    users += list(ticket.watchers.all())
    if include_internal:
        for link in ticket.department_links.select_related('assignee'):
            users.append(link.assignee)
    return [u for u in users if u]


def _admin_recipients(ticket):
    users = list(User.objects.filter(is_superuser=True, is_active=True))
    users += list(User.objects.filter(administered_modules__code=MODULE_CODE, is_active=True))
    if ticket.organization_id:
        users = [u for u in users if u.is_superuser or u.organization_id in (None, ticket.organization_id)]
    return users


# --------------------------------------------------------------------------- yaratma / təyinat

def _validate_department(department, ticket_org_id, user):
    if user.is_superuser or is_ticket_admin(user):
        return
    if department.organization_id and ticket_org_id and department.organization_id != ticket_org_id:
        raise ValidationError({'departments': f"'{department.title}' şöbəsi sizin qurumunuza aid deyil."})


@transaction.atomic
def create_ticket(*, user, data, department_ids=None, watcher_ids=None):
    category = data.get('category')
    ticket = Ticket(
        title=data['title'].strip(),
        description=data['description'].strip(),
        ticket_type=data.get('ticket_type') or Ticket.TYPE_INCIDENT,
        category=category,
        priority=data.get('priority') or (category.default_priority if category else Ticket.PRIORITY_MEDIUM),
        tags=data.get('tags') or [],
        requester=user,
        requester_department=user.department,
        organization=user.organization,
        status=Ticket.STATUS_NEW,
    )
    ticket.apply_sla(ticket.created_at)
    ticket.save()
    log_activity(ticket, user, TicketActivity.A_CREATED, {'priority': ticket.priority})

    dept_ids = list(dict.fromkeys(department_ids or []))
    if not dept_ids and category and category.default_department_id:
        dept_ids = [category.default_department_id]
    if dept_ids:
        _set_departments(ticket, user, dept_ids, notify_new=False)

    ticket.watchers.add(user)
    for uid in (watcher_ids or []):
        w = User.objects.filter(id=uid, is_active=True).first()
        if w:
            ticket.watchers.add(w)

    # Bildirişlər: təyin olunan şöbələrin rəhbərləri, yoxdursa adminlər
    recipients = []
    for link in ticket.department_links.select_related('department__manager'):
        recipients += _department_recipients(link.department)
    if not recipients:
        recipients = _admin_recipients(ticket)
    notify_users(
        ticket, recipients, f"Yeni müraciət: {ticket.number}",
        f"{ticket.title} — {user.name}", actor=user, ntype=Notification.TYPE_TICKET_ASSIGNED,
    )
    _record_operation(user, ticket, 'created', f"{ticket.number} müraciəti yaradıldı")
    return ticket


def _record_operation(user, ticket, action, description):
    """Mərkəzi 'Əməliyyatlar' reyestrinə yazır; xəta olarsa əsas əməliyyatı pozmur."""
    try:
        from operations.services import record_crud_operation
        record_crud_operation(
            user=user, action=action, instance=ticket, category_code=MODULE_CODE,
            category_title='Müraciətlər', object_repr=str(ticket), description=description,
            organization=ticket.organization,
        )
    except Exception:  # pragma: no cover
        logger.exception("Ticket əməliyyat qeydi yazıla bilmədi")


@transaction.atomic
def _set_departments(ticket, actor, department_ids, notify_new=True):
    """Şöbə siyahısını verilən siyahıya uyğunlaşdırır (əlavə/çıxar)."""
    depts = {d.id: d for d in Department.objects.filter(id__in=department_ids).select_related('manager')}
    missing = [i for i in department_ids if i not in depts]
    if missing:
        raise ValidationError({'departments': 'Seçilmiş şöbə tapılmadı.'})
    for d in depts.values():
        _validate_department(d, ticket.organization_id, actor)

    existing = {l.department_id: l for l in ticket.department_links.all()}
    added = []
    for dept_id in department_ids:
        if dept_id in existing:
            continue
        link = TicketDepartment.objects.create(
            ticket=ticket, department=depts[dept_id], assigned_by=actor,
            is_primary=not existing and not added,
        )
        added.append(link)
        log_activity(ticket, actor, TicketActivity.A_DEPT_ADDED, {'department': depts[dept_id].title, 'department_id': dept_id})

    for dept_id, link in existing.items():
        if dept_id not in department_ids:
            log_activity(ticket, actor, TicketActivity.A_DEPT_REMOVED, {'department': link.department.title, 'department_id': dept_id})
            link.delete()

    remaining = list(ticket.department_links.all())
    if remaining and not any(l.is_primary for l in remaining):
        remaining[0].is_primary = True
        remaining[0].save(update_fields=['is_primary'])

    if notify_new and added:
        recipients = []
        for link in added:
            recipients += _department_recipients(link.department)
        notify_users(
            ticket, recipients, f"Sizin şöbəyə müraciət təyin edildi: {ticket.number}",
            ticket.title, actor=actor, ntype=Notification.TYPE_TICKET_ASSIGNED,
        )
    return added


def set_departments(ticket, actor, items):
    """items: [{'department': id, 'assignee': id|None, 'note': str}, ...] - tam siyahı."""
    if not can_assign(ticket, actor):
        raise PermissionDenied("Şöbə təyin etmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES:
        raise ValidationError({'detail': 'Bağlanmış müraciətdə şöbə dəyişmək olmaz.'})
    ids = [i['department'] for i in items]
    if not ids:
        raise ValidationError({'departments': 'Ən azı bir şöbə seçilməlidir.'})
    with transaction.atomic():
        _set_departments(ticket, actor, ids)
        for item in items:
            link = ticket.department_links.get(department_id=item['department'])
            changed = []
            if 'note' in item and item['note'] != link.note:
                link.note = item['note'] or ''
                changed.append('note')
            if 'assignee' in item:
                _apply_link_assignee(ticket, actor, link, item['assignee'])
            if changed:
                link.save(update_fields=changed)
    return ticket


def _apply_link_assignee(ticket, actor, link, assignee_id):
    if assignee_id in (None, ''):
        if link.assignee_id:
            link.assignee = None
            link.save(update_fields=['assignee'])
        return
    assignee = User.objects.filter(id=assignee_id, is_active=True).first()
    if not assignee:
        raise ValidationError({'assignee': 'İstifadəçi tapılmadı.'})
    if not is_ticket_admin(actor) and link.department_id not in user_department_ids(assignee):
        raise ValidationError({'assignee': 'İcraçı həmin şöbənin əməkdaşı olmalıdır.'})
    if link.assignee_id != assignee.id:
        link.assignee = assignee
        link.save(update_fields=['assignee'])
        log_activity(ticket, actor, TicketActivity.A_ASSIGNEE, {
            'department': link.department.title, 'assignee': assignee.name, 'assignee_id': assignee.id,
        })
        add_assignee(ticket, actor, assignee, department=link.department, log=False)


def _user_link_for(ticket, user):
    """İstifadəçinin əməkdaşı olduğu (və ya rəhbəri olduğu) təyin olunmuş şöbənin bağlantısı."""
    links = list(ticket.department_links.select_related('department'))
    for l in links:
        if l.department_id == user.department_id:
            return l
    dept_ids = user_department_ids(user)
    for l in links:
        if l.department_id in dept_ids:
            return l
    return None


def is_assignee(ticket, user):
    return ticket.assignee_links.filter(user_id=user.id).exists()


def can_take(ticket, user):
    """Şöbə əməkdaşı (və ya admin) müraciəti özünə götürə bilərmi."""
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        return False
    if is_assignee(ticket, user):
        return False
    return is_ticket_admin(user) or _user_link_for(ticket, user) is not None


def _sync_primary(ticket):
    """Ticket.assignee - ilk icraçı (siyahı, filtr və köhnə API uyğunluğu üçün)."""
    first = ticket.assignee_links.order_by('id').first()
    new_id = first.user_id if first else None
    if ticket.assignee_id != new_id:
        ticket.assignee_id = new_id
        ticket.save(update_fields=['assignee', 'updated_at'])


def _start_ticket(ticket, actor):
    """İcra başlayanda müraciət 'İcradadır' olur, ilk cavab vaxtı yazılır."""
    if ticket.status in (Ticket.STATUS_NEW, Ticket.STATUS_OPEN):
        old = ticket.status
        ticket.status = Ticket.STATUS_IN_PROGRESS
        fields = ['status', 'updated_at']
        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
            fields.append('first_response_at')
        ticket.save(update_fields=fields)
        log_activity(ticket, actor, TicketActivity.A_STATUS, {'from': old, 'to': ticket.status})


def _recompute_link(ticket, actor, department_id):
    """Şöbənin icra statusunu onun icraçılarının statuslarından çıxarır."""
    if not department_id:
        return
    link = ticket.department_links.filter(department_id=department_id).first()
    if not link:
        return
    statuses = list(ticket.assignee_links.filter(department_id=department_id).values_list('status', flat=True))
    if not statuses:
        return
    if all(s == TicketAssignee.STATUS_DONE for s in statuses):
        target = TicketDepartment.STATUS_DONE
    elif any(s in (TicketAssignee.STATUS_IN_PROGRESS, TicketAssignee.STATUS_DONE) for s in statuses):
        target = TicketDepartment.STATUS_IN_PROGRESS
    else:
        return
    if target != link.status:
        set_department_status(ticket, actor, department_id, target)


def _notify_progress(ticket, actor, text):
    notify_users(ticket, [ticket.requester] + list(ticket.watchers.all()),
                 f"{ticket.number}: {text}", ticket.title, actor=actor, ntype=Notification.TYPE_TICKET_UPDATE)


@transaction.atomic
def add_assignee(ticket, actor, user, department=None, self_assigned=False, notify=True, log=True):
    """Müraciətə icraçı əlavə edir. Artıq varsa mövcud sətri qaytarır."""
    existing = ticket.assignee_links.filter(user_id=user.id).first()
    if existing:
        return existing
    if department is None:
        link = _user_link_for(ticket, user)
        department = link.department if link else None
    row = TicketAssignee.objects.create(
        ticket=ticket, user=user, department=department, assigned_by=actor, self_assigned=self_assigned,
        status=TicketAssignee.STATUS_IN_PROGRESS if self_assigned else TicketAssignee.STATUS_ASSIGNED,
        started_at=timezone.now() if self_assigned else None,
    )
    if log:
        log_activity(ticket, actor, TicketActivity.A_ASSIGNEE_ADDED, {
            'assignee': user.name, 'assignee_id': user.id, 'self': self_assigned,
            'department': department.title if department else None,
        })
    _sync_primary(ticket)
    if ticket.status == Ticket.STATUS_NEW:
        ticket.status = Ticket.STATUS_OPEN
        ticket.save(update_fields=['status', 'updated_at'])
    if self_assigned:
        _start_ticket(ticket, actor)
        _recompute_link(ticket, actor, department.id if department else None)
        if notify:
            _notify_progress(ticket, actor, f"{user.name} müraciəti üzərinə götürdü")
    elif notify and user.id != getattr(actor, 'id', None):
        notify_users(
            ticket, [user], f"Müraciət sizə təyin edildi: {ticket.number}", ticket.title,
            actor=actor, ntype=Notification.TYPE_TICKET_ASSIGNED,
        )
    return row


def take_ticket(ticket, user):
    """Şöbə əməkdaşı müraciəti 'özümə götür' edir: icraçı siyahısına düşür, statusu 'İcradadır' olur."""
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        raise ValidationError({'detail': 'Bu statusda müraciəti götürmək olmaz.'})
    row = ticket.assignee_links.filter(user_id=user.id).first()
    if row:
        # artıq təyin olunubsa, "götür" işə başlamaq deməkdir
        if row.status == TicketAssignee.STATUS_ASSIGNED:
            set_assignee_status(ticket, user, TicketAssignee.STATUS_IN_PROGRESS)
            return ticket
        raise ValidationError({'detail': 'Siz artıq bu müraciətin icraçısısınız.'})
    if not can_take(ticket, user):
        raise PermissionDenied("Bu müraciəti yalnız təyin olunmuş şöbənin əməkdaşları götürə bilər.")
    add_assignee(ticket, user, user, self_assigned=True)
    return ticket


@transaction.atomic
def release_assignee(ticket, actor, user_id=None):
    """İcraçını siyahıdan çıxarır (özünü və ya, səlahiyyəti varsa, başqasını)."""
    target_id = user_id or actor.id
    row = ticket.assignee_links.select_related('user').filter(user_id=target_id).first()
    if not row:
        raise ValidationError({'detail': 'Bu istifadəçi müraciətin icraçısı deyil.'})
    if target_id != actor.id and not (is_ticket_admin(actor) or is_agent(ticket, actor)):
        raise PermissionDenied("İcraçını çıxarmaq icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        raise ValidationError({'detail': 'Bu statusda icraçını çıxarmaq olmaz.'})
    department_id = row.department_id
    user = row.user
    row.delete()
    log_activity(ticket, actor, TicketActivity.A_ASSIGNEE_REMOVED, {
        'assignee': user.name, 'assignee_id': user.id, 'self': target_id == actor.id,
    })
    _sync_primary(ticket)
    if not TicketAssignee.objects.filter(ticket=ticket).exists() and ticket.status == Ticket.STATUS_IN_PROGRESS:
        ticket.status = Ticket.STATUS_OPEN
        ticket.save(update_fields=['status', 'updated_at'])
    _recompute_link(ticket, actor, department_id)
    if target_id != actor.id:
        notify_users(ticket, [user], f"Siz {ticket.number} müraciətindən çıxarıldınız", ticket.title,
                     actor=actor, ntype=Notification.TYPE_TICKET_UPDATE)
    return ticket


@transaction.atomic
def set_assignee_status(ticket, actor, status, user_id=None, note=''):
    """İcraçının öz statusunu dəyişir (Təyin olunub / İcradadır / Tamamlayıb)."""
    if status not in dict(TicketAssignee.STATUS_CHOICES):
        raise ValidationError({'status': 'Yanlış status.'})
    target_id = user_id or actor.id
    row = ticket.assignee_links.select_related('user').filter(user_id=target_id).first()
    if not row:
        raise ValidationError({'detail': 'Bu istifadəçi müraciətin icraçısı deyil.'})
    if target_id != actor.id and not is_ticket_admin(actor):
        raise PermissionDenied("Başqasının icra statusunu dəyişmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        raise ValidationError({'detail': 'Bu statusda icra statusunu dəyişmək olmaz.'})
    if row.status == status:
        return ticket
    now = timezone.now()
    row.status = status
    if status == TicketAssignee.STATUS_IN_PROGRESS and not row.started_at:
        row.started_at = now
    row.completed_at = now if status == TicketAssignee.STATUS_DONE else None
    if note:
        row.note = note[:500]
    row.save()
    log_activity(ticket, actor, TicketActivity.A_ASSIGNEE_STATUS, {
        'assignee': row.user.name, 'assignee_id': row.user_id, 'to': status,
    })
    if status in (TicketAssignee.STATUS_IN_PROGRESS, TicketAssignee.STATUS_DONE):
        _start_ticket(ticket, actor)
    _recompute_link(ticket, actor, row.department_id)
    ticket.refresh_from_db()
    if status == TicketAssignee.STATUS_DONE and ticket.status in Ticket.ACTIVE_STATUSES:
        _notify_progress(ticket, actor, f"{row.user.name} öz hissəsini tamamladı")
    return ticket


@transaction.atomic
def set_assignee(ticket, actor, assignee_id):
    """Köhnə uyğunluq API-si: müraciətin icraçısını təkli təyin edir (digərlərini çıxarır).
    Boş dəyər bütün icraçıları təmizləyir."""
    if not is_agent(ticket, actor) and not is_ticket_admin(actor):
        raise PermissionDenied("İcraçı təyin etmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES:
        raise ValidationError({'detail': 'Bağlanmış müraciətdə icraçı dəyişmək olmaz.'})
    new = None
    if assignee_id:
        new = User.objects.filter(id=assignee_id, is_active=True).first()
        if not new:
            raise ValidationError({'assignee': 'İstifadəçi tapılmadı.'})
        linked = {l.department_id for l in ticket.department_links.all()}
        if not is_ticket_admin(actor) and not (user_department_ids(new) & linked):
            raise ValidationError({'assignee': 'İcraçı təyin olunmuş şöbələrdən birinin əməkdaşı olmalıdır.'})
    for row in list(ticket.assignee_links.select_related('user').exclude(user=new) if new else ticket.assignee_links.select_related('user')):
        row.delete()
        log_activity(ticket, actor, TicketActivity.A_ASSIGNEE_REMOVED, {'assignee': row.user.name, 'assignee_id': row.user_id})
    if new:
        add_assignee(ticket, actor, new)
    _sync_primary(ticket)
    return ticket


def add_assignees(ticket, actor, user_ids):
    """Şöbə əməkdaşlarını (və ya admin istənilən istifadəçini) icraçı kimi əlavə edir."""
    if not is_agent(ticket, actor) and not is_ticket_admin(actor):
        raise PermissionDenied("İcraçı təyin etmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        raise ValidationError({'detail': 'Bu statusda icraçı əlavə etmək olmaz.'})
    users = list(User.objects.filter(id__in=user_ids, is_active=True))
    if len(users) != len(set(user_ids)):
        raise ValidationError({'assignees': 'İstifadəçi tapılmadı.'})
    linked = {l.department_id for l in ticket.department_links.all()}
    for u in users:
        if not is_ticket_admin(actor) and not (user_department_ids(u) & linked):
            raise ValidationError({'assignees': f'{u.name} təyin olunmuş şöbələrin əməkdaşı deyil.'})
    for u in users:
        add_assignee(ticket, actor, u, self_assigned=(u.id == actor.id))
    return ticket


# --------------------------------------------------------------------------- status

@transaction.atomic
def change_status(ticket, user, new_status, comment=''):
    if new_status not in dict(Ticket.STATUS_CHOICES):
        raise ValidationError({'status': 'Yanlış status.'})
    if new_status == ticket.status:
        return ticket
    if new_status not in allowed_transitions(ticket, user):
        raise ValidationError({'status': 'Bu statusa keçid mümkün deyil.'})

    old = ticket.status
    now = timezone.now()
    ticket.status = new_status
    fields = ['status', 'updated_at']

    reopened = old in (Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED) and new_status in (
        Ticket.STATUS_IN_PROGRESS, Ticket.STATUS_OPEN)
    if reopened:
        ticket.reopen_count += 1
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.escalated_at = None
        ticket.apply_sla(now)
        fields += ['reopen_count', 'resolved_at', 'closed_at', 'escalated_at',
                   'first_response_due_at', 'due_at']
        # bütün şöbələr yenidən işə qayıdır
        ticket.department_links.filter(status=TicketDepartment.STATUS_DONE).update(
            status=TicketDepartment.STATUS_IN_PROGRESS, completed_at=None)
        ticket.assignee_links.filter(status=TicketAssignee.STATUS_DONE).update(
            status=TicketAssignee.STATUS_IN_PROGRESS, completed_at=None)
    if new_status == Ticket.STATUS_RESOLVED:
        ticket.resolved_at = now
        fields.append('resolved_at')
        if not ticket.first_response_at:
            ticket.first_response_at = now
            fields.append('first_response_at')
    if new_status == Ticket.STATUS_CLOSED:
        ticket.closed_at = now
        fields.append('closed_at')
        if not ticket.resolved_at:
            ticket.resolved_at = now
            fields.append('resolved_at')
    if new_status == Ticket.STATUS_CANCELED:
        ticket.closed_at = now
        fields.append('closed_at')
    if new_status == Ticket.STATUS_IN_PROGRESS and is_agent(ticket, user) and not ticket.first_response_at:
        ticket.first_response_at = now
        fields.append('first_response_at')
    ticket.save(update_fields=list(dict.fromkeys(fields)))

    if new_status == Ticket.STATUS_IN_PROGRESS and not reopened:
        ticket.department_links.filter(status=TicketDepartment.STATUS_PENDING).update(
            status=TicketDepartment.STATUS_IN_PROGRESS)

    log_activity(ticket, user, TicketActivity.A_REOPENED if reopened else TicketActivity.A_STATUS,
                 {'from': old, 'to': new_status})
    if comment and comment.strip():
        add_comment(ticket, user, comment.strip(), is_internal=False, _notify=False)

    status_label = dict(Ticket.STATUS_CHOICES)[new_status]
    if is_requester(ticket, user) and not is_agent(ticket, user):
        recipients = assignee_users(ticket) + [l.assignee for l in ticket.department_links.all()]
        for l in ticket.department_links.select_related('department__manager'):
            if not TicketAssignee.objects.filter(ticket=ticket).exists():
                recipients += _department_recipients(l.department)
    else:
        recipients = [ticket.requester] + list(ticket.watchers.all())
    notify_users(ticket, recipients, f"{ticket.number}: status — {status_label}", ticket.title,
                 actor=user, ntype=Notification.TYPE_TICKET_UPDATE)
    if new_status in (Ticket.STATUS_CLOSED, Ticket.STATUS_CANCELED):
        _record_operation(user, ticket, 'updated', f"{ticket.number} müraciəti — {status_label}")
    return ticket


@transaction.atomic
def set_department_status(ticket, user, department_id, status, note=''):
    link = ticket.department_links.select_related('department').filter(department_id=department_id).first()
    if not link:
        raise ValidationError({'detail': 'Bu şöbə müraciətə təyin olunmayıb.'})
    allowed = is_ticket_admin(user) or link.assignee_id == user.id \
        or link.department_id in user_department_ids(user)
    if not allowed:
        raise PermissionDenied("Bu şöbənin statusunu dəyişmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES or ticket.status == Ticket.STATUS_RESOLVED:
        raise ValidationError({'detail': 'Bu statusda şöbə statusunu dəyişmək olmaz.'})
    if status not in dict(TicketDepartment.STATUS_CHOICES):
        raise ValidationError({'status': 'Yanlış status.'})

    link.status = status
    link.completed_at = timezone.now() if status == TicketDepartment.STATUS_DONE else None
    if note:
        link.note = note[:500]
    link.save()
    log_activity(ticket, user, TicketActivity.A_DEPT_STATUS, {
        'department': link.department.title, 'department_id': department_id, 'to': status,
    })

    if status == TicketDepartment.STATUS_IN_PROGRESS and ticket.status in (Ticket.STATUS_NEW, Ticket.STATUS_OPEN):
        ticket.status = Ticket.STATUS_IN_PROGRESS
        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
        ticket.save(update_fields=['status', 'first_response_at', 'updated_at'])
        log_activity(ticket, user, TicketActivity.A_STATUS, {'from': Ticket.STATUS_OPEN, 'to': ticket.status})

    # bütün şöbələr tamamlayıbsa - müraciət avtomatik 'Həll edildi'
    if status == TicketDepartment.STATUS_DONE and not ticket.department_links.exclude(
            status=TicketDepartment.STATUS_DONE).exists() and ticket.status in Ticket.ACTIVE_STATUSES:
        now = timezone.now()
        old = ticket.status
        ticket.status = Ticket.STATUS_RESOLVED
        ticket.resolved_at = now
        if not ticket.first_response_at:
            ticket.first_response_at = now
        ticket.save(update_fields=['status', 'resolved_at', 'first_response_at', 'updated_at'])
        log_activity(ticket, user, TicketActivity.A_STATUS, {'from': old, 'to': ticket.status, 'auto': True})
        notify_users(ticket, [ticket.requester] + list(ticket.watchers.all()),
                     f"{ticket.number}: bütün şöbələr işi tamamladı", ticket.title,
                     actor=user, ntype=Notification.TYPE_TICKET_UPDATE)
    return ticket


# --------------------------------------------------------------------------- şərh, fayl, digər

@transaction.atomic
def add_comment(ticket, user, body, is_internal=False, _notify=True):
    agent = is_agent(ticket, user)
    if not (agent or is_requester(ticket, user) or ticket.watchers.filter(id=user.id).exists()):
        raise PermissionDenied("Bu müraciətə şərh yazmaq icazəniz yoxdur.")
    if is_internal and not agent:
        raise PermissionDenied("Daxili qeyd yalnız şöbə əməkdaşları tərəfindən yazıla bilər.")
    if ticket.status in Ticket.FINAL_STATUSES:
        raise ValidationError({'detail': 'Bağlanmış müraciətə şərh yazmaq olmaz. Əvvəlcə yenidən açın.'})
    body = (body or '').strip()
    if not body:
        raise ValidationError({'body': 'Şərh boş ola bilməz.'})

    comment = TicketComment.objects.create(ticket=ticket, author=user, body=body, is_internal=is_internal)
    log_activity(ticket, user, TicketActivity.A_COMMENT, {'comment_id': comment.id}, is_internal=is_internal)

    # İlk cavab SLA-sı: icraçının müraciətçiyə açıq cavabı
    if agent and not is_internal and not is_requester(ticket, user) and not ticket.first_response_at:
        ticket.first_response_at = timezone.now()
        ticket.save(update_fields=['first_response_at', 'updated_at'])
    # Müraciətçi 'Cavab gözlənilir' statusunda cavab verirsə - icraya qayıdır
    if is_requester(ticket, user) and ticket.status == Ticket.STATUS_WAITING:
        ticket.status = Ticket.STATUS_IN_PROGRESS
        ticket.save(update_fields=['status', 'updated_at'])
        log_activity(ticket, user, TicketActivity.A_STATUS, {'from': Ticket.STATUS_WAITING, 'to': ticket.status, 'auto': True})

    if _notify:
        if is_internal:
            recipients = assignee_users(ticket) + [l.assignee for l in ticket.department_links.all()]
            recipients += [w for w in ticket.watchers.all() if is_agent(ticket, w)]
        elif is_requester(ticket, user):
            recipients = assignee_users(ticket) + [l.assignee for l in ticket.department_links.all()]
            if not TicketAssignee.objects.filter(ticket=ticket).exists():
                for l in ticket.department_links.select_related('department__manager'):
                    recipients += _department_recipients(l.department)
            recipients += list(ticket.watchers.all())
        else:
            recipients = [ticket.requester] + list(ticket.watchers.all())
        notify_users(ticket, recipients, f"{ticket.number}: yeni {'daxili qeyd' if is_internal else 'şərh'}",
                     body[:200], actor=user, ntype=Notification.TYPE_TICKET_COMMENT)
    return comment


ALLOWED_EXTENSIONS = {
    'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'txt', 'csv', 'doc', 'docx', 'xls', 'xlsx',
    'ppt', 'pptx', 'zip', 'rar', '7z', 'log',
}
MAX_ATTACHMENT_MB = 10
MAX_ATTACHMENTS_PER_TICKET = 30


def add_attachment(ticket, user, uploaded_file, comment=None, is_internal=False):
    if not (is_agent(ticket, user) or is_requester(ticket, user)):
        raise PermissionDenied("Fayl əlavə etmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES:
        raise ValidationError({'detail': 'Bağlanmış müraciətə fayl əlavə etmək olmaz.'})
    name = uploaded_file.name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1][:200]
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError({'file': f"'.{ext}' fayl növünə icazə verilmir."})
    if uploaded_file.size > MAX_ATTACHMENT_MB * 1024 * 1024:
        raise ValidationError({'file': f"Fayl {MAX_ATTACHMENT_MB} MB-dan böyük ola bilməz."})
    if ticket.attachments.count() >= MAX_ATTACHMENTS_PER_TICKET:
        raise ValidationError({'file': 'Bir müraciətə maksimum 30 fayl əlavə oluna bilər.'})
    uploaded_file.name = name
    att = TicketAttachment.objects.create(
        ticket=ticket, comment=comment, file=uploaded_file, original_name=name,
        size=uploaded_file.size, content_type=getattr(uploaded_file, 'content_type', '') or '',
        uploaded_by=user, is_internal=is_internal,
    )
    log_activity(ticket, user, TicketActivity.A_ATTACHMENT, {'name': name}, is_internal=is_internal)
    return att


def update_ticket_fields(ticket, user, validated):
    """Mövzu/təsvir/prioritet/kateqoriya/növ/etiket redaktəsi."""
    agent = is_agent(ticket, user)
    owner_edit = is_requester(ticket, user) and ticket.status == Ticket.STATUS_NEW
    if not (agent or owner_edit):
        raise PermissionDenied("Müraciəti redaktə etmək icazəniz yoxdur.")
    if ticket.status in Ticket.FINAL_STATUSES:
        raise ValidationError({'detail': 'Bağlanmış müraciət redaktə oluna bilməz.'})
    changed = []
    for field in ('title', 'description', 'ticket_type', 'tags'):
        if field in validated and validated[field] != getattr(ticket, field):
            setattr(ticket, field, validated[field])
            changed.append(field)
    if 'category' in validated and validated['category'] != ticket.category:
        old = ticket.category.title if ticket.category else None
        ticket.category = validated['category']
        changed.append('category')
        log_activity(ticket, user, TicketActivity.A_CATEGORY, {
            'from': old, 'to': ticket.category.title if ticket.category else None})
    if 'priority' in validated and validated['priority'] != ticket.priority:
        if not agent and not owner_edit:
            raise PermissionDenied("Prioriteti dəyişmək icazəniz yoxdur.")
        old = ticket.priority
        ticket.priority = validated['priority']
        ticket.apply_sla(ticket.created_at)
        changed += ['priority', 'first_response_due_at', 'due_at']
        log_activity(ticket, user, TicketActivity.A_PRIORITY, {'from': old, 'to': ticket.priority})
        notify_users(ticket, [ticket.requester] + assignee_users(ticket), f"{ticket.number}: prioritet dəyişdi",
                     ticket.get_priority_display(), actor=user, ntype=Notification.TYPE_TICKET_UPDATE)
    if changed:
        ticket.save(update_fields=list(dict.fromkeys(changed + ['updated_at'])))
        if set(changed) & {'title', 'description', 'ticket_type', 'tags'}:
            log_activity(ticket, user, TicketActivity.A_UPDATED, {'fields': [c for c in changed if c in ('title', 'description', 'ticket_type', 'tags')]})
    return ticket


def set_watching(ticket, user, watch=True):
    if not can_view(ticket, user):
        raise PermissionDenied("İcazəniz yoxdur.")
    if watch:
        ticket.watchers.add(user)
    elif ticket.requester_id != user.id:
        ticket.watchers.remove(user)
    return ticket


def add_watchers(ticket, actor, user_ids):
    if not (is_agent(ticket, actor) or is_requester(ticket, actor)):
        raise PermissionDenied("İzləyici əlavə etmək icazəniz yoxdur.")
    added = []
    for u in User.objects.filter(id__in=user_ids, is_active=True):
        if not ticket.watchers.filter(id=u.id).exists():
            ticket.watchers.add(u)
            added.append(u)
            log_activity(ticket, actor, TicketActivity.A_WATCHER, {'added': u.name})
    notify_users(ticket, added, f"Siz {ticket.number} müraciətinin izləyicisi təyin olundunuz",
                 ticket.title, actor=actor, ntype=Notification.TYPE_TICKET_UPDATE)
    return ticket


def rate_ticket(ticket, user, rating, comment=''):
    if not is_requester(ticket, user):
        raise PermissionDenied("Yalnız müraciətçi qiymət verə bilər.")
    if ticket.status not in (Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED):
        raise ValidationError({'detail': 'Qiymət yalnız həll edilmiş müraciətə verilə bilər.'})
    if not 1 <= int(rating) <= 5:
        raise ValidationError({'rating': 'Qiymət 1-5 arası olmalıdır.'})
    ticket.rating = int(rating)
    ticket.rating_comment = (comment or '')[:500]
    ticket.save(update_fields=['rating', 'rating_comment', 'updated_at'])
    log_activity(ticket, user, TicketActivity.A_RATED, {'rating': ticket.rating})
    return ticket


# --------------------------------------------------------------------------- avtomatik işlər

def auto_close_resolved(now=None):
    """Həll edilib, müraciətçi cavab vermədiyi müraciətləri avtomatik bağlayır."""
    now = now or timezone.now()
    limit = now - timedelta(days=AUTO_CLOSE_AFTER_DAYS)
    count = 0
    for t in Ticket.objects.filter(status=Ticket.STATUS_RESOLVED, resolved_at__lt=limit):
        t.status = Ticket.STATUS_CLOSED
        t.closed_at = now
        t.save(update_fields=['status', 'closed_at', 'updated_at'])
        log_activity(t, None, TicketActivity.A_STATUS, {'from': Ticket.STATUS_RESOLVED, 'to': Ticket.STATUS_CLOSED, 'auto': True})
        notify_users(t, [t.requester], f"{t.number} avtomatik bağlandı", t.title,
                     ntype=Notification.TYPE_TICKET_UPDATE)
        count += 1
    return count


def escalate_overdue(now=None):
    """SLA vaxtı keçən aktiv müraciətləri şöbə rəhbərlərinə və adminlərə eskalasiya edir (bir dəfə)."""
    now = now or timezone.now()
    count = 0
    qs = Ticket.objects.filter(
        status__in=Ticket.ACTIVE_STATUSES, due_at__lt=now, escalated_at__isnull=True,
    ).select_related('requester', 'assignee', 'organization')
    for t in qs:
        t.escalated_at = now
        t.save(update_fields=['escalated_at', 'updated_at'])
        log_activity(t, None, TicketActivity.A_ESCALATED, {'due_at': t.due_at.isoformat()})
        recipients = _admin_recipients(t) + [t.assignee]
        for l in t.department_links.select_related('department__manager'):
            if l.department.manager_id:
                recipients.append(l.department.manager)
        notify_users(t, recipients, f"SLA keçdi: {t.number}", t.title,
                     ntype=Notification.TYPE_TICKET_ESCALATED)
        count += 1
    return count
