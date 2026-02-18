import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 設定 ---
YT_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDS = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def main():
    print(f"🚀 --- 同期開始 ({datetime.now().strftime('%H:%M:%S')}) ---")
    
    # スプレッドシート接続
    creds = Credentials.from_service_account_info(GOOGLE_CREDS, scopes=SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    
    all_data = sheet.get_all_records()

    for i, row in enumerate(all_data, start=2): # 2行目から
        t_name = row.get('タレント名')
        u_id = row.get('uploadsId')

        if not u_id: continue

        # まずは最新5件のIDだけ取得（1ユニット）
        yt_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=5&playlistId={u_id}&key={YT_API_KEY}"
        yt_res = requests.get(yt_url).json()
        video_ids = [item['contentDetails']['videoId'] for item in yt_res.get('items', [])]

        # 書き込み用変数の初期化（どちらもない時：ステータスFALSE、他はクリア）
        is_live_status = "FALSE"
        v_id = ""
        v_title = ""
        v_time = ""

        if video_ids:
            # 複数動画のステータスを1回の実行で取得（1ユニット）
            v_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,liveStreamingDetails&id={','.join(video_ids)}&key={YT_API_KEY}"
            v_res = requests.get(v_url).json()

            # 判定用の一時変数
            live_item = None
            upcoming_item = None

            for v in v_res.get('items', []):
                status = v['snippet']['liveBroadcastContent']
                if status == "live":
                    live_item = v
                    break # ライブがあれば最優先
                elif status == "upcoming" and not upcoming_item:
                    upcoming_item = v

            # 🚀 代表指定の条件分岐ロジック
            if live_item:
                # 【配信中】ステータスTRUE、ID・タイトル入力
                is_live_status = "TRUE"
                v_id = live_item['id']
                v_title = live_item['snippet']['title']
                print(f"  🎯 [{t_name}] 配信中！")
            elif upcoming_item:
                # 【配信予定】ステータスFALSE、ID・タイトル・時間入力
                is_live_status = "FALSE"
                v_id = upcoming_item['id']
                v_title = upcoming_item['snippet']['title']
                v_time = upcoming_item.get('liveStreamingDetails', {}).get('scheduledStartTime', "").replace('Z', '.000Z')
                print(f"  ⏰ [{t_name}] 予定あり")
            else:
                print(f"  💤 [{t_name}] 予定なし")

        # 4. スプレッドシート更新（D列:isLive, E:liveVideoId, F:scheduleTitle, G:scheduledAt）
        # 列の順番通りに一括更新
        update_values = [is_live_status, v_id, v_title, v_time]
        sheet.update(f"D{i}:G{i}", [update_values])

    print("✨ --- 同期完了 ---")

if __name__ == "__main__":
    main()
