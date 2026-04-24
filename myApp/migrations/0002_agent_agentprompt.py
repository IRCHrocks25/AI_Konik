from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("myApp", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Agent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True)),
                ("slug", models.SlugField(max_length=180, unique=True)),
                ("industry", models.CharField(db_index=True, max_length=100)),
                ("description", models.TextField()),
                ("icon_class", models.CharField(default="fa-robot", max_length=80)),
                ("accent_bg", models.CharField(default="#EEF2FF", max_length=20)),
                ("tag", models.CharField(blank=True, max_length=120)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("is_featured", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "-usage_count", "name"]},
        ),
        migrations.CreateModel(
            name="AgentPrompt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "prompt_type",
                    models.CharField(choices=[("hint", "Hint"), ("use_case", "Use Case")], default="hint", max_length=20),
                ),
                ("content", models.TextField()),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "agent",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prompts", to="myApp.agent"),
                ),
            ],
            options={"ordering": ["prompt_type", "sort_order", "id"]},
        ),
    ]
