from django.contrib import admin

from .models import (
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    Training,
    TrainingFeedback,
    TrainingProgress,
)


class QuizOptionInline(admin.TabularInline):
    model = QuizOption
    extra = 0


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "training", "order")
    list_filter = ("training",)
    inlines = (QuizOptionInline,)


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0
    show_change_link = True


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "duration_seconds", "pass_percent", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("title", "description")
    inlines = (QuizQuestionInline,)


@admin.register(TrainingProgress)
class TrainingProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "training", "status", "attempts_count", "first_started_at", "completed_at")
    list_filter = ("status", "training")
    search_fields = ("user__username", "user__firstname", "user__lastname", "training__title")


class QuizAnswerInline(admin.TabularInline):
    model = QuizAnswer
    extra = 0
    readonly_fields = ("question_text", "selected_text", "correct_text", "is_correct")
    exclude = ("question", "selected_option")
    can_delete = False


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "training", "percent", "passed", "submitted_at")
    list_filter = ("passed", "training")
    search_fields = ("user__username", "user__firstname", "user__lastname", "training__title")
    inlines = (QuizAnswerInline,)


@admin.register(TrainingFeedback)
class TrainingFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "training", "rating", "updated_at")
    list_filter = ("rating", "training")
    search_fields = ("user__username", "comment", "training__title")
