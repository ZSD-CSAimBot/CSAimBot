import json
import os


class StatsManager:
    DEFAULTS = {
        "lmb": 0,
        "rmb": 0,
        "time": 0,
        "mouse": 0,
        "dist": 0.0,
        "energy": 0.0,
        "unknown": 0,
        "keys": 0,
    }

    def __init__(self, path=None):
        if path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "..", "data", "stats.json")
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.stats = self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {**self.DEFAULTS, **data}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self.DEFAULTS)

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=4)

    def reload(self):
        self.stats = self.load()

    def get(self, key):
        return self.stats.get(key, 0)

    def set(self, key, value):
        self.stats[key] = value
        self.save()

    def increment(self, key, amount=1):
        self.stats[key] = self.stats.get(key, 0) + amount
        self.save()

    def get_all(self):
        return dict(self.stats)

    @staticmethod
    def format_value(key, value):
        if key == "time":
            secs = int(value)
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return f"{h}h {m}m {s}s"
        if key == "dist":
            return f"{value:.1f} m"
        if key == "energy":
            return f"{value:.2f} Wh"
        return str(int(value))
