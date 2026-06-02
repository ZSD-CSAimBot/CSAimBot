#!/bin/bash

# Zatrzymaj skrypt w przypadku błędu
set -e

# Pobranie bezwzględnej ścieżki do folderu "installer-linux" (tam gdzie jest ten skrypt)
SCRIPT_DIR=$(dirname "$(realpath "$0")")

# Ścieżki robocze bazujące na lokalizacji skryptu
STAGING_DIR="$SCRIPT_DIR/CsAimBot-Package"
DIST_DIR="$SCRIPT_DIR/dist/CsAimBot"
OUTPUT_DIR="$SCRIPT_DIR/Output"
OUTPUT_INSTALLER="$OUTPUT_DIR/CsAimBot-Installer-x64-v2.run"

echo -e "\033[0;36m=== AUTOMATYCZNE BUDOWANIE INSTALATORA LINUX ===\033[0m"

# 1. Sprawdzenie wymagań makeself
if ! command -v makeself &> /dev/null; then
    echo "Narzędzie 'makeself' nie jest zainstalowane. Instalowanie..."
    sudo apt-get update && sudo apt-get install -y makeself
fi

# 2. Przygotowanie folderów
echo "Przygotowywanie folderów roboczych..."
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
mkdir -p "$OUTPUT_DIR"

# 3. Kopiowanie skompilowanej aplikacji z PyInstallera (razem z gazebo_sim.tar w środku)
if [ -d "$DIST_DIR" ]; then
    echo "Kopiowanie plików binarnej aplikacji z dist..."
    cp -r "$DIST_DIR" "$STAGING_DIR/CsAimBot"
else
    echo -e "\033[0;31mBŁĄD: Nie znaleziono folderu $DIST_DIR! Uruchom najpierw komendę PyInstallera.\033[0m"
    exit 1
fi

# 4. GENEROWANIE SKRYPTU INSTALACYJNEGO
echo "Automatyczne generowanie wewnętrznego skryptu instalacyjnego..."
cat << 'EOF' > "$STAGING_DIR/install.sh"
#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== Instalator CsAimBot dla Linuxa ===${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}BŁĄD: Instalator wymaga uprawnień administratora!${NC}"
  echo -e "${YELLOW}Uruchom ponownie komendą: sudo ./CsAimBot-Installer-x64-v2.run${NC}"
  exit 1
fi

REAL_USER=${SUDO_USER:-$USER}

echo -e "\n${YELLOW}[1/4] Sprawdzanie i instalacja Dockera...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${CYAN}Instalowanie Dockera...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $REAL_USER
    rm get-docker.sh
else
    echo -e "${GREEN}Docker jest już zainstalowany: $(docker --version)${NC}"
fi

echo -e "\n${YELLOW}[2/4] Sprawdzanie NVIDIA Container Toolkit...${NC}"
if ! command -v nvidia-ctk &> /dev/null; then
    echo -e "${CYAN}Instalowanie NVIDIA Container Toolkit...${NC}"
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg --yes
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
    apt-get update && apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
else
    echo -e "${GREEN}NVIDIA Container Toolkit jest już zainstalowany.${NC}"
fi

echo -e "\n${YELLOW}[3/4] Sprawdzanie natywnego CUDA Toolkit 12.8...${NC}"
if command -v nvcc &> /dev/null && nvcc --version | grep -q "12.8"; then
    echo -e "${GREEN}CUDA Toolkit 12.8 jest już zainstalowany.${NC}"
else
    echo -e "${CYAN}Instalowanie natywnego CUDA Toolkit 12.8 (Repozytorium Ubuntu)...${NC}"
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb -O /tmp/cuda-keyring.deb
    dpkg -i /tmp/cuda-keyring.deb
    apt-get update && apt-get install -y cuda-toolkit-12-8
    rm /tmp/cuda-keyring.deb
fi

echo -e "\n${YELLOW}[4/4] Konfiguracja reguł Udev dla urządzeń wejściowych...${NC}"
cat <<UDEV > /etc/udev/rules.d/99-csaimbot.rules
KERNEL=="event*", SUBSYSTEM=="input", MODE="0666"
KERNEL=="uinput", SUBSYSTEM=="misc", MODE="0666", OPTIONS+="static_node=uinput"
UDEV
udevadm control --reload-rules && udevadm trigger
echo -e "${GREEN}Reguły Udev zostały zaktualizowane.${NC}"

echo -e "\n${CYAN}=== Kopiowanie plików aplikacji do /opt/CsAimBot ===${NC}"
INSTALL_DIR="/opt/CsAimBot"
mkdir -p "$INSTALL_DIR"

if [ -d "./CsAimBot" ]; then
    cp -r ./CsAimBot/* "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/CsAimBot"
    echo -e "${GREEN}Pliki zostały poprawnie zainstalowane.${NC}"
else
    echo -e "${RED}BŁĄD KRYTYCZNY: Nie znaleziono plików aplikacji w archiwum!${NC}"
    exit 1
fi

cat <<DESKTOP > /usr/share/applications/csaimbot.desktop
[Desktop Entry]
Version=2.0
Name=CsAimBot
Comment=Automatyczny system detekcji
Exec=$INSTALL_DIR/CsAimBot
Path=$INSTALL_DIR
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Game;Utility;
DESKTOP
chmod +x /usr/share/applications/csaimbot.desktop

echo -e "\n${YELLOW}=== Operacje poinstalacyjne ===${NC}"

# Skrypt automatycznie szuka gazebo_sim.tar w skopiowanych plikach (odporność na ukrytą strukturę PyInstallera)
GAZEBO_TAR=$(find "$INSTALL_DIR" -name "gazebo_sim.tar" | head -n 1)

if [ -n "$GAZEBO_TAR" ]; then
    echo -e "${CYAN}Wczytywanie obrazu Gazebo do Dockera ($GAZEBO_TAR)...${NC}"
    sudo -u $REAL_USER docker load -i "$GAZEBO_TAR"
else
    echo -e "${RED}OSTRZEŻENIE: Nie znaleziono pliku gazebo_sim.tar! Pominięto konfigurację symulatora.${NC}"
fi

echo -e "${CYAN}Eksportowanie modelu YOLO do formatu TensorRT (może to potrwać chwilę)...${NC}"
sudo -u $REAL_USER "$INSTALL_DIR/CsAimBot" --export-only

echo -e "\n${GREEN}==========================================${NC}"
echo -e "${GREEN}  INSTALACJA ZAKOŃCZONA SUKCESEM!  ${NC}"
echo -e "${GREEN}==========================================${NC}"
echo -e "Aplikacja jest dostępna w menu systemowym lub pod ścieżką: /opt/CsAimBot/CsAimBot"
echo -e "${RED}Zaleca się restart komputera w celu pełnego zaaplikowania uprawnień Dockera.${NC}"
EOF

# Nadanie uprawnień wykonywania
chmod +x "$STAGING_DIR/install.sh"

echo "Generowanie finalnego pliku instalatora .run..."
TMPDIR="$SCRIPT_DIR" makeself "$STAGING_DIR" "$OUTPUT_INSTALLER" "CsAimBot System Installer" ./install.sh

# 6. Sprzątanie
echo "Czyszczenie środowiska roboczego..."
rm -rf "$STAGING_DIR"

echo -e "\033[0;32m=== GOTOWE! Paczka instalacyjna czeka w: $OUTPUT_INSTALLER ===\033[0m"