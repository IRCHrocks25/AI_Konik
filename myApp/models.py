from django.db import models


class CustomUser(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, blank=True)
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
