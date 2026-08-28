# Testler

```bash
./ops/test_calistir.sh
```

## İzolasyon

Testler **üretim veritabanına dokunmaz**, ve bu yorumla değil kodla garanti:

- Ayrı bir veritabanı kullanılıyor (`binaryenerji_test`)
- `tests/conftest.py` içindeki koruma, veritabanı adı beklenen değilse
  **tüm oturumu durduruyor** — yanlış yapılandırılmış bir çalıştırma
  production'a yazmak yerine hiç başlamıyor
- Her test kendi işleminde çalışıp geri alınıyor, testler birbirini de
  kirletmiyor

## Neler test ediliyor

| Dosya | Kapsam |
|---|---|
| `test_fatura.py` | Reaktif ceza (tamamı/aşan kısım), zaman dilimi fiyatları, güç aşımı, toplam tutarlılığı, öneri metinleri |
| `test_erisim.py` | Organizasyon/tesis/bölüm kapsamı, çapraz müşteri sızıntısı, bildirim alıcılarının panelle aynı kapsamı kullanması |
| `test_abonelik.py` | Aktif/deneme/süresi dolmuş/iptal, uyarı eşiği, `expired`'ın saklanmayıp hesaplanması |
| `test_enerji_delta.py` | Saatlik artış, saatler arası boşluk, **sayaç sıfırlanması** |
| `test_guc_kalitesi.py` | Kapalı cihaz aralıklarının ihlal sayılmaması, ölçülmeyen parametrenin "kaldı" gösterilmemesi, yetersiz veride uygunluk beyan edilmemesi, EN 50160 sınırları |

## Testlerin gerçekten koruduğu doğrulandı

Bir test paketinin geçmesi, regresyonu yakalayacağı anlamına gelmez. Üç
kritik davranış kasten bozulup doğru testlerin düştüğü görüldü:

| Bozulan | Düşen test |
|---|---|
| Reaktif ceza modu (tamamı → aşan kısım) | `test_limit_asilinca_tamami_faturalanir` |
| Tesis yöneticisi kapsam kontrolü | 3 erişim testi |
| Sayaç sıfırlaması ele alınması | 4 delta testi |
