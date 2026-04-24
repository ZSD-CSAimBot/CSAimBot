import time
import random

from utils.json_utils import StatsManager

def print_stats(sm: StatsManager):
    print("\n--- Aktualne statystyki ---")
    for key in StatsManager.DEFAULTS:
        raw = sm.get(key)
        formatted = StatsManager.format_value(key, raw)
        print(f"  {key:10s}: {formatted}")
    print("---------------------------")


def main():
    sm = StatsManager()
    print(f"Plik stats.json: {sm.path}")
    print_stats(sm)

    rounds = 10
    for i in range(1, rounds + 1):
        print(f"\n[Runda {i}/{rounds}]")

        sm.increment("lmb", random.randint(1, 5))
        sm.increment("rmb", random.randint(0, 2))
        sm.increment("keys", random.randint(5, 20))
        sm.increment("time", 1)
        sm.increment("dist", round(random.uniform(0.1, 2.0), 2))
        sm.increment("energy", round(random.uniform(0.01, 0.1), 3))

        if i % 3 == 0:
            sm.increment("mouse", 1)

        print_stats(sm)
        time.sleep(1)

    print("\nGotowe. Dane zapisane w:", sm.path)


if __name__ == "__main__":
    main()
