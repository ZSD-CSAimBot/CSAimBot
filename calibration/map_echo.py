import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5000))
print("Oczekiwanie na pociski")

while True:
    data, addr = sock.recvfrom(1024)
    msg = data.decode('utf-8').strip('\x00')

    parts = msg.split(';')

    if parts[0] == "IMPACT":
        player = parts[1]
        x, y, z = parts[2], parts[3], parts[4]

        print(f"Strzelec: {player} | Pozycja uderzenia: X={x} Y={y} Z={z}")