package no.hugin.titansms.protocol

import org.junit.Assert.*
import org.junit.Test

class HubProtocolTest {
    @Test fun normalSmsDoesNotActivateHubParsing() {
        assertNull(RoutingLogic.classify("+4722222222", "+4711111111", "(tg/nikolai #184)\nHello"))
    }

    @Test fun onlyConfiguredNormalizedHubActivatesParsing() {
        val parsed = RoutingLogic.classify("+4711111111", "+4711111111", "(tg/nikolai #184)\nHello")
        assertTrue(parsed is HubEnvelope.Routed)
    }

    @Test fun virtualConversationsRemainSeparate() {
        val nikolai = HubProtocol.parse("(tg/nikolai #184)\nAre you coming?") as HubEnvelope.Routed
        val family = HubProtocol.parse("(tg/family #185)\nAnna: Dinner at 17?") as HubEnvelope.Routed
        assertNotEquals(nikolai.alias, family.alias)
    }

    @Test fun newMessageGetsAliasPrefixAndKeepsNewlines() {
        assertEquals("tg/nikolai First line\nsecond line", RoutingLogic.transportBody("tg/nikolai", "First line\nsecond line", null))
    }

    @Test fun explicitReplyKeepsSelectedReference() {
        val selected = 184L
        // Arrival of another message does not participate in envelope construction.
        HubProtocol.parse("(tg/family #999)\nLater arrival")
        assertEquals("#184 Yes", RoutingLogic.transportBody("tg/nikolai", "Yes", selected))
    }

    @Test fun malformedHeadersRemainUnknownWithRawText() {
        val raw = "prefix (tg/nikolai #184)\nHello"
        assertEquals(HubEnvelope.Unknown(raw), HubProtocol.parse(raw))
    }

    @Test fun sameAliasAndReferenceFromDifferentHubsHaveDifferentIdentity() {
        val a = ChunkIdentity("+471", "tg/family", 4, 2)
        val b = ChunkIdentity("+472", "tg/family", 4, 2)
        assertNotEquals(a, b)
        assertNotEquals(RoutingLogic.scopeKey(a.hubKey, a.alias), RoutingLogic.scopeKey(b.hubKey, b.alias))
    }

    @Test fun duplicateAndOutOfOrderChunksAssembleOnce() {
        val accumulator = ChunkAccumulator()
        val key = ChunkIdentity("+471", "tg/nikolai", 184, 3)
        assertEquals(setOf(1, 3), accumulator.add(key, 2, "middle ").missing)
        accumulator.add(key, 1, "first ")
        accumulator.add(key, 2, "duplicate ignored")
        val complete = accumulator.add(key, 3, "last")
        assertTrue(complete.complete)
        assertEquals("first middle last", complete.body)
    }

    @Test fun missingChunksRemainExplicitlyIncomplete() {
        val result = ChunkAccumulator().add(ChunkIdentity("+471", "tg/family", 185, 3), 2, "middle")
        assertFalse(result.complete)
        assertEquals(setOf(1, 3), result.missing)
    }

    @Test fun invalidChunkMetadataAndCaseAreHandledStrictly() {
        assertTrue(HubProtocol.parse("(tg/a #1 3/2)\nbad") is HubEnvelope.Unknown)
        assertEquals("tg/nikolai", (HubProtocol.parse("(TG/NIKOLAI #1)\nok") as HubEnvelope.Routed).alias)
    }

    @Test fun knownStatusIsParsedButNotCorrelatedToAnOutgoingMessage() {
        val parsed = HubProtocol.parse("(hub) Sent to tg/nikolai.") as HubEnvelope.Hub
        assertEquals(HubStatus.Kind.SENT, parsed.status?.kind)
        assertEquals("tg/nikolai", parsed.status?.alias)
    }

    @Test fun legacyBracketedEnvelopeStillParses() {
        val routed = HubProtocol.parse("[tg/nikolai #184]\nHello") as HubEnvelope.Routed
        val hub = HubProtocol.parse("[hub] Sent to tg/nikolai.") as HubEnvelope.Hub
        assertEquals("tg/nikolai", routed.alias)
        assertEquals(HubStatus.Kind.SENT, hub.status?.kind)
    }
}
