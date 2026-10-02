package no.hugin.titansms.protocol

data class ChunkIdentity(val hubKey: String, val alias: String, val reference: Long, val partCount: Int)
data class ChunkAssembly(val body: String, val received: Set<Int>, val missing: Set<Int>, val complete: Boolean)

/** Small pure components used by both tests and the Android persistence boundary. */
object RoutingLogic {
    fun classify(senderKey: String, configuredHubKey: String, raw: String): HubEnvelope? =
        if (configuredHubKey.isNotBlank() && senderKey == configuredHubKey) HubProtocol.parse(raw) else null

    fun transportBody(alias: String, body: String, replyReference: Long?): String =
        if (replyReference == null) HubProtocol.outgoing(alias, body) else HubProtocol.reply(replyReference, body)

    fun scopeKey(hubKey: String, alias: String): String = "hub:$hubKey:${alias.lowercase()}"
}

class ChunkAccumulator {
    private val parts = mutableMapOf<ChunkIdentity, MutableMap<Int, String>>()

    fun add(identity: ChunkIdentity, part: Int, body: String): ChunkAssembly {
        require(part in 1..identity.partCount)
        val collected = parts.getOrPut(identity) { mutableMapOf() }
        if (!collected.containsKey(part)) collected[part] = body
        val received = collected.keys.toSortedSet()
        val missing = (1..identity.partCount).filterNot(received::contains).toSortedSet()
        return ChunkAssembly(
            body = (1..identity.partCount).mapNotNull(collected::get).joinToString(""),
            received = received,
            missing = missing,
            complete = missing.isEmpty(),
        )
    }
}
