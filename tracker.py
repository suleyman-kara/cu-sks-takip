"""
Çukurova Üniversitesi SKS Kısmi Zamanlı Öğrenci İş İlanı & Sınav Takip Botu
"""

import os
import sys
import json
import smtplib
import argparse
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
import urllib.request
import ssl
from bs4 import BeautifulSoup

# Windows konsolunda Türkçe karakterlerin düzgün görünmesi için
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Sayfa URL'leri
IFRAME_URL = "https://sksoto.cu.edu.tr/burs/yarizaman-monitor.asp"
MAIN_PAGE_URL = "https://sks.cu.edu.tr/cu/kismi-zamanli-ogrenci-destek/kismi-zamanli-ogrenci-is-ilanlari-ve-sinavlari"
BURS_SISTEM_URL = "https://sks.cu.edu.tr/burs"

# Durum dosyası yolu
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "last_state.json")

# Türkiye Saati (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))


def fetch_url(url: str, timeout: int = 15) -> str:
    """Verilen URL'yi uygun header ve encoding ile çeker."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
        raw_data = response.read()
        # Kodlama tespiti (ASP sayfaları genellikle windows-1254 veya iso-8859-9'dur)
        for encoding in ["windows-1254", "iso-8859-9", "utf-8", "latin-1"]:
            try:
                return raw_data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw_data.decode("utf-8", errors="replace")


def parse_sks_data() -> dict:
    """SKS yarizaman-monitor sayfasını ve duyuru sayfasını ayrıştırır."""
    result = {
        "jobs": [],
        "exams": [],
        "announcement_text": "",
        "checked_at": datetime.now(TURKEY_TZ).strftime("%d.%m.%Y %H:%M:%S")
    }

    # 1. Iframe içeriğini çek ve ayrıştır
    try:
        iframe_html = fetch_url(IFRAME_URL)
        soup = BeautifulSoup(iframe_html, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            text = table.get_text()
            rows = table.find_all("tr")
            
            # İş İlanları Tablosu
            if "Açılan Yarızamanlı Öğrenci İş İlanları" in text and "Sınav Tarihleri" not in text:
                for row in rows:
                    cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if not cols or len(cols) < 3:
                        continue
                    # Başlık satırlarını ve 'aktif iş ilanı yoktur' mesajını atla
                    if "Birim" in cols[0] or "Açılan Yarızamanlı" in cols[0]:
                        continue
                    if "aktif iş ilanı yoktur" in cols[0].lower():
                        continue
                    
                    result["jobs"].append({
                        "unit": cols[0],
                        "title": cols[1],
                        "deadline": cols[2]
                    })

            # Sınav Tarihleri Tablosu
            elif "Sınav Tarihleri ve Yerleri" in text:
                for row in rows:
                    cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if not cols or len(cols) < 3:
                        continue
                    if "Birim" in cols[0] or "Açılan Yarızamanlı" in cols[0]:
                        continue
                    if "aktif bir sınav kaydı yoktur" in cols[0].lower():
                        continue
                    
                    result["exams"].append({
                        "unit": cols[0],
                        "title": cols[1],
                        "exam_info": cols[2]
                    })

    except Exception as e:
        print(f"[UYARI] Iframe verisi çekilirken hata oluştu: {e}")

    # 2. Ana duyuru sayfasındaki metin notlarını çek
    try:
        main_html = fetch_url(MAIN_PAGE_URL)
        main_soup = BeautifulSoup(main_html, "html.parser")
        content_div = main_soup.find("div", class_="blog-post__content")
        if content_div:
            # Iframe hariç metni al
            for iframe in content_div.find_all("iframe"):
                iframe.decompose()
            result["announcement_text"] = content_div.get_text(strip=True)
    except Exception as e:
        print(f"[UYARI] Ana sayfa verisi çekilirken hata oluştu: {e}")

    return result


def load_previous_state() -> dict:
    """Kayıtlı önceki durumu dosyadan okur."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[UYARI] Durum dosyası okunamadı: {e}")
    return {"jobs": [], "exams": [], "announcement_text": ""}


def save_current_state(state: dict):
    """Güncel durumu dosyaya kaydeder."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def generate_email_content(changes: dict, current_state: dict) -> tuple[str, str]:
    """E-posta konu ve HTML/Düz metin içeriğini oluşturur."""
    subject = "🎓 Çukurova Üni. SKS - Kısmi Zamanlı Öğrenci İlanı Güncellemesi!"
    
    new_jobs = changes.get("new_jobs", [])
    removed_jobs = changes.get("removed_jobs", [])
    new_exams = changes.get("new_exams", [])

    # Düz metin versiyonu
    text_lines = [
        "Çukurova Üniversitesi SKS Kısmi Zamanlı Öğrenci Takip Bildirimi",
        "=" * 60,
        f"Kontrol Tarihi: {current_state.get('checked_at', '')}",
        ""
    ]

    if new_jobs:
        text_lines.append("📢 YENİ EKLENEN İŞ İLANLARI:")
        for j in new_jobs:
            text_lines.append(f"- Birim: {j['unit']}")
            text_lines.append(f"  İlan Adı: {j['title']}")
            text_lines.append(f"  Son Başvuru: {j['deadline']}")
            text_lines.append("")

    if new_exams:
        text_lines.append("📝 YENİ EKLENEN SINAV BİLGİLERİ:")
        for ex in new_exams:
            text_lines.append(f"- Birim: {ex['unit']}")
            text_lines.append(f"  İlan Adı: {ex['title']}")
            text_lines.append(f"  Sınav Tarihi/Yeri: {ex['exam_info']}")
            text_lines.append("")

    if removed_jobs:
        text_lines.append("ℹ️ KALDIRILAN / SÜRESİ DOLAN İLANLAR:")
        for j in removed_jobs:
            text_lines.append(f"- {j['unit']} / {j['title']}")
        text_lines.append("")

    text_lines.append("Başvuru Sistemi: " + BURS_SISTEM_URL)
    text_lines.append("İlan Sayfası: " + MAIN_PAGE_URL)
    plain_text = "\n".join(text_lines)

    # Modern ve Şık HTML Şablonu
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #ffffff; padding: 25px 20px; text-align: center; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 20px; font-weight: 700; }}
        .header p {{ margin: 0; font-size: 13px; opacity: 0.9; }}
        .content {{ padding: 25px 20px; }}
        .alert-box {{ background-color: #e8f4fd; border-left: 4px solid #1e88e5; padding: 12px 15px; margin-bottom: 20px; border-radius: 4px; font-size: 14px; }}
        .section-title {{ font-size: 16px; font-weight: 700; color: #1e3c72; border-bottom: 2px solid #eef2f5; padding-bottom: 8px; margin-top: 20px; margin-bottom: 15px; }}
        .job-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 12px; }}
        .job-card strong {{ color: #0f172a; display: block; font-size: 15px; margin-bottom: 6px; }}
        .job-meta {{ font-size: 13px; color: #475569; margin: 3px 0; }}
        .badge {{ display: inline-block; padding: 3px 8px; font-size: 11px; font-weight: 600; border-radius: 12px; background: #dbeafe; color: #1e40af; }}
        .badge-exam {{ background: #fef3c7; color: #92400e; }}
        .btn {{ display: inline-block; background-color: #1e3c72; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; font-size: 14px; text-align: center; margin-top: 15px; }}
        .footer {{ background: #f8fafc; text-align: center; padding: 15px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Çukurova Üniversitesi SKS</h1>
          <p>Kısmi Zamanlı Öğrenci İlan Takip Sistemi</p>
        </div>
        <div class="content">
          <div class="alert-box">
            🕒 <strong>Son Kontrol:</strong> {current_state.get('checked_at', '')} tarihinde sistemde değişiklik tespit edildi.
          </div>
    """

    if new_jobs:
        html += '<div class="section-title">📢 Yeni Eklenen İş İlanları</div>'
        for j in new_jobs:
            html += f"""
            <div class="job-card">
              <span class="badge">YENİ İŞ İLANI</span>
              <strong>{j['title']}</strong>
              <div class="job-meta">🏢 <strong>Birim:</strong> {j['unit']}</div>
              <div class="job-meta">⏳ <strong>Son Başvuru Tarihi:</strong> {j['deadline']}</div>
            </div>
            """

    if new_exams:
        html += '<div class="section-title">📝 Yeni Sınav / Mülakat Duyuruları</div>'
        for ex in new_exams:
            html += f"""
            <div class="job-card" style="border-left: 4px solid #f59e0b;">
              <span class="badge badge-exam">SINAV BİLGİSİ</span>
              <strong>{ex['title']}</strong>
              <div class="job-meta">🏢 <strong>Birim:</strong> {ex['unit']}</div>
              <div class="job-meta">📍 <strong>Sınav Tarihi ve Yeri:</strong> {ex['exam_info']}</div>
            </div>
            """

    if removed_jobs:
        html += '<div class="section-title" style="color: #64748b;">ℹ️ Yayından Kaldırılan / Süresi Dolan İlanlar</div><ul>'
        for j in removed_jobs:
            html += f"<li style='color: #64748b; font-size: 13px;'>{j['unit']} - {j['title']}</li>"
        html += '</ul>'

    html += f"""
          <div style="text-align: center; margin-top: 25px;">
            <a href="{BURS_SISTEM_URL}" class="btn" target="_blank">Öğrenci Burslar Sistemine Giriş Yap ↗</a>
          </div>
          <div style="text-align: center; margin-top: 10px;">
            <a href="{MAIN_PAGE_URL}" style="font-size: 12px; color: #64748b;" target="_blank">SKS Resmi İlan Sayfasını Görüntüle</a>
          </div>
        </div>
        <div class="footer">
          Bu e-posta GitHub Actions tarafından otomatik olarak gönderilmiştir.
        </div>
      </div>
    </body>
    </html>
    """

    return subject, plain_text, html


def send_email(subject: str, plain_text: str, html_content: str):
    """SMTP kullanarak yapılandırılmış alıcıya e-posta gönderir."""
    sender_email = os.environ.get("EMAIL_SENDER")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    receiver_email = os.environ.get("EMAIL_RECEIVER", sender_email)
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not sender_email or not sender_password:
        print("[HATA] EMAIL_SENDER veya EMAIL_PASSWORD ortam değişkenleri tanımlı değil!")
        print("Lütfen GitHub Repository Secrets içerisine gerekli bilgileri ekleyin.")
        return False

    receivers = [r.strip() for r in receiver_email.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    # Gönderen kısmında ismin düzgün görünmesi ve e-postanın mükerrer basılmaması için formataddr kullanılır
    msg["From"] = formataddr((str(Header("Çukurova SKS Takip", "utf-8")), sender_email))
    msg["To"] = ", ".join(receivers)


    part1 = MIMEText(plain_text, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        print(f"[BİLGİ] {smtp_server}:{smtp_port} üzerinden {len(receivers)} alıcıya e-posta gönderiliyor...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receivers, msg.as_string())
        print("[BAŞARILI] E-posta başarıyla gönderildi!")
        return True
    except Exception as e:
        print(f"[HATA] E-posta gönderilirken hata oluştu: {e}")
        return False


def find_differences(current: dict, previous: dict) -> dict:
    """Önceki durum ile şimdiki durum arasındaki farkları bulur."""
    current_jobs = current.get("jobs", [])
    prev_jobs = previous.get("jobs", [])
    current_exams = current.get("exams", [])
    prev_exams = previous.get("exams", [])

    # İlan karşılaştırması
    prev_job_keys = {(j["unit"], j["title"], j["deadline"]) for j in prev_jobs}
    new_jobs = [j for j in current_jobs if (j["unit"], j["title"], j["deadline"]) not in prev_job_keys]

    curr_job_keys = {(j["unit"], j["title"], j["deadline"]) for j in current_jobs}
    removed_jobs = [j for j in prev_jobs if (j["unit"], j["title"], j["deadline"]) not in curr_job_keys]

    # Sınav karşılaştırması
    prev_exam_keys = {(e["unit"], e["title"], e["exam_info"]) for e in prev_exams}
    new_exams = [e for e in current_exams if (e["unit"], e["title"], e["exam_info"]) not in prev_exam_keys]

    has_changes = bool(new_jobs or removed_jobs or new_exams)

    return {
        "has_changes": has_changes,
        "new_jobs": new_jobs,
        "removed_jobs": removed_jobs,
        "new_exams": new_exams
    }


def main():
    parser = argparse.ArgumentParser(description="Çukurova Üniversitesi SKS İş İlanı Takip Botu")
    parser.add_argument("--test", action="store_true", help="Yalnızca kontrol et, e-posta gönderme ve dosyayı güncelleme")
    parser.add_argument("--force-email", action="store_true", help="Değişiklik olmasa bile test amaçlı e-posta gönder")
    parser.add_argument("--init", action="store_true", help="Mevcut durumu hafızaya kaydet (ilk kurulum)")
    args = parser.parse_args()

    print(f"[{datetime.now(TURKEY_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Çukurova SKS sayfası kontrol ediliyor...")

    current_state = parse_sks_data()
    previous_state = load_previous_state()

    print(f"[BİLGİ] Bulunan güncel aktif iş ilanı sayısı: {len(current_state['jobs'])}")
    print(f"[BİLGİ] Bulunan güncel aktif sınav sayısı: {len(current_state['exams'])}")

    if args.init:
        save_current_state(current_state)
        print("[BAŞARILI] Mevcut durum başarıyla 'data/last_state.json' dosyasına kaydedildi.")
        return

    differences = find_differences(current_state, previous_state)

    if differences["has_changes"]:
        print(f"[DİKKAT] Değişiklik tespit edildi! Yeni ilan: {len(differences['new_jobs'])}, Kaldırılan: {len(differences['removed_jobs'])}, Yeni sınav: {len(differences['new_exams'])}")
        subject, plain, html = generate_email_content(differences, current_state)
        
        if not args.test:
            send_email(subject, plain, html)
            save_current_state(current_state)
        else:
            print("[TEST MODU] E-posta içeriği (Özet):")
            print(plain)
    elif args.force_email:
        print("[BİLGİ] --force-email parametresi verildi. Test e-postası hazırlanıyor...")
        test_diff = {
            "has_changes": True,
            "new_jobs": current_state["jobs"] or [{"unit": "Test Birimi (Rektörlük)", "title": "Kısmi Zamanlı Öğrenci (Örnek)", "deadline": "30.09.2026"}],
            "removed_jobs": [],
            "new_exams": current_state["exams"]
        }
        subject, plain, html = generate_email_content(test_diff, current_state)
        subject = "[TEST] " + subject
        send_email(subject, plain, html)
    else:
        print("[BİLGİ] Herhangi bir değişiklik yok. E-posta gönderilmedi.")
        # Zaman bilgisini güncelle
        previous_state["last_checked"] = current_state["checked_at"]
        if not args.test:
            save_current_state(previous_state)


if __name__ == "__main__":
    main()
