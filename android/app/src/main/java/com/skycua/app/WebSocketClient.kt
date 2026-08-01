package com.skycua.app

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

data class AgentState(
    val app: String = "Finder",
    val screenshot: String? = null,
    val text: String = "",
    val apps: String = "",
    val log: List<Map<String, Any>> = emptyList(),
    val connected: Boolean = false,
    val connecting: Boolean = false,
    val error: String? = null,
    val chatMessages: List<ChatMessage> = emptyList(),
    val chatThinking: Boolean = false
)

data class ChatMessage(
    val role: String, // "user" or "assistant"
    val text: String
)

class WebSocketClient {
    private var webSocket: WebSocket? = null
    private val client: OkHttpClient = run {
        val trustAllCerts = arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        })
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, trustAllCerts, SecureRandom())
        OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .pingInterval(30, TimeUnit.SECONDS)
            .sslSocketFactory(sslContext.socketFactory, trustAllCerts[0] as X509TrustManager)
            .hostnameVerifier { _, _ -> true }
            .build()
    }
    private val gson = Gson()

    private val _state = MutableStateFlow(AgentState())
    val state: StateFlow<AgentState> = _state.asStateFlow()

    private val _messages = MutableSharedFlow<String>()
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    fun connect(url: String) {
        _state.value = _state.value.copy(connecting = true, error = null)
        val wsUrl = when {
            url.startsWith("wss://") -> url
            url.startsWith("ws://") -> "wss://" + url.removePrefix("ws://")
            url.startsWith("https://") -> "wss://" + url.removePrefix("https://")
            url.startsWith("http://") -> "wss://" + url.removePrefix("http://")
            else -> "wss://$url"
        }
        Log.d("SkyCUA", "Connecting to $wsUrl")
        val request = Request.Builder()
            .url(wsUrl)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("SkyCUA", "Connected to $wsUrl")
                _state.value = _state.value.copy(connected = true, error = null)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JsonParser.parseString(text).asJsonObject
                    val type = json.get("type")?.asString ?: return

                    when (type) {
                        "screenshot" -> {
                            _state.value = _state.value.copy(
                                app = json.get("app")?.asString ?: _state.value.app,
                                screenshot = json.get("screenshot")?.asString,
                                text = json.get("text")?.asString ?: ""
                            )
                        }
                        "state" -> {
                            _state.value = _state.value.copy(
                                app = json.get("app")?.asString ?: _state.value.app,
                                screenshot = json.get("screenshot")?.asString,
                                text = json.get("text")?.asString ?: "",
                                apps = json.get("apps")?.asString ?: ""
                            )
                        }
                        "apps" -> {
                            _state.value = _state.value.copy(
                                apps = json.get("apps")?.asString ?: ""
                            )
                        }
                        "chat_response" -> {
                            val text = json.get("text")?.asString ?: ""
                            _state.value = _state.value.copy(
                                chatMessages = _state.value.chatMessages + ChatMessage("assistant", text),
                                chatThinking = false
                            )
                        }
                        "chat_thinking" -> {
                            _state.value = _state.value.copy(chatThinking = true)
                        }
                        "chat_cleared" -> {
                            _state.value = _state.value.copy(chatMessages = emptyList())
                        }
                    }
                } catch (e: Exception) {
                    Log.e("SkyCUA", "Parse error: ${e.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                _state.value = _state.value.copy(connected = false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("SkyCUA", "Connection failed: ${t.message}")
                _state.value = _state.value.copy(connected = false, error = t.message)
            }
        })
    }

    fun setApp(app: String) {
        webSocket?.send(gson.toJson(mapOf("type" to "set_app", "app" to app)))
    }

    fun click(elementIndex: String) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "click",
            "args" to mapOf("element_index" to elementIndex)
        )))
    }

    fun typeText(text: String) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "type_text",
            "args" to mapOf("text" to text)
        )))
    }

    fun pressKey(key: String) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "press_key",
            "args" to mapOf("key" to key)
        )))
    }

    fun scroll(elementIndex: String, direction: String, pages: Int = 1) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "scroll",
            "args" to mapOf(
                "element_index" to elementIndex,
                "direction" to direction,
                "pages" to pages
            )
        )))
    }

    fun requestScreenshot() {
        webSocket?.send(gson.toJson(mapOf("type" to "screenshot")))
    }

    fun listApps() {
        webSocket?.send(gson.toJson(mapOf("type" to "list_apps")))
    }

    fun clickCoordinate(x: Float, y: Float) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "click",
            "args" to mapOf("x" to x.toInt(), "y" to y.toInt())
        )))
    }

    fun swipe(x1: Float, y1: Float, x2: Float, y2: Float) {
        webSocket?.send(gson.toJson(mapOf(
            "type" to "action",
            "tool" to "drag",
            "args" to mapOf(
                "from_x" to x1.toInt(), "from_y" to y1.toInt(),
                "to_x" to x2.toInt(), "to_y" to y2.toInt()
            )
        )))
    }

    fun sendChat(text: String) {
        _state.value = _state.value.copy(
            chatMessages = _state.value.chatMessages + ChatMessage("user", text)
        )
        webSocket?.send(gson.toJson(mapOf("type" to "chat", "text" to text)))
    }

    fun clearChat() {
        webSocket?.send(gson.toJson(mapOf("type" to "chat_clear")))
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        _state.value = AgentState()
    }
}
