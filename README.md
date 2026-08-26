# 🎓 Çukurova Üniversitesi SKS Kısmi Zamanlı Öğrenci İlan Takip Botu

Bu bot, **Çukurova Üniversitesi Sağlık Kültür ve Spor Daire Başkanlığı (SKS)** bünyesindeki kısmi zamanlı öğrenci iş ilanlarını ve sınav duyurularını her gün otomatik olarak takip eder. 

Yeni bir iş ilanı veya sınav tarihi eklendiğinde size anında **e-posta** ile bildirim gönderir.

---

## 🚀 Özellikler

- **%100 Ücretsiz & Sunucusuz:** GitHub Actions üzerinde çalışır, bilgisayarınızın açık kalmasına gerek yoktur.
- **Her Sabah Otomatik Kontrol:** Her gün Türkiye saati ile **sabah 08:00'de** çalışır.
- **Akıllı Fark Tespiti:** Yalnızca yeni bir ilan eklendiğinde, kaldırıldığında veya sınav duyurusu yapıldığında e-posta gönderir; gereksiz mail kalabalığı yapmaz.
- **Şık HTML E-posta Bildirimi:** İlan birimi, başvuru süresi, sınav detayları ve başvuru linklerini içeren kart tasarımı ile gelir.
- **Tek Tıkla Manuel Tetikleme:** GitHub arayüzündeki "Run workflow" butonuyla istediğiniz zaman tek tıkla çalıştırabilirsiniz.

---

## ⚙️ Kurulum ve Yapılandırma (2 Dakika)

Botun size e-posta gönderebilmesi için Gmail veya Outlook hesabınızı GitHub deponuza güvenli bir şekilde bağlamanız gerekir.

### Adım 1: Gmail "Uygulama Şifresi" (App Password) Alma

> [!NOTE]
> Normal e-posta şifrenizi **kullanmayacaksınız**. Google, üçüncü parti otomasyonlar için 16 haneli özel bir "Uygulama Şifresi" üretir.

1. [Google Hesap Güvenliği](https://myaccount.google.com/security) sayfasına gidin.
2. Hesabınızda **2 Adımlı Doğrulama**'nın açık olduğundan emin olun.
3. Arama çubuğuna **"Uygulama şifreleri"** (veya *App Passwords*) yazıp tıklayın (veya doğrudan [bu linke](https://myaccount.google.com/apppasswords) gidin).
4. Bir isim verin (Örneğin: `SKS Takip Botu`) ve **Oluştur** butonuna tıklayın.
5. Ekranınıza gelen **16 haneli sarı kutucuktaki şifreyi** (boşlukları olmadan) kopyalayın.

---

### Adım 2: GitHub Repository Secrets Eklemek

1. GitHub'da bu deponun sayfasına gidin.
2. Üst menüden **Settings** > sol menüden **Secrets and variables** > **Actions** seçeneğine tıklayın.
3. **New repository secret** butonuna basarak aşağıdaki değişkenleri tek tek ekleyin:

| Secret Adı | Değer / Açıklama |
| :--- | :--- |
| `EMAIL_SENDER` | E-postayı gönderecek Gmail adresiniz (Örn: `adiniz@gmail.com`) |
| `EMAIL_PASSWORD` | Adım 1'de aldığınız 16 haneli Uygulama Şifresi (Örn: `abcd efgh ijkl mnop`) |
| `EMAIL_RECEIVER` | Bildirimin gelmesini istediğiniz e-posta adresi (Gönderici ile aynı olabilir) |

*(İsteğe bağlı olarak birden fazla alıcıya mail gitmesi için `EMAIL_RECEIVER` kısmına virgülle ayırarak birden çok mail yazabilirsiniz: `ali@gmail.com, veli@gmail.com`)*

---

## 🧪 Sistemi Test Etme

### 1. GitHub Üzerinden Test
1. Deponuzdaki **Actions** sekmesine gidin.
2. Sol menüden **"SKS Kısmi Zamanlı İlan Takipçisi"** seçeneğine tıklayın.
3. Sağ taraftaki **"Run workflow"** butonuna basarak işlemi anında manuel olarak başlatın.

### 2. Kendi Bilgisayarınızda Yerel Test

Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

Yalnızca sayfayı kontrol edip durumu ekrana yazdırmak için:
```bash
python tracker.py --test
```

Değişiklik olmasa bile örnek bir test e-postası göndermek için:
```bash
# Windows PowerShell için:
$env:EMAIL_SENDER="adiniz@gmail.com"
$env:EMAIL_PASSWORD="uygulama_sifreniz"
python tracker.py --force-email
```

---

## 📁 Proje Yapısı

```
cu-sks-takip/
├── .github/
│   └── workflows/
│       └── tracker.yml         # Her sabah 08:00'de çalışan zamanlanmış iş akışı
├── data/
│   └── last_state.json        # Önceki ilan durumunu tutan hafıza dosyası
├── tracker.py                 # Web kazıma, fark bulma ve mail atma betiği
├── requirements.txt           # Python bağımlılıkları (requests, beautifulsoup4)
└── README.md                  # Kurulum ve kullanım kılavuzu
```

---

## 🔗 İlgili Bağlantılar

- [Çukurova Üniversitesi SKS Kısmi Zamanlı İlanlar Sayfası](https://sks.cu.edu.tr/cu/kismi-zamanli-ogrenci-destek/kismi-zamanli-ogrenci-is-ilanlari-ve-sinavlari)