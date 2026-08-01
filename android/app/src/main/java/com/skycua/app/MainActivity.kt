package com.skycua.app

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

class MainActivity : ComponentActivity() {
    private var wsClient: WebSocketClient? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                App()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        wsClient?.disconnect()
    }
}

@Composable
fun App() {
    var url by remember { mutableStateOf("localhost:8765") }
    var connected by remember { mutableStateOf(false) }
    var app by remember { mutableStateOf("Finder") }
    var tree by remember { mutableStateOf("") }
    var chatInput by remember { mutableStateOf("") }
    var messages by remember { mutableStateOf(listOf<Pair<String, String>>()) }
    var thinking by remember { mutableStateOf(false) }
    
    val client = remember { WebSocketClient() }
    
    LaunchedEffect(Unit) {
        client.state.collect { state ->
            connected = state.connected
            app = state.app
            tree = state.text
            thinking = state.chatThinking
            messages = state.chatMessages.map { it.role to it.text }
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Color(0xFF0D0D0D))
            .padding(8.dp)
    ) {
        // Header
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Computer, null, tint = Color(0xFF90CAF9))
            Spacer(Modifier.width(8.dp))
            Text("SkyCUA", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color.White)
            Spacer(Modifier.width(8.dp))
            Box(Modifier.size(8.dp).background(
                if (connected) Color(0xFF4CAF50) else Color(0xFFF44336),
                RoundedCornerShape(4.dp)
            ))
            Spacer(Modifier.weight(1f))
            Text(app, fontSize = 12.sp, color = Color.Gray)
        }

        Spacer(Modifier.height(8.dp))

        // Connection
        if (!connected) {
            Row(Modifier.fillMaxWidth()) {
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("localhost:8765") },
                    singleLine = true
                )
                Spacer(Modifier.width(8.dp))
                Button(onClick = { client.connect(url) }) {
                    Text("Connect")
                }
            }
            Spacer(Modifier.height(8.dp))
        }

        // Tree preview
        if (tree.isNotEmpty()) {
            Card(
                Modifier.fillMaxWidth().height(150.dp),
                colors = CardDefaults.cardColors(Color(0xFF1A1A1A))
            ) {
                Text(
                    tree.take(800),
                    Modifier.padding(8.dp),
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    color = Color(0xFF90CAF9)
                )
            }
            Spacer(Modifier.height(8.dp))
        }

        // Quick actions
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf("Return" to "⏎", "Escape" to "ESC", "Tab" to "TAB", "Delete" to "DEL").forEach { (key, label) ->
                Button(
                    onClick = { client.pressKey(key) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(Color(0xFF2A2A2A))
                ) { Text(label, fontSize = 12.sp) }
            }
        }
        
        Spacer(Modifier.height(4.dp))
        
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf("super+c" to "⌘C", "super+v" to "⌘V", "super+a" to "⌘A", "super+z" to "⌘Z").forEach { (key, label) ->
                Button(
                    onClick = { client.pressKey(key) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(Color(0xFF1E3A5F))
                ) { Text(label, fontSize = 12.sp) }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Chat
        Card(
            Modifier.fillMaxWidth().weight(1f),
            colors = CardDefaults.cardColors(Color(0xFF1A1A2E))
        ) {
            Column(Modifier.padding(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Chat with OpenCode", fontSize = 12.sp, color = Color(0xFF90CAF9), fontWeight = FontWeight.Bold)
                    if (thinking) {
                        Spacer(Modifier.width(8.dp))
                        CircularProgressIndicator(Modifier.size(12.dp), strokeWidth = 2.dp)
                    }
                }
                
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    messages.forEach { (role, text) ->
                        Text(
                            text.take(300),
                            fontSize = 11.sp,
                            color = if (role == "user") Color(0xFF90CAF9) else Color(0xFFA5D6A7),
                            modifier = Modifier.padding(vertical = 2.dp)
                        )
                    }
                }
                
                Row(Modifier.fillMaxWidth()) {
                    OutlinedTextField(
                        value = chatInput,
                        onValueChange = { chatInput = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Ask AI...") },
                        singleLine = true
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(
                        onClick = {
                            if (chatInput.isNotBlank()) {
                                client.sendChat(chatInput)
                                chatInput = ""
                            }
                        },
                        enabled = chatInput.isNotBlank() && !thinking
                    ) { Icon(Icons.Default.Send, null) }
                }
            }
        }
    }
}
