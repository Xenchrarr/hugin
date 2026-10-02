package no.hugin.titansms.notifications

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import no.hugin.titansms.data.AppPreferences
import no.hugin.titansms.data.IndexedMessage
import no.hugin.titansms.sms.NotificationReplyReceiver
import no.hugin.titansms.ui.MainActivity

class MessageNotifier(private val context: Context) {
    fun notify(message: IndexedMessage) {
        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "Messages", NotificationManager.IMPORTANCE_HIGH))
        }
        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(MainActivity.OPEN_CONVERSATION, message.conversationId)
        }
        val openIntent = PendingIntent.getActivity(
            context, message.conversationId.hashCode(), open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val replyIntent = Intent(context, NotificationReplyReceiver::class.java).apply {
            action = "${context.packageName}.reply.${message.conversationId}"
            putExtra(NotificationReplyReceiver.CONVERSATION_ID, message.conversationId)
        }
        val mutable = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
        val replyPending = PendingIntent.getBroadcast(
            context, message.conversationId.hashCode(), replyIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or mutable,
        )
        val remoteInput = RemoteInput.Builder(REPLY_TEXT).setLabel("Reply").build()
        val replyAction = Notification.Action.Builder(android.R.drawable.ic_menu_send, "Reply", replyPending)
            .addRemoteInput(remoteInput).build()
        val hidden = AppPreferences(context).hideNotificationContent
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(context, CHANNEL) else Notification.Builder(context)
        val notification = builder
            .setSmallIcon(android.R.drawable.sym_action_chat)
            .setContentTitle(message.title)
            .setContentText(if (hidden) "New message" else message.body)
            .setStyle(Notification.BigTextStyle().bigText(if (hidden) "New message" else message.body))
            .setContentIntent(openIntent)
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setVisibility(if (hidden) Notification.VISIBILITY_PRIVATE else Notification.VISIBILITY_PUBLIC)
            .addAction(replyAction)
            .build()
        manager.notify(message.conversationId.hashCode(), notification)
    }

    companion object {
        const val CHANNEL = "messages"
        const val REPLY_TEXT = "reply_text"
    }
}
