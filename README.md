# Seed Balance Scanner

A Python desktop GUI app that scans mnemonic seed phrases from `data.txt` and checks wallet balances for BTC, ETH, SOL, and BNB.

## Features

- Read seed phrases from `data.txt` (one phrase per line, 12+ words)
- Check/uncheck which coins to scan before starting
- Derives wallet addresses locally using BIP44 (BTC, ETH, BNB) and SLIP10 ed25519 (SOL)
- Fetches balances via public blockchain RPC APIs
- Modern dark-themed desktop UI (customtkinter)
- Progress bar, live status updates, found-count tracking
- Click any result row to see full seed phrase and all derived addresses
- Export results to a timestamped text file

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

Run the build script — it installs PyInstaller, bundles everything, and outputs a single `.exe`:

```powershell
.\build_exe.bat
```

Output: `dist\SeedBalanceScanner.exe`

Double-click the `.exe` to run — no Python or dependencies required. Place your `data.txt` next to the `.exe`.

### Linux (.deb)

```bash
chmod +x build_exe.sh
./build_exe.sh
```

The script builds a standalone binary and optionally creates a `.deb` package.

Output: `dist/seed-balance-scanner_1.0.0_amd64.deb`

Install with:

```bash
sudo dpkg -i dist/seed-balance-scanner_1.0.0_amd64.deb
seed-balance-scanner
```

## Usage

1. **Prepare data.txt** — one mnemonic seed phrase per line (12, 18, or 24 words):

```
abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art
acid vintage artwork krypton gospel fossil glance frequent solid beyond exile bachelor
...
```

2. **Launch the app** — either `python main.py` or the built executable.

3. In the GUI:
   - Check/uncheck the coins you want to scan (BTC, ETH, SOL, BNB)
   - Click **Start Scan**
   - Progress updates in real time
   - Click any result row to view full seed and addresses in the **Details** panel
   - Click **Export Results** to save findings

## Coin Details

| Coin | Derivation Path | Curve | Balance API |
|---|---|---|---|
| BTC | `m/44'/0'/0'/0/0` | secp256k1 | blockchain.info |
| ETH | `m/44'/60'/0'/0/0` | secp256k1 | public RPC (blastapi) |
| SOL | `m/44'/501'/0'/0'` | ed25519 | solana public RPC |
| BNB | `m/44'/60'/0'/0/0` | secp256k1 | bsc-dataseed |

> ETH and BNB share the same derivation path (both use coin type 60) and will produce the same address.

## Output

Results are displayed in the GUI table and can be exported to a text file (`results_YYYYMMDD_HHMMSS.txt`) with full seed phrases, derived addresses, and balances.

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
│   ├── seed-balance-scanner_1.0.0_amd64.deb
│   └── data.txt
└── README.md           # This file
```
