import customtkinter as ctk
import threading
import queue
import time
import requests
import json
import os
import sys
import hashlib
import hmac
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from tkinter import messagebox

try:
    from mnemonic import Mnemonic as MnemonicLib
    MNEMONIC_OK = True
except ImportError:
    MNEMONIC_OK = False

try:
    import base58
    BASE58_OK = True
except ImportError:
    BASE58_OK = False

try:
    from coincurve import PrivateKey, PublicKey
    COINCURVE_OK = True
except ImportError:
    COINCURVE_OK = False

try:
    from Crypto.Hash import keccak, RIPEMD160
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

try:
    from nacl.bindings import crypto_sign_seed_keypair
    NACL_OK = True
except ImportError:
    NACL_OK = False


COINS = ["BTC", "ETH", "SOL", "BNB"]
COIN_COLORS = {
    "BTC": "#F7931A",
    "ETH": "#627EEA",
    "SOL": "#14F195",
    "BNB": "#F3BA2F",
}

RPC_ENDPOINTS = {
    "ETH": "https://eth-mainnet.public.blastapi.io",
    "SOL": "https://api.mainnet-beta.solana.com",
    "BNB": "https://bsc-dataseed.binance.org",
}

DATA_FILE = "data.txt"

SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HARDENED = 0x80000000

COIN_PATHS = {
    "BTC": "m/44'/0'/0'/0/0",
    "ETH": "m/44'/60'/0'/0/0",
    "SOL": "m/44'/501'/0'/0'",
    "BNB": "m/44'/60'/0'/0/0",
}


def load_seeds(filepath: str) -> List[str]:
    seeds = []
    if not os.path.exists(filepath):
        return seeds
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line[0].isdigit() and len(line.split()) >= 12:
                seeds.append(line)
    return seeds


def parse_bip32_path(path: str) -> List[int]:
    elements = path.split("/")
    if elements[0] == "m":
        elements = elements[1:]
    parsed = []
    for elem in elements:
        hardened = elem.endswith("'")
        idx = int(elem.rstrip("'"))
        parsed.append(idx | HARDENED if hardened else idx)
    return parsed


def seed_from_mnemonic(phrase: str) -> bytes:
    mnemo = MnemonicLib("english")
    return mnemo.to_seed(phrase)


def bip32_secp256k1(seed_bytes: bytes, path: str) -> bytes:
    if not COINCURVE_OK:
        raise RuntimeError("coincurve not available")
    I = hmac.new(b"Bitcoin seed", seed_bytes, hashlib.sha512).digest()
    priv = I[:32]
    chain = I[32:]

    for idx in parse_bip32_path(path):
        if idx & HARDENED:
            data = b"\x00" + priv + idx.to_bytes(4, "big")
        else:
            pub = PrivateKey(priv).public_key
            data = pub.format(compressed=True) + idx.to_bytes(4, "big")

        I = hmac.new(chain, data, hashlib.sha512).digest()
        tweak = I[:32]
        chain = I[32:]

        priv_int = int.from_bytes(priv, "big")
        tweak_int = int.from_bytes(tweak, "big")
        priv = ((priv_int + tweak_int) % SECP256K1_N).to_bytes(32, "big")

    return priv


def slip10_ed25519(seed_bytes: bytes, path: str) -> bytes:
    I = hmac.new(b"ed25519 seed", seed_bytes, hashlib.sha512).digest()
    priv = I[:32]
    chain = I[32:]

    for idx in parse_bip32_path(path):
        if not (idx & HARDENED):
            raise ValueError("ed25519 only supports hardened derivation")
        data = b"\x00" + priv + idx.to_bytes(4, "big")
        I = hmac.new(chain, data, hashlib.sha512).digest()
        priv = I[:32]
        chain = I[32:]

    return priv


def btc_address(priv_key: bytes) -> str:
    if not CRYPTO_OK:
        return "crypto missing"
    pub = PrivateKey(priv_key).public_key
    pub_bytes = pub.format(compressed=True)
    sha = hashlib.sha256(pub_bytes).digest()
    ripe = RIPEMD160.new(sha).digest()
    versioned = b"\x00" + ripe
    checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
    return base58.b58encode(versioned + checksum).decode()


def eth_address(priv_key: bytes) -> str:
    if not CRYPTO_OK:
        return "crypto missing"
    pub = PrivateKey(priv_key).public_key
    pub_bytes = pub.format(compressed=False)
    pub_no_prefix = pub_bytes[1:]
    k = keccak.new(digest_bits=256)
    k.update(pub_no_prefix)
    addr_bytes = k.digest()[-20:]
    return "0x" + addr_bytes.hex()


def sol_address(ed25519_priv_key: bytes) -> str:
    if not NACL_OK:
        return "nacl missing"
    pub_key, _ = crypto_sign_seed_keypair(ed25519_priv_key)
    return base58.b58encode(pub_key).decode()


def derive_address(mnemonic_phrase: str, coin: str) -> Optional[str]:
    try:
        seed = seed_from_mnemonic(mnemonic_phrase)
        path = COIN_PATHS[coin]

        if coin == "SOL":
            priv_key = slip10_ed25519(seed, path)
            return sol_address(priv_key)
        else:
            priv_key = bip32_secp256k1(seed, path)
            if coin == "BTC":
                return btc_address(priv_key)
            else:
                return eth_address(priv_key)
    except Exception:
        return None


def get_balance(coin: str, address: str) -> float:
    try:
        if coin == "BTC":
            url = f"https://blockchain.info/balance?active={address}"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get(address, {}).get("final_balance", 0) / 1e8
        elif coin == "ETH":
            payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [address, "latest"], "id": 1}
            resp = requests.post(RPC_ENDPOINTS["ETH"], json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "result" in data:
                return int(data["result"], 16) / 1e18
        elif coin == "SOL":
            payload = {"jsonrpc": "2.0", "method": "getBalance", "params": [address], "id": 1}
            resp = requests.post(RPC_ENDPOINTS["SOL"], json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "result" in data:
                return data["result"]["value"] / 1e9
        elif coin == "BNB":
            payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [address, "latest"], "id": 1}
            resp = requests.post(RPC_ENDPOINTS["BNB"], json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "result" in data:
                return int(data["result"], 16) / 1e18
    except Exception:
        pass
    return -1.0


def truncate_seed(seed: str, max_words: int = 4) -> str:
    words = seed.split()
    if len(words) <= max_words + 1:
        return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")
    return " ".join(words[:max_words]) + "..." + words[-1]


def format_balance(bal: float) -> str:
    if bal < 0:
        return "ERR"
    if bal == 0:
        return "0.0000"
    if bal < 0.0001:
        return f"{bal:.8f}"
    return f"{bal:.4f}"


class SeedScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Seed Balance Scanner")
        self.geometry("1200x780")
        self.minsize(1000, 650)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.seeds: List[str] = []
        self.results: List[dict] = []
        self.selected_row: Optional[int] = None

        self.scanning = False
        self.stop_flag = threading.Event()
        self.result_queue: queue.Queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None

        self.setup_ui()
        self.load_seed_file()

        self.after(200, self.process_queue)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self.setup_header()
        self.setup_content()
        self.setup_status_bar()

    def setup_header(self):
        header = ctk.CTkFrame(self, fg_color=("gray95", "gray10"), corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        header.pack_propagate(False)

        icon_label = ctk.CTkLabel(header, text="\U0001F50D", font=ctk.CTkFont(size=24), anchor="w")
        icon_label.grid(row=0, column=0, padx=(20, 5), pady=10)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")

        title = ctk.CTkLabel(title_frame, text="Seed Balance Scanner",
                              font=ctk.CTkFont(size=20, weight="bold"), anchor="w")
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(title_frame, text="Scan mnemonic seed phrases from data.txt for wallet balances",
                                font=ctk.CTkFont(size=12), text_color="gray", anchor="w")
        subtitle.pack(anchor="w")

        self.dep_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=11), anchor="e")
        self.dep_label.grid(row=0, column=2, padx=(5, 20), pady=10)
        self.check_dependencies()

    def check_dependencies(self):
        issues = []
        if not MNEMONIC_OK:
            issues.append("mnemonic")
        if not BASE58_OK:
            issues.append("base58")
        if not COINCURVE_OK:
            issues.append("coincurve")
        if not CRYPTO_OK:
            issues.append("pycryptodome")
        if not NACL_OK:
            issues.append("PyNaCl")
        if issues:
            self.dep_label.configure(text=f"\u26A0 Missing: {', '.join(issues)}", text_color="#ffaa00")
        else:
            self.dep_label.configure(text="\u2705 All dependencies loaded", text_color="#44cc44")

    def setup_content(self):
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=15, pady=(10, 5))
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.setup_sidebar(content)
        self.setup_main_panel(content)

    def setup_sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, fg_color=("gray85", "gray17"), corner_radius=12, width=260)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(4, weight=1)

        section_font = ctk.CTkFont(size=14, weight="bold")

        settings_header = ctk.CTkLabel(sidebar, text="Settings", font=section_font, anchor="w")
        settings_header.grid(row=0, column=0, padx=18, pady=(18, 8), sticky="ew")

        coin_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        coin_frame.grid(row=1, column=0, padx=18, pady=5, sticky="ew")

        coin_label = ctk.CTkLabel(coin_frame, text="Coins to scan:", font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        coin_label.pack(anchor="w", pady=(0, 6))

        coin_font = ctk.CTkFont(size=13)
        self.coin_vars = {}
        self.coin_checkboxes = {}
        for coin in COINS:
            f = ctk.CTkFrame(coin_frame, fg_color="transparent")
            f.pack(fill="x", pady=2)
            dot = ctk.CTkLabel(f, text="\u25CF", text_color=COIN_COLORS[coin], font=ctk.CTkFont(size=16))
            dot.pack(side="left", padx=(0, 6))
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(f, text=coin, variable=var, font=coin_font,
                                  border_width=2, checkbox_width=20, checkbox_height=20)
            cb.pack(side="left", fill="x", expand=True)
            self.coin_vars[coin] = var
            self.coin_checkboxes[coin] = cb

        sep1 = ctk.CTkFrame(sidebar, height=1, fg_color=("gray70", "gray30"))
        sep1.grid(row=2, column=0, padx=18, pady=12, sticky="ew")

        info_label = ctk.CTkLabel(sidebar, text="Data File", font=section_font, anchor="w")
        info_label.grid(row=3, column=0, padx=18, pady=(0, 5), sticky="ew")

        self.file_label = ctk.CTkLabel(sidebar, text="Loading...", font=ctk.CTkFont(size=12), anchor="w",
                                        text_color="gray")
        self.file_label.grid(row=4, column=0, padx=18, pady=(0, 10), sticky="nw")

        btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=18, pady=(5, 18), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self.start_btn = ctk.CTkButton(btn_frame, text="\u25B6  Start Scan", font=ctk.CTkFont(size=14, weight="bold"),
                                        height=42, corner_radius=8, fg_color="#1f6eb0", hover_color="#155a8a",
                                        command=self.start_scan)
        self.start_btn.grid(row=0, column=0, pady=(0, 6), sticky="ew")

        self.stop_btn = ctk.CTkButton(btn_frame, text="\u25A0  Stop", font=ctk.CTkFont(size=14, weight="bold"),
                                       height=38, corner_radius=8, fg_color="#a03030", hover_color="#802020",
                                       state="disabled", command=self.stop_scan)
        self.stop_btn.grid(row=1, column=0, pady=3, sticky="ew")

        self.export_btn = ctk.CTkButton(btn_frame, text="\u2B07  Export Results", font=ctk.CTkFont(size=13),
                                         height=34, corner_radius=8, fg_color="gray25", hover_color="gray35",
                                         state="disabled", command=self.export_results)
        self.export_btn.grid(row=2, column=0, pady=(6, 0), sticky="ew")

    def setup_main_panel(self, parent):
        main_panel = ctk.CTkFrame(parent, fg_color=("gray87", "gray18"), corner_radius=12)
        main_panel.grid(row=0, column=1, sticky="nsew")
        main_panel.grid_rowconfigure(0, weight=1)
        main_panel.grid_rowconfigure(1, weight=0)
        main_panel.grid_columnconfigure(0, weight=1)

        results_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        results_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 5))
        results_frame.grid_rowconfigure(1, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        results_header = ctk.CTkLabel(results_frame, text="Results", font=ctk.CTkFont(size=15, weight="bold"),
                                       anchor="w")
        results_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.setup_results_table(results_frame)
        self.setup_detail_panel(main_panel)

    def setup_results_table(self, parent):
        container = ctk.CTkFrame(parent, fg_color=("gray80", "gray20"), corner_radius=8)
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(container, fg_color="transparent", height=34)
        header_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(4, 0))
        header_frame.grid_propagate(False)

        self.cols = ["#", "Seed Phrase", "BTC", "ETH", "SOL", "BNB"]
        col_weights = [1, 4, 2, 2, 2, 2]
        self.header_labels = []

        for i, (col, w) in enumerate(zip(self.cols, col_weights)):
            header_frame.grid_columnconfigure(i, weight=w, minsize=50)
            lbl = ctk.CTkLabel(header_frame, text=col, font=ctk.CTkFont(size=12, weight="bold"),
                                text_color=("gray20", "gray80"))
            lbl.grid(row=0, column=i, padx=6, pady=4, sticky="w")
            self.header_labels.append(lbl)

        self.table_canvas = ctk.CTkScrollableFrame(container, fg_color=("gray83", "gray22"), corner_radius=6)
        self.table_canvas.grid(row=1, column=0, sticky="nsew", padx=2, pady=(2, 4))
        self.table_canvas.grid_columnconfigure(0, weight=1)

    def setup_detail_panel(self, parent):
        self.detail_frame = ctk.CTkFrame(parent, fg_color=("gray82", "gray16"), corner_radius=8, height=90)
        self.detail_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))
        self.detail_frame.grid_propagate(False)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(1, weight=1)

        detail_header = ctk.CTkLabel(self.detail_frame, text="Details",
                                      font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 0))

        self.detail_text = ctk.CTkLabel(self.detail_frame, text="Click a result row to see details",
                                         font=ctk.CTkFont(size=11), anchor="w", justify="left",
                                         text_color="gray")
        self.detail_text.grid(row=1, column=0, sticky="nsw", padx=12, pady=(2, 6))

    def setup_status_bar(self):
        status_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=0, height=48)
        status_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=(5, 0))
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.pack_propagate(False)

        self.progress = ctk.CTkProgressBar(status_frame, height=10, corner_radius=5,
                                            fg_color=("gray70", "gray30"), progress_color="#1f6eb0")
        self.progress.grid(row=0, column=0, padx=(15, 10), pady=6, sticky="ew", columnspan=4)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(status_frame, text="Ready. Load seeds from data.txt",
                                          font=ctk.CTkFont(size=12), anchor="w", text_color="gray")
        self.status_label.grid(row=1, column=0, padx=(15, 5), pady=(0, 6), sticky="w")

        self.found_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12), anchor="e")
        self.found_label.grid(row=1, column=1, padx=(5, 5), pady=(0, 6), sticky="e")

        self.count_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12), anchor="e",
                                         text_color="gray")
        self.count_label.grid(row=1, column=2, padx=(5, 15), pady=(0, 6), sticky="e")

    def load_seed_file(self):
        data_path = DATA_FILE
        if not os.path.exists(data_path):
            data_path = os.path.join(os.path.dirname(__file__), DATA_FILE)
        self.seeds = load_seeds(data_path)
        count = len(self.seeds)
        self.file_label.configure(text=f"{os.path.basename(DATA_FILE)}\n{count} seed{'' if count == 1 else 's'} loaded")
        if count == 0:
            self.status_label.configure(text="\u26A0 No valid seed phrases found in data.txt")
        else:
            self.status_label.configure(text=f"Ready to scan {count} seed{'' if count == 1 else 's'}")

    def clear_table(self):
        for w in self.table_canvas.winfo_children():
            w.destroy()

    def populate_table(self):
        self.clear_table()
        for i, r in enumerate(self.results):
            row_frame = ctk.CTkFrame(self.table_canvas, fg_color="transparent", height=30)
            row_frame.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            row_frame.grid_columnconfigure(0, weight=0)
            row_frame.grid_columnconfigure(1, weight=3)
            for j in range(2, len(self.cols)):
                row_frame.grid_columnconfigure(j, weight=1)

            row_frame.bind("<Button-1>", lambda e, idx=i: self.on_row_click(idx))
            for child in row_frame.winfo_children():
                child.bind("<Button-1>", lambda e, idx=i: self.on_row_click(idx))

            has_balance = any(r["balances"].get(c, 0) > 0 for c in COINS)
            bg = ("#e8ffe8", "#1a3a1a") if has_balance else (
                ("gray85", "gray25") if i % 2 == 0 else ("gray82", "gray20")
            )

            row_bg = ctk.CTkLabel(row_frame, text="", fg_color=bg, corner_radius=4)
            row_bg.place(relx=0, rely=0, relwidth=1, relheight=1)
            row_bg.bind("<Button-1>", lambda e, idx=i: self.on_row_click(idx))

            vals = [str(r["index"]), truncate_seed(r["mnemonic"], 3)]
            for c in COINS:
                vals.append(format_balance(r["balances"].get(c, 0)))

            for j, v in enumerate(vals):
                txt_color = None
                if j >= 2:
                    bal = r["balances"].get(COINS[j - 2], 0)
                    if bal > 0:
                        txt_color = "#44dd44"
                    elif bal < 0:
                        txt_color = "#ff6644"
                lbl = ctk.CTkLabel(row_frame, text=v, font=ctk.CTkFont(size=11),
                                    text_color=txt_color, anchor="w")
                lbl.grid(row=0, column=j, padx=6, pady=3, sticky="w")
                lbl.bind("<Button-1>", lambda e, idx=i: self.on_row_click(idx))

            for j in range(len(self.cols)):
                row_frame.grid_columnconfigure(j, weight=[0.4, 3, 1, 1, 1, 1][j] if j < 6 else 1)

    def on_row_click(self, idx):
        self.selected_row = idx
        r = self.results[idx]
        details = f"Seed: {r['mnemonic']}\n"
        for c in COINS:
            addr = r["addresses"].get(c, "N/A")
            bal = r["balances"].get(c, 0)
            details += f"{c}: {addr}  |  {format_balance(bal)} {c}\n"
        self.detail_text.configure(text=details.strip())

    def update_result_row(self, idx, coin, address, balance):
        if idx < len(self.results):
            self.results[idx]["addresses"][coin] = address
            self.results[idx]["balances"][coin] = balance
            self.results[idx]["status"] = "scanned"

    def start_scan(self):
        if self.scanning:
            return

        active_coins = [c for c in COINS if self.coin_vars[c].get()]
        if not active_coins:
            messagebox.showwarning("No Coins Selected", "Please select at least one coin to scan.")
            return
        if not self.seeds:
            messagebox.showwarning("No Seeds", "No seed phrases found in data.txt")
            return

        missing = []
        if not MNEMONIC_OK:
            missing.append("mnemonic")
        if not BASE58_OK:
            missing.append("base58")
        if not COINCURVE_OK:
            missing.append("coincurve")
        if not CRYPTO_OK:
            missing.append("pycryptodome")
        if not NACL_OK:
            missing.append("PyNaCl")
        if missing:
            messagebox.showerror("Missing Dependencies",
                                  f"pip install {' '.join(missing)}")
            return

        self.scanning = True
        self.stop_flag.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.export_btn.configure(state="disabled")

        self.results = []
        for i, seed in enumerate(self.seeds):
            self.results.append({
                "index": i + 1,
                "mnemonic": seed,
                "addresses": {},
                "balances": {},
                "status": "pending",
            })

        self.clear_table()
        self.populate_table()
        self.progress.set(0)
        self.status_label.configure(text="Starting scan...")
        self.found_label.configure(text="")
        self.count_label.configure(text="")

        self.worker_thread = threading.Thread(
            target=self.scan_worker,
            args=(active_coins,),
            daemon=True,
        )
        self.worker_thread.start()

    def stop_scan(self):
        if self.scanning:
            self.stop_flag.set()
            self.status_label.configure(text="Stopping scan...")

    def scan_worker(self, active_coins):
        total = len(self.seeds)
        found_count = 0

        for idx, seed_data in enumerate(self.results):
            if self.stop_flag.is_set():
                self.result_queue.put(("scan_done", {"stopped": True}))
                return

            seed = seed_data["mnemonic"]
            self.result_queue.put(("progress", {"current": idx + 1, "total": total, "seed": seed}))

            seed_has_balance = False
            for coin in active_coins:
                if self.stop_flag.is_set():
                    self.result_queue.put(("scan_done", {"stopped": True}))
                    return

                addr = derive_address(seed, coin)
                if addr:
                    balance = get_balance(coin, addr)
                    self.result_queue.put(("result", {
                        "idx": idx,
                        "coin": coin,
                        "address": addr,
                        "balance": balance,
                    }))
                    if balance > 0:
                        seed_has_balance = True
                else:
                    self.result_queue.put(("result", {
                        "idx": idx,
                        "coin": coin,
                        "address": "error",
                        "balance": -1.0,
                    }))

                time.sleep(0.5)

            if seed_has_balance:
                found_count += 1
            self.result_queue.put(("seed_done", {"idx": idx}))

        self.result_queue.put(("scan_done", {"stopped": False, "found": found_count, "total": total}))

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.result_queue.get_nowait()

                if msg_type == "progress":
                    current = data["current"]
                    total = data["total"]
                    seed = data["seed"]
                    pct = current / total if total > 0 else 0
                    self.progress.set(pct)
                    short = truncate_seed(seed, 2)
                    self.status_label.configure(text=f"Scanning {current}/{total}: {short}")
                    self.count_label.configure(text=f"{current}/{total}")

                elif msg_type == "result":
                    idx = data["idx"]
                    coin = data["coin"]
                    address = data["address"]
                    balance = data["balance"]
                    self.update_result_row(idx, coin, address, balance)
                    self.populate_table()
                    if balance > 0:
                        found = sum(
                            1 for r in self.results
                            if any(b > 0 for b in r["balances"].values())
                        )
                        self.found_label.configure(text=f"\U0001F4B0 Found: {found}")
                        self.on_row_click(idx)

                elif msg_type == "seed_done":
                    pass

                elif msg_type == "scan_done":
                    self.scanning = False
                    self.stop_btn.configure(state="disabled")
                    self.start_btn.configure(state="normal")
                    self.export_btn.configure(state="normal")

                    if data.get("stopped"):
                        self.status_label.configure(text="Scan stopped by user.")
                    else:
                        found = data.get("found", 0)
                        total = data.get("total", 0)
                        self.progress.set(1.0)
                        self.status_label.configure(
                            text=f"Scan complete. Scanned {total} seeds, found {found} wallet(s) with balance."
                        )
                        self.found_label.configure(text=f"\U0001F4B0 Found: {found}")
                        self.count_label.configure(text=f"{total}/{total}")

        except queue.Empty:
            pass

        self.after(200, self.process_queue)

    def export_results(self):
        if not self.results:
            return

        found = [r for r in self.results if any(b > 0 for b in r["balances"].values())]
        filename = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write("Seed Balance Scanner - Results\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total seeds scanned: {len(self.results)}\n")
            f.write(f"Wallets with balance: {len(found)}\n")
            f.write("=" * 80 + "\n\n")

            for r in self.results:
                line = f"Seed #{r['index']}: {r['mnemonic']}\n"
                for c in COINS:
                    addr = r["addresses"].get(c, "N/A")
                    bal = r["balances"].get(c, 0)
                    line += f"  {c}: {addr}  |  Balance: {format_balance(bal)}\n"
                line += "-" * 60 + "\n"
                f.write(line)

        self.status_label.configure(text=f"Results exported to {filename}")


if __name__ == "__main__":
    app = SeedScannerApp()
    app.mainloop()
