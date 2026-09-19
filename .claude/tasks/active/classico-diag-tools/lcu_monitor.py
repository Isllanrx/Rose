"""Read-only LCU event recorder for issue #68. Only subscribes; never sends PATCH/POST."""
import base64
import json
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path

import websocket

LOCKFILE = Path(r"D:\Riot Games\League of Legends\lockfile")
OUT = Path(sys.argv[1])
EVENTS = [
    "OnJsonApiEvent_lol-gameflow_v1_gameflow-phase",
    "OnJsonApiEvent_lol-champ-select_v1_session",
    "OnJsonApiEvent_lol-champ-select_v1_skin-selector-info",
    "OnJsonApiEvent_lol-champ-select_v1_skin-carousel-skins",
]


def out(tag, data):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"{ts} {tag} {json.dumps(data, ensure_ascii=False)}"
    with OUT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def session_view(s):
    me = s.get("localPlayerCellId")
    my_pick = None
    for rnd in s.get("actions") or []:
        for a in rnd or []:
            if a.get("actorCellId") == me and a.get("type") == "pick":
                my_pick = {"champ": a.get("championId"), "completed": a.get("completed"), "inProgress": a.get("isInProgress")}
    mine = next((p for p in s.get("myTeam") or [] if p.get("cellId") == me), {})
    timer = s.get("timer") or {}
    return {
        "phase": timer.get("phase"),
        "left_ms": timer.get("adjustedTimeLeftInPhase"),
        "allowSkinSelection": s.get("allowSkinSelection"),
        "cell": me,
        "myPick": my_pick,
        "champ": mine.get("championId"),
        "selectedSkinId": mine.get("selectedSkinId"),
        "players": len(s.get("myTeam") or []) + len(s.get("theirTeam") or []),
    }


def run_once():
    while not LOCKFILE.exists():
        time.sleep(1)
    _, _, port, password, _ = LOCKFILE.read_text().split(":")
    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    ws = websocket.create_connection(
        f"wss://127.0.0.1:{port}/", header=[f"Authorization: Basic {auth}"],
        sslopt={"cert_reqs": ssl.CERT_NONE}, subprotocols=["wamp"],
    )
    for e in EVENTS:
        ws.send(json.dumps([5, e]))
    out("CONNECTED", {"port": port})
    last_view = None
    while True:
        msg = ws.recv()
        if not msg:
            continue
        data = json.loads(msg)
        if not (isinstance(data, list) and len(data) >= 3 and isinstance(data[2], dict)):
            continue
        ev = data[2]
        uri, typ, payload = ev.get("uri"), ev.get("eventType"), ev.get("data")
        if uri == "/lol-champ-select/v1/session":
            if payload:
                view = session_view(payload)
                cmp = {k: v for k, v in view.items() if k != "left_ms"}
                if cmp != last_view:
                    last_view = cmp
                    out("SESSION", view)
            else:
                out("SESSION", {"eventType": typ})
                last_view = None
        elif uri == "/lol-champ-select/v1/skin-carousel-skins":
            skins = payload or []
            out("CAROUSEL", {"eventType": typ, "count": len(skins),
                             "unlocked": [s.get("id") for s in skins if s.get("unlocked")]})
        else:
            out(uri.rsplit("/", 1)[-1].upper(), {"eventType": typ, "data": payload})


while True:
    try:
        run_once()
    except Exception as e:  # client closed or restarted: wait for the next lockfile
        out("DISCONNECTED", {"error": str(e)})
        time.sleep(2)
