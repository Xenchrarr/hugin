package no.hugin.titansms.sms

import android.app.RemoteInput
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.notifications.MessageNotifier
import kotlin.concurrent.thread

class NotificationReplyReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val body = RemoteInput.getResultsFromIntent(intent)?.getCharSequence(MessageNotifier.REPLY_TEXT)?.toString()
            ?.takeIf { it.isNotBlank() } ?: return
        val conversationId = intent.getLongExtra(CONVERSATION_ID, -1)
        val conversation = MessageStore(context).conversation(conversationId) ?: return
        val pending = goAsync()
        thread(name = "notification-reply") {
            try {
                SmsSender(context).sendToConversation(conversation, body)
            } finally { pending.finish() }
        }
    }

    companion object { const val CONVERSATION_ID = "conversation_id" }
}
