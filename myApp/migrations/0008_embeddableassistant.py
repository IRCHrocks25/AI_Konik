from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("myApp", "0007_agent_avatar_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmbeddableAssistant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("description", models.TextField(blank=True)),
                ("brand", models.CharField(blank=True, default="", max_length=80)),
                ("brand_full", models.CharField(blank=True, default="", max_length=140)),
                ("greeting", models.CharField(blank=True, default="", max_length=240)),
                ("suggestions", models.JSONField(blank=True, default=list)),
                ("powered_by", models.CharField(blank=True, default="AI KONIK", max_length=120)),
                ("logo_url", models.URLField(blank=True, default="", max_length=500)),
                ("orb_logo_url", models.URLField(blank=True, default="", max_length=500)),
                ("launcher_label", models.CharField(blank=True, default="Need help? Ask us!", max_length=120)),
                ("voice", models.CharField(blank=True, default="", max_length=80)),
                ("extra_instructions", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
