import subprocess
import threading
import re
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger("tunnel_manager")

class TunnelManager:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.is_starting: bool = False
        self.error: Optional[str] = None
        self.cloudflared_path = Path(__file__).resolve().parent / "cloudflared.exe"

    def get_status(self) -> Dict[str, Any]:
        import os
        # 若在 Vercel 部署環境中，Vercel 預設即具備全球公開 HTTPS 網域名稱 (*.vercel.app)
        if os.environ.get("VERCEL"):
            v_url = os.environ.get("VERCEL_URL", "")
            if v_url and not v_url.startswith("http"):
                public_url = f"https://{v_url}"
            else:
                public_url = v_url or "https://line-airport-dispatch.vercel.app"
            return {
                "is_running": True,
                "is_starting": False,
                "public_url": public_url,
                "webhook_url": f"{public_url}/api/line/webhook",
                "customer_booking_url": f"{public_url}/book",
                "is_vercel": True,
                "error": None
            }

        is_running = self.proc is not None and self.proc.poll() is None and self.public_url is not None
        return {
            "is_running": is_running,
            "is_starting": self.is_starting,
            "public_url": self.public_url if is_running else None,
            "webhook_url": f"{self.public_url}/api/line/webhook" if (is_running and self.public_url) else None,
            "customer_booking_url": f"{self.public_url}/book" if (is_running and self.public_url) else None,
            "is_vercel": False,
            "error": self.error
        }

    def start_tunnel(self, port: int = 8000) -> Dict[str, Any]:
        if self.proc is not None and self.proc.poll() is None and self.public_url:
            return self.get_status()

        if not self.cloudflared_path.exists():
            self.error = "找不到 cloudflared.exe 執行檔"
            return self.get_status()

        self.is_starting = True
        self.error = None
        self.public_url = None

        def run_thread():
            try:
                cmd = [str(self.cloudflared_path), "tunnel", "--url", f"http://127.0.0.1:{port}"]
                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                start_time = time.time()
                while time.time() - start_time < 20:
                    if self.proc.poll() is not None:
                        self.error = "cloudflared 程序意外終止"
                        self.is_starting = False
                        return

                    line = self.proc.stderr.readline()
                    if not line:
                        time.sleep(0.1)
                        continue

                    m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if m:
                        self.public_url = m.group(0)
                        self.is_starting = False
                        logger.info("Cloudflare tunnel active: %s", self.public_url)
                        break

                if not self.public_url:
                    self.error = "啟動超時：未能於時間內取得 Cloudflare 公開網址"
                    self.is_starting = False

            except Exception as e:
                self.error = str(e)
                self.is_starting = False
                logger.error("Failed to start tunnel: %s", e)

        t = threading.Thread(target=run_thread, daemon=True)
        t.start()

        # Wait up to 5 seconds for fast response
        waited = 0
        while waited < 5 and self.is_starting:
            time.sleep(0.3)
            waited += 0.3

        return self.get_status()

    def stop_tunnel(self) -> Dict[str, Any]:
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        self.public_url = None
        self.is_starting = False
        return self.get_status()

tunnel_mgr = TunnelManager()
