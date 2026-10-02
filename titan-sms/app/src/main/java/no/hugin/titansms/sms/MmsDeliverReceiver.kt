package no.hugin.titansms.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.widget.Toast
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.notifications.MessageNotifier

/**
 * The role contract requires an MMS receiver. v0.1 is text-SMS-only, so it makes
 * unsupported content visible instead of silently claiming to have displayed it.
 */
class MmsDeliverReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.WAP_PUSH_DELIVER_ACTION) return
        val text = "Unsupported MMS received. This text-only release does not decode or persist its payload; make an MMS-capable app the default before receiving MMS."
        val indexed = MessageStore(context).recordUnsupportedContent(text)
        MessageNotifier(context).notify(indexed)
        Toast.makeText(context, text, Toast.LENGTH_LONG).show()
    }
}
