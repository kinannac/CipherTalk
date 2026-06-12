import socket
import threading
import json
import sys
from datetime import datetime

HOST = '127.0.0.1'
PORT = 7002

def listen_from_server(client_socket):
    buffer = ""

    while True:
        try:
            data = client_socket.recv(4096).decode('utf-8')

            if not data:
                print("\n[INFO] Koneksi terputus dari server CipherTalk.")
                break

            buffer += data

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                if not line.strip():
                    continue

                packet = json.loads(line)

                status = packet.get("status")
                sender = packet.get("sender_alias", "SISTEM")
                message = packet.get("message", "")
                timestamp = datetime.now().strftime("%H:%M:%S")

                if status == "error":
                    print(f"\n[{timestamp}] [!! ERROR !!] {message}")
                elif status == "info":
                    print(f"\n[{timestamp}] [* INFO *] {message}")
                else:
                    print(f"\n[{timestamp}] [{sender}]: {message}")

                print("> ", end="", flush=True)
                
        except OSError:
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            break

    client_socket.close()
    sys.exit()

def start_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((HOST, PORT))
    except Exception as e:
        print(f"Gagal terhubung ke Server CipherTalk: {e}")
        return

    print("🫷🏻 Selamat Datang di CipherTalk: Anonymous Campus Forum 💌")
    
    # Proses Autentikasi Awal (Looping sampai server melepas status sukses)
    authenticated = False
    authenticated = False

    while not authenticated:
        nrp_input = input(
            "\nMasukkan 10-digit NRP ITS Anda untuk verifikasi keamanan: "
        ).strip()

        login_packet = {
            "command": "login",
            "payload": nrp_input
        }

        client.sendall(
            (json.dumps(login_packet) + "\n").encode('utf-8')
        )

        response_data = client.recv(4096).decode('utf-8').strip()

        if not response_data:
            print("Server mati saat verifikasi.")
            return

        res = json.loads(response_data)
        status = res.get("status")

        if status == "error":
            print(f"[!] {res.get('message')}")
            continue

        elif status == "otp_sent":
            print(res.get("message"))

            # OTP loop
            while True:
                otp = input(
                    "Masukkan OTP yang dikirim ke email ITS Anda: "
                ).strip()

                verify_packet = {
                    "command": "verify_otp",
                    "nrp": nrp_input,
                    "payload": otp
                }

                client.sendall(
                    (json.dumps(verify_packet) + "\n").encode('utf-8')
                )

                response_data = client.recv(4096).decode('utf-8').strip()

                if not response_data:
                    print("Server mati saat verifikasi OTP.")
                    return

                res = json.loads(response_data)
                status = res.get("status")

                if status == "success":
                    print(f"\n[* SYSTEM *] {res.get('message')}")
                    authenticated = True
                    break

                elif status == "error":
                    print(f"[!] {res.get('message')}")

                    # Go back to NRP only if OTP session ended
                    if (
                        "kedaluwarsa" in res.get("message", "").lower()
                        or "terlalu banyak" in res.get("message", "").lower()
                        or "tidak ada proses login" in res.get("message", "").lower()
                    ):
                        break
    
    # Hidupkan Thread Listener setelah sukses terautentikasi
    listener_thread = threading.Thread(target=listen_from_server, args=(client,))
    listener_thread.daemon = True
    listener_thread.start()

    # Loop Thread Utama: Menangani Ketikan Input Pengguna ke Jaringan
    running = True
    while running:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue
            
            # Keluar aplikasi
            if user_input.lower() == "/exit":
                running = False
                break
                
            packet = {}
            # Parsing Perintah Berawalan Garis Miring (Slash Command)
            if user_input.startswith("/"):
                parts = user_input.split(" ", 2)
                command = parts[0].lower()
                if command == "/list":
                    packet = {"command": "list"}
                elif command == "/help":
                    packet = {"command": "help"}
                elif command == "/leave":
                    packet = {"command": "leave"}

                elif command == "/create" and len(parts) > 1:
                    packet = {"command": "create", "payload": parts[1]}
                elif command == "/join" and len(parts) > 1:
                    packet = {"command": "join", "payload": parts[1]}
                elif command == "/w" and len(parts) > 2:
                    # format: /w alias_target isi_pesan
                    packet = {"command": "whisper", "target": parts[1], "payload": parts[2]}
                else:
                    print("[!] Format perintah salah atau argumen kurang.")
                    continue
            else:
                # Jika input teks biasa tanpa command -> Otomatis Broadcast ke Forum Aktif
                packet = {
                    "command": "broadcast",
                    "payload": user_input
                }
                
            client.sendall((json.dumps(packet) + "\n").encode("utf-8"))
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari CipherTalk...")
            break
        except Exception as e:
            print(f"\nGagal mengirim data: {e}")
            break

    client.close()

if __name__ == "__main__":
    start_client()