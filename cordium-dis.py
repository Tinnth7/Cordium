#!/usr/bin/env python3
"""
cordium.py - Standalone Discord Link Collector & Manager
"""

import sys
import os
import re
import json
import webbrowser
import requests
import ctypes
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
    QMessageBox,
    QDialog,
    QLineEdit,
    QFormLayout,
)


# --- WINDOWS DPAPI ENCRYPTION WRAPPERS ---
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def dpapi_encrypt(data: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI (bound to current Windows user)."""
    if sys.platform != "win32":
        return data  # Fallback for non-Windows operating systems

    in_blob = DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte))
    )
    out_blob = DATA_BLOB()

    if ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return encrypted_bytes
    raise RuntimeError("Failed to encrypt credentials with DPAPI.")


def dpapi_decrypt(data: bytes) -> bytes:
    """Decrypts bytes using Windows DPAPI."""
    if sys.platform != "win32":
        return data

    in_blob = DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte))
    )
    out_blob = DATA_BLOB()

    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return decrypted_bytes
    raise RuntimeError("Failed to decrypt credentials with DPAPI.")


# --- CONFIGURATION STORAGE HANDLERS ---
def get_config_path() -> Path:
    """Returns path to %LOCALAPPDATA%\\Cordium\\config.bin."""
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data) / "Cordium"
    else:
        base_dir = Path.home() / ".config" / "cordium"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "config.bin"


def save_credentials(token: str, channel_id: str):
    """Encrypts and writes credentials to the local .bin file."""
    config_file = get_config_path()
    payload = {"bot_token": token, "channel_id": channel_id}
    raw_bytes = json.dumps(payload).encode("utf-8")
    encrypted_bytes = dpapi_encrypt(raw_bytes)

    with open(config_file, "wb") as f:
        f.write(encrypted_bytes)


def load_credentials() -> tuple[str, str]:
    """Reads and decrypts credentials from the local .bin file."""
    config_file = get_config_path()
    if not config_file.exists():
        return "", ""
    try:
        with open(config_file, "rb") as f:
            encrypted_bytes = f.read()

        decrypted_bytes = dpapi_decrypt(encrypted_bytes)
        data = json.loads(decrypted_bytes.decode("utf-8"))
        return data.get("bot_token", ""), data.get("channel_id", "")
    except Exception:
        return "", ""


# --- UI DIALOGS AND COMPONENTS ---
class SettingsDialog(QDialog):
    """Configuration prompt for setting Discord credentials."""

    def __init__(self, parent=None, is_first_run=False):
        super().__init__(parent)
        self.setWindowTitle("Cordium Setup" if is_first_run else "Cordium Settings")
        self.resize(450, 260)

        layout = QVBoxLayout(self)

        if is_first_run:
            welcome_lbl = QLabel(
                "<h3>Welcome to Cordium</h3>"
                "To get started, you will need a <b>Discord Bot Token</b> and a <b>Channel ID</b>."
            )
            welcome_lbl.setWordWrap(True)
            layout.addWidget(welcome_lbl)

        # Guide button
        guide_btn = QPushButton("View Bot Setup Guide")
        guide_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
        """)
        # Update this URL to point to your documentation or repository
        guide_url = "https://github.com/Tinnth7/Cordium/blob/main/README.md"
        guide_btn.clicked.connect(lambda: webbrowser.open(guide_url))
        layout.addWidget(guide_btn)

        layout.addSpacing(10)

        # Inputs
        form_layout = QFormLayout()
        curr_token, curr_channel = load_credentials()

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Paste Bot Token here...")
        self.token_input.setText(curr_token)

        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("e.g. 1242824150024720456")
        self.channel_input.setText(curr_channel)

        form_layout.addRow("Discord Bot Token:", self.token_input)
        form_layout.addRow("Channel ID:", self.channel_input)
        layout.addLayout(form_layout)

        # Message Content Intent Warning
        intent_hint = QLabel(
            "<small><b>Important:</b> Ensure <b>Message Content Intent</b> is turned ON in the Discord Developer Portal under the Bot tab.</small>"
        )
        intent_hint.setWordWrap(True)
        layout.addWidget(intent_hint)

        layout.addSpacing(10)

        save_btn = QPushButton("Save & Connect")
        save_btn.setStyleSheet("padding: 6px; font-weight: bold;")
        save_btn.clicked.connect(self.save_and_close)
        layout.addWidget(save_btn)

    def save_and_close(self):
        token = self.token_input.text().strip()
        channel = self.channel_input.text().strip()

        if not token or not channel:
            QMessageBox.warning(self, "Missing Information", "Both Bot Token and Channel ID are required.")
            return

        save_credentials(token, channel)
        self.accept()


class DiscordFetcher(QThread):
    links_updated = pyqtSignal(list)
    status_signal = pyqtSignal(str)

    def __init__(self, token, channel_id, interval=10):
        super().__init__()
        self.token = token
        self.channel_id = channel_id
        self.interval = interval
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        headers = {"Authorization": f"Bot {self.token}"}
        url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages?limit=100"

        url_pattern = re.compile(r"https?://[^\s()<>]+(?:\([\w_]+\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])")
        title_pattern = re.compile(r"\[(.*?)\]")

        while self._running:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    messages = response.json()
                    parsed_items = []

                    for msg in reversed(messages):
                        content = msg.get("content", "")
                        link_match = url_pattern.search(content)

                        if link_match:
                            link = link_match.group(0).strip()
                            title_match = title_pattern.search(content)
                            name = title_match.group(1).strip() if title_match else link

                            raw_date = msg.get("timestamp", "")
                            parsed_date = raw_date[:10] if raw_date else "N/A"

                            parsed_items.append({
                                "name": name,
                                "date": parsed_date,
                                "link": link
                            })

                    self.links_updated.emit(parsed_items)
                    self.status_signal.emit(f"Synced ({len(parsed_items)} items loaded).")
                elif response.status_code == 401:
                    self.status_signal.emit("Error: Invalid Bot Token. Check Settings.")
                elif response.status_code == 403:
                    self.status_signal.emit("Error: Missing Access or Message Content Intent.")
                else:
                    self.status_signal.emit(f"Discord API error: {response.status_code}")
            except Exception as e:
                self.status_signal.emit(f"Sync error: {e}")

            for _ in range(self.interval):
                if not self._running:
                    break
                self.msleep(1000)


class LinkManager(QWidget):
    def __init__(self, token, channel_id):
        super().__init__()
        self.setWindowTitle("Cordium")
        self.resize(720, 500)

        self.token = token
        self.channel_id = channel_id
        self.items = []
        self.fetcher = None

        layout = QVBoxLayout(self)

        # Header Bar
        top_bar = QHBoxLayout()
        self.status_label = QLabel("Connecting to Discord...")
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings)

        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        top_bar.addWidget(settings_btn)
        layout.addLayout(top_bar)

        # Table Setup
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Date", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)

        # Controls
        bottom_bar = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_none)

        open_selected_btn = QPushButton("Open Selected Links")
        open_selected_btn.clicked.connect(self.open_selected)

        bottom_bar.addWidget(select_all_btn)
        bottom_bar.addWidget(select_none_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(open_selected_btn)
        layout.addLayout(bottom_bar)

        self.start_fetcher()

    def start_fetcher(self):
        if self.fetcher and self.fetcher.isRunning():
            self.fetcher.stop()
            self.fetcher.wait()

        self.fetcher = DiscordFetcher(self.token, self.channel_id)
        self.fetcher.links_updated.connect(self.update_table)
        self.fetcher.status_signal.connect(self.status_label.setText)
        self.fetcher.start()

    def open_settings(self):
        dialog = SettingsDialog(self, is_first_run=False)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.token, self.channel_id = load_credentials()
            self.start_fetcher()

    def update_table(self, new_items):
        if new_items == self.items:
            return

        checked_urls = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_urls.add(self.items[row]["link"])

        self.items = new_items
        self.table.setRowCount(len(self.items))

        for row, item in enumerate(self.items):
            name_item = QTableWidgetItem(item["name"])
            is_checked = item["link"] in checked_urls
            name_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(item["date"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["link"]))

    def on_item_double_clicked(self, item):
        row = item.row()
        if row < len(self.items):
            webbrowser.open(self.items[row]["link"])

    def select_all(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

    def select_none(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def open_selected(self):
        selected = [
            self.items[row]["link"]
            for row in range(self.table.rowCount())
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            QMessageBox.information(self, "No selection", "Please select at least one item.")
            return

        for link in selected:
            webbrowser.open(link)

    def closeEvent(self, event):
        if self.fetcher:
            self.fetcher.stop()
            self.fetcher.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)

    token, channel = load_credentials()

    if not token or not channel:
        dialog = SettingsDialog(is_first_run=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        token, channel = load_credentials()

    win = LinkManager(token, channel)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()