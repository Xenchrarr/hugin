package no.hugin.titansms.sms

import android.Manifest
import android.app.PendingIntent
import android.app.role.RoleManager
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Telephony
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import no.hugin.titansms.data.AppPreferences
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.model.Conversation
import no.hugin.titansms.model.ConversationKind
import no.hugin.titansms.phone.PhoneNumbers
import no.hugin.titansms.protocol.HubProtocol

data class SendRequest(
    val address: String,
    val displayBody: String,
    val alias: String? = null,
    val replyToReference: Long? = null,
)

class SmsSender(private val context: Context) {
    fun send(request: SendRequest): Result<Long> = runCatching {
        require(request.address.isNotBlank()) { "Recipient is empty" }
        require(request.displayBody.isNotBlank()) { "Message body is empty" }
        check(isDefaultSmsApp(context)) { "Titan SMS must be the default SMS app before sending" }
        check(context.checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED) {
            "SMS permission is not granted"
        }

        val prefs = AppPreferences(context)
        val subscriptionId = prefs.subscriptionId
        check(subscriptionId >= 0) { "Choose a sending SIM in Settings" }
        val subscriptions = context.getSystemService(SubscriptionManager::class.java)
            .activeSubscriptionInfoList.orEmpty()
        check(subscriptions.any { it.subscriptionId == subscriptionId }) {
            "The selected SIM is no longer available. Choose it again in Settings; no other SIM was used."
        }

        val rawBody = when {
            request.replyToReference != null -> HubProtocol.reply(request.replyToReference, request.displayBody)
            request.alias != null -> HubProtocol.outgoing(request.alias, request.displayBody)
            else -> request.displayBody
        }
        val now = System.currentTimeMillis()
        val providerValues = ContentValues().apply {
            put(Telephony.Sms.ADDRESS, request.address)
            put(Telephony.Sms.BODY, rawBody)
            put(Telephony.Sms.DATE, now)
            put(Telephony.Sms.READ, 1)
            put(Telephony.Sms.SEEN, 1)
            put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_OUTBOX)
            put("sub_id", subscriptionId)
            put("creator", context.packageName)
        }
        val providerUri = context.contentResolver.insert(Telephony.Sms.CONTENT_URI, providerValues)
            ?: error("Could not add the outgoing SMS to Android's SMS provider")
        val providerId = ContentUris.parseId(providerUri)
        val localId = MessageStore(context).recordOutgoing(
            providerId, request.address, rawBody, request.displayBody, now, prefs.hubNumber,
            request.alias, request.replyToReference,
        )

        try {
            val manager = SmsManager.getSmsManagerForSubscriptionId(subscriptionId)
            val parts = manager.divideMessage(rawBody)
            val sent = ArrayList<PendingIntent>(parts.size)
            val delivered = ArrayList<PendingIntent>(parts.size)
            parts.indices.forEach { index ->
                sent += resultIntent(localId, providerUri, "sent", index, parts.size)
                delivered += resultIntent(localId, providerUri, "delivery", index, parts.size)
            }
            MessageStore(context).markSending(localId)
            manager.sendMultipartTextMessage(request.address, null, parts, sent, delivered)
        } catch (failure: Exception) {
            MessageStore(context).markSendFailed(localId, failure.message ?: failure.javaClass.simpleName)
            context.contentResolver.update(providerUri, ContentValues().apply {
                put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_FAILED)
                put(Telephony.Sms.ERROR_CODE, -1)
            }, null, null)
            throw failure
        }
        localId
    }

    fun sendToConversation(conversation: Conversation, body: String, reference: Long? = null): Result<Long> {
        val prefs = AppPreferences(context)
        if (conversation.kind != ConversationKind.NORMAL) {
            if (conversation.address.isBlank()) return Result.failure(IllegalStateException("This system conversation is read-only"))
            if (!PhoneNumbers.same(conversation.address, prefs.hubNumber)) {
                return Result.failure(IllegalStateException("This chat belongs to a different hub number. Restore that hub setting or start a new chat."))
            }
        }
        return send(
            SendRequest(
                address = if (conversation.kind == ConversationKind.NORMAL) conversation.address else prefs.hubNumber,
                displayBody = body,
                alias = conversation.alias,
                replyToReference = reference,
            )
        )
    }

    private fun resultIntent(localId: Long, providerUri: Uri, stage: String, part: Int, total: Int): PendingIntent {
        val intent = Intent(context, SendResultReceiver::class.java).apply {
            action = "${context.packageName}.$stage.$localId.$part"
            putExtra(SendResultReceiver.MESSAGE_ID, localId)
            putExtra(SendResultReceiver.PROVIDER_URI, providerUri.toString())
            putExtra(SendResultReceiver.STAGE, stage)
            putExtra(SendResultReceiver.PART, part)
            putExtra(SendResultReceiver.TOTAL, total)
        }
        return PendingIntent.getBroadcast(
            context, (localId.hashCode() * 31 + part) * 31 + stage.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        fun isDefaultSmsApp(context: Context): Boolean =
            Telephony.Sms.getDefaultSmsPackage(context) == context.packageName

        fun canRequestRole(context: Context): Boolean {
            if (Build.VERSION.SDK_INT < 29) return true
            val role = context.getSystemService(RoleManager::class.java)
            return role.isRoleAvailable(RoleManager.ROLE_SMS)
        }
    }
}
