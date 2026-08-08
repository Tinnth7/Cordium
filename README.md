# Cordium Setup Guide

### This guide walks you through setting up a Discord Bot to sync channel links with Cordium. Total setup time is about 2 minutes.\

Step 1: Create a Discord Application and Bot

    Open the Discord Developer Portal and log in.

    Click New Application at the top right.

    Name your application (e.g., Cordium) and click Create.

Step 2: Enable Message Content Intent (Required)

    In the left sidebar, click Bot.

    Scroll down to the Privileged Gateway Intents section.

    Toggle Message Content Intent to ON.

    Click Save Changes at the bottom of the page.

    Important: If this setting is not enabled, Cordium cannot read message text or extract links from your channel.

Step 3: Get Your Bot Token

    On the Bot page, locate the Token section near the top.

    Click Reset Token (or Copy Token).

    Copy the token string and save it safely. Treat this token like a password.

Step 4: Invite the Bot to Your Server

    In the left sidebar, go to OAuth2 -> URL Generator.

    Under Scopes, check bot.

    Under Bot Permissions, check:

        Read Messages/View Channels

        Read Message History

    Copy the generated URL at the bottom of the page.

    Paste the URL into your browser, select your Discord server, and click Authorize.

Step 5: Get Your Channel ID

    Open your Discord app or web client.

    Go to User Settings -> Advanced, and toggle Developer Mode to ON.

    Right-click the text channel where your links are posted.

    Click Copy Channel ID.

Step 6: Connect Cordium

    Launch Cordium.exe.

    Paste your Bot Token and Channel ID into the prompt.

    Click Save & Connect.
