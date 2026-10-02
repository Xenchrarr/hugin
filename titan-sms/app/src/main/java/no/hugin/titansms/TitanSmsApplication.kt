package no.hugin.titansms

import android.app.Application
import no.hugin.titansms.data.MessageStore

class TitanSmsApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Runs once per process, unlike Activity.onCreate during rotation.
        MessageStore(this).recoverInterruptedSends()
    }
}
