[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)

# Network Programming - Assignment G01

## Anggota Kelompok

| Nama                  | NRP        | Kelas                    |
| --------------------- | ---------- | ------------------------ |
| Ahsin Khuluqil Karim  | 5025241063 | Pemrograman Jaringan - D |
| Liem, Alfred Haryanto | 5025241100 | Pemrograman Jaringan - D |

## Link Youtube (Unlisted)

Link ditaruh di bawah ini

```

```

## Penjelasan Program

### 1. Fungsi Inti Server dan Client

Sebelum membahas perbedaannya, keempat file server dan client sudah dibekali fungsi untuk berkomunikasi secara dasar:

``` py
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
    for c in list(clients):
        if c != exclude_sock:
            try:
                with client_locks[c]:
                    send_cmd(c, f"BRD|{message_str}")
            except:
                pass
```

- **send_cmd & recv_cmd**: Keduanya menggunakan _Length-Prefixed Framing_, dimana setiap kali pesan dikirimkan, program akan menyisipkan "ukuran datanya" ke dalam 4-byte _header_ di awal pesan (menggunakan `struct.pack(">I", length)`). Nanti ketika menerima, fungsi `recv_cmd` akan membaca 4 byte yang dikirimkan oleh `send_cmd`, jadi sistem tahu seberapa panjang pesan yang harus diterima.
- **Transfer File Bertahap (Chunk)**: Saat melakukan upload atau download, aplikasinya tidak membaca dan mengirim seluruh isi file sekaligus ke RAM. Kalau ukuran filenya sangat besar, RAM bisa langsung penuh. Solusinya adalah mengirim file sedikit demi sedikit (metode _chunking_) sebesar 4096 byte per loop sampai keseluruhannya selesai ditransfer.
- **Broadcast Message**: Server otomatis menyebarkan notifikasi (_server log_) ke semua _client_ yang sedang aktif kalau ada _client_ baru yang berhasil masuk (`WELCOME`), atau sebaliknya, saat ada yang terputus koneksinya.
- **Command yang Didukung**:
  - `/list`: Melihat daftar file yang tersedia untuk diunduh dari folder `server_data`.
  - `/download <nama_file>`: Mengunduh file dari server ke komputer _client_.
  - `/upload <nama_file>`: Mengirim file dari folder lokal `client_data` ke server.

### 2. Fungsi tambahan
**A. Server**
```py
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
        with client_locks.get(sock, threading.Lock()):
            send_cmd(sock, f"BRD|{res}")
        
    elif cmd == 'UPLOAD':
        filename = os.path.basename(parts[1])
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
        filename = os.path.basename(parts[1])
        filepath = os.path.join(SERVER_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            with client_locks.get(sock, threading.Lock()):
                send_cmd(sock, f"DOWNLOAD_OK|{filename}|{size}")
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk: break
                        sock.sendall(chunk)
        else:
            with client_locks.get(sock, threading.Lock()):
                send_cmd(sock, "DOWNLOAD_ERR|File not found on the server.")

    return True
```
- Server akan membaca command yang diterima dari socket. Jika tidak ada yang diterima, maka akan _disconnect_ dan return _false_ untuk memberikan tanda untuk memberhentikan loop. 
- Karena command yang diterima sudah di _encode_, maka harus dilakukan _decode_ yang akan disimpan di variabel `cmd_str`. Isi dari `cmd_str` akan dibagi dengan `"|"` agar pemrosesan berikutnya bisa terlaksana dengan lebih mudah. 
- Command yang diberikan client kemudian akan dieksekusi sesuai dengan jenis command nya. 
- `LIST`: Server akan menampilkan semua file yang ada di directory `server_data`. Cara kerjanya adalah dengan mengecek isi dari `server_data`, jika kosong maka akan menampilkan tulisan `empty`, jika terdapat file maka akan menggabungkanya kedalam sebuah string yang akan dikirim kembali ke requester.
- `UPLOAD`: Client akan mengirimkan format `UPLOAD|nama file|size` terlebih dahulu, kemudian melakukan _stream_ sebesar bytes file yang ingin diupload. Server akan membuat sebuah file untuk mencatat _chunk_ yang dikirimkan hingga 4096 bytes dalam satu waktu sampai mencapai jumlah bytes yang diinginkan. Bagian `min(40096, size - bytes_received) memastikan agar tidak terjadi _over-reading_ di bagian akhir. 
- `DOWNLOAD`: Secara simple, DOWNLOAD adalah UPLOAD yang terbalik, dimana server akan mengirimkan format `DOWNLAOD_OK|nama file|size` ke client dan melakukan streaming, dimana client yang akan menerima file tersebut (sama seperti server menerima streaming _chunk_ dari client).

*Khusus di server-thread.py*
``` py
with client_locks.get(sock, threading.Lock()):
    send_cmd(sock, f"BRD|{res}")
        
elif cmd == 'DOWNLOAD':
    filename = os.path.basename(parts[1])
    filepath = os.path.join(SERVER_DIR, filename)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        with client_locks.get(sock, threading.Lock()):
            send_cmd(sock, f"DOWNLOAD_OK|{filename}|{size}")
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    sock.sendall(chunk)
        broadcast(f"[Server info] Client {client_id} has downloaded '{filename}'")
    else:
        with client_locks.get(sock, threading.Lock()):
            send_cmd(sock, "DOWNLOAD_ERR|File not found on the server.")

if sock in client_locks:
    del client_locks[sock]
```
- Karena `server-thread.py` menggunakan metode thread, maka untuk menjaga agar tidak terjadi masalah seperti _race condition_, diperlukan _Mutual Exclusion_ dengan menggunakan variabel `client_locks`. Tujuan dari `client_locks` adalah agar tidak ada thread lain yang dapat melakukan proses di socket yang sama secara bersamaan.


### 3. Arsitektur Penanganan Client Setiap Server

**A. `server-sync.py` (Synchronous / Blocking)**
Arsitektur server yang paling dasar dan memproses hanya dengan antrean.

``` py
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_IP, SERVER_PORT))
    server.listen(5)
    print(f"[*] Sync Server running on {SERVER_IP}:{SERVER_PORT}")

    while True:
        try:
            client_sock, addr = server.accept()
            print(f"[*] Client connected: {addr}")
            clients.append(client_sock)
            
            send_cmd(client_sock, "WELCOME|0")
            broadcast(f"[Server info] Client {addr[0]}:{addr[1]} connected", exclude_sock=client_sock)
            
            while True:
                if not handle_client_message(client_sock):
                    break
        except Exception as e:
            print(f"[!] Error: {e}")
        finally:
            if 'client_sock' in locals() and client_sock in clients:
                print(f"[*] Client disconnected: {addr}")
                clients.remove(client_sock)
                broadcast(f"[Server info] Client {addr[0]}:{addr[1]} disconnected")
                client_sock.close()
```

- **Cara Kerja**: Server sync bekerja dengan melayani _client_ satu per satu. Ketika sebuah _client_ berhasil masuk, server hanya akan memfokuskan _resource_ di dalam fungsi loop _client_ tersebut (`handle_client_message`) sampai tuntas atau koneksinya diputus.
- Pada bagian awal terdapat _setup_ untuk server itu sendiri, seperti menyiapkan socket, reusable port, dan semacamnya. Di `server-sync` sendiri bisa menampung sampai dengan 5 pending connection melalui `server.listen(5)`, jika melebihi 5 antrian maka antrian ke-6 akan langsung di reject oleh server.
- Ketika mengaccept sebuah client, socket akan di _block_ sehingga client lain yang ingin terhubung harus menunggu client yang sedang terhubung untuk disconnect. 
- **Kelebihan**: Simple dan mudah dipahami karena logikanya yang linear, predictable karena hanya ada 1 _client_ yang terhubung di 1 waktu, dan juga _resource_ yang digunakan ringan karena tidak digunakan untuk thread atau proses tambahan (overhead minimal). 
- **Kekurangan**: Karena sifatnya yang menahan proses yang lain (_blocking_), kalau sewaktu-waktu ada _client_ selanjutnya yang mencoba terhubung di saat server sedang sibuk melayani _client_ pertama, _client_ baru ini harus murni mengantre dan tidak akan direspons. Jadi konsep ini sama sekali tidak pas untuk dipakai secara bersamaan oleh banyak pengguna.

**B. `server-thread.py` (Multi-Threading)**
Sistem ini dirancang untuk menyelesaikan masalah antrean lambat dari `server-sync` dengan memanfaatkan sistem _thread_.

```py
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_IP, SERVER_PORT))
    server.listen(5)
    print(f"[*] Thread Server running on {SERVER_IP}:{SERVER_PORT}")

    while True:
        client_sock, addr = server.accept()
        print(f"[*] Client connected: {addr}")
        clients.append(client_sock)
        client_locks[client_sock] = threading.Lock()
        
        send_cmd(client_sock, "WELCOME|0")
        broadcast(f"[Server info] Client {addr[0]}:{addr[1]} connected", exclude_sock=client_sock)
        
        thread = threading.Thread(target=handle_client, args=(client_sock, addr))
        thread.daemon = True
        thread.start()
```

- **Cara Kerja**: Ketika _client_ baru yang sukses terhubung (`server.accept()`), server akan langsung menyerahkan _client_ tersebut ke sebuah _thread_ baru menggunakan fungsi `threading.Thread()`. Setiap koneksi ditangani secara terpisah dan berjalan secara independen.
- `threading.Thread` akan membuat sebuah thread baru, `thread.daemon` akan membuat thread tersebut ditandai sebagai sebuah daemon (langsung mati jika main program/process exit), dan kemudian menjalankan thread itu kepada client nya. 
- **Kelebihan**: Kodenya _to-the-point_ dan bisa seketika menangani puluhan koneksi berbarengan (_concurrent_). Setiap client memiliki session yang independen sehingga tidak meganggu client lain. 
- **Kekurangan**: Sisi kurangnya, setiap penambahan _thread_ akan otomatis mengambil jatah memori (RAM) dan prosesor CPU yang lumayan. Bayangkan bila mendadak ada ribuan perangkat yang masuk, sistem operasi server bisa seketika luar biasa terbebani (_overhead_). Selain itu, penggunaan thread juga menambah kompleksitas kode karena diperlukan pelindung berupa `threading.Lock()` untuk mencegah race condition saat beberapa thread mencoba menulis ke socket yang sama secara bersamaan."

**C. `server-select.py` (I/O Multiplexing dengan `select()`)**
Sistem server asinkron (_non-blocking_) yang terbukti cukup dioperasikan lewat landasan satu _thread_ saja (_single-thread_).

```py
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

```

- **Cara Kerja**: Server dimulai dengan mengisi socket pada `input_sockets`.
- `Select Loop`: Server akan berjalan dalam loop, dimana setiap loop akan mengecek _client_ yang memiliki _data_. Server kemudian akan menandai _client_ yang aktif dan meletakkan socket baru pada `input_sockets` dan _client_ agar client bisa berkomunikasi dengan server. 
- Jika select menandai server socket yang aktif, artinya ada client baru yang ingin terhubung, server akan accept() dan menambahkan socket client baru ke input_sockets. Jika yang aktif adalah client socket, maka akan memanggil `handle_client_message`. 
- Jika return _false_, maka menghapus socket yang digunakan untuk berkomunikasi pada `input_sockets` dan _client_
- **Kelebihan**: Jauh menghemat _resource_ pemrosesan CPU dan RAM kalau dibandingkan dengan menggunakan metode `threading` biasa. 
- **Kelemahan**: Fitur pemantauan primitif dari modul `select()` OS itu pada umumnya memiliki limit yang hanya bisa menampung serta memantau maksimal 1024 objek sekaligus. Selain itu, jika jumlah pendaftar koneksinya bertambah secar drastis, program akan melambat karena instruksi _select_ memaksa pengecekan menyisir semua daftar dari ujung ke ujung secara berurutan. Karena sifatnya yang _single threaded_, jika 1 fungsi `handle_client_message` memiliki proses yang lama, proses lain nya akan ikut tertahan. 

**D. `server-poll.py` (I/O Multiplexing dengan `poll()`)**
Inovasi lanjutan dari metode _multiplexing_ di atas guna menambal tuntas semua problem kelemahan antrean `server-select`.

```py
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_IP, SERVER_PORT))
    server.listen(5)
    print(f"[*] Poll Server running on {SERVER_IP}:{SERVER_PORT}")

    poll_obj = select.poll()
    poll_obj.register(server.fileno(), select.POLLIN)
    
    fd_map = {server.fileno(): server}
    
    while True:
        for fd, event in poll_obj.poll():
            notified_socket = fd_map.get(fd)
            if not notified_socket:
                continue
            
            if notified_socket == server:
                client_sock, addr = server.accept()
                print(f"[*] Client connected: {addr}")
                poll_obj.register(client_sock, select.POLLIN)
                fd_map[client_sock.fileno()] = client_sock
                clients.append(client_sock)
                
                send_cmd(client_sock, "WELCOME|0")
                broadcast(f"[Server info] Client {addr[0]}:{addr[1]} connected", exclude_sock=client_sock)
                
            elif event & select.POLLIN:
                try:
                    if not handle_client_message(notified_socket):
                        addr = notified_socket.getpeername()
                        print(f"[*] Client disconnected: {addr}")
                        poll_obj.unregister(notified_socket)
                        del fd_map[fd]
                        if notified_socket in clients:
                            clients.remove(notified_socket)
                        broadcast(f"[Server info] Client {addr[0]}:{addr[1]} disconnected")
                        notified_socket.close()
                except Exception as e:
                    print(f"[!] Error from client: {e}")
                    poll_obj.unregister(notified_socket)
                    del fd_map[fd]
                    if notified_socket in clients:
                        clients.remove(notified_socket)
                    notified_socket.close()
            
            elif event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                print(f"[*] Client disconnected (HUP/ERR): {notified_socket.getpeername()}")
                poll_obj.unregister(notified_socket)
                del fd_map[fd]
                if notified_socket in clients:
                    clients.remove(notified_socket)
                notified_socket.close()
```

- **Cara Kerja**: _Client_ yang terhubung pada socket tertentu, akan di pasangkan dengan _fd numbers_ yang sudah di set oleh server. 
- `Poll` memiliki cara bekerja yang similiar dengan `select`, yang membedakan adalah `Poll` menggunakan _hash map_ `(fd numbers)` untuk menyimpan pasangan `fd numbers` dan socket. 
- `Poll` akan bekerja dalam sebuah loop, untuk mengecek socket mana yang aktif, kemudian melakukan fetch kepada `fd numbers` untuk mendapatkan socket yang aktif untuk menghubungkan _client_ dengan server untuk berkomunikasi. Terdapat juga _event model_ setiap kali fetching `fd numbers`. 
- **Kelebihan**: Meskipun menggunakan metode/workflow yang mirip dengan `select`, namun `Poll` memiliki kelebihan seperti tidak adanya batasan pada 1024 objek untuk pengecekan, dan punya error handling yang lebih spesifik. Selain itu, karena terdapat _event model_, server jadi tahu event nya secara eksplisit, dan tidak perlu melakukan _rebuilding_ sepert `select` karena sudah ada `fd_set`.
- **Kekurangan**: Hanya bisa dijalankan di linux dan tidak cross platform (tidak bisa digunakan di windows). Karena menggunakan fd_set (hashmap), kompleksitas kode bertambah, serta masih berjalan secara sequential dengan O(n) scanning (tetap melakukan scan satu per satu).

### 4. Penjelasan `client.py`
Sejenis alat utilitas baris antarmuka perintah CLI (_Command Line Interface_) utama guna menghubungkan user berkirim terima parameter data ke keempat server di atas.

```py
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
                    print("[!] Invalid format. Use: /upload <filename>")
                    continue
                filename = parts[1]
                filepath = os.path.join(CLIENT_DIR, filename)
                if not os.path.exists(filepath):
                    print(f"[!] File '{filename}' not found in local folder '{CLIENT_DIR}'")
                    continue
                
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
```

- **Cara Kerja**: Client memiliki fungsi `main` yang berfokus untuk mengirim command ke server, misalnya `LIST` untuk mengirimkan command yang dapat digunakan untuk melihat daftar file yang ada di `server_data`, `DOWNLOAD` untuk meminta ke server file yang ingin di download, dan `UPLOAD` untuk memberitahu server kita ingin melakukan upload. 
- Jika terdapat _command_ yang diberikan dari server maka akan diparsing dengan separator `"|"`. 
- Karena client hanya akan menerima download dari server, maka di function `handle_messages` terdapat handling untuk menerima file dari server (download) dan juga melakukan handle terhadap broadcast.
- Terdapat kondisi yang membedakan yakni `BRD` atau broadcast, dimana client akan menerima _message_ notifikasi dari server bila client lain melakukan download/upload. 
- `DOWNLOAD`: sama seperti pada file _server_, dimana client akan menerima format `DOWNLOAD_OK|nama file|size`, kemudian menerima stream _chunk_ dari server, dan menuliskannya pada file di sisi client.
- `DOWNLOAD_ERR`: merupakan error handling bila file yang ingin di download tidak ada di sisi server. 
- Bagian terakhir merupakan error handling jika terjadi problem di network atau semacamnya (code block tersebut akan melakukan print errornya apa dan melakukan exit program). 

## Screenshot Hasil
