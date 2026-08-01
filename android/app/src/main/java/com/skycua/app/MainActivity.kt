package com.skycua.app

import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

class MainActivity : ComponentActivity() {
    private val wsClient = WebSocketClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFF90CAF9),
                    secondary = Color(0xFFA5D6A7),
                    background = Color(0xFF0D0D0D),
                    surface = Color(0xFF1A1A1A),
                    onPrimary = Color.Black,
                    onSecondary = Color.Black,
                    onBackground = Color.White,
                    onSurface = Color.White,
                )
            ) {
                SkyCUAApp(wsClient)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        wsClient.disconnect()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SkyCUAApp(client: WebSocketClient) {
    val state by client.state.collectAsState()
    var serverHost by remember { mutableStateOf("localhost:8765") }
    var showConnectDialog by remember { mutableStateOf(!state.connected) }
    var inputText by remember { mutableStateOf("") }
    var chatInput by remember { mutableStateOf("") }
    var imageSize by remember { mutableStateOf(IntSize.Zero) }

    LaunchedEffect(state.connected) {
        while (state.connected && isActive) {
            client.requestScreenshot()
            delay(2000)
        }
    }

    LaunchedEffect(state.connected, state.error) {
        if (!state.connected && state.error != null && !state.connecting) {
            delay(3000)
            client.connect(serverHost)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Computer, "PC", tint = Color(0xFF90CAF9))
                        Spacer(Modifier.width(8.dp))
                        Text("SkyCUA", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Spacer(Modifier.width(8.dp))
                        Box(
                            Modifier
                                .size(8.dp)
                                .clip(RoundedCornerShape(4.dp))
                                .background(
                                    when {
                                        state.connected -> Color(0xFF4CAF50)
                                        state.connecting -> Color(0xFFFF9800)
                                        else -> Color(0xFFF44336)
                                    }
                                )
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            when {
                                state.connected -> "Connected"
                                state.connecting -> "Connecting..."
                                else -> "Offline"
                            },
                            fontSize = 12.sp,
                            color = Color.Gray
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { client.requestScreenshot() }) {
                        Icon(Icons.Default.Refresh, "Refresh")
                    }
                    IconButton(onClick = { showConnectDialog = true }) {
                        Icon(Icons.Default.Link, "Connect")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFF1A1A1A))
            )
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF0D0D0D))
        ) {
            // Tappable screenshot
            Card(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A)),
                shape = RoundedCornerShape(12.dp)
            ) {
                if (state.screenshot != null) {
                    val bytes = Base64.decode(state.screenshot, Base64.DEFAULT)
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    bitmap?.let { bmp ->
                        Image(
                            bmp.asImageBitmap(),
                            contentDescription = "Screen",
                            modifier = Modifier
                                .fillMaxSize()
                                .clip(RoundedCornerShape(12.dp))
                                .onSizeChanged { imageSize = it }
                                .pointerInput(Unit) {
                                    detectTapGestures { offset ->
                                        val scaleX = bmp.width.toFloat() / imageSize.width
                                        val scaleY = bmp.height.toFloat() / imageSize.height
                                        client.clickCoordinate(offset.x * scaleX, offset.y * scaleY)
                                    }
                                },
                            contentScale = ContentScale.Fit
                        )
                    }
                } else {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.Computer, "PC",
                                modifier = Modifier.size(64.dp),
                                tint = Color.Gray
                            )
                            Spacer(Modifier.height(8.dp))
                            Text(
                                if (state.connected) "Waiting for screenshot..." else "Tap link icon to connect",
                                color = Color.Gray
                            )
                        }
                    }
                }
            }

            // App selector
            Card(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("App:", color = Color.Gray, fontSize = 12.sp)
                    Spacer(Modifier.width(8.dp))
                    listOf("Finder", "Safari", "System Settings", "Terminal").forEach { app ->
                        FilterChip(
                            selected = state.app == app,
                            onClick = { client.setApp(app) },
                            label = { Text(app, fontSize = 11.sp) },
                            modifier = Modifier.padding(end = 4.dp)
                        )
                    }
                }
            }

            // Keyboard
            Card(
                Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Column(Modifier.padding(8.dp)) {
                    // Text input
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("Type...", fontSize = 13.sp) },
                            singleLine = true,
                            textStyle = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(Modifier.width(8.dp))
                        FilledTonalButton(onClick = {
                            if (inputText.isNotBlank()) {
                                client.typeText(inputText)
                                inputText = ""
                            }
                        }) {
                            Icon(Icons.Default.Send, "Type", modifier = Modifier.size(18.dp))
                        }
                    }

                    Spacer(Modifier.height(8.dp))

                    // Row 1: Common keys
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        listOf(
                            Triple("Return", "⏎", Color(0xFF4CAF50)),
                            Triple("Escape", "ESC", Color(0xFFF44336)),
                            Triple("Tab", "TAB", Color(0xFFFF9800)),
                            Triple("Delete", "DEL", Color(0xFF9C27B0)),
                            Triple("space", "SPC", Color(0xFF607D8B)),
                        ).forEach { (key, label, color) ->
                            FilledTonalButton(
                                onClick = { client.pressKey(key) },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = color.copy(alpha = 0.25f)
                                ),
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(vertical = 8.dp)
                            ) {
                                Text(label, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(Modifier.height(4.dp))

                    // Row 2: Cmd shortcuts
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        listOf(
                            Triple("super+a", "⌘A", Color(0xFF2196F3)),
                            Triple("super+c", "⌘C", Color(0xFF2196F3)),
                            Triple("super+v", "⌘V", Color(0xFF2196F3)),
                            Triple("super+x", "⌘X", Color(0xFF2196F3)),
                            Triple("super+z", "⌘Z", Color(0xFF2196F3)),
                        ).forEach { (key, label, color) ->
                            FilledTonalButton(
                                onClick = { client.pressKey(key) },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = color.copy(alpha = 0.25f)
                                ),
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(vertical = 8.dp)
                            ) {
                                Text(label, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(Modifier.height(4.dp))

                    // Row 3: Arrow keys
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        listOf(
                            Triple("Up", "▲", Color(0xFF795548)),
                            Triple("Down", "▼", Color(0xFF795548)),
                            Triple("Left", "◀", Color(0xFF795548)),
                            Triple("Right", "▶", Color(0xFF795548)),
                        ).forEach { (key, label, color) ->
                            FilledTonalButton(
                                onClick = { client.pressKey(key) },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = color.copy(alpha = 0.25f)
                                ),
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(vertical = 8.dp)
                            ) {
                                Text(label, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(Modifier.height(4.dp))

                    // Row 4: More shortcuts
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        listOf(
                            Triple("super+q", "⌘Q", Color(0xFFF44336)),
                            Triple("super+w", "⌘W", Color(0xFFFF9800)),
                            Triple("super+tab", "⌘⇥", Color(0xFF9C27B0)),
                            Triple("super+space", "Spotlight", Color(0xFF00BCD4)),
                        ).forEach { (key, label, color) ->
                            FilledTonalButton(
                                onClick = { client.pressKey(key) },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = color.copy(alpha = 0.25f)
                                ),
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(vertical = 8.dp)
                            ) {
                                Text(label, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Chat with OpenCode
            Card(
                Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A2E)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Column(Modifier.padding(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.SmartToy, "AI", tint = Color(0xFF90CAF9), modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("OpenCode Agent", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF90CAF9))
                        if (state.chatThinking) {
                            Spacer(Modifier.width(8.dp))
                            CircularProgressIndicator(Modifier.size(12.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(4.dp))
                            Text("Thinking...", fontSize = 10.sp, color = Color.Gray)
                        }
                        Spacer(Modifier.weight(1f))
                        TextButton(onClick = { client.clearChat() }) {
                            Text("Clear", fontSize = 10.sp)
                        }
                    }

                    // Messages
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .heightIn(min = 60.dp, max = 120.dp)
                            .verticalScroll(rememberScrollState())
                    ) {
                        if (state.chatMessages.isEmpty()) {
                            Text(
                                "Write to OpenCode agent...",
                                fontSize = 12.sp,
                                color = Color.Gray
                            )
                        }
                        state.chatMessages.forEach { msg ->
                            val bgColor = if (msg.role == "user") Color(0xFF2D4A7A) else Color(0xFF2A3A2A)
                            val textColor = if (msg.role == "user") Color(0xFF90CAF9) else Color(0xFFA5D6A7)
                            val label = if (msg.role == "user") "You" else "OpenCode"
                            Column(
                                Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 2.dp)
                                    .background(bgColor, RoundedCornerShape(6.dp))
                                    .padding(6.dp)
                            ) {
                                Text(label, fontSize = 9.sp, fontWeight = FontWeight.Bold, color = textColor.copy(alpha = 0.7f))
                                Spacer(Modifier.height(2.dp))
                                Text(msg.text.take(600), fontSize = 11.sp, color = textColor)
                            }
                        }
                    }

                    Spacer(Modifier.height(4.dp))

                    // Input
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = chatInput,
                            onValueChange = { chatInput = it },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("Ask OpenCode...", fontSize = 13.sp) },
                            singleLine = true,
                            textStyle = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(Modifier.width(8.dp))
                        FilledTonalButton(
                            onClick = {
                                if (chatInput.isNotBlank()) {
                                    client.sendChat(chatInput)
                                    chatInput = ""
                                }
                            },
                            enabled = chatInput.isNotBlank() && !state.chatThinking
                        ) {
                            Icon(Icons.Default.Send, "Send", modifier = Modifier.size(18.dp))
                        }
                    }
                }
            }
        }
    }

    if (showConnectDialog) {
        AlertDialog(
            onDismissRequest = { if (state.connected) showConnectDialog = false },
            title = { Text("Connect to Mac") },
            text = {
                Column {
                    OutlinedTextField(
                        value = serverHost,
                        onValueChange = { serverHost = it },
                        label = { Text("Server URL") },
                        singleLine = true,
                        placeholder = { Text("ngrok/CF tunnel URL or LAN IP") }
                    )
                    Spacer(Modifier.height(8.dp))
                    Text("Examples:", fontSize = 12.sp, color = Color.Gray)
                    Text("  xxx.ngrok-free.app", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = Color.Gray)
                    Text("  192.168.1.100:8765", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = Color.Gray)
                }
            },
            confirmButton = {
                Button(onClick = {
                    client.disconnect()
                    client.connect(serverHost)
                    showConnectDialog = false
                }) {
                    Text("Connect")
                }
            },
            dismissButton = {
                if (state.connected) {
                    TextButton(onClick = { showConnectDialog = false }) {
                        Text("Cancel")
                    }
                }
            }
        )
    }
}
