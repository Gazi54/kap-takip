"""KAP takip: watchlist'teki şirketlerin yeni bildirimlerini çeker,
Supabase'e yazar, Gemini ile özetler, Telegram'dan bildirir."""
import os
import time
import json
import datetime as dt
import requests
from kap_client import Kap, KapError, EmptyResponseError

SB = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
KEY = os.environ["SUPABASE_KEY"]
H = {"apikey": KEY, "Content-Type": "application/json"}
if not KEY.startswith("sb_"):  # eski JWT tipi service_role anahtarı için
    H["Authorization"] = "Bearer " + KEY

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # AI Studio'da güncel ücretsiz modele bak
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")
MIN_NOTIFY = int(os.environ.get("MIN_NOTIFY", "3"))  # bu önemin altındakiler bildirilmez, sadece kaydedilir


def sb_get(path, params=None):
    r = requests.get(f"{SB}/{path}", headers=H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def analyze(row):
    """Gemini ile önem (1-5), kısa özet ve tür çıkarır. Hata olursa None döner."""
    if not GEMINI_KEY:
        return None
    prompt = (
        "Bir KAP bildirimini bireysel yatırımcı için değerlendir. "
        'Sadece şu JSON\'u döndür: {"onem": 1-5 arası tam sayı, '
        '"ozet": "en fazla 2 cümle Türkçe özet", '
        '"tur": "bilanço|temettü|sermaye artırımı|ihale-sözleşme|yönetim|diğer"}\n'
        f"Şirket: {row['company_name']} ({row['ticker']})\n"
        f"Konu: {row['subject']}\n"
        f"Özet: {row['summary']}"
    )
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        time.sleep(4)  # ücretsiz katman dakika limiti için nefes payı
        return json.loads(text)
    except Exception as e:
        print("Gemini hatası:", e)
        return None


def telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True},
            timeout=30,
        )
    except Exception as e:
        print("Telegram hatası:", e)


def main():
    tickers = [w["ticker"] for w in sb_get("watchlist", {"active": "eq.true", "select": "ticker"})]
    today = dt.date.today()
    start = today - dt.timedelta(days=2)
    print("Takip edilen:", tickers)

    with Kap() as kap:
        for t in tickers:
            try:
                items = kap.fetch_disclosures(t, start, today)
            except EmptyResponseError:
                continue
            except KapError as e:
                print(f"{t}: KAP hatası (403/503 ise IP engeli olabilir): {e}")
                continue

            # İlk çalıştırmada eski bildirimleri sessizce kaydet, bildirim gönderme
            first_run = not sb_get("disclosures", {"ticker": f"eq.{t}", "select": "idx", "limit": "1"})
            rows = [
                {
                    "idx": d.index,
                    "ticker": t,
                    "published_at": d.publish_datetime.isoformat(),
                    "company_name": d.company_name,
                    "subject": d.subject,
                    "summary": d.summary,
                    "url": d.url,
                    "has_attachment": d.has_attachment,
                    "is_corrective": d.is_corrective,
                    "notified": first_run,
                }
                for d in items
            ]
            if not rows:
                continue

            # Zaten kayıtlı olanlar atlanır, sadece yeni satırlar geri döner
            r = requests.post(
                f"{SB}/disclosures?on_conflict=idx",
                headers={**H, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=rows,
                timeout=30,
            )
            r.raise_for_status()
            new = r.json()
            print(f"{t}: {len(new)} yeni bildirim")
            if first_run:
                continue

            for row in new:
                ai = analyze(row)
                patch = {"notified": True}
                if ai:
                    patch.update(
                        importance=ai.get("onem"),
                        ai_summary=ai.get("ozet"),
                        category=ai.get("tur"),
                    )
                requests.patch(
                    f"{SB}/disclosures?idx=eq.{row['idx']}", headers=H, json=patch, timeout=30
                ).raise_for_status()

                onem = patch.get("importance")
                if onem is None or onem >= MIN_NOTIFY:
                    body = patch.get("ai_summary") or row.get("summary") or ""
                    telegram(f"{row['ticker']} | {row['subject']}\n{body}\n{row['url']}")


if __name__ == "__main__":
    main()
