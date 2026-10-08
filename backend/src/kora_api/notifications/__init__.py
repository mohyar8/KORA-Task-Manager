"""In-app notifications (no email, push or real-time transport).

Generic: a notification references a source by type and id. Source modules (tasks,
announcements) create notifications with `service.notify` inside their own transaction, and
register a `SourceAccess` checker on `app.state.notification_sources` so listings can redact
notifications whose source the reader can no longer see. This module never imports them.
"""
