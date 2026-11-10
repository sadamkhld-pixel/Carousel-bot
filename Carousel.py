import time
import requests
import os
import sqlite3
import re
import json

# ====== KONFIGURASI ======
BOT_TOKEN = "8939814471:AAHbg3pwnwSggnvR30AGneIL0BqlsCZkifQ" 
CHAT_ID   = "8242555405"
URL_TARGET = "https://id.carousell.com/categories/mobile-phones-338/?sort_by=time_created%2Cdescending"
MAX_ITEMS  = 10
DB_FILE = "riwayat_iklan.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ====== SETUP DATABASE ======
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS iklan (id_iklan TEXT PRIMARY KEY)''')
    conn.commit()
    return conn

def is_sent(conn, id_iklan):
    if not id_iklan: return False
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM iklan WHERE id_iklan = ?", (id_iklan,))
    return cursor.fetchone() is not None

def save_sent(conn, id_iklan):
    if not id_iklan: return
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO iklan (id_iklan) VALUES (?)", (id_iklan,))
    conn.commit()

# ====== SCRAPER SUPER CEPAT (TANPA SELENIUM) ======
def scrape_carousell():
    listings = []
    try:
        # Menggunakan requests (jauh lebih cepat dari Selenium)
        response = requests.get(URL_TARGET, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"❌ Gagal akses web: {response.status_code}")
            return []

        # Ekstrak JSON data dari script tersembunyi di dalam HTML Carousell
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            if script.string and '__INITIAL_STATE__' in script.string:
                # Ambil data JSON internal Carousell
                json_str = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script.string)
                if json_str:
                    data = json.loads(json_str.group(1))
                    # Navigasi ke dalam JSON untuk mencari list produk
                    try:
                        products = data['listingStore']['listingData']['items']
                        for p in products:
                            id_iklan = str(p.get('listingId'))
                            title = p.get('title', 'Tanpa judul')
                            price = p.get('price', 0)
                            
                            # Ambil URL
                            base_url = "https://id.carousell.com/p/"
                            slug = p.get('slug', '')
                            url = f"{base_url}{slug}-{id_iklan}/"
                            
                            listings.append({
                                "id": id_iklan, 
                                "title": title, 
                                "price": f"Rp{price:,}".replace(',', '.'), 
                                "url": url
                            })
                            
                            if len(listings) >= MAX_ITEMS:
                                break
                        return listings
                    except KeyError:
                        continue
    except Exception as e:
        print(f"Error Scraping: {e}")
    
    return listings

# ====== KIRIM TELEGRAM ======
def send_single_listing(item):
    title = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    price = item["price"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    msg = f"📱 <b>{title}</b>\n"
    msg += f"💰 {price}\n"
    msg += f"🔗 <a href='{item['url']}'>Lihat Listing</a>"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except:
        return False

# ====== MAIN (LOOP NON-STOP) ======
def main():
    conn = init_db()
    print("🚀 Bot Mode Kilat Aktif (Target: < 5 Detik).")
    
    while True:
        try:
            raw_listings = scrape_carousell()
            
            if raw_listings:
                new_listings = [item for item in raw_listings if not is_sent(conn, item["id"])]
                
                if new_listings:
                    print(f"✨ Ditemukan {len(new_listings)} iklan baru!")
                    # Urutkan dari terlama ke terbaru
                    for item in reversed(new_listings): 
                        if send_single_listing(item):
                            save_sent(conn, item["id"]) 
                            time.sleep(1) # Jeda 1 detik antar pesan Telegram
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Tidak ada iklan baru.")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Gagal ambil data (Mungkin diblokir Captcha).")
                
        except Exception as e:
            print(f"⚠️ Error: {e}")
            
        # Jeda 20 detik (Batas aman tercepat agar IP GitHub tidak diblokir)
        time.sleep(20) 
        
    conn.close()

if __name__ == "__main__":
    main()
