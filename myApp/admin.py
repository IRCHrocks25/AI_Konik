from django.contrib import admin

from .models import ChatMessage, ChatSession, CustomUser, Prompt, SavedPrompt


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "first_name", "industry", "created_at")
    search_fields = ("email", "first_name", "last_name", "industry")


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "industry", "category", "status", "usage_count")
    list_filter = ("industry", "category", "status")
    search_fields = ("title", "body")


@admin.register(SavedPrompt)
class SavedPromptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "prompt", "created_at")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "agent_name", "updated_at")
    search_fields = ("title", "agent_name", "user__email")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "token_count", "created_at")
    list_filter = ("role", "feedback")
