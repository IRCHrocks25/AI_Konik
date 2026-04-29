from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myApp', '0006_email_verification_and_onboarding'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='avatar_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
    ]
