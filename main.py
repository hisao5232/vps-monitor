import os
import asyncio
import flet as ft
import paramiko
import time
from dotenv import load_dotenv

# .envファイルから環境変数（VPSの接続情報）を読み込みます
load_dotenv()

HOST = os.getenv("VPS_HOST")
USER = os.getenv("VPS_USER")
KEY_PATH = os.getenv("SSH_KEY_PATH")
PORT = int(os.getenv("VPS_PORT"))

# --- バックエンド：VPSとの通信を管理するクラス ---
class VPSMonitor:
    def __init__(self):
        self.ssh = None

    def connect(self):
        """SSH接続を確立するメソッド"""
        path = os.path.normpath(os.path.expanduser(KEY_PATH))
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(HOST, username=USER, key_filename=path, port=PORT, timeout=5)

    def get_info(self):
        """Linuxコマンドを実行し、VPSの状態（CPU/メモリ/ディスク/Docker）を取得"""
        # 1:ホスト名, 2:メモリ使用率, 3:CPU使用率, 4:ディスク使用率, 5:Docker一覧
        cmds = [
            "hostname", 
            "free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2 }'", 
            "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8\"%\"}'", 
            "df -h / | awk 'NR==2{print $5}'",
            "docker ps --format '{{.Names}}:{{.Status}}'"
        ]
        # コマンドを '---' で区切って一括実行し、通信回数を減らして高速化
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

    def prune_docker(self):
        """未使用のDockerイメージとボリュームを一括削除して容量を確保"""
        cmd = "docker image prune -f && docker volume prune -f"
        self.ssh.exec_command(cmd)
        return "Prune command sent"

# --- フロントエンド：FletによるGUIの制御 ---
async def main(page: ft.Page):
    # アプリウィンドウの基本設定
    page.title = "VPS Pro Monitor"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 400      # デスクトップに常駐させやすいスリム幅
    page.window.height = 850
    page.window.resizable = True # サイズ変更を許可
    page.scroll = ft.ScrollMode.AUTO # 中身が増えたら自動スクロール
    
    # UIパーツの作成
    server_info = ft.Text("Connecting...", size=20, weight="bold", color="blue")
    update_time_label = ft.Text("Update: --:--:--", size=12, color="green")
    
    # メーター表示（CPU, メモリ, ディスク）
    cpu_label = ft.Text("CPU: ---", size=15, weight="bold")
    cpu_bar = ft.ProgressBar(width=320, value=0, color="blue")
    
    mem_label = ft.Text("MEM: ---", size=15, weight="bold")
    mem_bar = ft.ProgressBar(width=320, value=0, color="green")
    
    disk_label = ft.Text("DISK: ---", size=15, weight="bold")
    disk_bar = ft.ProgressBar(width=320, value=0, color="orange")
    
    # Dockerコンテナを表示するための入れ物（Column）
    container_list = ft.Column(spacing=5)
    
    # メンテナンス結果を表示するテキスト
    prune_result_text = ft.Text("", size=13, weight="bold")

    monitor = VPSMonitor()

    # --- ユーザー操作（イベント）の定義 ---
    
    async def launch_site(e):
        """フッターのリンクをクリックしたときにブラウザでサイトを開く"""
        try:
            await page.launch_url("https://go-pro-world.net")
        except:
            page.launch_url("https://go-pro-world.net")

    async def on_prune_click(e):
        """メンテナンスボタンが押された時の処理"""
        prune_button.disabled = True # 連打防止
        prune_result_text.value = "🗑️ Pruning..."
        page.update()
        try:
            # 重い通信処理はスレッドを分けて実行し、GUIをフリーズさせない
            await asyncio.to_thread(monitor.prune_docker)
            prune_result_text.value = "✅ Docker Pruned Successfully!"
            prune_result_text.color = "cyan"
        except:
            prune_result_text.value = "❌ Error"
            prune_result_text.color = "red"
        
        prune_button.disabled = False
        page.update()
        await asyncio.sleep(3) # 3秒後にメッセージを消す
        prune_result_text.value = ""
        page.update()

    # メンテナンスボタンの設定
    prune_button = ft.FilledButton(
        content=ft.Text("Cleanup Docker Assets", size=12, color="white"),
        on_click=on_prune_click,
        style=ft.ButtonStyle(bgcolor="red700")
    )

    def to_val(s):
        """ '85.5%' のような文字列を 0.855 の数値に変換する補助関数 """
        try: return float(s.replace("%",""))/100
        except: return 0

    # フッターセクション（独自ドメインとリンク）
    footer = ft.Column([
        ft.Divider(),
        ft.Text("go-pro-world.net since 2025", size=12, color="grey700"),
        ft.TextButton(
            content=ft.Text("https://go-pro-world.net", size=12, color="blue400", italic=True),
            on_click=launch_site
        )
    ], horizontal_alignment="center", spacing=0)

    # 画面に要素を配置
    page.add(
        ft.Container(
            content=ft.Column([
                server_info,
                ft.Divider(),
                cpu_label, cpu_bar,
                mem_label, mem_bar,
                disk_label, disk_bar,
                update_time_label,
                ft.Divider(),
                ft.Text("MAINTENANCE", size=12, weight="bold", color="red"),
                prune_button,
                prune_result_text,
                ft.Divider(),
                ft.Text("RUNNING CONTAINERS", size=12, weight="bold", color="cyan"),
                container_list,
                footer
            ], horizontal_alignment="center"),
            padding=20
        )
    )
    page.update()

    # 最初に一度だけSSH接続を実行
    try:
        await asyncio.to_thread(monitor.connect)
    except Exception as e:
        update_time_label.value = f"Error: {e}"
        page.update()
        return

    # --- メインループ：10秒ごとに情報を更新 ---
    while True:
        try:
            # データを取得
            res = await asyncio.to_thread(monitor.get_info)
            
            # 各UIパーツに取得データを反映
            server_info.value = f"Server: {res['name']}"
            cpu_label.value = f"CPU: {res['cpu']}"
            cpu_bar.value = to_val(res['cpu'])
            mem_label.value = f"MEM: {res['mem']}"
            mem_bar.value = to_val(res['mem'])
            disk_label.value = f"DISK: {res['disk']}"
            disk_bar.value = to_val(res['disk'])
            
            # コンテナリストを一旦空にして再構築
            container_list.controls.clear()
            if not res['containers'] or res['containers'] == ['']:
                container_list.controls.append(ft.Text("No active containers", size=11, italic=True))
            else:
                for c in res['containers']:
                    if ":" in c:
                        name, c_status = c.split(":", 1)
                        container_list.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Text("●", color="green" if "Up" in c_status else "red", size=10),
                                    ft.Text(f"{name}", weight="bold", size=12, expand=True),
                                    ft.Text(f"{c_status.split(' ')[0]}", size=10, color="grey")
                                ]),
                                bgcolor="#1A1A1A",
                                padding=8,
                                border_radius=5
                            )
                        )
            # 最終更新時刻を更新
            update_time_label.value = f"Update {time.strftime('%H:%M:%S')}"
        except:
            pass # エラー時はスキップして次回の更新を待つ
        
        page.update()
        await asyncio.sleep(10) # 10秒待機

if __name__ == "__main__":
    ft.app(target=main)
