package com.skycua.app

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.flow.*
import okhttp3.*
import java.util.concurrent.TimeUnit

data class AgentState(
    val connected: Boolean = false,
    val app: String = "Finder",
    val text: String = "",
    val screenshot: String? = null,
    val chatMessages: List<ChatMessage> = emptyList(),
    val chatThinking: Boolean = false,
)

data class ChatMessage(val role: String, val text: String)

class WebSocketClient {
    private var ws: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()
    private val _state = MutableStateFlow(AgentState())
    val state = _state.asStateFlow()

    fun connect(url: String) {
        val wsUrl = when {
            url.startsWith("ws://") || url.startsWith("wss://") -> url
            url.contains("localhost") || url.contains("127.0.0.1") -> "ws://$url"
            else -> "wss://$url"
        }
        
        Log.d("SkyCUA", "Connecting to $wsUrl")
        _state.value = _state.value.copy(connected = false)
        
        ws = client.newWebSocket(Request.Builder().url(wsUrl).build(), object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                Log.d("SkyCUA", "Connected")
                _state.value = _state.value.copy(connected = true)
            }

            override fun onMessage(ws: WebSocket, text: String) {
                try {
                    val json = JsonParser.parseString(text).asJsonObject
                    when (json.get("type")?.asString) {
                        "state", "screenshot" -> {
                            _state.value = _state.value.copy(
                                app = json.get("app")?.asString ?: _state.value.app,
                                text = json.get("text")?.asString ?: "",
                                screenshot = json.get("screenshot")?.asString,
                            )
                        }
                        "chat_thinking" -> _state.value = _state.value.copy(chatThinking = true)
                        "chat_response" -> {
                            val msg = json.get("text")?.asString ?: ""
                            _state.value = _state.value.copy(
                                chatMessages = _state.value.chatMessages + ChatMessage("assistant", msg),
                                chatThinking = false
                            )
                        }
                        "chat_cleared" -> _state.value = _state.value.copy(chatMessages = emptyList())
                    }
                } catch (e: Exception) {
                    Log.e("SkyCUA", "Parse error: ${e.message}")
                }
            }

            override fun onClosing(ws: WebSocket, code: Int, reason: String) {
                ws.close(1000, null)
                _state.value = _state.value.copy(connected = false)
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.e("SkyCUA", "Failed: ${t.message}")
                _state.value = _state.value.copy(connected = false)
            }
        })
    }

    fun setApp(app: String) = send("set_app", mapOf("app" to app))
    fun click(element: String) = send("action", mapOf("tool" to "click", "args" to mapOf("element_index" to element)))
    fun typeText(text: String) = send("action", mapOf("tool" to "type_text", "args" to mapOf("text" to text)))
    fun pressKey(key: String) = send("action", mapOf("tool" to "press_key", "args" to mapOf("key" to key)))
    fun scroll(element: String, dir: String) = send("action", mapOf("tool" to "scroll", "args" to mapOf("element_index" to element, "direction" to dir)))
    fun requestScreenshot() = send("screenshot", emptyMap())
    fun sendChat(text: String) {
        _state.value = _state.value.copy(chatMessages = _state.value.chatMessages + ChatMessage("user", text))
        send("chat", mapOf("text" to text))
    }
    fun clearChat() = send("chat_clear", emptyMap())
    fun disconnect() {
        ws?.close(1000, null)
        _state.value = AgentState()
    }

    private fun send(type: String, data: Map<String, Any>) {
        ws?.send(gson.toJson(mapOf("type" to type) + data))
    }
}
