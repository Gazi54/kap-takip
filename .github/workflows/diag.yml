"""KAP'a GitHub sunucusundan erişilebiliyor mu? Sadece teşhis içindir."""
import requests

H = {
    "Origin": "https://www.kap.org.tr",
    "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

URLS = [
    "https://www.kap.org.tr/tr/api/company/items/YK/A",
    "https://www.kap.org.tr/tr/api/company/items/HT/A",
    "https://www.kap.org.tr/tr/bildirim-sorgu",
]

for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=30)
        print("URL:", u)
        print("  durum:", r.status_code, "| tür:", r.headers.get("content-type"))
        print("  sunucu:", r.headers.get("server"), "| uzunluk:", len(r.text))
        print("  başlangıç:", r.text[:200].replace("\n", " "))
    except Exception as e:
        print("URL:", u, "-> HATA:", e)
