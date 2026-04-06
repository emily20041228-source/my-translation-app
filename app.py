from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. 載入環境變數 (本地端讀取 .env)
load_dotenv()

app = Flask(__name__)
# 允許所有的前端網站來接資料
CORS(app)

# ==========================================
# 1. 設置 Google Sheets API 授權與變數
# ==========================================
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CREDENTIALS_FILE = 'service_account.json'
SHEET_ID = '16y0ew8cL_t6m4EBol7lJGZnb87jF1sKOu3atTrN-cLA' 

def get_gspread_client():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"找不到憑證檔案 {CREDENTIALS_FILE}")
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(credentials)

# ==========================================
# 2. 設置 Google Gemini API
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("❌ 錯誤：找不到環境變數 GEMINI_API_KEY，請檢查 .env 或 Render 設定")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# 初始化模型與系統提示詞
system_instruction = """
你是一個負責指導學測英文翻譯的高中英文老師。請嚴格遵從以下 7 個步驟引導學生，運用蘇格拉底教學法。
【🚨對話核心原則🚨】每次回覆字數低於 50 字，一次一問，直接了當。
"""

# 模型初始化防呆
try:
    model = genai.GenerativeModel('models/gemini-1.5-flash', system_instruction=system_instruction)
    print("✅ 成功啟動模型: models/gemini-1.5-flash")
except Exception:
    model = genai.GenerativeModel('models/gemini-1.5-pro', system_instruction=system_instruction)
    print("⚠️ 降級使用模型: models/gemini-1.5-pro")

# ==========================================
# API 路由區塊
# ==========================================

@app.route('/api/questions', methods=['GET'])
def get_questions():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet("Questions")
        records = worksheet.get_all_records()
        return jsonify({"status": "success", "data": records})
    except Exception as e:
        print(f"💥 讀取題庫失敗: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/generate_hint', methods=['POST'])
def generate_hint():
    try:
        data = request.json
        question = data.get('question', '')
        prompt = f"題目：「{question}」。請提供逐步翻譯(Chaining)的起手式提示，不要給答案。"
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "hint": response.text})
    except Exception as e:
        print(f"💥 AI 提示失敗: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_gemini():
    try:
        data = request.json
        raw_history = data.get('history', [])
        gemini_history = []
        for msg in raw_history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        if gemini_history and gemini_history[0]["role"] == "model":
            gemini_history.insert(0, {"role": "user", "parts": [{"text": "你好"}]})
            
        chat = model.start_chat(history=gemini_history)
        latest_message = raw_history[-1]["content"] if raw_history else "你好"
        response = chat.send_message(latest_message)
        return jsonify({"status": "success", "reply": response.text})
    except Exception as e:
        print(f"💥 AI 對話失敗: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/eval_chaining', methods=['POST'])
def eval_chaining():
    try:
        data = request.json
        prompt = f"題目：「{data.get('question')}」，學生輸入：「{data.get('input')}」。請給予簡短回饋。"
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "feedback": response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/eval_mastery', methods=['POST'])
def eval_mastery():
    try:
        data = request.json
        prompt = f"題目：「{data.get('question')}」，學生最終答案：「{data.get('input')}」。請以 JSON 格式回傳 score (0-5), mistakes, good_points, standard_answer。"
        response = model.generate_content(prompt)
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        import json
        return jsonify({"status": "success", "data": json.loads(raw_text)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/log', methods=['POST'])
def universal_log():
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header != 'Bearer 12345': return jsonify({"status": "error", "message": "拒絕存取"}), 403
        data = request.json
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet(data.get('sheet_name'))
        worksheet.append_row(data.get('row_data'))
        return jsonify({"status": "success", "message": "寫入成功"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
