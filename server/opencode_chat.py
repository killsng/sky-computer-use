#!/usr/bin/env python3
"""OpenCode chat bridge - reads messages from Android app and responds.

Usage:
    python3 opencode_chat.py
    
OpenCode agent runs this script. It:
1. Reads /tmp/skycua-chat.json for new messages
2. Processes each message (can control computer via MCP)
3. Writes response back to the file
"""

import json
import os
import sys
import time

CHAT_FILE = "/tmp/skycua-chat.json"


def read_chat():
    try:
        with open(CHAT_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"queue": [], "responses": {}, "app": "Safari", "screenshot": None}


def write_chat(data):
    with open(CHAT_FILE, "w") as f:
        json.dump(data, f)


def process_message(msg):
    """Process a message from the Android app."""
    text = msg.get("text", "")
    app = msg.get("app", "Safari")
    msg_id = msg.get("id", "")
    
    # Here OpenCode agent would process the message
    # For now, return a simple response
    return f"Received: {text}"


def main():
    print("OpenCode Chat Bridge running...")
    print(f"Watching: {CHAT_FILE}")
    print("Press Ctrl+C to stop\n")
    
    seen_ids = set()
    
    while True:
        try:
            data = read_chat()
            queue = data.get("queue", [])
            
            for msg in queue:
                msg_id = msg.get("id", "")
                if msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    text = msg.get("text", "")
                    print(f"[{msg_id}] User: {text}")
                    
                    # Process and respond
                    response = process_message(msg)
                    
                    # Add response
                    if "responses" not in data:
                        data["responses"] = {}
                    data["responses"][msg_id] = response
                    
                    # Clear processed message
                    data["queue"] = [m for m in queue if m.get("id") != msg_id]
                    
                    write_chat(data)
                    print(f"[{msg_id}] Agent: {response}\n")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
