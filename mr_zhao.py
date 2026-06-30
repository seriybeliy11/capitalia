import time
import csv
import os
import random
import requests
from config_zhao import BOT_TOKEN, DIFY_API_KEY, DIFY_URL

BOT_TOKEN = BOT_TOKEN
DIFY_API_KEY = DIFY_API_KEY
DIFY_URL =  DIFY_URL

# --- КОНФИГУРАЦИЯ ---
CSV_FILE = "database.csv"

# --- ПРОМПТЫ ДЛЯ DIFY ---
FREE_PROMPT = """Tu és um assistente de busca rápido. Usa o CONTEXT para encontrar programas (Sebrae, BNDES, etc).
Responda de forma muito curta (2-3 linhas). No final, adicione EXATAMENTE este texto:
"⚠️ Para receber o **Roteiro de Aprovação** completo (com Radar de Recusa e Carta de Motivação pronta), pague 3 USDT. Digite /pay"
CONTEXT: {context}"""

PAID_PROMPT = """Tu és um consultor sênior de financiamento do Brasil. O usuário PAGOU por um Roteiro de Aprovação detalhado. Use APENAS o CONTEXT.
Sua resposta DEVE seguir esta estrutura:
1. 🎯 **PROGRAMA IDEAL:** Nome e valor.
2. ⚠️ **RADAR DE RECUSA:** O que pode dar erro no formulário e como evitar.
3. 📝 **CARTA DE MOTIVAÇÃO:** Um parágrafo de 3 frases para ele copiar e colar no site do governo.
4. 🛠️ **PASSO A PASSO:** O que clicar.
CONTEXT: {context}"""

# --- РАБОТА С CSV ---
def init_csv():
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "balance_usdt", "ref_code", "invited_by", "reminder_date"])

def get_user(user_id):
    with open(CSV_FILE, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['user_id']) == user_id:
                return row
    return None

def save_or_update_user(user_id, balance=0.0, ref_code=None, invited_by=None, reminder_date=""):
    rows = []
    exists = False
    try:
        with open(CSV_FILE, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['user_id']) == user_id:
                    exists = True
                    if balance != 0: row['balance_usdt'] = float(row['balance_usdt']) + balance
                    if ref_code: row['ref_code'] = ref_code
                    if invited_by is not None: row['invited_by'] = invited_by
                    if reminder_date: row['reminder_date'] = reminder_date
                rows.append(row)
    except FileNotFoundError:
        pass

    if not exists:
        new_ref = f"REF{random.randint(1000, 9999)}"
        rows.append({
            "user_id": user_id, 
            "balance_usdt": balance, 
            "ref_code": new_ref, 
            "invited_by": invited_by or "", 
            "reminder_date": reminder_date or ""
        })

    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "balance_usdt", "ref_code", "invited_by", "reminder_date"])
        writer.writeheader()
        writer.writerows(rows)
        
    return get_user(user_id) # Возвращаем обновленные данные

# --- ЛОГИКА DIFY ---
def ask_dify(user_id, message_text):
    user = get_user(user_id)
    balance = float(user['balance_usdt']) if user else 0.0

    if balance >= 0.01:
        prompt = PAID_PROMPT
        save_or_update_user(user_id, balance=-0.01) # Списываем за ответ
    else:
        prompt = FREE_PROMPT

    payload = {
        "inputs": {},
        "query": message_text,
        "response_mode": "blocking",
        "conversation_id": "",
        "user": f"tg_{user_id}",
        "messages": [
            {"role": "system", "content": prompt}, 
            {"role": "user", "content": message_text}
        ]
    }
    
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
    
    try:
        # УВЕЛИЧЕН ТАЙМАУТ! PythonAnywhere бесплатный тариф часто "засыпает". 
        # Первое обращение к Dify может идти до 30 секунд.
        resp = requests.post(DIFY_URL, json=payload, headers=headers, timeout=45)
        return resp.json().get('answer', 'Erro ao contatar a IA.')
    except requests.exceptions.Timeout:
        return "⏳ O servidor demorou para responder (PythonAnywhere acordando). Por favor, envie sua mensagem novamente."
    except Exception as e:
        return f"Erro: {str(e)}"

# --- ОТПРАВКА СООБЩЕНИЙ В TELEGRAM ---
def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки ТГ: {e}")

# --- ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ ---
def process_message(message):
    chat_id = message['chat']['id']
    text = message.get('text', '')
    user_id = chat_id

    if text.startswith('/start'):
        args = text.split()
        invited_by = args[1] if len(args) > 1 else None
        
        user = save_or_update_user(user_id, invited_by=invited_by)
        bot_username = "ТВОЙ_ЮЗЕРНЕЙМ_В_ТЕЛЕГРАМЕ" # Без @, например: mr_zhao_bot
        
        welcome = f"Olá! Sou seu assistente de subsídios (Sebrae, BNDES).\nSeu saldo: {user['balance_usdt']} USDT.\n\nMe diga seu segmento e cidade para achar editais."
        
        if not invited_by:
            welcome += f"\n\n🔗 Seu link de indicação: https://t.me/{bot_username}?start={user['ref_code']}\n(Convide amigos e ganhe 1 USDT!)"
            
        send_telegram(chat_id, welcome)

    elif text.lower() == '/pay':
        # МОК-ФУНКЦИЯ 2328.io 
        send_telegram(chat_id, 
            "💳 Pagamento de 3 USDT (TRC20).\n\n"
            "[СЮДА БУДЕТ ССЫЛКА НА ОПЛАТУ 2328.io]\n\n"
            "⚠️ ВРЕМЕННО ДЛЯ ТЕСТОВ: Напиши /addfunds"
        )

    elif text.lower() == '/addfunds':
        # Эмуляция успеха оплаты 2328.io
        user = save_or_update_user(user_id, balance=3.0)
        
        # --- ЛОГИКА РЕФЕРАЛОВ ---
        if user and user['invited_by']:
            inviter_code = user['invited_by']
            with open(CSV_FILE, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['ref_code'] == inviter_code:
                        inviter_id = int(row['user_id'])
                        inviter_user = save_or_update_user(inviter_id, balance=1.0)
                        send_telegram(inviter_id, f"🎉 Seu amigo pagou! +1 USDT. Seu saldo agora: {inviter_user['balance_usdt']}")
                        break
        
        send_telegram(chat_id, "✅ Баланс пополнен на 3 USDT. Задавайте вопрос!")

    else:
        # Обычный текст от пользователя
        if not get_user(user_id):
            process_message({'chat': {'id': user_id}, 'text': '/start'}) # Авто-регистрация
            return

        send_telegram(chat_id, "⏳ Analisando editais...")
        answer = ask_dify(user_id, text)
        send_telegram(chat_id, answer)

# --- ОСНОВНОЙ ЦИКЛ (LONG POLLING) ---
def main():
    print("Бот запущен на чистом requests...")
    offset = 0
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()

            if data.get("ok"):
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    if "message" in result:
                        # Запускаем обработку в фоне, чтобы бот не зависал, если Dify думает долго
                        import threading
                        threading.Thread(target=process_message, args=(result["message"],)).start()
            else:
                print("Ошибка API Telegram:", data)
                time.sleep(5)

        except requests.exceptions.Timeout:
            # Нормальное поведение для Long Polling, просто продолжаем цикл
            continue
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            time.sleep(10) # Ждем 10 секунд при падении и пытаемся снова

if __name__ == "__main__":
    init_csv()
    main()
