from django.db import transaction
from rest_framework import serializers

from .models import (
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    Training,
    TrainingFeedback,
    TrainingProgress,
)
from core.media_urls import media_url


def _abs_url(context, field_file):
    # BACKEND_BASE_URL nəzərə alınır - bax: core/media_urls.py
    return media_url(context.get("request"), field_file)


def _user_info(user):
    if not user:
        return {"id": None, "name": "—", "username": "", "department": None, "organization": None}
    return {
        "id": user.id,
        "name": (user.name or "").strip() or user.username,
        "username": user.username,
        "department": user.department.title if user.department_id else None,
        "organization": user.organization.title if user.organization_id else None,
    }


# --------------------------------------------------------------------------- #
#  Təlim materialı                                                            #
# --------------------------------------------------------------------------- #

class _DefaultTrueBooleanField(serializers.BooleanField):
    """
    multipart/form-data-da göndərilməyən BooleanField DRF-də False sayılır
    (HTML checkbox davranışı). Yeni təlim yaradılanda `is_active` göndərilməsə
    belə aktiv olmalıdır.
    """

    default_empty_html = serializers.empty


class TrainingSerializer(serializers.ModelSerializer):
    is_active = _DefaultTrueBooleanField(required=False, default=True)
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.title", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.name", read_only=True, default=None)
    questions_count = serializers.SerializerMethodField()
    my_progress = serializers.SerializerMethodField()
    my_quiz = serializers.SerializerMethodField()
    my_feedback = serializers.SerializerMethodField()

    class Meta:
        model = Training
        fields = (
            "id", "title", "description",
            "video", "video_url", "thumbnail", "thumbnail_url",
            "duration_seconds", "pass_percent",
            "organization", "organization_name", "is_active",
            "created_by_name", "created_at", "updated_at",
            "questions_count", "my_progress", "my_quiz", "my_feedback",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "video": {"write_only": True, "required": False},
            "thumbnail": {"write_only": True, "required": False},
        }

    def validate(self, attrs):
        if self.instance is None and not attrs.get("video"):
            raise serializers.ValidationError({"video": "Video faylı məcburidir."})
        return attrs

    def get_video_url(self, obj):
        return _abs_url(self.context, obj.video)

    def get_thumbnail_url(self, obj):
        return _abs_url(self.context, obj.thumbnail)

    def get_questions_count(self, obj):
        annotated = getattr(obj, "questions_total", None)
        return annotated if annotated is not None else obj.quiz_questions.count()

    def _progress_map(self):
        return self.context.get("progress_map") or {}

    def get_my_progress(self, obj):
        progress = self._progress_map().get(obj.id)
        if progress is None:
            request = self.context.get("request")
            if request is None or "progress_map" in self.context:
                return None
            progress = TrainingProgress.objects.filter(user=request.user, training=obj).first()
        if not progress:
            return None
        return {
            "status": progress.status,
            "completed_at": progress.completed_at,
            "attempts_count": progress.attempts_count,
        }

    def get_my_quiz(self, obj):
        attempts = (self.context.get("attempts_map") or {}).get(obj.id)
        if attempts is None:
            request = self.context.get("request")
            if request is None or "attempts_map" in self.context:
                return None
            attempts = list(QuizAttempt.objects.filter(user=request.user, training=obj))
        if not attempts:
            return None
        best = max(attempts, key=lambda a: (a.percent, a.submitted_at))
        last = max(attempts, key=lambda a: a.submitted_at)
        return {
            "attempts": len(attempts),
            "best_percent": best.percent,
            "passed": any(a.passed for a in attempts),
            "last_percent": last.percent,
            "last_submitted_at": last.submitted_at,
        }

    def get_my_feedback(self, obj):
        fb = (self.context.get("feedback_map") or {}).get(obj.id)
        if fb is None:
            request = self.context.get("request")
            if request is None or "feedback_map" in self.context:
                return None
            fb = TrainingFeedback.objects.filter(user=request.user, training=obj).first()
        if not fb:
            return None
        return TrainingFeedbackSerializer(fb).data


# --------------------------------------------------------------------------- #
#  Quiz                                                                       #
# --------------------------------------------------------------------------- #

class QuizOptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizOption
        fields = ("id", "text")


class QuizQuestionPublicSerializer(serializers.ModelSerializer):
    """İstifadəçi üçün - düzgün cavab GİZLƏDİLİR."""

    options = QuizOptionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ("id", "text", "options")


class QuizOptionManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizOption
        fields = ("id", "text", "is_correct")
        read_only_fields = ("id",)


class QuizQuestionManageSerializer(serializers.ModelSerializer):
    """Admin üçün - düzgün cavab da göstərilir."""

    options = QuizOptionManageSerializer(many=True)

    class Meta:
        model = QuizQuestion
        fields = ("id", "text", "options")
        read_only_fields = ("id",)


class QuizReplaceSerializer(serializers.Serializer):
    """
    Quiz-i TAM əvəz edir (bütün suallar bir dəfəyə göndərilir). Köhnə nəticələr
    snapshot kimi saxlanıldığı üçün (bax: QuizAnswer) təsirlənmir.
    """

    questions = QuizQuestionManageSerializer(many=True)

    def validate_questions(self, questions):
        for idx, q in enumerate(questions, start=1):
            if not (q.get("text") or "").strip():
                raise serializers.ValidationError(f"{idx}-ci sualın mətni boşdur.")
            options = [o for o in q.get("options", []) if (o.get("text") or "").strip()]
            if len(options) < 2:
                raise serializers.ValidationError(f"{idx}-ci sualın ən azı 2 cavab variantı olmalıdır.")
            correct = [o for o in options if o.get("is_correct")]
            if len(correct) != 1:
                raise serializers.ValidationError(f"{idx}-ci sualda dəqiq 1 düzgün cavab seçilməlidir.")
            q["options"] = options
        return questions

    @transaction.atomic
    def save(self, training):
        training.quiz_questions.all().delete()
        for q_order, q in enumerate(self.validated_data["questions"]):
            question = QuizQuestion.objects.create(
                training=training, text=q["text"].strip(), order=q_order,
            )
            QuizOption.objects.bulk_create([
                QuizOption(
                    question=question, text=o["text"].strip(),
                    is_correct=bool(o.get("is_correct")), order=o_order,
                )
                for o_order, o in enumerate(q["options"])
            ])
        return training


class QuizSubmitSerializer(serializers.Serializer):
    """{"answers": {"<question_id>": <option_id>, ...}}"""

    answers = serializers.DictField(child=serializers.IntegerField())


class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ("id", "question_text", "selected_text", "correct_text", "is_correct")


class QuizAttemptSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    training_title = serializers.CharField(source="training.title", read_only=True)
    pass_percent = serializers.IntegerField(source="training.pass_percent", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            "id", "user", "training", "training_title", "correct_count", "total_count",
            "percent", "passed", "pass_percent", "submitted_at",
        )

    def get_user(self, obj):
        return _user_info(obj.user)


class QuizAttemptDetailSerializer(QuizAttemptSerializer):
    answers = QuizAnswerSerializer(many=True, read_only=True)

    class Meta(QuizAttemptSerializer.Meta):
        fields = QuizAttemptSerializer.Meta.fields + ("answers",)


# --------------------------------------------------------------------------- #
#  Rəy                                                                        #
# --------------------------------------------------------------------------- #

class TrainingFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingFeedback
        fields = ("id", "rating", "comment", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        rating = attrs.get("rating")
        comment = (attrs.get("comment") or "").strip()
        if rating is None and not comment:
            raise serializers.ValidationError("Qiymət seçin və ya rəy yazın.")
        attrs["comment"] = comment
        return attrs


class TrainingFeedbackStatSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    training_title = serializers.CharField(source="training.title", read_only=True)

    class Meta:
        model = TrainingFeedback
        fields = ("id", "user", "training", "training_title", "rating", "comment", "created_at", "updated_at")

    def get_user(self, obj):
        return _user_info(obj.user)


# --------------------------------------------------------------------------- #
#  Baxış statistikası                                                         #
# --------------------------------------------------------------------------- #

class TrainingProgressStatSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    training_title = serializers.CharField(source="training.title", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TrainingProgress
        fields = (
            "id", "user", "training", "training_title", "status", "status_label",
            "attempts_count", "first_started_at", "last_heartbeat_at", "completed_at",
        )

    def get_user(self, obj):
        return _user_info(obj.user)
