# ANL21 Güç Analizörü: Ölçümden Müşteri Raporuna

## Özet

Bu çalışma, Grup Arge ANL21 güç analizöründen alınan üç fazlı elektrik ölçümlerini ESP32 tabanlı bir ağ geçidiyle sunucuya taşır. Sunucu veriyi zaman serisi olarak saklar, enerji ve güç kalitesi göstergelerini hesaplar; web ve mobil uygulamalar da müşteriye canlı izleme, geçmiş karşılaştırması, alarm ve dönemsel rapor sunar.

Bu belge sistemin çalışma biçimini anlatır. Örnek cihaz kimlikleri, alan adları ve sunucu adresleri temsili tutulmuştur. Gerçek Wi-Fi bilgileri, MQTT kullanıcı adı/parolası, API anahtarları, JWT sırları, e-posta/ödeme servis anahtarları, müşteri bilgileri ve sunucu erişim ayrıntıları bu makalede yer almaz.

## 1. Sistem akışı

```text
ANL21 güç analizörü
    │ RS-485 / Modbus RTU
    ▼
ESP32 ağ geçidi
    │ MQTT + TLS, cihaz kimliği ve yetkilendirme
    ▼
MQTT broker (sunucu)
    │ canlı ölçüm mesajları
    ▼
API ve veri işleme katmanı ─────► zaman serisi veritabanı
    │                                      │
    ├── WebSocket: canlı ekran             ├── ham ölçümler
    ├── REST API: geçmiş ve analiz          ├── saatlik özetler
    └── rapor üretimi                       └── alarm ve rapor girdileri
             │
             ▼
      Web ve mobil uygulamalar
      Canlı izleme · analiz · müşteri raporu
```

## 2. Analizörden ESP32'ye: ölçümün alınması

ANL21 ile ESP32 arasındaki fiziksel bağlantı RS-485 üzerinden Modbus RTU olarak kurulur. ESP32, seri hat üzerinden analizörün kayıt haritasındaki ölçüm bloklarını okur. Okumalar faz gerilimi ve akımı, aktif/reaktif/görünür güç, frekans, güç faktörü, harmonik bozulma ve enerji sayaçları gibi grupları kapsar. Bazı değerler birden çok 16 bit Modbus kaydına yayıldığı için firmware bunları işaretli 32 bit veya 64 bit sayılara birleştirir; ardından cihaz kılavuzundaki ölçek katsayılarını uygular.

Firmware yalnızca anlık değerlerle sınırlı değildir. Uygun kayıt bloklarından minimum/maksimum değerler, demand değerleri, tek harmonikler ve cihaz bilgileri de toplanır. Her okuma grubunun kendi adresleme ve veri türü bulunur. Bu nedenle register haritası üretici dokümanına göre ele alınır; belirsiz veri genişlikleri ve kelime sıralaması varsayımla genişletilmek yerine ayrıca doğrulanır.

ESP32, cihaz kimliğini donanımın MAC adresinden türetilmiş kısa bir takma adla oluşturur (ör. `anl21-<cihaz-soneki>`). Böylece aynı firmware farklı cihazlara yüklenebilir ve her birinin mesajı sunucuda ayrıştırılabilir. Firmware ayrıca bağlantı kesilmelerinde yeniden bağlanmayı, MQTT mesajlarını Modbus işlemleri arasında canlı tutmayı ve uzaktan güncellemelerde başarısız yazılımı geri almayı hedefler.

## 3. ESP32'den sunucuya: güvenli telemetri

Ölçümler JSON mesajları olarak MQTT başlıklarına (topic) gönderilir. Topic yapısı cihaz kimliğini ve veri grubunu taşır; örneğin canlı değerler, enerji sayaçları, durum, harmonikler ve tepe değerleri farklı topic'lerde tutulur. Periyodik canlı ölçüm yaklaşık birkaç saniyede bir yayımlanır; daha seyrek okunan analiz blokları kendi döngülerinde gönderilir.

İletişimde TLS kullanılır ve ESP32 sunucu sertifikasını doğrular. Cihaz kimlik bilgileri firmware içindeki ayrı bir yerel sır dosyasından sağlanır; bu dosya örnek şablonla paylaşılır, gerçek değerler kaynak depoya eklenmez. Sunucu tarafında broker anonim bağlantıyı kabul etmez ve topic erişimi ACL kurallarıyla sınırlandırılır. Cihaz ekleme/yenileme akışında kimlik bilgileri güvenli biçimde hazırlanır; gerçek parolalar bu makalede veya örnek komutlarda gösterilmez.

Bu tasarım, ölçümlerin aktarım sırasında okunması veya yetkisiz bir istemcinin başka cihaza ait topic'lere erişmesi riskini azaltır. TLS tek başına cihazın doğru topic'e yazdığını garanti etmez; broker kimlik doğrulaması ve topic yetkileri de bu nedenle veri akışının parçasıdır.

## 4. Sunucu veriyi nasıl işler?

MQTT broker mesajı API'nin dinleyicisine iletir. API, cihaz kimliğini ve mesaj türünü topic/payload üzerinden belirler; alanları doğrular ve ilgili veri tablosuna yazar. Canlı elektrik ölçümleri zaman damgasıyla zaman serisi tablosuna eklenir. Enerji sayaçları, durum ve cihaz bilgileri ayrı saklanır; demand, harmonik ve minimum/maksimum grupları da kendi yapılarında tutulur.

Veri katmanında ham zaman serisi ile türetilmiş özetler birlikte kullanılır:

- **Ham ölçümler:** faz bazında gerilim, akım, güç, frekans ve güç kalitesi alanları.
- **Enerji:** aktif tüketim/üretim ve reaktif enerji sayaçlarının artışları.
- **Zaman pencereleri:** raporlamayı hızlandırmak için saatlik ve 15 dakikalık gruplamalar.
- **Analiz verileri:** demand tepeleri, harmonikler, minimum/maksimum değerler ve cihaz bilgileri.
- **İşletim verileri:** cihazın son görülme zamanı, bağlantı durumu, alarmlar ve kullanıcı ayarları.

Enerji toplamlarında sayaç sıfırlanması veya taşması gibi durumlar, ardışık sayaç farkı hesaplanırken ele alınır. Zaman damgaları saklama ve raporlama sırasında tutarlı zaman diliminde işlenir. İstemciye veri sunulmadan önce API kullanıcı oturumunu ve kullanıcının ilgili cihaza erişim yetkisini kontrol eder.

Canlı MQTT mesajı aynı zamanda bağlı istemcilere WebSocket üzerinden iletilir; böylece ekranı yenilemeden güncellenebilir. Geçmiş dönem ve analiz ekranları ise kimlik doğrulamalı REST uç noktalarından sorgulanır. MQTT cihaz ile sunucu arasındaki taşıma kanalıdır; mobil/web uygulamasının broker'a doğrudan bağlanması gerekmez.

## 5. Ölçümden değerlendirmeye

Uygulamalar ham değerleri tek başına bırakmak yerine müşteri için okunabilir göstergelere dönüştürür:

1. **Canlı izleme:** faz bazında gerilim, akım ve güç; toplam güç/enerji; bağlantı ve veri akışı durumu.
2. **Tüketim ve üretim eğilimi:** gün/saat bazında enerji değişimi ve seçilen dönemlerin karşılaştırması.
3. **Güç kalitesi:** güç faktörü, gerilim/akım harmonikleri ve gerilim uygunluğu gibi ölçüm tabanlı göstergeler.
4. **Demand ve tepe değerleri:** dönem içindeki en yüksek talepler ve sözleşme gücü girilmişse olası aşımın görünür kılınması.
5. **Reaktif enerji ve tarife etkisi:** tarife bilgileri girildiğinde reaktif tüketim/üretim ve maliyet etkisinin dönem bazında hesaplanması.
6. **Alarm ve olay özeti:** eşik ihlalleri, veri akışının kesilmesi ve ilgili dönem içindeki olaylar.

Bu göstergeler teknik ölçümü işletme kararlarına bağlar: hangi fazın dengesiz göründüğü, talebin ne zaman yükseldiği, güç kalitesi değerlerinin nasıl değiştiği veya tarifeye göre hangi kalemlerin maliyeti etkilediği incelenebilir. Sonuçlar ölçüm ve yapılandırılmış tarife bilgisine dayanır; tek başına ekipman arızasının kesin teşhisi veya mevzuat uygunluk belgesi olarak değerlendirilmemelidir.

## 6. Müşteriye sunulan rapor

Müşteri web veya mobil uygulamada cihazını seçerek canlı ekranlara ve dönemsel analizlere ulaşır. Yetkiye bağlı olarak geçmiş ölçümleri, enerji eğilimlerini, demand/reaktif değerlendirmesini ve alarm özetini inceler. Sistem ayrıca seçilen ay için PDF rapor oluşturabilir. Rapor; dönem bilgisi, cihaz etiketi, tüketim/enerji özeti, talep ve reaktif maliyet bileşenleri, grafikler ve ölçümlere dayalı öneriler gibi bölümleri bir araya getirir.

Müşteriye sunulan değerlendirme, ham kayıtların saklanabilir olmasını ve hesaplanan sonuçların kaynak ölçümlere bağlanabilmesini amaçlar. Tarife, sözleşme gücü veya cihaz saati gibi kullanıcı tarafından girilen bilgiler eksik ya da hatalıysa maliyet hesapları da değişebilir; rapor bu parametrelerle birlikte yorumlanmalıdır. PDF ve ekranlarda gerçek müşteri adı, telefon, e-posta, adres veya hesap bilgisi ancak müşterinin yetkili oturumunda gösterilir; teknik makale ve herkese açık örneklerde anonimleştirilir.

## 7. ANL21 kapsamı ve doğrulama

ANL21 firmware'i, farklı genişlikte register'lar ve geniş ölçüm grupları için ayrı okuma/çözümleme mantığı içerir. Sunucu, web paneli ve mobil uygulama bu cihaz sınıfının özet, tepe, demand, harmonik ve cihaz bilgisi verilerini gösterecek şekilde genişletilmiştir. Proje kayıtlarında firmware'in gerçek cihazda denenip kapsamlı ekranlarının uygulamalarda doğrulandığı belirtiliyor; bazı nadir bozulma işaretleri için tekrar deneme mekanizması da not edilmiş. Sahadaki her cihaz ve her ölçüm grubu için sonuçlar ayrıca doğrulanmalıdır.

Üretimde bu akışın güvenilirliği; register haritasının cihaz dokümanıyla karşılaştırılması, referans ölçü aletiyle değer kontrolü, bağlantı kesintisi senaryoları, zaman damgası ve enerji farklarının incelenmesiyle değerlendirilir. Bir özellik ya da eşik, doğrulama yapılmadan tüm cihazlarda aynı sonucu verecekmiş gibi sunulmamalıdır.

## 8. Gizlilik ve yayın ilkeleri

Bu makale uygulama akışını açıklamak için yazılmıştır; kurulum kılavuzu veya erişim belgesi değildir. Yayınlanabilir örneklerde:

- Parola, API anahtarı, token, özel anahtar ve sertifika kimlik bilgisi paylaşılmaz.
- Üretim IP'si, SSH kullanıcı adı/anahtarı, özel servis yolları ve iç ağ ayrıntıları genelleştirilir.
- Cihaz seri numarası/MAC adresi, kullanıcı adı, e-posta, telefon ve müşteri verisi örneklerden çıkarılır.
- `.env`, `secrets.h`, servis hesabı anahtarı, veritabanı yedeği ve derlenmiş firmware gibi dosyalar makaleye eklenmez.
- Örnek kimlik ve adresler temsilidir; gerçek sistemdeki değerleri tarif etmez.

Bu kurallarla makale, ESP32'den müşterinin değerlendirme ekranına kadar olan süreci açıklarken kullanılabilir sırları ve kişisel bilgileri açığa çıkarmaz.
