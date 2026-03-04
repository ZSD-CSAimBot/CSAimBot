# CSAimBot [CSBot]

---

## Krótki opis projektu
Celem projektu jest stworzenie fizycznego AimBota do gry CSGO. Program czytałby ekran z grą, oznaczałby przeciwników oraz zwracał wartość, o którą musiałaby poruszyć się mysz. Do ruchu myszką stworzony zostanie robot typu kartezjańskiego z odpowiednim uchwytem. Robot byłby w stanie zaadaptować się do różnych myszek i wartości DPI. Robot będzie w stanie strzelać i kompensować odrzut broni zapewniając większą dokładność. Klawiszami WASD kierowałby gracz, więc robot musiałby z nim współpracować.

---

## Zakres funkcjonalny
* Czytanie ekranu i oznaczanie przeciwników.
* Obliczanie drogi robota.
* Ruch myszką za pomocą robota kartezjańskiego oraz strzał za pomocą przycisku.
* Rozglądanie się w przypadku braku wykrycia przeciwników.
* Współpraca z graczem.

---

## Budowa systemu
* **Robot ruszający myszką:** Robot typu kartezjańskiego z silnikami krokowymi i enkoderami lub serwomechanizmami dla osi XY i śrubą kulową/trapezową dla osi Z wraz z odpowiednim uchwytem zdolnym do trzymania wielu rodzajów myszek. Robot korygowałby sterowanie w przypadku braku osiągnięcia celownika na przeciwniku oraz kompensował odrzut broni.
* **System przechwytujący ekran:** Przechwytywanie ekranu odbywać się będzie za pomocą odpowiednich bibliotek w Pythonie/C++ oraz przekazywania przechwyconych klatek do algorytmu wykrywającego przeciwników.
* **System wykrywający przeciwników:** System bazujący na YOLO będzie wykrywał i oznaczał przeciwników na obrazie i zwracał wartości pozwalające na sterowanie silnikami w robocie w celu namierzenia i eliminacji przeciwnika.

---

## Stack technologiczny

**Sprzęt - robot:**
* Mikrokontrolery, diody led, sterowniki silników.
* Silniki krokowe np. NEMA 23, śruba kulowa/trapezowa.
* Zasilacz, przetwornice step-down.
* Wydrukowane ramię robota i chwytak, serwo do obsługi chwytaka.

**Sprzęt - komputer:**
* Komputer z kartą graficzną, monitor, myszka, klawiatura.

**Oprogramowanie:**
* Język Python/ C/C++ i odpowiednie biblioteki, YOLO.
* PyCharm, Arduino IDE, VSC.
* Komunikacja szeregowa np. SPI, UART, Wi-Fi, USB.
* Algorytmy kinematyki odwrotnej.

---

## Główne założenia

### Założenia sprzętowe (Hardware)
* Projekt będzie działać w temperaturze pokojowej w zamkniętym pomieszczeniu na poziomej płaskiej powierzchni umożliwiającej poprawne zamontowanie robota (np. biurko) i umożliwiającej poprawne użycie klawiatury.
* Mysz będzie się poruszać na materiałowej podkładce do myszy.
* Mysz musi korzystać z laserowego lub optycznego sensora i posiadać przynajmniej 2 przyciski (lewy i prawy), reszta przycisków będzie ignorowana. 
* Przy zmianie myszki/wartości DPI na inną wykonywana będzie półautomatyczna procedura kalibracji. Robot będzie sprawdzał o ile musi się poruszyć, żeby przejść między punktami referencyjnymi na specjalnej mapie.
* Komunikacja PC-Mikrokontroler poprzez UART (USB) z prędkością 115200 baud.

### Założenia programowe (Software)
* Program komputerowy będzie działać na systemie Windows 11 Pro build >=25H2 lub równoważnym. Program nie będzie działać na Linuxie ani na MacOS.
* Wymagany komputer PC o odpowiedniej mocy obliczeniowej (karta graficzna wspierająca CUDA, min. GTX 1060) z monitorem, nie na laptopie.
* Program będzie wykrywać modele przeciwników w grze (będzie odróżniał modele CT od T).
* Program będzie wykrywał czy użytkownik trzyma pistolet czy karabin za pomocą klasycznej wizji maszynowej (template matching z openCV). Jeśli gracz trzyma pistolet lub karabin snajperski, to kompensacja odrzutu będzie wyłączona. W przeciwnym wypadku program będzie korygował odrzut konkretnych broni (AK47/M4A1).

### Założenia gry
* Program będzie działał tylko podczas rozpoczętej rundy, na dowolnej mapie.
* Gra musi być ustawiona na minimum 60 FPS. Wymagane włączenie opcji natychmiastowego usuwania ciał po zabójstwie w grze lokalnej.
* Czas reakcji przy eDPI dobranym tak, aby robot nie musiał podnosić myszy będzie wynosił maksymalnie tyle ile czas reakcji dobrego gracza (<200ms).

---

## Kamienie milowe

| Faza | Kategoria | Cel |
| :--- | :--- | :--- |
| **Milestone 1** | Software | Wykorzystanie YOLO do przetworzenia przechwyconych danych i wyznaczenia położenia przeciwnika. Skuteczność 100%. |
| **Milestone 1** | Hardware | Wstępny projekt robota kartezjańskiego przeznaczonego do poruszania myszką na płaszczyźnie XY oraz podnoszenia w osi Z w celu przemieszczenia myszki z krawędzi. |
| **Milestone 2** | Software | Stworzenie aplikacji pozwalającej na integrację pracy robota z danymi wejściowymi z klawiatury komputera (poruszanie robotem poprzez przytrzymywanie odpowiednich przycisków). |
| **Milestone 2** | Hardware | Konstrukcja robota, realizacja projektu, integracja z warstwą aplikacji sterującej. |
| **Milestone 3** | Soft + Hard | Integracja systemu przetwarzania danych z aplikacją do sterowania robota w celu automatycznego namierzania przeciwników. Finalizacja projektu, stworzenie instalatora aplikacji, przygotowanie półautomatycznej kalibracji. |

---

## Zespół projektowy
* Tomasz Nazar
* Filip Pietrzak
* Patryk Polechoński
* Hubert Czarnecki
* Karol Puczyński
* Piotr Rokita
* Łukasz Mroczek
* Antoni Sulkowski
* Andrzej Placek
* Łukasz Orluk
