# MCP Instagram

## Setup

The project uses a virtual environment so `mcp` and `httpx` install without conflicting with Homebrew’s `cffi`.

1. **Activate the virtual environment:**

   ```bash
   source .venv/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. When you’re done, deactivate with:

   ```bash
   deactivate
   ```

If you see an SSL certificate error when running `pip install`, check your network and macOS keychain/certificates, or try:

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```
