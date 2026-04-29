"""Generate AI portraits for agents that are missing one.

Default mode only touches agents with an empty `avatar_url`, so re-running is
a safe idempotent no-op once the catalog is fully covered. Pass `--force` to
re-roll every agent (useful after editing AGENT_AVATAR_STYLE_SUFFIX, since
existing stored URLs are not retroactively re-rendered).

Each call costs ~$0.04 against the OpenAI Images API and takes 5-15s, so
prefer `--limit N` for trial runs. The command processes agents serially —
parallelism is intentionally avoided to stay under image-API rate limits and
to keep stdout output readable.

Run examples:
    python manage.py backfill_agent_avatars --dry-run
    python manage.py backfill_agent_avatars --limit 3
    python manage.py backfill_agent_avatars --force
"""
from django.core.management.base import BaseCommand

from myApp.models import Agent
from myApp.views import _generate_and_store_agent_avatar


class Command(BaseCommand):
    help = "Generate AI portraits for agents that are missing one (or all, with --force)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the agents that would be processed; do not call OpenAI or Cloudinary.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate every agent's avatar, even those with an existing avatar_url.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N agents (0 = no limit). Useful for trial runs.",
        )

    def handle(self, *args, dry_run=False, force=False, limit=0, **opts):
        queryset = Agent.objects.all().order_by("id")
        if not force:
            queryset = queryset.filter(avatar_url="")
        if limit and limit > 0:
            queryset = queryset[:limit]

        agents = list(queryset)
        total = len(agents)
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "No agents need an avatar. (Pass --force to regenerate existing ones.)"
            ))
            return

        mode = "FORCE regenerating" if force else "Backfilling"
        self.stdout.write(f"{mode} {total} agent avatar(s){' (dry-run)' if dry_run else ''}.")

        succeeded = 0
        failed = 0
        for index, agent in enumerate(agents, start=1):
            label = f"[{index}/{total}] {agent.name} (#{agent.id})"
            if dry_run:
                self.stdout.write(f"  {label} — would generate")
                continue

            try:
                new_url = _generate_and_store_agent_avatar(agent)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stdout.write(self.style.ERROR(f"  {label} — error: {exc}"))
                continue

            if new_url:
                succeeded += 1
                self.stdout.write(self.style.SUCCESS(f"  {label} — OK"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  {label} — generation returned no URL "
                    "(check OPENAI_API_KEY and Cloudinary settings)"
                ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete. {total} agent(s) eligible."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. succeeded={succeeded} failed={failed} total={total}"
            ))
