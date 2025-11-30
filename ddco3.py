import tkinter as tk
import threading
import time
import random

running = False

class BusArbitrationSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Bus Arbitration Simulator - Fixed Layout")
        self.root.geometry("1150x600")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=1150, height=500, bg="white")
        self.canvas.pack()

        # Devices
        self.device_labels = ["Device 1", "Device 2", "Device n"]
        self.device_count = len(self.device_labels)

        # Positions
        self.arbiter_x, self.arbiter_y = 200, 300
        self.device_start_x, self.device_y = 650, 280  # moved left to fit
        self.device_spacing = 150
        self.bus_y = 100

        self.draw_static_components()

        # Start/Stop Buttons
        self.start_btn = tk.Button(root, text="START", font=("Arial", 14), command=self.start)
        self.start_btn.place(x=450, y=560)
        self.stop_btn = tk.Button(root, text="STOP", font=("Arial", 14), command=self.stop)
        self.stop_btn.place(x=600, y=560)

        # Log box with scrollbar
        frame = tk.Frame(root)
        frame.place(x=10, y=510, width=1130, height=50)

        self.scrollbar = tk.Scrollbar(frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log = tk.Text(frame, width=130, height=4, font=("Consolas", 10), yscrollcommand=self.scrollbar.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH)

        self.scrollbar.config(command=self.log.yview)

    def draw_static_components(self):
        # Bus line at top
        self.canvas.create_line(50, self.bus_y, 1100, self.bus_y, width=3, fill="black")
        self.canvas.create_text(150, self.bus_y-20, text="BUS Busy", font=("Arial", 12, "bold"))
        self.canvas.create_text(400, self.bus_y-20, text="BUS Request", font=("Arial", 12, "bold"))
        self.canvas.create_text(700, self.bus_y-20, text="BUS Grant", font=("Arial", 12, "bold"))
        self.canvas.create_text(1000, self.bus_y-20, text="Address", font=("Arial", 12, "bold"))

        # Arbiter box
        self.arbiter_box = self.canvas.create_rectangle(
            self.arbiter_x-70, self.arbiter_y-60,
            self.arbiter_x+70, self.arbiter_y+60,
            fill="lightgray", outline="black", width=3
        )
        self.canvas.create_text(self.arbiter_x, self.arbiter_y, text="Bus Arbiter", font=("Arial", 16, "bold"))

        # Device boxes
        self.device_boxes = []
        for i in range(self.device_count):
            x = self.device_start_x + i*self.device_spacing
            box = self.canvas.create_rectangle(
                x-60, self.device_y-40, x+60, self.device_y+40,
                fill="lightgray", outline="black", width=3
            )
            self.canvas.create_text(x, self.device_y, text=self.device_labels[i], font=("Arial", 14, "bold"))
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
        while running:
            requests = [random.choice([True, False]) for _ in range(self.device_count)]
            requesting_devices = [self.device_labels[i] for i, req in enumerate(requests) if req]

            winner_index = None
            for i, req in enumerate(requests):
                if req:
                    winner_index = i
                    break

            self.update_colors(requests, winner_index)

            if requesting_devices:
                if len(requesting_devices) > 1:
                    self.log_message(f"Multiple devices requesting: {', '.join(requesting_devices)}.\n")
                self.log_message(f"Bus granted to: {self.device_labels[winner_index]} (highest priority).\n")

                data = random.randint(1, 255)
                self.animate_data_packet(winner_index, data)
            else:
                self.log_message("No devices requested bus. Bus idle.\n")

            time.sleep(2)

        self.reset_colors()

    def update_colors(self, requests, winner_index):
        for i, box in enumerate(self.device_boxes):
            if winner_index == i:
                self.canvas.itemconfig(box, fill="lightgreen")
            elif requests[i]:
                self.canvas.itemconfig(box, fill="yellow")
            else:
                self.canvas.itemconfig(box, fill="lightgray")

        if winner_index is not None:
            self.canvas.itemconfig(self.arbiter_box, fill="lightgreen")
        else:
            self.canvas.itemconfig(self.arbiter_box, fill="lightgray")

    def reset_colors(self):
        for box in self.device_boxes:
            self.canvas.itemconfig(box, fill="lightgray")
        self.canvas.itemconfig(self.arbiter_box, fill="lightgray")

    def animate_data_packet(self, winner_index, data):
        x1, y1, x2, y2 = self.canvas.coords(self.device_boxes[winner_index])
        device_center_x = (x1+x2)/2
        device_top_y = y1

        packet_radius = 12
        packet = self.canvas.create_oval(
            device_center_x-packet_radius, device_top_y-2*packet_radius,
            device_center_x+packet_radius, device_top_y,
            fill="blue"
        )
        data_text = self.canvas.create_text(device_center_x, device_top_y-packet_radius, text=str(data), fill="white", font=("Arial", 10, "bold"))

        steps = 40
        dy = (device_top_y - self.bus_y + 20)/steps
        for _ in range(steps):
            if not running:
                break
            self.canvas.move(packet, 0, -dy)
            self.canvas.move(data_text, 0, -dy)
            self.root.update()
            time.sleep(0.03)

        self.canvas.delete(packet)
        self.canvas.delete(data_text)

    def log_message(self, msg):
        self.log.insert(tk.END, msg)
        self.log.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = BusArbitrationSimulator(root)
    root.mainloop()
