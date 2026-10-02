package no.hugin.titansms.sms

import android.app.IntentService
import android.content.Intent

@Suppress("DEPRECATION")
class RespondViaMessageService : IntentService("respond-via-message") {
    override fun onHandleIntent(intent: Intent?) {
        val request = intent ?: return
        val address = request.data?.schemeSpecificPart ?: return
        val body = request.getStringExtra(Intent.EXTRA_TEXT) ?: return
        SmsSender(this).send(SendRequest(address = address, displayBody = body))
    }
}
