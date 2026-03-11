#!/usr/bin/env python3

import time
import yaml
from evdev import UInput, ecodes as e
from openrazer.client import DeviceManager


# -------------------------
# Load Config
# -------------------------
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

BASE_INDEX = config.get("base_index", 2)
DOWN_KEY_NAME = config.get("down_key", "g").upper()
UP_KEY_NAME = config.get("up_key", "h").upper()
COOLDOWN = config.get("cooldown", 0.35)
POLL = config.get("poll_interval", 0.04)

try:
    DOWN_KEY = getattr(e, f"KEY_{DOWN_KEY_NAME}")
    UP_KEY = getattr(e, f"KEY_{UP_KEY_NAME}")
except AttributeError:
    raise ValueError("Invalid key in config.yaml")

print("=== Razer DPI Hijack (Directional Mode) ===")
print(f"Base stage: {BASE_INDEX}")
print(f"Down key: {DOWN_KEY_NAME}")
print(f"Up key: {UP_KEY_NAME}")


# -------------------------
# Setup
# -------------------------
manager = DeviceManager()

def get_mouse():
    if manager.devices:
        return manager.devices[0]
    return None

ui = UInput()

cooldown_until = 0
restoring = False
previous_index = None


# -------------------------
# Safe DBus Read
# -------------------------
def get_stage_info(mouse):
    try:
        reply = mouse._dbus.getDPIStages()
        active_index = int(reply[0])
        stages = [(int(s[0]), int(s[1])) for s in reply[1]]
        return active_index, stages
    except Exception:
        return None, None


# -------------------------
# Restore Base
# -------------------------
def restore_base(mouse, stages):
    global restoring
    try:
        restoring = True
        mouse._dbus.setDPIStages(BASE_INDEX, stages)
        time.sleep(0.02)
    except Exception:
        restoring = False


# -------------------------
# Main Loop
# -------------------------
while True:
    mouse = get_mouse()

    if not mouse:
        previous_index = None
        restoring = False
        time.sleep(0.5)
        continue

    now = time.time()

    active_index, stages = get_stage_info(mouse)

    if active_index is None:
        time.sleep(POLL)
        continue

    # Wait until restore completes
    if restoring:
        if active_index == BASE_INDEX:
            restoring = False
        previous_index = active_index
        time.sleep(POLL)
        continue

    # Initialize previous
    if previous_index is None:
        previous_index = active_index
        time.sleep(POLL)
        continue

    # Cooldown guard
    if now < cooldown_until:
        previous_index = active_index
        time.sleep(POLL)
        continue

    # EDGE DETECTION from BASE
    if previous_index == BASE_INDEX and active_index != BASE_INDEX:

        if active_index < BASE_INDEX:
            key_to_fire = DOWN_KEY
            print(f"[DOWN] {BASE_INDEX} → {active_index}")

        elif active_index > BASE_INDEX:
            key_to_fire = UP_KEY
            print(f"[UP] {BASE_INDEX} → {active_index}")

        else:
            key_to_fire = None

        if key_to_fire:
            restore_base(mouse, stages)

            ui.write(e.EV_KEY, key_to_fire, 1)
            ui.write(e.EV_KEY, key_to_fire, 0)
            ui.syn()

            cooldown_until = now + COOLDOWN

    previous_index = active_index
    time.sleep(POLL)