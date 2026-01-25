from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os
import warnings
import requests
import tempfile
import threading
import random
import subprocess
import re
import zipfile
import webbrowser
from urllib.parse import quote
from werkzeug.exceptions import HTTPException

warnings.filterwarnings("ignore")

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    app.logger.exception("Unhandled exception")
    return jsonify({'error': str(e)}), 500

driver_lock = threading.Lock()
driver_instance = None

# Configuración de Selenium
def get_chrome_info():
    for binary in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(binary)
        if not path:
            continue
        try:
            output = subprocess.check_output([path, "--version"], text=True).strip()
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
            return path, match.group(1) if match else None
        except Exception:
            return path, None
    return None, None

def download_chromedriver(chrome_version):
    if not chrome_version:
        return None

    dest_dir = os.path.join(tempfile.gettempdir(), f"chromedriver-{chrome_version}")
    binary_path = os.path.join(dest_dir, "chromedriver-linux64", "chromedriver")
    if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
        return binary_path

    url = (
        "https://storage.googleapis.com/chrome-for-testing-public/"
        f"{chrome_version}/linux64/chromedriver-linux64.zip"
    )
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return None
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, "chromedriver.zip")
        with open(zip_path, "wb") as f:
            f.write(response.content)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_dir)
        if os.path.isfile(binary_path):
            os.chmod(binary_path, 0o755)
            return binary_path
    except Exception:
        return None

    return None


def ensure_profile_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return False
    return os.path.isdir(path) and os.access(path, os.W_OK)


def get_driver():
    global driver_instance
    if driver_instance:
        try:
            driver_instance.title  # simple call to verify session
            return driver_instance
        except Exception:
            try:
                driver_instance.quit()
            except Exception:
                pass
            driver_instance = None

    options = Options()
    headless_env = os.getenv("WHATSAPP_HEADLESS", "0") == "1"
    headless = headless_env or not os.getenv("DISPLAY")
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    user_agent = os.getenv("WHATSAPP_USER_AGENT")
    if user_agent:
        options.add_argument(f"--user-agent={user_agent}")
    default_profile = os.path.join(os.path.expanduser("~"), "DispatcherWhatsAppProfile")
    profile_dir = os.getenv("WHATSAPP_PROFILE_DIR", default_profile)
    if not ensure_profile_dir(profile_dir):
        profile_dir = default_profile
        ensure_profile_dir(profile_dir)
    options.add_argument(f"--user-data-dir={profile_dir}")
    extra_flags = os.getenv("CHROME_FLAGS")
    if extra_flags:
        for flag in extra_flags.split("|"):
            flag = flag.strip()
            if flag:
                options.add_argument(flag)
    chrome_path, _chrome_version = get_chrome_info()
    if chrome_path:
        options.binary_location = chrome_path
    # Prefer a downloaded chromedriver compatible with this Chrome
    downloaded_driver = download_chromedriver(_chrome_version)
    if downloaded_driver:
        service = Service(downloaded_driver, log_path="/tmp/chromedriver.log")
        driver_instance = webdriver.Chrome(service=service, options=options)
        return driver_instance

    # Fallback to system chromedriver/chromium if present
    chromedriver_path = shutil.which("chromedriver")
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser")
    if chromium_path:
        options.binary_location = chromium_path
    if chromedriver_path:
        service = Service(chromedriver_path, log_path="/tmp/chromedriver.log")
        driver_instance = webdriver.Chrome(service=service, options=options)
        return driver_instance

    # Last resort: Selenium Manager (uses system browser/driver if available)
    try:
        driver_instance = webdriver.Chrome(options=options)
        return driver_instance
    except Exception:
        pass

    raise RuntimeError(
        "Chrome/Chromedriver no disponible. Instala Google Chrome/Chromium y chromedriver en el servidor, "
        "o asegúrate de que el servidor tenga salida a Internet para descargar el driver compatible. "
        "Si Chrome se cierra al iniciar, revisa /tmp/chromedriver.log."
    )


def ensure_logged_in(driver):
    driver.get("https://web.whatsapp.com")
    wait = WebDriverWait(driver, 20)
    try:
        # Espera hasta que aparezca el panel/chat list o la caja de búsqueda
        wait.until(
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//div[@id='pane-side']")),
                EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @contenteditable='true' and (contains(@aria-label,'Search') or contains(@aria-label,'Buscar'))]"))
            )
        )
        return True
    except TimeoutException:
        return False



def wait_for_chat_input(driver, timeout=30):
    wait = WebDriverWait(driver, timeout)
    xpaths = [
        "//footer//div[@role='textbox' and @contenteditable='true']",
        "//div[@role='textbox' and @contenteditable='true' and (contains(@aria-label,'message') or contains(@aria-label,'mensaje') or contains(@aria-label,'Message'))]",
        "//div[@contenteditable='true'][@data-tab='10']"
    ]
    last_error = None
    for xpath in xpaths:
        try:
            return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        except TimeoutException as exc:
            last_error = exc
            continue
    raise last_error

def click_send_button(driver):
    xpaths = [
        "//span[@data-icon='send']",
        "//button[@data-testid='compose-btn-send']",
        "//span[@data-testid='send']"
    ]
    for xpath in xpaths:
        try:
            button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            button.click()
            return True
        except TimeoutException:
            continue
    return False

def normalize_file_links(data):
    file_links = data.get('fileLinks')
    if isinstance(file_links, list):
        return [link for link in file_links if link]
    single_link = data.get('fileLink')
    if single_link:
        return [single_link]
    return []


@app.route('/open_whatsapp', methods=['POST'])
def open_whatsapp():
    driver = get_driver()
    with driver_lock:
        driver.get("https://web.whatsapp.com")
    return jsonify({'status': 'opened'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_csv():
    try:
        import pandas as pd
        import openpyxl
    except ImportError:
        return jsonify({'error': 'Pandas or openpyxl not available'})
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        # Mapear columnas a las esperadas: country_code, phone, name, message, file_link
        column_mapping = {
            'country_code': ['country_code', 'codigo_pais', 'country code', 'código de país'],
            'phone': ['phone', 'telefono', 'número', 'numero', 'teléfono'],
            'name': ['name', 'nombre'],
            'message': ['message', 'mensaje'],
            'file_link': ['file_link', 'archivo', 'file link', 'link archivo']
        }
        mapped_data = []
        for _, row in df.iterrows():
            item = {}
            for key, possible_names in column_mapping.items():
                for col in df.columns:
                    if col.lower().strip() in [p.lower() for p in possible_names]:
                        item[key] = str(row[col]) if pd.notna(row[col]) else ''
                        break
                if key not in item:
                    item[key] = ''
            mapped_data.append(item)
        return jsonify({'data': mapped_data})
    return jsonify({'error': 'Invalid file'})

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    file_links = normalize_file_links(data)
    if not phone or not message:
        return jsonify({'error': 'Phone and message required'})
    
    # Si el teléfono no comienza con +, asumimos que es local y necesitamos country_code
    if not phone.startswith('+'):
        country_code = data.get('country_code', '57')  # Default Colombia
        phone = f"+{country_code}{phone}"
    
    try:
        driver = get_driver()
    except Exception as e:
        return jsonify({'error': str(e)})
    with driver_lock:
        if not ensure_logged_in(driver):
            return jsonify({'error': 'WhatsApp no está autenticado. Abre WhatsApp Web en el navegador del servidor y escanea el QR.'})
        try:
            encoded_message = quote(message)
            driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0")
            chat_input = wait_for_chat_input(driver, 30)

            for file_link in file_links:
                response = requests.get(file_link, timeout=15)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(response.content)
                        file_path = tmp_file.name

                    attach_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//span[@data-icon='clip'] | //span[@data-testid='clip']")))
                    attach_button.click()

                    file_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                    file_input.send_keys(file_path)

                    time.sleep(5)
                    os.unlink(file_path)

            if not click_send_button(driver):
                chat_input.send_keys(Keys.ENTER)
            time.sleep(2)
            return jsonify({'status': 'Message sent'})
        except Exception as e:
            return jsonify({'error': str(e)})

@app.route('/send_all', methods=['POST'])
def send_all():
    data = request.json
    messages = data.get('contacts', data.get('messages', []))
    global_message = data.get('message')
    global_file_links = normalize_file_links(data)
    min_interval = data.get('min_interval', 2)  # segundos
    max_interval = data.get('max_interval', 4)  # segundos
    try:
        driver = get_driver()
    except Exception as e:
        return jsonify({'error': str(e)})
    with driver_lock:
        if not ensure_logged_in(driver):
            return jsonify({'error': 'WhatsApp no está autenticado. Abre WhatsApp Web en el navegador del servidor y escanea el QR.'})

        if not global_message and not any(msg.get('message') for msg in messages):
            return jsonify({'error': 'Message required'})

        for msg in messages:
            phone = msg.get('phone')
            message = global_message or msg.get('message')
            file_links = global_file_links or normalize_file_links(msg)
            if not phone or not message:
                continue
            if not phone.startswith('+'):
                country_code = msg.get('country_code', '57')
                phone = f"+{country_code}{phone}"

            try:
                encoded_message = quote(message)
                driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0")
                chat_input = wait_for_chat_input(driver, 30)

                for file_link in file_links:
                    response = requests.get(file_link, timeout=15)
                    if response.status_code == 200:
                        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                            tmp_file.write(response.content)
                            file_path = tmp_file.name

                        attach_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//span[@data-icon='clip'] | //span[@data-testid='clip']")))
                        attach_button.click()

                        file_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                        file_input.send_keys(file_path)

                        time.sleep(5)
                        os.unlink(file_path)

                if not click_send_button(driver):
                    chat_input.send_keys(Keys.ENTER)
                time.sleep(2)
            except Exception as e:
                print(f"Error sending to {phone}: {e}")

            interval = random.uniform(min_interval, max_interval)
            time.sleep(interval)

    return jsonify({'status': f'Sent {len(messages)} messages with random intervals'})

@app.route('/health')
def health():
    return jsonify({'status': 'OK'})

if __name__ == '__main__':
    def open_ui():
        if os.getenv("DISPATCHER_AUTO_OPEN", "1") == "1":
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:5000")

    threading.Thread(target=open_ui, daemon=True).start()
    try:
        from waitress import serve
        serve(app, host='127.0.0.1', port=5000)
    except Exception:
        app.run(host='127.0.0.1', debug=False, use_reloader=False)