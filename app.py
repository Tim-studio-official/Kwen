import base64
import json
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

APP_TITLE = "Kwen Script Hub"
SPLASH_IMAGE = Path("img/kwenlogo.png")


@dataclass
class ScriptItem:
    name: str
    path: str
    branch: str
    download_url: str


class GitHubClient:
    BASE_API = "https://api.github.com"

    @staticmethod
    def _request_json(url: str):
        req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "KwenScriptHub"})
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def list_scripts(self, owner: str, repo: str, branch: str, folder: str):
        encoded_folder = quote(folder.strip("/"))
        url = f"{self.BASE_API}/repos/{owner}/{repo}/contents/{encoded_folder}?ref={quote(branch)}"
        data = self._request_json(url)
        if isinstance(data, dict) and data.get("type") == "file":
            data = [data]

        items = []
        for item in data:
            if item.get("type") == "file" and item.get("name", "").lower().endswith((".py", ".js", ".ts", ".sh", ".ps1", ".lua")):
                items.append(
                    ScriptItem(
                        name=item["name"],
                        path=item["path"],
                        branch=branch,
                        download_url=item["download_url"],
                    )
                )
        return items

    def read_script(self, download_url: str) -> str:
        req = Request(download_url, headers={"User-Agent": "KwenScriptHub"})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")


class KwenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x700")
        self.client = GitHubClient()
        self.scripts: list[ScriptItem] = []

        self._build_ui()
        self._show_splash()

    def _build_ui(self):
        control = ttk.Frame(self, padding=10)
        control.pack(fill="x")

        self.owner_var = tk.StringVar(value="octocat")
        self.repo_var = tk.StringVar(value="Hello-World")
        self.branch_var = tk.StringVar(value="master")
        self.folder_var = tk.StringVar(value="")

        fields = [
            ("Owner", self.owner_var),
            ("Repo", self.repo_var),
            ("Branch", self.branch_var),
            ("Scripts folder", self.folder_var),
        ]

        for idx, (label, var) in enumerate(fields):
            ttk.Label(control, text=label).grid(row=0, column=idx * 2, sticky="w", padx=(0, 4))
            ttk.Entry(control, textvariable=var, width=20).grid(row=0, column=idx * 2 + 1, sticky="ew", padx=(0, 10))

        control.columnconfigure(1, weight=1)
        control.columnconfigure(3, weight=1)
        control.columnconfigure(5, weight=1)
        control.columnconfigure(7, weight=1)

        ttk.Button(control, text="Load from branch", command=self.load_scripts).grid(row=0, column=8, padx=5)
        ttk.Button(control, text="Add to library", command=self.add_to_library).grid(row=0, column=9, padx=5)

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        ttk.Label(left, text="Store (GitHub branch scripts)").pack(anchor="w")
        self.store_list = tk.Listbox(left, height=20)
        self.store_list.pack(fill="both", expand=True)
        self.store_list.bind("<<ListboxSelect>>", self.preview_selected)

        ttk.Label(left, text="Library (saved locally)").pack(anchor="w", pady=(10, 0))
        self.library_list = tk.Listbox(left, height=10)
        self.library_list.pack(fill="both", expand=True)

        ttk.Label(right, text="Script preview").pack(anchor="w")
        self.preview = tk.Text(right, wrap="none")
        self.preview.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, padding=8).pack(fill="x")

    def _show_splash(self):
        if not SPLASH_IMAGE.exists():
            self.status.set("Splash image not found yet: img/kwenlogo.png")
            return

        try:
            img_data = base64.b64encode(SPLASH_IMAGE.read_bytes()).decode("ascii")
            image = tk.PhotoImage(data=img_data)
        except Exception as exc:
            self.status.set(f"Failed to load splash: {exc}")
            return

        splash = tk.Toplevel(self)
        splash.title("Welcome")
        splash.geometry("640x360")
        splash.overrideredirect(True)
        x = (self.winfo_screenwidth() - 640) // 2
        y = (self.winfo_screenheight() - 360) // 2
        splash.geometry(f"640x360+{x}+{y}")

        label = ttk.Label(splash, image=image)
        label.image = image
        label.pack(fill="both", expand=True)

        self.after(2000, splash.destroy)

    def load_scripts(self):
        owner = self.owner_var.get().strip()
        repo = self.repo_var.get().strip()
        branch = self.branch_var.get().strip()
        folder = self.folder_var.get().strip()
        if not (owner and repo and branch):
            messagebox.showwarning("Missing data", "Owner, repo and branch are required.")
            return

        try:
            self.scripts = self.client.list_scripts(owner, repo, branch, folder)
        except (HTTPError, URLError, TimeoutError) as exc:
            messagebox.showerror("Load error", f"Could not load scripts: {exc}")
            return

        self.store_list.delete(0, tk.END)
        for item in self.scripts:
            self.store_list.insert(tk.END, f"{item.name} ({item.branch})")

        self.status.set(f"Loaded {len(self.scripts)} script(s) from {owner}/{repo}@{branch}")

    def preview_selected(self, _event=None):
        selection = self.store_list.curselection()
        if not selection:
            return

        item = self.scripts[selection[0]]
        try:
            content = self.client.read_script(item.download_url)
        except (HTTPError, URLError, TimeoutError) as exc:
            messagebox.showerror("Preview error", f"Could not read script: {exc}")
            return

        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", content)

    def add_to_library(self):
        selection = self.store_list.curselection()
        if not selection:
            messagebox.showinfo("Nothing selected", "Select a script from store first.")
            return

        item = self.scripts[selection[0]]
        self.library_list.insert(tk.END, f"{item.name} — {item.path}")
        self.status.set(f"Added to library: {item.name}")


if __name__ == "__main__":
    app = KwenApp()
    app.mainloop()
