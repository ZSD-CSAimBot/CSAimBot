# Milestones

---

## Milestone 1: Wstępny model i projekt sprzętowy
### M1 - Software (Wykrywanie w YOLO):

* **Cel**: Przetwarzanie obrazu i lokalizacja przeciwników na ekranie, komunikacja z mikrokontrolerem.

* **Mierzalny wskaźnik**: Średnia precyzja, szybkość przetwarzania (FPS) oraz rozmiar datasetu.

* **Dataset / Sposób pomiaru**: Ewaluacja na zbiorze testowym złożonym ze screenów z gry na różnych mapach z użyciem wbudowanych skryptów YOLO. Prędkość mierzona podczas gry lokalnej.

* **Warunek przejścia dalej**: Skuteczność YOLO > 80% dla wykrywania modeli CT/T, stałe utrzymanie min. 60 FPS w czasie inferencji na karcie RTX 2060, dataset o rozmiarze min 5000 zdjęć.

### M1 - Hardware (Projekt CAD):

* **Cel**: Zaprojektowanie robota kartezjańskiego zdolnego do przemieszczania i podnoszenia myszki oraz przygotowanie kosztorysu

* **Mierzalny wskaźnik**: Osiągalna przestrzeń robocza oraz teoretyczny luz mechaniczny.

* **Sposób pomiaru**: Symulacja kinematyki i pomiary w programie typu CAD (np. Fusion 360).

* **Warunek przejścia dalej**: Projekt pozwala na pełne pokrycie wirtualnej podkładki o wymiarach min. 25x25 cm, podniesienie uchwytu z myszką w osi Z na wysokość gwarantującą brak odczytu sensora oraz zakupienie części.
---

## Milestone 2: Konstrukcja i sterowanie ręczne
### M2 - Software (Aplikacja i integracja wejścia):

* **Cel**: Aplikacja PC czytająca klawiaturę i wysyłająca komendy do mikrokontrolera, symulacja w Gazebo, kompensacja odrzutu broni.

* **Mierzalny wskaźnik**:Opóźnienie przesyłu danych (Latency) na linii PC -> Mikrokontroler.

* **Sposób pomiaru**: Analiza logów z timestampami wysłania paczki danych oraz potwierdzenia jej odbioru przez UART (115200 baud).

* **Warunek przejścia dalej**: Skuteczność YOLO > 95%, opóźnienie wysłania pakietu poniżej 5 ms i ~0% zgubionych ramek na dystansie 10 tysięcy prób, dataset o rozmiarze min 10000 zdjęć.

### M2 - Hardware (Fizyczny robot):

* **Cel**: Budowa fizycznego robota i weryfikacja poprawności sterowania silnikami z poziomu aplikacji.

* **Mierzalny wskaźnik**: Czas reakcji mechaniki na komendę.

* **Sposób pomiaru**: Nagranie w zwolnionym tempie od momentu wciśnięcia przycisku klawiatury do rozpoczęcia ruchu silnika krokowego/serwa.

* **Warunek przejścia dalej**: Wydrukowane elementy 3D, reakcja silników i fizyczne poruszenie myszką w czasie < ~50 ms.
---

## Milestone 3: Pełna integracja (Auto-Aim i kalibracja)
### M3 - Software + Hardware:

* **Cel**: Integracja całego systemu: YOLO podaje koordynaty, algorytm przelicza je na kroki, a robot fizycznie namierza i strzela.

* **Mierzalny wskaźnik**: Całkowity czas reakcji układu, celność strzału oraz skuteczność wykrywania broni po stronie gracza.

* **Dataset / Sposób pomiaru**: Testy na lokalnym serwerze treningowym (np. Aim Botz). Mierzenie poprzez analizę nagrania z rozgrywki.

* **Warunki przejścia dalej**:

* Całkowity czas reakcji układu (Wykrycie -> Ruch -> Strzał) wynosi < 200 ms.

* Dokładność namierzania stojącego celu > 90%.

* Półautomatyczna procedura kalibracji eDPI/myszki działa poprawnie i kończy się w czasie < 2 minut.

* System poprawnie włącza/wyłącza kompensację odrzutu na podstawie trzymanej broni (AK47/M4A1 vs Pistolet/Snajperka).


