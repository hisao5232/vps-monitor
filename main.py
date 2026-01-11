import os
import asyncio
import flet as ft
import paramiko
import time
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("VPS_HOST")
USER = os.getenv("VPS_USER")
KEY_PATH = os.getenv("SSH_KEY_PATH")
PORT = int(os.getenv("VPS_PORT", 56756))

class VPSMonitor:
    def __init__(self):
        self.ssh = None

    def connect(self):
        path = os.path.normpath(os.path.expanduser(KEY_PATH))
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(HOST, username=USER, key_filename=path, port=PORT, timeout=5)

    def get_info(self):
        cmds = [
            "hostname", 
            "free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2 }'", 
            "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8\"%\"}'", 
            "df -h / | awk 'NR==2{print $5}'"
        ]
        full_cmd = " && ".join([f"echo '---'; {c}" for c in cmds])
        stdin, stdout, stderr = self.ssh.exec_command(full_cmd)
        results = stdout.read().decode().split("---")
        data = [r.strip() for r in results if r.strip()]
        return {"name": data[0], "mem": data[1], "cpu": data[2], "disk": data[3]}

async def main(page: ft.Page):
    page.title = "VPS Pro Realtime Monitor"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 650
    page.window_resizable = False
    
    # --- 1. UI要素の定義（バーグラフ付き） ---
    server_info = ft.Text("Initializing...", size=22, weight="bold", color="blue")
    
    cpu_info = ft.Text("---", size=18, weight="bold")
    cpu_bar = ft.ProgressBar(width=320, value=0, color="blue", bgcolor="#333333")
    
    mem_info = ft.Text("---", size=18, weight="bold")
    mem_bar = ft.ProgressBar(width=320, value=0, color="green", bgcolor="#333333")
    
    disk_info = ft.Text("---", size=18, weight="bold")
    disk_bar = ft.ProgressBar(width=320, value=0, color="orange", bgcolor="#333333")
    
    status_log = ft.Text("Ready to connect", italic=True, color="grey", size=12)

    # 数値変換用
    def to_val(s):
        try: return float(s.replace("%", "")) / 100
        except: return 0

    # レイアウト配置
    page.add(
        ft.Container(
            content=ft.Column([
                server_info,
                ft.Divider(height=30),
                
                ft.Text("CPU USAGE", size=12, color="grey"),
                cpu_info, cpu_bar,
                
                ft.Container(height=10),
                
                ft.Text("MEMORY USAGE", size=12, color="grey"),
                mem_info, mem_bar,
                
                ft.Container(height=10),
                
                ft.Text("DISK USAGE", size=12, color="grey"),
                disk_info, disk_bar,
                
                ft.Divider(height=30),
                status_log
            ], horizontal_alignment="center"),
            padding=30,
            alignment=ft.Alignment(0, 0)
        )
    )
    page.update()

    monitor = VPSMonitor()
    
    # SSH接続
    try:
        status_log.value = "Status: Connecting to VPS..."
        page.update()
        await asyncio.to_thread(monitor.connect)
        status_log.value = "Status: Connected (Realtime mode)"
        page.update()
    except Exception as e:
        status_log.value = f"Connection Error: {e}"
        page.update()
        return

    # --- メインループ ---
    while True:
        try:
            # データ取得
            res = await asyncio.to_thread(monitor.get_info)
            
            # 画面反映
            server_info.value = f"Server: {res['name']}"
            cpu_info.value = res['cpu']
            cpu_bar.value = to_val(res['cpu'])
            
            mem_info.value = res['mem']
            mem_bar.value = to_val(res['mem'])
            
            disk_info.value = res['disk']
            disk_bar.value = to_val(res['disk'])
            
            status_log.value = f"Last sync: {time.strftime('%H:%M:%S')}"
            status_log.color = "green"
            
        except Exception as e:
            status_log.value = f"Update Error: {e}"
            status_log.color = "red"
            
        page.update()
        await asyncio.sleep(10)

if __name__ == "__main__":
    ft.app(target=main)
    