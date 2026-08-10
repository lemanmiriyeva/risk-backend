import logging

from django.utils import timezone

from .models import Operation, OperationApprovalStep

logger = logging.getLogger('colored')


def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _resolve_module(category_code):
    if not category_code:
        return None
    from core.models import Module
    return Module.objects.filter(code=category_code).first()


def record_crud_operation(
    *, user, action, instance=None, category_code='', category_title='',
    object_repr='', description='', changes=None, request=None, organization=None,
):
    """
    Sadə CRUD əməliyyatını (yaratdı/redaktə etdi/sildi/ixrac etdi) mərkəzi
    Əməliyyatlar reyestrinə yazır. Status avtomatik 'completed' olur, çünki
    bu əməliyyat bir addımda tamamlanmış sayılır.
    """
    module = _resolve_module(category_code)
    username = getattr(user, 'username', '') or ''

    operation = Operation.objects.create(
        operation_type=Operation.TYPE_CRUD,
        action=action,
        status=Operation.STATUS_COMPLETED,
        module=module,
        category_code=category_code,
        category_title=category_title or (module.title if module else ''),
        user=user if (user and getattr(user, 'is_authenticated', False)) else None,
        user_username_snapshot=username,
        organization=organization or getattr(user, 'organization', None),
        content_object=instance,
        object_repr=object_repr or (str(instance) if instance else ''),
        description=description,
        changes=changes,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )

    logger.info(
        f"[ƏMƏLİYYAT] {username or 'anonim'} - {operation.get_action_display()} "
        f"- kateqoriya={operation.category_title or operation.category_code or '-'} "
        f"- {object_repr or description}"
    )
    return operation


def start_approval_operation(
    *, user, instance, category_code, category_title, steps=None,
    object_repr='', description='', organization=None, request=None,
):
    """
    Təsdiq tələb edən yeni əməliyyat başladır.

    steps: [{"role_label": "Şöbə müdiri", "approver": user_or_None}, ...]
    Mərhələ sayı tamamilə sərbəstdir - hər modul özü müəyyən edir (boş siyahı
    ötürülərsə əməliyyat birbaşa 'approved' statusu ilə tamamlanır).
    """
    steps = steps or []
    module = _resolve_module(category_code)
    username = getattr(user, 'username', '') or ''

    operation = Operation.objects.create(
        operation_type=Operation.TYPE_APPROVAL,
        action=Operation.ACTION_REQUESTED,
        status=Operation.STATUS_PENDING if steps else Operation.STATUS_APPROVED,
        module=module,
        category_code=category_code,
        category_title=category_title or (module.title if module else ''),
        user=user,
        user_username_snapshot=username,
        organization=organization or getattr(user, 'organization', None),
        content_object=instance,
        object_repr=object_repr or (str(instance) if instance else ''),
        description=description,
        total_steps=len(steps) or None,
        current_step=1 if steps else 0,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )

    for idx, step in enumerate(steps, start=1):
        OperationApprovalStep.objects.create(
            operation=operation,
            step_number=idx,
            role_label=step.get('role_label', ''),
            approver=step.get('approver'),
        )

    logger.info(
        f"[ƏMƏLİYYAT] {username or 'anonim'} - yeni təsdiq sorğusu "
        f"- kateqoriya={operation.category_title or operation.category_code or '-'} "
        f"- {object_repr or description}"
    )
    return operation


def advance_approval_step(*, operation, reviewer, action, comment=''):
    """
    Hazırkı mərhələni yekunlaşdırır.
    action: 'approve' | 'reject'
    - approve: sonuncu mərhələdirsə əməliyyat 'approved' olur, deyilsə növbəti
      mərhələyə keçir ('in_progress').
    - reject: proses harada olursa olsun dərhal 'rejected' statusu ilə bağlanır.
    """
    if operation.operation_type != Operation.TYPE_APPROVAL:
        raise ValueError("Yalnız təsdiq tələb edən əməliyyatlar üçün istifadə olunur.")

    step = operation.approval_steps.filter(step_number=operation.current_step).first()
    if not step:
        raise ValueError("Aktiv mərhələ tapılmadı.")

    step.reviewed_by = reviewer
    step.comment = comment
    step.reviewed_at = timezone.now()

    if action == 'approve':
        step.status = OperationApprovalStep.STATUS_APPROVED
        step.save(update_fields=['reviewed_by', 'comment', 'reviewed_at', 'status'])

        if operation.current_step >= (operation.total_steps or operation.current_step):
            operation.status = Operation.STATUS_APPROVED
            operation.action = Operation.ACTION_REVIEWED
            operation.save(update_fields=['status', 'action'])
        else:
            operation.current_step += 1
            operation.status = Operation.STATUS_IN_PROGRESS
            operation.save(update_fields=['status', 'current_step'])
    elif action == 'reject':
        step.status = OperationApprovalStep.STATUS_REJECTED
        step.save(update_fields=['reviewed_by', 'comment', 'reviewed_at', 'status'])

        operation.status = Operation.STATUS_REJECTED
        operation.action = Operation.ACTION_REVIEWED
        operation.save(update_fields=['status', 'action'])
    else:
        raise ValueError("action 'approve' və ya 'reject' olmalıdır.")

    logger.info(
        f"[ƏMƏLİYYAT] {getattr(reviewer, 'username', '')} - mərhələ {step.step_number} "
        f"{step.get_status_display()} - əməliyyat #{operation.id}"
    )
    return operation