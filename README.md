# e-Okul Fotoğraf Küçültücü

Öğrenci fotoğraflarını e-Okul'a uygun hâle getiren masaüstü aracı: yüzü otomatik bulur,
133×171 piksel oranında kırpar, gerekirse elle ince ayar yaptırır ve JPG olarak kaydeder.

Kaydedilen fotoğraflar masaüstündeki `eOkul_Hazir_Fotograflar` klasörüne yazılır.

## Çalıştırma

Kurulu sürümde `launcher.pyw`, uygulamayla gelen `python_runtime\pythonw.exe` ile `main.py`'yi başlatır.

Geliştirme için: Python 3.12, `pip install -r requirements.txt`, ardından `python main.py`.

## Dosyalar

- `main.py`: yüz algılama, kırpma ve kaydetme (yerel sunucu + uygulama penceresi)
- `launcher.pyw`: kurulu sürümün başlatıcısı
- `static/`: arayüz (`index.html`, `app.js`, Cropper.js)
- `haarcascade_frontalface_default.xml`: OpenCV yüz algılama modeli
