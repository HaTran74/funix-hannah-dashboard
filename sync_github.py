#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tự động đồng bộ file app.py lên GitHub Repository thông qua GitHub REST API.
Không yêu cầu Git CLI hay Xcode Command Line Tools.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error

REPO_OWNER = "HaTran74"
REPO_NAME = "funix-hannah-dashboard"
BRANCH = "main"
TARGET_FILE = "app.py"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_TO_SYNC = os.path.join(BASE_DIR, "app.py")
CONFIG_FILE = os.path.join(BASE_DIR, "github_config.json")

def load_github_token():
    # 1. Thử đọc từ biến môi trường
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()

    # 2. Thử đọc từ file github_config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("github_token", "").strip()
        except Exception as e:
            print(f"⚠️ Lỗi đọc file config: {e}")

    # 3. Thử đọc từ secrets.toml của streamlit
    secrets_file = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "github_token" in line and "=" in line:
                        return line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass

    return None

def sync_to_github(commit_message="Auto-sync app.py from dashboard"):
    token = load_github_token()
    if not token:
        print("❌ Không tìm thấy GITHUB_TOKEN!")
        print("👉 Vui lòng cấu hình token trong file 'github_config.json' theo mẫu:")
        print('   {"github_token": "ghp_xxxxxxxxxxxxxxxxxxxx"}')
        return False

    if not os.path.exists(FILE_TO_SYNC):
        print(f"❌ Không tìm thấy file {FILE_TO_SYNC}")
        return False

    # Đọc nội dung file app.py
    with open(FILE_TO_SYNC, "rb") as f:
        file_bytes = f.read()

    b64_content = base64.b64encode(file_bytes).decode("utf-8")

    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TARGET_FILE}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Hannah-Dashboard-AutoSync",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # 1. Lấy SHA hiện tại của file trên GitHub
    current_sha = None
    try:
        import hashlib
        req_get = urllib.request.Request(f"{api_url}?ref={BRANCH}", headers=headers, method="GET")
        with urllib.request.urlopen(req_get, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            current_sha = data.get("sha")
            remote_size = data.get("size", 0)

            # Kiểm tra nội dung local có giống hệt remote không bằng Git Blob SHA-1
            local_git_sha = hashlib.sha1(f"blob {len(file_bytes)}\0".encode("utf-8") + file_bytes).hexdigest()
            if current_sha and local_git_sha == current_sha:
                print(f"ℹ️ Tệp local đã hoàn toàn trùng khớp với GitHub (SHA: {current_sha[:8]}). Bỏ qua, không cần đẩy lại.")
                return True

            print(f"ℹ️ File hiện tại trên GitHub: {remote_size:,} bytes (SHA: {current_sha[:8]}...)")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("ℹ️ File chưa tồn tại trên GitHub, sẽ tạo mới.")
        else:
            print(f"❌ Lỗi lấy thông tin file từ GitHub (HTTP {e.code}): {e.read().decode('utf-8')}")
            return False
    except Exception as e:
        print(f"❌ Lỗi kết nối GitHub: {e}")
        return False

    # 2. Gửi request PUT để commit cập nhật
    payload = {
        "message": commit_message,
        "content": b64_content,
        "branch": BRANCH
    }
    if current_sha:
        payload["sha"] = current_sha

    data_bytes = json.dumps(payload).encode("utf-8")
    req_put = urllib.request.Request(api_url, data=data_bytes, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req_put, timeout=20) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            new_commit = res_data.get("commit", {}).get("sha", "")[:8]
            print(f"✅ ĐỒNG BỘ THÀNH CÔNG LÊN GITHUB!")
            print(f"   Repository : {REPO_OWNER}/{REPO_NAME}")
            print(f"   Branch     : {BRANCH}")
            print(f"   Commit SHA : {new_commit}")
            print(f"   File Size  : {len(file_bytes):,} bytes")
            print("🚀 Streamlit Cloud sẽ tự động cập nhật trong vòng 20-30 giây.")
            return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"❌ Lỗi đồng bộ lên GitHub (HTTP {e.code}): {err_msg}")
        return False
    except Exception as e:
        print(f"❌ Lỗi bất ngờ: {e}")
        return False

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Auto-sync app.py from dashboard"
    success = sync_to_github(msg)
    sys.exit(0 if success else 1)
