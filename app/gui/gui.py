import tkinter as tk
from tkinter import ttk, messagebox
from finger_device.device import Device
from client.client import Client
from PIL import Image, ImageTk
import io
import tempfile
import os

class GUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Fingerprint GUI")
        self.root.state("zoomed")  # Full screen
        self.status = tk.StringVar(value="Ready")
        self.max_fingerprints = 10
        self.registered_images = []
        self.client = Client()
        
        # Styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background="#E5E5E5")
        self.style.configure('TLabelFrame', background="#006cd8", foreground='white', font=('Arial', 12, 'bold'))
        self.style.configure('TLabel', background="#000000", foreground='white', font=('Arial', 11))
        self.style.configure('TButton', background="#000000", foreground='white', font=('Arial', 11, 'bold'))
        self.style.map('TButton', background=[('active', "#6D6D71")])

        # Initialize fingerprint device
        try:
            self.dev = Device()
            self.status.set("Device ready")
        except Exception as e:
            self.dev = None
            self.status.set(f"Device error: {e}")
            messagebox.showerror("Device Error", str(e))
        
        self._build()

    def _build(self):
        # Main container with 2 halves
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # ---------------- LEFT SIDE (Registration) ----------------
        reg_frame = ttk.LabelFrame(main_frame, text="Register", padding=16)
        reg_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # Name and Email
        ttk.Label(reg_frame, text="Name:").grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(reg_frame)
        self.entry_name.grid(row=0, column=1, sticky="ew")
        ttk.Label(reg_frame, text="Email:").grid(row=1, column=0, sticky="w")
        self.entry_email = ttk.Entry(reg_frame)
        self.entry_email.grid(row=1, column=1, sticky="ew")

        # Fingerprint buttons
        self.btn_add_fp = ttk.Button(reg_frame, text="Add Fingerprint", command=self.add_fingerprint)
        self.btn_add_fp.grid(row=2, column=0, columnspan=2, pady=8, sticky="ew")
        self.fp_status = ttk.Label(reg_frame, text="0 / 10 fingerprints added")
        self.fp_status.grid(row=3, column=0, columnspan=2, pady=4)
        self.btn_register_user = ttk.Button(reg_frame, text="Submit Registration", command=self.register_user)
        self.btn_register_user.grid(row=4, column=0, columnspan=2, pady=8, sticky="ew")

        # ---------------- RIGHT SIDE (Verification) ----------------
        check_frame = ttk.LabelFrame(main_frame, text="Verify", padding=16)
        check_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.btn_check_fp = ttk.Button(check_frame, text="Check Fingerprint", command=self.check_fingerprint)
        self.btn_check_fp.pack(pady=20, fill="x")

        # ---------------- BOTTOM (Status + Exit) ----------------
        bottom_frame = ttk.Frame(self.root, padding=8)
        bottom_frame.pack(fill="x", side="bottom")
        ttk.Label(bottom_frame, text="Status:").pack(side="left")
        ttk.Label(bottom_frame, textvariable=self.status).pack(side="left")
        ttk.Button(bottom_frame, text="Exit", command=self.on_exit).pack(side="right")

    # ================= Fingerprint Functions =================
    def add_fingerprint(self):
        if not self.dev:
            messagebox.showerror("Error", "Device not available")
            return
        if len(self.registered_images) >= self.max_fingerprints:
            messagebox.showwarning("Limit Reached", "You can only register 10 fingerprints.")
            return
        try:
            self.status.set("Place finger on sensor...")
            img_bytes = self.dev.read_fingerprint()
            self.registered_images.append(img_bytes)
            self.fp_status.config(text=f"{len(self.registered_images)} / {self.max_fingerprints} fingerprints added")
            self.status.set("Fingerprint captured")
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def register_user(self):
        if not self.registered_images:
            messagebox.showwarning("No Data", "Please add at least 1 fingerprint.")
            return
        name = self.entry_name.get().strip()
        email = self.entry_email.get().strip()
        if not name or not email:
            messagebox.showwarning("Missing Data", "Name and Email are required.")
            return
        temp_files = []
        try:
            self.status.set("Preparing images...")
            for i, img_bytes in enumerate(self.registered_images):
                width, height = 256, 256
                img = Image.frombytes("L", (width, height), img_bytes)
                tmp = tempfile.NamedTemporaryFile(suffix=".bmp", delete=False)
                img.save(tmp.name, format="BMP")
                tmp.flush()
                temp_files.append(tmp)
            files = [
                ('files', (f'fingerprint_{i+1}.bmp', open(tmp.name, 'rb'), 'image/bmp'))
                for i, tmp in enumerate(temp_files)
            ]
            self.status.set("Sending data to server...")
            response = self.client.register_user(email, name, [f[1][1].read() for f in files])
            for _, file_tuple in files:
                file_tuple[1].close()
            if response and response.get("user"):
                self.status.set("User registered successfully ✅")
                messagebox.showinfo("Success", "User registered successfully.")
                self.registered_images.clear()
                self.fp_status.config(text="0 / 10 fingerprints added")
            else:
                self.status.set("Registration failed ❌")
                messagebox.showerror("Error", response.get("message", "Unknown error"))
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            for tmp in temp_files:
                try:
                    tmp.close()
                    os.unlink(tmp.name)
                except Exception:
                    pass

    def check_fingerprint(self):
        if not self.dev:
            messagebox.showerror("Error", "Device not available")
            return
        try:
            self.status.set("Place finger for verification...")
            img_bytes = self.dev.read_fingerprint()
            width, height = 256, 288
            img = Image.frombytes("L", (width, height), img_bytes)
            img_tk = ImageTk.PhotoImage(img.resize((150, 170)))
            top_img = tk.Toplevel(self.root)
            top_img.title("Scanned Fingerprint")
            tk.Label(top_img, image=img_tk).pack()
            top_img.image = img_tk
            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
                img.save(tmp.name, format="BMP")
                bmp_path = tmp.name
            with open(bmp_path, "rb") as f:
                response = self.client.check_fingerprint(f.read())
            print(response)
            table_win = tk.Toplevel(self.root)
            table_win.title("Fingerprint Matches")
            table_win.geometry("500x300")
            cols = ("Name", "Email", "Distance", "Match" , "Matching Time")
            tree = ttk.Treeview(table_win, columns=cols, show="headings")
            for col in cols:
                tree.heading(col, text=col)
                tree.column(col, width=100, anchor="center")
            tree.pack(fill="both", expand=True)
            for match in response.get("matching", []):
                user = match.get("user", {})
                name = user.get("name", "N/A")
                email = user.get("email", "N/A")
                dist = round(float(match.get("distance", 0)), 2)
                is_match = "✅" if dist < 50 else "❌"
                matching_time = match.get("matching_time", "N/A")
                tree.insert("", "end", values=(name, email, dist, is_match , matching_time))
            best = response.get("best_match")
            if best:
                self.status.set(
                    f"Best match: {best['user']['name']} ({best['distance']:.2f})"
                )
            else:
                self.status.set("No match found ❌")
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def on_exit(self):
        if self.dev:
            self.dev.close()
        self.root.quit()

    def run(self):
        self.root.mainloop()
