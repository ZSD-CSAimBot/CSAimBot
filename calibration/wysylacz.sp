#include <sourcemod>
#include <socket>

Handle g_hSocket;
bool g_bConnected = false;

public void OnPluginStart() {
    HookEvent("bullet_impact", Event_BulletImpact);
    
    // Tworzymy gniazdo UDP
    g_hSocket = SocketCreate(SOCKET_UDP, OnSocketError);
    
    // stałe połączenie z pythonem
    SocketConnect(g_hSocket, OnSocketConnected, OnSocketReceive, OnSocketDisconnected, "127.0.0.1", 5000);
}

public void OnSocketConnected(Handle socket, any arg) {
    g_bConnected = true;
    PrintToServer("Połączona z Pythonem");
}

public void OnSocketReceive(Handle socket, char[] receiveData, const int dataSize, any arg) {
    // Ignorujemy sygnały od pythona
}

public void OnSocketDisconnected(Handle socket, any arg) {
    g_bConnected = false;
}

public void OnSocketError(Handle socket, const int errorType, const int errorNum, any arg) {
    LogError("Blad Socket: %d", errorType);
    g_bConnected = false;
}

public Action Event_BulletImpact(Event event, const char[] name, bool dontBroadcast) {
    // Jeśli nie jesteśmy połączeni, nie wysyłamy
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
        
        SocketSend(g_hSocket, buffer); 
    }
    return Plugin_Continue;
}
