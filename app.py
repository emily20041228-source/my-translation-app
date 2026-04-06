from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import google.generativeai as genai

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
        raise FileNotFoundError(f"找不到憑證檔案 {CREDENTIALS_FILE}，請確認是否已下載並放置正確位置。")
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(credentials)

# ==========================================
# 2. 設置 Google Gemini API
# ==========================================
GEMINI_API_KEY = 'AIzaSyB4oQg8kF0Cfur9opv5TYtjLnHaALyik88'
genai.configure(api_key=GEMINI_API_KEY)

# 初始化模型與系統提示詞
system_instruction = """
你是一個負責指導學測英文翻譯的高中英文老師。請嚴格遵從以下 7 個步驟引導學生，運用蘇格拉底教學法。

【🚨對話核心原則🚨 - 絕對要遵守】
1. 極度精簡：每次回覆字數強烈建議低於 50 字。廢話少說。
2. 一次一問：每次結尾只能丟出「一個」具體、封閉或簡單的問題。
3. 直接了當：不要長篇大論解釋前面的規矩，學生答對就說「很好！那...」，然後立刻進下一步。

【7步驟引導】(一次只推進一步)
1. 語意核心：請學生找出中文句子的「主詞」與「動詞」。
2. 字彙選擇：針對這題的難字，提供 2~3 個 CEEC 四級選項讓學生「選擇」。
3. 句型架構：問學生這裡的語法結構（例如：該用關係子句嗎？用什麼時態？）。
4. 切分翻譯：請學生只翻出「某個小短語」。
5. 語序重組：把前面的碎片組合順序。
6. 細節監控：抓漏（冠詞、單複數、時態）。
7. 完整產出：請學生打出完整的一句，你再給予超精簡的總評分。

請一律用繁體中文。請確保你現在的第一句話立刻是提出第1步驟的問題。
"""
model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)


# ==========================================
# API 路由區塊
# ==========================================

import random

@app.route('/api/questions', methods=['GET'])
def get_questions():
    """從 Google Sheets 取得題目庫"""
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet("Questions")
        
        # get_all_records 會把第一行標題當作 key，返回 dict 陣列
        records = worksheet.get_all_records()
        if not records:
            return jsonify({"status": "error", "message": "題庫工作表是空的"}), 404
            
        return jsonify({"status": "success", "data": records})
    except gspread.exceptions.WorksheetNotFound:
        return jsonify({"status": "error", "message": "找不到名為 'Questions' 的工作表"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/generate_hint', methods=['POST'])
def generate_hint():
    """讓 AI 為 Chaining 模式自動產生提示"""
    try:
        data = request.json
        question = data.get('question', '')
        if not question:
            return jsonify({"status": "error", "message": "未提供題目"}), 400
            
        prompt = (f"學生正在練習學測英文翻譯，題目是：「{question}」。"
                  f"請你提供一個『逐步翻譯(Chaining)』的起手式提示。"
                  f"引導學生先翻出前幾個字或是句子的主要結構即可，請用溫和的口語提出，"
                  f"注意：絕對不要給出完整的英文翻譯！只要給開頭的提示就好。")
                  
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "hint": response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_gemini():
    """蘇格拉底對話端點"""
    try:
        data = request.json
        # 前端傳來的紀錄：[{"role": "user", "content": "..."}, {"role": "ai", "content": "..."}]
        raw_history = data.get('history', [])
        
        # 轉換成 Gemini 的特定格式 (user / model)
        gemini_history = []
        for msg in raw_history:
            # 最新的一句話不放進歷史裡，要單獨傳送
            if msg == raw_history[-1]: 
                continue
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})
            
        # 修復：Gemini 歷史紀錄必須由 user 開頭
        if gemini_history and gemini_history[0]["role"] == "model":
            gemini_history.insert(0, {"role": "user", "parts": [{"text": "你好"}]})
        
        # 開啟 Gemini 的對話引擎
        chat = model.start_chat(history=gemini_history)
        
        # 取得學生最新傳來的那句話送給 Gemini
        latest_message = raw_history[-1]["content"] if raw_history else "你好！"
        response = chat.send_message(latest_message)
        
        return jsonify({"status": "success", "reply": response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/eval_chaining', methods=['POST'])
def eval_chaining():
    """Chaining 模式的段落自動回饋"""
    try:
        data = request.json
        question = data.get('question', '')
        user_input = data.get('input', '')
        if not question or not user_input:
            return jsonify({"status": "error", "message": "缺失題目或作答資料"}), 400
            
        prompt = (f"學生正在翻譯：「{question}」。\n"
                  f"學生目前的進度是：「{user_input}」。\n"
                  f"請你做一個溫和的助教。如果學生寫錯了，點出哪裡拼錯或文法不對，給出小提示糾正；"
                  f"如果學生寫對了部分，請大力稱讚，並引導他繼續翻譯下一小段。"
                  f"注意：字數限制在 50 字以內，極度精簡，絕對不要直接給完整的解答！")
                  
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "feedback": response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/eval_mastery', methods=['POST'])
def eval_mastery():
    """Mastery 模式的總成績單與大考閱卷"""
    try:
        data = request.json
        question = data.get('question', '')
        user_input = data.get('input', '')
        if not question or not user_input:
            return jsonify({"status": "error", "message": "缺失題目或作答資料"}), 400
            
        prompt = (f"學生已提交大考英文翻譯測驗。題目：「{question}」。學生的最終答案：「{user_input}」。\n"
                  f"你是一位嚴苛但客觀的學測中心閱卷委員。請以 JSON 格式回傳一份成績單，完全不要回傳任何額外文字，只要 JSON 格式，包含以下欄位：\n"
                  f"{{\n"
                  f"  \"score\": (0到5的數字，代表得分，5為滿分。文法/拼字錯誤扣分),\n"
                  f"  \"mistakes\": [\"錯誤點1\", \"錯誤點2\"... (如果沒有請空陣列)],\n"
                  f"  \"good_points\": [\"優點1\", \"優點2\"... (肯定好的用詞)],\n"
                  f"  \"standard_answer\": \"(提供一句最漂亮的大考中心滿分標準翻譯)\"\n"
                  f"}}")
                  
        response = model.generate_content(prompt)
        # 簡單清除可能包含的 markdown json 標記
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        import json
        result_data = json.loads(raw_text)
        return jsonify({"status": "success", "data": result_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/log', methods=['POST'])
def universal_log():
    """全域日誌記錄：將資料存入不同的 Worksheet"""
    auth_header = request.headers.get('Authorization')
    if auth_header != 'Bearer 12345':
        return jsonify({"status": "error", "message": "密碼錯誤，拒絕寫入"}), 403

    data = request.json
    sheet_name = data.get('sheet_name')  # "Chaining", "Socratic", 或 "Mastery"
    row_data = data.get('row_data')      # 要寫入的資料陣列
    
    if not sheet_name or not row_data or not isinstance(row_data, list):
         return jsonify({"status": "error", "message": "請提供正確的 sheet_name 與 row_data 陣列"}), 400

    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        
        # 根據參數選擇對應的工作表去寫入
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(row_data)
        return jsonify({"status": "success", "message": f"成功寫入 {sheet_name} 工作表"})
    except gspread.exceptions.WorksheetNotFound:
        return jsonify({"status": "error", "message": f"找不到名為 '{sheet_name}' 的工作表，請先在 Google Sheets 建立"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
