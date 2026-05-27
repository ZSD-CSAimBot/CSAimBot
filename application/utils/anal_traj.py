import os
import glob
import json
import matplotlib.pyplot as plt


def get_latest_telemetry_file(folder="telemetry"):
    files = glob.glob(os.path.join(folder, "*.json"))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def analyze_and_plot():
    filepath = get_latest_telemetry_file()
    if not filepath:
        print("Nie znaleziono logów telemetrii w folderze data/telemetry.")
        return

    print(f"Analiza pliku: {os.path.basename(filepath)}")
    with open(filepath, 'r') as f:
        data = json.loads(f.read())

    path = data.get("path", [])
    if not path:
        print("Brak danych ścieżki w pliku.")
        return

    times = [p["time"] for p in path]
    xs = [p["x"] for p in path]
    ys = [p["y"] for p in path]

    start_x = xs[0]
    start_y = ys[0]
    end_x = xs[-1]
    end_y = ys[-1]

    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.canvas.manager.set_window_title(f"Telemetry: {os.path.basename(filepath)}")

    ax1.plot(xs, ys, label="Fizyczna ścieżka", color="cyan", linewidth=2, marker='o', markersize=3)
    ax1.scatter([start_x], [start_y], color="lime", s=100, label="START", zorder=5)
    ax1.scatter([end_x], [end_y], color="red", s=100, label="KONIEC", zorder=5)

    ax1.set_title("Odwzorowanie ruchu 2D")
    ax1.set_xlabel("Oś X (CM)")
    ax1.set_ylabel("Oś Y (CM)")
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.2)
    ax1.legend()
    ax1.axis('equal')

    ax2.plot(times, xs, label="Oś X", color="cyan", linewidth=2)
    ax2.plot(times, ys, label="Oś Y", color="magenta", linewidth=2)
    ax2.set_title("Overshoot i Stabilizacja w Czasie")
    ax2.set_xlabel("Czas (Sekundy)")
    ax2.set_ylabel("Pozycja (CM)")
    ax2.grid(True, alpha=0.2)
    ax2.legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    analyze_and_plot()