package no.hugin.titansms.phone

import android.telephony.PhoneNumberUtils

object PhoneNumbers {
    /** Comparison key only. The original address always remains in the SMS provider. */
    fun normalize(value: String): String {
        val normalized = PhoneNumberUtils.normalizeNumber(value)
        return if (normalized.startsWith("00")) "+${normalized.drop(2)}" else normalized
    }

    fun same(a: String?, b: String?): Boolean {
        if (a.isNullOrBlank() || b.isNullOrBlank()) return false
        val na = normalize(a)
        val nb = normalize(b)
        return na == nb || PhoneNumberUtils.compare(a, b)
    }
}
