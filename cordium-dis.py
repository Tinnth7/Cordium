#!/usr/bin/env python3
"""
cordium.py - Standalone Discord Link Collector & Manager
Architecture: Direct Discord API + Double Layer Encrypted Credentials (Fernet + DPAPI)
Features:
 - Full Discord Dark Mode UI
 - Real-time Link Search & Filtering
 - Config Import/Export with Cross-Machine Compatibility
 - Zero-Leak Token UI Protection (Tokens cannot be unmasked or copied from imported/saved configs)
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
from cryptography.fernet import Fernet

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
    QFileDialog,
)

# App-specific AES key for Inner Encryption Layer
APP_SECRET_KEY = b'4v9Z_J8xQ3Yw2K1p0mN7bV5cC3xZ1a9s8d7f6g5h4j3='

# --- GLOBAL DISCORD DARK THEME STYLESHEET ---
DARK_STYLE = """
QWidget {
    background-color: #313338;
    color: #DBDEE1;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QDialog {
    background-color: #313338;
}
QLabel {
    color: #DBDEE1;
}
QLineEdit {
    background-color: #1E1F22;
    color: #F2F3F5;
    border: 1px solid #383A40;
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: #5865F2;
}
QLineEdit:focus {
    border: 1px solid #5865F2;
}
QTableWidget {
    background-color: #2B2D31;
    color: #F2F3F5;
    gridline-color: #383A40;
    border: 1px solid #383A40;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 6px;
}
QTableWidget::item:selected {
    background-color: #404249;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #1E1F22;
    color: #949BA4;
    padding: 8px;
    font-weight: bold;
    border: none;
    border-bottom: 1px solid #383A40;
}
QPushButton {
    background-color: #4E5058;
    color: #FFFFFF;
    font-weight: bold;
    padding: 7px 14px;
    border-radius: 4px;
    border: none;
}
QPushButton:hover {
    background-color: #6D6F78;
}
QPushButton:pressed {
    background-color: #3B3D44;
}
QPushButton#primaryBtn {
    background-color: #5865F2;
}
QPushButton#primaryBtn:hover {
    background-color: #4752C4;
}
QPushButton#dangerBtn {
    background-color: #DA373C;
}
QPushButton#dangerBtn:hover {
    background-color: #A1282C;
}
"""


# --- LAYER 2: WINDOWS DPAPI WRAPPERS ---
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def dpapi_encrypt(data: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI (bound strictly to current Windows user account)."""
    if sys.platform != "win32":
        return data

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


# --- ENCRYPTION PIPELINES ---
def double_encrypt_config(payload: dict) -> bytes:
    """Local Storage Encryption: Fernet + Machine DPAPI."""
    raw_json = json.dumps(payload).encode("utf-8")
    fernet = Fernet(APP_SECRET_KEY)
    layer1_cipher = fernet.encrypt(raw_json)
    return dpapi_encrypt(layer1_cipher)


def double_decrypt_config(encrypted_data: bytes) -> dict:
    """Local Storage Decryption: Machine DPAPI + Fernet."""
    layer1_cipher = dpapi_decrypt(encrypted_data)
    fernet = Fernet(APP_SECRET_KEY)
    raw_json = fernet.decrypt(layer1_cipher)
    return json.loads(raw_json.decode("utf-8"))


def export_portable_config(payload: dict) -> bytes:
    """Portable Export Encryption: Fernet only (allows cross-machine transfer)."""
    raw_json = json.dumps(payload).encode("utf-8")
    fernet = Fernet(APP_SECRET_KEY)
    return fernet.encrypt(raw_json)


def import_portable_config(encrypted_data: bytes) -> dict:
    """Attempts local DPAPI+Fernet decrypt first; falls back to Fernet-only for exported files."""
    try:
        return double_decrypt_config(encrypted_data)
    except Exception:
        fernet = Fernet(APP_SECRET_KEY)
        raw_json = fernet.decrypt(encrypted_data)
        return json.loads(raw_json.decode("utf-8"))


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


def save_credentials(bot_token: str, channel_id: str):
    """Double-encrypts and writes connection info to local config.bin."""
    config_file = get_config_path()
    payload = {"bot_token": bot_token, "channel_id": channel_id}
    encrypted_data = double_encrypt_config(payload)

    with open(config_file, "wb") as f:
        f.write(encrypted_data)


def load_credentials() -> tuple[str, str]:
    """Reads and double-decrypts connection info from local config.bin."""
    config_file = get_config_path()
    if not config_file.exists():
        return "", ""
    try:
        with open(config_file, "rb") as f:
            encrypted_data = f.read()

        data = double_decrypt_config(encrypted_data)
        return data.get("bot_token", ""), data.get("channel_id", "")
    except Exception:
        return "", ""


# --- UI DIALOGS AND COMPONENTS ---
class SettingsDialog(QDialog):
    """Setup and settings dialog with strict zero-leak token protection."""

    def __init__(self, parent=None, is_first_run=False):
        super().__init__(parent)
        self.setWindowTitle("Cordium Setup" if is_first_run else "Cordium Settings")
        self.resize(580, 320)

        # Internal token storage (never exposed to UI widgets when active)
        curr_token, curr_channel = load_credentials()
        self.loaded_token = curr_token

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if is_first_run:
            welcome_lbl = QLabel(
                "<h2 style='margin: 0; color: #FFFFFF;'>Welcome to Cordium</h2>"
                "<p style='color: #949BA4;'>Enter your Discord Bot Token and Channel ID to connect, or import a pre-configured config file.</p>"
            )
            welcome_lbl.setWordWrap(True)
            layout.addWidget(welcome_lbl)

        # Top Action Buttons
        top_btns = QHBoxLayout()

        guide_btn = QPushButton("Guide")
        guide_url = "https://github.com/Tinnth7/cordium#readme"
        guide_btn.clicked.connect(lambda: webbrowser.open(guide_url))
        top_btns.addWidget(guide_btn)

        import_btn = QPushButton("Import Config")
        import_btn.clicked.connect(self.import_config_file)
        top_btns.addWidget(import_btn)

        export_btn = QPushButton("Export Config")
        export_btn.clicked.connect(self.export_config_file)
        top_btns.addWidget(export_btn)

        delete_btn = QPushButton("Delete Credentials")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self.delete_credentials)
        top_btns.addWidget(delete_btn)

        layout.addLayout(top_btns)
        layout.addSpacing(5)

        # Form Inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        token_container = QHBoxLayout()
        token_container.setContentsMargins(0, 0, 0, 0)

        self.token_input = QLineEdit()
        self.action_btn = QPushButton("Show")
        self.action_btn.setFixedWidth(75)
        self.action_btn.clicked.connect(self.handle_token_action)

        token_container.addWidget(self.token_input)
        token_container.addWidget(self.action_btn)

        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("e.g. 1242824150024720456")
        self.channel_input.setText(curr_channel)

        form_layout.addRow("Bot Token:", token_container)
        form_layout.addRow("Channel ID:", self.channel_input)
        layout.addLayout(form_layout)

        # Initialize input state
        if self.loaded_token:
            self.lock_token_ui()
        else:
            self.unlock_token_ui()

        layout.addSpacing(10)

        # Save Button
        save_btn = QPushButton("Save & Connect")
        save_btn.setObjectName("primaryBtn")
        save_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        save_btn.clicked.connect(self.save_and_close)
        layout.addWidget(save_btn)

    def lock_token_ui(self):
        """Locks the input field with dummy bullet dots so Ctrl+C copies useless text."""
        self.token_input.setReadOnly(True)
        self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.token_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.token_input.setText("••••••••••••••••••••••••••••••••")
        self.action_btn.setText("Replace")

    def unlock_token_ui(self):
        """Unlocks the field so the user can enter a new token manually."""
        self.loaded_token = ""
        self.token_input.setReadOnly(False)
        self.token_input.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.clear()
        self.token_input.setPlaceholderText("Paste Bot Token Here")
        self.action_btn.setText("Show")

    def handle_token_action(self):
        """Handles the dual-purpose action button (Show/Hide or Replace)."""
        if self.token_input.isReadOnly():
            # If token is locked, clicking button clears it and lets user type a new one
            self.unlock_token_ui()
        else:
            # If user is typing a new token manually, toggle password visibility
            if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
                self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
                self.action_btn.setText("Hide")
            else:
                self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
                self.action_btn.setText("Show")

    def delete_credentials(self):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete stored credentials from LocalAppData?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            config_file = get_config_path()
            if config_file.exists():
                try:
                    config_file.unlink()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete config file:\n{e}")
                    return

            self.unlock_token_ui()
            self.channel_input.clear()
            QMessageBox.information(self, "Deleted", "Credentials file successfully deleted.")

    def export_config_file(self):
        bot_token = self.loaded_token if self.token_input.isReadOnly() else self.token_input.text().strip()
        channel_id = self.channel_input.text().strip()

        if not bot_token or not channel_id:
            QMessageBox.warning(self, "Export Warning", "Fill in Bot Token and Channel ID before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Cordium Config", "cordium_config.bin", "Binary Files (*.bin);;All Files (*)"
        )
        if not file_path:
            return

        try:
            payload = {"bot_token": bot_token, "channel_id": channel_id}
            portable_data = export_portable_config(payload)

            with open(file_path, "wb") as f:
                f.write(portable_data)

            QMessageBox.information(self, "Success", f"Config exported successfully to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export config:\n{e}")

    def import_config_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cordium Config File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as src:
                data = src.read()

            decoded = import_portable_config(data)
            bot_token = decoded.get("bot_token", "")
            channel_id = decoded.get("channel_id", "")

            if bot_token and channel_id:
                save_credentials(bot_token, channel_id)
                self.loaded_token = bot_token
                self.lock_token_ui()
                self.channel_input.setText(channel_id)

                QMessageBox.information(self, "Success", "Config imported! Token remains securely hidden.")
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid File", "The config file is missing required fields.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to decrypt config file:\n{e}")

    def save_and_close(self):
        typed_token = self.token_input.text().strip()
        bot_token = self.loaded_token if self.token_input.isReadOnly() else typed_token
        channel_id = self.channel_input.text().strip()

        if not bot_token or not channel_id:
            QMessageBox.warning(self, "Missing Info", "Both Bot Token and Channel ID are required.")
            return

        save_credentials(bot_token, channel_id)
        self.accept()


class DiscordFetcher(QThread):
    links_updated = pyqtSignal(list)
    status_signal = pyqtSignal(str)

    def __init__(self, bot_token, channel_id, interval=10):
        super().__init__()
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.interval = interval
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        auth_header = self.bot_token if self.bot_token.startswith("Bot ") else f"Bot {self.bot_token}"
        headers = {"Authorization": auth_header}
        request_url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages?limit=100"

        url_pattern = re.compile(r"https?://[^\s()<>]+(?:\([\w_]+\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])")
        title_pattern = re.compile(r"\[(.*?)\]")

        while self._running:
            try:
                response = requests.get(request_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    messages = response.json()
                    parsed_items = []

                    if isinstance(messages, list):
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
                    else:
                        self.status_signal.emit("Error: Unexpected payload from Discord API.")
                elif response.status_code == 401:
                    self.status_signal.emit("Error: Unauthorized (Invalid Bot Token).")
                elif response.status_code == 403:
                    self.status_signal.emit("Error: Forbidden (Bot lacks channel access).")
                elif response.status_code == 404:
                    self.status_signal.emit("Error: Channel ID not found.")
                else:
                    self.status_signal.emit(f"Discord API error: HTTP {response.status_code}")
            except Exception as e:
                self.status_signal.emit(f"Sync error: {e}")

            for _ in range(self.interval):
                if not self._running:
                    break
                self.msleep(1000)


class LinkManager(QWidget):
    def __init__(self, bot_token, channel_id):
        super().__init__()
        self.setWindowTitle("Cordium")
        self.resize(760, 520)

        self.bot_token = bot_token
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

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search titles or links...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_table)
        layout.addWidget(self.search_input)

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
        open_selected_btn.setObjectName("primaryBtn")
        open_selected_btn.clicked.connect(self.open_selected)

        bottom_bar.addWidget(select_all_btn)
        bottom_bar.addWidget(select_none_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(open_selected_btn)
        layout.addLayout(bottom_bar)

        self.start_fetcher()

    def filter_table(self, query: str):
        query = query.lower().strip()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            link_item = self.table.item(row, 2)
            name_text = name_item.text().lower() if name_item else ""
            link_text = link_item.text().lower() if link_item else ""

            match = (query in name_text) or (query in link_text)
            self.table.setRowHidden(row, not match)

    def start_fetcher(self):
        if self.fetcher and self.fetcher.isRunning():
            self.fetcher.stop()
            self.fetcher.wait()

        self.fetcher = DiscordFetcher(self.bot_token, self.channel_id)
        self.fetcher.links_updated.connect(self.update_table)
        self.fetcher.status_signal.connect(self.status_label.setText)
        self.fetcher.start()

    def open_settings(self):
        dialog = SettingsDialog(self, is_first_run=False)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.bot_token, self.channel_id = load_credentials()
            if self.bot_token and self.channel_id:
                self.start_fetcher()
            else:
                if self.fetcher:
                    self.fetcher.stop()
                    self.fetcher.wait()
                self.status_label.setText("No credentials configured.")
                self.items = []
                self.table.setRowCount(0)

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

        self.filter_table(self.search_input.text())

    def on_item_double_clicked(self, item):
        row = item.row()
        if row < len(self.items):
            webbrowser.open(self.items[row]["link"])

    def select_all(self):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
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
    app.setStyleSheet(DARK_STYLE)

    bot_token, channel_id = load_credentials()

    if not bot_token or not channel_id:
        dialog = SettingsDialog(is_first_run=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        bot_token, channel_id = load_credentials()

    win = LinkManager(bot_token, channel_id)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
