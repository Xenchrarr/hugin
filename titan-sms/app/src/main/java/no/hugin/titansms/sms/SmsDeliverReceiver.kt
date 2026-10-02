package no.hugin.titansms.sms

import android.content.BroadcastReceiver
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import no.hugin.titansms.data.AppPreferences
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.notifications.MessageNotifier
import kotlin.concurrent.thread

class SmsDeliverReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_DELIVER_ACTION) return
        val pending = goAsync()
        thread(name = "sms-delivery") {
            try {
                val pdus = Telephony.Sms.Intents.getMessagesFromIntent(intent)
                if (pdus.isEmpty()) return@thread
                val address = pdus.first().originatingAddress.orEmpty()
                val body = pdus.joinToString("") { it.messageBody.orEmpty() }
                val timestamp = pdus.minOf { it.timestampMillis }
                val subscriptionId = intent.getIntExtra("subscription", -1)
                val values = ContentValues().apply {
                    put(Telephony.Sms.ADDRESS, address); put(Telephony.Sms.BODY, body)
                    put(Telephony.Sms.DATE, timestamp); put(Telephony.Sms.DATE_SENT, timestamp)
                    put(Telephony.Sms.READ, 0); put(Telephony.Sms.SEEN, 0)
                    put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_INBOX)
                    if (subscriptionId >= 0) put("sub_id", subscriptionId)
                    put("creator", context.packageName)
                }
                val uri = context.contentResolver.insert(Telephony.Sms.Inbox.CONTENT_URI, values) ?: return@thread
                val indexed = MessageStore(context).indexProviderSms(
                    ContentUris.parseId(uri), address, body, timestamp, true,
                    AppPreferences(context).hubNumber, markUnread = true,
                ) ?: return@thread
                MessageNotifier(context).notify(indexed)
            } finally { pending.finish() }
        }
    }
}
