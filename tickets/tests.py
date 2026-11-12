from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from authentication.models import Department, Organization, User
from core.models import Module
from notifications.models import Notification

from . import services
from .models import Ticket, TicketCategory, TicketDepartment

BASE = '/api/tickets/'


def make_user(username, org=None, dept=None, **extra):
    return User.objects.create_user(
        username=username, email=f'{username}@example.az', password='x',
        firstname=username.title(), lastname='Test', organization=org, department=dept,
        two_fa_confirmed=True, is_approved=True, **extra,
    )


class TicketFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(title='Qurum A')
        cls.other_org = Organization.objects.create(title='Qurum B')
        cls.it = Department.objects.create(title='İT şöbəsi', shortname='İT', organization=cls.org)
        cls.hr = Department.objects.create(title='Kadr şöbəsi', shortname='Kadr', organization=cls.org)
        cls.foreign = Department.objects.create(title='Yad şöbə', organization=cls.other_org)
        cls.sales = Department.objects.create(title='Satış', organization=cls.org)

        cls.requester = make_user('requester', cls.org, cls.sales)
        cls.it_manager = make_user('itmanager', cls.org, cls.it)
        cls.it.manager = cls.it_manager
        cls.it.save()
        cls.it_agent = make_user('itagent', cls.org, cls.it)
        cls.hr_agent = make_user('hragent', cls.org, cls.hr)
        cls.stranger = make_user('stranger', cls.org, cls.sales)
        cls.admin = make_user('tadmin', cls.org)
        Module.objects.get(code='tickets').admin_users.add(cls.admin)
        cls.cat = TicketCategory.objects.get(code='it-support')

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def create(self, **kw):
        payload = {'title': 'Printer işləmir', 'description': 'Üçüncü mərtəbədəki printer çap etmir',
                   'priority': 'high', 'departments': [self.it.id, self.hr.id], 'category': self.cat.id}
        payload.update(kw)
        r = self.api(self.requester).post(BASE, payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_module_seeded_and_public(self):
        m = Module.objects.get(code='tickets')
        self.assertTrue(m.is_public)
        self.assertEqual(m.url_endpoint, 'muracietler')

    def test_create_assigns_departments_sla_and_notifies(self):
        data = self.create()
        self.assertEqual(data['status'], 'new')
        self.assertTrue(data['number'].startswith('TKT-'))
        self.assertEqual({d['department'] for d in data['department_links']}, {self.it.id, self.hr.id})
        self.assertTrue(data['department_links'][0]['is_primary'])
        t = Ticket.objects.get(pk=data['id'])
        self.assertEqual(t.due_at - t.created_at, timedelta(hours=8))   # high -> 8 saat
        self.assertTrue(Notification.objects.filter(recipient=self.it_manager, related_object_id=t.id).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.requester, related_object_id=t.id).exists())

    def test_default_department_from_category(self):
        self.cat.default_department = self.it
        self.cat.save()
        data = self.create(departments=[])
        self.assertEqual([d['department'] for d in data['department_links']], [self.it.id])

    def test_foreign_org_department_rejected(self):
        r = self.api(self.requester).post(BASE, {
            'title': 'Test mövzu', 'description': 'Kifayət qədər uzun təsvir',
            'departments': [self.foreign.id]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_visibility(self):
        tid = self.create()['id']
        for user, expected in [(self.requester, 200), (self.it_agent, 200), (self.hr_agent, 200),
                               (self.admin, 200), (self.stranger, 404)]:
            self.assertEqual(self.api(user).get(f'{BASE}{tid}/').status_code, expected, user.username)
        lst = self.api(self.stranger).get(BASE).data
        self.assertEqual(lst['count'], 0)
        self.assertEqual(self.api(self.it_agent).get(BASE + '?scope=department').data['count'], 1)
        self.assertEqual(self.api(self.requester).get(BASE + '?scope=mine').data['count'], 1)

    def test_status_workflow_and_permissions(self):
        tid = self.create()['id']
        # müraciətçi icraya keçirə bilməz
        r = self.api(self.requester).post(f'{BASE}{tid}/status/', {'status': 'in_progress'}, format='json')
        self.assertEqual(r.status_code, 400)
        # icraçı götürür
        r = self.api(self.it_agent).post(f'{BASE}{tid}/take/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status'], 'in_progress')
        self.assertEqual(r.data['assignee'], self.it_agent.id)
        self.assertIsNotNone(r.data['first_response_at'])
        # həll
        r = self.api(self.it_agent).post(f'{BASE}{tid}/status/', {'status': 'resolved', 'comment': 'Toner dəyişdirildi'}, format='json')
        self.assertEqual(r.data['status'], 'resolved')
        self.assertEqual(r.data['comments'][-1]['body'], 'Toner dəyişdirildi')
        # müraciətçi yenidən açır
        r = self.api(self.requester).post(f'{BASE}{tid}/status/', {'status': 'in_progress', 'comment': 'Yenə işləmir'}, format='json')
        self.assertEqual(r.data['status'], 'in_progress')
        self.assertEqual(r.data['reopen_count'], 1)
        # həll → müraciətçi bağlayır → qiymətləndirir
        self.api(self.it_agent).post(f'{BASE}{tid}/status/', {'status': 'resolved'}, format='json')
        r = self.api(self.requester).post(f'{BASE}{tid}/status/', {'status': 'closed'}, format='json')
        self.assertEqual(r.data['status'], 'closed')
        r = self.api(self.requester).post(f'{BASE}{tid}/rate/', {'rating': 5, 'comment': 'Əla'}, format='json')
        self.assertEqual(r.data['rating'], 5)
        # bağlanmışa şərh olmaz
        r = self.api(self.requester).post(f'{BASE}{tid}/comments/', {'body': 'salam'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_internal_notes_hidden_from_requester(self):
        tid = self.create()['id']
        self.api(self.it_agent).post(f'{BASE}{tid}/comments/', {'body': 'Daxili: sürücü problemi', 'is_internal': True}, format='json')
        self.api(self.it_agent).post(f'{BASE}{tid}/comments/', {'body': 'Baxırıq'}, format='json')
        agent_view = self.api(self.it_agent).get(f'{BASE}{tid}/').data
        req_view = self.api(self.requester).get(f'{BASE}{tid}/').data
        self.assertEqual(len(agent_view['comments']), 2)
        self.assertEqual([c['body'] for c in req_view['comments']], ['Baxırıq'])
        r = self.api(self.requester).post(f'{BASE}{tid}/comments/', {'body': 'x', 'is_internal': True}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_waiting_resumes_on_requester_reply(self):
        tid = self.create()['id']
        self.api(self.it_agent).post(f'{BASE}{tid}/status/', {'status': 'waiting'}, format='json')
        r = self.api(self.requester).post(f'{BASE}{tid}/comments/', {'body': 'Cavab verirəm'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Ticket.objects.get(pk=tid).status, 'in_progress')

    def test_department_progress_auto_resolves(self):
        tid = self.create()['id']
        r = self.api(self.it_agent).post(f'{BASE}{tid}/department-status/',
                                         {'department': self.it.id, 'status': 'done'}, format='json')
        self.assertEqual(r.data['status'], 'new')
        # başqa şöbənin statusunu dəyişə bilməz
        r = self.api(self.it_agent).post(f'{BASE}{tid}/department-status/',
                                         {'department': self.hr.id, 'status': 'done'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.api(self.hr_agent).post(f'{BASE}{tid}/department-status/',
                                         {'department': self.hr.id, 'status': 'done'}, format='json')
        self.assertEqual(r.data['status'], 'resolved')

    def test_reassign_departments_and_assignee_rules(self):
        tid = self.create(departments=[self.it.id])['id']
        r = self.api(self.it_manager).put(f'{BASE}{tid}/departments/', {'departments': [
            {'department': self.it.id, 'assignee': self.it_agent.id},
            {'department': self.hr.id}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['department_links']), 2)
        # hr-ə IT əməkdaşını icraçı kimi vermək olmaz
        r = self.api(self.it_manager).put(f'{BASE}{tid}/departments/', {'departments': [
            {'department': self.hr.id, 'assignee': self.it_agent.id}]}, format='json')
        self.assertEqual(r.status_code, 400)
        # müraciətçi 'new' statusunda şöbə dəyişə bilər, stranger bilməz
        r = self.api(self.stranger).put(f'{BASE}{tid}/departments/', {'departments': [{'department': self.hr.id}]}, format='json')
        self.assertEqual(r.status_code, 404)
        # əsas icraçı
        r = self.api(self.it_manager).post(f'{BASE}{tid}/assignee/', {'assignee': self.hr_agent.id}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_department_staff_self_assign_multiple_assignees(self):
        tid = self.create()['id']
        # təyin olunmamış şöbənin əməkdaşı müraciəti görmür/götürə bilmir
        r = self.api(self.stranger).post(f'{BASE}{tid}/take/')
        self.assertIn(r.status_code, (403, 404))

        r = self.api(self.it_agent).post(f'{BASE}{tid}/take/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status'], 'in_progress')
        self.assertEqual([a['user'] for a in r.data['assignees']], [self.it_agent.id])
        self.assertEqual(r.data['assignees'][0]['status'], 'in_progress')
        self.assertTrue(r.data['assignees'][0]['self_assigned'])
        self.assertEqual(r.data['assignee'], self.it_agent.id)
        # təkrar götürmək olmaz
        r = self.api(self.it_agent).post(f'{BASE}{tid}/take/')
        self.assertEqual(r.status_code, 400)
        # eyni şöbədən daha biri və digər şöbədən biri də götürür
        self.assertEqual(self.api(self.it_manager).post(f'{BASE}{tid}/take/').status_code, 200)
        r = self.api(self.hr_agent).post(f'{BASE}{tid}/take/')
        self.assertEqual(len(r.data['assignees']), 3)
        self.assertEqual(r.data['permissions']['my_assignee_status'], 'in_progress')
        # siyahıda bir neçə icraçı göstərilir
        row = self.api(self.requester).get(BASE).data['results'][0]
        self.assertEqual(len(row['assignees']), 3)
        self.assertTrue(row['assignee_name'].endswith('+2'))
        # müraciətçi (və izləyənlər) bildirişi alır
        self.assertTrue(Notification.objects.filter(recipient=self.requester, related_object_id=tid).exists())

        # icraçı statusları: hər şöbənin bütün icraçıları bitirəndə şöbə, sonra müraciət tamamlanır
        def done(user):
            return self.api(user).post(f'{BASE}{tid}/assignee-status/', {'status': 'done'}, format='json')
        r = done(self.it_agent)
        self.assertEqual(r.status_code, 200, r.data)
        links = {l['department']: l['status'] for l in r.data['department_links']}
        self.assertEqual(links[self.it.id], 'in_progress')       # menecer hələ bitirməyib
        self.assertEqual(r.data['status'], 'in_progress')
        r = done(self.it_manager)
        links = {l['department']: l['status'] for l in r.data['department_links']}
        self.assertEqual(links[self.it.id], 'done')
        self.assertEqual(r.data['status'], 'in_progress')
        r = done(self.hr_agent)
        self.assertEqual(r.data['status'], 'resolved')

        # müraciət yenidən açılanda tamamlayanlar yenidən icradadır
        r = self.api(self.requester).post(f'{BASE}{tid}/status/', {'status': 'in_progress', 'comment': 'Yenə'}, format='json')
        self.assertEqual({a['status'] for a in r.data['assignees']}, {'in_progress'})

    def test_release_add_and_assignee_status_rules(self):
        tid = self.create()['id']
        self.api(self.it_agent).post(f'{BASE}{tid}/take/')
        # götürən çıxır -> icraçı yoxdur, müraciət yenidən 'Qəbul edildi'
        r = self.api(self.it_agent).post(f'{BASE}{tid}/release/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['assignees'], [])
        self.assertIsNone(r.data['assignee'])
        self.assertEqual(r.data['status'], 'open')
        # icraçı olmayan çıxa bilməz
        self.assertEqual(self.api(self.it_agent).post(f'{BASE}{tid}/release/', {}, format='json').status_code, 400)
        # admin başqasını təyin edir: status 'Təyin olunub', bildiriş gedir
        r = self.api(self.admin).post(f'{BASE}{tid}/assignees/', {'users': [self.hr_agent.id, self.it_agent.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual({a['status'] for a in r.data['assignees']}, {'assigned'})
        self.assertTrue(Notification.objects.filter(recipient=self.hr_agent, related_object_id=tid).exists())
        # təyin olunmamış şöbənin əməkdaşı təyin edilə bilməz
        r = self.api(self.it_manager).post(f'{BASE}{tid}/assignees/', {'users': [self.stranger.id]}, format='json')
        self.assertEqual(r.status_code, 400)
        # icraçı öz statusunu dəyişir -> müraciət 'İcradadır'
        r = self.api(self.hr_agent).post(f'{BASE}{tid}/assignee-status/', {'status': 'in_progress'}, format='json')
        self.assertEqual(r.data['status'], 'in_progress')
        # başqasının statusunu yalnız admin dəyişə bilər
        r = self.api(self.it_agent).post(f'{BASE}{tid}/assignee-status/',
                                         {'status': 'done', 'user': self.hr_agent.id}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.api(self.admin).post(f'{BASE}{tid}/assignee-status/',
                                      {'status': 'done', 'user': self.hr_agent.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # köhnə təkli API hələ də işləyir
        r = self.api(self.it_manager).post(f'{BASE}{tid}/assignee/', {'assignee': self.it_manager.id}, format='json')
        self.assertEqual([a['user'] for a in r.data['assignees']], [self.it_manager.id])

    def test_attachments(self):
        tid = self.create()['id']
        ok = SimpleUploadedFile('screen.png', b'\x89PNG....', content_type='image/png')
        r = self.api(self.requester).post(f'{BASE}{tid}/attachments/', {'files': ok}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        bad = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        r = self.api(self.requester).post(f'{BASE}{tid}/attachments/', {'files': bad}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.api(self.requester).get(f'{BASE}{tid}/').data['attachments']), 1)

    def test_edit_rules(self):
        tid = self.create()['id']
        r = self.api(self.requester).patch(f'{BASE}{tid}/', {'title': 'Yeni mövzu burada'}, format='json')
        self.assertEqual(r.data['title'], 'Yeni mövzu burada')
        r = self.api(self.it_agent).patch(f'{BASE}{tid}/', {'priority': 'critical'}, format='json')
        t = Ticket.objects.get(pk=tid)
        self.assertEqual(t.priority, 'critical')
        self.assertEqual(t.due_at - t.created_at, timedelta(hours=4))
        self.api(self.it_agent).post(f'{BASE}{tid}/status/', {'status': 'in_progress'}, format='json')
        r = self.api(self.requester).patch(f'{BASE}{tid}/', {'title': 'Dəyişmək olmaz'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_stats_filters_and_search(self):
        tid = self.create()['id']
        self.create(title='İnternet kəsilib', priority='low')
        Ticket.objects.filter(pk=tid).update(due_at=timezone.now() - timedelta(hours=1))
        s = self.api(self.admin).get(BASE + 'stats/').data
        self.assertEqual((s['total'], s['active'], s['overdue'], s['unassigned']), (2, 2, 1, 2))
        self.assertEqual(s['by_priority']['high'], 1)
        self.assertEqual(len(s['trend']), 14)
        self.assertEqual(self.api(self.admin).get(BASE + '?overdue=true').data['count'], 1)
        self.assertEqual(self.api(self.admin).get(BASE + '?search=nternet').data['count'], 1)
        self.assertEqual(self.api(self.admin).get(f'{BASE}?search=TKT-{tid:05d}').data['count'], 1)
        self.assertEqual(self.api(self.admin).get(BASE + '?status=new,open&ordering=-priority_rank').data['results'][0]['priority'], 'high')
        self.assertEqual(self.api(self.admin).get(BASE + f'?department={self.hr.id}').data['count'], 2)

    def test_categories_admin_only(self):
        r = self.api(self.requester).post(BASE + 'categories/', {'title': 'X', 'code': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.api(self.admin).post(BASE + 'categories/', {'title': 'Yeni kat', 'code': 'yeni'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertGreaterEqual(len(self.api(self.requester).get(BASE + 'categories/').data), 6)

    def test_meta_and_users(self):
        m = self.api(self.requester).get(BASE + 'meta/').data
        self.assertEqual(len(m['priorities']), 4)
        self.assertNotIn(self.foreign.id, [d['id'] for d in m['departments']])
        u = self.api(self.requester).get(f'{BASE}users/?department={self.it.id}').data
        self.assertEqual({x['username'] for x in u}, {'itmanager', 'itagent'})

    def test_maintenance_jobs(self):
        tid = self.create()['id']
        t = Ticket.objects.get(pk=tid)
        Ticket.objects.filter(pk=tid).update(due_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(services.escalate_overdue(), 1)
        self.assertEqual(services.escalate_overdue(), 0)    # ikinci dəfə eskalasiya olunmur
        self.assertTrue(Notification.objects.filter(recipient=self.it_manager, notification_type='ticket_escalated').exists())
        Ticket.objects.filter(pk=tid).update(status='resolved', resolved_at=timezone.now() - timedelta(days=4))
        self.assertEqual(services.auto_close_resolved(), 1)
        self.assertEqual(Ticket.objects.get(pk=tid).status, 'closed')

    def test_operations_log_written(self):
        from operations.models import Operation
        self.create()
        self.assertTrue(Operation.objects.filter(category_code='tickets', action='created').exists())

    def test_login_requirements_enforced(self):
        c = APIClient()
        self.assertIn(c.get(BASE).status_code, (401, 403))
        no2fa = make_user('no2fa', self.org, self.it)
        no2fa.two_fa_confirmed = False
        no2fa.save()
        self.assertEqual(self.api(no2fa).get(BASE).status_code, 403)
