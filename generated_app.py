import streamlit as st
import folium
import random
import math
import os
import json
import re
import base64
from openai import OpenAI

# DeepSeek API クライアント
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# セッションステート初期化
if 'show' not in st.session_state:
    st.session_state.show = False
if 'route' not in st.session_state:
    st.session_state.route = None
if 'total_distance_m' not in st.session_state:
    st.session_state.total_distance_m = 0
if 'start_lat' not in st.session_state:
    st.session_state.start_lat = 35.6812
if 'start_lon' not in st.session_state:
    st.session_state.start_lon = 139.7671

# ---------------------------------------------------------
# パスワードの確認
# ---------------------------------------------------------
def check_password():
    PASSWD = os.environ.get('PASS_KEY')
    if not PASSWD:
        st.error("システムエラー: サーバー側にパスワードが設定されていません。")
        return False
        
    password = st.text_input("パスワードを入力してください", type="password")
    
    if not password:
        return False
        
    # タイミング攻撃を防ぐセキュアな比較
    if hmac.compare_digest(password, PASSWD):
        return True
    else:
        st.error("パスワードが間違っています。")
        return False

def geocode_address(address: str):
    """住所文字列から緯度経度を取得（エラーハンドリング強化版）"""
    prompt = (
        f"以下の住所を解析し、有効なJSON形式でキーをダブルクォートで囲んで "
        f'{{"lat": 緯度, "lon": 経度}} のみを返してください。説明やコードブロックは一切不要です。\n'
        f"住所: {address}"
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100
        )
        content = response.choices[0].message.content.strip()

        # ```json ... ``` の除去
        if "```" in content:
            parts = content.split("```")
            # 2つ目の要素がJSONを含む可能性がある
            for part in parts:
                candidate = part.strip()
                # json or no language tag
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate:
                    content = candidate
                    break

        # JSONとしてパース
        try:
            coords = json.loads(content)
        except json.JSONDecodeError:
            # どうしてもパースできない場合、シングルクォートをダブルクォートに置き換えて再試行
            fixed_content = re.sub(r"'([^']*)':", r'"\1":', content)
            fixed_content = fixed_content.replace("'", '"')
            coords = json.loads(fixed_content)

        lat = float(coords["lat"])
        lon = float(coords["lon"])
        return lat, lon
    except Exception as e:
        st.error(f"ジオコーディングに失敗しました: {e}")
        return None, None

# ---------- UI ----------
if check_password():
    
    st.title("ランダム散歩経路提案")

    address = st.text_input("出発地点の住所", value="東京都千代田区丸の内1丁目")

    time_min = st.slider("所用時間（分）", 10, 120, 30)

    if st.button("経路を生成"):
        lat, lon = geocode_address(address)
        if lat is None:
            st.stop()
        st.session_state.start_lat = lat
        st.session_state.start_lon = lon

        speed_m_per_min = 5000 / 60  # 約83.33 m/分
        total_distance_m = speed_m_per_min * time_min
        num_points = random.randint(3, 8)
        segment_distances = [random.uniform(0.8, 1.2) * total_distance_m / num_points for _ in range(num_points)]
        directions = [random.uniform(0, 360) for _ in range(num_points)]
        lat_per_m = 1 / 111000
        lon_per_m = 1 / (111000 * math.cos(math.radians(lat)))
        points = [(lat, lon)]
        current_lat, current_lon = lat, lon
        for dist_m, deg in zip(segment_distances, directions):
            rad = math.radians(deg)
            dlat = dist_m * math.cos(rad) * lat_per_m
            dlon = dist_m * math.sin(rad) * lon_per_m
            current_lat += dlat
            current_lon += dlon
            points.append((current_lat, current_lon))
        st.session_state.route = points
        st.session_state.total_distance_m = total_distance_m
        st.session_state.show = True

    if st.session_state.show:
        route = st.session_state.route
        if route:
            m = folium.Map(location=[st.session_state.start_lat, st.session_state.start_lon], zoom_start=14)
            folium.Marker(route[0], popup="出発点", icon=folium.Icon(color='green')).add_to(m)
            folium.Marker(route[-1], popup="到着点", icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine(route, color='blue', weight=5, opacity=0.7).add_to(m)
            # HTMLをBase64エンコードしてdata URIとしてsrcに渡す
            html = m._repr_html_()
            encoded_html = base64.b64encode(html.encode()).decode()
            st.iframe(src="data:text/html;base64," + encoded_html, height=500)
            st.write(f"経由地点数: {len(route)}")
            st.write(f"おおよその距離: {st.session_state.total_distance_m:.0f} m")