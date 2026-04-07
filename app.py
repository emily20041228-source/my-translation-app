from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import random
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ==========================================
# 1. 設置 Google Sheets API
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'service_account.json'
SHEET_ID = '16y0ew8cL_t6m4EBol7lJGZnb87jF1sKOu3atTrN-cLA' 

def get_gspread_client():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"找不到憑證檔案 {CREDENTIALS_FILE}")
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(credentials)

# ==========================================
# 2. 金鑰輪詢與模型獲取
# ==========================================
raw_keys = os.environ.get('GEMINI_API_KEY', '')
API_KEYS = [k.strip() for k in raw_keys.split(',') if k.strip()]

def get_ai_model(instruction=""):
    if not API_KEYS:
        raise ValueError("❌ 找不到 GEMINI_API_KEY")
    selected_key = random.choice(API_KEYS)
    genai.configure(api_key=selected_key)
    
    # 預設老師指令
    default_instruction = "你是一個負責指導學測英文翻譯的高中英文老師。請用蘇格拉底教學法引導學生，每次回覆低於 50 字。"
    final_instruction = instruction if instruction else default_instruction
    
    try:
        return genai.Generative('gemini-1.5-flash', system_instruction=final_instruction)
    except:
        return genai.Generative('gemini-1.5-pro', system_instruction=final_instruction)

# ==========================================
# API 路由區塊 (全方位自動重試)
# ==========================================

@app.route('/api/questions', methods=['GET'])
def get_questions():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet("Questions")
        return jsonify({"status": "success", "data": worksheet.get_all_records()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def retry_ai_call(prompt_func):
    """通用的 AI 重試包裝器"""
    max_retries = min(len(API_KEYS), 3)
    last_err = ""
    for i in range(max_retries):
        try:
            return prompt_func()
        except Exception as e:
            last_err = str(e)
            print(f"⚠️ 金鑰失效 ({i+1})，重試中...")
            continue
    raise Exception(last_err)

@app.route('/api/generate_hint', methods=['POST'])
def generate_hint():
    try:
        data = request.json
        def call():
            m = get_ai_model()
            p = f"題目：「{data.get('question')}」。請提供 Chaining 提示，不要答案。"
            return m.generate_content(p).text
        return jsonify({"status": "success", "hint": retry_ai_call(call)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_gemini():
    try:
        data = request.json
        def call():
            m = get_ai_model()
            hist = []
            for msg in data.get('history', [])[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                hist.append({"role": role, "parts": [{"text": msg["content"]}]})
            if hist and hist[0]["role"] == "model": hist.insert(0, {"role": "user", "parts": [{"text": "你好"}]})
            chat = m.start_chat(history=hist)
            return chat.send_message(data.get('history')[-1]["content"]).text
        return jsonify({"status": "success", "reply": retry_ai_call(call)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/eval_chaining', methods=['POST'])
def eval_chaining():
    try:
        data = request.json
        def call():
            m = get_ai_model("你是一個溫和的翻譯助教。如果學生寫錯了，點出哪裡拼錯或文法不對，給出小提示糾正；如果學生寫對了部分，請大力稱讚，並引導他繼續翻譯下一小段。")
            p = f"題目：「{data.get('question')}」，學生輸入：「{data.get('input')}」。字數 50 字以內，不要給解答。"
            return m.generate_content(p).text
        return jsonify({"status": "success", "feedback": retry_ai_call(call)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/eval_mastery', methods=['POST'])
def eval_mastery():
    try:
        data = request.json
        def call():
            m = get_ai_model("你是一位嚴苛但客觀的學測中心閱卷委員。")
            p = f"題目：「{data.get('question')}」，學生答案：「{data.get('input')}」。請以 JSON 格式回報：score (0-5), mistakes (array), good_points (array), standard_answer (string)。"
            res = m.generate_content(p).text
            return json.loads(res.replace("```json", "").replace("```", "").strip())
        return jsonify({"status": "success", "data": retry_ai_call(call)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/log', methods=['POST'])
def universal_log():
    try:
        if request.headers.get('Authorization') != 'Bearer 12345': return jsonify({"status": "error", "message": "Denied"}), 403
        data = request.json
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        sh.worksheet(data.get('sheet_name')).append_row(data.get('row_data'))
        return jsonify({"status": "success", "message": "OK"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
