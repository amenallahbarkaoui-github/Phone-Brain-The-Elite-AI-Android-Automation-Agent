"""
Phone Brain - Complete Tool/Command System Reference
==================================================

Architecture:
  1. Agent receives task
  2. System calls `uiautomator dump` -> gets XML hierarchy of all on-screen widgets
  3. XML is parsed into a flat list of interactive elements with:
     - index, text, content-desc, resource-id, class, bounds, clickable, enabled
  4. Agent picks a TOOL by widget name/desc/id instead of guessing X,Y coordinates
  5. Tool resolves the widget -> extracts center of bounds -> executes adb input tap

This eliminates coordinate guessing entirely. The AI never needs to estimate pixels.
"""

# =============================================================================
# PACKAGE DICTIONARY - 80+ Common Android Apps
# =============================================================================

PACKAGE_MAP: dict[str, str] = {
    # --- Google Apps ---
    "youtube":          "com.google.android.youtube",
    "chrome":           "com.android.chrome",
    "gmail":            "com.google.android.gm",
    "google maps":      "com.google.android.apps.maps",
    "maps":             "com.google.android.apps.maps",
    "google photos":    "com.google.android.apps.photos",
    "photos":           "com.google.android.apps.photos",
    "google drive":     "com.google.android.apps.docs",
    "drive":            "com.google.android.apps.docs",
    "google play store":"com.android.vending",
    "play store":       "com.android.vending",
    "google calendar":  "com.google.android.calendar",
    "calendar":         "com.google.android.calendar",
    "google keep":      "com.google.android.keep",
    "keep":             "com.google.android.keep",
    "google meet":      "com.google.android.apps.tachyon",
    "meet":             "com.google.android.apps.tachyon",
    "google translate":  "com.google.android.apps.translate",
    "translate":        "com.google.android.apps.translate",
    "google lens":      "com.google.ar.lens",
    "google messages":  "com.google.android.apps.messaging",
    "messages":         "com.google.android.apps.messaging",
    "google phone":     "com.google.android.dialer",
    "phone":            "com.google.android.dialer",
    "google contacts":  "com.google.android.contacts",
    "contacts":         "com.google.android.contacts",
    "google clock":     "com.google.android.deskclock",
    "clock":            "com.google.android.deskclock",
    "google calculator": "com.google.android.calculator",
    "calculator":       "com.google.android.calculator",
    "google files":     "com.google.android.apps.nbu.files",
    "files":            "com.google.android.apps.nbu.files",
    "google news":      "com.google.android.apps.magazines",
    "google assistant":  "com.google.android.apps.googleassistant",
    "google home":      "com.google.android.apps.chromecast.app",
    "google sheets":    "com.google.android.apps.docs.editors.sheets",
    "google docs":      "com.google.android.apps.docs.editors.docs",
    "google slides":    "com.google.android.apps.docs.editors.slides",
    "youtube music":    "com.google.android.apps.youtube.music",

    # --- Social Media ---
    "whatsapp":         "com.whatsapp",
    "instagram":        "com.instagram.android",
    "facebook":         "com.facebook.katana",
    "messenger":        "com.facebook.orca",
    "twitter":          "com.twitter.android",
    "x":                "com.twitter.android",
    "tiktok":           "com.zhiliaoapp.musically",
    "snapchat":         "com.snapchat.android",
    "telegram":         "org.telegram.messenger",
    "reddit":           "com.reddit.frontpage",
    "discord":          "com.discord",
    "pinterest":        "com.pinterest",
    "linkedin":         "com.linkedin.android",
    "threads":          "com.instagram.barcelona",
    "signal":           "org.thoughtcrime.securesms",
    "viber":            "com.viber.voip",
    "wechat":           "com.tencent.mm",
    "line":             "jp.naver.line.android",
    "tumblr":           "com.tumblr",

    # --- Entertainment & Streaming ---
    "spotify":          "com.spotify.music",
    "netflix":          "com.netflix.mediaclient",
    "amazon prime video": "com.amazon.avod.thirdpartyclient",
    "prime video":      "com.amazon.avod.thirdpartyclient",
    "disney+":          "com.disney.disneyplus",
    "disney plus":      "com.disney.disneyplus",
    "hbo max":          "com.hbo.hbonow",
    "max":              "com.hbo.hbonow",
    "hulu":             "com.hulu.plus",
    "twitch":           "tv.twitch.android.app",
    "soundcloud":       "com.soundcloud.android",
    "shazam":           "com.shazam.android",
    "apple music":      "com.apple.android.music",
    "youtube tv":       "com.google.android.apps.youtube.unplugged",
    "crunchyroll":      "com.crunchyroll.crunchyroid",
    "vlc":              "org.videolan.vlc",

    # --- Productivity & Finance ---
    "notion":           "notion.id",
    "slack":            "com.Slack",
    "zoom":             "us.zoom.videomeetings",
    "microsoft teams":  "com.microsoft.teams",
    "teams":            "com.microsoft.teams",
    "microsoft outlook": "com.microsoft.office.outlook",
    "outlook":          "com.microsoft.office.outlook",
    "microsoft word":   "com.microsoft.office.word",
    "word":             "com.microsoft.office.word",
    "microsoft excel":  "com.microsoft.office.excel",
    "excel":            "com.microsoft.office.excel",
    "microsoft onenote": "com.microsoft.office.onenote",
    "onenote":          "com.microsoft.office.onenote",
    "evernote":         "com.evernote",
    "todoist":          "com.todoist",
    "trello":           "com.trello",
    "paypal":           "com.paypal.android.p2pmobile",
    "venmo":            "com.venmo",
    "cash app":         "com.squareup.cash",
    "robinhood":        "com.robinhood.android",
    "coinbase":         "com.coinbase.android",

    # --- Shopping & Food ---
    "amazon":           "com.amazon.mShop.android.shopping",
    "amazon shopping":  "com.amazon.mShop.android.shopping",
    "ebay":             "com.ebay.mobile",
    "aliexpress":       "com.alibaba.aliexpresshd",
    "uber":             "com.ubercab",
    "uber eats":        "com.ubercab.eats",
    "lyft":             "me.lyft.android",
    "doordash":         "com.dd.doordash",
    "grubhub":          "com.grubhub.android",
    "instacart":        "com.instacart.client",
    "walmart":          "com.walmart.android",
    "target":           "com.target.ui",
    "starbucks":        "com.starbucks.mobilecard",

    # --- Utilities ---
    "settings":         "com.android.settings",
    "camera":           "com.android.camera",
    "gallery":          "com.android.gallery3d",
    "file manager":     "com.android.documentsui",
    "notes":            "com.android.notes",

    # --- Travel & Transport ---
    "airbnb":           "com.airbnb.android",
    "booking":          "com.booking",
    "google earth":     "com.google.earth",
    "flightradar24":    "com.flightradar24free",
    "tripadvisor":      "com.tripadvisor.tripadvisor",

    # --- Health & Fitness ---
    "fitbit":           "com.fitbit.FitbitMobile",
    "myfitnesspal":     "com.myfitnesspal.android",
    "strava":           "com.strava",
    "samsung health":   "com.sec.android.app.shealth",
    "google fit":       "com.google.android.apps.fitness",

    # --- News & Reading ---
    "kindle":           "com.amazon.kindle",
    "pocket":           "com.ideashower.readitlater.pro",
    "flipboard":        "flipboard.app",
    "bbc news":         "bbc.mobile.news.ww",
    "cnn":              "com.cnn.mobile.android.phone",

    # --- Games (popular) ---
    "candy crush":      "com.king.candycrushsaga",
    "clash of clans":   "com.supercell.clashofclans",
    "pubg mobile":      "com.tencent.ig",
    "genshin impact":   "com.miHoYo.GenshinImpact",
    "roblox":           "com.roblox.client",
    "among us":         "com.innersloth.spacemafia",
    "minecraft":        "com.mojang.minecraftpe",
    "subway surfers":   "com.kiloo.subwaysurf",
}


# =============================================================================
# SETTINGS INTENTS - Android Settings Pages
# =============================================================================

SETTINGS_INTENTS: dict[str, str] = {
    "wifi":             "android.settings.WIFI_SETTINGS",
    "bluetooth":        "android.settings.BLUETOOTH_SETTINGS",
    "display":          "android.settings.DISPLAY_SETTINGS",
    "sound":            "android.settings.SOUND_SETTINGS",
    "battery":          "android.intent.action.POWER_USAGE_SUMMARY",
    "storage":          "android.settings.INTERNAL_STORAGE_SETTINGS",
    "apps":             "android.settings.APPLICATION_SETTINGS",
    "location":         "android.settings.LOCATION_SOURCE_SETTINGS",
    "security":         "android.settings.SECURITY_SETTINGS",
    "accounts":         "android.settings.SYNC_SETTINGS",
    "accessibility":    "android.settings.ACCESSIBILITY_SETTINGS",
    "language":         "android.settings.LOCALE_SETTINGS",
    "date":             "android.settings.DATE_SETTINGS",
    "developer":        "android.settings.APPLICATION_DEVELOPMENT_SETTINGS",
    "notifications":    "android.settings.NOTIFICATION_SETTINGS",
    "network":          "android.settings.WIRELESS_SETTINGS",
    "airplane":         "android.settings.AIRPLANE_MODE_SETTINGS",
    "nfc":              "android.settings.NFC_SETTINGS",
    "vpn":              "android.settings.VPN_SETTINGS",
    "tethering":        "android.settings.TETHERING_SETTINGS",
    "about":            "android.settings.DEVICE_INFO_SETTINGS",
    "default_apps":     "android.settings.MANAGE_DEFAULT_APPS_SETTINGS",
    "input_method":     "android.settings.INPUT_METHOD_SETTINGS",
    "biometric":        "android.settings.BIOMETRIC_ENROLL",
}


# =============================================================================
# KEY CODES - Android KeyEvent Constants
# =============================================================================

KEYCODES: dict[str, int] = {
    # Navigation
    "HOME":         3,
    "BACK":         4,
    "DPAD_UP":      19,
    "DPAD_DOWN":    20,
    "DPAD_LEFT":    21,
    "DPAD_RIGHT":   22,
    "DPAD_CENTER":  23,
    "ENTER":        66,
    "TAB":          61,
    "ESCAPE":       111,
    "RECENT":       187,
    "APP_SWITCH":   187,

    # System
    "POWER":        26,
    "SLEEP":        223,
    "WAKEUP":       224,
    "VOLUME_UP":    24,
    "VOLUME_DOWN":  25,
    "VOLUME_MUTE":  164,
    "CAMERA":       27,
    "SEARCH":       84,
    "MENU":         82,
    "NOTIFICATION": 83,

    # Media
    "MEDIA_PLAY":         126,
    "MEDIA_PAUSE":        127,
    "MEDIA_PLAY_PAUSE":   85,
    "MEDIA_STOP":         86,
    "MEDIA_NEXT":         87,
    "MEDIA_PREVIOUS":     88,

    # Editing
    "DELETE":       67,
    "FORWARD_DEL":  112,
    "CUT":          277,
    "COPY":         278,
    "PASTE":        279,
    "SELECT_ALL":   29,  # with META_CTRL
    "MOVE_HOME":    122,
    "MOVE_END":     123,
}


# =============================================================================
# TOOL DEFINITIONS - Complete Reference
# =============================================================================
#
# Each tool is defined as a dict with:
#   name          - Tool name (what the AI calls)
#   parameters    - Dict of param_name -> (type, required, description)
#   internal      - What ADB commands it runs internally
#   description   - What the tool does
#   example       - Example usage by the AI agent
#
# The UI dump flow (used by most tap_by_* tools):
#   1. adb shell uiautomator dump /sdcard/ui_dump.xml
#   2. adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml
#   3. Parse XML -> extract all <node> elements
#   4. Build widget list: [{index, text, content_desc, resource_id, class, bounds,
#                           clickable, enabled, scrollable, focusable, selected}]
#   5. Match the requested widget
#   6. Parse bounds "[x1,y1][x2,y2]" -> center = ((x1+x2)//2, (y1+y2)//2)
#   7. adb shell input tap <center_x> <center_y>
# =============================================================================

TOOLS = [

    # =========================================================================
    # CATEGORY 1: WIDGET-BASED TAPPING (The Core Innovation)
    # =========================================================================

    {
        "name": "tap_by_text",
        "parameters": {
            "text":  ("str", True,  "Visible text on the widget (exact or substring match)"),
            "index": ("int", False, "Which match to tap if multiple found (0-based, default 0)"),
        },
        "description": (
            "Find an on-screen widget whose 'text' attribute matches the given string, "
            "then tap the center of its bounds. Uses substring matching (case-insensitive). "
            "If multiple widgets match, taps the first one unless index is specified."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @text contains '{text}' (case-insensitive)",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input tap {cx} {cy}",
        ],
        "example": 'tap_by_text(text="Search")',
        "example_scenario": "Tap the 'Search' button visible on YouTube's home screen",
    },

    {
        "name": "tap_by_description",
        "parameters": {
            "desc":  ("str", True,  "Content description (accessibility label) of the widget"),
            "index": ("int", False, "Which match to tap if multiple found (0-based, default 0)"),
        },
        "description": (
            "Find a widget by its content-desc attribute (accessibility label) and tap its center. "
            "Many icons and image buttons have content-desc but no visible text. "
            "Uses substring matching (case-insensitive)."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @content-desc contains '{desc}' (case-insensitive)",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input tap {cx} {cy}",
        ],
        "example": 'tap_by_description(desc="Navigate up")',
        "example_scenario": "Tap the back arrow in an app toolbar (icon with no text, only content-desc)",
    },

    {
        "name": "tap_by_resource_id",
        "parameters": {
            "resource_id": ("str", True,  "Full or partial resource-id (e.g. 'com.google.android.youtube:id/search_edit_text')"),
            "index":       ("int", False, "Which match to tap if multiple found (0-based, default 0)"),
        },
        "description": (
            "Find a widget by its resource-id attribute and tap its center. "
            "Resource IDs are unique identifiers assigned by developers and are the most reliable "
            "way to target a specific widget. Supports partial matching."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @resource-id contains '{resource_id}'",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input tap {cx} {cy}",
        ],
        "example": 'tap_by_resource_id(resource_id="com.whatsapp:id/fab")',
        "example_scenario": "Tap WhatsApp's floating action button to start a new chat",
    },

    {
        "name": "tap_by_index",
        "parameters": {
            "index": ("int", True, "0-based index into the list of interactive widgets on screen"),
        },
        "description": (
            "Dump the UI, build a list of all interactive (clickable/focusable) widgets, "
            "and tap the Nth one. Useful when the AI sees a numbered widget list and wants "
            "to pick one by position."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: collect all nodes where @clickable='true' or @focusable='true'",
            "Sort by vertical position (top to bottom), then horizontal (left to right)",
            "Select widget at position {index}",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input tap {cx} {cy}",
        ],
        "example": "tap_by_index(index=3)",
        "example_scenario": "Tap the 4th interactive element in the widget list",
    },

    {
        "name": "tap_by_class",
        "parameters": {
            "class_name": ("str", True,  "Android widget class (e.g. 'android.widget.ImageButton')"),
            "index":      ("int", False, "Which match to tap if multiple found (0-based, default 0)"),
        },
        "description": (
            "Find a widget by its class name and tap it. Useful as a fallback when widgets "
            "have no text, no content-desc, and no resource-id."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @class == '{class_name}'",
            "Select match at {index}",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input tap {cx} {cy}",
        ],
        "example": 'tap_by_class(class_name="android.widget.ImageButton", index=0)',
        "example_scenario": "Tap the first ImageButton on screen when it has no other identifiers",
    },

    # =========================================================================
    # CATEGORY 2: COORDINATE-BASED INPUT (Fallback)
    # =========================================================================

    {
        "name": "tap_xy",
        "parameters": {
            "x": ("int", True, "X coordinate"),
            "y": ("int", True, "Y coordinate"),
        },
        "description": (
            "Fallback: tap at raw pixel coordinates. Use ONLY when widget-based tools fail "
            "(e.g. canvas apps, games, custom views not in UI hierarchy)."
        ),
        "internal": [
            "adb shell input tap {x} {y}",
        ],
        "example": "tap_xy(x=540, y=1200)",
        "example_scenario": "Tap a canvas element in a drawing app that has no UI nodes",
    },

    {
        "name": "long_press_by_text",
        "parameters": {
            "text":     ("str", True,  "Visible text on the widget"),
            "duration": ("int", False, "Hold duration in milliseconds (default 1000)"),
        },
        "description": (
            "Find widget by text and long-press its center. Implemented as a zero-distance "
            "swipe with the given duration."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @text contains '{text}'",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input swipe {cx} {cy} {cx} {cy} {duration}",
        ],
        "example": 'long_press_by_text(text="photo_001.jpg", duration=1500)',
        "example_scenario": "Long press a file to select it in a file manager",
    },

    {
        "name": "long_press_by_description",
        "parameters": {
            "desc":     ("str", True,  "Content description of the widget"),
            "duration": ("int", False, "Hold duration in milliseconds (default 1000)"),
        },
        "description": "Find widget by content-desc and long-press its center.",
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML: find node where @content-desc contains '{desc}'",
            "Extract bounds -> compute center (cx, cy)",
            "adb shell input swipe {cx} {cy} {cx} {cy} {duration}",
        ],
        "example": 'long_press_by_description(desc="Chat with Alice")',
        "example_scenario": "Long press a chat to archive or pin it",
    },

    {
        "name": "long_press_xy",
        "parameters": {
            "x":        ("int", True,  "X coordinate"),
            "y":        ("int", True,  "Y coordinate"),
            "duration": ("int", False, "Hold duration in ms (default 1000)"),
        },
        "description": "Fallback long press at raw coordinates.",
        "internal": [
            "adb shell input swipe {x} {y} {x} {y} {duration}",
        ],
        "example": "long_press_xy(x=540, y=1200, duration=2000)",
        "example_scenario": "Long press on a map location",
    },

    {
        "name": "double_tap_by_text",
        "parameters": {
            "text": ("str", True, "Visible text on the widget"),
        },
        "description": "Find widget by text and double-tap its center with a 100ms gap.",
        "internal": [
            "Resolve widget center (cx, cy) via UI dump",
            "adb shell input tap {cx} {cy} && sleep 0.1 && adb shell input tap {cx} {cy}",
        ],
        "example": 'double_tap_by_text(text="image_preview")',
        "example_scenario": "Double-tap to zoom into an image in a gallery",
    },

    # =========================================================================
    # CATEGORY 3: TEXT INPUT
    # =========================================================================

    {
        "name": "type_text",
        "parameters": {
            "text": ("str", True, "Text to type into the currently focused input field"),
        },
        "description": (
            "Type text into the currently focused text field. Handles special character "
            "escaping for ADB shell. For complex text (unicode, emoji), falls back to "
            "clipboard-based input via am broadcast."
        ),
        "internal": [
            "# Simple ASCII text:",
            "adb shell input text '{escaped_text}'",
            "",
            "# Complex/unicode text (fallback):",
            "adb shell am broadcast -a clipper.set -e text '{text}'",
            "adb shell input keyevent 279  # PASTE",
        ],
        "example": 'type_text(text="Hello, how are you?")',
        "example_scenario": "Type a message in the WhatsApp text input field",
    },

    {
        "name": "clear_field",
        "parameters": {},
        "description": (
            "Clear the currently focused text field by selecting all text and deleting it."
        ),
        "internal": [
            "adb shell input keyevent 123  # MOVE_END",
            "adb shell input keycombination 113 123  # CTRL+SHIFT+HOME (select all)",
            "# Alternative: adb shell input keyevent --longpress 67  # hold DELETE",
            "adb shell input keyevent 67  # DELETE",
        ],
        "example": "clear_field()",
        "example_scenario": "Clear the search box before typing a new query",
    },

    {
        "name": "type_in_field",
        "parameters": {
            "resource_id": ("str", True,  "Resource ID of the target text field"),
            "text":        ("str", True,  "Text to type"),
            "clear_first": ("bool", False, "Whether to clear existing text first (default True)"),
        },
        "description": (
            "Composite tool: tap on a specific text field (by resource-id), optionally clear it, "
            "then type the given text. Combines tap_by_resource_id + clear_field + type_text."
        ),
        "internal": [
            "# Step 1: Tap the field to focus it",
            "-> tap_by_resource_id(resource_id)",
            "# Step 2: Clear if needed",
            "-> clear_field() if clear_first",
            "# Step 3: Type",
            "-> type_text(text)",
        ],
        "example": 'type_in_field(resource_id="com.google.android.youtube:id/search_edit_text", text="lofi hip hop")',
        "example_scenario": "Clear the YouTube search bar and type a new query",
    },

    # =========================================================================
    # CATEGORY 4: NAVIGATION & GESTURES
    # =========================================================================

    {
        "name": "press_key",
        "parameters": {
            "key_name": ("str", True, "Key name: BACK, HOME, ENTER, RECENT, POWER, VOLUME_UP, VOLUME_DOWN, DELETE, TAB, ESCAPE, SEARCH, MENU, etc."),
        },
        "description": "Send a named key event to the device.",
        "internal": [
            "Resolve key_name to keycode via KEYCODES dict",
            "adb shell input keyevent {keycode}",
        ],
        "example": 'press_key(key_name="BACK")',
        "example_scenario": "Go back to the previous screen",
    },

    {
        "name": "input_keyevent",
        "parameters": {
            "code": ("int", True, "Raw Android KeyEvent code"),
        },
        "description": "Send a raw keyevent code. Use when press_key doesn't cover the needed key.",
        "internal": [
            "adb shell input keyevent {code}",
        ],
        "example": "input_keyevent(code=85)",
        "example_scenario": "Send MEDIA_PLAY_PAUSE (keycode 85)",
    },

    {
        "name": "scroll",
        "parameters": {
            "direction": ("str", True,  "UP, DOWN, LEFT, or RIGHT"),
            "amount":    ("int", False, "Number of scroll steps (default 1, each ~1/3 screen)"),
        },
        "description": (
            "Scroll the screen in the given direction. Each step scrolls roughly 1/3 of "
            "the screen height/width. Implemented as a swipe gesture."
        ),
        "internal": [
            "# For SCROLL DOWN (content moves up, revealing lower content):",
            "center_x = screen_width // 2",
            "start_y  = screen_height * 2 // 3",
            "end_y    = screen_height * 1 // 3",
            "adb shell input swipe {center_x} {start_y} {center_x} {end_y} 300",
            "",
            "# Repeated {amount} times with 200ms gaps",
        ],
        "example": 'scroll(direction="DOWN", amount=3)',
        "example_scenario": "Scroll down 3 times to see more search results",
    },

    {
        "name": "scroll_to_text",
        "parameters": {
            "text":      ("str", True,  "Text to find by scrolling"),
            "direction": ("str", False, "Scroll direction: DOWN (default) or UP"),
            "max_scrolls": ("int", False, "Maximum scroll attempts before giving up (default 10)"),
        },
        "description": (
            "Repeatedly scroll and dump UI until a widget with the given text appears on screen. "
            "Returns the widget info once found, or fails after max_scrolls."
        ),
        "internal": [
            "for i in range(max_scrolls):",
            "    dump UI hierarchy",
            "    if widget with text found: return widget",
            "    scroll(direction)",
            "raise 'Text not found after scrolling'",
        ],
        "example": 'scroll_to_text(text="Privacy", direction="DOWN")',
        "example_scenario": "Scroll down in Settings until 'Privacy' menu item is visible, then return its position",
    },

    {
        "name": "swipe",
        "parameters": {
            "x1":       ("int", True,  "Start X"),
            "y1":       ("int", True,  "Start Y"),
            "x2":       ("int", True,  "End X"),
            "y2":       ("int", True,  "End Y"),
            "duration": ("int", False, "Duration in ms (default 300)"),
        },
        "description": "Perform a precise swipe gesture between two coordinates.",
        "internal": [
            "adb shell input swipe {x1} {y1} {x2} {y2} {duration}",
        ],
        "example": "swipe(x1=800, y1=1200, x2=200, y2=1200, duration=200)",
        "example_scenario": "Swipe left on a notification to dismiss it",
    },

    {
        "name": "pinch",
        "parameters": {
            "direction": ("str", True,  "'in' to zoom out, 'out' to zoom in"),
            "x":         ("int", False, "Center X (default: screen center)"),
            "y":         ("int", False, "Center Y (default: screen center)"),
        },
        "description": (
            "Perform a pinch gesture to zoom in or out. Requires simultaneous two-finger "
            "input which is simulated using sendevent or the input gesture API on Android 10+."
        ),
        "internal": [
            "# Android 10+ with multi-touch gesture support:",
            "# Compute two finger paths converging (pinch in) or diverging (pinch out)",
            "adb shell input gesture <duration> <path1> <path2>",
            "",
            "# Fallback for older Android versions:",
            "# Use sendevent to simulate multi-touch (device-specific)",
        ],
        "example": 'pinch(direction="out", x=540, y=1200)',
        "example_scenario": "Pinch to zoom in on Google Maps",
    },

    # =========================================================================
    # CATEGORY 5: APP MANAGEMENT
    # =========================================================================

    {
        "name": "open_app",
        "parameters": {
            "package_name": ("str", True, "Full Android package name (e.g. 'com.google.android.youtube')"),
        },
        "description": "Launch an app by its package name using monkey command.",
        "internal": [
            "adb shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1",
        ],
        "example": 'open_app(package_name="com.google.android.youtube")',
        "example_scenario": "Launch YouTube",
    },

    {
        "name": "open_app_by_name",
        "parameters": {
            "name": ("str", True, "Common app name (e.g. 'youtube', 'whatsapp', 'chrome')"),
        },
        "description": (
            "Look up the package name from the PACKAGE_MAP dictionary and launch the app. "
            "Case-insensitive matching. If not found in the dictionary, attempts to search "
            "installed packages via pm list."
        ),
        "internal": [
            "package = PACKAGE_MAP.get(name.lower())",
            "if not package:",
            "    # Fuzzy search installed packages",
            "    adb shell pm list packages | grep -i {name}",
            "adb shell monkey -p {package} -c android.intent.category.LAUNCHER 1",
        ],
        "example": 'open_app_by_name(name="whatsapp")',
        "example_scenario": "Launch WhatsApp without needing to know the package name",
    },

    {
        "name": "open_activity",
        "parameters": {
            "package":  ("str", True, "Package name"),
            "activity": ("str", True, "Activity class name"),
        },
        "description": "Launch a specific activity within an app using am start.",
        "internal": [
            "adb shell am start -n {package}/{activity}",
        ],
        "example": 'open_activity(package="com.android.settings", activity=".wifi.WifiSettings")',
        "example_scenario": "Open the WiFi settings page directly",
    },

    {
        "name": "install_app",
        "parameters": {
            "apk_path": ("str", True, "Local path to the APK file on the host machine"),
        },
        "description": "Install an APK file onto the device.",
        "internal": [
            "adb install -r {apk_path}",
        ],
        "example": 'install_app(apk_path="/downloads/myapp.apk")',
        "example_scenario": "Install an APK from the local machine",
    },

    {
        "name": "uninstall_app",
        "parameters": {
            "package": ("str", True, "Package name to uninstall"),
        },
        "description": "Uninstall an app from the device.",
        "internal": [
            "adb uninstall {package}",
        ],
        "example": 'uninstall_app(package="com.example.unwanted")',
        "example_scenario": "Remove an unwanted app",
    },

    {
        "name": "force_stop_app",
        "parameters": {
            "package": ("str", True, "Package name to force stop"),
        },
        "description": "Force stop a running application.",
        "internal": [
            "adb shell am force-stop {package}",
        ],
        "example": 'force_stop_app(package="com.spotify.music")',
        "example_scenario": "Force stop Spotify when it's misbehaving",
    },

    {
        "name": "clear_app_data",
        "parameters": {
            "package": ("str", True, "Package name to clear data for"),
        },
        "description": "Clear all data for an app (cache, databases, shared preferences). Equivalent to 'Clear Data' in settings.",
        "internal": [
            "adb shell pm clear {package}",
        ],
        "example": 'clear_app_data(package="com.android.chrome")',
        "example_scenario": "Reset Chrome to factory state",
    },

    {
        "name": "get_current_app",
        "parameters": {},
        "description": "Get the currently focused app's package name and activity.",
        "internal": [
            "adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'",
            "# Parse output to extract package/activity",
        ],
        "example": "get_current_app()",
        "returns": '{"package": "com.google.android.youtube", "activity": ".HomeActivity"}',
        "example_scenario": "Check what app is currently in the foreground",
    },

    {
        "name": "list_running_apps",
        "parameters": {},
        "description": "List all currently running app processes.",
        "internal": [
            "adb shell ps -A | grep -v 'system\\|root'",
            "# Or: adb shell dumpsys activity recents",
        ],
        "example": "list_running_apps()",
        "example_scenario": "See what apps are currently running",
    },

    # =========================================================================
    # CATEGORY 6: SCREEN & UI INFORMATION
    # =========================================================================

    {
        "name": "get_screen_info",
        "parameters": {
            "interactive_only": ("bool", False, "If True, only return clickable/focusable widgets (default False)"),
        },
        "description": (
            "Dump the full UI hierarchy via uiautomator and return a structured list of all "
            "widgets. Each widget includes: index, text, content_desc, resource_id, class, "
            "bounds, clickable, enabled, scrollable, focusable, selected, checked. "
            "This is the primary tool for understanding what's on screen."
        ),
        "internal": [
            "adb shell uiautomator dump /sdcard/ui_dump.xml",
            "adb pull /sdcard/ui_dump.xml ./temp/ui_dump.xml",
            "Parse XML with xml.etree.ElementTree",
            "For each <node>: extract all attributes",
            "Return structured widget list",
        ],
        "example": "get_screen_info(interactive_only=True)",
        "returns": """[
    {"index": 0, "text": "YouTube", "content_desc": "", "resource_id": "", "class": "android.widget.TextView", "bounds": "[0,128][1080,220]", "clickable": true},
    {"index": 1, "text": "", "content_desc": "Search", "resource_id": "com.google.android.youtube:id/menu_item_1", "class": "android.widget.ImageView", "bounds": "[880,56][1016,192]", "clickable": true},
    ...
]""",
        "example_scenario": "Before any action, dump the screen to understand available widgets",
    },

    {
        "name": "take_screenshot",
        "parameters": {
            "save_path": ("str", False, "Local path to save the PNG (default: ./temp/screenshot_{timestamp}.png)"),
        },
        "description": "Capture the current screen as a PNG image. Returns the image as base64 and saves locally.",
        "internal": [
            "adb shell screencap -p > {save_path}",
            "# Or pipe: adb exec-out screencap -p > {save_path}",
            "# Return base64-encoded image for LLM vision",
        ],
        "example": "take_screenshot()",
        "example_scenario": "Capture what's currently on screen for the AI to analyze",
    },

    {
        "name": "get_screen_size",
        "parameters": {},
        "description": "Get the device screen dimensions in pixels.",
        "internal": [
            "adb shell wm size",
            "# Parse output: 'Physical size: 1080x2400'",
        ],
        "example": "get_screen_size()",
        "returns": '{"width": 1080, "height": 2400}',
        "example_scenario": "Get screen dimensions to calculate scroll distances",
    },

    {
        "name": "find_widget",
        "parameters": {
            "text":         ("str", False, "Match by text"),
            "content_desc": ("str", False, "Match by content-desc"),
            "resource_id":  ("str", False, "Match by resource-id"),
            "class_name":   ("str", False, "Match by class"),
        },
        "description": (
            "Search the UI hierarchy for widgets matching any combination of the given attributes. "
            "Returns all matching widgets with their full info. Does NOT tap -- just finds."
        ),
        "internal": [
            "Dump UI hierarchy",
            "Filter nodes by all provided attributes (AND logic)",
            "Return matching widgets",
        ],
        "example": 'find_widget(text="Send", class_name="android.widget.Button")',
        "returns": '[{"index": 12, "text": "Send", "resource_id": "com.whatsapp:id/send", ...}]',
        "example_scenario": "Find the Send button to verify it exists before tapping",
    },

    {
        "name": "wait_for_widget",
        "parameters": {
            "text":         ("str", False, "Text to wait for"),
            "content_desc": ("str", False, "Content-desc to wait for"),
            "resource_id":  ("str", False, "Resource-id to wait for"),
            "timeout":      ("int", False, "Max wait time in ms (default 10000)"),
            "poll_interval": ("int", False, "Polling interval in ms (default 500)"),
        },
        "description": (
            "Repeatedly dump UI until a widget with the specified attributes appears, or timeout. "
            "Essential for waiting for screens to load, dialogs to appear, etc."
        ),
        "internal": [
            "start = time.now()",
            "while elapsed < timeout:",
            "    dump UI hierarchy",
            "    if matching widget found: return widget",
            "    sleep(poll_interval)",
            "raise TimeoutError",
        ],
        "example": 'wait_for_widget(text="Sign in", timeout=15000)',
        "example_scenario": "Wait for a login page to fully load before interacting",
    },

    # =========================================================================
    # CATEGORY 7: CLIPBOARD
    # =========================================================================

    {
        "name": "get_clipboard",
        "parameters": {},
        "description": "Get the current clipboard contents from the device.",
        "internal": [
            "# Method 1: Using service call (Android 10+)",
            "adb shell service call clipboard 2 s16 com.android.shell",
            "# Parse the hex output to get the string",
            "",
            "# Method 2: Using clipper app (if installed)",
            "adb shell am broadcast -a clipper.get",
            "# Read from logcat output",
        ],
        "example": "get_clipboard()",
        "returns": '"https://copied-url.com"',
        "example_scenario": "Check what was copied to clipboard after a copy operation",
    },

    {
        "name": "set_clipboard",
        "parameters": {
            "text": ("str", True, "Text to place on the clipboard"),
        },
        "description": "Set the device clipboard to the given text.",
        "internal": [
            "# Method 1: Using am broadcast",
            "adb shell am broadcast -a clipper.set -e text '{text}'",
            "",
            "# Method 2: Using service call",
            "adb shell service call clipboard 1 s16 com.android.shell s16 '{text}'",
        ],
        "example": 'set_clipboard(text="Hello from Phone Brain")',
        "example_scenario": "Set clipboard text, then paste it into a field",
    },

    # =========================================================================
    # CATEGORY 8: SYSTEM SETTINGS & TOGGLES
    # =========================================================================

    {
        "name": "open_url",
        "parameters": {
            "url": ("str", True, "Full URL to open (including https://)"),
        },
        "description": "Open a URL in the default browser.",
        "internal": [
            "adb shell am start -a android.intent.action.VIEW -d '{url}'",
        ],
        "example": 'open_url(url="https://github.com/rundroid")',
        "example_scenario": "Open a webpage in Chrome",
    },

    {
        "name": "open_settings",
        "parameters": {
            "setting": ("str", True, "Setting name: wifi, bluetooth, display, sound, battery, storage, apps, location, security, accounts, accessibility, language, date, developer, notifications, network, airplane, nfc, vpn, tethering, about, default_apps, input_method, biometric"),
        },
        "description": "Open a specific Android settings page by name.",
        "internal": [
            "intent = SETTINGS_INTENTS[setting]",
            "adb shell am start -a {intent}",
        ],
        "example": 'open_settings(setting="wifi")',
        "example_scenario": "Open WiFi settings to connect to a network",
    },

    {
        "name": "toggle_wifi",
        "parameters": {
            "enabled": ("bool", True, "True to enable, False to disable"),
        },
        "description": "Enable or disable WiFi.",
        "internal": [
            "adb shell svc wifi enable   # if enabled=True",
            "adb shell svc wifi disable  # if enabled=False",
        ],
        "example": "toggle_wifi(enabled=True)",
        "example_scenario": "Turn WiFi on",
    },

    {
        "name": "toggle_bluetooth",
        "parameters": {
            "enabled": ("bool", True, "True to enable, False to disable"),
        },
        "description": "Enable or disable Bluetooth.",
        "internal": [
            "# Requires BLUETOOTH_ADMIN permission or root",
            "adb shell am start -a android.bluetooth.adapter.action.REQUEST_ENABLE  # enable",
            "# Or via settings command:",
            "adb shell settings put global bluetooth_on 1  # enable",
            "adb shell settings put global bluetooth_on 0  # disable",
            "adb shell svc bluetooth enable  # alternative (Android 12+)",
        ],
        "example": "toggle_bluetooth(enabled=False)",
        "example_scenario": "Turn Bluetooth off to save battery",
    },

    {
        "name": "toggle_airplane_mode",
        "parameters": {
            "enabled": ("bool", True, "True to enable, False to disable"),
        },
        "description": "Enable or disable airplane mode.",
        "internal": [
            "adb shell settings put global airplane_mode_on {1 if enabled else 0}",
            "adb shell am broadcast -a android.intent.action.AIRPLANE_MODE",
        ],
        "example": "toggle_airplane_mode(enabled=True)",
        "example_scenario": "Enable airplane mode before a flight",
    },

    {
        "name": "set_brightness",
        "parameters": {
            "level": ("int", True, "Brightness level (0-255)"),
            "auto":  ("bool", False, "Enable auto-brightness (default False)"),
        },
        "description": "Set screen brightness level.",
        "internal": [
            "# Disable auto brightness first (unless auto=True)",
            "adb shell settings put system screen_brightness_mode {1 if auto else 0}",
            "adb shell settings put system screen_brightness {level}",
        ],
        "example": "set_brightness(level=128)",
        "example_scenario": "Set brightness to 50%",
    },

    {
        "name": "set_volume",
        "parameters": {
            "stream":  ("str", True,  "Stream type: music, ring, notification, alarm, system"),
            "level":   ("int", True,  "Volume level (0-15 typical, varies by device)"),
        },
        "description": "Set volume for a specific audio stream.",
        "internal": [
            "# Stream type mapping:",
            "# music=3, ring=2, notification=5, alarm=4, system=1",
            "adb shell media volume --stream {stream_code} --set {level}",
        ],
        "example": 'set_volume(stream="music", level=10)',
        "example_scenario": "Set media volume to ~66%",
    },

    {
        "name": "toggle_mobile_data",
        "parameters": {
            "enabled": ("bool", True, "True to enable, False to disable"),
        },
        "description": "Enable or disable mobile data.",
        "internal": [
            "adb shell svc data enable   # if enabled=True",
            "adb shell svc data disable  # if enabled=False",
        ],
        "example": "toggle_mobile_data(enabled=False)",
        "example_scenario": "Disable mobile data to use WiFi only",
    },

    {
        "name": "set_screen_timeout",
        "parameters": {
            "ms": ("int", True, "Screen timeout in milliseconds (e.g. 30000, 60000, 120000, 300000, 600000)"),
        },
        "description": "Set the screen auto-lock timeout.",
        "internal": [
            "adb shell settings put system screen_off_timeout {ms}",
        ],
        "example": "set_screen_timeout(ms=300000)",
        "example_scenario": "Set screen timeout to 5 minutes",
    },

    {
        "name": "toggle_rotation",
        "parameters": {
            "auto": ("bool", True, "True for auto-rotate, False for portrait lock"),
        },
        "description": "Enable or disable auto-rotation.",
        "internal": [
            "adb shell settings put system accelerometer_rotation {1 if auto else 0}",
        ],
        "example": "toggle_rotation(auto=True)",
        "example_scenario": "Enable auto-rotation for video watching",
    },

    # =========================================================================
    # CATEGORY 9: NOTIFICATIONS
    # =========================================================================

    {
        "name": "get_notifications",
        "parameters": {},
        "description": "Get all current notifications from the notification shade.",
        "internal": [
            "adb shell dumpsys notification --noredact",
            "# Parse output to extract:",
            "#   - package, title, text, time, key",
            "# Filter to StatusBarNotification entries",
        ],
        "example": "get_notifications()",
        "returns": """[
    {"package": "com.whatsapp", "title": "Alice", "text": "Hey, are you free?", "time": "2m ago"},
    {"package": "com.google.android.gm", "title": "New email", "text": "Meeting at 3pm", "time": "15m ago"},
    ...
]""",
        "example_scenario": "Check if there's a new WhatsApp message notification",
    },

    {
        "name": "open_notification_shade",
        "parameters": {},
        "description": "Pull down the notification shade.",
        "internal": [
            "adb shell cmd statusbar expand-notifications",
        ],
        "example": "open_notification_shade()",
        "example_scenario": "Open the notification shade to see and interact with notifications",
    },

    {
        "name": "open_quick_settings",
        "parameters": {},
        "description": "Open the quick settings panel (full pull-down).",
        "internal": [
            "adb shell cmd statusbar expand-settings",
        ],
        "example": "open_quick_settings()",
        "example_scenario": "Open quick settings to toggle WiFi/Bluetooth/etc.",
    },

    {
        "name": "dismiss_notifications",
        "parameters": {},
        "description": "Dismiss all clearable notifications.",
        "internal": [
            "adb shell service call notification 1",
            "# Or: tap 'Clear all' button after opening shade",
        ],
        "example": "dismiss_notifications()",
        "example_scenario": "Clear all notifications",
    },

    # =========================================================================
    # CATEGORY 10: FILE & DEVICE OPERATIONS
    # =========================================================================

    {
        "name": "push_file",
        "parameters": {
            "local_path":  ("str", True, "Path on host machine"),
            "remote_path": ("str", True, "Path on Android device"),
        },
        "description": "Push a file from the host machine to the device.",
        "internal": [
            "adb push {local_path} {remote_path}",
        ],
        "example": 'push_file(local_path="./photo.jpg", remote_path="/sdcard/DCIM/photo.jpg")',
        "example_scenario": "Upload a photo to the device",
    },

    {
        "name": "pull_file",
        "parameters": {
            "remote_path": ("str", True, "Path on Android device"),
            "local_path":  ("str", True, "Path on host machine"),
        },
        "description": "Pull a file from the device to the host machine.",
        "internal": [
            "adb pull {remote_path} {local_path}",
        ],
        "example": 'pull_file(remote_path="/sdcard/DCIM/Camera/IMG_001.jpg", local_path="./photos/")',
        "example_scenario": "Download a photo from the device",
    },

    {
        "name": "shell",
        "parameters": {
            "command": ("str", True, "Raw shell command to execute on the device"),
        },
        "description": (
            "Execute an arbitrary ADB shell command. This is the escape hatch for anything "
            "not covered by other tools. Use with caution."
        ),
        "internal": [
            "adb shell {command}",
        ],
        "example": 'shell(command="pm list packages -3")',
        "example_scenario": "List all third-party installed packages",
    },

    {
        "name": "get_device_info",
        "parameters": {},
        "description": "Get comprehensive device information.",
        "internal": [
            "adb shell getprop ro.product.model        # Device model",
            "adb shell getprop ro.build.version.release # Android version",
            "adb shell getprop ro.build.version.sdk     # SDK level",
            "adb shell wm size                          # Screen size",
            "adb shell wm density                       # Screen density",
            "adb shell dumpsys battery                  # Battery info",
        ],
        "example": "get_device_info()",
        "returns": """{
    "model": "Pixel 7",
    "android_version": "14",
    "sdk": "34",
    "screen": "1080x2400",
    "density": 420,
    "battery": 85,
    "battery_status": "charging"
}""",
        "example_scenario": "Get device info to adapt behavior to screen size and Android version",
    },

    {
        "name": "get_battery_info",
        "parameters": {},
        "description": "Get battery level and charging status.",
        "internal": [
            "adb shell dumpsys battery",
            "# Parse: level, status, temperature, technology",
        ],
        "example": "get_battery_info()",
        "returns": '{"level": 85, "status": "charging", "temperature": 28.5}',
        "example_scenario": "Check battery before starting a long task",
    },

    # =========================================================================
    # CATEGORY 11: WAITING & TIMING
    # =========================================================================

    {
        "name": "wait",
        "parameters": {
            "ms": ("int", True, "Milliseconds to wait"),
        },
        "description": "Wait for the specified number of milliseconds. Use between actions to let UI settle.",
        "internal": [
            "time.sleep(ms / 1000)",
        ],
        "example": "wait(ms=2000)",
        "example_scenario": "Wait 2 seconds for an app to fully load after launching",
    },

    {
        "name": "wait_for_activity",
        "parameters": {
            "activity": ("str", True,  "Activity class name to wait for (partial match)"),
            "timeout":  ("int", False, "Max wait time in ms (default 10000)"),
        },
        "description": (
            "Wait until a specific activity is in the foreground. Useful for waiting for "
            "an app or screen to load."
        ),
        "internal": [
            "while elapsed < timeout:",
            "    current = adb shell dumpsys window | grep mCurrentFocus",
            "    if activity in current: return True",
            "    sleep(500)",
            "return False",
        ],
        "example": 'wait_for_activity(activity="SearchActivity", timeout=5000)',
        "example_scenario": "Wait for the search screen to load after tapping search",
    },

    # =========================================================================
    # CATEGORY 12: TEXT EXTRACTION & READING
    # =========================================================================

    {
        "name": "get_text_content",
        "parameters": {
            "resource_id": ("str", False, "Get text from a specific widget by resource-id"),
        },
        "description": (
            "Extract all visible text from the current screen, or text from a specific widget. "
            "Useful for reading messages, checking values, verifying state."
        ),
        "internal": [
            "Dump UI hierarchy",
            "If resource_id: find node, return its @text",
            "Else: collect all @text attributes from all nodes",
            "Return as structured text",
        ],
        "example": "get_text_content()",
        "example_scenario": "Read all visible text on screen to understand the current state",
    },

    {
        "name": "is_widget_visible",
        "parameters": {
            "text":         ("str", False, "Check by text"),
            "content_desc": ("str", False, "Check by content-desc"),
            "resource_id":  ("str", False, "Check by resource-id"),
        },
        "description": "Check if a specific widget is currently visible on screen. Returns bool.",
        "internal": [
            "Dump UI hierarchy",
            "Search for matching node",
            "Return True if found, False otherwise",
        ],
        "example": 'is_widget_visible(text="Send")',
        "returns": "true",
        "example_scenario": "Check if the Send button is visible before trying to tap it",
    },

    # =========================================================================
    # CATEGORY 13: COMPOSITE / HIGH-LEVEL ACTIONS
    # =========================================================================

    {
        "name": "open_app_and_wait",
        "parameters": {
            "name":    ("str", True,  "App name (looked up in PACKAGE_MAP)"),
            "timeout": ("int", False, "Max wait time in ms (default 10000)"),
        },
        "description": (
            "Launch an app by name and wait until it's fully loaded (activity in foreground "
            "and UI is interactive). Combines open_app_by_name + wait_for_activity."
        ),
        "internal": [
            "package = PACKAGE_MAP[name]",
            "adb shell monkey -p {package} -c android.intent.category.LAUNCHER 1",
            "Wait for activity to appear in foreground",
            "Wait for UI dump to show interactive widgets",
        ],
        "example": 'open_app_and_wait(name="youtube", timeout=8000)',
        "example_scenario": "Open YouTube and wait until it's fully loaded before interacting",
    },

    {
        "name": "search_in_app",
        "parameters": {
            "query":            ("str", True,  "Search query text"),
            "search_button":    ("str", False, "How to find the search button: text, desc, or resource_id value"),
            "search_field_id":  ("str", False, "Resource ID of the search input field"),
        },
        "description": (
            "Composite: tap the search icon/button, wait for search field, type query, press Enter. "
            "Attempts to auto-detect the search UI if specific IDs aren't provided."
        ),
        "internal": [
            "# Step 1: Find and tap search button",
            "Try: tap_by_description('Search') or tap_by_description('search')",
            "Or:  tap_by_resource_id(search_button) if provided",
            "",
            "# Step 2: Wait for search field",
            "wait(ms=500)",
            "wait_for_widget(class_name='android.widget.EditText')",
            "",
            "# Step 3: Type query",
            "type_text(query)",
            "",
            "# Step 4: Submit",
            "press_key('ENTER')",
        ],
        "example": 'search_in_app(query="lofi hip hop radio")',
        "example_scenario": "Search for a video on YouTube",
    },

    {
        "name": "share_to_app",
        "parameters": {
            "target_app": ("str", True, "Name of the app to share to"),
        },
        "description": (
            "After triggering a share action, select the target app from the share sheet. "
            "Looks for the app name in the share dialog."
        ),
        "internal": [
            "# Assumes share dialog is already open",
            "Dump UI, find share target by text or content-desc",
            "tap_by_text(target_app) or scroll_to_text(target_app) then tap",
        ],
        "example": 'share_to_app(target_app="WhatsApp")',
        "example_scenario": "Share a photo to WhatsApp from the gallery",
    },

    # =========================================================================
    # CATEGORY 14: TASK CONTROL (Agent Lifecycle)
    # =========================================================================

    {
        "name": "DONE",
        "parameters": {
            "summary": ("str", False, "Brief summary of what was accomplished"),
        },
        "description": (
            "Signal that the task has been completed successfully. The agent should call this "
            "when the requested task is fully done and verified."
        ),
        "internal": [
            "# No ADB command - this is an agent control signal",
            "# Ends the execution loop with success status",
        ],
        "example": 'DONE(summary="Opened YouTube and searched for lofi hip hop")',
        "example_scenario": "Task completed, signal to the orchestrator",
    },

    {
        "name": "FAIL",
        "parameters": {
            "reason": ("str", True, "Why the task could not be completed"),
        },
        "description": (
            "Signal that the task cannot be completed. The agent should call this when it "
            "determines the task is impossible, blocked, or has failed after retries."
        ),
        "internal": [
            "# No ADB command - this is an agent control signal",
            "# Ends the execution loop with failure status",
        ],
        "example": 'FAIL(reason="App not installed on device")',
        "example_scenario": "WhatsApp is not installed, cannot send a message",
    },

    {
        "name": "ASK_USER",
        "parameters": {
            "question": ("str", True, "Question to ask the user"),
        },
        "description": (
            "Pause execution and ask the user for clarification or input. Use when the task "
            "is ambiguous or requires information the agent doesn't have."
        ),
        "internal": [
            "# No ADB command - pauses execution and prompts user",
        ],
        "example": 'ASK_USER(question="There are 3 contacts named John. Which one: John Smith, John Doe, or John Lee?")',
        "example_scenario": "Multiple matches found, need user to disambiguate",
    },
]


# =============================================================================
# UI DUMP XML PARSER - Reference Implementation
# =============================================================================

UI_DUMP_PARSER = '''
import xml.etree.ElementTree as ET
import re

def parse_ui_dump(xml_path: str) -> list[dict]:
    """
    Parse uiautomator XML dump into a flat list of widgets.
    
    Each widget dict contains:
        index        (int)  - Position in the list
        text         (str)  - Visible text
        content_desc (str)  - Accessibility content description
        resource_id  (str)  - Developer-assigned resource ID
        class_name   (str)  - Android widget class
        package      (str)  - Package that owns this widget
        bounds       (str)  - Raw bounds string "[x1,y1][x2,y2]"
        center_x     (int)  - Center X coordinate
        center_y     (int)  - Center Y coordinate
        clickable    (bool) - Whether the widget is clickable
        enabled      (bool) - Whether the widget is enabled
        focusable    (bool) - Whether the widget is focusable
        scrollable   (bool) - Whether the widget is scrollable
        selected     (bool) - Whether the widget is selected
        checked      (bool) - Whether the widget is checked
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    widgets = []
    
    for idx, node in enumerate(root.iter("node")):
        bounds_str = node.get("bounds", "[0,0][0,0]")
        
        # Parse bounds "[x1,y1][x2,y2]"
        match = re.findall(r"\\[(\\d+),(\\d+)\\]", bounds_str)
        if len(match) == 2:
            x1, y1 = int(match[0][0]), int(match[0][1])
            x2, y2 = int(match[1][0]), int(match[1][1])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        else:
            cx, cy = 0, 0
        
        widget = {
            "index":        idx,
            "text":         node.get("text", ""),
            "content_desc": node.get("content-desc", ""),
            "resource_id":  node.get("resource-id", ""),
            "class_name":   node.get("class", ""),
            "package":      node.get("package", ""),
            "bounds":       bounds_str,
            "center_x":     cx,
            "center_y":     cy,
            "clickable":    node.get("clickable", "false") == "true",
            "enabled":      node.get("enabled", "false") == "true",
            "focusable":    node.get("focusable", "false") == "true",
            "scrollable":   node.get("scrollable", "false") == "true",
            "selected":     node.get("selected", "false") == "true",
            "checked":      node.get("checked", "false") == "true",
        }
        widgets.append(widget)
    
    return widgets


def find_by_text(widgets: list[dict], text: str, index: int = 0) -> dict | None:
    """Find widget by text (case-insensitive substring match)."""
    text_lower = text.lower()
    matches = [w for w in widgets if text_lower in w["text"].lower()]
    return matches[index] if index < len(matches) else None


def find_by_description(widgets: list[dict], desc: str, index: int = 0) -> dict | None:
    """Find widget by content-desc (case-insensitive substring match)."""
    desc_lower = desc.lower()
    matches = [w for w in widgets if desc_lower in w["content_desc"].lower()]
    return matches[index] if index < len(matches) else None


def find_by_resource_id(widgets: list[dict], rid: str, index: int = 0) -> dict | None:
    """Find widget by resource-id (substring match)."""
    matches = [w for w in widgets if rid in w["resource_id"]]
    return matches[index] if index < len(matches) else None


def find_interactive(widgets: list[dict]) -> list[dict]:
    """Get all interactive (clickable or focusable) widgets."""
    return [w for w in widgets if w["clickable"] or w["focusable"]]


def format_widget_list(widgets: list[dict], interactive_only: bool = False) -> str:
    """Format widget list as a readable string for the AI agent."""
    if interactive_only:
        widgets = find_interactive(widgets)
    
    lines = []
    for w in widgets:
        parts = []
        if w["text"]:
            parts.append(f"text=\\"{w['text']}\\"")
        if w["content_desc"]:
            parts.append(f"desc=\\"{w['content_desc']}\\"")
        if w["resource_id"]:
            # Shorten resource ID for readability
            short_id = w["resource_id"].split("/")[-1] if "/" in w["resource_id"] else w["resource_id"]
            parts.append(f"id=\\"{short_id}\\"")
        parts.append(f"class={w['class_name'].split('.')[-1]}")
        parts.append(f"center=({w['center_x']},{w['center_y']})")
        
        flags = []
        if w["clickable"]: flags.append("clickable")
        if w["scrollable"]: flags.append("scrollable")
        if w["checked"]: flags.append("checked")
        if w["selected"]: flags.append("selected")
        if flags:
            parts.append(f"[{','.join(flags)}]")
        
        lines.append(f"  [{w['index']:3d}] {' | '.join(parts)}")
    
    return f"Widgets ({len(lines)}):\\n" + "\\n".join(lines)
'''


# =============================================================================
# AGENT PROMPT TEMPLATE - How the AI uses these tools
# =============================================================================

AGENT_SYSTEM_PROMPT = '''
You are Phone Brain, an AI agent that controls an Android phone.

## How You See the Screen
Before each action, you receive:
1. A screenshot (image) of the current screen
2. A parsed UI widget list from `uiautomator dump` showing all interactive elements

## Available Tools
You MUST respond with exactly ONE tool call per turn.

### Widget-Based Tapping (PREFERRED - use these first):
- tap_by_text(text, index?) - Tap widget by visible text
- tap_by_description(desc, index?) - Tap by content-description (icons, images)
- tap_by_resource_id(resource_id, index?) - Tap by developer resource ID (most reliable)
- tap_by_index(index) - Tap Nth interactive widget
- tap_by_class(class_name, index?) - Tap by widget class

### Long Press:
- long_press_by_text(text, duration?)
- long_press_by_description(desc, duration?)
- long_press_xy(x, y, duration?)
- double_tap_by_text(text)

### Text Input:
- type_text(text) - Type into focused field
- clear_field() - Clear focused field
- type_in_field(resource_id, text, clear_first?) - Tap field + type

### Navigation:
- press_key(key_name) - BACK, HOME, ENTER, RECENT, etc.
- scroll(direction, amount?) - UP/DOWN/LEFT/RIGHT
- scroll_to_text(text, direction?, max_scrolls?) - Scroll until text found
- swipe(x1, y1, x2, y2, duration?)

### App Management:
- open_app(package_name) - Launch by package
- open_app_by_name(name) - Launch by friendly name
- open_app_and_wait(name, timeout?)
- force_stop_app(package)
- clear_app_data(package)

### Information:
- get_screen_info(interactive_only?) - Dump all widgets
- take_screenshot() - Capture screen
- get_current_app() - What app is in foreground
- get_notifications() - Read notifications
- find_widget(text?, content_desc?, resource_id?) - Search without tapping
- wait_for_widget(text?, resource_id?, timeout?) - Wait for element to appear
- is_widget_visible(text?, resource_id?) - Check existence
- get_text_content(resource_id?) - Read text

### System:
- open_url(url) - Open in browser
- open_settings(setting) - Open settings page
- toggle_wifi(enabled) / toggle_bluetooth(enabled)
- set_brightness(level) / set_volume(stream, level)
- shell(command) - Raw ADB shell

### Clipboard:
- get_clipboard() / set_clipboard(text)

### Flow Control:
- wait(ms) - Wait for UI to settle
- DONE(summary?) - Task complete
- FAIL(reason) - Task impossible
- ASK_USER(question) - Need clarification

### Fallback (use only when widget-based tools fail):
- tap_xy(x, y) - Raw coordinate tap

## Rules
1. ALWAYS prefer widget-based tapping over coordinate tapping
2. Start each turn by reading the widget list to understand the screen
3. Use resource_id when available (most reliable), then text, then content-desc
4. After launching an app, wait for it to load before interacting
5. If a tap doesn't work, try scrolling to find the widget
6. Call DONE when the task is verifiably complete
7. Call FAIL if the task is impossible after reasonable attempts
'''


# =============================================================================
# TOOL COUNT SUMMARY
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  Phone Brain Tool System Reference")
    print("=" * 70)
    print()
    
    categories = {}
    for tool in TOOLS:
        # Infer category from position in list
        name = tool["name"]
        param_count = len(tool["parameters"])
        required = sum(1 for _, (_, req, _) in tool["parameters"].items() if req)
        categories.setdefault("all", []).append(tool)
        print(f"  {name:30s}  params={param_count} (required={required})")
    
    print()
    print(f"  Total tools:    {len(TOOLS)}")
    print(f"  Total packages: {len(PACKAGE_MAP)}")
    print(f"  Total settings: {len(SETTINGS_INTENTS)}")
    print(f"  Total keycodes: {len(KEYCODES)}")
    print()
    print("  Categories:")
    print("    1.  Widget-Based Tapping     (5 tools)  -- THE CORE INNOVATION")
    print("    2.  Coordinate-Based Input   (5 tools)  -- Fallback + long press")
    print("    3.  Text Input               (3 tools)")
    print("    4.  Navigation & Gestures    (6 tools)")
    print("    5.  App Management           (9 tools)")
    print("    6.  Screen & UI Information  (6 tools)")
    print("    7.  Clipboard                (2 tools)")
    print("    8.  System Settings/Toggles  (9 tools)")
    print("    9.  Notifications            (4 tools)")
    print("    10. File & Device Ops        (5 tools)")
    print("    11. Waiting & Timing         (2 tools)")
    print("    12. Text Extraction          (2 tools)")
    print("    13. Composite/High-Level     (3 tools)")
    print("    14. Task Control             (3 tools)")
    print("=" * 70)
