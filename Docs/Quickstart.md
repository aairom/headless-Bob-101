# Quickstart Guide — Headless Bob Demo

This guide gets you from zero to a running application in under 10 minutes.

---

## Step 1: Prerequisites

Ensure the following are available on your machine:

| Tool | Version | Check |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| npm | 18+ | `npm --version` |
| IBM Bob Shell | 2.0.4+ | `bob --version` |
| Git | any | `git --version` |

### IBM Bob Shell installation

If Bob Shell is not installed:

1. Go to https://bob.ibm.com and sign in with your IBMid.
2. Download the Bob Shell installer for macOS (arm64 or x64).
3. Follow the [installation instructions](https://bob.ibm.com/docs/shell/getting-started/install-and-setup).
4. Generate an **Inference-scope API key** at Account → API Keys.

---

## Step 2: Start the Headless Bob Service

The demo connects to a Headless Bob service.  
Clone and start the service from the IBM self-serve-assets repository:

```bash
# Clone the building blocks repo
git clone https://github.com/ibm-self-serve-assets/building-blocks.git
cd building-blocks/ai/ai-engineering/headless-bob/assets/headlessbob

# Install dependencies
npm ci

# Configure credentials
cp .env.example .env
# Edit .env — set these two required fields:
#   BOB_API_KEY=<your-bob-inference-api-key>
#   AUTH_TOKENS={"owner":"my-demo-token-at-least-24-chars"}
#
# AUTH_TOKENS is a JSON object you invent — the key ("owner") is a label,
# the value is the bearer token you will also set as HEADLESS_BOB_TOKEN
# in the demo's .env file.  Generate a strong token with:
#   python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Build and start
npm run build
npm start
```

Verify the service is running:

```bash
curl -s http://127.0.0.1:8000/api/v1/capabilities \
     -H "Authorization: Bearer my-demo-token-at-least-24-chars" | jq .
```

You should see a JSON response with `version`, `bob_version`, and capacity info.

---

## Step 3: Clone and Configure the Demo

```bash
# Navigate to the headless-bob-demo project
cd headless-bob-demo   # or the root of this repo

# Copy the environment template
cp .env.example .env
```

Edit `.env` and set:

```ini
HEADLESS_BOB_URL=http://127.0.0.1:8000
HEADLESS_BOB_TOKEN=my-demo-token-at-least-24-chars
```

> **Note:** `HEADLESS_BOB_TOKEN` must be **exactly the value** you used for the token
> inside `AUTH_TOKENS` in the Headless Bob service's `.env` (e.g. if `AUTH_TOKENS={"owner":"abc123"}`,
> then `HEADLESS_BOB_TOKEN=abc123`). The key name (`"owner"`) does not matter.

---

## Step 4: Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 5: Run the Application

```bash
# Option A: using the launch script (runs detached, prints URL)
./scripts/start.sh

# Option B: run directly
streamlit run src/app.py --server.port 8501
```

Open **http://localhost:8501** in your browser.

---

## Step 6: Run the Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

All tests run offline (no live service needed).

---

## Step 7: Try It Out

1. The sidebar shows **✅ Connected** with service version info.
2. Click **➕ New** to create your first conversation thread.
3. Leave the mode as **agent**.
4. Type a prompt, for example:

   > `Create a file called hello.txt in the workspace with the content "Hello from Headless Bob!"`

5. Watch Bob's response stream in real time.
6. When the run completes, expand **📊 Run details** to see token usage and execution time.
7. Expand **📁 Workspace files** — you should see `hello.txt`. Click **⬇️ Download** to save it locally.

---

## Stopping the Application

```bash
./scripts/stop.sh
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "HEADLESS_BOB_TOKEN not set" | Check that `.env` exists and has `HEADLESS_BOB_TOKEN=...` |
| "Not configured: Connection refused" | The Headless Bob service is not running — run `npm start` in the headlessbob directory |
| "HTTP Error 400: Bad Request" | Never pass extra fields to the message API — only `{"content":"..."}` is accepted. The demo handles this automatically; if you call the API directly, remove any `mode` or other fields |
| "Service unreachable" | Verify the service is running: `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/v1/capabilities` |
| Port 8501 already in use | Edit `scripts/start.sh` and change `--server.port 8501` |
| Bob returns an error | Check `BOB_API_KEY` in the Headless Bob service `.env` is valid |
| Tests fail | Make sure `.venv` is active and `pytest` is installed |

---

## Cleaning Up

To remove virtual environment, caches, and output files:

```bash
./scripts/cleanup.sh
```
