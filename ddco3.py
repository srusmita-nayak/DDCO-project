import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import threading
import time
import random
import socket
import traceback
import asyncio
import os

import pyshark  # requires tshark/Wireshark and tshark in PATH

running = False


class BusArbitrationSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Arbitration Simulator - With PyShark")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 700)
        self.root.resizable(True, True)
        # Light, clean background
        self.root.configure(bg="#f3f4f6")

        # ---------- Global styles ----------
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground="#111827")

        # Top title bar
        header = tk.Frame(root, bg="#ffffff", height=48, highlightthickness=1, highlightbackground="#e5e7eb")
        header.pack(fill="x", side="top")
        title_lbl = tk.Label(
            header,
            text="Bus Arbitration Simulator",
            font=("Segoe UI", 14, "bold"),
            fg="#111827",
            bg="#ffffff",
        )
        title_lbl.pack(side="left", padx=16, pady=8)
        subtitle_lbl = tk.Label(
            header,
            text="Visualizing Fixed, Round-Robin, and Daisy Chain arbitration with live packet capture",
            font=("Segoe UI", 9),
            fg="#6b7280",
            bg="#ffffff",
        )
        subtitle_lbl.pack(side="left", padx=8, pady=8)

        # Canvas for diagram
        canvas_frame = tk.Frame(root, bg="#f3f4f6")
        canvas_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.canvas = tk.Canvas(canvas_frame, width=1200, height=380, bg="#ffffff", highlightthickness=1,
                                highlightbackground="#e5e7eb")
        self.canvas.pack(padx=16, pady=(8, 4))

        # Bottom control panel - scrollable container
        control_container = tk.Frame(root, bg="#f3f4f6")
        control_container.pack(fill="both", expand=False, side="bottom", padx=0, pady=(4, 0))
        
        # Create scrollable canvas for control panel
        self.control_canvas = tk.Canvas(control_container, bg="#f3f4f6", highlightthickness=0)
        control_scrollbar = tk.Scrollbar(control_container, orient="vertical", command=self.control_canvas.yview)
        self.control_frame = tk.Frame(self.control_canvas, bg="#f3f4f6")
        
        # Function to update scroll region and canvas width
        def update_scroll_region(event=None):
            self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))
            # Make sure the frame width matches canvas width
            canvas_width = event.width if event else self.control_canvas.winfo_width()
            if canvas_width > 1:
                self.control_canvas.itemconfig(self.control_frame_id, width=canvas_width)
        
        # Configure scrolling
        self.control_frame.bind("<Configure>", update_scroll_region)
        self.control_canvas.bind("<Configure>", update_scroll_region)
        
        self.control_frame_id = self.control_canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        self.control_canvas.configure(yscrollcommand=control_scrollbar.set)
        
        # Pack scrollable components
        self.control_canvas.pack(side="left", fill="both", expand=True)
        control_scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel to control canvas
        def _on_control_mousewheel(event):
            self.control_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.control_canvas.bind("<MouseWheel>", _on_control_mousewheel)
        self.control_frame.bind("<MouseWheel>", _on_control_mousewheel)
        
        for col in range(3):
            self.control_frame.columnconfigure(col, weight=1)

        # Devices & Arbiter
        self.device_labels = ["Device 1", "Device 2", "Device 3", "Device 4"]
        self.device_count = len(self.device_labels)
        self.arbiter_x, self.arbiter_y = 150, 250
        self.device_start_x, self.device_y = 650, 250
        self.device_spacing = 150
        self.bus_y = 100

        self.arbiter_box = None
        self.device_boxes = []
        self.draw_static_components()

        # Per-device status labels (under each device) - create a frame below canvas
        status_frame = tk.Frame(canvas_frame, bg="#f3f4f6", height=30)
        status_frame.pack(fill="x", padx=16, pady=(0, 4))
        status_frame.pack_propagate(False)
        self.device_status_labels = []
        for i in range(self.device_count):
            x = self.device_start_x + i * self.device_spacing
            status = tk.Label(status_frame, text="Idle", font=("Segoe UI", 9), fg="#6b7280", bg="#f3f4f6")
            status.place(x=x - 30, y=5)
            self.device_status_labels.append(status)

        # -------- Controls layout (bottom panel) --------

        # Log box - larger area for better visibility
        self.log_frame = tk.Frame(self.control_frame, bg="#f3f4f6")
        self.log_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(8, 4))
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        self.scrollbar = tk.Scrollbar(self.log_frame)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.log = tk.Text(
            self.log_frame,
            width=140,
            height=10,  # Increased from 4 to 10 lines
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#111827",
            insertbackground="#111827",
            relief="solid",
            borderwidth=1,
            wrap=tk.WORD,
            yscrollcommand=self.scrollbar.set
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.config(command=self.log.yview)

        info_frame = tk.Frame(self.control_frame, bg="#f3f4f6")
        info_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12)
        # Stats: grants per device
        self.grant_counts = [0] * self.device_count
        self.stats_label = tk.Label(info_frame, text="Stats: ", font=("Segoe UI", 9), fg="#4b5563", bg="#f3f4f6")
        self.stats_label.pack(side="left")
        # Error/info bar
        self.error_label = tk.Label(info_frame, text="", font=("Segoe UI", 9), fg="#b91c1c", bg="#f3f4f6")
        self.error_label.pack(side="right")

        # Left: Arbitration Mode
        mode_frame = tk.LabelFrame(
            self.control_frame,
            text="Arbitration",
            bg="#f3f4f6",
            fg="#4b5563",
            font=("Segoe UI", 9, "bold"),
            labelanchor="n"
        )
        mode_frame.grid(row=2, column=0, sticky="w", padx=12, pady=8)
        self.mode_label = tk.Label(mode_frame, text="Mode", font=("Segoe UI", 9), fg="#111827", bg="#f3f4f6")
        self.mode_label.grid(row=0, column=0, padx=(8, 4), pady=6, sticky="w")
        self.mode_var = tk.StringVar(value="Fixed Priority")
        self.mode_menu = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=["Fixed Priority", "Round Robin", "Daisy Chain"],
            state="readonly",
            width=15
        )
        self.mode_menu.grid(row=0, column=1, padx=(0, 8), pady=6)

        # Center: Simulation controls
        sim_frame = tk.LabelFrame(
            self.control_frame,
            text="Simulation",
            bg="#f3f4f6",
            fg="#4b5563",
            font=("Segoe UI", 9, "bold"),
            labelanchor="n"
        )
        sim_frame.grid(row=2, column=1, pady=8)
        self.start_btn = tk.Button(
            sim_frame,
            text="Start",
            font=("Segoe UI", 10, "bold"),
            command=self.start,
            bg="#22c55e",
            fg="#064e3b",
            activebackground="#16a34a",
            activeforeground="#020617",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
        )
        self.start_btn.grid(row=0, column=0, padx=(18, 6), pady=8)
        self.stop_btn = tk.Button(
            sim_frame,
            text="Stop",
            font=("Segoe UI", 10, "bold"),
            command=self.stop,
            bg="#ef4444",
            fg="#f9fafb",
            activebackground="#b91c1c",
            activeforeground="#f9fafb",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
        )
        self.stop_btn.grid(row=0, column=1, padx=(6, 18), pady=8)

        # Networking for Wireshark integration (UDP on localhost)
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5555  # choose any unused port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Find TShark path automatically
        self.tshark_path = self.find_tshark()
        if not self.tshark_path:
            self.log_message("[Warning] TShark not found. Please configure the path manually.\n")

        # Wireshark / PyShark integration controls
        net_frame = tk.LabelFrame(
            self.control_frame,
            text="Wireshark / PyShark",
            bg="#f3f4f6",
            fg="#4b5563",
            font=("Segoe UI", 9, "bold"),
            labelanchor="n"
        )
        net_frame.grid(row=2, column=2, sticky="e", padx=12, pady=8)

        self.wireshark_enabled = tk.BooleanVar(value=True)
        self.wireshark_check = tk.Checkbutton(
            net_frame,
            text="Send events (UDP 127.0.0.1:5555)",
            variable=self.wireshark_enabled,
            font=("Segoe UI", 9),
            fg="#111827",
            bg="#f3f4f6",
            activebackground="#f3f4f6",
            selectcolor="#f3f4f6",
        )
        self.wireshark_check.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))
        
        # TShark path configuration
        tk.Label(net_frame, text="TShark path:", font=("Segoe UI", 9), fg="#111827", bg="#f3f4f6").grid(
            row=1, column=0, padx=(8, 4), pady=4, sticky="w"
        )
        self.tshark_path_entry = tk.Entry(net_frame, width=18, font=("Segoe UI", 8), bg="#ffffff", fg="#111827",
                                          insertbackground="#111827", relief="solid", borderwidth=1)
        if self.tshark_path:
            self.tshark_path_entry.insert(0, self.tshark_path)
        else:
            self.tshark_path_entry.insert(0, "C:\\Program Files\\Wireshark\\tshark.exe")
        self.tshark_path_entry.grid(row=1, column=1, padx=(0, 2), pady=4, sticky="ew")
        net_frame.columnconfigure(1, weight=1)
        
        browse_btn = tk.Button(
            net_frame,
            text="...",
            font=("Segoe UI", 8),
            command=self.browse_tshark,
            bg="#e5e7eb",
            fg="#111827",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        browse_btn.grid(row=1, column=2, padx=(2, 8), pady=4, sticky="e")
        
        tk.Label(net_frame, text="PyShark iface:", font=("Segoe UI", 9), fg="#111827", bg="#f3f4f6").grid(
            row=2, column=0, padx=(8, 4), pady=4, sticky="w"
        )
        # Use Combobox for interface selection with common options (editable)
        self.capture_iface_var = tk.StringVar()
        self.capture_iface = ttk.Combobox(
            net_frame,
            textvariable=self.capture_iface_var,
            width=18,
            font=("Segoe UI", 9),
            state="normal"  # Allow typing custom interface names
        )
        # Default to loopback interface (Windows format)
        self.capture_iface_var.set(r"\Device\NPF_Loopback")
        # Common interface options (user can also type custom)
        common_interfaces = [
            r"\Device\NPF_Loopback",  # Loopback (for localhost traffic)
            "Wi-Fi",
            "Ethernet",
            "Local Area Connection",
        ]
        self.capture_iface['values'] = common_interfaces
        self.capture_iface.grid(row=2, column=1, padx=(0, 2), pady=4, sticky="ew")
        
        # Button to refresh/list interfaces
        refresh_iface_btn = tk.Button(
            net_frame,
            text="List",
            font=("Segoe UI", 8),
            command=self.list_interfaces,
            bg="#e5e7eb",
            fg="#111827",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
        )
        refresh_iface_btn.grid(row=2, column=2, padx=(2, 8), pady=4, sticky="e")

        self.capture_running = False
        self.capture_thread = None
        self.capture_btn = tk.Button(
            net_frame,
            text="Start Capture",
            font=("Segoe UI", 9, "bold"),
            command=self.toggle_capture,
            bg="#3b82f6",
            fg="#f9fafb",
            activebackground="#2563eb",
            activeforeground="#f9fafb",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.capture_btn.grid(row=3, column=0, columnspan=3, padx=8, pady=(2, 8), sticky="e")

        # For round-robin
        self.next_index = 0

        # Bind mouse wheel to log scrolling - Windows uses MouseWheel, Linux/Mac use Button-4/5
        self.log.bind("<MouseWheel>", self._on_mousewheel)
        self.log_frame.bind("<MouseWheel>", self._on_mousewheel)
        # Linux/Mac fallback
        self.log.bind("<Button-4>", lambda e: self.log.yview_scroll(-1, "units"))
        self.log.bind("<Button-5>", lambda e: self.log.yview_scroll(1, "units"))
        self.log_frame.bind("<Button-4>", lambda e: self.log.yview_scroll(-1, "units"))
        self.log_frame.bind("<Button-5>", lambda e: self.log.yview_scroll(1, "units"))
        # Make log focusable for better scrolling
        self.log_frame.bind("<Enter>", lambda e: self.log.focus_set())

    def find_tshark(self):
        """Try to find tshark.exe in common installation paths"""
        common_paths = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
            r"C:\Program Files\Wireshark\tshark.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        # Also check if tshark is in PATH
        import shutil
        tshark_in_path = shutil.which("tshark")
        if tshark_in_path:
            return tshark_in_path
        return None

    def browse_tshark(self):
        """Open file dialog to browse for tshark.exe"""
        filename = filedialog.askopenfilename(
            title="Select TShark executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            initialdir=r"C:\Program Files\Wireshark"
        )
        if filename:
            self.tshark_path_entry.delete(0, tk.END)
            self.tshark_path_entry.insert(0, filename)
            self.tshark_path = filename
            self.log_message(f"TShark path set to: {filename}\n")

    def list_interfaces(self):
        """List available network interfaces using tshark"""
        tshark_path = self.tshark_path_entry.get().strip()
        if not tshark_path or not os.path.exists(tshark_path):
            self.set_error("TShark path not set or invalid")
            self.log_message("[Error] Please set TShark path first.\n")
            return

        try:
            import subprocess
            # Run: tshark -D to list interfaces
            result = subprocess.run(
                [tshark_path, "-D"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                interfaces = result.stdout.strip().split('\n')
                self.log_message("\n=== Available Interfaces ===\n")
                interface_list = []
                for iface in interfaces:
                    if iface.strip():
                        self.log_message(f"{iface}\n")
                        # Extract interface name (format: "1. \Device\NPF_...")
                        parts = iface.split('.', 1)
                        if len(parts) > 1:
                            iface_name = parts[1].strip()
                            interface_list.append(iface_name)
                
                # Update combobox with found interfaces
                if interface_list:
                    current_values = list(self.capture_iface['values'])
                    # Add new interfaces that aren't already in the list
                    for iface in interface_list:
                        if iface not in current_values:
                            current_values.append(iface)
                    self.capture_iface['values'] = tuple(current_values)
                    self.log_message("\nInterfaces added to dropdown list.\n")
            else:
                self.log_message(f"[Error] Failed to list interfaces: {result.stderr}\n")
        except Exception as e:
            self.log_message(f"[Error] Could not list interfaces: {e}\n")
            self.set_error("Failed to list interfaces - see log")

    def draw_static_components(self):
        # Horizontal bus
        self.canvas.create_line(50, self.bus_y, 1150, self.bus_y, width=4, fill="black")
        self.canvas.create_text(100, self.bus_y - 20, text="BUS Busy", font=("Arial", 12, "bold"))
        self.canvas.create_text(400, self.bus_y - 20, text="BUS Request", font=("Arial", 12, "bold"))
        self.canvas.create_text(700, self.bus_y - 20, text="BUS Grant", font=("Arial", 12, "bold"))
        self.canvas.create_text(1050, self.bus_y - 20, text="Address/Data", font=("Arial", 12, "bold"))

        # Arbiter
        self.arbiter_box = self.canvas.create_rectangle(
            self.arbiter_x - 50,
            self.arbiter_y - 50,
            self.arbiter_x + 50,
            self.arbiter_y + 50,
            fill="#d9d9d9",
            outline="black",
            width=3
        )
        self.canvas.create_text(self.arbiter_x, self.arbiter_y,
                                text="ARBITER", font=("Arial", 14, "bold"))

        # Devices
        self.device_boxes = []
        for i in range(self.device_count):
            x = self.device_start_x + i * self.device_spacing
            box = self.canvas.create_rectangle(
                x - 50,
                self.device_y - 40,
                x + 50,
                self.device_y + 40,
                fill="#d9d9d9",
                outline="black",
                width=3
            )
            self.canvas.create_text(
                x,
                self.device_y,
                text=self.device_labels[i],
                font=("Arial", 12, "bold")
            )
            self.device_boxes.append(box)

    def start(self):
        global running
        if not running:
            running = True
            self.clear_error()
            threading.Thread(target=self.simulation_loop, daemon=True).start()
            self.log_message("Simulation started.\n")

    def stop(self):
        global running
        running = False
        self.log_message("Simulation stopped.\n")

    def simulation_loop(self):
        global running
        while running:
            try:
                # Generate requests
                requests = [random.choice([True, False]) for _ in range(self.device_count)]
                requesting_devices = [
                    self.device_labels[i] for i, req in enumerate(requests) if req
                ]

                # Determine winner
                winner_index = self.determine_winner(requests)

                # Update UI (must be done in main thread)
                self.root.after(0, self.update_colors, requests, winner_index)

                if requesting_devices and winner_index is not None:
                    msg = f"Bus granted to {self.device_labels[winner_index]}.\n"
                    self.root.after(0, self.log_message, msg)
                    data = random.randint(1, 255)

                    # Send UDP events
                    self.root.after(0, self.send_wireshark_frame, "GRANT", winner_index, None)
                    self.root.after(0, self.send_wireshark_frame, "DATA", winner_index, data)

                    # Stats and animation
                    self.root.after(0, self.update_stats, winner_index)
                    self.root.after(0, self.animate_data_packet, winner_index, data)
                else:
                    self.root.after(0, self.log_message, "No requests. Bus idle.\n")
                    self.root.after(0, self.send_wireshark_frame, "IDLE", None, None)

                time.sleep(2)
            except Exception as e:
                err_text = f"[Simulation error] {e}\n"
                tb = traceback.format_exc()
                self.root.after(0, self.log_message, err_text)
                self.root.after(0, self.set_error, "Simulation error – see log.")
                self.root.after(0, self.log_message, tb)

        self.root.after(0, self.reset_colors)

    def determine_winner(self, requests):
        try:
            mode = self.mode_var.get()
        except Exception:
            mode = "Fixed Priority"

        if mode == "Fixed Priority":
            for i, req in enumerate(requests):
                if req:
                    return i
        elif mode == "Round Robin":
            for i in range(self.device_count):
                idx = (self.next_index + i) % self.device_count
                if requests[idx]:
                    self.next_index = (idx + 1) % self.device_count
                    return idx
        elif mode == "Daisy Chain":
            for i in reversed(range(self.device_count)):
                if requests[i]:
                    return i
        else:
            self.log_message(f"[Error] Unknown mode '{mode}', using Fixed Priority.\n")
            for i, req in enumerate(requests):
                if req:
                    return i
        return None

    def update_colors(self, requests, winner_index):
        self.canvas.itemconfig(
            self.arbiter_box,
            fill="#a1d99b" if winner_index is not None else "#d9d9d9"
        )
        for i, box in enumerate(self.device_boxes):
            if winner_index == i:
                self.canvas.itemconfig(box, fill="#74c476")
                self.device_status_labels[i].config(text="Granted", fg="green")
            elif requests[i]:
                self.canvas.itemconfig(box, fill="#fdae6b")
                self.device_status_labels[i].config(text="Requesting", fg="orange")
            else:
                self.canvas.itemconfig(box, fill="#d9d9d9")
                self.device_status_labels[i].config(text="Idle", fg="gray")

    def reset_colors(self):
        self.canvas.itemconfig(self.arbiter_box, fill="#d9d9d9")
        for box in self.device_boxes:
            self.canvas.itemconfig(box, fill="#d9d9d9")
        for lbl in self.device_status_labels:
            lbl.config(text="Idle", fg="gray")

    def animate_data_packet(self, winner_index, data):
        x1, y1, x2, y2 = self.canvas.coords(self.device_boxes[winner_index])
        start_x = (x1 + x2) / 2
        start_y = y1
        packet = self.canvas.create_rectangle(
            start_x - 10, start_y - 20, start_x + 10, start_y, fill="#3182bd"
        )
        text = self.canvas.create_text(
            start_x, start_y - 10, text=str(data), fill="white",
            font=("Arial", 10, "bold")
        )

        steps = 50
        dy = (start_y - self.bus_y) / steps

        def step(i):
            global running
            if not running:
                self.canvas.delete(packet)
                self.canvas.delete(text)
                return
            if i >= steps:
                self.canvas.delete(packet)
                self.canvas.delete(text)
                return
            self.canvas.move(packet, 0, -dy)
            self.canvas.move(text, 0, -dy)
            self.root.after(20, step, i + 1)

        step(0)

    def send_wireshark_frame(self, event_type, device_index, data=None):
        if not self.wireshark_enabled.get():
            return

        try:
            device_name = (
                self.device_labels[device_index]
                if device_index is not None and 0 <= device_index < self.device_count
                else "NONE"
            )
        except Exception:
            device_name = "INVALID"

        payload = f"BUS_EVENT {event_type} DEVICE={device_name} DATA={data if data is not None else '-'}"
        try:
            self.sock.sendto(payload.encode("utf-8"), (self.udp_ip, self.udp_port))
        except OSError as e:
            self.log_message(f"[Wireshark error] {e}\n")
            self.set_error("Wireshark UDP send failed – see log.")

    def toggle_capture(self):
        if self.capture_running:
            self.capture_running = False
            self.capture_btn.config(text="Start Capture")
            self.log_message("PyShark capture stopping...\n")
        else:
            iface = self.capture_iface_var.get().strip()
            if not iface:
                self.set_error("Capture interface is empty.")
                return
            
            # Get TShark path from entry
            tshark_path = self.tshark_path_entry.get().strip()
            if not tshark_path:
                self.set_error("TShark path is empty. Please configure it.")
                return
            
            if not os.path.exists(tshark_path):
                self.set_error(f"TShark not found at: {tshark_path}")
                self.log_message(f"[Error] TShark executable not found at: {tshark_path}\n")
                self.log_message("[Info] Please install Wireshark or set the correct TShark path.\n")
                return
            
            self.tshark_path = tshark_path
            self.clear_error()
            self.capture_running = True
            self.capture_btn.config(text="Stop Capture")
            self.log_message(f"Starting PyShark capture on '{iface}' (udp.port == {self.udp_port})...\n")
            self.log_message(f"Using TShark: {tshark_path}\n")
            self.capture_thread = threading.Thread(
                target=self.pyshark_capture_loop, args=(iface, tshark_path), daemon=True
            )
            self.capture_thread.start()

    def pyshark_capture_loop(self, iface_name: str, tshark_path: str):
        # Ensure this background thread has its own asyncio event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        except Exception:
            # If we can't set up a loop, pyshark may still work on some versions
            pass

        try:
            # Configure pyshark to use the specified tshark path
            # Try to set it in config first (if available)
            try:
                import pyshark.config
                if hasattr(pyshark.config, 'set_tshark_path'):
                    pyshark.config.set_tshark_path(tshark_path)
            except Exception:
                pass  # Config method might not exist in all pyshark versions
            
            # Create capture with tshark_path parameter
            capture = pyshark.LiveCapture(
                interface=iface_name,
                display_filter=f"udp.port == {self.udp_port}",
                tshark_path=tshark_path
            )
        except Exception as e:
            error_msg = str(e)
            if "TShark not found" in error_msg or "tshark" in error_msg.lower():
                help_msg = (
                    f"\n[TShark Error] {error_msg}\n"
                    f"[Solution] Please:\n"
                    f"  1. Install Wireshark from https://www.wireshark.org/\n"
                    f"  2. Or set the correct TShark path using the '...' button\n"
                    f"  3. Common paths:\n"
                    f"     - C:\\Program Files\\Wireshark\\tshark.exe\n"
                    f"     - C:\\Program Files (x86)\\Wireshark\\tshark.exe\n"
                )
                self.root.after(0, self.log_message, help_msg)
                self.root.after(0, self.set_error, "TShark not found - see log for instructions")
            elif "does not exist" in error_msg.lower() or "interface" in error_msg.lower():
                # Interface error - extract available interfaces from error message
                help_msg = f"\n[Interface Error] {error_msg}\n"
                help_msg += "\n[Solution] Please:\n"
                help_msg += "  1. Click the 'List' button next to 'PyShark iface' to see available interfaces\n"
                help_msg += "  2. Select the correct interface from the dropdown\n"
                help_msg += "  3. For localhost traffic, use: \\Device\\NPF_Loopback\n"
                help_msg += "\nCommon interface names:\n"
                help_msg += "  - \\Device\\NPF_Loopback (for localhost/loopback)\n"
                help_msg += "  - Wi-Fi (for wireless)\n"
                help_msg += "  - Ethernet (for wired)\n"
                self.root.after(0, self.log_message, help_msg)
                self.root.after(0, self.set_error, "Interface not found - click 'List' to see available interfaces")
            else:
                self.root.after(0, self.set_error, f"PyShark init failed: {error_msg}")
                self.root.after(0, self.log_message, f"[PyShark init error] {error_msg}\n")
            self.capture_running = False
            self.root.after(0, self.capture_btn.config, {"text": "Start Capture"})
            return

        try:
            for pkt in capture.sniff_continuously():
                if not self.capture_running:
                    break
                try:
                    src = pkt.ip.src if hasattr(pkt, "ip") else "?"
                    dst = pkt.ip.dst if hasattr(pkt, "ip") else "?"
                    length = pkt.length if hasattr(pkt, "length") else "?"
                    payload = ""
                    if hasattr(pkt, "udp") and hasattr(pkt.udp, "payload"):
                        payload = str(pkt.udp.payload)
                    msg = (f"[PyShark] {src} -> {dst} len={length} payload={payload}\n")
                    self.root.after(0, self.log_message, msg)
                except Exception as inner_e:
                    self.root.after(0, self.log_message,
                                    f"[PyShark packet error] {inner_e}\n")
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, self.log_message, f"[PyShark capture error] {error_msg}\n")
            if "interface" in error_msg.lower() or "does not exist" in error_msg.lower():
                self.root.after(0, self.log_message, 
                    "\n[Tip] Click the 'List' button to see available interfaces.\n"
                    "For localhost traffic, use: \\Device\\NPF_Loopback\n")
            self.root.after(0, self.set_error, "PyShark capture error – see log.")
        finally:
            try:
                capture.close()
            except Exception:
                pass
            self.capture_running = False
            self.root.after(0, self.capture_btn.config, {"text": "Start Capture"})
            self.root.after(0, self.log_message, "PyShark capture stopped.\n")

    def update_stats(self, winner_index):
        if winner_index is None:
            return
        if 0 <= winner_index < self.device_count:
            self.grant_counts[winner_index] += 1
            parts = [
                f"{name}={cnt}"
                for name, cnt in zip(self.device_labels, self.grant_counts)
            ]
            self.stats_label.config(text="Stats: " + " | ".join(parts))

    def log_message(self, msg):
        self.log.insert(tk.END, msg)
        self.log.see(tk.END)

    # --- mouse wheel support for log scrolling ---
    def _on_mousewheel(self, event):
        # Windows uses event.delta in steps of 120
        # Scroll the log widget
        try:
            delta = event.delta
            # Windows: delta is typically 120 or -120 per notch
            # Linux/Mac: delta might be different, handle both
            if abs(delta) >= 120:
                units = int(-1 * (delta / 120))
            else:
                units = -1 if delta > 0 else 1
            self.log.yview_scroll(units, "units")
        except Exception as e:
            # Fallback: try direct scrolling
            try:
                self.log.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
        return "break"

    def set_error(self, message: str):
        self.error_label.config(text=message)

    def clear_error(self):
        self.error_label.config(text="")

    def cleanup(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.capture_running = False


if __name__ == "__main__":
    root = tk.Tk()
    app = BusArbitrationSimulator(root)
    root.mainloop()
