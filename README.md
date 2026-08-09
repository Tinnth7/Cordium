# Cordium

Cordium is a lightweight, standalone desktop link collector and manager that turns any Discord channel into a self-updating bookmark dashboard. Built with **Python** and **PyQt6**, it automatically extracts shared links and custom titles (`[Title] URL`) from Discord into a clean, searchable, dark-themed interface.

---

## Key Features

- **Discord Dark Theme:** Native dark-mode UI designed to mirror Discord's aesthetic.
- **Real-Time Search:** Instantly filter gathered links by title or URL as you type.
- **Double-Layer Credential Security:** Bot tokens are protected using two-layer encryption (**Fernet + Windows DPAPI**), binding stored credentials strictly to your Windows account at `%LOCALAPPDATA%\Cordium\config.bin`.
- **Portable Config Export & Import:** Export encrypted configurations to share across machines. Upon import, Cordium automatically re-encrypts and locks the configuration to the local machine's DPAPI.
- **One-Click Local Data Eraser:** Easily clear stored credentials and settings directly from the Settings dialog.
- **Bulk Link Management:** Select all, deselect, or open multiple selected links in your default browser at once.
- **Smart Title Extraction:** Automatically parses link labels formatted as `[Title] URL`.

---

## Download & Installation

### Option 1: Executable (Recommended)

1. Go to the [Releases page](https://github.com/Tinnth7/cordium/releases).
2. Download `Cordium.exe` under the **Assets** section of the latest release.
3. Move `Cordium.exe` to any folder — Cordium is completely portable and single-file.

> **Note on Windows SmartScreen:**  
> Because Cordium is an independently built app and not code-signed, Windows may show a *"Windows protected your PC"* message on first launch. Click **More info** → **Run anyway**.

### Requirements
- **OS:** Windows 10 or later
- **Dependencies:** None (Python and all required libraries are pre-bundled into the executable)

---

## Setup Guide

To connect Cordium to a Discord channel, you need a Discord Bot Token and the Channel ID where links are posted.

### Step 1: Create a Discord Application & Bot
1. Log in to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (top right), name it `Cordium`, and click **Create**.

### Step 2: Enable Message Content Intent (Required)
1. Select **Bot** from the left sidebar.
2. Scroll down to **Privileged Gateway Intents**.
3. Toggle **Message Content Intent** to **ON**.
4. Click **Save Changes**.

> **Important:** Without Message Content Intent enabled, Discord blocks the bot from reading message text, preventing link extraction.

### Step 3: Copy Your Bot Token
1. In the **Bot** tab, locate the **Token** section near the top.
2. Click **Reset Token** (or **Copy**).
3. Save this token securely — treat it like a password.

### Step 4: Invite the Bot to Your Server
1. Go to **OAuth2 → URL Generator** in the left sidebar.
2. Under **Scopes**, select `bot`.
3. Under **Bot Permissions**, select:
   - `Read Messages/View Channels`
   - `Read Message History`
4. Copy the generated URL at the bottom, paste it into your browser, select your target server, and click **Authorize**.

### Step 5: Get Your Channel ID
1. Open Discord and go to **User Settings → Advanced**.
2. Toggle **Developer Mode** to **ON**.
3. Right-click the channel where links will be posted and select **Copy Channel ID**.

### Step 6: Connect Cordium
1. Launch `Cordium.exe`.
2. Paste your **Bot Token** and **Channel ID** into the setup prompt.
3. Click **Save & Connect**.

---

## Discord Message Formatting

Cordium parses messages in real time. To set custom titles for your links, format your messages in Discord using square brackets `[ ]`:

| Message Format | Parsed Name in Cordium | Parsed URL |
| :--- | :--- | :--- |
| `[PyQt6 Docs] https://www.riverbankcomputing.com` | `PyQt6 Docs` | `https://www.riverbankcomputing.com` |
| `[GitHub Portal] Useful link: https://github.com` | `GitHub Portal` | `https://github.com` |
| `https://github.com` *(No brackets)* | `https://github.com` | `https://github.com` |

---

## Configuration Management

Access these options anytime via the **Settings** button in the top-right corner of the application:

- **Export Config:** Generates a portable, Fernet-encrypted configuration file (`.bin`) that can be transferred to another computer.
- **Import Config:** Loads a pre-configured `.bin` file and automatically re-wraps it with local Windows DPAPI encryption.
- **Delete Credentials:** Wipes all locally stored tokens and configuration files from `%LOCALAPPDATA%\Cordium`.
