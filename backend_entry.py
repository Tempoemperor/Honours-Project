# backend_entry.py
import sys
import uvicorn

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run("blockchain.api.server:app", host="0.0.0.0", port=port, reload=False)
