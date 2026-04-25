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
