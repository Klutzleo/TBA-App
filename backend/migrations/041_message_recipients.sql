-- Whispers are private: record who received each one so history and live delivery can be limited to the sender and the recipients.
-- Additive only; safe to re-run. Older whispers (none exist in production) have no rows here and stay visible to their sender only.

CREATE TABLE IF NOT EXISTS message_recipients (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_message_recipient UNIQUE (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_message_recipients_message_id ON message_recipients (message_id);
CREATE INDEX IF NOT EXISTS ix_message_recipients_user_id ON message_recipients (user_id);
