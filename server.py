import socket
import threading
import json
import os
import re
import random
import logging
from datetime import datetime, timedelta

# Setup Logging ke File server.log
logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - [SERVER_LOG] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Konfigurasi Jaringan Server
HOST = '127.0.0.1'
PORT = 7002
DB_FILE = 'database.json'

db_lock = threading.Lock()

def load_database():
    """Memuat data dari file JSON saat server pertama kali menyala"""
    with db_lock:
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r') as f:
                    data = json.load(f)
                
                # --- LOGIKA RETENTION: Hapus chat yang usianya > 7 hari ---
                limit_date = datetime.now() - timedelta(days=7)
                cleaned_rooms = {}
                
                for room_name, chat_history in data.get("rooms", {}).items():
                    valid_chats = []
                    for chat in chat_history:
                        # Cek timestamp tiap chat
                        chat_time = datetime.strptime(chat['timestamp'], '%Y-%m-%d %H:%M:%S')
                        if chat_time > limit_date:
                            valid_chats.append(chat)
                    cleaned_rooms[room_name] = valid_chats
                
                # Kembalikan struktur data yang sudah bersih dari chat kadaluwarsa
                return {"rooms": cleaned_rooms}
            except Exception as e:
                print(f"[DB ERROR] Gagal membaca database, membuat ulang. Error: {e}")
                
        # Jika file belum ada, buat struktur default dengan Lobby kosongan
        return {"rooms": {"Lobby": []}}

def save_database(data_to_save):
    """Menyimpan data terupdate ke file JSON secara permanen"""
    with db_lock:
        try:
            with open(DB_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            print(f"[DB ERROR] Gagal menyimpan ke file JSON: {e}")

db_data = load_database()

persistent_rooms_data = db_data["rooms"]

rooms_sockets = {}
for room_name in persistent_rooms_data.keys():
    rooms_sockets[room_name] = []

clients = {}

# Daftar Kata Acak untuk Generator Nama Samaran
FIRST = ["Pejuang", "Kucing", "Kakak", "Bocah", "Maba", "Mahasiswa"]
SECOND = ["Informatika", "Progjar", "Cantik", "Ngoding", "StresFP", "Penasaran"]

def generate_alias():
    while True:
        alias = f"{random.choice(FIRST)}_{random.choice(SECOND)}_{random.randint(10,99)}"
        # Pastikan alias belum dipakai pengguna lain yang online
        if all(info["alias"] != alias for info in clients.values()):
            return alias

def broadcast_to_room(room_name, sender_socket, message_dict):
    packet = json.dumps(message_dict).encode('utf-8')
    for client_socket in rooms_sockets.get(room_name, []):
        if client_socket != sender_socket:
            try:
                client_socket.sendall(packet)
            except:
                handle_disconnect(client_socket)

def handle_disconnect(client_socket):
    if client_socket in clients:
        user_info = clients[client_socket]
        alias = user_info["alias"]
        nrp = user_info["nrp"]
        room = user_info["current_room"]
        
        # Hapus dari room
        if room in rooms_sockets and client_socket in rooms_sockets[room]:
            rooms_sockets[room].remove(client_socket)
            
        # Peringatan ke anggota room lain
        exit_notification = {
            "status": "info",
            "sender_alias": "SISTEM",
            "timestamp": "INFO",
            "message": f"Pengguna [{alias}] telah keluar dari forum."
        }
        broadcast_to_room(room, client_socket, exit_notification)
        
        # Hapus dari database user aktif
        del clients[client_socket]
        client_socket.close()
        
        log_msg = f"NRP {nrp} ({alias}) terputus dari jaringan."
        print(f"[DISCONNECT] {log_msg}")
        logging.info(log_msg)

def handle_client(client_socket):
    # Tahap 1: Autentikasi Login (Wajib NRP Valid)
    authenticated = False
    nrp = ""
    alias = ""
    
    while not authenticated:
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                client_socket.close()
                return
            
            packet = json.loads(data)
            if packet.get("command") == "login":
                input_nrp = packet.get("payload", "")
                # Regex mencocokkan format 10 digit angka NRP ITS
                if re.match(r"^\d{10}$", input_nrp):
                    # Cek apakah NRP ini sudah login sebelumnya (mencegah duplicate login)
                    if any(info["nrp"] == input_nrp for info in clients.values()):
                        response = {"status": "error", "message": "NRP ini sudah login dari perangkat lain!"}
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                        continue
                    
                    nrp = input_nrp
                    alias = generate_alias()
                    authenticated = True
                    
                    # Daftarkan ke state server
                    clients[client_socket] = {
                        "nrp": nrp,
                        "alias": alias,
                        "current_room": "Lobby"
                    }
                    rooms_sockets["Lobby"].append(client_socket)
                    
                    # Kirim sukses login beserta nama samaran yang didapatkan
                    response = {
                        "status": "success",
                        "sender_alias": "SISTEM",
                        "message": f"Selamat datang! Identitas asli Anda disamarkan. Anda masuk sebagai: {alias}"
                    }
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
                    log_msg = f"NRP {nrp} sukses login menggunakan identitas samaran {alias}."
                    print(f"[AUTH SUCCESS] {log_msg}")
                    logging.info(log_msg)
                else:
                    response = {"status": "error", "message": "Format gagal! NRP harus berisi 10 digit angka murni."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"[AUTH ERROR] Kendala autentikasi klien: {e}")
            client_socket.close()
            return

    # Tahap 2: Loop Utama Komunikasi (Routing Perintah JSON)
    while True:
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                break
            
            packet = json.loads(data)
            command = packet.get("command")
            target = packet.get("target", "")
            payload = packet.get("payload", "")
            
            current_room = clients[client_socket]["current_room"]
            my_alias = clients[client_socket]["alias"]
            
            if command == "broadcast":
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                chat_entry = {
                    "sender": my_alias,
                    "message": payload,
                    "timestamp": now_str
                }
                persistent_rooms_data[current_room].append(chat_entry)
                
                # SIMPAN KE FILE JSON
                save_database({"rooms": persistent_rooms_data})

                broadcast_packet = {
                    "status": "success",
                    "sender_alias": my_alias,
                    "message": payload
                }
                broadcast_to_room(current_room, client_socket, broadcast_packet)
                
            elif command == "create":
                room_name = payload.strip()
                if room_name not in persistent_rooms_data: # Gunakan persistent_rooms_data sebagai acuan
                    persistent_rooms_data[room_name] = []
                    rooms_sockets[room_name] = []
                    
                    # SIMPAN KE FILE JSON
                    save_database({"rooms": persistent_rooms_data})
                    
                    response = {"status": "info", "sender_alias": "SISTEM", "message": f"Forum [{room_name}] sukses dibuat."}
                else:
                    response = {"status": "error", "sender_alias": "SISTEM", "message": "Nama forum tersebut sudah ada!"}
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            elif command == "join":
                room_name = payload.strip()
                history = persistent_rooms_data[room_name][-10:]
                if history:
                    client_socket.sendall(json.dumps({"status": "info", "sender_alias": "SISTEM", "message": "[RIWAYAT DISKUSI " + room_name + "]"}).encode('utf-8'))
                    for chat in history:
                        h_packet = {
                            "status": "success",
                            "sender_alias": f"{chat['sender']} ({chat['timestamp'].split(' ')[1]})",
                            "message": chat["message"]                            }
                        client_socket.sendall(json.dumps(h_packet).encode('utf-8'))
                    client_socket.sendall(json.dumps({"status": "info", "sender_alias": "SISTEM", "message": "-----------------------"}).encode('utf-8'))

                if room_name in rooms_sockets:
                    # Keluar dari room lama
                    rooms_sockets[current_room].remove(client_socket)
                    # Notifikasi orang di room lama
                    leave_msg = {"status": "info", "sender_alias": "SISTEM", "message": f"[{my_alias}] pindah ke forum lain."}
                    broadcast_to_room(current_room, client_socket, leave_msg)
                    
                    # Masuk ke room baru
                    rooms_sockets[room_name].append(client_socket)
                    clients[client_socket]["current_room"] = room_name
                    
                    response = {"status": "info", "sender_alias": "SISTEM", "message": f"Anda sukses masuk ke forum [{room_name}]."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
                    # Notifikasi orang di room baru
                    join_msg = {"status": "info", "sender_alias": "SISTEM", "message": f"[{my_alias}] bergabung ke forum ini."}
                    broadcast_to_room(room_name, client_socket, join_msg)
                else:
                    response = {"status": "error", "sender_alias": "SISTEM", "message": "Forum tidak ditemukan! Gunakan /create dulu."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
            elif command == "whisper":
                target_alias = target
                target_socket = None
                # Cari socket milik target_alias
                for sock, info in clients.items():
                    if info["alias"] == target_alias and info["current_room"] == current_room:
                        target_socket = sock
                        break
                
                if target_socket:
                    whisper_packet = {
                        "status": "success",
                        "sender_alias": f"[RAHASIA] {my_alias}",
                        "message": payload
                    }
                    target_socket.sendall(json.dumps(whisper_packet).encode('utf-8'))
                else:
                    response = {"status": "error", "sender_alias": "SISTEM", "message": f"Pengguna [{target_alias}] tidak ditemukan di forum ini."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
            elif command == "leave":
                if current_room != "Lobby":
                    rooms_sockets[current_room].remove(client_socket)
                    leave_msg = {"status": "info", "sender_alias": "SISTEM", "message": f"[{my_alias}] kembali ke Lobby utama."}
                    broadcast_to_room(current_room, client_socket, leave_msg)
                    
                    rooms_sockets["Lobby"].append(client_socket)
                    clients[client_socket]["current_room"] = "Lobby"
                    
                    response = {"status": "info", "sender_alias": "SISTEM", "message": "Anda kembali ke Lobby Utama."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                else:
                    response = {"status": "error", "sender_alias": "SISTEM", "message": "Anda sudah berada di Lobby Utama."}
                    client_socket.sendall(json.dumps(response).encode('utf-8'))

            elif command == "list":
                # Mengambil semua nama room yang terdaftar di dictionary rooms
                room_list = list(rooms_sockets.keys())
                response = {
                    "status": "info",
                    "sender_alias": "SISTEM",
                    "message": f"Daftar Forum Aktif: {', '.join(room_list)}"
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))

            elif command == "help":
                help_text = (
                    "\n--- PANDUAN PERINTAH CIPHERTALK ---\n"
                    "1. /list               -> Menampilkan semua forum yang aktif\n"
                    "2. /create [nama]      -> Membuat forum diskusi baru\n"
                    "3. /join [nama]        -> Masuk ke dalam forum tertentu\n"
                    "4. /leave              -> Keluar dari forum aktif dan kembali ke Lobby\n"
                    "5. /w [alias] [pesan]  -> Membisiki pengguna secara privat\n"
                    "6. Teks Biasa          -> Mengirim pesan publik ke semua orang di forum\n"
                    "7. /exit               -> Keluar dari aplikasi CipherTalk"
                )
                response = {
                    "status": "info",
                    "sender_alias": "SISTEM",
                    "message": help_text
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))        
        except:
            break

    handle_disconnect(client_socket)

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[START] Server CipherTalk aktif mendengarkan di {HOST}:{PORT}")
    logging.info(f"Server CipherTalk diaktifkan pada {HOST}:{PORT}")
    
    while True:
        client_socket, client_address = server.accept()
        print(f"[CONNECTION] Koneksi fisik masuk dari {client_address}")
        # Alokasikan satu thread mandiri untuk melayani klien baru ini
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    start_server()