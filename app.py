from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import random
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ==========================================
# 1. 設置 Google Sheets API (維持原樣)
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
# 2. 設置 API Key 輪詢邏輯 (多金鑰支援)
# ==========================================
# 支援多個金鑰，請在環境變數用逗號隔開：Key1,Key2,Key3
raw_keys = os.environ.get('GEMINI_API_KEY', '')
API_KEYS = [k.strip() for k in raw_keys.split(',') if k.strip()]

def get_ai_model():
    """隨機挑選一個 Key 並返回初始化好的模型"""
    if not API_KEYS:
        raise ValueError("❌ 找不到任何有效的 GEMINI_API_KEY！")
    
    # 隨機選一個
    selected_key = random.choice(API_KEYS)
    genai.configure(api_key=selected_key)
    
    system_instruction = "你是一個負責指導學測英文翻譯的高中英文老師。請用蘇格拉底教學法引導學生，每次回覆低於 50 字。"
    
    # 優先嘗試 1.5-flash
    try:
        return genai.GenerativeModel('models/gemini-1.5-flash', system_instruction=system_instruction)
    except:
        return genai.GenerativeModel('models/gemini-1.5-pro', system_instruction=system_instruction)

# ==========================================
# API 路由區塊 (加入自動重試邏輯)
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
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_gemini():
    data = request.json
    raw_history = data.get('history', [])
    
    # 建立重試機制：如果一組 Key 爆了，就試另一組
    max_retries = min(len(API_KEYS), 3)
    last_error = ""

    for i in range(max_retries):
        try:
            model = get_ai_model()
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
            last_error = str(e)
            print(f"⚠️ 第 {i+1} 組金鑰失效，正在嘗試下一組... 錯誤: {last_error}")
            continue
            
    return jsonify({"status": "error", "message": f"所有金鑰皆失效或額度爆掉: {last_error}"}), 500

# 為了精簡，其他 generate_hint 等路由也套用 get_ai_model() 即可
@app.route('/api/generate_hint', methods=['POST'])
def generate_hint():
    try:
        data = request.json
        model = get_ai_model()
        prompt = f"題目：「{data.get('question')}」。請提供 Chaining 提示，不要答案。"
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "hint": response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/log', methods=['POST'])
def universal_log():
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header != 'Bearer 12345': return jsonify({"status": "error", "message": "拒絕"}), 403
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
