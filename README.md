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

Sebelum membahas perbedaannya, keempat server ini dan client sudah dibekali fungsi komunikasi dasar yang sama rata:

- **`send_cmd` & `recv_cmd`**: Menggunakan trik _Length-Prefixed Framing_. Intinya, setiap kali mengirim pesan, program akan menyisipkan info "ukuran datanya" ke dalam 4-byte _header_ di awal pesan (pakai `struct.pack(">I", length)`). Nanti saat menerima, fungsi `recv_cmd` akan membaca 4 byte ini terlebih dahulu, jadi sistem tahu persis seberapa banyak sisa pesan yang harus ditunggu sampai selesai.
- **Transfer File Bertahap (Chunk)**: Saat melakukan _upload_ atau _download_, aplikasinya tidak membaca dan mengirim seluruh isi file sekaligus ke RAM. Kalau ukuran filenya sangat besar, RAM bisa langsung penuh. Solusinya, file dikirim sedikit demi sedikit (_chunking_) sebesar 4096 byte per perulangan sampai keseluruhannya tuntas ditransfer.
- **Broadcast Pesan (Notifikasi)**: Server otomatis menyebarkan notifikasi informasi (_server log_) ke semua _client_ yang sedang aktif kalau ada _client_ baru yang berhasil masuk (`WELCOME`), atau sebaliknya, saat ada yang terputus koneksinya.
- **Perintah yang Didukung**:
  - `/list`: Melihat daftar file yang sedia untuk diunduh dari folder `server_data`.
  - `/download <nama_file>`: Mengunduh file dari server masuk ke komputer _client_.
  - `/upload <nama_file>`: Mengirim file dari folder lokal `client_data` menuju server.

### 2. Arsitektur Penanganan Client Setiap Server

**A. `server-sync.py` (Synchronous / Blocking)**
Arsitektur server yang paling dasar dan memproses hanya dengan antrean.

- **Cara Kerja**: Server ini benar-benar melayani _client_ satu per satu. Saat sebuah _client_ sukses masuk, server hanya akan memfokuskan sumber dayanya di dalam fungsi perulangan _client_ tersebut (`handle_client_message`) sampai tuntas atau koneksinya diputus sendiri.
- **Kelemahan Utama**: Karena sifatnya yang menahan proses yang lain (_blocking_), kalau sewaktu-waktu ada _client_ selanjutnya yang mencoba terhubung di saat server sedang sibuk melayani _client_ pertama, _client_ baru ini harus murni mengantre dan tidak akan direspons. Jadi konsep ini sama sekali tidak pas untuk dipakai secara bersamaan oleh banyak pengguna.

**B. `server-thread.py` (Multi-Threading)**
Sistem ini dirancang untuk menyelesaikan masalah antrean lambat dari `server-sync` dengan memanfaatkan sistem _thread_.

- **Cara Kerja**: Kalau ada _client_ baru yang sukses terhubung (`server.accept()`), utas program utamanya akan langsung menyerahkan tugas tersebut ke sebuah pelayan _thread_ baru memakai fungsi `threading.Thread()`. Hasilnya, setiap koneksi ditangani secara terpisah dan berjalan secara independen.
- **Kelebihan & Kekurangan**: Kodenya cukup _to-the-point_ dan bisa seketika menangani puluhan koneksi berbarengan (_concurrent_). Sisi kurangnya, setiap penambahan _thread_ akan otomatis mengambil jatah memori (RAM) dan prosesor CPU yang lumayan. Bayangkan bila mendadak ada ribuan perangkat yang masuk, sistem operasi server bisa seketika luar biasa terbebani (_overhead_). Pada aplikasinya metode ini juga ditambah _guard_ pelindung berupa `threading.Lock()` agar memori tidak bertabrakan (_race condition_) waktu mengirim pesan _broadcast_ secara serempak.

**C. `server-select.py` (I/O Multiplexing dengan `select()`)**
Sistem server asinkron (_non-blocking_) yang terbukti cukup dioperasikan lewat landasan satu _thread_ saja (_single-thread_).

- **Cara Kerja**: Sangat menguntungkan diri dari mekanisme fungsi bawaan sistem operasi bernama `select.select()`. Semua soket _client_ dikumpulkan masuk ke dalam daftar variabel pantau referensi (`input_sockets`). Fungsi _select_ ini lantas akan membuat program berhenti sejenak secara pasif, lalu kemudian berjalan lagi hanya ketika kebetulan ada dari daftar referensi konektornya tersebut yang memang sudah punya data masuk siap diproses datanya (`read_ready`).
- **Kelebihan & Kekurangan**: Bakal jauh lebih menghemat sumber daya pemrosesan CPU dan RAM kalau disandingkan pakai metode `threading` biasa. Kelemahannya, fitur pemantauan primitif dari modul `select()` OS itu pada umumnya sudah ditahan limit cuma bisa menampung serta memantau maksimal 1024 objek paralel. Selain itu, kalau jumlah pendaftar koneksinya membesar drastis, programnya akan berangsur sangat lamban lantaran instruksi _select_ memaksa pengecekan menyisir semua daftar dari nol ujung ke ujung secara berurutan.

**D. `server-poll.py` (I/O Multiplexing dengan `poll()`)**
Inovasi lanjutan dari metode _multiplexing_ di atas guna menambal tuntas semua problem kelemahan antrean `server-select`.

- **Cara Kerja**: Arsitektur operasinya memanfaatkan _system-call_ berbasis pemantauan tanggap kejadian (_event-driven_) `select.poll()`. Berbeda dengan pendaftaran variabel array konvensional, modul pintar OS ini akan meregistrasi tanda indikator parameter yang jauh lebih spesifik ke tiap titik menggunakan `poll_obj.register()`. Parameter pantauan ini bisa meliputi filter pemberitahuan paket datang (`POLLIN`) sampai khusus mendeteksi jika saluran internet _client_ terputus error darurat dari dalam sirkuit jaringannya (`POLLHUP` & `POLLERR`).
- **Kelebihan & Kekurangan**: Performanya dijamin super kencang dalam mengefisiensikan durasi penantian latensi antar interaksi paralel yang besar. Karena keunggulan instrumen detektornya ini murni hanya merespons dan me-_waking up_ OS kalau ada aktivitas konkret saja, algoritma skrip berhasil sukses melewati batasan kaku limit 1024 titik koneksi standar. Berkat poin kecepatan tanpa ada limit soket inilah menjadikannya lazim dianut sebagai standar rancang bangun awal sebuah server bertenaga tinggi untuk sistem korporasi di lingkungan _UNIX/Linux_.

### 3. Penjelasan `client.py`

Sejenis alat utilitas baris antarmuka perintah CLI (_Command Line Interface_) utama guna menghubungkan user berkirim terima parameter data ke keempat server di atas.

- **Menggunakan Background Thread (_Daemon_)**: Memang menjadi hal lumrah apabila pemanggilan fungsi inputan teks `input()` akan statis memberhentikan (_freeze_) keseluruhan jalannya skrip selama ia belum kunjung ditekan _Enter_. Buat mengatasi problem penyumbatan responsi notifikasi karena menunggu masukan di konsol ini, _client_ diprogram memiliki rute proses cabangan ekstra kecil di balik layarnya yang berperan selaku _daemon_ bernama `receive_messages(sock)`.
- **Cara Layanannya**: Perantara asinkron ini akan dengan rajin memosisikan siaga fokus demi menangkapi berbagai arus info server atau kiriman chat tanpa terhambat apakah _user_ yang tengah menggunakan sedang mengetik instruksinya di menu. Alhasil kolom ruang interaksi terminal tidak pernah memblokir jalannya notifikasi dan masih aman sambil mengetik instruksi baru. Proses _download_ juga otomatis disimpan di sub lokasi ruang folder komputer yakni `client_data`.

## Screenshot Hasil
