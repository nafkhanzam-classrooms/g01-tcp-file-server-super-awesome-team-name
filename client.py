import socket
import struct
import threading
import os
import sys

SERVER_IP = '127.0.0.1'
SERVER_PORT = 8080
CLIENT_DIR = 'client_data'

if not os.path.exists(CLIENT_DIR):
    os.makedirs(CLIENT_DIR)

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

def receive_messages(sock):
    while True:
        try:
            cmd_bytes = recv_cmd(sock)
            if not cmd_bytes:
                print("[!] Disconnected from server.")
                os._exit(0)
            
            cmd_str = cmd_bytes.decode('utf-8')
            parts = cmd_str.split('|')
            cmd = parts[0]
            
            if cmd == 'BRD':
                print(cmd_str[4:])
            
            elif cmd == 'DOWNLOAD_OK':
                filename = os.path.basename(parts[1])
                size = int(parts[2])
                filepath = os.path.join(CLIENT_DIR, filename)
                print(f"[*] Downloading {filename} ({size} bytes)...")
                
                with open(filepath, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < size:
                        chunk_size = min(4096, size - bytes_received)
                        chunk = sock.recv(chunk_size)
                        if not chunk: break
                        f.write(chunk)
                        bytes_received += len(chunk)
                print(f"[*] Successfully downloaded to folder {CLIENT_DIR}")
            
            elif cmd == 'DOWNLOAD_ERR':
                print(f"[!] Error: {cmd_str[13:]}")
                
        except Exception as e:
            print(f"[!] Connection error: {e}")
            os._exit(0)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((SERVER_IP, SERVER_PORT))
        print(f"[*] Connecting to server {SERVER_IP}:{SERVER_PORT}...")
        
        cmd_bytes = recv_cmd(sock)
        if not cmd_bytes:
            print("[!] Connection rejected by server.")
            return
            
        cmd_str = cmd_bytes.decode('utf-8')
        parts = cmd_str.split('|')
        if parts[0] == 'WELCOME':
            print(f"[*] Connected to server {SERVER_IP}:{SERVER_PORT}")
        else:
            print("[!] Unexpected response from server.")
            return
    except Exception as e:
        print(f"[!] Failed to connect: {e}")
        return

    recv_thread = threading.Thread(target=receive_messages, args=(sock,))
    recv_thread.daemon = True
    recv_thread.start()

    print("[Commands] /list | /upload <file> | /download <file>")

    while True:
        try:
            user_input = input()
            if not user_input:
                continue

            if user_input.startswith('/list'):
                send_cmd(sock, "LIST|0")
            
            elif user_input.startswith('/upload'):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("[!] Invalid format. Use: /upload <filepath>")
                    continue
                filepath = parts[1]
                if not os.path.exists(filepath):
                    print(f"[!] File '{filepath}' not found.")
                    continue
                
                filename = os.path.basename(filepath)
                size = os.path.getsize(filepath)
                send_cmd(sock, f"UPLOAD|{filename}|{size}")
                print(f"[*] Uploading {filename} ({size} bytes)...")
                
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk: break
                        sock.sendall(chunk)
                print(f"[*] Finished uploading {filename}")

            elif user_input.startswith('/download'):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("[!] Invalid format. Use: /download <filename>")
                    continue
                filename = parts[1]
                send_cmd(sock, f"DOWNLOAD|{filename}")

            else:
                print(f"[!] Unknown command: {user_input}")

        except KeyboardInterrupt:
            print("\n[*] Exiting...")
            sock.close()
            break
        except Exception as e:
            print(f"[!] Input error: {e}")
            sock.close()
            break

if __name__ == '__main__':
    main()
