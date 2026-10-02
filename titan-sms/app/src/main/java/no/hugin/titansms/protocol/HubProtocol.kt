package no.hugin.titansms.protocol

/** Pure, Android-independent representation of the SMS hub wire protocol. */
sealed interface HubEnvelope {
    val raw: String

    data class Routed(
        val alias: String,
        val reference: Long,
        val body: String,
        val part: Int? = null,
        val partCount: Int? = null,
        override val raw: String,
    ) : HubEnvelope

    data class Hub(
        val body: String,
        val status: HubStatus? = null,
        val part: Int? = null,
        val partCount: Int? = null,
        override val raw: String,
    ) : HubEnvelope

    data class Unknown(override val raw: String) : HubEnvelope
}

data class HubStatus(val kind: Kind, val alias: String, val detail: String? = null) {
    enum class Kind { SENT, QUEUED, UNCERTAIN, FAILED }
}

object HubProtocol {
    const val VERSION = 1

    // Mirrors sms-bot/src/conversation_routing.py. Keep this deliberately narrow.
    private const val ALIAS = "[a-z][a-z0-9_-]{0,9}/[a-z0-9][a-z0-9_-]{0,17}"
    private val routed = Regex(
        "^\\(($ALIAS) #(\\d+)(?: ([1-9]\\d*)/([1-9]\\d*))?\\)\\r?\\n([\\s\\S]*)$",
        RegexOption.IGNORE_CASE,
    )
    private val legacyRouted = Regex(
        "^\\[($ALIAS) #(\\d+)(?: ([1-9]\\d*)/([1-9]\\d*))?]\\r?\\n([\\s\\S]*)$",
        RegexOption.IGNORE_CASE,
    )
    private val hub = Regex("^\\(hub(?: ([1-9]\\d*)/([1-9]\\d*))?\\)(?: |\\r?\\n)([\\s\\S]*)$", RegexOption.IGNORE_CASE)
    private val legacyHub = Regex("^\\[hub(?: ([1-9]\\d*)/([1-9]\\d*))?](?: |\\r?\\n)([\\s\\S]*)$", RegexOption.IGNORE_CASE)
    private val sent = Regex("^Sent to ($ALIAS)\\.$", RegexOption.IGNORE_CASE)
    private val queued = Regex("^Queued for ($ALIAS)\\.$", RegexOption.IGNORE_CASE)
    private val uncertain = Regex("^Send to ($ALIAS) is uncertain; it will not be retried automatically\\.$", RegexOption.IGNORE_CASE)
    private val failed = Regex("^Could not send to ($ALIAS): ([\\s\\S]+)\\.$", RegexOption.IGNORE_CASE)

    fun parse(raw: String): HubEnvelope {
        (routed.matchEntire(raw) ?: legacyRouted.matchEntire(raw))?.let { match ->
            val part = match.groupValues[3].takeIf(String::isNotEmpty)?.toIntOrNull()
            val total = match.groupValues[4].takeIf(String::isNotEmpty)?.toIntOrNull()
            if ((part == null) != (total == null) || part != null && (part > total!! || total > 999)) {
                return HubEnvelope.Unknown(raw)
            }
            val reference = match.groupValues[2].toLongOrNull() ?: return HubEnvelope.Unknown(raw)
            return HubEnvelope.Routed(
                alias = match.groupValues[1].lowercase(),
                reference = reference,
                body = match.groupValues[5],
                part = part,
                partCount = total,
                raw = raw,
            )
        }
        (hub.matchEntire(raw) ?: legacyHub.matchEntire(raw))?.let { match ->
            val part = match.groupValues[1].takeIf(String::isNotEmpty)?.toIntOrNull()
            val total = match.groupValues[2].takeIf(String::isNotEmpty)?.toIntOrNull()
            if ((part == null) != (total == null) || part != null && (part > total!! || total > 999)) {
                return HubEnvelope.Unknown(raw)
            }
            val body = match.groupValues[3]
            return HubEnvelope.Hub(body, parseStatus(body), part, total, raw)
        }
        return HubEnvelope.Unknown(raw)
    }

    fun outgoing(alias: String, body: String): String {
        require(Regex("^$ALIAS$").matches(alias)) { "Invalid hub alias" }
        require(body.isNotBlank()) { "Message body is empty" }
        return "${alias.lowercase()} $body"
    }

    fun reply(reference: Long, body: String): String {
        require(reference >= 0) { "Invalid reference" }
        require(body.isNotBlank()) { "Message body is empty" }
        return "#$reference $body"
    }

    fun isValidAlias(alias: String): Boolean = Regex("^$ALIAS$").matches(alias)

    private fun parseStatus(body: String): HubStatus? {
        sent.matchEntire(body)?.let { return HubStatus(HubStatus.Kind.SENT, it.groupValues[1].lowercase()) }
        queued.matchEntire(body)?.let { return HubStatus(HubStatus.Kind.QUEUED, it.groupValues[1].lowercase()) }
        uncertain.matchEntire(body)?.let { return HubStatus(HubStatus.Kind.UNCERTAIN, it.groupValues[1].lowercase()) }
        failed.matchEntire(body)?.let { return HubStatus(HubStatus.Kind.FAILED, it.groupValues[1].lowercase(), it.groupValues[2]) }
        return null
    }
}
