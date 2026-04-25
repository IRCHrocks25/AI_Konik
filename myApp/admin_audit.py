"""Admin audit and error logging helpers.

Both functions are append-only and intentionally side-effect-free beyond
the DB write. Callers should still use ``logger.exception`` for full stack
traces when relevant — ``log_error`` here persists a queryable summary
for the OPERATIONS dashboard, not a debug record.
"""

from .models import AdminAction, ErrorLog


def record_admin_action(admin, action_type, target_type=None, target_id=None, metadata=None):
    """Append an AdminAction row.

    admin: CustomUser instance — the admin performing the action.
    action_type: dotted notation, e.g. ``'user.suspend'``, ``'agent.delete'``.
    target_type: optional resource type, e.g. ``'user'``, ``'agent'``, ``'prompt'``.
    target_id: optional ID of the affected resource.
    metadata: optional dict (snapshot of changes, payload, before/after state).

    Returns the created AdminAction.
    """
    return AdminAction.objects.create(
        admin=admin,
        action_type=action_type,
        target_type=target_type or "",
        target_id=target_id,
        metadata=metadata or {},
    )


def log_error(error_type, message, user=None, metadata=None):
    """Persist a user-facing error event for the OPERATIONS dashboard.

    error_type: short category, e.g. ``'openai_chat_send'``, ``'profile_save'``.
    message: human-readable message; truncated to 500 chars.
    user: optional CustomUser the error affected.
    metadata: optional dict.

    Full stack traces should still go to ``logger.exception`` in the caller.
    This function persists a queryable summary, not a full trace.
    """
    return ErrorLog.objects.create(
        error_type=error_type,
        message=(message or "")[:500],
        user=user,
        metadata=metadata or {},
    )
