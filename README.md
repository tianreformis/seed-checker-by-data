# Seed Balance Scanner

A Python desktop GUI app that scans mnemonic seed phrases from any text file and checks wallet balances for BTC, ETH, SOL, and BNB.

## Features

- **Browse any file** — pick your seed phrase file with the Browse button or type the path
- **Select coins** — check/uncheck which coins to scan (BTC, ETH, SOL, BNB)
- **Local derivation** — derives wallet addresses using BIP44 (BTC, ETH, BNB) and SLIP10 ed25519 (SOL) — seeds never leave your machine
- **Balance API** — fetches live balances from public blockchain RPC endpoints
- **Modern dark UI** — customtkinter with sidebar, scrollable results table, and detail panel
- **Live progress** — progress bar, real-time status, found-count tracking
- **Row details** — click any result row to see the full seed phrase and all derived addresses
- **Export All** — saves full results (seed, addresses, balances) to a timestamped file
- **Save Funded Only** — exports only seeds with non-zero balance (one per line)

## Requirements

- Python 3.13+
- Windows / macOS / Linux

## Quick Start (Python)

```powershell
pip install -r requirements.txt
python main.py
```

If `coincurve` fails to build, install an older version:

```powershell
pip install coincurve==18.0.0
```

## Build Standalone Executable

The app can be packaged into a portable `.exe` (Windows) or `.deb` (Linux) that runs **without Python installed**.

### Windows (.exe)

```powershell
.\build_exe.bat
```

Output: `dist\SeedBalanceScanner.exe`

Double-click it to run — no Python or dependencies required.

### Linux (.deb)

```bash
chmod +x build_exe.sh
./build_exe.sh
```

Output: `dist/seed-balance-scanner_1.0.0_amd64.deb`

Install:

```bash
sudo dpkg -i dist/seed-balance-scanner_1.0.0_amd64.deb
seed-balance-scanner
```

## Usage

1. **Prepare a text file** — one mnemonic seed phrase per line (12, 18, or 24 words):

```
abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art
acid vintage artwork krypton gospel fossil glance frequent solid beyond exile bachelor
```

2. **Launch the app** — either `python main.py` or double-click the built executable.

3. **In the GUI:**
   - **File** — Click **Browse** to select your seed phrase file, or type the path directly in the entry box
   - **Coins** — Check or uncheck which coins to scan
   - **Start** — Click **Start Scan** to begin
   - **Progress** — Watch live progress per seed. Rows turn green when a non-zero balance is found
   - **Details** — Click any row to see the full seed, all derived addresses, and balances in the **Details** panel
   - **Export All** — Saves a complete report (seed, addresses, balances for every seed)
   - **Save Funded Only** — Saves only seeds that have a non-zero balance (one phrase per line)

## Coin Details

| Coin | Derivation Path | Curve | Balance API |
|---|---|---|---|
| BTC | `m/44'/0'/0'/0/0` | secp256k1 | blockchain.info |
| ETH | `m/44'/60'/0'/0/0` | secp256k1 | public Ethereum RPC |
| SOL | `m/44'/501'/0'/0'` | ed25519 | Solana public RPC |
| BNB | `m/44'/60'/0'/0/0` | secp256k1 | BSC public RPC |

> ETH and BNB share the same derivation path (coin type 60) and will produce the same address.

## Output Files

| Button | File | Contents |
|---|---|---|
| Export All | `results_YYYYMMDD_HHMMSS.txt` | Full report: seed, addresses, balances for every seed |
| Save Funded Only | `funded_YYYYMMDD_HHMMSS.txt` | Only seeds with non-zero balance (one per line) |

## Important Notes

- **Security:** All address derivation happens locally on your machine. Seed phrases are not sent over the network — only derived public addresses are sent to public RPC endpoints for balance queries.
- **Rate limits:** The public RPC endpoints may have rate limits. The app includes a 500ms delay between each coin check to be respectful.
- **APIs:** If an API endpoint fails (timeout, rate limit, maintenance), that coin will show `ERR` for the affected seed. You can retry later.

## File Structure

```
seed-checker-by-data/
├── data.txt            # Input: seed phrases (one per line)
├── main.py             # GUI application source
├── requirements.txt    # Python dependencies
├── build_exe.bat       # Windows build script (.exe)
├── build_exe.sh        # Linux build script (.deb)
├── dist/               # Build output directory
│   ├── SeedBalanceScanner.exe
│   └── seed-balance-scanner_1.0.0_amd64.deb
└── README.md           # This file
```
