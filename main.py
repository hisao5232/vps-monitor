import os
import flet as ft
import paramiko
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

HOST = os.getenv("VPS_HOST")
USER = os.getenv("VPS_USER")
KEY_PATH = os.getenv("SSH_KEY_PATH")
# ポート番号を取得（.envにない場合は56756をデフォルトにする）
PORT = int(os.getenv("VPS_PORT", 56756))

def get_vps_memory():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        path = os.path.expanduser(KEY_PATH)
        # 追加：念のためWindows/Linuxの区切り文字を正規化
        path = os.path.normpath(path)
        
        ssh.connect(HOST, username=USER, key_filename=path, port=PORT, timeout=10)
        
        cmd = "free -m | awk 'NR==2{printf \"%.2f%%\", $3*100/$2 }'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        result = stdout.read().decode().strip()
        
        ssh.close()
        return result
    except Exception as e:
        return f"Error: {str(e)}"

def main(page: ft.Page):
    page.title = "VPS Real-time Monitor"
    page.theme_mode = ft.ThemeMode.DARK
    
    # --- デスクトップアプリ用設定 ---
    page.window.width = 350       # 幅
    page.window.height = 450      # 高さ
    page.window.resizable = False # サイズ変更不可
    page.window.always_on_top = True  # ★常に最前面に表示
    # ----------------------------
    
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    
    # 色の指定を文字列 "blue" などにすることで AttributeError を回避
    memory_value = ft.Text("---%", size=60, weight="bold", color="blue")
    status_text = ft.Text("待機中...", size=16, color="grey")

    def on_click(e):
        status_text.value = "更新中..."
        status_text.color = "grey"
        page.update()
        
        res = get_vps_memory()
        
        if "Error" in res:
            status_text.value = res
            status_text.color = "red"
        else:
            memory_value.value = res
            status_text.value = "最終更新: 成功"
            status_text.color = "green"
            
        page.update()

    page.add(
        ft.Text("VPS メモリ使用率", size=20),
        memory_value,
        status_text,
        ft.Container(height=30),
        # アイコン名も文字列で指定
        ft.FilledButton("ステータスを更新", on_click=on_click, icon="refresh")
    )

if __name__ == "__main__":
    # ft.app(target=main) の代わりに最新の実行方法
    ft.app(target=main)
    