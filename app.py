
import os
import json
import requests
from flask import Flask, jsonify, render_template, request, Response, redirect
import traceback
import datetime
import re

# --- バージョン情報 ---
APP_VERSION = "1.6.6"
DEPLOY_TARGET = "Render"
LAST_UPDATED = "2025-08-02 17:17:31 UTC"

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    "BASE_CLIENT_ID": "ここにクライアントIDを入力",
    "BASE_CLIENT_SECRET": "ここにクライアントシークレットを入力",
    "BASE_AUTH_CODE": "認可後に取得したコードを入力",
    "BASE_ACCESS_TOKEN": "アクセストークンを入力",
    "order_limit": 5,
    "display_fields": ["product_name", "buyer_name"],
    "custom_message": ""
}

def is_ascii(s):
    return all(ord(c) < 128 for c in s)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            config_data = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config_data:
                    config_data[key] = value
            return config_data
        except json.JSONDecodeError:
            return DEFAULT_CONFIG.copy()

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

TUTORIAL_HTML = """

<h3>はじめに：このツールでできること</h3>
<p>このツールは、あなたのBASEショップの最新の注文情報を取得し、OBSなどを通じてYouTube Liveの画面上にリアルタイムで表示するためのものです。</p>
<h3>設定の3ステップ</h3>
<ol>
    <li><strong>BASEでプライベートアプリを作成する:</strong> Client IDとClient Secretを取得します。</li>
    <li><strong>認可コード(Auth Code)を取得する:</strong> このサイトの機能を使って、認可コードを取得します。</li>
    <li><strong>アクセストークンを取得する:</strong> 認可コードを使って、アクセストークンを取得します。</li>
</ol>
<hr>
<h3>各キーの取得方法</h3>
<h4>1. Client ID & Client Secret</h4>
<ul>
    <li><a href="https://developers.thebase.in/" target="_blank">こちらのリンク</a>からBASEにログインし、プライベートアプリを新規作成します。</li>
    <li><strong>コールバックURL:</strong> <code>https://baseobsapp.onrender.com/callback</code> を入力してください。</li>
    <li><strong>権限（スコープ）:</strong> 「注文情報の読み取り (read_orders)」にチェックを入れてください。</li>
</ul>
<h4>2. 認可コード (Auth Code)</h4>
<ol>
    <li>上記のキーを下のフォームに入力し、「保存」ボタンを押してください。</li>
    <li><a href="/get_auth_code" target="_blank">こちらの認可コード取得ページ</a> にアクセスしてください。</li>
    <li>連携を許可すると、認可コードが表示されます。それを下のフォームに貼り付けてください。</li>
</ol>
<h4>3. アクセストークン (Access Token)</h4>
<ul>
    <li><a href="/get_token" target="_blank">こちらのアクセストークン取得ページ</a> をクリックすると、アクセストークンが自動的に取得・入力されます。</li>
</ul>
<p><strong>全ての値を入力したら、再度「保存」ボタンをクリックしてください。</strong></p>

"""

@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION, deploy_target=DEPLOY_TARGET, last_updated=LAST_UPDATED)

@app.route('/get_auth_code')
def get_auth_code():
    config = load_config()
    client_id = config.get('BASE_CLIENT_ID')
    if not client_id or 'ここに' in client_id:
        return "エラー: Client IDが設定されていません。", 400
    redirect_uri = "https://baseobsapp.onrender.com/callback"
    scopes = "read_orders"
    authorization_url = "https://api.thebase.in/1/oauth/authorize?response_type=code&client_id=" + client_id + "&redirect_uri=" + redirect_uri + "&scope=" + scopes
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    auth_code = request.args.get('code')
    if auth_code:
        config = load_config()
        config['BASE_AUTH_CODE'] = auth_code
        save_config(config)
        return '<h1>認可コード取得成功</h1><p>コード: <code>' + auth_code + '</code></p><p>このタブは閉じて構いません。</p>'
    return "エラー: 認可コードを取得できませんでした。", 400

@app.route('/get_token')
def get_token():
    config = load_config()
    auth_code = config.get('BASE_AUTH_CODE')
    client_id = config.get('BASE_CLIENT_ID')
    client_secret = config.get('BASE_CLIENT_SECRET')

    if not all([auth_code, client_id, client_secret]):
        return "エラー: 必要な情報が設定されていません。", 400

    redirect_uri = "https://baseobsapp.onrender.com/callback"
    token_url = "https://api.thebase.in/1/oauth/token"
    payload = {'grant_type': 'authorization_code', 'client_id': client_id, 'client_secret': client_secret, 'code': auth_code, 'redirect_uri': redirect_uri}

    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get('access_token')
        if access_token:
            config['BASE_ACCESS_TOKEN'] = access_token
            save_config(config)
            return '<h1>アクセストークン取得成功</h1><p>Token: <code>' + access_token + '</code></p><p>このタブは閉じて構いません。</p>'
        else:
            return "エラー: トークン取得失敗: " + response.text, 500
    except requests.exceptions.RequestException as e:
        return f"APIエラー: " + str(e), 500

@app.route('/settings', methods=['GET', 'POST'])
def settings_route():
    message = None
    if request.method == 'POST':
        current_config = load_config()
        current_config['BASE_CLIENT_ID'] = request.form.get('base_client_id', '')
        current_config['BASE_CLIENT_SECRET'] = request.form.get('base_client_secret', '')
        current_config['BASE_AUTH_CODE'] = request.form.get('base_auth_code', '')
        current_config['BASE_ACCESS_TOKEN'] = request.form.get('base_access_token', '')
        order_limit_str = request.form.get('order_limit', '5')
        try:
            current_config['order_limit'] = int(order_limit_str)
        except ValueError:
            current_config['order_limit'] = 5
        current_config['display_fields'] = request.form.getlist('display_fields')
        current_config['custom_message'] = request.form.get('custom_message', '')
        save_config(current_config)
        message = "設定を保存しました。"

    current_config = load_config()
    return render_template('settings.html', config=current_config, message=message, tutorial_html=TUTORIAL_HTML)

@app.route('/api/orders')
def get_orders_from_base():
    current_config = load_config()
    access_token = current_config.get('BASE_ACCESS_TOKEN')
    order_limit = current_config.get('order_limit', 5)
    display_fields = current_config.get('display_fields', [])
    custom_message = current_config.get('custom_message', '')

    if not access_token or 'ここに' in access_token:
        return jsonify({"error": "アクセストークンが設定されていません。"})
    if not is_ascii(access_token):
        return jsonify({"error": "アクセストークンに不正な文字が含まれています。"})

    orders_api_url = "https://api.thebase.in/1/orders"
    headers = {"Authorization": "Bearer " + access_token}
    params = {"limit": order_limit, "order": "ordered_datetime", "sort": "desc"}
    try:
        orders_response = requests.get(orders_api_url, headers=headers, params=params)
        orders_response.raise_for_status()
        orders_data = orders_response.json()
        formatted_orders = []
        for order in orders_data.get('orders', []):
            unique_key = order.get('unique_key')
            if not unique_key: continue
            detail_api_url = "https://api.thebase.in/1/orders/detail/" + unique_key
            detail_response = requests.get(detail_api_url, headers=headers)
            if detail_response.ok:
                detail_data = detail_response.json().get('order', {})
                if not detail_data: continue
                order_info = {}
                if 'product_name' in display_fields:
                    order_info['product_name'] = detail_data.get('details', [{}])[0].get('item_name', '')
                if 'buyer_name' in display_fields:
                    order_info['buyer_name'] = detail_data.get('last_name', '') + " " + detail_data.get('first_name', '')
                if 'total' in display_fields:
                    order_info['total'] = detail_data.get('total')
                if 'add_comment' in display_fields:
                    order_info['add_comment'] = detail_data.get('add_comment', '')
                if 'title' in display_fields:
                    order_info['title'] = detail_data.get('details', [{}])[0].get('item_name', '')
                if 'price' in display_fields:
                    order_info['price'] = detail_data.get('details', [{}])[0].get('price')
                if 'amount' in display_fields:
                    order_info['amount'] = detail_data.get('details', [{}])[0].get('amount')
                if 'item_total' in display_fields:
                    order_info['item_total'] = detail_data.get('details', [{}])[0].get('item_total')

                if order_info: formatted_orders.append(order_info)
        return jsonify({"orders": formatted_orders, "custom_message": custom_message})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "API接続エラー: " + str(e)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "予期せぬエラーが発生しました。"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
