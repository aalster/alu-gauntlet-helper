from PyQt6.QtNetwork import QLocalSocket, QLocalServer


APP_ID = "alu_helper_instance"

def single_instance_lock(show_window):
    socket = QLocalSocket()
    socket.connectToServer(APP_ID)

    if socket.waitForConnected(100):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(100)
        socket.disconnectFromServer()
        return None

    server = QLocalServer()
    try:
        QLocalServer.removeServer(APP_ID)
    except Exception:
        pass
    server.listen(APP_ID)

    def on_new_connection():
        client = server.nextPendingConnection()
        if client and client.waitForReadyRead(500):
            message = client.readAll().data().decode()
            if message == "show":
                show_window()
        client.disconnectFromServer()

    server.newConnection.connect(on_new_connection) # type: ignore
    return server
