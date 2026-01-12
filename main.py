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
        # Dockerコンテナの状態を取得
        cmds = [
            "hostname", 
            "free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2 }'", 
            "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8\"%\"}'", 
            "df -h / | awk 'NR==2{print $5}'",
            "docker ps --format '{{.Names}}:{{.Status}}'"
        ]
        full_cmd = " && ".join([f"echo '---'; {c}" for c in cmds])
        stdin, stdout, stderr = self.ssh.exec_command(full_cmd)
        results = stdout.read().decode().split("---")
        data = [r.strip() for r in results if r.strip()]
        
        return {
            "name": data[0] if len(data) > 0 else "Unknown", 
            "mem": data[1] if len(data) > 1 else "0%", 
            "cpu": data[2] if len(data) > 2 else "0%", 
            "disk": data[3] if len(data) > 3 else "0%",
            "containers": data[4].split('\n') if len(data) > 4 else []
        }

async def main(page: ft.Page):
    page.title = "VPS Pro Monitor + Docker"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 700
    
    # スクロールを有効化
    page.scroll = ft.ScrollMode.AUTO
    
    # UI要素
    server_info = ft.Text("Connecting...", size=22, weight="bold", color="blue")
    cpu_label = ft.Text("CPU: ---", size=16, weight="bold")
    cpu_bar = ft.ProgressBar(width=320, value=0, color="blue")
    mem_label = ft.Text("MEM: ---", size=16, weight="bold")
    mem_bar = ft.ProgressBar(width=320, value=0, color="green")
    disk_label = ft.Text("DISK: ---", size=16, weight="bold")
    disk_bar = ft.ProgressBar(width=320, value=0, color="orange")
    container_list = ft.Column(spacing=5)
    status_log = ft.Text("Ready", italic=True, color="grey", size=12)

    def to_val(s):
        try: return float(s.replace("%",""))/100
        except: return 0

    page.add(
        ft.Container(
            content=ft.Column([
                server_info,
                ft.Divider(),
                cpu_label, cpu_bar,
                mem_label, mem_bar,
                disk_label, disk_bar,
                ft.Divider(),
                ft.Text("RUNNING CONTAINERS", weight="bold", color="cyan"),
                container_list,
                ft.Divider(),
                status_log
            ], horizontal_alignment="center"),
            padding=20
        )
    )
    
    # update() は await せずに呼ぶ（エラー回避の肝）
    page.update()

    monitor = VPSMonitor()
    try:
        await asyncio.to_thread(monitor.connect)
    except Exception as e:
        status_log.value = f"Connect Error: {e}"
        page.update()
        return

    while True:
        try:
            # データの取得
            res = await asyncio.to_thread(monitor.get_info)
            
            # UIの更新
            server_info.value = f"Server: {res['name']}"
            cpu_label.value = f"CPU: {res['cpu']}"
            cpu_bar.value = to_val(res['cpu'])
            mem_label.value = f"MEM: {res['mem']}"
            mem_bar.value = to_val(res['mem'])
            disk_label.value = f"DISK: {res['disk']}"
            disk_bar.value = to_val(res['disk'])
            
            container_list.controls.clear()
            if not res['containers'] or res['containers'] == ['']:
                container_list.controls.append(ft.Text("No active containers", size=12, italic=True))
            else:
                for c in res['containers']:
                    if ":" in c:
                        name, c_status = c.split(":", 1)
                        container_list.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Text("●", color="green" if "Up" in c_status else "red"),
                                    ft.Text(f"{name}", weight="bold", expand=True),
                                    ft.Text(f"{c_status.split(' ')[0]}", size=11, color="grey")
                                ]),
                                bgcolor="#222222",
                                padding=10,
                                border_radius=5
                            )
                        )
            
            status_log.value = f"Last Update: {time.strftime('%H:%M:%S')}"
            status_log.color = "green"
        except Exception as e:
            status_log.value = f"Update Error: {e}"
            status_log.color = "red"
        
        # page.update() を同期関数として呼ぶ
        page.update()
        
        # 待機だけは非同期で行い、UIフリーズを防ぐ
        await asyncio.sleep(10)

if __name__ == "__main__":
    ft.app(target=main)
    