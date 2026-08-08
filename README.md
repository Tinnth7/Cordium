# About Cordium
Cordium is a lightweight desktop link manager that turns any Discord channel into a self-updating bookmark dashboard. Built with Python and PyQt6, it automatically extracts shared links and custom titles (`[Title] URL`) from Discord into a clean, interactive table.

## Getting Cordium

### Download

1. Go to the [Releases page](https://github.com/lituz-de/Cordium/releases) *(update this link to your actual repo)*.
2. Under the latest release, download `Cordium.exe` from the **Assets** section.
3. Move the file to a folder of your choice — Cordium is a single-file, standalone executable and doesn't require installation.

> **Windows SmartScreen Warning:** Since Cordium is an independently built app and not code-signed, Windows may show a "Windows protected your PC" warning the first time you run it. Click **More info** → **Run anyway** to launch it. This is expected for unsigned executables and does not mean the file is unsafe.

### Requirements
- Windows 10 or later
- No Python installation needed — everything is bundled into the `.exe`

Once downloaded, continue to the setup guide below to connect Cordium to your Discord server.

---

## Cordium Setup Guide
This guide walks you through setting up a Discord Bot to sync channel links with Cordium, as well as how to post links in Discord so Cordium parses them correctly.

### Caution
You will need to be the server's owner in order to make the bot work.

### Step 1: Create a Discord Application and Bot
1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and log in.
2. Click **New Application** at the top right.
3. Name your application (e.g., `Cordium`) and click **Create**.

### Step 2: Enable Message Content Intent (Required)
1. In the left sidebar, click **Bot**.
2. Scroll down to the **Privileged Gateway Intents** section.
3. Toggle **Message Content Intent** to ON.
4. Click **Save Changes** at the bottom of the page.

> **Important:** If this setting is not enabled, Cordium cannot read message text or extract links from your channel.

### Step 3: Get Your Bot Token
1. On the Bot page, locate the **Token** section near the top.
2. Click **Reset Token** (or **Copy Token**).
3. Copy the token string and save it safely. Treat this token like a password.

### Step 4: Invite the Bot to Your Server
1. In the left sidebar, go to **OAuth2 -> URL Generator**.
2. Under **Scopes**, check `bot`.
3. Under **Bot Permissions**, check:
   - Read Messages/View Channels
   - Read Message History
     (it should look like this, click to enlarge: <img width="10" height="10" alt="image" src="https://github.com/user-attachments/assets/3bd8e5e7-d6fb-4414-87f2-6ae2bc3c7af3" />)
4. Copy the generated URL at the bottom of the page.
5. Paste the URL into your browser, select your Discord server, and click **Authorize**.

### Step 5: Get Your Channel ID
1. Open your Discord app or web client.
2. Go to **User Settings -> Advanced**, and toggle **Developer Mode** to ON.
3. Right-click the text channel where your links are posted.
4. Click **Copy Channel ID**.

### Step 6: Connect Cordium
1. Launch `Cordium.exe`.
2. Paste your Bot Token and Channel ID into the prompt.
3. Click **Save & Connect**.

### Step 7: How to Format Messages in Discord
To set a custom name for a link in Cordium, place the title inside square brackets `[ ]` anywhere in your Discord message alongside the URL.

### Recommended Format
```
[Link Title] https://example.com
```

### Examples
- **Formatted Link:** `[PyQt6 Documentation] https://www.riverbankcomputing.com/software/pyqt/`
  - Parsed Name: `PyQt6 Documentation`
  - Parsed URL: `https://www.riverbankcomputing.com/software/pyqt/`
- **Link with Additional Text:** `[Discord Developer Portal] Check out the portal here: https://discord.com/developers`
  - Parsed Name: `Discord Developer Portal`
  - Parsed URL: `https://discord.com/developers`
- **Raw Link (Fallback):** `https://github.com`
  - Parsed Name: `https://github.com` (If no brackets are found, Cordium defaults to using the URL as the title.)
