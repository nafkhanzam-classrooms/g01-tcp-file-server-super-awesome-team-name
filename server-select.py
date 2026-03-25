import socket
import struct
import os
import select

SERVER_IP = '127.0.0.1'
SERVER_PORT = 8080
SERVER_DIR = 'server_data'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)

clients = []

def send_cmd(sock, cmd_str):
    cmd_bytes = cmd_str.encode('utf-8')
    header = struct.pack(">I", len(cmd_bytes))
    sock.sendall(header + cmd_bytes)

def recv_all(sock, num_bytes):
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)

def recv_cmd(sock):
    header = recv_all(sock, 4)
    if not header:
        return None
    length = struct.unpack(">I", header)[0]
    return recv_all(sock, length)

def broadcast(message_str, exclude_sock=None):
    for c in clients:
        if c != exclude_sock:
            try:
                send_cmd(c, f"BRD|{message_str}")
            except:
                pass

def handle_client_message(sock):
    cmd_bytes = recv_cmd(sock)
    if not cmd_bytes:
        return False
    
    cmd_str = cmd_bytes.decode('utf-8')
    parts = cmd_str.split('|')
    cmd = parts[0]

    addr = sock.getpeername()
    client_id = f"{addr[0]}:{addr[1]}"
    
    if cmd in ['UPLOAD'] and len(parts) > 1:
        print(f"[*] ({client_id}) executed command: /upload (file: {os.path.basename(parts[1])})")
    elif cmd in ['DOWNLOAD'] and len(parts) > 1:
        print(f"[*] ({client_id}) executed command: /download (file: {os.path.basename(parts[1])})")
    elif cmd in ['LIST']:
        print(f"[*] ({client_id}) executed command: /list")

    if cmd == 'LIST':
        files = os.listdir(SERVER_DIR)
        res = f"--- Server File List ({len(files)} file) ---\n"
        if len(files) == 0:
            res += "(Empty)"
        else:
            res += "\n".join(files)
        res += "\n-----------------------------------"
        send_cmd(sock, f"BRD|{res}")
        
    elif cmd == 'UPLOAD':
        filename = parts[1]
        size = int(parts[2])
        filepath = os.path.join(SERVER_DIR, filename)
        with open(filepath, 'wb') as f:
            bytes_received = 0
            while bytes_received < size:
                chunk_size = min(4096, size - bytes_received)
                chunk = sock.recv(chunk_size)
                if not chunk: break
                f.write(chunk)
                bytes_received += len(chunk)
        broadcast(f"[Server info] Client {client_id} has uploaded '{filename}'")
        
    elif cmd == 'DOWNLOAD':
        filename = parts[1]
        filepath = os.path.join(SERVER_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            send_cmd(sock, f"DOWNLOAD_OK|{filename}|{size}")
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    sock.sendall(chunk)
        else:
            send_cmd(sock, "DOWNLOAD_ERR|File not found on the server.")

    return True

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_IP, SERVER_PORT))
    server.listen(5)
    print(f"[*] Select Server running on {SERVER_IP}:{SERVER_PORT}")

    input_sockets = [server]
    
    while True:
        read_ready, _, _ = select.select(input_sockets, [], [])
        
        for notified_socket in read_ready:
            if notified_socket == server:
                client_sock, addr = server.accept()
                print(f"[*] Client connected: {addr}")
                input_sockets.append(client_sock)
                clients.append(client_sock)
                
                send_cmd(client_sock, "WELCOME|0")
                broadcast(f"[Server info] Client {addr[0]}:{addr[1]} connected", exclude_sock=client_sock)
            else:
                try:
                    if not handle_client_message(notified_socket):
                        addr = notified_socket.getpeername()
                        print(f"[*] Client disconnected: {addr}")
                        if notified_socket in input_sockets: input_sockets.remove(notified_socket)
                        if notified_socket in clients: clients.remove(notified_socket)
                        broadcast(f"[Server info] Client {addr[0]}:{addr[1]} disconnected")
                        notified_socket.close()
                except Exception as e:
                    print(f"[!] Error from client: {e}")
                    if notified_socket in input_sockets: input_sockets.remove(notified_socket)
                    if notified_socket in clients: clients.remove(notified_socket)
                    notified_socket.close()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
