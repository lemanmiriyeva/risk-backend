import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from attendance_permissions.models import AttendancePermission
from attendance_permissions.permissions import get_approval_flow, FLOW_AUTO, FLOW_APPARATUS_ONLY
from risk.models import Risk

from .models import Operation, OperationApprovalStep
from .services import record_crud_operation, start_approval_operation

logger = logging.getLogger('colored')


# ---------------------------------------------------------------------------
# Risk modulu - sadə CRUD nümunəsi (yaratdı / redaktə etdi / sildi)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Risk)
def on_risk_saved(sender, instance, created, **kwargs):
    action = Operation.ACTION_CREATED if created else Operation.ACTION_UPDATED
    user = instance.created_by if created else (instance.updated_by or instance.created_by)
    record_crud_operation(
        user=user,
        action=action,
        instance=instance,
        category_code='risk',
        category_title='Risk Reyestri',
        object_repr=instance.designation,
        description=f"\"{instance.designation}\" adlı risk {'yaradıldı' if created else 'redaktə edildi'}",
        organization=instance.organization,
    )


@receiver(post_delete, sender=Risk)
def on_risk_deleted(sender, instance, **kwargs):
    record_crud_operation(
        user=instance.updated_by or instance.created_by,
        action=Operation.ACTION_DELETED,
        instance=None,  # obyekt artıq silinib - yalnız snapshot saxlanılır
        category_code='risk',
        category_title='Risk Reyestri',
        object_repr=instance.designation,
        description=f"\"{instance.designation}\" adlı risk silindi",
        organization=instance.organization,
    )


# ---------------------------------------------------------------------------
# İcazə (attendance_permissions) modulu - təsdiq tələb edən əməliyyat nümunəsi
# ---------------------------------------------------------------------------

def _get_or_create_permission_operation(instance):
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(AttendancePermission)
    return Operation.objects.filter(
        content_type=content_type, object_id=instance.id, operation_type=Operation.TYPE_APPROVAL,
    ).order_by('-created_at').first()


@receiver(post_save, sender=AttendancePermission)
def on_attendance_permission_saved(sender, instance, created, **kwargs):
    if created:
        # Mərhələ sayı sorğunu yaradanın vəzifə sırasından (Role.order) asılıdır:
        # auto -> 0 mərhələ, apparatus_only -> 1 mərhələ, full -> 2 mərhələ.
        flow = get_approval_flow(instance.user)
        if flow == FLOW_AUTO:
            steps = []
        elif flow == FLOW_APPARATUS_ONLY:
            steps = [{'role_label': 'Aparat rəhbəri'}]
        else:
            steps = [
                {'role_label': 'Şöbə müdiri'},
                {'role_label': 'Aparat rəhbəri'},
            ]
        start_approval_operation(
            user=instance.user,
            instance=instance,
            category_code='attendance_permissions',
            category_title='İcazələr',
            steps=steps,
            object_repr=str(instance),
            description=f"{instance.user.name} - {instance.date} tarixi üçün icazə sorğusu göndərdi",
            organization=instance.organization,
        )
        return

    operation = _get_or_create_permission_operation(instance)
    if not operation:
        return

    status_map = {
        AttendancePermission.STATUS_AWAITING_APPARATUS: Operation.STATUS_IN_PROGRESS,
        AttendancePermission.STATUS_APPROVED: Operation.STATUS_APPROVED,
        AttendancePermission.STATUS_REJECTED: Operation.STATUS_REJECTED,
    }
    new_status = status_map.get(instance.status)
    if not new_status or new_status == operation.status:
        return

    total_steps = operation.total_steps or 0

    # 1-ci mərhələ (şöbə müdiri) nəticələnib - bu mərhələ yalnız tam (2 addımlı) axında mövcuddur
    if total_steps == 2:
        step_1 = operation.approval_steps.filter(step_number=1).first()
        if step_1 and step_1.status == OperationApprovalStep.STATUS_PENDING and instance.department_reviewed_by:
            step_1.status = (
                OperationApprovalStep.STATUS_APPROVED
                if instance.status != AttendancePermission.STATUS_REJECTED
                else OperationApprovalStep.STATUS_REJECTED
            )
            step_1.reviewed_by = instance.department_reviewed_by
            step_1.comment = instance.department_review_comment
            step_1.reviewed_at = instance.department_reviewed_at or timezone.now()
            step_1.save(update_fields=['status', 'reviewed_by', 'comment', 'reviewed_at'])

    # Son mərhələ - Aparat rəhbəri (tam axında 2-ci, birbaşa aparat axınında 1-ci addımdır)
    if instance.status in (AttendancePermission.STATUS_APPROVED, AttendancePermission.STATUS_REJECTED) and instance.reviewed_by:
        final_step = operation.approval_steps.filter(step_number=total_steps).first()
        if final_step and final_step.status == OperationApprovalStep.STATUS_PENDING:
            final_step.status = (
                OperationApprovalStep.STATUS_APPROVED
                if instance.status == AttendancePermission.STATUS_APPROVED
                else OperationApprovalStep.STATUS_REJECTED
            )
            final_step.reviewed_by = instance.reviewed_by
            final_step.comment = instance.review_comment
            final_step.reviewed_at = instance.reviewed_at or timezone.now()
            final_step.save(update_fields=['status', 'reviewed_by', 'comment', 'reviewed_at'])

    operation.status = new_status
    operation.action = Operation.ACTION_REVIEWED
    operation.current_step = total_steps if instance.status == AttendancePermission.STATUS_AWAITING_APPARATUS else operation.current_step
    operation.save(update_fields=['status', 'action', 'current_step'])