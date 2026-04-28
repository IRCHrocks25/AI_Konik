"""Send day-3 and day-14 lifecycle emails to qualifying users.

Idempotency contract:
  Each user gets at most one day_3 and one day_14 email. The decision is keyed
  on `last_lifecycle_email_kind`. Re-running the command after it has already
  processed today's cohorts is a safe no-op.

Cohort criteria:
  * Verified (email_verified=True). Unverified accounts are excluded.
  * Not suspended.
  * date_joined__date is at least N days ago (using date arithmetic, not
    hour-of-day, so a user who signed up at 23:55 yesterday is "1 day old"
    today not "0 days").
  * last_lifecycle_email_kind is not yet "day_N".

Run via cron: ``0 9 * * * cd /app && python manage.py send_lifecycle_emails``
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_tz

from myApp.email_service import (
    KIND_DAY_3,
    KIND_DAY_14,
    send_day_3_email,
    send_day_14_email,
)
from myApp.models import ChatMessage, ChatSession, CustomUser


class Command(BaseCommand):
    help = "Send day-3 and day-14 lifecycle emails to qualifying users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print intended sends without calling Resend or writing to the DB.",
        )

    def handle(self, *args, dry_run=False, **opts):
        now = dj_tz.now()
        today = now.date()
        day_3_cutoff = today - timedelta(days=3)
        day_14_cutoff = today - timedelta(days=14)

        sent_day_3 = 0
        sent_day_14 = 0
        failed = 0

        # Day-3 cohort: signed up at least 3 days ago, never sent day_3.
        # We allow signups older than 3 days too — late catch-up is fine since
        # the email is generic ("how's your first week?") and idempotency is
        # guaranteed by the kind check.
        day_3_qs = CustomUser.objects.filter(
            email_verified=True,
            is_suspended=False,
            created_at__date__lte=day_3_cutoff,
        ).exclude(last_lifecycle_email_kind=KIND_DAY_3).exclude(
            last_lifecycle_email_kind=KIND_DAY_14,
        )

        for user in day_3_qs.iterator():
            self.stdout.write(f"  ->day_3  to {user.email}")
            if dry_run:
                sent_day_3 += 1
                continue
            ok, _ = send_day_3_email(user)
            if ok:
                user.last_lifecycle_email_sent = dj_tz.now()
                user.last_lifecycle_email_kind = KIND_DAY_3
                user.save(update_fields=[
                    "last_lifecycle_email_sent",
                    "last_lifecycle_email_kind",
                    "updated_at",
                ])
                sent_day_3 += 1
            else:
                failed += 1

        # Day-14 cohort: signed up at least 14 days ago, never sent day_14.
        # Independent of day_3 — a user can receive both, just not the same one twice.
        day_14_qs = CustomUser.objects.filter(
            email_verified=True,
            is_suspended=False,
            created_at__date__lte=day_14_cutoff,
        ).exclude(last_lifecycle_email_kind=KIND_DAY_14)

        for user in day_14_qs.iterator():
            agents_used = (
                ChatSession.objects.filter(user=user)
                .values("agent_name")
                .distinct()
                .count()
            )
            prompts_run = ChatMessage.objects.filter(
                session__user=user, role="user",
            ).count()

            self.stdout.write(
                f"  ->day_14 to {user.email}  "
                f"(agents_used={agents_used}, prompts_run={prompts_run})"
            )
            if dry_run:
                sent_day_14 += 1
                continue
            ok, _ = send_day_14_email(
                user, agents_used=agents_used, prompts_run=prompts_run,
            )
            if ok:
                user.last_lifecycle_email_sent = dj_tz.now()
                user.last_lifecycle_email_kind = KIND_DAY_14
                user.save(update_fields=[
                    "last_lifecycle_email_sent",
                    "last_lifecycle_email_kind",
                    "updated_at",
                ])
                sent_day_14 += 1
            else:
                failed += 1

        prefix = "[DRY-RUN] would send" if dry_run else "Sent"
        self.stdout.write(self.style.SUCCESS(
            f"{prefix} {sent_day_3} day_3 emails, {sent_day_14} day_14 emails"
            + (f" ({failed} send failures)" if failed else "")
        ))
