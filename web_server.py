"""
Phone Brain v2 - Web UI Server (High-Performance)
================================================
Beautiful web interface for the Phone Brain AI Android Control Agent.
Uses Flask + Flask-SocketIO for real-time WebSocket communication.

Optimized for maximum speed:
- Parallel screenshot + UI dump via ThreadPoolExecutor
- Loop detection with auto-completion
- Minimal inter-step delays

Usage:
    python web_server.py
    Then open http://localhost:5000 in your browser.
"""

import asyncio
import json
import threading
import time
import base64
import hashlib
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

from phone_brain import (
    Config, DeviceController, LLMClient, ToolExecutor, PhoneBrainAgent, SessionMemory,
    SYSTEM_PROMPT, PACKAGE_MAP, parse_ui_hierarchy, format_screen_info,
    InterruptionHandler, classify_error, TaskPlanner, KnowledgeBase,
    screen_hash_from_b64, screens_are_same, is_progress_sensitive, build_reflection,
)

# ═══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "rundroid-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Thread pool for parallel ADB operations (screenshot + UI dump at once)
executor_pool = ThreadPoolExecutor(max_workers=4)

# Global state
agent_state = {
    "running": False,
    "task": "",
    "step": 0,
    "max_steps": 60,
    "status": "idle",  # idle, running, done, failed
    "history": [],
    "last_screenshot": None,
    "last_thought": "",
    "last_action": "",
    "device_connected": False,
    "device_info": "",
    "screen_size": "unknown",
    "turbo_mode": False,
}

device_controller: DeviceController | None = None
config: Config | None = None
agent_lock = threading.Lock()

# Pending ask_user state
ask_user_event = threading.Event()
ask_user_answer = ""


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP DETECTION  (action-aware + screen-state-aware)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_action_loop(action_log: list[str], window: int = 4) -> bool:
    """Detect repetitive *action* patterns (ignores screen state)."""
    if len(action_log) < window:
        return False
    recent = action_log[-window:]
    # All same action repeated
    if len(set(recent)) == 1:
        return True
    # A-B-A-B alternation  (3 cycles in last 6)
    if len(action_log) >= 6:
        last6 = action_log[-6:]
        if (last6[0] == last6[2] == last6[4]) and (last6[1] == last6[3] == last6[5]):
            return True
    # 3-of-5 dominance
    if len(action_log) >= 5:
        from collections import Counter
        counts = Counter(action_log[-5:])
        if counts.most_common(1)[0][1] >= 3:
            return True
    return False


def detect_screen_loop(screen_hash_log: list, window: int = 3) -> bool:
    """Return True when the last *window* screens are perceptually identical."""
    if len(screen_hash_log) < window:
        return False
    recent = screen_hash_log[-window:]
    first = recent[0]
    if first is None:
        return False
    return all(h is not None and screens_are_same(first, h) for h in recent[1:])


def detect_loop(action_log: list[str], screen_hash_log: list | None = None, window: int = 4) -> str:
    """
    Combined loop detector.
    Returns:
      ""          – no loop
      "action"    – action-pattern loop (screen may be changing)
      "stuck"     – both action AND screen are repeating → truly stuck
    """
    action_loop = detect_action_loop(action_log, window)
    screen_stuck = detect_screen_loop(screen_hash_log or [], window=3)

    if action_loop and screen_stuck:
        return "stuck"
    if action_loop:
        return "action"
    if screen_stuck and len(action_log) >= 3:
        return "stuck"      # screen frozen even with varied actions
    return ""


def build_loop_hint(action_log: list[str], loop_level: str = "") -> str:
    """Build a warning message for the LLM when loop-like behavior detected."""
    if not loop_level:
        # Soft pre-warning: last 3 actions have very low diversity
        if len(action_log) >= 3 and len(set(action_log[-3:])) <= 2:
            return (
                "\n\n*** WARNING: Your recent actions look repetitive. "
                "If the task is already complete, call done. "
                "Otherwise try a COMPLETELY different approach. ***\n"
            )
        return ""
    if loop_level == "action":
        return (
            "\n\n*** LOOP DETECTED: You are repeating the same action(s). "
            "The task may be complete — call done if so. "
            "Otherwise you MUST try a fundamentally different strategy "
            "(different widget, scroll, go back, etc.). DO NOT repeat the same action. ***\n"
        )
    # "stuck"
    return (
        "\n\n*** STUCK: The screen has NOT changed despite repeated actions. "
        "Either call done (if task is complete) or try: press back, scroll, "
        "open a different app, or change your entire approach. ***\n"
    )


def fallback_actions(action: str, params: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    if action == "tap_by_text" and params.get("text"):
        out.append(("tap_by_desc", {"desc": params.get("text")}))
    elif action == "tap_by_desc" and params.get("desc"):
        out.append(("tap_by_text", {"text": params.get("desc")}))
    elif action == "tap_by_id":
        rid = params.get("resource_id", params.get("id", ""))
        if rid and "/" in rid:
            out.append(("tap_by_text", {"text": rid.split("/")[-1].replace("_", " ")}))
    elif action == "type_text":
        text_value = params.get("text", params.get("value"))
        if text_value:
            out.append(("clear_and_type", {"text": text_value}))
    return out


def infer_memory_from_action(action: str, params: dict, success: bool, message: str) -> list[tuple[str, str, str]]:
    if not success:
        return []
    writes: list[tuple[str, str, str]] = []
    text_value = params.get("text", params.get("value"))
    if action == "type_text" and text_value:
        writes.append(("last_typed_text", str(text_value), "task"))
    elif action == "set_clipboard" and text_value:
        writes.append(("clipboard_text", str(text_value), "task"))
    elif action == "ask_user" and message.startswith("User answered:"):
        answer = message.split(":", 1)[1].strip()
        writes.append(("last_user_answer", answer, "task"))

    if action == "web_search" and success:
        query = str(params.get("query", "")).lower()
        if "package" in query and "name" in query:
            alias = re.sub(r"[^a-z0-9 ]+", " ", query).strip()
            alias = " ".join([t for t in alias.split() if t not in {"package", "name", "android", "app"}])[:40].strip()
            m = re.search(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", str(message).lower())
            if alias and m:
                writes.append((f"package_alias_{alias.replace(' ', '_')}", m.group(0), "session"))

    return writes


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE INIT
# ═══════════════════════════════════════════════════════════════════════════════

def init_device(device_serial=None, model=None, reasoning=False):
    """Initialize device controller and config."""
    global device_controller, config
    try:
        config = Config(
            DEVICE_SERIAL=device_serial,
            REASONING_ENABLED=reasoning,
        )
        if model:
            config.LLM_MODEL = model

        device_controller = DeviceController(config)
        agent_state["device_connected"] = True
        agent_state["screen_size"] = f"{device_controller.width}x{device_controller.height}"

        # Get device info
        ok, info = device_controller.get_device_info()
        if ok:
            agent_state["device_info"] = info

        return True, "Device connected"
    except Exception as e:
        agent_state["device_connected"] = False
        return False, str(e)


def web_ask_user(question: str) -> str:
    """Ask user via WebSocket and wait for response."""
    global ask_user_answer
    ask_user_event.clear()
    ask_user_answer = ""

    socketio.emit("ask_user", {"question": question})

    # Wait for user response (timeout 120 seconds)
    ask_user_event.wait(timeout=120)

    return ask_user_answer if ask_user_answer else "(no answer provided)"


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT TASK RUNNER (OPTIMIZED FOR SPEED)
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent_task(task: str, max_steps: int = 60, reasoning: bool = False, turbo_mode: bool = False):
    """
    Run an agent task in a background thread, emitting events via SocketIO.

    Speed optimizations:
    - Screenshot + UI dump run in PARALLEL via ThreadPoolExecutor
    - No unnecessary sleep between steps (only after tool execution)
    - LLM call starts immediately after screen capture
    - Loop detection auto-completes stuck agents
    """
    global agent_state

    # Fallback no-op (overridden after memory init inside try)
    def record_task_once(success: bool, message: str):
        return

    with agent_lock:
        if agent_state["running"]:
            socketio.emit("error", {"message": "A task is already running"})
            return

        agent_state["running"] = True
        agent_state["task"] = task
        agent_state["step"] = 0
        agent_state["max_steps"] = max_steps
        agent_state["status"] = "running"
        agent_state["history"] = []
        agent_state["last_thought"] = ""
        agent_state["last_action"] = ""
        agent_state["turbo_mode"] = bool(turbo_mode)

    socketio.emit("task_started", {
        "task": task,
        "max_steps": max_steps,
        "turbo_mode": bool(turbo_mode),
    })

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if config is None:
            init_device(reasoning=bool(reasoning))

        if not agent_state["device_connected"] or config is None or device_controller is None:
            socketio.emit("task_finished", {
                "success": False,
                "message": "No device connected. Please connect a device first.",
            })
            agent_state["running"] = False
            agent_state["status"] = "failed"
            return

        # Local refs for speed (avoid global lookups in tight loop)
        _config = config
        _config.REASONING_ENABLED = bool(reasoning)
        _device = device_controller
        llm = LLMClient(_config)
        memory = SessionMemory(_config.MEMORY_DIR)
        knowledge = KnowledgeBase(_config.KNOWLEDGE_DIR)
        memory.start_task()
        memory.remember("current_task", task, "task")

        tools = ToolExecutor(
            _device,
            ask_user_fn=web_ask_user,
            remember_fn=memory.remember,
            recall_fn=memory.recall,
        )

        # ── Task Planning: decompose into sub-goals ──
        socketio.emit("step_update", {"step": 0, "phase": "planning", "message": "Planning task sub-goals..."})
        try:
            task_plan = loop.run_until_complete(TaskPlanner.plan(
                llm, task, memory.session_facts_text(limit=20)
            ))
        except Exception:
            task_plan = [task]
        plan_step = 0
        memory.remember("task_plan", json.dumps(task_plan, ensure_ascii=False), "task")
        socketio.emit("step_update", {"step": 0, "phase": "planned", "message": f"Plan: {len(task_plan)} steps", "plan": task_plan})

        # ── Retrieve similar past traces (demonstration learning) ──
        demo_text = knowledge.format_demonstrations(task)

        history: list[str] = []
        action_log: list[str] = []  # compact action signatures for loop detection
        screen_hash_log: list = []  # perceptual hashes for screen-state loop detection
        loop_strike = 0             # escalating counter: 1=warn, 2=re-plan, 3+=force-stop
        iteration = 0
        consecutive_failures = 0
        task_recorded = False
        last_reflection = ""

        def memory_context_text() -> str:
            return (
                "WORKING MEMORY (current task):\n"
                f"{memory.task_memory_text()}\n\n"
                "SESSION FACTS (persistent from all previous tasks):\n"
                f"{memory.session_facts_text(limit=40)}\n\n"
                "SESSION TIMELINE (since session start):\n"
                f"{memory.session_timeline_text(limit=25)}\n\n"
                "RECENT TASK OUTCOMES:\n"
                f"{memory.session_history_text(limit=8)}"
            )

        def record_auto_memory(action: str, params: dict, success: bool, message: str):
            try:
                for k, v, scope in infer_memory_from_action(action, params, success, message):
                    memory.remember(k, v, scope)
            except Exception:
                pass

        def record_task_once(success: bool, message: str):
            nonlocal task_recorded
            if task_recorded:
                return
            try:
                memory.record_task(task, success, message, history)
            except Exception:
                pass
            task_recorded = True

        while iteration < max_steps:
            if not agent_state["running"]:
                stop_msg = "Task stopped by user"
                socketio.emit("task_finished", {
                    "success": False,
                    "message": stop_msg,
                })
                record_task_once(False, stop_msg)
                break

            iteration += 1
            agent_state["step"] = iteration

            socketio.emit("step_start", {
                "step": iteration,
                "max_steps": max_steps,
                "phase": "scanning",
            })

            # ── Capture screen state ──
            if turbo_mode:
                screenshot = None
                screen_info = _device.get_screen_context()
            else:
                # PARALLEL: screenshot + UI context at the same time
                future_screenshot = executor_pool.submit(_device.screenshot)
                future_context = executor_pool.submit(_device.get_screen_context)

                screenshot = future_screenshot.result()
                screen_info = future_context.result()

                if not screenshot:
                    socketio.emit("step_update", {
                        "step": iteration,
                        "phase": "error",
                        "message": "Screenshot failed, retrying...",
                    })
                    time.sleep(0.5)
                    continue

                # Send screenshot to UI immediately
                agent_state["last_screenshot"] = screenshot
                socketio.emit("screenshot", {
                    "image": screenshot,
                    "step": iteration,
                })

            # ── Auto-handle interruptions (permissions, crashes, consents) ──
            handled, handle_msg = InterruptionHandler.detect_and_handle(_device)
            if handled:
                history.append(f"[{iteration}] auto → {handle_msg}")
                socketio.emit("step_update", {
                    "step": iteration,
                    "phase": "auto_handled",
                    "message": handle_msg,
                })
                continue  # Re-capture screen after handling

            # ── Track screen hash for loop detection ──
            if screenshot:
                screen_hash_log.append(screen_hash_from_b64(screenshot))
            else:
                screen_hash_log.append(None)

            # ── LOOP DETECTION: escalating response ──
            loop_level = detect_loop(action_log, screen_hash_log, window=4)
            loop_hint = build_loop_hint(action_log, loop_level)

            if loop_level:
                loop_strike += 1
                socketio.emit("step_update", {
                    "step": iteration,
                    "phase": "loop_detected",
                    "message": f"Loop detected (level={loop_level}, strike={loop_strike})",
                })
            else:
                loop_strike = max(0, loop_strike - 1)  # cool down

            # Strike 3+: force-stop as FAILED (not assumed success)
            if loop_strike >= 3:
                fail_msg = f"Agent stuck in loop ({loop_level}) after {iteration} steps — stopping"
                agent_state["status"] = "failed"
                socketio.emit("task_finished", {
                    "success": False,
                    "message": fail_msg,
                    "steps": iteration,
                })
                record_task_once(False, fail_msg)
                loop.run_until_complete(llm.close())
                break

            # Strike 2: attempt re-planning
            if loop_strike == 2:
                socketio.emit("step_update", {"step": iteration, "phase": "re-planning", "message": "Re-planning after loop..."})
                try:
                    remaining_desc = f"{task} (the agent already tried {iteration} steps but got stuck in a loop; re-plan remaining work)"
                    task_plan = loop.run_until_complete(TaskPlanner.plan(
                        llm, remaining_desc, memory.session_facts_text(limit=20)
                    ))
                    plan_step = 0
                    action_log.clear()
                except Exception:
                    pass

            # ── BUILD MESSAGES FOR LLM ──
            history_text = ""
            if history:
                history_text = "\n\nACTION HISTORY (recent):\n"
                for h in history[-8:]:
                    history_text += f"  {h}\n"

            mem_text = memory_context_text()
            plan_text = TaskPlanner.format_plan_for_context(task_plan, plan_step)

            user_content: list[dict] = [
                {"type": "text", "text": f"""TASK: {task}

{plan_text}

{demo_text}

SCREEN UI HIERARCHY:
{screen_info}

MEMORY CONTEXT:
{mem_text}

{last_reflection}
{history_text}{loop_hint}
Step {iteration}/{max_steps}. Analyze the screen and respond with your next action as JSON."""}
            ]

            if not turbo_mode and screenshot:
                # Annotate with Set-of-Mark labels for the LLM (raw screenshot already sent to browser)
                som_screenshot = _device.screenshot_with_som(screenshot)
                user_content.insert(0, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{som_screenshot or screenshot}"}})

            messages: list = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]

            last_msg = llm.get_last_assistant_message()
            if last_msg and _config.REASONING_ENABLED:
                messages.append({"role": "user", "content": "Proceed with the task."})
                messages.append(last_msg)

            messages.append({"role": "user", "content": user_content})

            # ── LLM CALL ──
            socketio.emit("step_update", {
                "step": iteration,
                "phase": "thinking",
                "message": (
                    "AI is reasoning (Turbo XML-only)..." if (_config.REASONING_ENABLED and turbo_mode)
                    else "AI is analyzing (Turbo XML-only)..." if turbo_mode
                    else "AI is reasoning..." if _config.REASONING_ENABLED
                    else "AI is analyzing..."
                ),
            })

            try:
                response = loop.run_until_complete(llm.chat(messages, max_tokens=1024))
            except Exception as e:
                socketio.emit("step_update", {
                    "step": iteration,
                    "phase": "error",
                    "message": f"LLM Error: {e}",
                })
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    fail_msg = f"LLM failed {consecutive_failures} times: {e}"
                    agent_state["status"] = "failed"
                    socketio.emit("task_finished", {
                        "success": False,
                        "message": fail_msg,
                    })
                    record_task_once(False, fail_msg)
                    break
                time.sleep(1)
                continue

            # ── PARSE RESPONSE ──
            parsed = PhoneBrainAgent._parse_llm_response(response)
            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            params = parsed.get("params", {})
            subgoal = parsed.get("subgoal", "")
            success_check = parsed.get("success_check", "")
            memory_write = parsed.get("memory_write", {})
            memory_read = parsed.get("memory_read", [])

            if isinstance(memory_read, list):
                for key in memory_read[:6]:
                    ok_mem, val_mem = memory.recall(str(key), "")
                    if ok_mem and val_mem:
                        history.append(f"[mem-read] {key}={val_mem}")

            if isinstance(memory_write, dict) and memory_write.get("key"):
                memory.remember(
                    str(memory_write.get("key")),
                    memory_write.get("value", ""),
                    str(memory_write.get("scope", "task")),
                )

            agent_state["last_thought"] = thought
            agent_state["last_action"] = f"{action} {json.dumps(params)}"

            socketio.emit("step_update", {
                "step": iteration,
                "phase": "acting",
                "thought": thought,
                "subgoal": subgoal,
                "success_check": success_check,
                "action": action,
                "params": params,
            })

            # ── EXECUTE TOOL ──
            pre_hash = screen_hash_from_b64(screenshot)
            if action == "done":
                done_ok, done_msg = PhoneBrainAgent.validate_done_action(task, params, history, screen_info, memory)
                if not done_ok:
                    success, message, is_terminal = False, f"Premature done blocked: {done_msg}", False
                else:
                    success, message, is_terminal = tools.execute(action, params)
            else:
                success, message, is_terminal = tools.execute(action, params)
            record_auto_memory(action, params, success, message)

            # ── Advance plan step on successful progress ──
            if success and not is_terminal and subgoal and plan_step < len(task_plan):
                plan_step += 1

            # ── Critic: verify visual progress and auto-recover ──
            if pre_hash and success and (not is_terminal) and is_progress_sensitive(action):
                time.sleep(0.12)
                post_shot = _device.screenshot()
                post_hash = screen_hash_from_b64(post_shot)
                if pre_hash and post_hash and screens_are_same(pre_hash, post_hash):
                    no_change_msg = "No visual change detected after action"
                    history.append(f"[{iteration}] critic -> {no_change_msg}")
                    memory.remember("last_no_change_action", f"{action}:{json.dumps(params, ensure_ascii=False)}", "task")

                    recovered = False
                    for fb_action, fb_params in fallback_actions(action, params):
                        fb_success, fb_message, _ = tools.execute(fb_action, fb_params)
                        fb_result = f"{'OK' if fb_success else 'FAIL'}: {fb_message}"
                        history.append(f"[{iteration}] fallback {fb_action}({json.dumps(fb_params)}) -> {fb_result}")

                        if not fb_success:
                            continue

                        time.sleep(0.12)
                        verify_shot = _device.screenshot()
                        verify_hash = screen_hash_from_b64(verify_shot)
                        if verify_hash and not screens_are_same(verify_hash, pre_hash):
                            success = True
                            message = f"Recovered via {fb_action}: {fb_message}"
                            recovered = True
                            break

                    if not recovered:
                        success = False
                        message = no_change_msg

            # ── Self-critique reflection ──
            screen_changed = False
            if pre_hash:
                final_shot = _device.screenshot() if not post_hash else None
                final_hash = screen_hash_from_b64(final_shot) if final_shot else post_hash
                if final_hash:
                    screen_changed = not screens_are_same(pre_hash, final_hash)
            last_reflection = build_reflection(action, params, success, message, success_check, screen_changed)

            result_str = f"{'OK' if success else 'FAIL'}: {message}"
            history_entry = {
                "step": iteration,
                "action": action,
                "params": params,
                "thought": thought,
                "result": result_str,
                "success": success,
            }

            # Compact action signature for loop detection
            action_sig = f"{action}:{json.dumps(params, sort_keys=True)}"
            action_log.append(action_sig)

            history.append(f"[{iteration}] {action}({json.dumps(params)}) -> {result_str}")
            agent_state["history"].append(history_entry)

            socketio.emit("step_complete", {
                "step": iteration,
                "action": action,
                "params": params,
                "thought": thought,
                "subgoal": subgoal,
                "success_check": success_check,
                "result": result_str,
                "success": success,
                "is_terminal": is_terminal,
            })

            if is_terminal:
                agent_state["status"] = "done" if success else "failed"
                socketio.emit("task_finished", {
                    "success": success,
                    "message": message,
                    "steps": iteration,
                })
                record_task_once(success, message)
                # Save successful trace for demonstration learning
                if success:
                    knowledge.save_trace(task, history, True, dict(memory.task_facts))
                loop.run_until_complete(llm.close())
                break

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    fail_msg = "Too many consecutive failures"
                    agent_state["status"] = "failed"
                    socketio.emit("task_finished", {
                        "success": False,
                        "message": fail_msg,
                        "steps": iteration,
                    })
                    record_task_once(False, fail_msg)
                    loop.run_until_complete(llm.close())
                    break

            # Minimal delay - just enough for the device to settle after action
            # Skip delay for non-interaction actions (wait, done, get_* etc.)
            if action not in ("wait", "wait_for_widget", "get_current_app",
                              "get_device_info", "get_battery", "get_clipboard"):
                time.sleep(0.15)

        else:
            # Reached max iterations
            fail_msg = f"Reached max iterations ({max_steps})"
            agent_state["status"] = "failed"
            socketio.emit("task_finished", {
                "success": False,
                "message": fail_msg,
                "steps": iteration,
            })
            record_task_once(False, fail_msg)
            loop.run_until_complete(llm.close())

        loop.close()

    except Exception as e:
        fail_msg = f"Error: {e}"
        agent_state["status"] = "failed"
        socketio.emit("task_finished", {
            "success": False,
            "message": fail_msg,
        })
        if "record_task_once" in locals():
            record_task_once(False, fail_msg)
    finally:
        agent_state["running"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(agent_state)


@app.route("/api/screenshot")
def api_screenshot():
    """Get a fresh screenshot."""
    if device_controller:
        screenshot = device_controller.screenshot()
        if screenshot:
            return jsonify({"image": screenshot})
    return jsonify({"error": "No device connected"}), 400


@app.route("/api/apps")
def api_apps():
    """Get list of known app names."""
    if device_controller and device_controller.dynamic_package_map:
        return jsonify(sorted(device_controller.dynamic_package_map.keys()))
    return jsonify(sorted(PACKAGE_MAP.keys()))


@app.route("/temp/<path:filename>")
def serve_temp(filename):
    return send_from_directory("temp", filename)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@socketio.on("connect")
def handle_connect():
    """Client connected - send current state."""
    emit("state_update", agent_state)
    # Try to auto-connect device
    if not agent_state["device_connected"]:
        ok, msg = init_device()
        emit("device_status", {
            "connected": ok,
            "message": msg,
            "screen_size": agent_state["screen_size"],
            "device_info": agent_state["device_info"],
        })
    else:
        emit("device_status", {
            "connected": True,
            "message": "Device already connected",
            "screen_size": agent_state["screen_size"],
            "device_info": agent_state["device_info"],
        })


@socketio.on("connect_device")
def handle_connect_device(data):
    """Manually connect to a device."""
    serial = data.get("serial")
    model = data.get("model")
    reasoning = as_bool(data.get("reasoning", False))
    ok, msg = init_device(device_serial=serial, model=model, reasoning=reasoning)
    emit("device_status", {
        "connected": ok,
        "message": msg,
        "screen_size": agent_state["screen_size"],
        "device_info": agent_state["device_info"],
    })


@socketio.on("run_task")
def handle_run_task(data):
    """Start a new agent task."""
    task = data.get("task", "").strip()
    if not task:
        emit("error", {"message": "No task provided"})
        return

    max_steps = data.get("max_steps", 60)
    reasoning = as_bool(data.get("reasoning", False))
    turbo_mode = as_bool(data.get("turbo_mode", False))

    if config and reasoning != config.REASONING_ENABLED:
        config.REASONING_ENABLED = bool(reasoning)

    # Run in background thread
    thread = threading.Thread(
        target=run_agent_task,
        args=(task, max_steps, reasoning, turbo_mode),
        daemon=True,
    )
    thread.start()


@socketio.on("stop_task")
def handle_stop_task():
    """Stop the currently running task."""
    agent_state["running"] = False
    agent_state["status"] = "idle"
    emit("task_stopped", {"message": "Task stop requested"})


@socketio.on("answer_user")
def handle_answer_user(data):
    """Receive user's answer to an ask_user prompt."""
    global ask_user_answer
    ask_user_answer = data.get("answer", "")
    ask_user_event.set()


@socketio.on("take_screenshot")
def handle_take_screenshot():
    """Manually take a screenshot."""
    if device_controller:
        screenshot = device_controller.screenshot()
        if screenshot:
            emit("screenshot", {"image": screenshot, "step": 0})
        else:
            emit("error", {"message": "Screenshot failed"})
    else:
        emit("error", {"message": "No device connected"})


@socketio.on("quick_action")
def handle_quick_action(data):
    """Execute a quick one-off device action (not through the agent)."""
    if not device_controller:
        emit("error", {"message": "No device connected"})
        return

    action = data.get("action", "")
    params = data.get("params", {})
    tools = ToolExecutor(device_controller)

    success, message, _ = tools.execute(action, params)
    emit("quick_action_result", {
        "action": action,
        "success": success,
        "message": message,
    })

    # Send fresh screenshot after action (parallel with small delay)
    time.sleep(0.3)
    screenshot = device_controller.screenshot()
    if screenshot:
        emit("screenshot", {"image": screenshot, "step": 0})


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
 ╔══════════════════════════════════════════════════════════════╗
 ║           Phone Brain v2 - Web UI (High-Performance)           ║
 ║                                                              ║
 ║   Open http://localhost:5000 in your browser                ║
 ║                                                              ║
 ║   Features:                                                  ║
 ║    - Parallel screenshot + UI dump for max speed             ║
 ║    - Loop detection with auto-completion                     ║
 ║    - Real-time WebSocket updates                             ║
 ║                                                              ║
 ╚══════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
