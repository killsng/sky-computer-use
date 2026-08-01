package com.skycua.app

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import java.util.concurrent.TimeUnit

data class AgentState(
    val app: String = "Safari",
    val screenshot: String? = null,
    val text: String = "",
    val apps: String = "",
    val log: List<Map<String, Any>> = emptyList(),
    val connected: Boolean = false,
    val error: String? = null
)

class WebSocketClient {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()

    private val _state = MutableStateFlow(AgentState())
    val state: StateFlow<AgentState> = _state.asStateFlow()

    private val _messages = MutableSharedFlow<String>()
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    fun connect(host: String, port: Int = 8765) {
        val request = Request.Builder()
            .url("ws://$host:$port")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("SkyCUA", "Connected to $host:$port")
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

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        _state.value = AgentState()
    }
}
