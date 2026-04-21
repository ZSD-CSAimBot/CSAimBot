# Milestone 2: Konstrukcja i sterowanie ręczne

**Moduł:** M2 - Software (Aplikacja i integracja wejścia)
**Cel:** Aplikacja PC czytająca klawiaturę i wysyłająca komendy do mikrokontrolera, symulacja w Gazebo, kompensacja odrzutu broni.

### Weryfikacja Wymagań (Warunki przejścia)

- [x] **Rozmiar datasetu min. 10 000 zdjęć:** Zgromadzono **10 835** oznaczonych zdjęć (wersja v4.0), co z nadwyżką spełnia cel.
- [x] **Skuteczność YOLO > 95%:** Osiągnięto średnio **97.8%** mAP50 dla wszystkich klas, co znacząco przewyższa wymagany próg.
- [ ] **Opóźnienie komunikacji (Latency) < 5 ms:** Osiągnięto **[DO TESTU]** ms na linii PC -> Mikrokontroler (Baudrate: 115200).
- [ ] **Zgubione ramki ~0% (na 10 000 prób):** Zarejestrowano **[DO TESTU]** zgubionych ramek.

---

### 1. Komunikacja PC -> Mikrokontroler (UART)

Przeprowadzono analizę logów z timestampami wysłania paczki danych oraz potwierdzenia jej odbioru. 
* **Protokół i prędkość:** UART, 115200 baud
* **Średnie opóźnienie (Latency):** [DO TESTU] ms
* **Maksymalne opóźnienie:** [DO TESTU] ms
* **Ilość prób testowych:** 10 000 wysłanych pakietów
* **Skuteczność dostarczenia (Packet Loss):** [DO TESTU]%

### 2. Aplikacja PC i Logika Sterowania

Aplikacja integruje wejście użytkownika oraz przetwarza dane z modelu detekcji, realizując następujące założenia:
* **Czytanie klawiatury:** Zaimplementowano bez opóźnień asynchroniczne odczytywanie wciśnięć klawiszy sterujących.
* **Kompensacja odrzutu broni (Recoil Control):** [DO ZROBIENIA].
* **Symulacja (Gazebo):** [DO TESTU].

---

### 3. Wyniki Detekcji Wizyjnej (YOLO)

Zbiór danych został pomyślnie rozbudowany do wymaganych rozmiarów, a zoptymalizowany model (YOLO26n) wykazuje rewelacyjną skuteczność przy zachowaniu minimalnych opóźnień.

**Wydajność modelu:**
* **Sprzęt testowy:** Intel Core i7-13700KF, 32GB RAM, RTX 5070 Ti
* **Czas przetwarzania (Pipeline):** 1.8 ms (0.3 ms pre + 1.3 ms inferencja + 0.2 ms post)
* **Szacowany FPS (sam model):** ~555 FPS

**Skuteczność detekcji (Wybrane klasy):**

| Klasa | Precyzja (P) | Skuteczność (mAP50) |
| :--- | :---: | :---: |
| **Wszystkie (all)** | **95.8%** | **97.8%** |
| **Terrorysta (tt)** | 96.0% | 97.8% |
| **Antyterrorysta (ct)** | 95.6% | 96.8% |
| **Głowa TT / CT** | 96.5% / 94.5% | 97.2% / 95.6% |
| **Bronie (Rifle, Pistol, etc.)** | > 91.0% | > 97.8% |

**Dataset:**
* **Ilość zdjęć:** 10 835
* **Źródło:** [CSGO Dataset v4 (Roboflow)](https://universe.roboflow.com/ukaszs-workspace/csgo-dataset/dataset/4)