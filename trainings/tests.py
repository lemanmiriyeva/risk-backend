from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Organization, User
from core.models import Module, SubModule
from .models import QuizAttempt, Training, TrainingProgress

import tempfile

MEDIA = tempfile.mkdtemp()


def make_user(username, org, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@x.az", password="x",
        firstname=username.title(), lastname="Test", organization=org,
        two_fa_confirmed=True, is_approved=True, **extra,
    )


@override_settings(MEDIA_ROOT=MEDIA)
class TrainingsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(title="Qurum A")
        self.module = Module.objects.create(code="trainings", title="Təlimlər", url_endpoint="telimler")
        self.module.permitted_organizations.add(self.org)
        self.materials = SubModule.objects.create(
            module=self.module, code="training_materials", title="Təlim materialları", url_endpoint="materiallar")
        self.stats = SubModule.objects.create(
            module=self.module, code="training_statistics", title="Təlim statistikası", url_endpoint="statistika")
        for sm in (self.materials, self.stats):
            sm.permitted_organizations.add(self.org)

        self.viewer = make_user("viewer", self.org)
        self.mat_admin = make_user("matadmin", self.org)
        self.stat_admin = make_user("statadmin", self.org)
        self.outsider = make_user("outsider", self.org)
        # outsider-ə başqa bir modula giriş verək ki, HasSystemAccess keçsin, amma Təlimlərə yox
        other = Module.objects.create(code="other", title="Other", url_endpoint="other")
        other.permitted_users.add(self.outsider)

        for u in (self.viewer, self.mat_admin, self.stat_admin):
            self.module.permitted_users.add(u)
        self.materials.permitted_users.add(self.viewer)
        self.materials.admin_users.add(self.mat_admin)
        self.stats.admin_users.add(self.stat_admin)

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def create_training(self, duration=100):
        c = self.client_for(self.mat_admin)
        res = c.post("/api/trainings/materials/", {
            "title": "Yanğın təhlükəsizliyi",
            "video": SimpleUploadedFile("v.mp4", b"0" * 100, content_type="video/mp4"),
            "duration_seconds": duration,
        }, format="multipart")
        self.assertEqual(res.status_code, 201, res.content)
        return Training.objects.get(id=res.data["id"])

    def set_quiz(self, training):
        c = self.client_for(self.mat_admin)
        res = c.put(f"/api/trainings/materials/{training.id}/quiz/", {"questions": [
            {"text": "2+2?", "options": [{"text": "4", "is_correct": True}, {"text": "5"}]},
            {"text": "Rəng?", "options": [{"text": "Qırmızı", "is_correct": True}, {"text": "Yaşıl"}]},
        ]}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        return res.data["questions"]

    # --- icazələr -----------------------------------------------------------

    def test_permissions_are_separate_per_sub_module(self):
        training = self.create_training()
        # stat admin materiallara giriş almayıb -> görə bilməz, yükləyə bilməz
        self.assertEqual(self.client_for(self.stat_admin).get("/api/trainings/materials/").status_code, 403)
        # material admin statistikanı görə bilməz
        self.assertEqual(self.client_for(self.mat_admin).get("/api/trainings/statistics/summary/").status_code, 403)
        # stat admin statistikanı görür
        self.assertEqual(self.client_for(self.stat_admin).get("/api/trainings/statistics/summary/").status_code, 200)
        # adi izləyici yükləyə bilməz, quiz dəyişə bilməz
        viewer = self.client_for(self.viewer)
        self.assertEqual(viewer.get("/api/trainings/materials/").status_code, 200)
        self.assertEqual(viewer.patch(f"/api/trainings/materials/{training.id}/", {"title": "x"}).status_code, 403)
        self.assertEqual(viewer.put(f"/api/trainings/materials/{training.id}/quiz/", {"questions": []},
                                    format="json").status_code, 403)
        # modula ümumiyyətlə girişi olmayan
        self.assertEqual(self.client_for(self.outsider).get("/api/trainings/materials/").status_code, 403)
        self.assertEqual(self.client_for(self.outsider).get("/api/trainings/permissions/").status_code, 403)

        perms = self.client_for(self.mat_admin).get("/api/trainings/permissions/").data
        self.assertTrue(perms["can_manage_materials"])
        self.assertFalse(perms["can_view_statistics"])

    def test_module_admin_manages_both(self):
        boss = make_user("boss", self.org)
        self.module.admin_users.add(boss)
        perms = self.client_for(boss).get("/api/trainings/permissions/").data
        self.assertTrue(perms["can_manage_materials"] and perms["can_manage_statistics"])

    # --- baxış --------------------------------------------------------------

    def test_cannot_skip_and_leaving_resets(self):
        training = self.create_training(duration=100)
        c = self.client_for(self.viewer)
        c.post(f"/api/trainings/materials/{training.id}/start/")
        # dərhal sona atlamaq mümkün deyil
        res = c.post(f"/api/trainings/materials/{training.id}/complete/", {"position": 100})
        self.assertEqual(res.status_code, 400)
        res = c.post(f"/api/trainings/materials/{training.id}/progress/", {"position": 90})
        self.assertLess(res.data["max_position"], 15)

        # 50 saniyə real baxış
        TrainingProgress.objects.filter(user=self.viewer).update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=50))
        res = c.post(f"/api/trainings/materials/{training.id}/progress/", {"position": 50})
        self.assertAlmostEqual(res.data["max_position"], 50, delta=1)

        # səhifədən çıxıb yenidən gəlir -> sıfırlanır
        res = c.post(f"/api/trainings/materials/{training.id}/start/")
        self.assertEqual(res.data["max_position"], 0)
        self.assertEqual(res.data["attempts_count"], 2)
        # quiz bağlıdır
        self.assertEqual(c.get(f"/api/trainings/materials/{training.id}/quiz/").status_code, 403)

    def watch_fully(self, training, user):
        c = self.client_for(user)
        c.post(f"/api/trainings/materials/{training.id}/start/")
        TrainingProgress.objects.filter(user=user, training=training).update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=training.duration_seconds))
        res = c.post(f"/api/trainings/materials/{training.id}/complete/", {"position": training.duration_seconds})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["status"], "completed")
        return c

    def test_quiz_flow_and_statistics(self):
        training = self.create_training(duration=60)
        questions = self.set_quiz(training)
        c = self.watch_fully(training, self.viewer)

        quiz = c.get(f"/api/trainings/materials/{training.id}/quiz/").data
        self.assertEqual(len(quiz["questions"]), 2)
        self.assertNotIn("is_correct", quiz["questions"][0]["options"][0])

        # yarımçıq cavab qəbul edilmir
        q1, q2 = questions
        res = c.post(f"/api/trainings/materials/{training.id}/quiz/submit/",
                     {"answers": {str(q1["id"]): q1["options"][0]["id"]}}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(QuizAttempt.objects.count(), 0)

        res = c.post(f"/api/trainings/materials/{training.id}/quiz/submit/", {"answers": {
            str(q1["id"]): q1["options"][0]["id"], str(q2["id"]): q2["options"][1]["id"],
        }}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["percent"], 50)
        self.assertFalse(res.data["passed"])

        c.post(f"/api/trainings/materials/{training.id}/feedback/", {"rating": 4, "comment": "Faydalı"})

        stats = self.client_for(self.stat_admin)
        summary = stats.get("/api/trainings/statistics/summary/").data
        row = summary["trainings"][0]
        self.assertEqual(row["completed"], 1)
        self.assertEqual(row["quiz_attempts"], 1)
        self.assertEqual(row["feedback_count"], 1)
        self.assertEqual(row["avg_rating"], 4)

        views = stats.get("/api/trainings/statistics/views/?status=completed").data
        self.assertEqual(views["count"], 1)
        self.assertEqual(views["results"][0]["user"]["username"], "viewer")

        detail_id = stats.get("/api/trainings/statistics/quiz-results/").data["results"][0]["id"]
        detail = stats.get(f"/api/trainings/statistics/quiz-results/{detail_id}/").data
        self.assertEqual(len(detail["answers"]), 2)

        export = stats.get("/api/trainings/statistics/export/")
        self.assertEqual(export.status_code, 200)
        self.assertIn("spreadsheetml", export["Content-Type"])

        # admin quiz-i dəyişsə də köhnə nəticə snapshot kimi qalır
        self.set_quiz(training)
        detail = stats.get(f"/api/trainings/statistics/quiz-results/{detail_id}/").data
        self.assertEqual(detail["answers"][0]["question_text"], "2+2?")

        # statistika admini baxış qeydini sıfırlaya bilər
        progress_id = views["results"][0]["id"]
        self.assertEqual(stats.delete(f"/api/trainings/statistics/views/{progress_id}/").status_code, 204)

    def test_not_started_list(self):
        training = self.create_training(duration=30)
        stats = self.client_for(self.stat_admin)
        res = stats.get(f"/api/trainings/statistics/views/not-started/?training={training.id}")
        usernames = {u["username"] for u in res.data}
        self.assertIn("viewer", usernames)
        self.assertIn("matadmin", usernames)
        self.assertNotIn("statadmin", usernames)  # materiallara girişi yoxdur
        self.assertNotIn("outsider", usernames)

    def test_delete_with_history_archives(self):
        training = self.create_training(duration=30)
        self.client_for(self.viewer).post(f"/api/trainings/materials/{training.id}/start/")
        res = self.client_for(self.mat_admin).delete(f"/api/trainings/materials/{training.id}/")
        self.assertEqual(res.status_code, 200)
        training.refresh_from_db()
        self.assertFalse(training.is_active)
        # izləyici arxivləşdirilmiş təlimi görmür
        self.assertEqual(self.client_for(self.viewer).get("/api/trainings/materials/").data, [])


class SubModuleAdminAccessApiTests(TestCase):
    def test_org_admin_assigns_sub_module_admin(self):
        org = Organization.objects.create(title="Qurum")
        module = Module.objects.create(code="trainings", title="Təlimlər", url_endpoint="telimler")
        module.permitted_organizations.add(org)
        sub = SubModule.objects.create(module=module, code="training_statistics", title="S", url_endpoint="s")
        sub.permitted_organizations.add(org)
        admin = make_user("orgadmin", org, is_org_admin=True)
        worker = make_user("worker", org)

        c = APIClient()
        c.force_authenticate(admin)
        url = "/api/organization/module-access/"
        res = c.post(url, {"target": "sub_module_admin", "id": sub.id, "user_id": worker.id, "grant": True},
                     format="json")
        self.assertEqual(res.status_code, 400)  # əvvəlcə əsas modula giriş lazımdır
        module.permitted_users.add(worker)
        res = c.post(url, {"target": "sub_module_admin", "id": sub.id, "user_id": worker.id, "grant": True},
                     format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(sub.is_admin_user(worker))

        data = c.get(url).data
        sub_users = data["modules"][0]["sub_modules"][0]["users"]
        row = next(u for u in sub_users if u["id"] == worker.id)
        self.assertTrue(row["is_sub_module_admin"])
        self.assertTrue(row["has_access"])
