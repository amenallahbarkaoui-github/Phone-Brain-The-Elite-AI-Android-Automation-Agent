"""
Phone Brain v3 - Ultimate AI-Powered Android Control Agent
=======================================================
Single-agent architecture with widget-based interaction.
Uses UI hierarchy (uiautomator dump) for precise widget targeting
instead of error-prone coordinate-based tapping.
"""

import subprocess
import base64
import json
import os
import sys
import hashlib
import time
import re
import asyncio
import warnings
import aiohttp
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from datetime import datetime
from difflib import get_close_matches
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

try:
    from ddgs import DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS
        warnings.filterwarnings(
            "ignore",
            message="This package (`duckduckgo_search`) has been renamed to `ddgs`! Use `pip install ddgs` instead.",
            category=RuntimeWarning,
        )
    except Exception:
        DDGS = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    LLM_API_KEY: str = field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))
    LLM_MODEL: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "google/gemini-3-flash-preview"))
    LLM_BASE_URL: str = field(default_factory=lambda: os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"))
    REASONING_ENABLED: bool = False
    ADB_PATH: str = field(default_factory=lambda: os.environ.get("ADB_PATH", "adb"))
    DEVICE_SERIAL: Optional[str] = field(default_factory=lambda: os.environ.get("DEVICE_SERIAL") or None)
    MAX_ITERATIONS: int = 60
    SCREENSHOT_DELAY: float = 0.3
    COMMAND_TIMEOUT: int = 15
    TEMP_DIR: Path = field(default_factory=lambda: Path("./temp"))
    MEMORY_DIR: Path = field(default_factory=lambda: Path("./memory"))
    KNOWLEDGE_DIR: Path = field(default_factory=lambda: Path("./knowledge"))

    def __post_init__(self):
        if isinstance(self.TEMP_DIR, str):
            self.TEMP_DIR = Path(self.TEMP_DIR)
        self.TEMP_DIR.mkdir(exist_ok=True)
        if isinstance(self.MEMORY_DIR, str):
            self.MEMORY_DIR = Path(self.MEMORY_DIR)
        self.MEMORY_DIR.mkdir(exist_ok=True)
        if isinstance(self.KNOWLEDGE_DIR, str):
            self.KNOWLEDGE_DIR = Path(self.KNOWLEDGE_DIR)
        self.KNOWLEDGE_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON APP PACKAGES (100+)
# ═══════════════════════════════════════════════════════════════════════════════

PACKAGE_MAP = {
    # Google
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "drive": "com.google.android.apps.docs",
    "google drive": "com.google.android.apps.docs",
    "photos": "com.google.android.apps.photos",
    "google photos": "com.google.android.apps.photos",
    "calendar": "com.google.android.calendar",
    "google calendar": "com.google.android.calendar",
    "keep": "com.google.android.keep",
    "google keep": "com.google.android.keep",
    "translate": "com.google.android.apps.translate",
    "google translate": "com.google.android.apps.translate",
    "play store": "com.android.vending",
    "google play": "com.android.vending",
    "contacts": "com.google.android.contacts",
    "phone": "com.google.android.dialer",
    "dialer": "com.google.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "google messages": "com.google.android.apps.messaging",
    "files": "com.google.android.apps.nbu.files",
    "google files": "com.google.android.apps.nbu.files",
    "clock": "com.google.android.deskclock",
    "calculator": "com.google.android.calculator",
    "google meet": "com.google.android.apps.meetings",
    "google chat": "com.google.android.apps.dynamite",
    "google home": "com.google.android.apps.chromecast.app",
    "google lens": "com.google.ar.lens",
    "google earth": "com.google.earth",
    "youtube music": "com.google.android.apps.youtube.music",
    "google news": "com.google.android.apps.magazines",
    "google podcasts": "com.google.android.apps.podcasts",
    "google fit": "com.google.android.apps.fitness",
    "google docs": "com.google.android.apps.docs.editors.docs",
    "google sheets": "com.google.android.apps.docs.editors.sheets",
    "google slides": "com.google.android.apps.docs.editors.slides",
    "google assistant": "com.google.android.apps.googleassistant",
    # Social Media
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "messenger": "com.facebook.orca",
    "facebook messenger": "com.facebook.orca",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "tiktok": "com.zhiliaoapp.musically",
    "snapchat": "com.snapchat.android",
    "telegram": "org.telegram.messenger",
    "discord": "com.discord",
    "reddit": "com.reddit.frontpage",
    "linkedin": "com.linkedin.android",
    "pinterest": "com.pinterest",
    "tumblr": "com.tumblr",
    "threads": "com.instagram.barcelona",
    "signal": "org.thoughtcrime.securesms",
    "viber": "com.viber.voip",
    "wechat": "com.tencent.mm",
    "line": "jp.naver.line.android",
    # Streaming & Entertainment
    "netflix": "com.netflix.mediaclient",
    "spotify": "com.spotify.music",
    "amazon prime": "com.amazon.avod",
    "prime video": "com.amazon.avod",
    "disney+": "com.disney.disneyplus",
    "disney plus": "com.disney.disneyplus",
    "hbo max": "com.hbo.hbonow",
    "twitch": "tv.twitch.android.app",
    "soundcloud": "com.soundcloud.android",
    "deezer": "deezer.android.app",
    "shazam": "com.shazam.android",
    "vlc": "org.videolan.vlc",
    "plex": "com.plexapp.android",
    # Productivity
    "notion": "notion.id",
    "slack": "com.Slack",
    "zoom": "us.zoom.videomeetings",
    "teams": "com.microsoft.teams",
    "microsoft teams": "com.microsoft.teams",
    "outlook": "com.microsoft.office.outlook",
    "word": "com.microsoft.office.word",
    "excel": "com.microsoft.office.excel",
    "powerpoint": "com.microsoft.office.powerpoint",
    "onenote": "com.microsoft.office.onenote",
    "onedrive": "com.microsoft.skydrive",
    "evernote": "com.evernote",
    "todoist": "com.todoist",
    "trello": "com.trello",
    "asana": "com.asana.app",
    # Shopping
    "amazon": "com.amazon.mShop.android.shopping",
    "ebay": "com.ebay.mobile",
    "aliexpress": "com.alibaba.aliexpresshd",
    "wish": "com.contextlogic.wish",
    "etsy": "com.etsy.android",
    "shopify": "com.shopify.mobile",
    # Travel & Transport
    "uber": "com.ubercab",
    "lyft": "me.lyft.android",
    "grab": "com.grabtaxi.passenger",
    "airbnb": "com.airbnb.android",
    "booking": "com.booking",
    "google flights": "com.google.android.apps.travel.onthego",
    "tripadvisor": "com.tripadvisor.tripadvisor",
    # Finance
    "paypal": "com.paypal.android.p2pmobile",
    "venmo": "com.venmo",
    "cashapp": "com.squareup.cash",
    "cash app": "com.squareup.cash",
    "robinhood": "com.robinhood.android",
    "coinbase": "com.coinbase.android",
    # Health & Fitness
    "strava": "com.strava",
    "myfitnesspal": "com.myfitnesspal.android",
    "headspace": "com.getsomeheadspace.android",
    "calm": "com.calm.android",
    # News
    "bbc news": "bbc.mobile.news.ww",
    "cnn": "com.cnn.mobile.android.phone",
    "flipboard": "flipboard.app",
    # Utilities
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "gallery": "com.android.gallery3d",
    "browser": "com.android.browser",
    "file manager": "com.android.documentsui",
    "recorder": "com.android.soundrecorder",
    "notes": "com.android.notes",
    # Games
    "candy crush": "com.king.candycrushsaga",
    "clash royale": "com.supercell.clashroyale",
    "clash of clans": "com.supercell.clashofclans",
    "pubg": "com.tencent.ig",
    "among us": "com.innersloth.spacemafia",
    "roblox": "com.roblox.client",
    "minecraft": "com.mojang.minecraftpe",
    "genshin impact": "com.miHoYo.GenshinImpact",
    "fortnite": "com.epicgames.fortnite",
    "subway surfers": "com.kiloo.subwaysurf",
}

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS INTENTS
# ═══════════════════════════════════════════════════════════════════════════════

SETTINGS_INTENTS = {
    "wifi": "android.settings.WIFI_SETTINGS",
    "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
    "display": "android.settings.DISPLAY_SETTINGS",
    "sound": "android.settings.SOUND_SETTINGS",
    "battery": "android.settings.BATTERY_SAVER_SETTINGS",
    "storage": "android.settings.INTERNAL_STORAGE_SETTINGS",
    "apps": "android.settings.APPLICATION_SETTINGS",
    "location": "android.settings.LOCATION_SOURCE_SETTINGS",
    "security": "android.settings.SECURITY_SETTINGS",
    "accounts": "android.settings.SYNC_SETTINGS",
    "accessibility": "android.settings.ACCESSIBILITY_SETTINGS",
    "date": "android.settings.DATE_SETTINGS",
    "language": "android.settings.LOCALE_SETTINGS",
    "developer": "android.settings.APPLICATION_DEVELOPMENT_SETTINGS",
    "about": "android.settings.DEVICE_INFO_SETTINGS",
    "network": "android.settings.WIRELESS_SETTINGS",
    "nfc": "android.settings.NFC_SETTINGS",
    "hotspot": "android.settings.TETHER_SETTINGS",
    "vpn": "android.settings.VPN_SETTINGS",
    "notifications": "android.settings.NOTIFICATION_SETTINGS",
    "data_usage": "android.settings.DATA_USAGE_SETTINGS",
    "airplane": "android.settings.AIRPLANE_MODE_SETTINGS",
    "input_method": "android.settings.INPUT_METHOD_SETTINGS",
    "privacy": "android.settings.PRIVACY_SETTINGS",
}

KEYCODES = {
    "BACK": 4, "HOME": 3, "ENTER": 66, "RECENT": 187,
    "POWER": 26, "VOLUME_UP": 24, "VOLUME_DOWN": 25,
    "DELETE": 67, "DEL": 67, "TAB": 61, "ESCAPE": 111,
    "SEARCH": 84, "MENU": 82, "CAMERA": 27,
    "MEDIA_PLAY_PAUSE": 85, "MEDIA_NEXT": 87, "MEDIA_PREVIOUS": 88,
    "MEDIA_STOP": 86, "MUTE": 164,
    "DPAD_UP": 19, "DPAD_DOWN": 20, "DPAD_LEFT": 21, "DPAD_RIGHT": 22,
    "DPAD_CENTER": 23, "SPACE": 62, "PAGE_UP": 92, "PAGE_DOWN": 93,
    "MOVE_HOME": 122, "MOVE_END": 123,
    "SELECT_ALL": 277, "COPY": 278, "PASTE": 279, "CUT": 280,
}


# ═══════════════════════════════════════════════════════════════════════════════
# UI HIERARCHY PARSER (THE CORE INNOVATION)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Widget:
    """Represents a parsed UI element from hierarchy dump"""
    index: int
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    package: str
    clickable: bool
    enabled: bool
    focusable: bool
    scrollable: bool
    long_clickable: bool
    selected: bool
    checked: bool
    bounds: tuple  # (x1, y1, x2, y2)
    center_x: int
    center_y: int
    depth: int = 0
    parent_index: int = -1
    children_indices: list = field(default_factory=list)

    def matches_text(self, query: str) -> bool:
        return query.lower() in self.text.lower() if self.text else False

    def matches_desc(self, query: str) -> bool:
        return query.lower() in self.content_desc.lower() if self.content_desc else False

    def matches_id(self, query: str) -> bool:
        return query.lower() in self.resource_id.lower() if self.resource_id else False

    def is_interactive(self) -> bool:
        return self.clickable or self.focusable or self.scrollable or self.long_clickable

    def to_str(self) -> str:
        """Compact string representation for LLM context"""
        parts = [f"[{self.index}]"]
        if self.text:
            parts.append(f'text="{self.text}"')
        if self.content_desc:
            parts.append(f'desc="{self.content_desc}"')
        if self.resource_id:
            short_id = self.resource_id.split("/")[-1] if "/" in self.resource_id else self.resource_id
            parts.append(f'id="{short_id}"')
        cls_short = self.class_name.split(".")[-1] if "." in self.class_name else self.class_name
        parts.append(f'class={cls_short}')
        flags = []
        if self.clickable:
            flags.append("clickable")
        if self.scrollable:
            flags.append("scrollable")
        if self.long_clickable:
            flags.append("long-clickable")
        if self.checked:
            flags.append("checked")
        if self.selected:
            flags.append("selected")
        if not self.enabled:
            flags.append("DISABLED")
        if flags:
            parts.append(f'[{",".join(flags)}]')
        parts.append(f'bounds=({self.bounds[0]},{self.bounds[1]},{self.bounds[2]},{self.bounds[3]})')
        return " ".join(parts)


def parse_bounds(bounds_str: str) -> tuple:
    """Parse '[x1,y1][x2,y2]' -> (x1, y1, x2, y2)"""
    m = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if len(m) == 2:
        x1, y1 = int(m[0][0]), int(m[0][1])
        x2, y2 = int(m[1][0]), int(m[1][1])
        return (x1, y1, x2, y2)
    return (0, 0, 0, 0)


def parse_ui_hierarchy(xml_str: str) -> list[Widget]:
    """Parse uiautomator XML dump into Widget objects preserving tree structure"""
    widgets = []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return widgets

    # Map XML element -> widget index for parent tracking
    elem_to_idx: dict[int, int] = {}  # id(element) -> widget index
    idx = 0

    def _walk(node, parent_elem_id: int, depth: int):
        nonlocal idx
        for child in node:
            if child.tag != "node":
                continue
            bounds = parse_bounds(child.get("bounds", "[0,0][0,0]"))
            cx = (bounds[0] + bounds[2]) // 2
            cy = (bounds[1] + bounds[3]) // 2

            # Skip zero-area elements
            if bounds[2] - bounds[0] <= 0 or bounds[3] - bounds[1] <= 0:
                _walk(child, parent_elem_id, depth + 1)
                continue

            parent_widget_idx = elem_to_idx.get(parent_elem_id, -1)

            w = Widget(
                index=idx,
                text=child.get("text", ""),
                content_desc=child.get("content-desc", ""),
                resource_id=child.get("resource-id", ""),
                class_name=child.get("class", ""),
                package=child.get("package", ""),
                clickable=child.get("clickable", "false") == "true",
                enabled=child.get("enabled", "true") == "true",
                focusable=child.get("focusable", "false") == "true",
                scrollable=child.get("scrollable", "false") == "true",
                long_clickable=child.get("long-clickable", "false") == "true",
                selected=child.get("selected", "false") == "true",
                checked=child.get("checked", "false") == "true",
                bounds=bounds,
                center_x=cx,
                center_y=cy,
                depth=depth,
                parent_index=parent_widget_idx,
            )
            elem_to_idx[id(child)] = idx
            widgets.append(w)

            # Register this widget as a child of its parent
            if parent_widget_idx >= 0 and parent_widget_idx < len(widgets):
                widgets[parent_widget_idx].children_indices.append(idx)

            idx += 1
            _walk(child, id(child), depth + 1)

    _walk(root, id(root), 0)
    return widgets


def find_widget(widgets: list[Widget], text: Optional[str] = None, desc: Optional[str] = None,
                resource_id: Optional[str] = None, class_name: Optional[str] = None,
                clickable_only: bool = False) -> Optional[Widget]:
    """Find first widget matching criteria"""
    for w in widgets:
        if clickable_only and not (w.clickable or w.focusable):
            continue
        if text and w.matches_text(text):
            return w
        if desc and w.matches_desc(desc):
            return w
        if resource_id and w.matches_id(resource_id):
            return w
        if class_name and class_name.lower() in w.class_name.lower():
            return w
    return None


def find_all_widgets(widgets: list[Widget], text: Optional[str] = None, desc: Optional[str] = None,
                     resource_id: Optional[str] = None) -> list[Widget]:
    """Find all widgets matching criteria"""
    results = []
    for w in widgets:
        if text and w.matches_text(text):
            results.append(w)
        elif desc and w.matches_desc(desc):
            results.append(w)
        elif resource_id and w.matches_id(resource_id):
            results.append(w)
    return results


def format_screen_info(widgets: list[Widget], interactive_only: bool = False) -> str:
    """Format widget list for LLM context with tree indentation"""
    lines = []
    for w in widgets:
        if interactive_only and not (w.clickable or w.focusable or w.scrollable or w.text or w.content_desc):
            continue
        indent = "  " * min(w.depth, 8)  # cap indent to avoid excessive whitespace
        lines.append(f"{indent}{w.to_str()}")
    return "\n".join(lines)


class SessionMemory:
    """Persistent session memory for facts and task outcomes."""

    def __init__(self, memory_dir: Path):
        self.path = memory_dir / "session_memory.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_facts: dict[str, str] = {}
        self.task_facts: dict[str, str] = {}
        self.tasks: list[dict] = []
        self._load()

    @staticmethod
    def _normalize_key(key: str) -> str:
        return re.sub(r"\s+", "_", str(key).strip().lower())

    @staticmethod
    def _stringify_value(value) -> str:
        if isinstance(value, str):
            text = value.strip()
        else:
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        return text[:500]

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.session_facts = data.get("session_facts", {})
            self.tasks = data.get("tasks", [])
            if not isinstance(self.session_facts, dict):
                self.session_facts = {}
            if not isinstance(self.tasks, list):
                self.tasks = []
        except Exception:
            self.session_facts = {}
            self.tasks = []

    def _save(self):
        data = {
            "session_facts": self.session_facts,
            "tasks": self.tasks[-50:],
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def start_task(self):
        self.task_facts = {}

    def remember(self, key: str, value, scope: str = "task") -> tuple[bool, str]:
        k = self._normalize_key(key)
        if not k:
            return False, "Memory key is empty"
        v = self._stringify_value(value)
        if scope == "session":
            self.session_facts[k] = v
            self._save()
            return True, f"Saved session memory: {k}={v}"
        self.task_facts[k] = v
        return True, f"Saved task memory: {k}={v}"

    def recall(self, key: str, default: str = "") -> tuple[bool, str]:
        k = self._normalize_key(key)
        if k in self.task_facts:
            return True, self.task_facts[k]
        if k in self.session_facts:
            return True, self.session_facts[k]
        return False, default or f"No memory for key '{k}'"

    def task_memory_text(self) -> str:
        if not self.task_facts:
            return "(empty)"
        lines = [f"- {k}: {v}" for k, v in sorted(self.task_facts.items())]
        return "\n".join(lines)

    def session_facts_text(self, limit: int = 10) -> str:
        if not self.session_facts:
            return "(empty)"
        items = sorted(self.session_facts.items())[: max(1, limit)]
        return "\n".join([f"- {k}: {v}" for k, v in items])

    def session_history_text(self, limit: int = 5) -> str:
        if not self.tasks:
            return "(none yet)"
        lines = []
        for item in self.tasks[-limit:]:
            status = "SUCCESS" if item.get("success") else "FAIL"
            lines.append(f"- [{status}] {item.get('task', '')} -> {item.get('message', '')}")
        return "\n".join(lines)

    def session_timeline_text(self, limit: int = 25) -> str:
        if not self.tasks:
            return "(none yet)"
        rows = []
        for i, item in enumerate(self.tasks[-limit:], start=max(1, len(self.tasks) - limit + 1)):
            status = "OK" if item.get("success") else "FAIL"
            task_name = str(item.get("task", "")).strip().replace("\n", " ")[:120]
            rows.append(f"- #{i} [{status}] {task_name}")
        return "\n".join(rows)

    def record_task(self, task: str, success: bool, message: str, history_tail: list[str]):
        entry = {
            "time": datetime.utcnow().isoformat() + "Z",
            "task": task,
            "success": bool(success),
            "message": str(message)[:500],
            "task_facts": dict(self.task_facts),
            "history_tail": history_tail[-8:],
        }
        self.tasks.append(entry)

        # Promote task facts into session facts to keep all learned values available
        for k, v in self.task_facts.items():
            if k and v:
                self.session_facts[k] = v

        if len(self.tasks) > 100:
            self.tasks = self.tasks[-100:]
        self._save()


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE  (Demonstration Learning — save & retrieve successful traces)
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """
    Saves successful task traces as JSON files in KNOWLEDGE_DIR.
    On new tasks, retrieves the most similar past trace using keyword overlap
    so the LLM can learn from past solutions.
    """

    def __init__(self, knowledge_dir: Path):
        self.dir = knowledge_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index: list[dict] | None = None  # lazy loaded

    # ── persistence ──

    def save_trace(self, task: str, steps: list[str], success: bool, facts: dict):
        """Save a completed task trace for future reuse."""
        if not success or len(steps) < 2:
            return  # only save successful, non-trivial traces
        slug = re.sub(r"[^a-z0-9]+", "_", task.lower().strip())[:60].strip("_")
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{slug}.json"
        doc = {
            "task": task,
            "steps": steps[-30:],
            "facts": facts,
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }
        try:
            (self.dir / fname).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        self._index = None  # bust cache

    def _load_index(self) -> list[dict]:
        """Load all trace summaries (task + filename)."""
        if self._index is not None:
            return self._index
        index = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                index.append({"path": p, "task": doc.get("task", ""), "steps": doc.get("steps", [])})
            except Exception:
                continue
        self._index = index
        return index

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def retrieve(self, task: str, top_k: int = 2) -> list[dict]:
        """Return the top_k most similar past traces to the given task."""
        index = self._load_index()
        if not index:
            return []
        task_tokens = self._tokenize(task)
        if not task_tokens:
            return []
        scored = []
        for entry in index:
            entry_tokens = self._tokenize(entry["task"])
            if not entry_tokens:
                continue
            overlap = len(task_tokens & entry_tokens)
            jaccard = overlap / len(task_tokens | entry_tokens)
            if jaccard > 0.15:
                scored.append((jaccard, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def format_demonstrations(self, task: str, max_steps: int = 12) -> str:
        """Return a formatted string of similar past traces for LLM context."""
        demos = self.retrieve(task, top_k=2)
        if not demos:
            return ""
        parts = ["SIMILAR PAST TASKS (for reference):"]
        for i, d in enumerate(demos, 1):
            parts.append(f"\n  Demo {i}: {d['task']}")
            for step in d["steps"][:max_steps]:
                parts.append(f"    {step}")
            if len(d["steps"]) > max_steps:
                parts.append(f"    ... ({len(d['steps']) - max_steps} more steps)")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE CONTROLLER (ADB + UI Automator)
# ═══════════════════════════════════════════════════════════════════════════════

class DeviceController:
    """Full Android device control via ADB with widget-based interaction"""

    def __init__(self, config: Config):
        self.config = config
        self.adb = config.ADB_PATH
        self.device_flag = f"-s {config.DEVICE_SERIAL}" if config.DEVICE_SERIAL else ""
        self.width = 1080
        self.height = 2400
        self._widgets: list[Widget] = []
        self._last_xml = ""
        self.dynamic_package_map: dict[str, str] = {}
        self.installed_packages: set[str] = set()
        self._init_device()

    def _adb(self, cmd: str, timeout: Optional[int] = None) -> tuple[bool, str]:
        """Execute ADB command, return text output (utf-8 safe on Windows)"""
        full_cmd = f"{self.adb} {self.device_flag} {cmd}".strip()
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True,
                timeout=timeout or self.config.COMMAND_TIMEOUT
            )
            # Decode as utf-8 with replace to avoid cp1252 crash on Windows
            out = result.stdout.decode("utf-8", errors="replace")
            err = result.stderr.decode("utf-8", errors="replace")
            return result.returncode == 0, (out + err).strip()
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def _adb_bytes(self, cmd: str, timeout: Optional[int] = None) -> tuple[bool, bytes]:
        """Execute ADB command, return raw bytes"""
        full_cmd = f"{self.adb} {self.device_flag} {cmd}".strip()
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True,
                timeout=timeout or self.config.COMMAND_TIMEOUT
            )
            return result.returncode == 0, result.stdout
        except subprocess.TimeoutExpired:
            return False, b""
        except Exception as e:
            return False, b""

    def _init_device(self):
        success, out = self._adb("devices")
        if not success:
            raise RuntimeError(f"ADB error: {out}")
        success, out = self._adb("shell wm size")
        if success:
            m = re.search(r'(\d+)x(\d+)', out)
            if m:
                self.width, self.height = int(m.group(1)), int(m.group(2))
        print(f"[+] Device ready: {self.width}x{self.height}")
        self.refresh_package_cache()

    # ── Screenshot ──────────────────────────────────────────────────────────

    def screenshot(self) -> Optional[str]:
        """Capture screenshot as base64"""
        try:
            ok, data = self._adb_bytes("shell screencap -p", timeout=10)
            if ok and data:
                img = data.replace(b'\r\n', b'\n')
                path = self.config.TEMP_DIR / f"screen_{int(time.time()*1000)}.png"
                path.write_bytes(img)
                for old in sorted(self.config.TEMP_DIR.glob("screen_*.png"))[:-3]:
                    old.unlink(missing_ok=True)
                return base64.b64encode(img).decode()
        except Exception as e:
            print(f"[!] Screenshot error: {e}")
        return None

    def screenshot_with_som(self, screenshot_b64: Optional[str] = None) -> Optional[str]:
        """
        Set-of-Mark: Overlay numbered labels on interactive widgets.
        Takes a base64 screenshot and returns an annotated base64 screenshot.
        Each label corresponds to the widget index from the UI hierarchy.
        """
        if not HAS_PIL:
            return screenshot_b64  # fallback: return raw screenshot

        if not screenshot_b64:
            screenshot_b64 = self.screenshot()
        if not screenshot_b64:
            return None

        try:
            import io
            raw = base64.b64decode(screenshot_b64)
            img = Image.open(io.BytesIO(raw)).convert("RGBA")

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Try to get a compact font
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except Exception:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
                except Exception:
                    font = ImageFont.load_default()

            # Color palette for labels (high contrast)
            colors = [
                (255, 0, 0), (0, 200, 0), (0, 100, 255), (255, 165, 0),
                (255, 0, 255), (0, 200, 200), (200, 200, 0), (128, 0, 255),
                (255, 100, 100), (100, 255, 100), (100, 100, 255), (255, 200, 0),
            ]

            widgets = self._widgets
            annotated_count = 0
            for w in widgets:
                if not w.is_interactive() and not w.text and not w.content_desc:
                    continue

                color = colors[w.index % len(colors)]
                x1, y1, x2, y2 = w.bounds

                # Draw bounding box (semi-transparent)
                draw.rectangle([x1, y1, x2, y2], outline=color + (200,), width=2)

                # Draw label background + number
                label = str(w.index)
                bbox = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                lx, ly = max(0, x1), max(0, y1 - th - 4)
                if ly < 0:
                    ly = y1

                draw.rectangle([lx, ly, lx + tw + 6, ly + th + 4], fill=color + (220,))
                draw.text((lx + 3, ly + 1), label, fill=(255, 255, 255, 255), font=font)
                annotated_count += 1

            # Composite
            result = Image.alpha_composite(img, overlay).convert("RGB")
            buf = io.BytesIO()
            result.save(buf, format="PNG", optimize=True)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[!] SoM annotation error: {e}")
            return screenshot_b64  # fallback to raw screenshot

    # ── UI Hierarchy ────────────────────────────────────────────────────────

    def dump_ui(self) -> list[Widget]:
        """Dump UI hierarchy and parse all widgets"""
        # Dump to device
        self._adb("shell uiautomator dump /sdcard/ui_dump.xml", timeout=10)
        # Pull as binary then decode safely (avoids cp1252 crash on Windows)
        local_path = self.config.TEMP_DIR / "ui_dump.xml"
        ok, _ = self._adb(f"pull /sdcard/ui_dump.xml {local_path}", timeout=10)
        if ok and local_path.exists():
            try:
                xml_data = local_path.read_bytes().decode("utf-8", errors="replace")
                self._last_xml = xml_data
                self._widgets = parse_ui_hierarchy(xml_data)
            except Exception:
                self._widgets = []
        else:
            # Fallback: read via shell (already utf-8 safe from _adb fix)
            ok, xml_data = self._adb("shell cat /sdcard/ui_dump.xml", timeout=10)
            if ok and xml_data:
                self._last_xml = xml_data
                self._widgets = parse_ui_hierarchy(xml_data)
            else:
                self._widgets = []
        return self._widgets

    def get_screen_context(self) -> str:
        """Get formatted screen info for LLM"""
        widgets = self.dump_ui()
        if not widgets:
            return "ERROR: Could not dump UI hierarchy. Screen may be loading."

        # Get current activity/app
        _, activity = self._adb("shell dumpsys activity activities | grep mResumedActivity")
        current_app = activity.strip() if activity else "unknown"

        header = f"CURRENT APP: {current_app}\nSCREEN SIZE: {self.width}x{self.height}\nTOTAL ELEMENTS: {len(widgets)}\n"
        header += "─" * 60 + "\n"

        # Interactive elements (clickable, focusable, scrollable, or with text)
        interactive = []
        other = []
        for w in widgets:
            if w.clickable or w.focusable or w.scrollable or w.long_clickable:
                interactive.append(w)
            elif w.text or w.content_desc:
                other.append(w)

        lines = header
        if interactive:
            lines += f"\n▸ INTERACTIVE ELEMENTS ({len(interactive)}):\n"
            for w in interactive:
                lines += f"  {w.to_str()}\n"
        if other:
            lines += f"\n▸ TEXT/LABELS ({len(other)}):\n"
            for w in other:
                lines += f"  {w.to_str()}\n"

        return lines

    # ── Widget-Based Actions ────────────────────────────────────────────────

    def _find(self, text: Optional[str] = None, desc: Optional[str] = None,
              resource_id: Optional[str] = None, index: Optional[int] = None) -> Optional[Widget]:
        """Find a widget from current hierarchy"""
        if index is not None and 0 <= index < len(self._widgets):
            return self._widgets[index]
        found = find_widget(self._widgets, text=text, desc=desc, resource_id=resource_id)
        if found:
            return found

        # Retry once with fresh UI dump to avoid stale hierarchy mismatch.
        self.dump_ui()
        if index is not None and 0 <= index < len(self._widgets):
            return self._widgets[index]
        return find_widget(self._widgets, text=text, desc=desc, resource_id=resource_id)

    def tap_by_text(self, text: str) -> tuple[bool, str]:
        w = self._find(text=text)
        if not w:
            return False, f"No widget with text containing '{text}'"
        ok, msg = self._adb(f"shell input tap {w.center_x} {w.center_y}")
        return ok, f"Tapped '{text}' at ({w.center_x},{w.center_y})"

    def tap_by_desc(self, desc: str) -> tuple[bool, str]:
        w = self._find(desc=desc)
        if not w:
            return False, f"No widget with description containing '{desc}'"
        ok, msg = self._adb(f"shell input tap {w.center_x} {w.center_y}")
        return ok, f"Tapped desc='{desc}' at ({w.center_x},{w.center_y})"

    def tap_by_id(self, resource_id: str) -> tuple[bool, str]:
        w = self._find(resource_id=resource_id)
        if not w:
            return False, f"No widget with resource-id containing '{resource_id}'"
        ok, msg = self._adb(f"shell input tap {w.center_x} {w.center_y}")
        return ok, f"Tapped id='{resource_id}' at ({w.center_x},{w.center_y})"

    def tap_by_index(self, index: int) -> tuple[bool, str]:
        w = self._find(index=index)
        if not w:
            return False, f"No widget at index {index}"
        ok, msg = self._adb(f"shell input tap {w.center_x} {w.center_y}")
        label = w.text or w.content_desc or w.resource_id or f"index={index}"
        return ok, f"Tapped [{index}] '{label}' at ({w.center_x},{w.center_y})"

    def tap_xy(self, x: int, y: int) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell input tap {x} {y}")
        return ok, f"Tapped coordinates ({x},{y})"

    def long_press_by_text(self, text: str, ms: int = 1000) -> tuple[bool, str]:
        w = self._find(text=text)
        if not w:
            return False, f"No widget with text '{text}'"
        ok, msg = self._adb(f"shell input swipe {w.center_x} {w.center_y} {w.center_x} {w.center_y} {ms}")
        return ok, f"Long-pressed '{text}' for {ms}ms"

    def long_press_by_desc(self, desc: str, ms: int = 1000) -> tuple[bool, str]:
        w = self._find(desc=desc)
        if not w:
            return False, f"No widget with desc '{desc}'"
        ok, msg = self._adb(f"shell input swipe {w.center_x} {w.center_y} {w.center_x} {w.center_y} {ms}")
        return ok, f"Long-pressed desc='{desc}' for {ms}ms"

    def long_press_xy(self, x: int, y: int, ms: int = 1000) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell input swipe {x} {y} {x} {y} {ms}")
        return ok, f"Long-pressed ({x},{y}) for {ms}ms"

    # ── Text Input ──────────────────────────────────────────────────────────

    def type_text(self, text: str) -> tuple[bool, str]:
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("(", "\\(").replace(")", "\\)").replace("|", "\\|").replace(";", "\\;").replace("$", "\\$").replace("`", "\\`").replace('"', '\\"')
        ok, msg = self._adb(f'shell input text "{escaped}"')
        return ok, f"Typed: {text}"

    def clear_field(self) -> tuple[bool, str]:
        """Clear current input field using multiple strategies for reliability."""
        # Strategy 1: Ctrl+A then Delete (works on most standard fields)
        self._adb("shell input keyevent 29 --meta-state 28672")  # Ctrl+A (select all)
        time.sleep(0.1)
        self._adb("shell input keyevent 67")  # DELETE
        time.sleep(0.1)

        # Strategy 2: If field still has text, try long-pressing Delete
        # Move to end of text first, then delete backwards
        self._adb("shell input keyevent 123")  # MOVE_END
        time.sleep(0.05)
        # Select all from end to start
        self._adb("shell input keyevent 29 --meta-state 28672")  # Ctrl+A
        time.sleep(0.05)
        ok, msg = self._adb("shell input keyevent 67")  # DELETE
        return ok, "Cleared field (multi-strategy)"

    def clear_and_type(self, text: str) -> tuple[bool, str]:
        """Clear current field then type new text"""
        # Triple-tap to select all text in field
        self.clear_field()
        time.sleep(0.2)
        return self.type_text(text)

    # ── Navigation & Gestures ───────────────────────────────────────────────

    def press_key(self, key_name: str) -> tuple[bool, str]:
        code = KEYCODES.get(key_name.upper(), key_name)
        ok, msg = self._adb(f"shell input keyevent {code}")
        return ok, f"Pressed {key_name}"

    def scroll(self, direction: str) -> tuple[bool, str]:
        cx, cy = self.width // 2, self.height // 2
        d = self.height // 3
        moves = {
            "UP": (cx, cy + d, cx, cy - d),
            "DOWN": (cx, cy - d, cx, cy + d),
            "LEFT": (cx + d, cy, cx - d, cy),
            "RIGHT": (cx - d, cy, cx + d, cy)
        }
        coords = moves.get(direction.upper(), moves["DOWN"])
        ok, msg = self._adb(f"shell input swipe {coords[0]} {coords[1]} {coords[2]} {coords[3]} 300")
        return ok, f"Scrolled {direction}"

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell input swipe {x1} {y1} {x2} {y2} {ms}")
        return ok, f"Swiped ({x1},{y1})->({x2},{y2}) in {ms}ms"

    # ── App Management ──────────────────────────────────────────────────────

    @staticmethod
    def _normalize_app_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()

    def refresh_package_cache(self) -> tuple[bool, str]:
        """Discover installed user apps and build a dynamic alias map."""
        ok, msg = self._adb("shell pm list packages -3")
        if not ok:
            return False, msg

        packages = []
        for line in msg.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg = line.split(":", 1)[1].strip()
                if pkg:
                    packages.append(pkg)

        self.installed_packages = set(packages)
        dynamic_map: dict[str, str] = {}
        for pkg in packages:
            parts = [p for p in pkg.split(".") if p]
            aliases = {
                pkg,
                pkg.replace(".", " "),
                parts[-1] if parts else pkg,
            }
            if len(parts) >= 2:
                aliases.add(f"{parts[-2]} {parts[-1]}")
            for alias in aliases:
                key = self._normalize_app_name(alias)
                if key and key not in dynamic_map:
                    dynamic_map[key] = pkg

        self.dynamic_package_map = dynamic_map
        return True, f"Discovered {len(self.installed_packages)} installed user packages"

    def resolve_app_package(self, name: str) -> tuple[Optional[str], str]:
        raw = str(name).strip()
        if not raw:
            return None, "empty_name"

        # If the user already passed a package id, use it directly.
        if "." in raw and " " not in raw:
            return raw, "explicit_package"

        query = self._normalize_app_name(raw)
        if not query:
            return None, "empty_name"

        if query in self.dynamic_package_map:
            return self.dynamic_package_map[query], "dynamic_exact"

        if query in PACKAGE_MAP:
            return PACKAGE_MAP[query], "fallback_exact"

        for alias, pkg in self.dynamic_package_map.items():
            if query in alias or alias in query:
                return pkg, "dynamic_fuzzy"

        for alias, pkg in PACKAGE_MAP.items():
            if query in alias or alias in query:
                return pkg, "fallback_fuzzy"

        close = get_close_matches(query, list(self.dynamic_package_map.keys()), n=1, cutoff=0.72)
        if close:
            return self.dynamic_package_map[close[0]], "dynamic_close_match"

        return None, "not_found"

    def launch_app(self, package: str) -> tuple[bool, str]:
        """Launch app by package name"""
        ok, msg = self._adb(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1")
        return ok, f"Launched {package}"

    def launch_app_by_name(self, name: str) -> tuple[bool, str]:
        """Launch app by human name using dynamic discovery first."""
        pkg, source = self.resolve_app_package(name)
        if not pkg:
            self.refresh_package_cache()
            pkg, source = self.resolve_app_package(name)
        if not pkg:
            return False, (
                f"Unknown app '{name}'. Use web_search to find the package or call list_packages "
                f"to inspect installed apps."
            )
        ok, msg = self.launch_app(pkg)
        if ok:
            return True, f"Launched '{name}' as {pkg} ({source})"
        return False, msg

    def launch_activity(self, package: str, activity: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell am start -n {package}/{activity}")
        return ok, f"Launched {package}/{activity}"

    def force_stop(self, package: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell am force-stop {package}")
        return ok, f"Force stopped {package}"

    def clear_app_data(self, package: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell pm clear {package}")
        return ok, f"Cleared data for {package}"

    def get_current_app(self) -> tuple[bool, str]:
        ok, out = self._adb("shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        return ok, out

    def install_app(self, apk_path: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"install {apk_path}")
        return ok, msg

    def uninstall_app(self, package: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"uninstall {package}")
        return ok, msg

    def list_packages(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell pm list packages -3")
        if ok:
            self.refresh_package_cache()
        return ok, msg

    # ── URL & Settings ──────────────────────────────────────────────────────

    def open_url(self, url: str) -> tuple[bool, str]:
        ok, msg = self._adb(f'shell am start -a android.intent.action.VIEW -d "{url}"')
        return ok, f"Opened URL: {url}"

    def open_settings(self, setting: str = "") -> tuple[bool, str]:
        intent = SETTINGS_INTENTS.get(setting.lower(), "android.settings.SETTINGS")
        ok, msg = self._adb(f"shell am start -a {intent}")
        return ok, f"Opened settings: {setting or 'main'}"

    # ── System Controls ─────────────────────────────────────────────────────

    def toggle_wifi(self, enable: bool) -> tuple[bool, str]:
        state = "enable" if enable else "disable"
        ok, msg = self._adb(f"shell svc wifi {state}")
        return ok, f"WiFi {'enabled' if enable else 'disabled'}"

    def toggle_bluetooth(self, enable: bool) -> tuple[bool, str]:
        # Requires root on some devices; settings fallback
        if enable:
            ok, msg = self._adb("shell am start -a android.bluetooth.adapter.action.REQUEST_ENABLE")
        else:
            ok, msg = self._adb("shell settings put global bluetooth_on 0")
        return ok, f"Bluetooth {'enabled' if enable else 'disabled'}"

    def set_brightness(self, level: int) -> tuple[bool, str]:
        level = max(0, min(255, level))
        self._adb("shell settings put system screen_brightness_mode 0")  # manual
        ok, msg = self._adb(f"shell settings put system screen_brightness {level}")
        return ok, f"Brightness set to {level}/255"

    def set_volume(self, stream: str, level: int) -> tuple[bool, str]:
        streams = {"media": "3", "ring": "2", "alarm": "4", "notification": "5"}
        s = streams.get(stream.lower(), "3")
        ok, msg = self._adb(f"shell media volume --stream {s} --set {level}")
        return ok, f"Volume {stream} set to {level}"

    def toggle_airplane(self, enable: bool) -> tuple[bool, str]:
        val = "1" if enable else "0"
        self._adb(f"shell settings put global airplane_mode_on {val}")
        ok, msg = self._adb("shell am broadcast -a android.intent.action.AIRPLANE_MODE")
        return ok, f"Airplane mode {'on' if enable else 'off'}"

    def toggle_rotation(self, enable: bool) -> tuple[bool, str]:
        val = "1" if enable else "0"
        ok, msg = self._adb(f"shell settings put system accelerometer_rotation {val}")
        return ok, f"Auto-rotation {'on' if enable else 'off'}"

    # ── Notifications ───────────────────────────────────────────────────────

    def open_notifications(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell cmd statusbar expand-notifications")
        return ok, "Opened notification shade"

    def open_quick_settings(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell cmd statusbar expand-settings")
        return ok, "Opened quick settings"

    def dismiss_notifications(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell service call notification 1")
        return ok, "Dismissed notifications"

    # ── Device Info ─────────────────────────────────────────────────────────

    def get_device_info(self) -> tuple[bool, str]:
        info = []
        for prop in ["ro.product.model", "ro.product.manufacturer", "ro.build.version.release",
                      "ro.build.version.sdk"]:
            _, val = self._adb(f"shell getprop {prop}")
            info.append(f"{prop}: {val}")
        return True, "\n".join(info)

    def get_battery(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell dumpsys battery")
        return ok, msg

    # ── File Operations ─────────────────────────────────────────────────────

    def push_file(self, local: str, remote: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"push {local} {remote}")
        return ok, msg

    def pull_file(self, remote: str, local: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"pull {remote} {local}")
        return ok, msg

    def shell(self, command: str) -> tuple[bool, str]:
        ok, msg = self._adb(f"shell {command}")
        return ok, msg

    # ── Clipboard ───────────────────────────────────────────────────────────

    def get_clipboard(self) -> tuple[bool, str]:
        ok, msg = self._adb("shell am broadcast -a clipper.get")
        return ok, msg

    def set_clipboard(self, text: str) -> tuple[bool, str]:
        ok, msg = self._adb(f'shell am broadcast -a clipper.set -e text "{text}"')
        return ok, msg

    # ── Waiting ─────────────────────────────────────────────────────────────

    def wait(self, ms: int = 1000) -> tuple[bool, str]:
        time.sleep(ms / 1000)
        return True, f"Waited {ms}ms"

    def wait_for_widget(self, text: Optional[str] = None, desc: Optional[str] = None,
                        timeout: int = 10) -> tuple[bool, str]:
        """Poll until a widget appears"""
        start = time.time()
        while time.time() - start < timeout:
            self.dump_ui()
            w = self._find(text=text, desc=desc)
            if w:
                return True, f"Widget found: {w.to_str()}"
            time.sleep(0.5)
        return False, f"Widget not found after {timeout}s"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR TAXONOMY & AUTO-INTERRUPTION HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorType:
    ELEMENT_NOT_FOUND = "element_not_found"
    APP_CRASH = "app_crash"
    NETWORK_TIMEOUT = "network_timeout"
    PERMISSION_DIALOG = "permission_dialog"
    KEYBOARD_BLOCKING = "keyboard_blocking"
    STALE_HIERARCHY = "stale_hierarchy"
    SYSTEM_DIALOG = "system_dialog"
    UNKNOWN = "unknown"


def classify_error(success: bool, message: str, action: str) -> str:
    """Classify a tool execution result into an error category."""
    if success:
        return ""
    msg_lower = message.lower()
    if "no widget" in msg_lower or "not found" in msg_lower:
        return ErrorType.ELEMENT_NOT_FOUND
    if "timeout" in msg_lower:
        return ErrorType.NETWORK_TIMEOUT
    if "crash" in msg_lower or "stopped" in msg_lower:
        return ErrorType.APP_CRASH
    if "could not dump" in msg_lower or "error" in msg_lower and "hierarchy" in msg_lower:
        return ErrorType.STALE_HIERARCHY
    return ErrorType.UNKNOWN


# Patterns to detect common system interruptions in the UI hierarchy
INTERRUPTION_PATTERNS = {
    # (resource_id_contains, text_contains, desc_contains) → action to take
    "permission": {
        "detect": [
            {"id": "com.android.permissioncontroller", "text": ""},
            {"id": "permission", "text": "Allow"},
            {"id": "", "text": "While using the app"},
            {"id": "", "text": "Only this time"},
        ],
        "tap_texts": ["While using the app", "Allow", "Only this time", "ALLOW"],
    },
    "app_crash": {
        "detect": [
            {"id": "", "text": "has stopped"},
            {"id": "", "text": "keeps stopping"},
            {"id": "", "text": "isn't responding"},
            {"id": "aerr_", "text": ""},
        ],
        "tap_texts": ["OK", "Close app", "Close"],
    },
    "cookie_consent": {
        "detect": [
            {"id": "cookie", "text": ""},
            {"id": "consent", "text": ""},
            {"id": "", "text": "Accept all"},
            {"id": "", "text": "Accept cookies"},
        ],
        "tap_texts": ["Accept all", "Accept", "Accept cookies", "Agree", "OK"],
    },
    "update_prompt": {
        "detect": [
            {"id": "", "text": "Update available"},
            {"id": "", "text": "New version"},
        ],
        "tap_texts": ["Not now", "Later", "Skip", "No thanks", "NO THANKS"],
    },
    "rating_prompt": {
        "detect": [
            {"id": "", "text": "Rate this app"},
            {"id": "", "text": "Enjoying"},
            {"id": "rating", "text": ""},
        ],
        "tap_texts": ["Not now", "Maybe later", "No thanks", "NO THANKS"],
    },
}


class InterruptionHandler:
    """Auto-handle common system dialogs without wasting an LLM call."""

    @staticmethod
    def detect_and_handle(device: 'DeviceController') -> tuple[bool, str]:
        """
        Check current screen for known interruption patterns.
        If found, auto-dismiss and return (True, description).
        If nothing found, return (False, "").
        """
        widgets = device._widgets
        if not widgets:
            return False, ""

        for interrupt_name, config in INTERRUPTION_PATTERNS.items():
            detected = False
            for pattern in config["detect"]:
                pat_id = pattern.get("id", "").lower()
                pat_text = pattern.get("text", "").lower()
                for w in widgets:
                    id_match = pat_id and pat_id in w.resource_id.lower() if pat_id else False
                    text_match = pat_text and pat_text in w.text.lower() if pat_text else False
                    if id_match or text_match:
                        detected = True
                        break
                if detected:
                    break

            if detected:
                # Try to tap one of the dismiss buttons
                for tap_text in config["tap_texts"]:
                    for w in widgets:
                        if w.text and tap_text.lower() in w.text.lower() and (w.clickable or w.focusable):
                            ok, msg = device.tap_by_text(tap_text)
                            if ok:
                                time.sleep(0.5)
                                return True, f"Auto-handled {interrupt_name}: tapped '{tap_text}'"
                    # Also try by desc
                    for w in widgets:
                        if w.content_desc and tap_text.lower() in w.content_desc.lower():
                            ok, msg = device.tap_by_desc(tap_text)
                            if ok:
                                time.sleep(0.5)
                                return True, f"Auto-handled {interrupt_name}: tapped desc '{tap_text}'"

        return False, ""


# ═══════════════════════════════════════════════════════════════════════════════
# TASK PLANNER — Decomposes complex tasks into sub-goals
# ═══════════════════════════════════════════════════════════════════════════════

PLANNER_PROMPT = """You are a task planning assistant for an Android phone automation agent.

Given a user task, break it into a numbered list of concrete sub-goals.
Each sub-goal should be a single, verifiable step that the agent can execute and confirm.

Rules:
- Keep sub-goals specific and actionable (not vague).
- Include app launches, navigation, data entry, and verification steps.
- For multi-app tasks, include switching between apps.
- Include memory operations (save email, save OTP) when data needs to transfer between apps.
- Maximum 15 sub-goals. Simple tasks may only need 2-3.
- Output ONLY a JSON array of strings. No other text.

Example: Task "Send a WhatsApp message to Mom saying Hello"
["Launch WhatsApp", "Find and tap Mom's chat", "Tap the message input field", "Type 'Hello'", "Tap the send button", "Verify message appears in chat"]

Example: Task "Turn on WiFi"
["Open Settings or Quick Settings", "Toggle WiFi on", "Verify WiFi is enabled"]
"""


class TaskPlanner:
    """Decomposes a task into sub-goals using the LLM before execution begins."""

    @staticmethod
    async def plan(llm: 'LLMClient', task: str, memory_context: str = "") -> list[str]:
        """Generate a list of sub-goals for the given task."""
        messages = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"Task: {task}\n\nContext (known facts):\n{memory_context}"},
        ]
        try:
            response = await llm.chat(messages, max_tokens=512)
            # Extract JSON array from response
            response = response.strip()
            # Handle markdown code blocks
            if "```" in response:
                for block in re.findall(r'```(?:json)?\s*([\s\S]*?)```', response):
                    response = block.strip()
                    break
            plan = json.loads(response)
            if isinstance(plan, list) and all(isinstance(s, str) for s in plan):
                return plan[:15]
        except Exception as e:
            print(f"[!] Task planning failed: {e}")
        # Fallback: single sub-goal = the whole task
        return [task]

    @staticmethod
    def format_plan_for_context(plan: list[str], current_step: int) -> str:
        """Format the plan for injection into the LLM context."""
        if not plan or len(plan) <= 1:
            return ""
        lines = ["TASK PLAN:"]
        for i, step in enumerate(plan):
            if i < current_step:
                marker = "✓"
            elif i == current_step:
                marker = "→"
            else:
                marker = " "
            lines.append(f"  {marker} {i+1}. {step}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — imported from system_prompt.py (single source of truth)
# ═══════════════════════════════════════════════════════════════════════════════

from system_prompt import SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTOR (Maps LLM JSON responses to DeviceController methods)
# ═══════════════════════════════════════════════════════════════════════════════

class ToolExecutor:
    """Maps tool calls from LLM to DeviceController methods"""

    def __init__(
        self,
        device: DeviceController,
        ask_user_fn=None,
        remember_fn=None,
        recall_fn=None,
        web_search_fn=None,
    ):
        self.device = device
        self._ask_user_fn = ask_user_fn
        self._remember_fn = remember_fn
        self._recall_fn = recall_fn
        self._web_search_fn = web_search_fn
        self._local_memory: dict[str, str] = {}

    @staticmethod
    def _normalize_memory_key(key: str) -> str:
        return re.sub(r"\s+", "_", str(key).strip().lower())

    @staticmethod
    def _direct_web_search(query: str, max_results: int = 5) -> tuple[bool, str]:
        if DDGS is None:
            return False, "web_search unavailable: duckduckgo-search is not installed"
        safe_max = max(1, min(int(max_results), 8))
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=safe_max))
        except Exception as e:
            return False, f"web_search failed: {e}"

        if not results:
            return False, f"No web results for query: {query}"

        lines = []
        for i, item in enumerate(results, start=1):
            title = re.sub(r"\s+", " ", str(item.get("title", ""))).strip()[:120]
            href = re.sub(r"\s+", " ", str(item.get("href", ""))).strip()[:180]
            body = re.sub(r"\s+", " ", str(item.get("body", ""))).strip()[:220]
            lines.append(f"[{i}] {title}\nURL: {href}\nSnippet: {body}")
        return True, "\n\n".join(lines)

    @staticmethod
    def _get_param(params: dict, *names: str, default=None, required: bool = False):
        for name in names:
            if name in params and params[name] not in (None, ""):
                return params[name]
        if required:
            raise KeyError(names[0] if names else "param")
        return default

    @staticmethod
    def _extract_package_candidates(text: str) -> list[str]:
        matches = re.findall(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", text.lower())
        banned_first = {"www", "m", "play", "support", "help", "blog", "api", "docs"}
        tlds = {"com", "org", "net", "io", "gov", "edu", "co", "uk", "fr", "de", "cn"}
        seen = set()
        packages = []
        for pkg in matches:
            parts = pkg.split(".")
            if not parts:
                continue
            if parts[0] in banned_first:
                continue
            if parts[-1] in tlds:
                continue
            if pkg in seen:
                continue
            seen.add(pkg)
            packages.append(pkg)
        return packages

    @staticmethod
    def _query_to_alias(query: str) -> str:
        q = re.sub(r"[^a-z0-9\s]", " ", str(query).lower())
        tokens = [t for t in q.split() if t]
        stop = {
            "package", "name", "android", "apk", "app", "download", "official",
            "play", "store", "google", "for", "on", "in", "the", "tunisia", "tunisie",
        }
        kept = [t for t in tokens if t not in stop]
        return " ".join(kept[:4]).strip()

    def _learn_package_alias_from_search(self, query: str, search_text: str):
        if self.device is None:
            return
        alias = self._query_to_alias(query)
        if not alias:
            return
        candidates = self._extract_package_candidates(search_text)
        if not candidates:
            return
        package = candidates[0]
        try:
            installed = getattr(self.device, "installed_packages", set()) or set()
            installed_match = next((c for c in candidates if c in installed), None)
            if installed_match:
                package = installed_match
        except Exception:
            pass
        try:
            normalized = re.sub(r"[^a-z0-9]+", " ", alias).strip()
            if normalized:
                self.device.dynamic_package_map[normalized] = package
                if self._remember_fn:
                    self._remember_fn(f"package_alias_{normalized.replace(' ', '_')}", package, "session")
        except Exception:
            pass

    def execute(self, action: str, params: dict) -> tuple[bool, str, bool]:
        """Execute a tool. Returns (success, message, is_terminal)"""
        action = action.lower().strip()
        try:
            # ── Intelligence tools ──
            if action == "web_search":
                query = self._get_param(params, "query", "q", required=True)
                if not query:
                    return False, "Missing parameter: query", False
                max_results = int(self._get_param(params, "max_results", "limit", default=5))
                if self._web_search_fn:
                    ok, msg = self._web_search_fn(query, max_results)
                else:
                    ok, msg = self._direct_web_search(query, max_results)
                if ok:
                    self._learn_package_alias_from_search(query, msg)
                return ok, msg, False

            elif action == "remember":
                key = self._get_param(params, "key", "name", required=True)
                if not key:
                    return False, "Missing parameter: key", False
                value = self._get_param(params, "value", "text", default="")
                scope = self._get_param(params, "scope", default="task")
                if self._remember_fn:
                    ok, msg = self._remember_fn(key, value, scope)
                else:
                    normalized = self._normalize_memory_key(key)
                    self._local_memory[normalized] = str(value)
                    ok, msg = True, f"Saved local memory: {normalized}={value}"
                return ok, msg, False

            elif action == "recall":
                key = self._get_param(params, "key", "name", required=True)
                if not key:
                    return False, "Missing parameter: key", False
                default = self._get_param(params, "default", default="")
                if self._recall_fn:
                    ok, value = self._recall_fn(key, default)
                else:
                    normalized = self._normalize_memory_key(key)
                    if normalized in self._local_memory:
                        ok, value = True, self._local_memory[normalized]
                    else:
                        ok, value = False, default or f"No memory for key '{normalized}'"
                return ok, f"Memory[{key}] = {value}", False

            # ── Widget tapping ──
            elif action == "tap_by_text":
                text = self._get_param(params, "text", "label", required=True)
                ok, msg = self.device.tap_by_text(text)
                return ok, msg, False
            elif action == "tap_by_desc":
                desc = self._get_param(params, "desc", "description", "content_desc", required=True)
                ok, msg = self.device.tap_by_desc(desc)
                return ok, msg, False
            elif action == "tap_by_id":
                resource_id = self._get_param(params, "resource_id", "id", required=True)
                ok, msg = self.device.tap_by_id(resource_id)
                return ok, msg, False
            elif action == "tap_by_index":
                ok, msg = self.device.tap_by_index(int(params["index"]))
                return ok, msg, False
            elif action == "long_press_text":
                ok, msg = self.device.long_press_by_text(params["text"], int(params.get("ms", 1000)))
                return ok, msg, False
            elif action == "long_press_desc":
                ok, msg = self.device.long_press_by_desc(params["desc"], int(params.get("ms", 1000)))
                return ok, msg, False

            # ── Coordinate tapping ──
            elif action == "tap_xy":
                ok, msg = self.device.tap_xy(int(params["x"]), int(params["y"]))
                return ok, msg, False
            elif action == "long_press_xy":
                ok, msg = self.device.long_press_xy(int(params["x"]), int(params["y"]), int(params.get("ms", 1000)))
                return ok, msg, False

            # ── Text input ──
            elif action == "type_text":
                idx = self._get_param(params, "index", default=None)
                if idx is not None:
                    self.device.tap_by_index(int(idx))
                    time.sleep(0.05)
                text = self._get_param(params, "text", "value", required=True)
                ok, msg = self.device.type_text(text)
                return ok, msg, False
            elif action == "clear_and_type":
                idx = self._get_param(params, "index", default=None)
                if idx is not None:
                    self.device.tap_by_index(int(idx))
                    time.sleep(0.05)
                text = self._get_param(params, "text", "value", required=True)
                ok, msg = self.device.clear_and_type(text)
                return ok, msg, False
            elif action == "clear_field":
                ok, msg = self.device.clear_field()
                return ok, msg, False

            # ── Navigation ──
            elif action == "press_key":
                key = self._get_param(params, "key", "key_name", required=True)
                ok, msg = self.device.press_key(key)
                return ok, msg, False
            elif action == "scroll":
                direction = self._get_param(params, "direction", "dir", default="DOWN")
                ok, msg = self.device.scroll(direction)
                return ok, msg, False
            elif action == "swipe":
                ok, msg = self.device.swipe(
                    int(params["x1"]), int(params["y1"]),
                    int(params["x2"]), int(params["y2"]),
                    int(params.get("ms", 300))
                )
                return ok, msg, False

            # ── App management ──
            elif action == "launch_app":
                package = self._get_param(params, "package", "pkg", required=True)
                ok, msg = self.device.launch_app(package)
                return ok, msg, False
            elif action == "launch_app_name":
                name = self._get_param(params, "name", "app_name", "app", required=True)
                ok, msg = self.device.launch_app_by_name(name)
                return ok, msg, False
            elif action == "force_stop":
                ok, msg = self.device.force_stop(params["package"])
                return ok, msg, False
            elif action == "clear_app_data":
                ok, msg = self.device.clear_app_data(params["package"])
                return ok, msg, False
            elif action == "get_current_app":
                ok, msg = self.device.get_current_app()
                return ok, msg, False
            elif action == "install_app":
                ok, msg = self.device.install_app(params.get("apk_path", params.get("path", "")))
                return ok, msg, False
            elif action == "uninstall_app":
                ok, msg = self.device.uninstall_app(params["package"])
                return ok, msg, False
            elif action == "list_packages":
                ok, msg = self.device.list_packages()
                return ok, msg, False

            # ── URL & Settings ──
            elif action == "open_url":
                url = self._get_param(params, "url", "link", required=True)
                ok, msg = self.device.open_url(url)
                return ok, msg, False
            elif action == "open_settings":
                setting = self._get_param(params, "setting", "name", default="")
                ok, msg = self.device.open_settings(setting)
                return ok, msg, False

            # ── System controls ──
            elif action == "toggle_wifi":
                ok, msg = self.device.toggle_wifi(bool(params.get("enable", True)))
                return ok, msg, False
            elif action == "toggle_bluetooth":
                ok, msg = self.device.toggle_bluetooth(bool(params.get("enable", True)))
                return ok, msg, False
            elif action == "set_brightness":
                ok, msg = self.device.set_brightness(int(params["level"]))
                return ok, msg, False
            elif action == "set_volume":
                ok, msg = self.device.set_volume(params.get("stream", "media"), int(params["level"]))
                return ok, msg, False
            elif action == "toggle_airplane":
                ok, msg = self.device.toggle_airplane(bool(params.get("enable", True)))
                return ok, msg, False
            elif action == "toggle_rotation":
                ok, msg = self.device.toggle_rotation(bool(params.get("enable", True)))
                return ok, msg, False

            # ── Notifications ──
            elif action == "open_notifications":
                ok, msg = self.device.open_notifications()
                return ok, msg, False
            elif action == "open_quick_settings":
                ok, msg = self.device.open_quick_settings()
                return ok, msg, False
            elif action == "dismiss_notifications":
                ok, msg = self.device.dismiss_notifications()
                return ok, msg, False

            # ── Device info ──
            elif action == "get_device_info":
                ok, msg = self.device.get_device_info()
                return ok, msg, False
            elif action == "get_battery":
                ok, msg = self.device.get_battery()
                return ok, msg, False

            # ── Files ──
            elif action == "shell":
                command = self._get_param(params, "command", "cmd", required=True)
                ok, msg = self.device.shell(command)
                return ok, msg, False
            elif action == "push_file":
                ok, msg = self.device.push_file(params["local"], params["remote"])
                return ok, msg, False
            elif action == "pull_file":
                ok, msg = self.device.pull_file(params["remote"], params["local"])
                return ok, msg, False

            # ── Clipboard ──
            elif action == "get_clipboard":
                ok, msg = self.device.get_clipboard()
                return ok, msg, False
            elif action == "set_clipboard":
                text = self._get_param(params, "text", "value", required=True)
                ok, msg = self.device.set_clipboard(text)
                return ok, msg, False

            # ── Waiting ──
            elif action == "wait":
                ms = int(self._get_param(params, "ms", "duration", default=1000))
                ok, msg = self.device.wait(ms)
                return ok, msg, False
            elif action == "wait_for_widget":
                ok, msg = self.device.wait_for_widget(
                    text=self._get_param(params, "text", default=None),
                    desc=self._get_param(params, "desc", "description", "content_desc", default=None),
                    timeout=int(self._get_param(params, "timeout", default=10))
                )
                return ok, msg, False

            # ── Ask user for clarification ──
            elif action == "ask_user":
                question = self._get_param(params, "question", "prompt", required=True)
                if not question:
                    return False, "Missing 'question' parameter for ask_user", False
                if self._ask_user_fn:
                    answer = self._ask_user_fn(question)
                    return True, f"User answered: {answer}", False
                else:
                    return False, "ask_user not available in this mode", False

            # ── Terminal actions ──
            elif action == "done":
                return True, params.get("reason", "Task completed"), True
            elif action == "fail":
                return False, params.get("reason", "Task failed"), True

            else:
                return False, f"Unknown tool: {action}", False

        except KeyError as e:
            return False, f"Missing parameter: {e}", False
        except Exception as e:
            return False, f"Tool error: {e}", False


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """Async LLM client for OpenRouter with reasoning support"""

    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # Store last assistant message for reasoning_details continuity
        self._last_assistant_msg: Optional[dict] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def chat(self, messages: list, max_tokens: int = 1024) -> str:
        """
        Send chat completion request.
        Supports reasoning mode (extended thinking) when config.REASONING_ENABLED=True.
        Preserves reasoning_details across turns for conversation continuity.
        """
        session = await self._get_session()

        payload: dict = {
            "model": self.config.LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "reasoning": {
                "enabled": bool(self.config.REASONING_ENABLED),
                "exclude": not bool(self.config.REASONING_ENABLED),
                "effort": "low" if self.config.REASONING_ENABLED else "none",
            },
        }

        # Add extra token budget only when reasoning is enabled
        if self.config.REASONING_ENABLED:
            # Increase max_tokens for reasoning models (they need room to think)
            if max_tokens < 4096:
                payload["max_tokens"] = 4096

        headers = {
            "Authorization": f"Bearer {self.config.LLM_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rundroid",
            "X-Title": "Phone Brain"
        }

        async with session.post(
            f"{self.config.LLM_BASE_URL}/chat/completions",
            headers=headers, json=payload
        ) as resp:
            data = await resp.json()

            if resp.status != 200:
                error = data.get("error", {}).get("message", str(data))
                raise RuntimeError(f"API Error ({resp.status}): {error}")

            if "choices" in data and data["choices"]:
                msg = data["choices"][0]["message"]
                content = msg.get("content", "").strip()

                # Store full assistant message (including reasoning_details) for next turn
                self._last_assistant_msg = {
                    "role": "assistant",
                    "content": content,
                }
                # Preserve reasoning_details if present (for conversation continuity)
                if msg.get("reasoning_details"):
                    self._last_assistant_msg["reasoning_details"] = msg["reasoning_details"]

                return content
            elif "content" in data:
                return data["content"][0]["text"].strip()
            elif "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                raise RuntimeError(f"Unknown response format: {list(data.keys())}")

    def get_last_assistant_message(self) -> Optional[dict]:
        """Get the last assistant message with reasoning_details for conversation continuity"""
        return self._last_assistant_msg


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED UTILITY FUNCTIONS  (importable by web_server.py)
# ═══════════════════════════════════════════════════════════════════════════════

def screen_hash_from_b64(screenshot_b64: Optional[str]) -> str:
    """Compute perceptual hash from base64 screenshot (falls back to SHA1)."""
    if not screenshot_b64:
        return ""
    try:
        raw = base64.b64decode(screenshot_b64)
        if HAS_IMAGEHASH and HAS_PIL:
            import io as _io
            img = Image.open(_io.BytesIO(raw))
            return str(imagehash.phash(img, hash_size=16))
        return hashlib.sha1(raw).hexdigest()
    except Exception:
        return ""


def screens_are_same(hash1: str, hash2: str, threshold: int = 12) -> bool:
    """Compare two screen hashes. Uses Hamming distance for perceptual hashes."""
    if not hash1 or not hash2:
        return False
    if hash1 == hash2:
        return True
    if len(hash1) == len(hash2) and len(hash1) != 40:
        try:
            hamming = bin(int(hash1, 16) ^ int(hash2, 16)).count('1')
            return hamming <= threshold
        except ValueError:
            pass
    return False


def is_progress_sensitive(action: str) -> bool:
    """Return True for actions that should produce visible screen changes."""
    return action in {
        "tap_by_text", "tap_by_desc", "tap_by_id", "tap_by_index", "tap_xy",
        "long_press_text", "long_press_desc", "long_press_xy", "swipe", "scroll",
        "press_key", "launch_app", "launch_app_name", "open_url", "open_settings",
    }


def build_reflection(action: str, params: dict, success: bool, message: str,
                     success_check: str, screen_changed: bool) -> str:
    """Build a post-action reflection string for the next LLM turn."""
    parts = [f"REFLECTION on last action: {action}({json.dumps(params, ensure_ascii=False)})"]
    parts.append(f"  Result: {'SUCCESS' if success else 'FAILED'} — {message[:150]}")
    if success_check:
        if success and screen_changed:
            parts.append(f"  Expected: {success_check[:100]} → Likely achieved (screen changed)")
        elif success and not screen_changed:
            parts.append(f"  Expected: {success_check[:100]} → UNCERTAIN (no visual change detected)")
        else:
            parts.append(f"  Expected: {success_check[:100]} → NOT achieved (action failed)")
    if not success:
        error_type = classify_error(success, message, action)
        if error_type:
            parts.append(f"  Error type: {error_type} — consider alternative approach")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT (Single-Agent Architecture - Plan+Execute+Verify in one call)
# ═══════════════════════════════════════════════════════════════════════════════

class PhoneBrainAgent:
    """
    Single-agent controller: one LLM call per iteration.
    The LLM thinks, plans, and decides the next action all in one response.
    It sees the screenshot + full UI hierarchy each turn.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.device = DeviceController(self.config)
        self.llm = LLMClient(self.config)
        self.memory = SessionMemory(self.config.MEMORY_DIR)
        self.knowledge = KnowledgeBase(self.config.KNOWLEDGE_DIR)
        self.tools = ToolExecutor(
            self.device,
            ask_user_fn=self._ask_user,
            remember_fn=self._remember,
            recall_fn=self._recall,
            web_search_fn=self._web_search,
        )
        self.executor = ThreadPoolExecutor(max_workers=2)

    @staticmethod
    def _ask_user(question: str) -> str:
        """Prompt the user for input when the agent needs clarification"""
        print(f"\n{'─'*40}")
        print(f"  AGENT ASKS: {question}")
        print(f"{'─'*40}")
        try:
            answer = input("[Your answer]> ").strip()
            return answer if answer else "(no answer provided)"
        except (EOFError, KeyboardInterrupt):
            return "(user declined to answer)"

    def _remember(self, key: str, value, scope: str = "task") -> tuple[bool, str]:
        scope = (scope or "task").lower().strip()
        if scope not in ("task", "session"):
            scope = "task"
        return self.memory.remember(key, value, scope)

    def _recall(self, key: str, default: str = "") -> tuple[bool, str]:
        return self.memory.recall(key, default)

    @staticmethod
    def _truncate(text: str, max_len: int = 280) -> str:
        text = re.sub(r"\s+", " ", str(text)).strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    @staticmethod
    def _safe_console_text(value) -> str:
        text = str(value)
        encoding = sys.stdout.encoding or "utf-8"
        try:
            return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        except Exception:
            return text

    @staticmethod
    def _screen_hash_from_b64(screenshot_b64: Optional[str]) -> str:
        """Compute perceptual hash from base64 screenshot (falls back to SHA1)."""
        if not screenshot_b64:
            return ""
        try:
            raw = base64.b64decode(screenshot_b64)
            if HAS_IMAGEHASH and HAS_PIL:
                img = Image.open(__import__('io').BytesIO(raw))
                return str(imagehash.phash(img, hash_size=16))
            return hashlib.sha1(raw).hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _screens_are_same(hash1: str, hash2: str, threshold: int = 12) -> bool:
        """Compare two screen hashes. Uses Hamming distance for perceptual hashes."""
        if not hash1 or not hash2:
            return False
        if hash1 == hash2:
            return True
        # If both are hex perceptual hashes (same length, not SHA1 length 40)
        if len(hash1) == len(hash2) and len(hash1) != 40:
            try:
                h1 = int(hash1, 16)
                h2 = int(hash2, 16)
                hamming = bin(h1 ^ h2).count('1')
                return hamming <= threshold
            except ValueError:
                pass
        return False

    @staticmethod
    def _is_progress_sensitive_action(action: str) -> bool:
        return action in {
            "tap_by_text", "tap_by_desc", "tap_by_id", "tap_by_index", "tap_xy",
            "long_press_text", "long_press_desc", "long_press_xy", "swipe", "scroll",
            "press_key", "launch_app", "launch_app_name", "open_url", "open_settings",
        }

    @staticmethod
    def _fallback_actions(action: str, params: dict) -> list[tuple[str, dict]]:
        fallbacks: list[tuple[str, dict]] = []
        if action == "tap_by_text" and params.get("text"):
            fallbacks.append(("tap_by_desc", {"desc": params.get("text")}))
        elif action == "tap_by_desc" and params.get("desc"):
            fallbacks.append(("tap_by_text", {"text": params.get("desc")}))
        elif action == "tap_by_id":
            rid = params.get("resource_id", params.get("id", ""))
            if rid and "/" in rid:
                fallbacks.append(("tap_by_text", {"text": rid.split("/")[-1].replace("_", " ")}))
        elif action == "type_text" and params.get("text"):
            fallbacks.append(("clear_and_type", {"text": params.get("text")}))
        return fallbacks

    def _web_search(self, query: str, max_results: int = 5) -> tuple[bool, str]:
        if DDGS is None:
            return False, "web_search unavailable: duckduckgo-search is not installed"

        safe_max = max(1, min(int(max_results), 8))
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=safe_max))
        except Exception as e:
            return False, f"web_search failed: {e}"

        if not results:
            return False, f"No web results for query: {query}"

        lines = []
        for i, item in enumerate(results, start=1):
            title = self._truncate(item.get("title", ""), 120)
            href = self._truncate(item.get("href", ""), 180)
            body = self._truncate(item.get("body", ""), 220)
            lines.append(f"[{i}] {title}\nURL: {href}\nSnippet: {body}")
        return True, "\n\n".join(lines)

    @staticmethod
    def _extract_json_objects(text: str) -> list[str]:
        """Extract balanced JSON object strings from free-form text."""
        objects: list[str] = []
        start = -1
        depth = 0
        in_string = False
        escaped = False

        for i, ch in enumerate(text):
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    objects.append(text[start:i + 1])
                    start = -1

        return objects

    @staticmethod
    def _extract_emails(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", str(text))

    @staticmethod
    def validate_done_action(
        task: str,
        params: dict,
        history: list[str],
        screen_info: str,
        memory: Optional[SessionMemory] = None,
    ) -> tuple[bool, str]:
        """Prevent premature/hallucinated done on critical workflows."""
        task_l = str(task).lower()
        reason_l = str(params.get("reason", "")).lower()
        hist_l = "\n".join(history).lower()
        screen_l = str(screen_info).lower()

        is_instagram = "instagram" in task_l
        needs_temp_email = any(k in task_l for k in ["temp", "temporary", "mohmal", "mamo", "mail", "email"])

        if is_instagram and needs_temp_email:
            missing: list[str] = []

            visited_temp_mail = any(k in (hist_l + "\n" + screen_l) for k in [
                "mohmal", "temp-mail", "10minutemail", "guerrillamail", "mail.tm", "webxio", "tempmail",
            ])
            if not visited_temp_mail:
                missing.append("temp-mail site not confirmed")

            visited_instagram = "instagram" in (hist_l + "\n" + screen_l)
            if not visited_instagram:
                missing.append("instagram screen not confirmed")

            emails = set(PhoneBrainAgent._extract_emails(hist_l + "\n" + screen_l))
            if memory is not None:
                try:
                    emails.update(PhoneBrainAgent._extract_emails(memory.task_memory_text()))
                    emails.update(PhoneBrainAgent._extract_emails(memory.session_facts_text(limit=100)))
                except Exception:
                    pass
            if not emails:
                missing.append("no email value captured")

            typed_email = bool(
                re.search(r"(type_text|clear_and_type).*@[a-z0-9.-]+\.[a-z]{2,}", hist_l)
                or any("typed:" in h.lower() and "@" in h for h in history)
            )
            if not typed_email:
                missing.append("email not typed into form")

            if missing:
                return False, "missing evidence: " + "; ".join(missing)

        strong_claims = ["account created", "verification", "provided", "password set", "completed successfully"]
        if any(c in reason_l for c in strong_claims):
            success_events = sum(1 for h in history[-20:] if "ok:" in h.lower() or "→ ok:" in h.lower() or "-> ok:" in h.lower())
            if success_events < 3:
                return False, "insufficient successful evidence for strong completion claim"

        return True, "ok"

    @staticmethod
    def _parse_llm_response(response: str) -> dict:
        """Extract a valid action JSON from model output (handles nested objects)."""
        candidates: list[str] = []

        # 1) Try fenced code blocks first.
        for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", response):
            candidates.extend(PhoneBrainAgent._extract_json_objects(block))

        # 2) Then scan whole response.
        candidates.extend(PhoneBrainAgent._extract_json_objects(response))

        # 3) Finally try full text as JSON object.
        stripped = response.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        seen = set()
        for raw in candidates:
            if raw in seen:
                continue
            seen.add(raw)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("action"):
                if "params" not in parsed or not isinstance(parsed.get("params"), dict):
                    parsed["params"] = {}
                if "thought" not in parsed:
                    parsed["thought"] = ""
                return parsed

        return {
            "thought": "Failed to parse response; retrying safely",
            "action": "wait",
            "params": {"ms": 1000},
        }

    def _memory_context_text(self) -> str:
        return (
            "WORKING MEMORY (current task):\n"
            f"{self.memory.task_memory_text()}\n\n"
            "SESSION FACTS (persistent from all previous tasks):\n"
            f"{self.memory.session_facts_text(limit=40)}\n\n"
            "SESSION TIMELINE (since session start):\n"
            f"{self.memory.session_timeline_text(limit=25)}\n\n"
            "RECENT TASK OUTCOMES:\n"
            f"{self.memory.session_history_text(limit=8)}"
        )

    def _record_auto_memory(self, action: str, params: dict, success: bool, message: str):
        if not success:
            return
        try:
            text_value = params.get("text", params.get("value"))
            if action == "type_text" and text_value:
                self.memory.remember("last_typed_text", text_value, "task")
            elif action == "set_clipboard" and text_value:
                self.memory.remember("clipboard_text", text_value, "task")
            elif action == "ask_user" and message.startswith("User answered:"):
                answer = message.split(":", 1)[1].strip()
                self.memory.remember("last_user_answer", answer, "task")
        except Exception:
            pass

    # ── Loop Detection ──────────────────────────────────────────────────────

    @staticmethod
    def _detect_action_loop(action_log: list[str], window: int = 4) -> bool:
        if len(action_log) < window:
            return False
        recent = action_log[-window:]
        if len(set(recent)) == 1:
            return True
        if len(action_log) >= 6:
            last6 = action_log[-6:]
            if (last6[0] == last6[2] == last6[4]) and (last6[1] == last6[3] == last6[5]):
                return True
        if len(action_log) >= 5:
            from collections import Counter as _C
            if _C(action_log[-5:]).most_common(1)[0][1] >= 3:
                return True
        return False

    def _detect_screen_loop(self, screen_hash_log: list, window: int = 3) -> bool:
        if len(screen_hash_log) < window:
            return False
        recent = screen_hash_log[-window:]
        first = recent[0]
        if first is None:
            return False
        return all(h is not None and self._screens_are_same(first, h) for h in recent[1:])

    def _detect_loop(self, action_log: list[str], screen_hash_log: list, window: int = 4) -> str:
        """Returns '' | 'action' | 'stuck'"""
        action_loop = self._detect_action_loop(action_log, window)
        screen_stuck = self._detect_screen_loop(screen_hash_log, 3)
        if action_loop and screen_stuck:
            return "stuck"
        if action_loop:
            return "action"
        if screen_stuck and len(action_log) >= 3:
            return "stuck"
        return ""

    @staticmethod
    def _build_loop_hint(action_log: list[str], loop_level: str = "") -> str:
        if not loop_level:
            if len(action_log) >= 3 and len(set(action_log[-3:])) <= 2:
                return ("\n*** WARNING: Recent actions look repetitive. "
                        "Call done if complete, or try a different approach. ***\n")
            return ""
        if loop_level == "action":
            return ("\n*** LOOP DETECTED: Repeating actions. Call done if complete, "
                    "or try a fundamentally different strategy. ***\n")
        return ("\n*** STUCK: Screen unchanged despite actions. Call done, press back, "
                "scroll, or change approach entirely. ***\n")

    @staticmethod
    def _build_reflection(
        action: str, params: dict, success: bool, message: str,
        success_check: str, screen_changed: bool
    ) -> str:
        """Build a post-action reflection string for the next LLM turn."""
        parts = [f"REFLECTION on last action: {action}({json.dumps(params, ensure_ascii=False)})"]
        parts.append(f"  Result: {'SUCCESS' if success else 'FAILED'} — {message[:150]}")
        if success_check:
            if success and screen_changed:
                parts.append(f"  Expected: {success_check[:100]} → Likely achieved (screen changed)")
            elif success and not screen_changed:
                parts.append(f"  Expected: {success_check[:100]} → UNCERTAIN (no visual change detected)")
            else:
                parts.append(f"  Expected: {success_check[:100]} → NOT achieved (action failed)")
        if not success:
            error_type = classify_error(success, message, action)
            if error_type:
                parts.append(f"  Error type: {error_type} — consider alternative approach")
        return "\n".join(parts)

    async def run(self, task: str) -> tuple[bool, str]:
        """Execute a task using single-agent loop with task planning"""
        print(f"\n{'═'*60}")
        print(f"  TASK: {task}")
        print(f"{'═'*60}\n")

        self.memory.start_task()
        self.memory.remember("current_task", task, "task")

        # ── Task Planning: decompose into sub-goals ──
        print("[*] Planning task sub-goals...")
        task_plan = await TaskPlanner.plan(
            self.llm, task, self.memory.session_facts_text(limit=20)
        )
        plan_step = 0
        print(f"[*] Plan ({len(task_plan)} steps): {task_plan}")
        self.memory.remember("task_plan", json.dumps(task_plan, ensure_ascii=False), "task")

        # ── Retrieve similar past traces (demonstration learning) ──
        demo_text = self.knowledge.format_demonstrations(task)
        if demo_text:
            print(f"[*] Found similar past traces for guidance")

        history = []
        action_log: list[str] = []
        screen_hash_log: list = []
        loop_strike = 0
        iteration = 0
        consecutive_failures = 0
        last_reflection = ""
        loop = asyncio.get_event_loop()

        try:
            while iteration < self.config.MAX_ITERATIONS:
                iteration += 1

                # ── Gather screen state (screenshot + UI hierarchy in parallel) ──
                print(f"\n[Step {iteration}] Scanning screen...")

                screenshot, screen_info = await asyncio.gather(
                    loop.run_in_executor(self.executor, self.device.screenshot),
                    loop.run_in_executor(self.executor, self.device.get_screen_context),
                )

                if not screenshot:
                    print("[!] Screenshot failed, retrying...")
                    await asyncio.sleep(1)
                    continue

                # ── Auto-handle interruptions (permissions, crashes, consents) ──
                handled, handle_msg = InterruptionHandler.detect_and_handle(self.device)
                if handled:
                    print(f"[Step {iteration}] {handle_msg}")
                    history.append(f"[{iteration}] auto → {handle_msg}")
                    continue  # Re-capture screen after handling

                # ── Track screen hash for loop detection ──
                screen_hash_log.append(self._screen_hash_from_b64(screenshot))
                loop_level = self._detect_loop(action_log, screen_hash_log, window=4)
                loop_hint = self._build_loop_hint(action_log, loop_level)

                if loop_level:
                    loop_strike += 1
                    print(f"[Step {iteration}] Loop detected: level={loop_level}, strike={loop_strike}")
                else:
                    loop_strike = max(0, loop_strike - 1)

                if loop_strike >= 3:
                    final_msg = f"Agent stuck in loop ({loop_level}) after {iteration} steps"
                    print(f"[!] {final_msg}")
                    await self.llm.close()
                    self.memory.record_task(task, False, final_msg, history)
                    return False, final_msg

                if loop_strike == 2:
                    print("[*] Re-planning after loop...")
                    try:
                        task_plan = await TaskPlanner.plan(
                            self.llm,
                            f"{task} (re-plan: stuck after {iteration} steps)",
                            self.memory.session_facts_text(limit=20),
                        )
                        plan_step = 0
                        action_log.clear()
                    except Exception:
                        pass

                # ── Annotate screenshot with Set-of-Mark labels ──
                som_screenshot = await loop.run_in_executor(
                    self.executor, self.device.screenshot_with_som, screenshot
                )

                # ── Build messages for LLM ──
                history_text = ""
                if history:
                    history_text = "\n\nACTION HISTORY (recent):\n"
                    for h in history[-10:]:
                        history_text += f"  {h}\n"

                memory_text = self._memory_context_text()
                plan_text = TaskPlanner.format_plan_for_context(task_plan, plan_step)

                user_content = [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{som_screenshot or screenshot}"}},
                    {"type": "text", "text": f"""TASK: {task}

{plan_text}

{demo_text}

SCREEN UI HIERARCHY:
{screen_info}

MEMORY CONTEXT:
{memory_text}

{last_reflection}

{history_text}{loop_hint}
Step {iteration}/{self.config.MAX_ITERATIONS}. Analyze the screen and respond with your next action as JSON."""}
                ]

                messages: list[dict] = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                ]

                # If we have a previous assistant message with reasoning_details,
                # include it for conversation continuity (the model continues
                # reasoning from where it left off)
                last_msg = self.llm.get_last_assistant_message()
                if last_msg and self.config.REASONING_ENABLED:
                    # Add a synthetic prior user turn + assistant response to maintain context
                    messages.append({"role": "user", "content": "Proceed with the task."})
                    messages.append(last_msg)  # Contains reasoning_details

                messages.append({"role": "user", "content": user_content})

                # ── Get LLM decision ──
                print(f"[Step {iteration}] Thinking...")
                try:
                    response = await self.llm.chat(messages, max_tokens=1024)
                except Exception as e:
                    print(f"[!] LLM Error: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        final_msg = f"LLM failed {consecutive_failures} times: {e}"
                        self.memory.record_task(task, False, final_msg, history)
                        return False, final_msg
                    await asyncio.sleep(2)
                    continue

                # ── Parse response ──
                parsed = self._parse_llm_response(response)
                thought = parsed.get("thought", "")
                subgoal = parsed.get("subgoal", "")
                action = parsed.get("action", "")
                params = parsed.get("params", {})
                success_check = parsed.get("success_check", "")
                memory_write = parsed.get("memory_write", {})
                memory_read = parsed.get("memory_read", [])

                if isinstance(memory_read, list) and memory_read:
                    for key in memory_read[:6]:
                        if key:
                            ok, value = self.memory.recall(str(key), "")
                            if ok and value:
                                history.append(f"[mem-read] {key}={value}")

                if isinstance(memory_write, dict) and memory_write.get("key"):
                    self.memory.remember(
                        str(memory_write.get("key")),
                        memory_write.get("value", ""),
                        str(memory_write.get("scope", "task")),
                    )

                print(f"[Step {iteration}] Thought: {self._safe_console_text(thought[:120])}...")
                if subgoal:
                    print(f"[Step {iteration}] Subgoal: {self._safe_console_text(subgoal[:120])}")
                print(
                    f"[Step {iteration}] Action: {self._safe_console_text(action)} "
                    f"{self._safe_console_text(json.dumps(params, ensure_ascii=False))}"
                )
                if success_check:
                    print(f"[Step {iteration}] Success Check: {self._safe_console_text(success_check[:120])}")

                # ── Execute the tool ──
                pre_hash = self._screen_hash_from_b64(screenshot)
                if action == "done":
                    done_ok, done_msg = self.validate_done_action(task, params, history, screen_info, self.memory)
                    if not done_ok:
                        success, message, is_terminal = False, f"Premature done blocked: {done_msg}", False
                    else:
                        success, message, is_terminal = await loop.run_in_executor(
                            self.executor, self.tools.execute, action, params
                        )
                else:
                    success, message, is_terminal = await loop.run_in_executor(
                        self.executor, self.tools.execute, action, params
                    )

                result_str = f"{'OK' if success else 'FAIL'}: {message}"
                history.append(f"[{iteration}] {action}({json.dumps(params)}) → {result_str}")
                action_log.append(f"{action}:{json.dumps(params, sort_keys=True)}")
                print(f"[Step {iteration}] Result: {self._safe_console_text(result_str)}")
                self._record_auto_memory(action, params, success, message)

                # ── Advance plan step on successful progress ──
                if success and not is_terminal and subgoal and plan_step < len(task_plan):
                    plan_step += 1

                # ── Critic: verify visual progress for UI actions ──
                if success and (not is_terminal) and self._is_progress_sensitive_action(action):
                    await asyncio.sleep(0.12)
                    post_shot = await loop.run_in_executor(self.executor, self.device.screenshot)
                    post_hash = self._screen_hash_from_b64(post_shot)
                    if pre_hash and post_hash and self._screens_are_same(pre_hash, post_hash):
                        no_change_msg = "No visual change detected after action"
                        history.append(f"[{iteration}] critic → {no_change_msg}")
                        self.memory.remember("last_no_change_action", f"{action}:{json.dumps(params, ensure_ascii=False)}", "task")

                        recovered = False
                        for fb_action, fb_params in self._fallback_actions(action, params):
                            fb_success, fb_message, _ = await loop.run_in_executor(
                                self.executor, self.tools.execute, fb_action, fb_params
                            )
                            fb_result = f"{'OK' if fb_success else 'FAIL'}: {fb_message}"
                            history.append(f"[{iteration}] fallback {fb_action}({json.dumps(fb_params)}) → {fb_result}")
                            print(f"[Step {iteration}] Fallback: {fb_action} {fb_result}")

                            if not fb_success:
                                continue

                            await asyncio.sleep(0.12)
                            verify_shot = await loop.run_in_executor(self.executor, self.device.screenshot)
                            verify_hash = self._screen_hash_from_b64(verify_shot)
                            if verify_hash and not self._screens_are_same(verify_hash, pre_hash):
                                success = True
                                message = f"Recovered via {fb_action}: {fb_message}"
                                history.append(f"[{iteration}] critic → recovery succeeded")
                                recovered = True
                                break

                        if not recovered:
                            success = False
                            message = no_change_msg
                            history.append(f"[{iteration}] critic → marked as failure (no progress)")
                            print(f"[Step {iteration}] Critic: {no_change_msg}")

                final_result_str = f"{'OK' if success else 'FAIL'}: {message}"
                if final_result_str != result_str:
                    history.append(f"[{iteration}] final → {final_result_str}")

                # ── Build reflection for next turn ──
                screen_changed = True
                if self._is_progress_sensitive_action(action):
                    post_shot2 = await loop.run_in_executor(self.executor, self.device.screenshot)
                    post_hash2 = self._screen_hash_from_b64(post_shot2)
                    screen_changed = not self._screens_are_same(pre_hash, post_hash2) if pre_hash and post_hash2 else True
                last_reflection = self._build_reflection(action, params, success, message, success_check, screen_changed)

                if is_terminal:
                    await self.llm.close()
                    self.memory.record_task(task, success, message, history)
                    # Save successful trace for future demonstration learning
                    if success:
                        self.knowledge.save_trace(task, history, True, dict(self.memory.task_facts))
                    return success, message

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 5:
                        print("[!] Too many consecutive failures, stopping.")
                        await self.llm.close()
                        final_msg = "Too many consecutive failures"
                        self.memory.record_task(task, False, final_msg, history)
                        return False, final_msg

                # Brief delay before next iteration
                await asyncio.sleep(self.config.SCREENSHOT_DELAY)

            await self.llm.close()
            final_msg = f"Reached max iterations ({self.config.MAX_ITERATIONS})"
            self.memory.record_task(task, False, final_msg, history)
            return False, final_msg

        except KeyboardInterrupt:
            await self.llm.close()
            final_msg = "Interrupted by user"
            self.memory.record_task(task, False, final_msg, history)
            return False, final_msg
        except Exception as e:
            await self.llm.close()
            final_msg = f"Error: {e}"
            self.memory.record_task(task, False, final_msg, history)
            return False, final_msg


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Phone Brain v3 - Ultimate AI Android Control Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python phone_brain.py "Open YouTube and search for lofi music"
  python phone_brain.py "Send a WhatsApp message to Mom saying Hello"
  python phone_brain.py "Turn on WiFi and set brightness to 50%%"
  python phone_brain.py -r "Complex multi-step task"  (with reasoning/thinking)
  python phone_brain.py -m google/gemini-2.0-flash-001 "Open Settings"
  python phone_brain.py -i  (interactive mode)
        """
    )

    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--device", "-d", help="Device serial number")
    parser.add_argument("--max-steps", type=int, default=60, help="Max iterations (default: 60)")
    parser.add_argument("--model", "-m", help="LLM model override (default: google/gemini-3-flash-preview)")
    parser.add_argument("--reasoning", "-r", action="store_true", help="Enable extended thinking/reasoning")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    config = Config(
        DEVICE_SERIAL=args.device,
        MAX_ITERATIONS=args.max_steps,
        REASONING_ENABLED=args.reasoning,
    )
    if args.model:
        config.LLM_MODEL = args.model

    agent = PhoneBrainAgent(config)

    reasoning_str = "ON" if config.REASONING_ENABLED else "OFF"
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║  Phone Brain v3 - Ultimate AI Android Control Agent            ║
║  Model: {config.LLM_MODEL:<52}║
║  Reasoning: {reasoning_str:<48}║
║  Device: {f'{agent.device.width}x{agent.device.height}':<51}║
║                                                              ║
║  Features:                                                   ║
║   • Widget-based tapping (text/desc/id - no coord errors)   ║
║   • Full UI hierarchy scanning every turn                   ║
║   • Dynamic app discovery from installed packages            ║
║   • Memory tools (remember/recall) for multi-app tasks      ║
║   • web_search tool for missing app/package knowledge        ║
║   • Single-agent: observe + plan + execute + verify          ║
║   • Reasoning mode with conversation continuity             ║
║                                                              ║
║  Type 'quit' to exit                                        ║
╚══════════════════════════════════════════════════════════════╝"""

    if args.interactive or not args.task:
        print(banner)

        while True:
            try:
                task = input("\n[Phone Brain]> ").strip()
                if task.lower() in ("quit", "exit", "q"):
                    break
                if not task:
                    continue

                success, msg = asyncio.run(agent.run(task))
                status = "SUCCESS" if success else "FAILED"
                print(f"\n{'═'*40}")
                print(f"  [{status}] {msg}")
                print(f"{'═'*40}")

            except KeyboardInterrupt:
                print("\n[*] Exiting...")
                break
    else:
        success, msg = asyncio.run(agent.run(args.task))
        print(f"\n[{'SUCCESS' if success else 'FAILED'}] {msg}")
        return 0 if success else 1

    return 0


if __name__ == "__main__":
    exit(main())
