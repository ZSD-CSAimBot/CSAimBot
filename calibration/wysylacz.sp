#include <sourcemod>
#include <socket>

Handle g_hSocket;
bool g_bConnected = false;

public void OnPluginStart() {
    HookEvent("bullet_impact", Event_BulletImpact);
    
    // Tworzymy gniazdo UDP
    g_hSocket = SocketCreate(SOCKET_UDP, OnSocketError);
    
    // Zamiast strzelać w ciemno, nawiązujemy "stałe" połączenie z Pythonem
    SocketConnect(g_hSocket, OnSocketConnected, OnSocketReceive, OnSocketDisconnected, "127.0.0.1", 5000);
}

// Ta funkcja odpali się automatycznie, gdy gra pomyślnie zlokalizuje adres Pythona
public void OnSocketConnected(Handle socket, any arg) {
    g_bConnected = true;
    PrintToServer("--- WYSYLACZ: Pomyslnie polaczono z Pythonem! ---");
}

public void OnSocketReceive(Handle socket, char[] receiveData, const int dataSize, any arg) {
    // Ignorujemy (Python nic do gry nie wysyła, on tylko słucha)
}

public void OnSocketDisconnected(Handle socket, any arg) {
    g_bConnected = false;
}

public void OnSocketError(Handle socket, const int errorType, const int errorNum, any arg) {
    LogError("Blad Socket: %d", errorType);
    g_bConnected = false;
}

public Action Event_BulletImpact(Event event, const char[] name, bool dontBroadcast) {
    // Jeśli z jakiegoś powodu nie jesteśmy połączeni, nie wysyłamy (omijamy błąd)
    if (!g_bConnected) {
        return Plugin_Continue; 
    }

    int client = GetClientOfUserId(event.GetInt("userid"));
    
    if (client > 0 && IsClientInGame(client)) {
        float x = event.GetFloat("x");
        float y = event.GetFloat("y");
        float z = event.GetFloat("z");
        
        char buffer[256];
        Format(buffer, sizeof(buffer), "IMPACT;%N;%.2f;%.2f;%.2f", client, x, y, z);
        
        // Używamy zwykłego SocketSend (bez IP i portu, bo to ustaliliśmy wyżej)
        SocketSend(g_hSocket, buffer); 
    }
    return Plugin_Continue;
}