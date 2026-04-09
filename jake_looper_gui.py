import os
import math
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from threading import Thread
import re
import signal
import time
import shutil
import sys


def _resolve_tool(name: str):
    """Prefer PATH; then same folder as the script or frozen exe (portable `jakelooper/` layout)."""
    found = shutil.which(name)
    if found:
        return found
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    exe_name = f"{name}.exe" if os.name == "nt" else name
    candidate = base / exe_name
    if candidate.is_file():
        return str(candidate)
    return None


FFMPEG_PATH = _resolve_tool("ffmpeg")
FFPROBE_PATH = _resolve_tool("ffprobe")
TARGETS = {f"{i} Hours": i*3600 for i in range(1, 11)}

class VideoLooperApp:
    def __init__(self, master):
        self.master = master
        master.title("Jake Looper - MP4 Video Looper")
        master.geometry("1000x700")

        # -----------------------------
        # Runtime selection
        # -----------------------------
        tk.Label(master, text="Select target runtime:").pack(pady=5)
        self.target_var = tk.StringVar(value="3 Hours")
        runtime_frame = tk.Frame(master)
        runtime_frame.pack(pady=5)
        for key in TARGETS.keys():
            rb = tk.Radiobutton(runtime_frame, text=key, variable=self.target_var,
                                value=key, command=self.update_looped_durations)
            rb.pack(side=tk.LEFT, padx=3)

        # -----------------------------
        # File buttons
        # -----------------------------
        file_button_frame = tk.Frame(master)
        file_button_frame.pack(pady=5)
        tk.Button(file_button_frame, text="Add MP4 File(s)", command=self.select_files).pack(side=tk.LEFT, padx=5)
        tk.Button(file_button_frame, text="Clear File List", command=self.clear_file_list).pack(side=tk.LEFT, padx=5)

        # -----------------------------
        # Table container
        # -----------------------------
        table_container = tk.Frame(master)
        table_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(table_container, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(table_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollable_frame = tk.Frame(self.canvas)
        self.canvas_frame_window = self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="n")

        def resize_canvas(event):
            self.canvas.itemconfig(self.canvas_frame_window, width=event.width)

        self.canvas.bind("<Configure>", resize_canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # -----------------------------
        # Table headers
        # -----------------------------
        headers = ["File Name", "Original Duration", "Target Runtime", "Looped Duration", "Status", "Progress", "Remove"]
        widths = [25, 15, 12, 15, 10, 20, 10]
        for col, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(self.scrollable_frame, text=h, width=w, anchor="center",
                     font=("Arial", 10, "bold"), borderwidth=1, relief="raised")\
                .grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        for col in range(len(headers)):
            self.scrollable_frame.grid_columnconfigure(col, weight=1)

        # -----------------------------
        # Output folder
        # -----------------------------
        output_frame = tk.Frame(master)
        output_frame.pack(pady=5)
        tk.Label(output_frame, text="Output Folder: ").pack(side=tk.LEFT)
        self.output_label = tk.Label(output_frame, text="Not selected", fg="blue", cursor="hand2")
        self.output_label.pack(side=tk.LEFT)
        self.output_label.bind("<Button-1>", self.open_output_folder)
        tk.Button(output_frame, text="Select Output Folder", command=self.select_output_folder).pack(side=tk.LEFT, padx=5)

        # -----------------------------
        # Start button & status
        # -----------------------------
        self.start_btn = tk.Button(master, text="Start Looping", command=self.start_looping)
        self.start_btn.pack(pady=5)
        self.status_label = tk.Label(master, text="", fg="green")
        self.status_label.pack(pady=5)

        # -----------------------------
        # Variables
        # -----------------------------
        self.video_files = []
        self.output_folder = None
        self.video_rows = []
        self.processes = {}  # Track ffmpeg processes by file path

        # -----------------------------
        # Progress bar style for stopped videos
        # -----------------------------
        self.style = ttk.Style()
        self.style.configure("red.Horizontal.TProgressbar", foreground='red', background='red')

    # -----------------------------
    # File selection
    # -----------------------------
    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("MP4 files", "*.mp4")])
        if files:
            for f in files:
                path_obj = Path(f)
                # Check if the video is already in the table
                existing_row = next((r for r in self.video_rows if r["path"] == path_obj), None)
                if existing_row:
                    # Reset status if previously completed or stopped
                    existing_row["status_label"].config(text="Pending", fg="blue")
                    existing_row["progress_bar"]["value"] = 0
                    existing_row["stop_flag"] = False
                    continue  # skip adding a new row
                # Otherwise, add as a new row (only append if we can read duration successfully)
                if self.add_video_row(path_obj):
                    self.video_files.append(path_obj)


    def add_video_row(self, path_obj):
        orig_duration = self.get_video_duration(path_obj)
        if orig_duration is None:
            return False
        if orig_duration <= 0:
            messagebox.showerror("Error", f"Could not determine a valid duration for:\n{path_obj}")
            return False
        looped_duration = self.calculate_looped_duration(orig_duration)

        row_index = len(self.video_rows) + 1
        name_label = tk.Label(self.scrollable_frame, text=path_obj.name, width=25, anchor="center")
        name_label.grid(row=row_index, column=0, padx=2, pady=2)
        orig_label = tk.Label(self.scrollable_frame, text=self.format_time(orig_duration), width=15, anchor="center")
        orig_label.grid(row=row_index, column=1, padx=2, pady=2)
        target_label = tk.Label(self.scrollable_frame, text=self.target_var.get(), width=12, anchor="center")
        target_label.grid(row=row_index, column=2, padx=2, pady=2)
        looped_label = tk.Label(self.scrollable_frame, text=self.format_time(looped_duration), width=15, anchor="center")
        looped_label.grid(row=row_index, column=3, padx=2, pady=2)
        status_label = tk.Label(self.scrollable_frame, text="Pending", width=10, fg="blue", anchor="center")
        status_label.grid(row=row_index, column=4, padx=2, pady=2)
        pb = ttk.Progressbar(self.scrollable_frame, orient="horizontal", length=150, mode="determinate")
        pb.grid(row=row_index, column=5, padx=2, pady=2)

        remove_btn = tk.Button(self.scrollable_frame, text="Remove", width=8)
        remove_btn.grid(row=row_index, column=6, padx=2, pady=2)
        remove_btn.config(command=lambda rb=remove_btn, path=path_obj: self.remove_or_stop(rb, path_obj))

        self.video_rows.append({
            "path": path_obj,
            "name_label": name_label,
            "orig_label": orig_label,
            "target_label": target_label,
            "looped_label": looped_label,
            "status_label": status_label,
            "progress_bar": pb,
            "remove_btn": remove_btn,
            "orig_duration": orig_duration,
            "looped_duration": looped_duration,
            "stop_flag": False  # <-- Stop flag added
        })
        return True

    # -----------------------------
    # Remove or Stop handler
    # -----------------------------
    def remove_or_stop(self, button, path_obj):
        row = next(r for r in self.video_rows if r["path"] == path_obj)
        proc = self.processes.get(path_obj)
        output_file = None
        if self.output_folder:
            output_file = self.output_folder / f"{path_obj.stem}_{self.target_var.get().replace(' ','')}.mp4"

        # If currently processing, stop immediately and remove partial file
        if proc and proc.poll() is None:
            row["stop_flag"] = True
            try:
                proc.terminate()  # Stop ffmpeg immediately
            except:
                pass
            row["status_label"].config(text="Stopped", fg="red")
            row["progress_bar"].config(style="red.Horizontal.TProgressbar")
            # Try deleting partial file immediately if output folder exists
            try:
                if output_file and output_file.exists():
                    output_file.unlink()
            except:
                pass
            return

        # If already completed or stopped, just remove row
        self.remove_row(path_obj, delete_output=False)

    # -----------------------------
    # Remove row
    # -----------------------------
    def remove_row(self, path_obj, delete_output=True):
        proc = self.processes.get(path_obj)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except:
                pass

        output_file = None
        if self.output_folder:
            output_file = self.output_folder / f"{path_obj.stem}_{self.target_var.get().replace(' ','')}.mp4"

        if delete_output and output_file and output_file.exists():
            try:
                output_file.unlink()
            except:
                pass

        if path_obj in self.processes:
            del self.processes[path_obj]

        for row in self.video_rows:
            if row["path"] == path_obj:
                for widget in ["name_label","orig_label","target_label","looped_label","status_label","progress_bar","remove_btn"]:
                    row[widget].destroy()
                self.video_rows.remove(row)
                self.video_files.remove(path_obj)
                break

        for idx, row in enumerate(self.video_rows):
            r = idx + 1
            row["name_label"].grid(row=r)
            row["orig_label"].grid(row=r)
            row["target_label"].grid(row=r)
            row["looped_label"].grid(row=r)
            row["status_label"].grid(row=r)
            row["progress_bar"].grid(row=r)
            row["remove_btn"].grid(row=r)

    # -----------------------------
    # Clear file list
    # -----------------------------
    # -----------------------------
    def clear_file_list(self):
        for row in self.video_rows[:]:
            path_obj = row["path"]
            proc = self.processes.get(path_obj)
            output_file = None
            if self.output_folder:
                output_file = self.output_folder / f"{path_obj.stem}_{self.target_var.get().replace(' ','')}.mp4"

            # If processing, stop ffmpeg immediately and delete partial file after it exits
            if proc and proc.poll() is None:
                row["stop_flag"] = True
                try:
                    proc.terminate()
                except:
                    pass
                row["status_label"].config(text="Stopped", fg="red")
                row["progress_bar"].config(style="red.Horizontal.TProgressbar")
                try:
                    proc.wait()  # <-- wait for ffmpeg to fully exit
                    if output_file and output_file.exists():
                        output_file.unlink()
                except:
                    pass

            # Remove row from table and lists
            self.remove_row(path_obj, delete_output=False)

        self.video_rows.clear()
        self.video_files.clear()
        self.status_label.config(text="")


    # -----------------------------
    # Output folder
    # -----------------------------
    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = Path(folder)
            self.output_label.config(text=str(self.output_folder))

    def open_output_folder(self, event=None):
        if self.output_folder and self.output_folder.exists():
            os.startfile(self.output_folder)

    # -----------------------------
    # Video duration & time formatting
    # -----------------------------
    def get_video_duration(self, video_path):
        # Prefer ffprobe (fast + reliable). If it doesn't exist, fall back to parsing ffmpeg output.
        if FFPROBE_PATH:
            try:
                result = subprocess.run(
                    [FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of",
                     "default=noprint_wrappers=1:nokey=1", str(video_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW  # suppress CMD window
                )
                out = result.stdout.strip()
                return float(out) if out else None
            except (FileNotFoundError, ValueError):
                pass

        if not FFMPEG_PATH:
            return None

        # Fallback: ffmpeg writes "Duration: 00:00:12.34, ..." to stderr.
        try:
            proc = subprocess.run(
                [FFMPEG_PATH, "-i", str(video_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # suppress CMD window
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
            if not m:
                return None
            h = int(m.group(1))
            mm = int(m.group(2))
            s = float(m.group(3))
            return h * 3600 + mm * 60 + s
        except (FileNotFoundError, ValueError):
            return None

    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def calculate_looped_duration(self, orig_duration):
        target_sec = TARGETS[self.target_var.get()]
        loops_needed = math.ceil(target_sec / orig_duration)
        return loops_needed * orig_duration

    def update_looped_durations(self):
        for row in self.video_rows:
            row["looped_duration"] = self.calculate_looped_duration(row["orig_duration"])
            row["target_label"].config(text=self.target_var.get())
            row["looped_label"].config(text=self.format_time(row["looped_duration"]))

    # -----------------------------
    # Looping videos
    # -----------------------------
    def loop_video_realtime(self, video_path, loops, output_path, progress_bar, status_label, button):
        list_file = output_path.parent / "list.txt"
        with open(list_file, "w") as f:
            for _ in range(loops):
                f.write(f"file '{video_path.resolve()}'\n")

        total_duration = loops * self.get_video_duration(video_path)

        process = subprocess.Popen(
            [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i",
             str(list_file), "-c", "copy", str(output_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW  # <- suppress CMD window
        )

        self.processes[video_path] = process
        row = next(r for r in self.video_rows if r["path"] == video_path)
        button.config(text="Stop")

        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')

        while True:
            if row["stop_flag"]:
                try:
                    process.terminate()
                except:
                    pass
                break
            line = process.stderr.readline()
            if not line:
                break
            match = time_pattern.search(line)
            if match:
                hours = float(match.group(1))
                minutes = float(match.group(2))
                seconds = float(match.group(3))
                current_time = hours*3600 + minutes*60 + seconds
                progress_value = min(current_time / total_duration * 100, 100)
                progress_bar["value"] = progress_value
                self.master.update_idletasks()

        process.wait()
        list_file.unlink()

        # If stopped, delete partial file
        if row["stop_flag"]:
            progress_bar.config(style="red.Horizontal.TProgressbar")
            status_label.config(text="Stopped", fg="red")
            if output_path.exists():
                try:
                    output_path.unlink()
                except:
                    pass
        else:
            progress_bar["value"] = 100
            status_label.config(text="Completed", fg="green")

        button.config(text="Remove")
        if video_path in self.processes:
            del self.processes[video_path]

    def process_videos(self):
        if not FFMPEG_PATH:
            messagebox.showerror(
                "Error",
                "ffmpeg was not found.\n\nInstall ffmpeg and make sure it is available in your PATH, then try again."
            )
            return
        if not self.video_rows:
            messagebox.showerror("Error", "Please select MP4 files to process!")
            return
        if not self.output_folder:
            messagebox.showerror("Error", "Please select an output folder!")
            return

        # Remove old completed or stopped videos before starting new looping
        for row in self.video_rows[:]:
            status = row["status_label"].cget("text")
            if status in ("Completed", "Stopped"):
                self.remove_row(row["path"], delete_output=False)

        for idx, row in enumerate(self.video_rows):
            path_obj = row["path"]
            loops_needed = math.ceil(TARGETS[self.target_var.get()] / row["orig_duration"])
            output_file = self.output_folder / f"{path_obj.stem}_{self.target_var.get().replace(' ','')}.mp4"
            row["status_label"].config(text="Processing", fg="orange")
            self.status_label.config(text=f"Processing {idx+1}/{len(self.video_rows)}: {path_obj.name}")
            self.master.update_idletasks()
            self.loop_video_realtime(path_obj, loops_needed, output_file, row["progress_bar"], row["status_label"], row["remove_btn"])

        # Count Completed and Stopped videos
        completed_count = sum(1 for r in self.video_rows if r["status_label"].cget("text") == "Completed")
        stopped_count = sum(1 for r in self.video_rows if r["status_label"].cget("text") == "Stopped")

        self.status_label.config(text=f"Processing finished: {completed_count} Completed, {stopped_count} Stopped")
        messagebox.showinfo("Done", f"Looping finished!\n\nCompleted: {completed_count}\nStopped: {stopped_count}")

    def start_looping(self):
        thread = Thread(target=self.process_videos)
        thread.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoLooperApp(root)
    root.mainloop()
