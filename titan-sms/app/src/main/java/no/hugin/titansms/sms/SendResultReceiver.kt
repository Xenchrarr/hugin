package no.hugin.titansms.sms

import android.content.BroadcastReceiver
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Telephony
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.model.SendState

class SendResultReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getLongExtra(MESSAGE_ID, -1)
        val stage = intent.getStringExtra(STAGE) ?: return
        val part = intent.getIntExtra(PART, 0)
        val total = intent.getIntExtra(TOTAL, 1)
        if (id < 0) return
        val state = MessageStore(context).updateSendPart(id, stage, part, total, resultCode)
        val providerUri = intent.getStringExtra(PROVIDER_URI)?.let(Uri::parse) ?: return
        if (state == SendState.FAILED && stage == "sent") {
            context.contentResolver.update(providerUri, ContentValues().apply {
                put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_FAILED)
                put(Telephony.Sms.ERROR_CODE, resultCode)
            }, null, null)
        } else if (state == SendState.SMS_SENT) {
            context.contentResolver.update(providerUri, ContentValues().apply {
                put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_SENT)
                put(Telephony.Sms.DATE_SENT, System.currentTimeMillis())
            }, null, null)
        }
    }

    companion object {
        const val MESSAGE_ID = "message_id"
        const val PROVIDER_URI = "provider_uri"
        const val STAGE = "stage"
        const val PART = "part"
        const val TOTAL = "total"
    }
}
