package no.hugin.titansms.ui

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationManager
import android.app.role.RoleManager
import android.content.ContentUris
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.provider.Telephony
import android.telephony.SubscriptionInfo
import android.telephony.SubscriptionManager
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.*
import no.hugin.titansms.data.AppPreferences
import no.hugin.titansms.data.HistoryImporter
import no.hugin.titansms.data.MessageStore
import no.hugin.titansms.model.*
import no.hugin.titansms.sms.SmsSender
import java.text.DateFormat
import java.util.Date
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private lateinit var store: MessageStore
    private lateinit var prefs: AppPreferences
    private var openConversationId: Long? = null
    private var composer: EditText? = null
    private var replyReference: Long? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = MessageStore(this)
        prefs = AppPreferences(this)
        openConversationId = intent.getLongExtra(OPEN_CONVERSATION, -1).takeIf { it >= 0 }
        if (openConversationId != null) showConversation(openConversationId!!) else showConversationList()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getLongExtra(OPEN_CONVERSATION, -1).takeIf { it >= 0 }?.let { showConversation(it) }
    }

    override fun onResume() {
        super.onResume()
        if (openConversationId == null) showConversationList() else refreshOpenConversation()
    }

    override fun onBackPressed() {
        if (openConversationId != null) showConversationList() else super.onBackPressed()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN && event.isCtrlPressed) {
            when (event.keyCode) {
                KeyEvent.KEYCODE_L -> {
                    composer?.requestFocus(); showKeyboard(composer); return true
                }
                KeyEvent.KEYCODE_ENTER -> {
                    composer?.let { sendCurrentMessage() }; return true
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    private fun showConversationList() {
        openConversationId = null
        composer = null
        replyReference = null
        title = "Titan SMS"
        val root = vertical()
        val toolbar = horizontal().apply {
            addView(label("Titan SMS", 20f), weightedWidth())
            addView(button("New", "Start a new SMS or hub conversation") { showNewConversationDialog() })
            addView(button("Settings", "Open SMS role, hub, SIM and privacy settings") { showSettingsDialog() })
        }
        root.addView(toolbar)
        val warnings = statusWarnings()
        if (warnings.isNotEmpty()) {
            root.addView(label(warnings.joinToString("\n"), 13f).apply {
                setTextColor(Color.rgb(150, 60, 0)); setPadding(dp(8), dp(5), dp(8), dp(5))
            })
        }
        val conversations = store.conversations()
        val list = ListView(this).apply {
            isFocusable = true
            choiceMode = ListView.CHOICE_MODE_SINGLE
            adapter = object : ArrayAdapter<Conversation>(this@MainActivity, android.R.layout.simple_list_item_2, android.R.id.text1, conversations) {
                override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                    val view = super.getView(position, convertView, parent)
                    val item = getItem(position)!!
                    view.findViewById<TextView>(android.R.id.text1).text = buildString {
                        append(item.title); if (item.unread > 0) append("  (${item.unread})")
                    }
                    view.findViewById<TextView>(android.R.id.text2).text = "${shortTime(item.lastAt)}  ${item.lastBody.replace('\n', ' ').take(55)}"
                    view.contentDescription = "${item.title}, ${item.unread} unread. ${item.lastBody}"
                    return view
                }
            }
            setOnItemClickListener { _, _, position, _ -> showConversation(conversations[position].id) }
        }
        root.addView(list, weightedHeight())
        setContentView(root)
        toolbar.getChildAt(1).requestFocus()
    }

    private fun showConversation(id: Long) {
        val conversation = store.conversation(id) ?: return showConversationList()
        openConversationId = id
        store.markRead(id)
        if (SmsSender.isDefaultSmsApp(this)) {
            val read = ContentValues().apply { put(Telephony.Sms.READ, 1); put(Telephony.Sms.SEEN, 1) }
            store.providerIds(id).forEach { providerId ->
                runCatching { contentResolver.update(ContentUris.withAppendedId(Telephony.Sms.CONTENT_URI, providerId), read, null, null) }
            }
        }
        getSystemService(NotificationManager::class.java).cancel(id.hashCode())
        title = conversation.title
        val root = vertical()
        val back = button("‹", "Back to conversations") { showConversationList() }
        val header = horizontal().apply {
            addView(back)
            addView(label(conversation.title, 18f), weightedWidth())
        }
        root.addView(header)

        val messages = store.messages(id)
        val list = ListView(this).apply {
            transcriptMode = ListView.TRANSCRIPT_MODE_ALWAYS_SCROLL
            isStackFromBottom = true
            adapter = object : ArrayAdapter<Message>(this@MainActivity, android.R.layout.simple_list_item_2, android.R.id.text1, messages) {
                override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                    val view = super.getView(position, convertView, parent)
                    val message = getItem(position)!!
                    val prefix = when (message.direction) {
                        Direction.INCOMING -> "←"
                        Direction.OUTGOING -> "→"
                        Direction.SYSTEM -> "•"
                    }
                    view.findViewById<TextView>(android.R.id.text1).text = "$prefix ${message.body}"
                    view.findViewById<TextView>(android.R.id.text2).text = buildString {
                        append(shortTime(message.timestamp))
                        message.reference?.let { append("  #$it") }
                        if (message.direction == Direction.OUTGOING) append("  ${stateLabel(message.state)}")
                        if (message.incomplete) append("  incomplete")
                    }
                    view.contentDescription = "${message.direction.name.lowercase()}: ${message.body}"
                    return view
                }
            }
            setOnItemClickListener { _, _, position, _ -> showMessageActions(conversation, messages[position]) }
        }
        root.addView(list, weightedHeight())

        val replyBar = TextView(this).apply {
            visibility = View.GONE; setPadding(dp(8), dp(3), dp(8), dp(3)); setTextColor(Color.rgb(30, 80, 130))
        }
        root.addView(replyBar)
        val composeRow = horizontal()
        composer = EditText(this).apply {
            this.id = View.generateViewId(); hint = if (conversation.kind == ConversationKind.HUB) "Command or message" else "Message"
            minLines = 1; maxLines = 4; isSingleLine = false; gravity = Gravity.TOP
            contentDescription = "Message composer. Enter makes a new line. Control Enter sends."
        }
        val send = button("Send", "Send message") { sendCurrentMessage() }.apply { this.id = View.generateViewId() }
        composer!!.nextFocusForwardId = send.id
        send.nextFocusForwardId = composer!!.id
        composeRow.addView(composer, weightedWidth())
        composeRow.addView(send)
        root.addView(composeRow)
        setContentView(root)
        back.requestFocus()
        if (messages.isNotEmpty()) list.setSelection(messages.lastIndex)

        // Kept as a tag so the reply action can update the visible, rebuilt bar.
        replyBar.tag = REPLY_BAR_TAG
    }

    private fun showMessageActions(conversation: Conversation, message: Message) {
        val actions = mutableListOf("Details")
        if (conversation.kind == ConversationKind.VIRTUAL && message.reference != null) actions.add(0, "Reply to #${message.reference}")
        if (message.direction == Direction.OUTGOING && message.state in setOf(SendState.FAILED, SendState.DELIVERY_UNKNOWN)) {
            actions.add("Retry deliberately")
        }
        AlertDialog.Builder(this).setTitle("Message").setItems(actions.toTypedArray()) { _, which ->
            if (actions[which].startsWith("Reply")) {
                replyReference = message.reference
                findViewByTag<TextView>(REPLY_BAR_TAG)?.apply {
                    text = "Replying to #${message.reference} — Backspace body normally; tap here to cancel"
                    visibility = View.VISIBLE
                    setOnClickListener { replyReference = null; visibility = View.GONE }
                }
                composer?.requestFocus(); showKeyboard(composer)
            } else if (actions[which] == "Retry deliberately") {
                AlertDialog.Builder(this).setTitle("Retry this SMS?")
                    .setMessage("The earlier attempt may have reached the carrier or hub. Retrying creates a new SMS and can duplicate the message.")
                    .setNegativeButton("Cancel", null).setPositiveButton("Retry") { _, _ -> retryMessage(conversation, message) }.show()
            } else {
                AlertDialog.Builder(this).setTitle("Message details").setMessage(buildString {
                    append("State: ${stateLabel(message.state)}\n")
                    message.stateDetail?.let { append("Detail: $it\n") }
                    message.reference?.let { append("Reference: #$it\n") }
                    message.replyToReference?.let { append("Reply to: #$it\n") }
                    append("\nSMS transport body:\n${message.rawBody}")
                }).setPositiveButton("Close", null).show()
            }
        }.show()
    }

    private fun retryMessage(conversation: Conversation, message: Message) {
        thread(name = "sms-retry") {
            val result = SmsSender(this).sendToConversation(conversation, message.body, message.replyToReference)
            runOnUiThread {
                result.onFailure { Toast.makeText(this, it.message ?: "Retry failed", Toast.LENGTH_LONG).show() }
                showConversation(conversation.id)
            }
        }
    }

    private fun sendCurrentMessage() {
        val id = openConversationId ?: return
        val conversation = store.conversation(id) ?: return
        val field = composer ?: return
        val body = field.text.toString()
        if (body.isBlank()) { field.error = "Write a message first"; return }
        val reference = replyReference
        field.isEnabled = false
        thread(name = "sms-send") {
            val result = SmsSender(this).sendToConversation(conversation, body, reference)
            runOnUiThread {
                field.isEnabled = true
                result.onSuccess {
                    field.text.clear(); replyReference = null; showConversation(id); composer?.requestFocus()
                }.onFailure { field.error = it.message ?: "Could not send" }
            }
        }
    }

    private fun showNewConversationDialog() {
        val root = vertical(padding = 16)
        val normalTypeId = View.generateViewId()
        val hubTypeId = View.generateViewId()
        val hubCommandsTypeId = View.generateViewId()
        val types = RadioGroup(this).apply {
            orientation = RadioGroup.VERTICAL
            addView(RadioButton(this@MainActivity).apply { id = normalTypeId; text = "SMS"; isChecked = true })
            addView(RadioButton(this@MainActivity).apply { id = hubTypeId; text = "Hub chat" })
            addView(RadioButton(this@MainActivity).apply { id = hubCommandsTypeId; text = "Hub commands" })
        }
        val target = EditText(this).apply { hint = "Phone number"; isSingleLine = true }
        types.setOnCheckedChangeListener { _, checked ->
            target.visibility = if (checked == hubCommandsTypeId) View.GONE else View.VISIBLE
            target.hint = if (checked == hubTypeId) "Alias, e.g. tg/nikolai" else "Phone number"
        }
        root.addView(types); root.addView(target)
        val dialog = AlertDialog.Builder(this).setTitle("New conversation").setView(root)
            .setNegativeButton("Cancel", null).setPositiveButton("Open", null).create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                runCatching {
                    if (types.checkedRadioButtonId == hubTypeId) {
                        store.ensureVirtualConversation(prefs.hubNumber, target.text.toString().trim())
                    } else if (types.checkedRadioButtonId == hubCommandsTypeId) {
                        store.ensureHubConversation(prefs.hubNumber)
                    } else {
                        require(target.text.toString().isNotBlank()) { "Enter a phone number" }
                        store.ensureNormalConversation(target.text.toString().trim())
                    }
                }.onSuccess { dialog.dismiss(); showConversation(it) }
                    .onFailure { target.error = it.message }
            }
        }
        dialog.show()
    }

    private fun showSettingsDialog() {
        val root = vertical(padding = 16)
        val roleButton = button(if (SmsSender.isDefaultSmsApp(this)) "Default SMS role granted" else "Make default SMS app", "Request the Android SMS role") { explainAndRequestSmsRole() }
        roleButton.isEnabled = !SmsSender.isDefaultSmsApp(this) && SmsSender.canRequestRole(this)
        val permissionsButton = button("Grant SMS permissions", "Request SMS and phone permissions") { requestRequiredPermissions() }
        val hub = EditText(this).apply { hint = "Hub phone number"; setText(prefs.hubNumber); isSingleLine = true }
        val subscriptions = activeSubscriptions()
        val sim = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item,
                listOf("No SIM selected") + subscriptions.map { "${it.displayName} · SIM ${it.simSlotIndex + 1}" })
            setSelection(subscriptions.indexOfFirst { it.subscriptionId == prefs.subscriptionId }.let { if (it < 0) 0 else it + 1 })
            contentDescription = "Default sending SIM"
        }
        val privacy = CheckBox(this).apply { text = "Hide message content in notifications"; isChecked = prefs.hideNotificationContent }
        val import = button("Import SMS history", "Import new provider records without sending") { runImport(false) }
        val rebuild = button("Re-index raw SMS", "Rebuild local conversations without sending") { confirmReindex() }
        root.addView(roleButton); root.addView(permissionsButton)
        root.addView(label("Hub number", 13f)); root.addView(hub)
        root.addView(label("Sending SIM", 13f)); root.addView(sim)
        root.addView(privacy); root.addView(import); root.addView(rebuild)
        AlertDialog.Builder(this).setTitle("Settings").setView(root).setNegativeButton("Cancel", null)
            .setPositiveButton("Save") { _, _ ->
                prefs.hubNumber = hub.text.toString()
                prefs.subscriptionId = subscriptions.getOrNull(sim.selectedItemPosition - 1)?.subscriptionId ?: -1
                prefs.hideNotificationContent = privacy.isChecked
                showConversationList()
            }.show()
    }

    private fun requestSmsRole() {
        if (Build.VERSION.SDK_INT >= 29) {
            val manager = getSystemService(RoleManager::class.java)
            startActivityForResult(manager.createRequestRoleIntent(RoleManager.ROLE_SMS), ROLE_REQUEST)
        } else {
            startActivityForResult(Intent(Telephony.Sms.Intents.ACTION_CHANGE_DEFAULT).putExtra(Telephony.Sms.Intents.EXTRA_PACKAGE_NAME, packageName), ROLE_REQUEST)
        }
    }

    private fun explainAndRequestSmsRole() {
        AlertDialog.Builder(this).setTitle("Default SMS role required")
            .setMessage("Android delivers SMS to one default handler. Titan SMS needs this role to receive messages while closed, write readable raw messages to the system SMS provider, and send through the selected SIM. You can refuse and continue browsing already indexed local data; sending and background reception stay disabled.")
            .setNegativeButton("Not now", null).setPositiveButton("Continue") { _, _ -> requestSmsRole() }.show()
    }

    private fun requestRequiredPermissions() {
        val permissions = mutableListOf(Manifest.permission.READ_SMS, Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS, Manifest.permission.RECEIVE_MMS, Manifest.permission.READ_PHONE_STATE)
        if (Build.VERSION.SDK_INT >= 33) permissions += Manifest.permission.POST_NOTIFICATIONS
        requestPermissions(permissions.toTypedArray(), PERMISSION_REQUEST)
    }

    private fun activeSubscriptions(): List<SubscriptionInfo> {
        if (checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) return emptyList()
        return getSystemService(SubscriptionManager::class.java).activeSubscriptionInfoList.orEmpty()
    }

    private fun runImport(rebuild: Boolean) {
        if (checkSelfPermission(Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Grant SMS permissions first", Toast.LENGTH_LONG).show(); return
        }
        Toast.makeText(this, if (rebuild) "Re-indexing…" else "Importing…", Toast.LENGTH_SHORT).show()
        thread(name = "sms-import") {
            val result = runCatching { HistoryImporter(this).run(rebuild) }
            runOnUiThread {
                result.onSuccess { Toast.makeText(this, "Imported ${it.imported}; already indexed ${it.skipped}", Toast.LENGTH_LONG).show(); showConversationList() }
                    .onFailure { Toast.makeText(this, it.message ?: "Import failed", Toast.LENGTH_LONG).show() }
            }
        }
    }

    private fun confirmReindex() {
        if (store.hasActiveSends()) {
            Toast.makeText(this, "Wait for active sent-result callbacks before re-indexing", Toast.LENGTH_LONG).show()
            return
        }
        AlertDialog.Builder(this).setTitle("Re-index raw SMS?")
            .setMessage("This rebuilds only Titan SMS's local conversation index from Android's SMS provider. It never sends messages or alters the raw SMS records.")
            .setNegativeButton("Cancel", null).setPositiveButton("Re-index") { _, _ -> runImport(true) }.show()
    }

    private fun statusWarnings(): List<String> = buildList {
        if (!SmsSender.isDefaultSmsApp(this@MainActivity)) add("Not the default SMS app. Receiving, provider writes, and sending are disabled until the SMS role is granted.")
        if (checkSelfPermission(Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) add("SMS permission was not granted. Import and message access remain disabled.")
        if (prefs.hubNumber.isBlank()) add("Hub number is not configured; all senders remain normal SMS conversations.")
        if (prefs.subscriptionId < 0) add("No sending SIM is selected.")
        else if (activeSubscriptions().none { it.subscriptionId == prefs.subscriptionId }) add("The selected SIM is unavailable; sending will not switch SIM automatically.")
    }

    private fun refreshOpenConversation() { openConversationId?.let(::showConversation) }

    private fun vertical(padding: Int = 4) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(padding), dp(padding), dp(padding), dp(padding))
    }
    private fun horizontal() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
    private fun label(text: String, size: Float) = TextView(this).apply { this.text = text; textSize = size; setPadding(dp(6), dp(5), dp(6), dp(5)) }
    private fun button(text: String, description: String, action: () -> Unit) = Button(this).apply { this.text = text; contentDescription = description; minWidth = 0; setOnClickListener { action() } }
    private fun weightedWidth() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
    private fun weightedHeight() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun shortTime(value: Long): String = if (value == 0L) "" else DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(value))
    private fun stateLabel(state: SendState) = when (state) {
        SendState.RECEIVED -> "received"; SendState.QUEUED -> "queued locally"; SendState.SENDING -> "sending"
        SendState.SMS_SENT -> "SMS sent"; SendState.DELIVERY_CONFIRMED -> "SMS delivery confirmed"
        SendState.FAILED -> "failed"; SendState.DELIVERY_UNKNOWN -> "delivery unconfirmed"
    }
    private fun showKeyboard(view: View?) { view ?: return; getSystemService(InputMethodManager::class.java).showSoftInput(view, InputMethodManager.SHOW_IMPLICIT) }

    @Suppress("UNCHECKED_CAST")
    private fun <T : View> findViewByTag(tag: String): T? = window.decorView.findViewWithTag(tag) as? T

    companion object {
        const val OPEN_CONVERSATION = "open_conversation"
        private const val ROLE_REQUEST = 10
        private const val PERMISSION_REQUEST = 11
        private const val REPLY_BAR_TAG = "reply_bar"
    }
}
