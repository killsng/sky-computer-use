package com.skycua.app

import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val wsClient = WebSocketClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFF90CAF9),
                    secondary = Color(0xFFA5D6A7),
                    background = Color(0xFF121212),
                    surface = Color(0xFF1E1E1E),
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
    var serverHost by remember { mutableStateOf("192.168.1.100") }
    var showConnectDialog by remember { mutableStateOf(!state.connected) }
    var showInput by remember { mutableStateOf(false) }
    var inputText by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        client.connect(serverHost)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Computer, "PC", tint = Color(0xFF90CAF9))
                        Spacer(Modifier.width(8.dp))
                        Text("SkyCUA", fontWeight = FontWeight.Bold)
                        Spacer(Modifier.width(8.dp))
                        Box(
                            Modifier
                                .size(8.dp)
                                .clip(RoundedCornerShape(4.dp))
                                .background(if (state.connected) Color(0xFF4CAF50) else Color(0xFFF44336))
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            if (state.connected) "Connected" else "Disconnected",
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
                        Icon(Icons.Default.Settings, "Settings")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF1E1E1E)
                )
            )
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF121212))
        ) {
            // Screenshot
            Card(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF2A2A2A)),
                shape = RoundedCornerShape(12.dp)
            ) {
                if (state.screenshot != null) {
                    val bytes = Base64.decode(state.screenshot, Base64.DEFAULT)
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    bitmap?.let {
                        Image(
                            it.asImageBitmap(),
                            contentDescription = "Screen",
                            modifier = Modifier
                                .fillMaxSize()
                                .clip(RoundedCornerShape(12.dp)),
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
                                if (state.connected) "Waiting for screenshot..." else "Connect to computer",
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
                colors = CardDefaults.cardColors(containerColor = Color(0xFF2A2A2A)),
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
                    listOf("Safari", "Finder", "System Settings", "ChatGPT").forEach { app ->
                        FilterChip(
                            selected = state.app == app,
                            onClick = { client.setApp(app) },
                            label = { Text(app, fontSize = 12.sp) },
                            modifier = Modifier.padding(end = 4.dp)
                        )
                    }
                }
            }

            // Quick actions
            Card(
                Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF2A2A2A)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Column(Modifier.padding(8.dp)) {
                    // Text input row
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("Type text...", fontSize = 14.sp) },
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

                    // Key buttons
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        listOf(
                            Triple("Return", "⏎", Color(0xFF4CAF50)),
                            Triple("Escape", "ESC", Color(0xFFF44336)),
                            Triple("Tab", "⇥", Color(0xFFFF9800)),
                            Triple("Delete", "⌫", Color(0xFF9C27B0)),
                            Triple("super+a", "⌘A", Color(0xFF2196F3)),
                            Triple("super+c", "⌘C", Color(0xFF2196F3)),
                            Triple("super+v", "⌘V", Color(0xFF2196F3)),
                        ).forEach { (key, label, color) ->
                            FilledTonalButton(
                                onClick = { client.pressKey(key) },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = color.copy(alpha = 0.2f)
                                ),
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Text(label, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Accessibility tree preview
            if (state.text.isNotBlank()) {
                Card(
                    Modifier
                        .fillMaxWidth()
                        .height(120.dp)
                        .padding(8.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A2E)),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    LazyColumn(Modifier.padding(8.dp)) {
                        items(state.text.lines().take(15)) { line ->
                            Text(
                                line,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                color = Color(0xFF90CAF9),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
            }
        }
    }

    // Connect dialog
    if (showConnectDialog) {
        AlertDialog(
            onDismissRequest = { if (state.connected) showConnectDialog = false },
            title = { Text("Connect to Computer") },
            text = {
                Column {
                    OutlinedTextField(
                        value = serverHost,
                        onValueChange = { serverHost = it },
                        label = { Text("Server IP") },
                        singleLine = true
                    )
                    Spacer(Modifier.height(8.dp))
                    Text("Default port: 8765", fontSize = 12.sp, color = Color.Gray)
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
