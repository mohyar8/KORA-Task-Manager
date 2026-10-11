"""Calendar: scoped events and meetings with a historical invitation list, plus a merged
"my calendar" view that also shows (derived, read-only) task due dates.

Depends on access, organization, tasks (read-only) and notifications; nothing depends on it
except the app factory, which registers its notification source checker.
"""
