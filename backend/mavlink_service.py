"""Read-only MAVLink telemetry receiver; all socket work stays off the event loop."""
from __future__ import annotations
import logging, math, threading, time
from typing import Any
import config
from telemetry import ingest
logger = logging.getLogger(__name__)
try:
    from pymavlink import mavutil
except ImportError: mavutil = None

def _value(message: Any, name: str, default: Any = None) -> Any: return getattr(message, name, default)
def _source_id(message: Any, method: str) -> int | None:
    try:
        value = getattr(message, method, None)
        return int(value()) if callable(value) else None
    except (TypeError, ValueError): return None

class MavlinkTelemetryService:
    def __init__(self) -> None:
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._thread: threading.Thread | None = None; self._connection: Any = None
        self._status, self._last_heartbeat = "DISABLED", None; self._sample = self._empty_sample()
    def _source(self) -> str: return "sitl" if getattr(config.settings, "mavlink_simulation_mode", False) else "real"
    def _empty_sample(self) -> dict[str, Any]:
        return {"timestamp":None,"received_at":None,"system_id":None,"component_id":None,"latitude":None,"longitude":None,"altitude_m":None,"relative_altitude_m":None,"ground_speed_mps":None,"air_speed_mps":None,"heading_deg":None,"roll_deg":None,"pitch_deg":None,"yaw_deg":None,"battery_voltage_v":None,"battery_current_a":None,"battery_remaining_percent":None,"armed":None,"flight_mode":None,"gps_fix_type":None,"satellites_visible":None,"heartbeat_age_seconds":None,"source":self._source(),"battery_percent":None,"gps_fix":None,"satellite_count":None}
    @staticmethod
    def _coordinate(value: Any, limit: int) -> float | None:
        if not isinstance(value, (int, float)) or value == 0: return None
        value = value / 1e7
        return value if -limit <= value <= limit else None
    def start(self) -> None:
        if not config.settings.mavlink_enabled:
            with self._lock: self._status = "DISABLED"
            return
        if not config.settings.mavlink_read_only:
            logger.error("MAVLink startup rejected: MAVLINK_READ_ONLY must be true")
            with self._lock: self._status = "DISABLED"
            return
        if mavutil is None:
            logger.error("MAVLink enabled but pymavlink is unavailable")
            with self._lock: self._status = "DISCONNECTED"
            return
        if self._thread and self._thread.is_alive(): return
        self._stop.clear()
        with self._lock: self._status = "CONNECTING"
        self._thread = threading.Thread(target=self._run, daemon=True, name="mavlink-telemetry"); self._thread.start()
    def stop(self) -> None:
        self._stop.set(); connection = self._connection
        if connection is not None:
            try: connection.close()
            except Exception: pass
        if self._thread: self._thread.join(timeout=3)
        self._connection = None
    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self._status; age = None if self._last_heartbeat is None else round(max(0, time.time()-self._last_heartbeat), 2)
        timeout = getattr(config.settings, "mavlink_heartbeat_timeout_seconds", config.settings.airborne_telemetry_stale_seconds)
        if state == "CONNECTED" and age is not None and age > timeout:
            disconnect_after = max(timeout, getattr(config.settings, "mavlink_disconnect_seconds", timeout * 3))
            state = "DISCONNECTED" if age > disconnect_after else "STALE"
        return {"state":state,"connection":config.settings.mavlink_connection if config.settings.mavlink_enabled else None,"read_only":True,"heartbeat_age_seconds":age,"simulation":getattr(config.settings,"mavlink_simulation_mode",False),"telemetry_source":self._source()}
    def _run(self) -> None:
        first_attempt = True
        while not self._stop.is_set():
            try:
                with self._lock: self._status = "CONNECTING" if first_attempt else "RECONNECTING"
                first_attempt = False; self._connection = mavutil.mavlink_connection(config.settings.mavlink_connection, autoreconnect=False)
                while not self._stop.is_set():
                    message = self._connection.recv_match(blocking=True, timeout=1)
                    if message is not None: self.handle_message(message)
            except Exception as exc:
                if not self._stop.is_set(): logger.warning("MAVLink connection lost: %s", exc)
                with self._lock: self._status = "DISCONNECTED"
            finally:
                connection, self._connection = self._connection, None
                if connection is not None:
                    try: connection.close()
                    except Exception: pass
            if not self._stop.is_set():
                with self._lock: self._status = "RECONNECTING"
                self._stop.wait(getattr(config.settings,"mavlink_reconnect_seconds",3.0))
    def handle_message(self, message: Any, now: float | None = None) -> None:
        """Normalize a received message. This method never transmits MAVLink."""
        now = time.time() if now is None else now; kind = message.get_type() if hasattr(message,"get_type") else type(message).__name__
        with self._lock:
            s = self._sample; s.update(timestamp=int(now),received_at=now,source=self._source(),system_id=_source_id(message,"get_srcSystem") or s["system_id"],component_id=_source_id(message,"get_srcComponent") or s["component_id"])
            if kind == "HEARTBEAT":
                self._last_heartbeat=now; mode=_value(message,"base_mode"); s["armed"]=bool(mode&128) if isinstance(mode,int) else None
                if mavutil is not None:
                    try: s["flight_mode"]=mavutil.mode_string_v10(message)
                    except Exception: s["flight_mode"]=None
            elif kind in {"GLOBAL_POSITION_INT","GPS_RAW_INT"}:
                lat,lon=self._coordinate(_value(message,"lat"),90),self._coordinate(_value(message,"lon"),180)
                if lat is not None: s["latitude"]=lat
                if lon is not None: s["longitude"]=lon
                alt=_value(message,"alt")
                if isinstance(alt,(int,float)): s["altitude_m"]=alt/1000.0
                if kind == "GLOBAL_POSITION_INT":
                    relative=_value(message,"relative_alt")
                    if isinstance(relative,(int,float)): s["relative_altitude_m"]=relative/1000.0
                    heading=_value(message,"hdg")
                    if isinstance(heading,(int,float)) and heading != 65535: s["heading_deg"]=heading/100.0
                else:
                    s["gps_fix_type"],s["satellites_visible"]=_value(message,"fix_type"),_value(message,"satellites_visible")
                    s["gps_fix"],s["satellite_count"]=s["gps_fix_type"],s["satellites_visible"]
            elif kind == "VFR_HUD":
                s["ground_speed_mps"],s["air_speed_mps"]=_value(message,"groundspeed"),_value(message,"airspeed"); heading=_value(message,"heading")
                if isinstance(heading,(int,float)) and heading >= 0: s["heading_deg"]=heading
            elif kind == "SYS_STATUS":
                voltage,current=_value(message,"voltage_battery"),_value(message,"current_battery")
                s["battery_voltage_v"]=voltage/1000.0 if isinstance(voltage,(int,float)) and voltage>=0 else None; s["battery_current_a"]=current/100.0 if isinstance(current,(int,float)) and current>=0 else None
                remaining=_value(message,"battery_remaining"); s["battery_remaining_percent"]=remaining if isinstance(remaining,(int,float)) and remaining>=0 else None; s["battery_percent"]=s["battery_remaining_percent"]
            elif kind == "BATTERY_STATUS":
                remaining=_value(message,"battery_remaining")
                if isinstance(remaining,(int,float)) and remaining>=0: s["battery_remaining_percent"]=remaining; s["battery_percent"]=remaining
            elif kind == "ATTITUDE":
                for source,target in (("roll","roll_deg"),("pitch","pitch_deg"),("yaw","yaw_deg")):
                    value=_value(message,source); s[target]=math.degrees(value) if isinstance(value,(int,float)) else None
            s["heartbeat_age_seconds"]=None if self._last_heartbeat is None else round(max(0,now-self._last_heartbeat),2)
            if kind == "HEARTBEAT": self._status="CONNECTED"
            outgoing=dict(s)
        ingest(config.settings.airborne_camera_id,outgoing)
service=MavlinkTelemetryService()
