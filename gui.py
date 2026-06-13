import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
from datetime import datetime

HOST = '127.0.0.1'
PORT = 7002

class CipherTalkClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CipherTalk - Anonymous Campus Forum")
        self.root.geometry("800x600")
        
        self.client_socket = None
        self.my_alias = ""
        self.is_running = False
        self.nrp_saved = ""
        
        self.container = tk.Frame(self.root, padx=20, pady=20)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        self.show_login_screen()

    def clear_container(self):
        """Membersihkan elemen layar sebelum berganti halaman"""
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_login_screen(self):
        self.clear_container()
        
        tk.Label(self.container, text="🫷🏻 CIPHERTALK LOGIN 💌", font=("Arial", 16, "bold")).pack(pady=15)
        tk.Label(self.container, text="Masukkan 10-Digit NRP ITS Anda untuk verifikasi:", font=("Arial", 10)).pack(pady=5)
        
        self.nrp_entry = tk.Entry(self.container, font=("Arial", 12), width=25, justify="center")
        self.nrp_entry.pack(pady=5)
        self.nrp_entry.focus()
        
        self.login_btn = tk.Button(self.container, text="Kirim NRP", font=("Arial", 11, "bold"), 
                                   bg="#0056b3", fg="white", width=15, command=self.handle_nrp_submit)
        self.login_btn.pack(pady=20)

    def show_otp_screen(self, server_message):
        self.clear_container()
        
        tk.Label(self.container, text="🔐 VERIFIKASI KEAMANAN OTP", font=("Arial", 14, "bold"), fg="#d9534f").pack(pady=15)
        tk.Label(self.container, text=server_message, font=("Arial", 10), justify="center", fg="#555").pack(pady=5)
        
        self.otp_entry = tk.Entry(self.container, font=("Arial", 14), width=15, justify="center", show="*")
        self.otp_entry.pack(pady=10)
        self.otp_entry.focus()
        
        self.otp_btn = tk.Button(self.container, text="Verifikasi OTP", font=("Arial", 11, "bold"), 
                                 bg="#28a745", fg="white", width=15, command=self.handle_otp_submit)
        self.otp_btn.pack(pady=15)

    def show_chat_screen(self):
        self.clear_container()
        
        self.container.columnconfigure(0, weight=3)
        self.container.columnconfigure(1, weight=1)
        self.container.rowconfigure(0, weight=1)
        
        left_frame = tk.Frame(self.container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        self.info_label = tk.Label(left_frame, text=f"Identitas Samaran Anda: {self.my_alias}", 
                                   font=("Arial", 11, "bold"), fg="#0056b3", anchor="w")
        self.info_label.pack(fill=tk.X, pady=(0, 5))
        
        self.chat_area = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, font=("Arial", 10), bg="#f8f9fa")
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.chat_area.config(state=tk.DISABLED)
        
        bottom_frame = tk.Frame(left_frame)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.msg_entry = tk.Entry(bottom_frame, font=("Arial", 11))
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.msg_entry.bind("<Return>", lambda event: self.send_broadcast())
        
        self.send_btn = tk.Button(bottom_frame, text="Kirim Chat", font=("Arial", 10, "bold"),
                                  bg="#28a745", fg="white", width=12, command=self.send_broadcast)
        self.send_btn.pack(side=tk.RIGHT)
        
        right_frame = tk.LabelFrame(self.container, text=" PANEL KONTROL ", font=("Arial", 10, "bold"), padx=10, pady=10)
        right_frame.grid(row=0, column=1, sticky="nsew")
        
        tk.Label(right_frame, text="Manajemen Forum", font=("Arial", 9, "bold"), fg="#666").pack(anchor="w", pady=(5,2))
        
        tk.Button(right_frame, text="🌐 Daftar Forum", bg="#f1f3f4", fg="black", anchor="w",
                  command=lambda: self.send_action_packet({"command": "list"})).pack(fill=tk.X, pady=2)
                  
        tk.Button(right_frame, text="➕ Buat Forum Baru", bg="#e8f0fe", fg="#1a73e8", anchor="w",
                  command=self.gui_create_room).pack(fill=tk.X, pady=2)
                  
        tk.Button(right_frame, text="🚪 Masuk Forum", bg="#e6f4ea", fg="#137333", anchor="w",
                  command=self.gui_join_room).pack(fill=tk.X, pady=2)
                  
        tk.Button(right_frame, text="↩️ Kembali ke Lobby", bg="#fce8e6", fg="#c5221f", anchor="w",
                  command=lambda: self.send_action_packet({"command": "leave"})).pack(fill=tk.X, pady=2)
        
        tk.Frame(right_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)
        
        tk.Label(right_frame, text="Fitur Pengguna", font=("Arial", 9, "bold"), fg="#666").pack(anchor="w", pady=(0,2))
        
        tk.Button(right_frame, text="👥 Cek User Online", bg="#f1f3f4", fg="black", anchor="w",
                  command=lambda: self.send_action_packet({"command": "online"})).pack(fill=tk.X, pady=2)
                  
        tk.Button(right_frame, text="🔒 Bisikan Privat (Whisper)", bg="#feefc3", fg="#b06000", anchor="w",
                  command=self.gui_whisper_user).pack(fill=tk.X, pady=2)
                  
        tk.Button(right_frame, text="❓ Bantuan Perintah", bg="#f1f3f4", fg="black", anchor="w",
                  command=lambda: self.send_action_packet({"command": "help"})).pack(fill=tk.X, pady=2)
        
        tk.Button(right_frame, text="❌ Keluar Aplikasi", bg="#d9534f", fg="white", font=("Arial", 10, "bold"),
                  command=self.root.quit).pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        self.append_chat("SISTEM", "Selamat datang di CipherTalk Versi GUI!\nSilakan gunakan deretan tombol di panel kontrol sebelah kanan untuk mengelola room atau melakukan whisper secara instan.")
    
    def gui_create_room(self):
        room_name = simpledialog.askstring("Buat Forum Baru", "Masukkan nama forum yang ingin dibuat:", parent=self.root)
        if room_name and room_name.strip():
            self.send_action_packet({"command": "create", "payload": room_name.strip()})

    def gui_join_room(self):
        room_name = simpledialog.askstring("Masuk Forum", "Masukkan nama forum target:", parent=self.root)
        if room_name and room_name.strip():
            self.send_action_packet({"command": "join", "payload": room_name.strip()})

    def gui_whisper_user(self):
        target_user = simpledialog.askstring("Bisikan Privat", "Masukkan nama ALIAS pengguna target:", parent=self.root)
        if target_user and target_user.strip():
            message_body = simpledialog.askstring("Isi Pesan", f"Masukkan pesan rahasia untuk {target_user.strip()}:", parent=self.root)
            if message_body and message_body.strip():
                self.send_action_packet({
                    "command": "whisper", 
                    "target": target_user.strip(), 
                    "payload": message_body.strip()
                })

    def handle_nrp_submit(self):
        nrp = self.nrp_entry.get().strip()
        if not nrp or len(nrp) != 10 or not nrp.isdigit():
            messagebox.showerror("Error Format", "Format gagal! NRP harus berisi 10 digit angka murni.")
            return
            
        try:
            if not self.client_socket:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((HOST, PORT))
            
            self.nrp_saved = nrp
            login_packet = {"command": "login", "payload": nrp}
            self.client_socket.sendall((json.dumps(login_packet) + "\n").encode('utf-8'))
            
            response_data = self.client_socket.recv(4096).decode('utf-8').strip()
            res = json.loads(response_data)
            status = res.get("status")
            
            if status == "error":
                messagebox.showerror("Login Gagal", res.get("message"))
            elif status == "otp_sent":
                self.show_otp_screen(res.get("message"))
            elif status == "success":
                self.process_login_success(res)
                
        except Exception as e:
            messagebox.showerror("Connection Error", f"Gagal terhubung ke Server CipherTalk: {e}")
            self.client_socket = None

    def handle_otp_submit(self):
        otp = self.otp_entry.get().strip()
        if not otp:
            return
            
        try:
            verify_packet = {
                "command": "verify_otp",
                "nrp": self.nrp_saved,
                "payload": otp
            }
            self.client_socket.sendall((json.dumps(verify_packet) + "\n").encode('utf-8'))
            
            response_data = self.client_socket.recv(4096).decode('utf-8').strip()
            res = json.loads(response_data)
            status = res.get("status")
            
            if status == "success":
                self.process_login_success(res)
            elif status == "error":
                messagebox.showerror("Verifikasi OTP Gagal", res.get("message"))
                
                err_msg = res.get("message", "").lower()
                if "kedaluwarsa" in err_msg or "terlalu banyak" in err_msg or "tidak ada proses login" in err_msg:
                    self.show_login_screen()
        except Exception as e:
            messagebox.showerror("Error Jaringan", f"Kendala saat mengirim verifikasi OTP: {e}")

    def process_login_success(self, res_packet):
        welcome_msg = res_packet.get('message', '')
        self.my_alias = welcome_msg.split(": ")[1] if ": " in welcome_msg else "Anonymous"
        
        self.is_running = True
        self.show_chat_screen()
        
        threading.Thread(target=self.listen_from_server, daemon=True).start()

    def listen_from_server(self):
        buffer = ""
        while self.is_running:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    self.append_chat("SISTEM", "[INFO] Koneksi terputus dari server CipherTalk.")
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
                        self.append_chat(f"!! ERROR !! ({timestamp})", message)
                    elif status == "info":
                        self.append_chat(f"* INFO * ({timestamp})", message)
                    else:
                        self.append_chat(f"{sender} ({timestamp})", message)
            except:
                break
                
        self.is_running = False
        self.root.after(0, self.disable_inputs)

    def disable_inputs(self):
        self.msg_entry.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

    def send_broadcast(self):
        """Mengirim pesan teks publik biasa (Broadcast)"""
        user_input = self.msg_entry.get().strip()
        if not user_input:
            return
            
        packet = {
            "command": "broadcast",
            "payload": user_input
        }
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append_chat(f"Anda ({timestamp})", user_input)
        
        self.send_action_packet(packet)
        self.msg_entry.delete(0, tk.END)

    def send_action_packet(self, packet_dict):
        """Helper function untuk membungkus data dengan \\n lalu dikirim ke socket server"""
        try:
            self.client_socket.sendall((json.dumps(packet_dict) + "\n").encode("utf-8"))
        except Exception as e:
            self.append_chat("SISTEM", f"[!] Gagal mengirim instruksi ke server: {e}")

    def append_chat(self, sender, message):
        """Mencetak log obrolan ke widget ScrolledText secara rapi"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"[{sender}]: {message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = CipherTalkClientGUI(root)
    root.mainloop()