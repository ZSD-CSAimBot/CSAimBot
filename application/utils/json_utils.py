import json
import os


class StatsManager:
    """Persist and manage application statistics stored in a JSON file."""

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
        """Initialize the stats manager.

        Args:
            path: Optional path to the stats JSON file. When omitted, the
                default project stats file is used.
        """
        if path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "..", "data", "stats.json")
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.stats = self.load()

    def load(self):
        """Load statistics from disk.

        Returns:
            A dictionary containing the merged default and persisted stats.
        """
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {**self.DEFAULTS, **data}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self.DEFAULTS)

    def save(self):
        """Write the current statistics state to disk."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=4)

    def reload(self):
        """Reload statistics from disk and replace the in-memory state."""
        self.stats = self.load()

    def get(self, key):
        """Return a single statistic value.

        Args:
            key: Statistic name.

        Returns:
            The stored value for the given key, or 0 if it is missing.
        """
        return self.stats.get(key, 0)

    def set(self, key, value):
        """Set a statistic value and persist the change.

        Args:
            key: Statistic name.
            value: Value to store.
        """
        self.stats[key] = value
        #self.save()

    def increment(self, key, amount=1):
        """Increase a statistic value and persist the change.

        Args:
            key: Statistic name.
            amount: Amount to add to the stored value.
        """
        self.stats[key] = self.stats.get(key, 0) + amount
        #self.save()

    def get_all(self):
        """Return a copy of all stored statistics.

        Returns:
            A shallow copy of the statistics dictionary.
        """
        return dict(self.stats)

    @staticmethod
    def format_value(key, value):
        """Format a statistic value for display.

        Args:
            key: Statistic name.
            value: Raw statistic value.

        Returns:
            A human-readable string representation of the value.
        """
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
