"""Chat is private: the only audited action is a moderator removing someone's message, and it
records ids only (never the text)."""

from kora_api.audit.service import action

MESSAGE = "message"
MESSAGE_MODERATED = action(
    "message.moderated_deleted", MESSAGE, "message_id", "conversation_id", "author_member_id"
)
