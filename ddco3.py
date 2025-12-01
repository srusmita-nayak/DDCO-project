import tkinter as tk
from tkinter import ttk
import threading
import time
import random

running = False

class BusArbitrationSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Arbitration Simulator - Professional Mode")
        self.root.geometry("1200x650")
        self.root.resizable(False, False)

        # Canvas for diagram
        self.canvas = tk.Canvas(root, width=1200, height=500, bg="#f5f5f5")
        self.canvas.pack()

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

        # Start/Stop buttons
        self.start_btn = tk.Button(root, text="START", font=("Arial", 14), command=self.start, bg="lightgreen")
        self.start_btn.place(x=400, y=560)
        self.stop_btn = tk.Button(root, text="STOP", font=("Arial", 14), command=self.stop, bg="red")
        self.stop_btn.place(x=550, y=560)

        # Arbitration Mode
        self.mode_label = tk.Label(root, text="Arbitration Mode:", font=("Arial", 12))
        self.mode_label.place(x=700, y=560)
        self.mode_var = tk.StringVar(value="Fixed Priority")
        self.mode_menu = ttk.Combobox(root, textvariable=self.mode_var, values=["Fixed Priority", "Round Robin", "Daisy Chain"], state="readonly", width=15)
        self.mode_menu.place(x=850, y=560)

        # Log box
        frame = tk.Frame(root)
        frame.place(x=10, y=510, width=1180, height=50)
        self.scrollbar = tk.Scrollbar(frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log = tk.Text(frame, width=140, height=4, font=("Consolas", 10), yscrollcommand=self.scrollbar.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH)
        self.scrollbar.config(command=self.log.yview)

        # For round-robin
        self.next_index = 0

    def draw_static_components(self):
        # Horizontal bus
        self.canvas.create_line(50, self.bus_y, 1150, self.bus_y, width=4, fill="black")
        self.canvas.create_text(100, self.bus_y-20, text="BUS Busy", font=("Arial", 12, "bold"))
        self.canvas.create_text(400, self.bus_y-20, text="BUS Request", font=("Arial", 12, "bold"))
        self.canvas.create_text(700, self.bus_y-20, text="BUS Grant", font=("Arial", 12, "bold"))
        self.canvas.create_text(1050, self.bus_y-20, text="Address/Data", font=("Arial", 12, "bold"))

        # Arbiter
        self.arbiter_box = self.canvas.create_rectangle(
            self.arbiter_x-50, self.arbiter_y-50, self.arbiter_x+50, self.arbiter_y+50,
            fill="#d9d9d9", outline="black", width=3
        )
        self.canvas.create_text(self.arbiter_x, self.arbiter_y, text="ARBITER", font=("Arial", 14, "bold"))

        # Devices
        self.device_boxes = []
        for i in range(self.device_count):
            x = self.device_start_x + i*self.device_spacing
            box = self.canvas.create_rectangle(
                x-50, self.device_y-40, x+50, self.device_y+40,
                fill="#d9d9d9", outline="black", width=3
            )
            self.canvas.create_text(x, self.device_y, text=self.device_labels[i], font=("Arial", 12, "bold"))
            self.device_boxes.append(box)

    def start(self):
        global running
        if not running:
            running = True
            threading.Thread(target=self.simulation_loop, daemon=True).start()
            self.log_message("Simulation started.\n")

    def stop(self):
        global running
        running = False
        self.log_message("Simulation stopped.\n")

    def simulation_loop(self):
        global running
        while running:
            # Generate requests
            requests = [random.choice([True, False]) for _ in range(self.device_count)]
            requesting_devices = [self.device_labels[i] for i, req in enumerate(requests) if req]

            # Determine winner
            winner_index = self.determine_winner(requests)

            # Update UI
            self.update_colors(requests, winner_index)

            if requesting_devices and winner_index is not None:
                self.log_message(f"Bus granted to {self.device_labels[winner_index]}.\n")
                data = random.randint(1, 255)
                self.animate_data_packet(winner_index, data)
            else:
                self.log_message("No requests. Bus idle.\n")

            time.sleep(2)

        self.reset_colors()

    def determine_winner(self, requests):
        mode = self.mode_var.get()
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
        return None

    def update_colors(self, requests, winner_index):
        # Arbiter color
        self.canvas.itemconfig(self.arbiter_box, fill="#a1d99b" if winner_index is not None else "#d9d9d9")
        # Device colors
        for i, box in enumerate(self.device_boxes):
            if winner_index == i:
                self.canvas.itemconfig(box, fill="#74c476")
            elif requests[i]:
                self.canvas.itemconfig(box, fill="#fdae6b")
            else:
                self.canvas.itemconfig(box, fill="#d9d9d9")

    def reset_colors(self):
        self.canvas.itemconfig(self.arbiter_box, fill="#d9d9d9")
        for box in self.device_boxes:
            self.canvas.itemconfig(box, fill="#d9d9d9")

    def animate_data_packet(self, winner_index, data):
        x1, y1, x2, y2 = self.canvas.coords(self.device_boxes[winner_index])
        start_x = (x1+x2)/2
        start_y = y1
        packet = self.canvas.create_rectangle(start_x-10, start_y-20, start_x+10, start_y, fill="#3182bd")
        text = self.canvas.create_text(start_x, start_y-10, text=str(data), fill="white", font=("Arial", 10, "bold"))

        steps = 50
        dy = (start_y - self.bus_y)/steps
        for _ in range(steps):
            if not running:
                break
            self.canvas.move(packet, 0, -dy)
            self.canvas.move(text, 0, -dy)
            self.root.update()
            time.sleep(0.02)

        self.canvas.delete(packet)
        self.canvas.delete(text)

    def log_message(self, msg):
        self.log.insert(tk.END, msg)
        self.log.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = BusArbitrationSimulator(root)
    root.mainloop()
