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


def download_chrome_for_testing():
	platform_map = {
		"nt": "win64",
		"posix": "linux64"
	}
	platform = platform_map.get(os.name)
	if not platform:
		return None, None

	url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
	try:
		response = requests.get(url, timeout=30)
		response.raise_for_status()
		data = response.json()
		stable = data.get("channels", {}).get("Stable", {})
		version = stable.get("version")
		downloads = stable.get("downloads", {})
		chrome_url = next((d["url"] for d in downloads.get("chrome", []) if d.get("platform") == platform), None)
		driver_url = next((d["url"] for d in downloads.get("chromedriver", []) if d.get("platform") == platform), None)
		if not (version and chrome_url and driver_url):
			return None, None

		dest_dir = os.path.join(tempfile.gettempdir(), f"chrome-for-testing-{version}")
		chrome_path = os.path.join(dest_dir, f"chrome-{platform}", "chrome.exe" if os.name == "nt" else "chrome")
		driver_path = os.path.join(dest_dir, f"chromedriver-{platform}", "chromedriver.exe" if os.name == "nt" else "chromedriver")

		if os.path.isfile(chrome_path) and os.path.isfile(driver_path):
			return chrome_path, driver_path

		os.makedirs(dest_dir, exist_ok=True)
		chrome_zip = os.path.join(dest_dir, "chrome.zip")
		driver_zip = os.path.join(dest_dir, "chromedriver.zip")

		chrome_resp = requests.get(chrome_url, timeout=60)
		chrome_resp.raise_for_status()
		with open(chrome_zip, "wb") as f:
			f.write(chrome_resp.content)

		driver_resp = requests.get(driver_url, timeout=60)
		driver_resp.raise_for_status()
		with open(driver_zip, "wb") as f:
			f.write(driver_resp.content)

		with zipfile.ZipFile(chrome_zip) as zf:
			zf.extractall(dest_dir)
		with zipfile.ZipFile(driver_zip) as zf:
			zf.extractall(dest_dir)

		if os.path.isfile(chrome_path) and os.path.isfile(driver_path):
			if os.name != "nt":
				os.chmod(chrome_path, 0o755)
				os.chmod(driver_path, 0o755)
			return chrome_path, driver_path
	except Exception:
		return None, None

	return None, None


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
	if os.name == "nt":
		headless = headless_env
	else:
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
	if not chrome_path:
		chrome_path, downloaded_driver = download_chrome_for_testing()
		if chrome_path and downloaded_driver:
			options.binary_location = chrome_path
			service = Service(downloaded_driver, log_path="/tmp/chromedriver.log")
			driver_instance = webdriver.Chrome(service=service, options=options)
			return driver_instance
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

def wait_for_element(driver, xpaths, timeout=15, clickable=False):
	wait = WebDriverWait(driver, timeout)
	for xpath in xpaths:
		try:
			if clickable:
				return wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
			return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
		except TimeoutException:
			continue
	return None

def click_send_button(driver, timeout=15):
	xpaths = [
		"//button[@data-testid='send']",
		"//button[contains(@data-testid,'send')]",
		"//span[@data-icon='send']",
		"//span[@data-testid='send']",
		"//div[@role='button' and (@aria-label='Send' or @aria-label='Enviar')]",
		"//button[@aria-label='Send' or @aria-label='Enviar']"
	]
	for _ in range(2):
		button = wait_for_element(driver, xpaths, timeout=timeout, clickable=True)
		if button:
			try:
				button.click()
				return True
			except Exception:
				pass
		time.sleep(0.5)
	return False

def attach_files(driver, file_paths):
	if not file_paths:
		return False
	attach_xpaths = [
		"//span[@data-icon='clip']",
		"//span[@data-testid='clip']",
		"//div[@role='button' and (@aria-label='Attach' or @aria-label='Adjuntar')]",
		"//button[@title='Attach' or @title='Adjuntar']",
		"//div[@title='Attach' or @title='Adjuntar']"
	]
	file_input_xpaths = [
		"//input[@type='file' and @data-testid='attach-doc']",
		"//input[@type='file' and @data-testid='attach-document']",
		"//input[@type='file' and @data-testid='attach-file-input']",
		"//input[@type='file' and @accept]",
		"//input[@type='file']"
	]
	preview_xpaths = [
		"//div[@data-testid='media-preview']",
		"//div[contains(@class,'media-preview')]",
		"//div[@data-testid='media-preview-section']"
	]
	send_xpaths = [
		"//button[@data-testid='send']",
		"//span[@data-icon='send']",
		"//span[@data-testid='send']"
	]
	for _ in range(3):
		attach_button = wait_for_element(driver, attach_xpaths, timeout=12, clickable=True)
		if not attach_button:
			time.sleep(1)
			continue
		try:
			attach_button.click()
		except Exception:
			time.sleep(0.5)
		file_input = wait_for_element(driver, file_input_xpaths, timeout=12, clickable=False)
		if not file_input:
			try:
				inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
				if inputs:
					file_input = inputs[-1]
			except Exception:
				file_input = None
		if not file_input:
			time.sleep(1)
			continue
		try:
			file_input.send_keys("\n".join(file_paths))
		except Exception:
			time.sleep(1)
			continue
		if wait_for_element(driver, preview_xpaths, timeout=20, clickable=False) or wait_for_element(driver, send_xpaths, timeout=15, clickable=True):
			return True
		time.sleep(1)
	return False

def set_media_caption(driver, message):
	if not message:
		return False
	caption_xpaths = [
		"//div[@role='textbox' and @contenteditable='true' and (contains(@aria-label,'caption') or contains(@aria-label,'mensaje') or contains(@aria-label,'message') or contains(@aria-label,'Agregar un mensaje') or contains(@aria-label,'Add a caption'))]",
		"//div[@contenteditable='true' and @data-testid='media-caption-input-container']"
	]
	caption = wait_for_element(driver, caption_xpaths, timeout=6, clickable=True)
	if not caption:
		return False
	try:
		caption.click()
		caption.send_keys(message)
		return True
	except Exception:
		return False

def ensure_message_sent(driver, chat_input, message):
	if not message:
		return True
	try:
		driver.execute_script("arguments[0].focus();", chat_input)
	except Exception:
		pass
	existing = ""
	try:
		existing = (chat_input.get_attribute("innerText") or "").strip()
	except Exception:
		existing = ""
	if not existing:
		try:
			chat_input.send_keys(message)
		except Exception:
			pass
	if click_send_button(driver):
		return True
	try:
		chat_input.send_keys(Keys.ENTER)
		return True
	except Exception:
		return False

def normalize_file_links(data):
	file_links = data.get('fileLinks')
	if isinstance(file_links, list):
		return [link for link in file_links if link]
	single_link = data.get('fileLink')
	if single_link:
		return [single_link]
	return []


def render_message(template, name=None):
	if not template:
		return template
	if not name:
		name = ""
	return template.replace("{name}", name).replace("{{name}}", name)


def parse_request_payload():
	if request.content_type and request.content_type.startswith("multipart/form-data"):
		payload_raw = request.form.get("payload")
		payload = {}
		if payload_raw:
			try:
				import json as _json
				payload = _json.loads(payload_raw)
			except Exception:
				payload = {}
		files = request.files.getlist("files")
		return payload, files
	return request.get_json(force=True, silent=True) or {}, []


def save_uploaded_files(files):
	saved_paths = []
	if not files:
		return saved_paths
	for uploaded in files:
		if not uploaded or not uploaded.filename:
			continue
		suffix = os.path.splitext(uploaded.filename)[1]
		tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
		tmp.close()
		uploaded.save(tmp.name)
		saved_paths.append(tmp.name)
	return saved_paths


def _extract_drive_id(url):
	match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
	if match:
		return match.group(1)
	match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
	if match:
		return match.group(1)
	return None


def download_file_from_link(url, timeout=30):
	if not url:
		return None
	drive_id = _extract_drive_id(url)
	if drive_id:
		try:
			import gdown
			tmp_file = tempfile.NamedTemporaryFile(delete=False)
			tmp_file.close()
			gdown.download(id=drive_id, output=tmp_file.name, quiet=True)
			if os.path.isfile(tmp_file.name) and os.path.getsize(tmp_file.name) > 0:
				return tmp_file.name
		except Exception:
			return None

	response = requests.get(url, timeout=timeout)
	if response.status_code != 200 or not response.content:
		return None
	with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
		tmp_file.write(response.content)
		return tmp_file.name


@app.route('/open_whatsapp', methods=['POST'])
def open_whatsapp():
	global driver_instance
	try:
		driver = get_driver()
		with driver_lock:
			driver.get("https://web.whatsapp.com")
		return jsonify({'status': 'opened'})
	except Exception:
		try:
			if driver_instance:
				driver_instance.quit()
		except Exception:
			pass
		driver_instance = None
		try:
			driver = get_driver()
			with driver_lock:
				driver.get("https://web.whatsapp.com")
			return jsonify({'status': 'opened'})
		except Exception:
			return jsonify({'error': 'Could not open WhatsApp session', 'error_code': 'error_whatsapp_open_failed'}), 500

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
	data, uploaded_files = parse_request_payload()
	phone = data.get('phone')
	message_template = data.get('message')
	name = data.get('name')
	file_links = normalize_file_links(data)
	upload_paths = save_uploaded_files(uploaded_files)
	download_paths = []
	row_index = data.get('row_index')
	message = render_message(message_template, name)
	if not phone or not message:
		return jsonify({
			'error': 'Phone and message required',
			'error_code': 'error_phone_message_required',
			'row_index': row_index
		})
    
	# Si el teléfono no comienza con +, asumimos que es local y necesitamos country_code
	if not phone.startswith('+'):
		country_code = data.get('country_code', '57')  # Default Colombia
		phone = f"+{country_code}{phone}"
    
	try:
		driver = get_driver()
	except Exception as e:
		return jsonify({'error': str(e), 'row_index': row_index})
	with driver_lock:
		if not ensure_logged_in(driver):
			return jsonify({
				'error': 'WhatsApp no está autenticado. Abre WhatsApp Web en el navegador del servidor y escanea el QR.',
				'error_code': 'error_whatsapp_not_authenticated',
				'row_index': row_index
			})
		try:
			encoded_message = quote(message)
			driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0")
			chat_input = wait_for_chat_input(driver, 20)
			try:
				chat_input.click()
			except Exception:
				pass

			file_paths = upload_paths[:]
			if file_links and not file_paths:
				for file_link in file_links:
					file_path = download_file_from_link(file_link)
					if not file_path:
						continue
					file_paths.append(file_path)
					download_paths.append(file_path)

			if file_paths:
				if not attach_files(driver, file_paths):
					raise Exception("error_attach_files")
				caption_set = set_media_caption(driver, message)
				if not click_send_button(driver, timeout=30):
					raise Exception("error_send_attachments")
				time.sleep(0.2)
				if not caption_set:
					chat_input = wait_for_chat_input(driver, 15)
					if not ensure_message_sent(driver, chat_input, message):
						raise Exception("error_send_message")
			else:
				if not ensure_message_sent(driver, chat_input, message):
					raise Exception("error_send_message")
			time.sleep(0.2)
			return jsonify({'status': 'Message sent', 'row_index': row_index})
		except Exception as e:
			error_key = str(e)
			error_payload = {'error': error_key, 'row_index': row_index}
			if error_key.startswith('error_'):
				error_payload['error_code'] = error_key
			return jsonify(error_payload)
		finally:
			for path in upload_paths:
				try:
					os.unlink(path)
				except Exception:
					pass
			for path in download_paths:
				try:
					os.unlink(path)
				except Exception:
					pass

@app.route('/send_all', methods=['POST'])
def send_all():
	data, uploaded_files = parse_request_payload()
	messages = data.get('contacts', data.get('messages', []))
	global_message = data.get('message')
	global_file_links = normalize_file_links(data)
	upload_paths = save_uploaded_files(uploaded_files)
	min_interval = data.get('min_interval', 1)  # segundos
	max_interval = data.get('max_interval', 2)  # segundos
	try:
		min_interval = float(min_interval)
		max_interval = float(max_interval)
	except Exception:
		min_interval = 1
		max_interval = 2
	if max_interval < min_interval:
		max_interval = min_interval
	min_interval = max(0.5, min_interval)
	max_interval = max(0.5, max_interval)
	try:
		driver = get_driver()
	except Exception as e:
		return jsonify({'error': str(e)})
	with driver_lock:
		if not ensure_logged_in(driver):
			return jsonify({
				'error': 'WhatsApp no está autenticado. Abre WhatsApp Web en el navegador del servidor y escanea el QR.',
				'error_code': 'error_whatsapp_not_authenticated'
			})

		if not global_message and not any(msg.get('message') for msg in messages):
			return jsonify({'error': 'Message required', 'error_code': 'error_message_required'})

		results = []

		file_paths_global = upload_paths[:]
		download_paths = []
		if global_file_links and not file_paths_global:
			for file_link in global_file_links:
				file_path = download_file_from_link(file_link)
				if file_path:
					file_paths_global.append(file_path)
					download_paths.append(file_path)

		for msg in messages:
			phone = msg.get('phone')
			message_template = global_message or msg.get('message')
			message = render_message(message_template, msg.get('name'))
			file_links = global_file_links or normalize_file_links(msg)
			row_index = msg.get('row_index')
			if not phone or not message:
				results.append({'row_index': row_index, 'status': 'skipped'})
				continue
			if not phone.startswith('+'):
				country_code = msg.get('country_code', '57')
				phone = f"+{country_code}{phone}"

			try:
				encoded_message = quote(message)
				driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0")
				chat_input = wait_for_chat_input(driver, 20)
				try:
					chat_input.click()
				except Exception:
					pass

				file_paths = file_paths_global[:]
				if file_links and not file_paths:
					for file_link in file_links:
						file_path = download_file_from_link(file_link)
						if not file_path:
							continue
						file_paths.append(file_path)

				if file_paths:
					if not attach_files(driver, file_paths):
						raise Exception("error_attach_files")
					caption_set = set_media_caption(driver, message)
					if not click_send_button(driver, timeout=30):
						raise Exception("error_send_attachments")
					time.sleep(0.2)
					if not caption_set:
						chat_input = wait_for_chat_input(driver, 15)
						if not ensure_message_sent(driver, chat_input, message):
							raise Exception("error_send_message")
				else:
					if not ensure_message_sent(driver, chat_input, message):
						raise Exception("error_send_message")
				time.sleep(0.2)
				results.append({'row_index': row_index, 'status': 'sent'})
			except Exception as e:
				error_key = str(e)
				print(f"Error sending to {phone}: {error_key}")
				result = {'row_index': row_index, 'status': 'error', 'error': error_key}
				if error_key.startswith('error_'):
					result['error_code'] = error_key
				results.append(result)

			interval = random.uniform(min_interval, max_interval)
			time.sleep(interval)

	try:
		return jsonify({'status': f'Sent {len(messages)} messages with random intervals', 'results': results})
	finally:
		for path in upload_paths:
			try:
				os.unlink(path)
			except Exception:
				pass
		for path in download_paths:
			try:
				os.unlink(path)
			except Exception:
				pass

@app.route('/health')
def health():
	return jsonify({'status': 'OK'})

if __name__ == '__main__':
	def open_ui():
		if os.getenv("DISPATCHER_AUTO_OPEN", "1") == "1":
			time.sleep(1.5)
			webbrowser.open("http://127.0.0.1:5000")
		if os.getenv("DISPATCHER_AUTO_OPEN_SELENIUM", "0") == "1":
			try:
				driver = get_driver()
				with driver_lock:
					driver.get("https://web.whatsapp.com")
			except Exception:
				pass

	threading.Thread(target=open_ui, daemon=True).start()
	try:
		from waitress import serve
		serve(app, host='127.0.0.1', port=5000)
	except Exception:
		app.run(host='127.0.0.1', debug=False, use_reloader=False)