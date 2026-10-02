package no.hugin.titansms.model

enum class ConversationKind { NORMAL, VIRTUAL, HUB }

enum class Direction { INCOMING, OUTGOING, SYSTEM }

enum class SendState {
    RECEIVED, QUEUED, SENDING, SMS_SENT, DELIVERY_CONFIRMED, FAILED, DELIVERY_UNKNOWN
}

data class Conversation(
    val id: Long,
    val kind: ConversationKind,
    val address: String,
    val alias: String?,
    val title: String,
    val lastBody: String,
    val lastAt: Long,
    val unread: Int,
)

data class Message(
    val id: Long,
    val conversationId: Long,
    val direction: Direction,
    val body: String,
    val rawBody: String,
    val timestamp: Long,
    val reference: Long?,
    val replyToReference: Long?,
    val state: SendState,
    val stateDetail: String?,
    val incomplete: Boolean,
    val partsReceived: Int?,
    val partsTotal: Int?,
)

fun friendlyAlias(alias: String): String {
    val (service, name) = alias.split('/', limit = 2).let { parts -> parts[0] to parts.getOrElse(1) { parts[0] } }
    val friendlyName = name.replace('-', ' ').replace('_', ' ')
        .split(' ').joinToString(" ") { it.replaceFirstChar(Char::uppercase) }
    val friendlyService = when (service.lowercase()) {
        "tg" -> "Telegram"
        "fb" -> "Messenger"
        "rns" -> "Reticulum"
        else -> service.replaceFirstChar(Char::uppercase)
    }
    return "$friendlyName · $friendlyService"
}
