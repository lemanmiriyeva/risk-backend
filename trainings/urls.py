from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FeedbackStatsViewSet,
    ProgressStatsViewSet,
    QuizAttemptStatsViewSet,
    StatisticsExportView,
    StatisticsSummaryView,
    TrainingPermissionsView,
    TrainingViewSet,
)

app_name = "trainings"

router = DefaultRouter()
router.register("statistics/views", ProgressStatsViewSet, basename="training-stats-views")
router.register("statistics/quiz-results", QuizAttemptStatsViewSet, basename="training-stats-quiz")
router.register("statistics/feedback", FeedbackStatsViewSet, basename="training-stats-feedback")
router.register("materials", TrainingViewSet, basename="training")

urlpatterns = [
    path("permissions/", TrainingPermissionsView.as_view(), name="permissions"),
    path("statistics/summary/", StatisticsSummaryView.as_view(), name="statistics-summary"),
    path("statistics/export/", StatisticsExportView.as_view(), name="statistics-export"),
] + router.urls
