import os
import re
import json
import time
import sqlite3
import hashlib
import requests
import urllib3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ---------- 配置 ----------
BILLING_API_URL = 'https://skillpay.me'
BILLING_API_KEY = 'sk_civilpy_******'
SKILL_ID = '*****'
HEADERS = {'X-API-Key': BILLING_API_KEY, 'Content-Type': 'application/json'}
PRICE_USDT = 1.0
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'auth_access.db')


# ---------- 数据库 ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS ip_auth (
        ip TEXT PRIMARY KEY,
        is_active INTEGER DEFAULT 0,
        expires_at DATETIME
    )''')
    conn.commit()
    conn.close()


def check_ip_auth(ip):
    conn = get_db()
    cur = conn.execute("SELECT expires_at FROM ip_auth WHERE ip = ? AND is_active = 1", (ip,))
    row = cur.fetchone()
    conn.close()
    if row:
        expiry = datetime.strptime(row['expires_at'], "%Y-%m-%d %H:%M:%S")
        if expiry > datetime.now():
            return True, row['expires_at']
    return False, None


def update_ip_auth(ip, days=1):
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("REPLACE INTO ip_auth (ip, is_active, expires_at) VALUES (?, 1, ?)", (ip, expiry))
    conn.commit()
    conn.close()
    return expiry


# ---------- SkillPay API ----------
def get_payment_link(user_id: str, amount: float) -> str:
    try:
        resp = requests.post(
            f'{BILLING_API_URL}/api/v1/billing/payment-link',
            headers=HEADERS,
            json={'user_id': user_id, 'amount': amount},
            timeout=10
        )
        return resp.json().get('payment_url', "")
    except Exception:
        return ""


# ---------- 路由 ----------
@app.route('/api/activate-key', methods=['POST'])
def activate_key():
    user_ip = request.remote_addr

    # 1. 检查已有授权
    is_valid, expiry_time = check_ip_auth(user_ip)
    if is_valid:
        return jsonify({
            'ok': True,
            'ip': user_ip,
            'expires_at': expiry_time,
            'message': 'Access Granted (Active Session Found)'
        })

    # 2. 尝试扣费
    try:
        resp = requests.post(
            f'{BILLING_API_URL}/api/v1/billing/charge',
            headers=HEADERS,
            json={'user_id': user_ip, 'skill_id': SKILL_ID, 'amount': PRICE_USDT},
            timeout=10
        )
        charge_data = resp.json()
    except Exception:
        return jsonify({'ok': False, 'message': 'Payment Gateway Timeout'}), 500

    # 3. 扣费成功 → 授权
    if charge_data.get('success'):
        expiry_str = update_ip_auth(user_ip, days=1)
        return jsonify({
            'ok': True,
            'ip': user_ip,
            'expires_at': expiry_str,
            'message': 'Success! Daily Pass Activated.'
        })

    # 4. 扣费失败 → 返回支付链接
    pay_url = get_payment_link(user_ip, PRICE_USDT)
    return jsonify({
        'ok': False,
        'needs_pay': True,
        'payment_url': pay_url,
        'ip': user_ip,
        'message': 'Insufficient balance, please support via SkillPay'
    }), 402


@app.route('/support')
def support():
    return render_template('support.html')


@app.route('/admin/supports')
def auth_supports():
    conn = get_db()
    rows = conn.execute("SELECT ip, is_active, expires_at FROM ip_auth ORDER BY expires_at DESC").fetchall()
    conn.close()

    total_ips = len(rows)
    active_now = 0
    now = datetime.now()
    processed_list = []

    for row in rows:
        expiry = datetime.strptime(row['expires_at'], "%Y-%m-%d %H:%M:%S")
        is_expired = now > expiry
        status = "ACTIVE" if (row['is_active'] == 1 and not is_expired) else "EXPIRED"
        if status == "ACTIVE":
            active_now += 1
        processed_list.append({
            "ip": row['ip'],
            "status": status,
            "expires_at": row['expires_at'],
            "is_expired": is_expired
        })

    return render_template('auth_stats.html', total_ips=total_ips, active_now=active_now, auth_list=processed_list)


@app.route('/')
def index():
    return render_template('support.html')


# ---------- 启动 ----------
init_auth_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5009, debug=True)
