from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

import cantools
import can


class AnalyzerCore:
    def __init__(self) -> None:
        self.database: Optional[cantools.database.Database] = None
        self.log_file_path: Optional[Path] = None
        self.db_file_path: Optional[Path] = None
        self.available_channels: Set[int] = set()
        # channel -> set of arbitration ids
        self.available_messages: Dict[int, Set[int]] = {}
        # time range for current log
        self.time_min: Optional[float] = None
        self.time_max: Optional[float] = None
        # decode result cache
        self._decode_cache: Dict[Tuple[Any, ...], Dict[str, Dict[str, List]]] = {}

    # ---------- Loaders ----------
    def load_database(self, file_path: Path) -> int:
        self.db_file_path = file_path
        ext = file_path.suffix.lower()
        if ext == ".dbc":
            self.database = cantools.database.load_file(str(file_path))
        elif ext == ".arxml":
            self.database = cantools.database.load_file(str(file_path), database_format="arxml")
        else:
            raise ValueError("Unsupported database file format; use .dbc or .arxml")
        # invalidate cache on DB change
        self._decode_cache.clear()
        return len(self.database.messages) if self.database else 0

    def load_log(self, file_path: Path) -> int:
        self.log_file_path = file_path
        self.scan_log_file()
        # invalidate cache on log change
        self._decode_cache.clear()
        return len(self.available_channels)

    # ---------- Scanning & Queries ----------
    def scan_log_file(self) -> None:
        self.available_channels.clear()
        self.available_messages.clear()
        self.time_min = None
        self.time_max = None
        if not self.log_file_path:
            return
        with can.LogReader(str(self.log_file_path)) as reader:
            for msg in reader:
                ch = getattr(msg, "channel", None)
                if ch is None:
                    # fall back to 0 if channel unavailable
                    ch = 0
                self.available_channels.add(ch)
                if ch not in self.available_messages:
                    self.available_messages[ch] = set()
                self.available_messages[ch].add(msg.arbitration_id)
                ts = getattr(msg, "timestamp", None)
                if isinstance(ts, (int, float)):
                    if self.time_min is None or ts < self.time_min:
                        self.time_min = ts
                    if self.time_max is None or ts > self.time_max:
                        self.time_max = ts

    def get_available_channels(self) -> List[int]:
        return sorted(list(self.available_channels))

    def get_matching_messages(self, channel: int) -> Dict[int, str]:
        if not self.database:
            return {}
        found = {}
        for msg_id in sorted(list(self.available_messages.get(channel, set()))):
            try:
                m = self.database.get_message_by_frame_id(msg_id)
                found[msg_id] = f"{m.name} (0x{msg_id:X})"
            except KeyError:
                pass
        return found

    def get_signals_for_messages(self, message_ids: List[int]) -> Dict[str, str]:
        if not self.database:
            return {}
        signal_dict: Dict[str, str] = {}
        for mid in message_ids:
            try:
                msg = self.database.get_message_by_frame_id(mid)
                for s in msg.signals:
                    key = f"{msg.name}.{s.name}"
                    unit = s.unit or ""
                    signal_dict[key] = f"{msg.name}.{s.name} ({unit})"
            except KeyError:
                continue
        return signal_dict

    # ---------- Decoding ----------
    def decode(
        self,
        channel: int,
        message_ids: List[int],
        signal_keys: List[str],
        time_range: Optional[Tuple[Optional[float], Optional[float]]] = None,
        max_points: Optional[int] = None,
    ) -> Dict[str, Dict[str, List]]:
        if not (self.log_file_path and self.database):
            raise RuntimeError("Database and log file must be loaded")
        selected = set(message_ids)
        # cache key
        key = (
            channel,
            tuple(sorted(selected)),
            tuple(sorted(signal_keys)),
            (time_range[0] if time_range else None, time_range[1] if time_range else None),
            int(max_points) if max_points else None,
            self.log_file_path,
            self.db_file_path,
        )
        if key in self._decode_cache:
            return self._decode_cache[key]

        decoded_data: Dict[str, Dict[str, List]] = {k: {"timestamps": [], "values": []} for k in signal_keys}
        count = 0
        t_min = time_range[0] if time_range else None
        t_max = time_range[1] if time_range else None
        with can.LogReader(str(self.log_file_path)) as reader:
            for msg in reader:
                ch = getattr(msg, "channel", None)
                if ch is None:
                    ch = 0
                if ch != channel:
                    continue
                if msg.arbitration_id not in selected:
                    continue
                ts = getattr(msg, "timestamp", None)
                if isinstance(ts, (int, float)):
                    if t_min is not None and ts < t_min:
                        continue
                    if t_max is not None and ts > t_max:
                        continue
                try:
                    db_msg = self.database.get_message_by_frame_id(msg.arbitration_id)
                    values = db_msg.decode(msg.data)
                    for key in signal_keys:
                        msg_name, sig_name = key.split(".", 1)
                        if msg_name == db_msg.name and sig_name in values:
                            decoded_data[key]["timestamps"].append(ts if ts is not None else 0.0)
                            decoded_data[key]["values"].append(values[sig_name])
                    count += 1
                except Exception:
                    # Ignore decode errors
                    continue

        # optional downsampling per signal
        if max_points and max_points > 0:
            for sk, series in decoded_data.items():
                ts = series["timestamps"]
                vs = series["values"]
                n = len(ts)
                if n <= max_points:
                    continue
                # bucketed averaging
                bucket_count = max_points
                bucket_size = n / bucket_count
                new_ts: List[float] = []
                new_vs: List[float] = []
                acc_t = 0.0
                acc_v = 0.0
                acc_n = 0
                next_cut = bucket_size
                idx = 0
                for i in range(n):
                    acc_t += ts[i]
                    # values may be non-float; try cast
                    try:
                        acc_v += float(vs[i])
                    except Exception:
                        acc_v += 0.0
                    acc_n += 1
                    idx += 1
                    if idx >= next_cut or i == n - 1:
                        if acc_n:
                            new_ts.append(acc_t / acc_n)
                            new_vs.append(acc_v / acc_n)
                        acc_t = 0.0
                        acc_v = 0.0
                        acc_n = 0
                        next_cut += bucket_size
                series["timestamps"] = new_ts
                series["values"] = new_vs

        self._decode_cache[key] = decoded_data
        return decoded_data
