import cv2
import numpy as np
import qrcode
import re
import time
import easyocr
import firebase_admin
from firebase_admin import credentials, firestore
import threading
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime
import RPi.GPIO as GPIO

# === Firebase Setup ===
cred = credentials.Certificate('/home/pi/Downloads/qrcode-732b7-firebase-adminsdk-fbsvc-3a41af0c26.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# === Kamera Setup ===
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
time.sleep(2)

# === YOLO + OCR Setup ===
weights = "/home/pi/yolov4tinyrpi4/yolov4-tiny-custom_best.weights"
config = "/home/pi/yolov4tinyrpi4/yolov4-tiny-custom.cfg"
labels = "/home/pi/yolov4tinyrpi4/obj.names"
confidence_threshold = 0.8

from cvlib.object_detection import YOLO
yolo = YOLO(weights, config, labels)
reader = easyocr.Reader(['en'], recog_network='english_g2')

# === GPIO Setup ===
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

PIN_MERAH = 18  # GPIO18 (Pin 12)
PIN_HIJAU = 17  # GPIO17 (Pin 11)

GPIO.setup(PIN_MERAH, GPIO.OUT)
GPIO.setup(PIN_HIJAU, GPIO.OUT)

def set_merah():
    GPIO.output(PIN_MERAH, GPIO.HIGH)
    GPIO.output(PIN_HIJAU, GPIO.LOW)

def set_hijau_sementara():
    GPIO.output(PIN_MERAH, GPIO.LOW)
    GPIO.output(PIN_HIJAU, GPIO.HIGH)
    timer = threading.Timer(5.0, set_merah)  # Kembali ke merah setelah 5 detik
    timer.start()

# Set awal: Merah hidup
set_merah()

# === Global Variables ===
ocr_delay = 5
last_detected_time = 0
stop_event = threading.Event()
detected_plates = set()

# === Utility Functions ===
def safe_destroy_window(window_name):
    try:
        cv2.destroyWindow(window_name)
    except cv2.error:
        pass

def buat_qrcode_numpy(pelat_nomor):
    qr = qrcode.make(pelat_nomor)
    qr = np.array(qr.convert('L'))
    qr = cv2.resize(qr, (240, 240))
    return qr

def buat_qrcode_base64(pelat_nomor):
    qr = qrcode.make(pelat_nomor)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return qr_base64

# === Firebase Actions ===
def simpan_ke_firebase_qrcode(pelat_nomor, sudah_tampilkan=False):
    qr_base64 = buat_qrcode_base64(pelat_nomor)
    data = {
        'pelat_nomor': pelat_nomor,
        'kode_qrcode': pelat_nomor,
        'gambar_qr_base64': qr_base64,
        'waktu_dibuat': datetime.now().isoformat(),
        'sudah_tampilkan': sudah_tampilkan  # Status QR sudah ditampilkan
    }
    db.collection('qrcode_kendaraan').add(data)
    print(f"[✔] QR Code untuk Plat '{pelat_nomor}' berhasil dikirim ke Firestore dengan status sudah_tampilkan={sudah_tampilkan}.")

def simpan_ke_firebase_plat_masuk(pelat_nomor):
    timestamp = int(time.time())
    data = {
        'plat_nomor': pelat_nomor,
        'timestamp': timestamp
    }
    db.collection('plat_masuk').add(data)
    print(f"[✔] Plat Masuk '{pelat_nomor}' berhasil dikirim ke Firestore.")

def cek_qr_di_firebase_dan_hapus(qr_data):
    docs = db.collection('qrcode_kendaraan').where('kode_qrcode', '==', qr_data).stream()
    found = False
    for doc in docs:
        doc.reference.delete()
        print(f"[✔] QR cocok dan dihapus dari Firestore.")
        found = True
    if not found:
        print("[✘] QR tidak ditemukan di database!")
    return found

# === OCR Detection ===
def process_frame_for_plate(cap, last_detected_time):
    ret, img = cap.read()
    if not ret:
        return None, False, last_detected_time

    img_resized = cv2.resize(img, (680, 460))
    bbox, label, conf = yolo.detect_objects(img_resized)
    current_time = time.time()

    for i, box in enumerate(bbox):
        if conf[i] >= confidence_threshold and label[i] == 'pelat_nomor':
            if current_time - last_detected_time >= ocr_delay:
                x, y, w, h = box
                margin_x = int(0.1 * w)
                margin_y = int(0.1 * h)
                x = max(0, x - margin_x)
                y = max(0, y - margin_y)
                w = min(img_resized.shape[1], w + 2 * margin_x)
                h = min(img_resized.shape[0], h + 2 * margin_y)
                roi = img_resized[y:h, x:w]

                if roi.size != 0:
                    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
                    resized_roi = cv2.resize(blurred, (blurred.shape[1] // 2, blurred.shape[0] // 2))

                    results = reader.readtext(resized_roi)
                    if results:
                        text, prob = results[0][1], results[0][2]
                        filtered_text = re.sub('[^A-Za-z0-9]', '', text).upper()
                        print(f"[OCR] Hasil: {filtered_text}")
                        pattern = r'^[A-Z]{1,2}[0-9]{1,4}[A-Z]{1,3}$'
                        if re.match(pattern, filtered_text):
                            return filtered_text, True, current_time
                        else:
                            print("[!] Format tidak valid.")
    return None, False, last_detected_time

# === Thread Kamera ===
def kamera_thread():
    global last_detected_time
    while not stop_event.is_set():
        text, detected, last_detected_time = process_frame_for_plate(cap, last_detected_time)
        if detected and text not in detected_plates:
            detected_plates.add(text)
            print(f"[✔] Plat nomor terdeteksi: {text}")
            
            # Simpan QR Code ke Firebase dengan status sudah_tampilkan=False (belum ditampilkan)
            simpan_ke_firebase_qrcode(text, sudah_tampilkan=False)
            
            # Tampilkan QR Code
            qr_img = buat_qrcode_numpy(text)
            cv2.imshow("QR Code", qr_img)
            cv2.waitKey(10000)
            safe_destroy_window("QR Code")

            # Update status sudah_tampilkan menjadi True setelah QR Code ditampilkan
            simpan_ke_firebase_qrcode(text, sudah_tampilkan=True)
            
            # Simpan plat nomor masuk ke Firebase
            simpan_ke_firebase_plat_masuk(text)

        ret, frame = cap.read()
        if ret:
            cv2.imshow("Kamera Masuk", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            stop_event.set()
            break

# === Thread Scanner QR Manual ===
def scanner_thread():
    while not stop_event.is_set():
        try:
            scanned_data = input("[SCAN] Tempel hasil scan di sini: ").strip()
            if scanned_data:
                print(f"[✔] Data diterima dari scanner: {scanned_data}")
                if cek_qr_di_firebase_dan_hapus(scanned_data):
                    print(f"[INFO] QR Code valid dan sudah dihapus dari database.")
                    set_hijau_sementara()
                else:
                    print("[!] QR Code tidak valid atau sudah pernah digunakan!")
                    set_merah()
            time.sleep(1)
        except EOFError:
            stop_event.set()

# === MAIN ===
print("Program dimulai... Tekan [ESC] di jendela kamera untuk keluar.")

kamera_t = threading.Thread(target=kamera_thread)
scanner_t = threading.Thread(target=scanner_thread)

kamera_t.start()
scanner_t.start()

kamera_t.join()
scanner_t.join()

cap.release()
cv2.destroyAllWindows()
GPIO.cleanup()
print("[✔] Program dihentikan.")
