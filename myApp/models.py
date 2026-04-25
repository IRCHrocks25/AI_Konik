from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CustomUser(models.Model):
    # Core identity
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    # Section 1 — Identity & Context
    display_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(
        max_length=20, blank=True,
        choices=[("solo", "Solo"), ("2-10", "2–10"), ("11-50", "11–50"), ("51-200", "51–200"), ("200+", "200+")],
    )
    years_experience = models.CharField(
        max_length=10, blank=True,
        choices=[("<1", "<1"), ("1-3", "1–3"), ("3-7", "3–7"), ("7-15", "7–15"), ("15+", "15+")],
    )
    timezone = models.CharField(max_length=64, blank=True)

    # Section 2 — Communication Style
    communication_style = models.CharField(
        max_length=20, blank=True,
        choices=[("direct", "Direct"), ("friendly", "Friendly"), ("formal", "Formal"), ("casual", "Casual")],
    )
    response_length = models.CharField(
        max_length=20, blank=True,
        choices=[("concise", "Concise"), ("balanced", "Balanced"), ("detailed", "Detailed")],
    )
    expertise_level = models.CharField(
        max_length=20, blank=True,
        choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("expert", "Expert")],
    )
    formality = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    emoji_use = models.CharField(
        max_length=20, blank=True,
        choices=[("never", "Never"), ("sparingly", "Sparingly"), ("freely", "Freely")],
    )

    # Section 3 — AI Behavior Preferences
    pushback_style = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("always", "Always tell me when I'm wrong"),
            ("diplomatic", "Be diplomatic"),
            ("supportive", "Supportive — acknowledge effort before critiquing"),
        ],
    )
    explanation_style = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("answer_only", "Just give the answer"),
            ("with_reasoning", "Explain reasoning"),
            ("step_by_step", "Step by step"),
        ],
    )
    clarifying_questions = models.CharField(
        max_length=20, blank=True,
        choices=[
            ("when_needed", "When needed"),
            ("always", "Always confirm"),
            ("never", "Never ask, just go"),
        ],
    )

    # Section 4 — Work Context
    expertise_areas = models.JSONField(default=list, blank=True)
    current_focus = models.TextField(blank=True)
    things_to_avoid = models.TextField(blank=True)

    # Section 5 — About
    about_me = models.TextField(blank=True)

    # Analytics
    profile_completed_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Updated on each chat send for fast DAU/WAU queries.",
    )

    # Account state
    is_suspended = models.BooleanField(
        default=False,
        help_text="Soft-disable account without deletion.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email


class Prompt(models.Model):
    STATUS_CHOICES = [
        ("approved", "Approved"),
        ("pending", "Pending"),
    ]

    title = models.CharField(max_length=255)
    body = models.TextField()
    industry = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    usage_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name="prompts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SavedPrompt(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="saved_prompts")
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "prompt")


class ChatSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=255, default="New chat")
    agent_name = models.CharField(max_length=150, default="Contract Review Agent")
    industry = models.CharField(max_length=100, default="legal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]
    FEEDBACK_CHOICES = [
        ("up", "Thumbs Up"),
        ("down", "Thumbs Down"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    feedback = models.CharField(max_length=10, choices=FEEDBACK_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Agent(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    industry = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    icon_class = models.CharField(max_length=80, default="fa-robot")
    accent_bg = models.CharField(max_length=20, default="#EEF2FF")
    tag = models.CharField(max_length=120, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-usage_count", "name"]

    def __str__(self):
        return self.name


class AgentPrompt(models.Model):
    TYPE_CHOICES = [
        ("hint", "Hint"),
        ("use_case", "Use Case"),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="prompts")
    prompt_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="hint")
    content = models.TextField()
    sort_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["prompt_type", "sort_order", "id"]

    def __str__(self):
        return f"{self.agent.name} [{self.prompt_type}]"


# ── Admin dashboard models ──────────────────────────────────────────


class Industry(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(
        max_length=80, unique=True,
        help_text="URL-safe identifier; the application uses slugify() at create time.",
    )
    icon_class = models.CharField(
        max_length=80, default="fa-briefcase",
        help_text="Font Awesome class (e.g. 'fa-house', 'fa-scale-balanced').",
    )
    sort_order = models.PositiveIntegerField(
        default=100,
        help_text="Lower numbers appear first in lists.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft-disable without deletion.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    event_date = models.DateTimeField(
        db_index=True,
        help_text="When the event occurs (indexed to support 'upcoming' filters).",
    )
    location = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(blank=True, max_length=500)
    registration_url = models.URLField(blank=True, max_length=500)
    industry = models.ForeignKey(
        Industry, null=True, blank=True, on_delete=models.SET_NULL, related_name="events",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Surface this event in featured banners and tile sections.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "event_date", "title"]

    def __str__(self):
        return self.title


class Tool(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField()
    icon_class = models.CharField(
        max_length=80, default="fa-toolbox",
        help_text="Font Awesome class (e.g. 'fa-toolbox').",
    )
    external_url = models.URLField(max_length=500)
    category = models.CharField(max_length=80, blank=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Banner(models.Model):
    BANNER_TYPE_CHOICES = [
        ("info", "Info"),
        ("warn", "Warning"),
        ("critical", "Critical"),
    ]

    message = models.TextField()
    banner_type = models.CharField(
        max_length=20, choices=BANNER_TYPE_CHOICES, default="info",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_dismissible = models.BooleanField(
        default=True,
        help_text="If false, banner stays until end_at or admin deactivates.",
    )
    created_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="banners_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(
                fields=["is_active", "start_at", "end_at"],
                name="banner_active_window_idx",
            ),
        ]

    def __str__(self):
        return f"[{self.banner_type}] {self.message[:60]}"


class AdminAction(models.Model):
    admin = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="admin_actions",
        help_text="The admin who performed the action.",
    )
    action_type = models.CharField(
        max_length=80, db_index=True,
        help_text="Dotted notation, e.g. 'user.suspend' or 'agent.delete'.",
    )
    target_type = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="Resource type the action affected, e.g. 'user', 'agent'.",
    )
    target_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="ID of the affected resource (nullable for actions without a single target).",
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Arbitrary JSON snapshot of the action payload or before/after state.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action_type} by {self.admin_id} @ {self.created_at:%Y-%m-%d %H:%M}"


class ErrorLog(models.Model):
    error_type = models.CharField(
        max_length=80, db_index=True,
        help_text="Short category, e.g. 'openai_chat_send'.",
    )
    message = models.CharField(
        max_length=500,
        help_text="Truncated error message. Full stack traces stay in logger output.",
    )
    user = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="error_logs",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.error_type}] {self.message[:80]}"
