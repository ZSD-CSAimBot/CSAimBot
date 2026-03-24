# Zakres funkcjonalny
- Czytanie ekranu
- Oznaczanie przeciwników
- Obliczanie drogi robota
- Ruch myszką za pomocą robota kartezjańskiego
- Strzał za pomocą przycisku
- Rozglądanie się w przypadku braku wykrycia przeciwników
- Współpraca z graczem
- Symulacja robota przez ROS i Gazebo

# Szczegółowe założenia

<h3>Hardware'owe</h3>

- Projekt będzie działać w temperaturze pokojowej w zamkniętym pomieszczeniu na jednolitej poziomej płaskiej powierzchni umożliwiającej poprawne zamontowanie robota (np. biurko) i umożliwiającej poprawne użycie klawiatury.
- Robot będzie rozmiarów umożliwiających swobodne sterowanie myszką i wygodnie sterowanie klawiaturą przez użytkownika na jednym stanowisku.
- Mysz, będzie się poruszać na materiałowej podkładce do myszy.
- Komputer i robot, będą pobierały zasilanie z sieci 230V. Dalsze etapy zasilania (np. zasilacz komputerowy), realizowane w zależności od zastosowanego sprzętu.
- Wszystkie komponenty muszą być sprawne, aby projekt działał poprawnie.
- Pozycja silników krokowych będzie odczytywana z enkoderów podłączonych w odpowiedni sposób do silników.
- Mysz użyta do projektu powinna być bezprzewodowa lub powinna mieć kabel o długości zapewniającej swobodną pracę robota.
- Sterowanie robotem będzie odbywać się WYŁĄCZNIE za pomocą klawiatury i/lub myszki oraz dedykowanych przycisków przy robocie
- Mysz musi posiadać przynajmniej 2 przyciski - lewy i prawy przycisk, reszta przycisków będzie ignorowana.
- Mysz musi korzystać z laserowego lub optycznego sensora. Nie może być to mysz kulkowa. Mysz nie może mieć znacznie wystających niestandardowych elementów.
- Przy zmianie myszki/wartości DPI na inną wykonywana będzie półautomatyczna procedura kalibracji. Robot będzie sprawdzał o ile musi się poruszyć, żeby przejść między punktami referencyjnymi na specjalnej mapie.
- Klawiatura będzie obsługiwana przez jednego użytkownika, steruje poruszaniem się postacią klawiszami WSAD
- Projekt nie będzie obsługiwać komend głosowych ani wizji maszynowej do poleceń.
- Chwytak będzie zamykany serwomechanizmem
- Mysz będzie trzymana siłą tarcia
- Mysz pod chwytakiem robota umieszcza użytkownik w miejscu do tego przeznaczonym (centrum podkładki).
- Nastawy robota będą mogły być zmienione w przypadku poluzowania się części lub wykrycia innych nieprawidłowości.
- Gracz ma do dyspozycji przycisk zatrzymania robota.
- Komunikacja PC-Mikrokontroler poprzez UART (USB) z prędkością 115200 baud
- Przyciski myszy będą naciskane solenoidami lub szybkimi serwomechanizmami.
- Mysz musi mieć klawisze (lewy i prawy) równoległe do powierzchni na której stoi robot. Nie obsługiwane będą myszy typu Logitech MX Vertical itp. 
- Akceleracja wskaźnika myszy jest wyłączona.
- Elementy robota oprócz silników, szyn, sterowników, prowadnic, śrub, zębatek, pasów itp. będą wydrukowane 3d


<h3>Software'owe</h3>

- Program komputerowy będzie działać na systemie Windows 11 Pro build >=25H2 lub równoważnym systemie Windows. Program nie będzie działać na Linuxie ani na MacOS.
- Stworzony zostanie własny dataset do wykrywania przeciwników oraz rodzaju trzymanej broni
- Program będzie działać na komputerze PC o odpowiedniej mocy obliczeniowej (min. karta graficzna RTX 3060) z monitorem - nie na laptopie. Na laptopie może nie zostać spełniony warunek czasu reakcji.
- Program będzie wykrywać modele przeciwników w grze. (Będzie odróżniał modele CT od T)
- Program będzie współpracować z CS:GO w wersji umożliwiającej dodanie botów lub graczy do gry.
- Program będzie komunikował się z robotem za pomocą połączenia przewodowego.
- Program będzie przystosowany do działania lokalnie na komputerze na którym zostanie zainstalowany.
- Ewentualny interfejs użytkownika będzie zrealizowany w języku angielskim.
- Jeśli gracz trzyma pistolet lub karabin snajperski to kompensacja odrzutu będzie wyłączona. W przeciwnym wypadku program będzie korygował odrzut konkretnych broni (AK47/M4A1).
- Podczas celowania z karabinu snajperskiego wykrywani zostaną tylko wrogowie znajdujący się w polu widzenia lunety. Włączeniem / Wyłączeniem przybliżenia steruje użytkownik z klawiatury.
- Użytkownik będzie używał praworęcznego modelu broni.
- Robot będzie strzelał pojedynczymi strzałami lub seriami w zależności od ustawienia gracza. Odrzut będzie kompensowany jedynie przy strzelaniu seriami.
- Program będzie działał z grą ustawioną na minimum 60 FPS.
- Okno wykrywania będzie miało rozmiar 1280x736
- Robot będzie miał 100% celności w cele statyczne.
- Robot będzie miał 60% celności w cele poruszające się.
- Trenowanie YOLO - na komputerze 
- Rozdzielczość 1080p
- ROS obsługiwany za pomocą Dockera i WSL2 na Windows

<h3>Związane z grą</h3>

- Program będzie działał tylko podczas rozpoczętej rundy.
- Program będzie działał na dowolnej oficjalnej mapie CS:GO
- Program będzie działał z włączoną opcją natychmiastowego usuwania ciał po zabójstwie w grze lokalnej
- W przypadku wykrycia kilku celów, program wybiera cel najbliżej aktualnej pozycji celownika
- Czas reakcji przy eDPI dobranym tak, aby robot nie musiał podnosić myszy będzie wynosił maksymalnie tyle ile czas reakcji dobrego gracza (<200ms) Czasem reakcji nazywamy czas po którym robot zaczyna kierować mysz w stronę przeciwnika od jego pojawienia się na ekranie.
- Viewmodel będzie ustawiony tak aby było go widać w obszarze przechwytywania


