from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .auth_utils import SESSION_USER_ID_KEY
from .models import CustomUser, EmbeddableAssistant


class AssistantDashboardTests(TestCase):
    def setUp(self):
        self.custom_admin = CustomUser.objects.create(
            first_name="Admin",
            last_name="User",
            email="admin@example.com",
            password_hash="hashed",
            email_verified=True,
        )
        get_user_model().objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="password123",
        )
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.custom_admin.id
        session.save()

    def test_staff_access_assistant_dashboard(self):
        response = self.client.get(reverse("assistant_list"))
        self.assertEqual(response.status_code, 200)

    def test_assistant_create(self):
        response = self.client.post(
            reverse("assistant_new"),
            {
                "name": "Demo Bot",
                "slug": "demo-bot",
                "brand": "Demo",
                "greeting": "Hi there",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmbeddableAssistant.objects.filter(slug="demo-bot").exists())

    def test_embed_endpoints_available(self):
        EmbeddableAssistant.objects.create(
            name="Demo Bot",
            slug="demo-bot",
            is_active=True,
        )

        loader_res = self.client.get(reverse("embed_assistant_loader"))
        self.assertEqual(loader_res.status_code, 200)

        frame_res = self.client.get(reverse("embed_assistant_frame", args=["demo-bot"]))
        self.assertEqual(frame_res.status_code, 200)

        chat_res = self.client.post(
            reverse("embed_assistant_chat", args=["demo-bot"]),
            data='{"message":"hello"}',
            content_type="application/json",
        )
        self.assertEqual(chat_res.status_code, 200)
