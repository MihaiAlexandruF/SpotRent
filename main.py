import csv
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import random
import sys
from urllib.parse import urljoin

# --- LOGGING ---
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

log_file = open("log.txt", "a", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_file)
sys.stderr = Tee(sys.stderr, log_file)
# --- END LOGGING ---

options = Options()
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
# NU adăuga --headless, ca să fie vizibilă fereastra Chrome

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://www.olx.ro/imobiliare/apartamente-garsoniere-de-inchiriat/bucuresti/?currency=EUR"

with open("OLX_chirii_descriere.csv", "w", newline="", encoding="utf-8-sig") as file:
    writer = csv.writer(file)
    writer.writerow(["Titlu", "Descriere", "Telefon", "Tip", "Link"])
    file.flush()

    current_url = url
    processed_links = set()
    page_count = 0
    while True:
        driver.get(current_url)
        page_count += 1
        print(f"\n=== Pagina OLX {page_count} === {current_url}")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.css-1tqlkj0'))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        ads = soup.select("a.css-1tqlkj0")
        print(f"Găsite {len(ads)} anunțuri pe această pagină.")

        for idx, ad in enumerate(ads):
            try:
                # Sari peste anunțurile promovate (au titlu gol sau clasa specială)
                title_tag = ad.select_one("h4.css-1g61gc2")
                if not title_tag:
                    print(f"[SKIP] Anunț fără titlu (probabil PROMOVAT sau banner).")
                    continue
                title = title_tag.text.strip()
                if not title or title.upper() == "PROMOVAT":
                    print(f"[SKIP] Anunț PROMOVAT: '{title}'")
                    continue
                # Sari peste duplicate (link deja procesat)
                link = ad.get("href", "")
                if not link.startswith("http"):
                    continue
                if link in processed_links:
                    print(f"[SKIP] Anunț duplicat: {link}")
                    continue
                processed_links.add(link)

                print(f"\n---\nAccesez anunțul: {title}\n{link}")
                driver.get(link)
                # Scroll random pe pagină
                scroll_y = random.randint(40, 400)
                driver.execute_script(f"window.scrollTo(0, {scroll_y});")
                time.sleep(random.uniform(0.5, 1.2))

                # Click „Mai mult” dacă există
                try:
                    btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[span[contains(text(),'Mai mult') or contains(text(),'Vezi mai mult')]]"))
                    )
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(random.uniform(0.5, 1.2))
                    print("Am apăsat pe 'Mai mult' pentru descriere.")
                except Exception as e:
                    print("Nu am găsit butonul 'Mai mult' sau nu am putut apăsa.")

                # Reparsăm pagina
                page = BeautifulSoup(driver.page_source, "html.parser")
                desc_div = page.select_one("div[data-cy='adPageAdDescription']")
                if desc_div:
                    description = desc_div.get_text(separator=" ", strip=True)
                else:
                    description = "Fără descriere"
                print(f"Descriere extrasă: {description[:200]}")

                # --- DETECTARE TIP ANUNȚ ---
                tip = "Agentie"  # default
                if page.find(string=lambda t: t and "Anunț proprietar" in t):
                    tip = "Proprietar"
                elif page.select_one("a[href*='/companii/agentii/']"):
                    tip = "Agentie"
                print(f"Tip anunț: {tip}")
                # --- END DETECTARE ---

                # Click pe butonul de telefon și extrage numărul
                try:
                    phone_btn = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, 'button[data-cy="phone-number.show-full-number-button"]'))
                    )
                    driver.execute_script("arguments[0].style.background='yellow';", phone_btn)
                    print("Butonul de telefon a fost găsit și colorat în galben.")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", phone_btn)
                    time.sleep(random.uniform(0.5, 1.2))
                    driver.execute_script("arguments[0].click();", phone_btn)
                    print("Am dat click pe butonul de telefon (cu JS).")
                    phone_link = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-cy="phone-number.number-button"]'))
                    )
                    phone_number = phone_link.get_attribute('href')
                    if phone_number and phone_number.startswith('tel:'):
                        phone_number = phone_number.replace('tel:', '').replace(' ', '').strip()
                    else:
                        phone_number = None
                    if not phone_number:
                        try:
                            span = phone_link.find_element(By.CSS_SELECTOR, 'span.n-button-text-wrapper')
                            phone_number = span.text.strip().replace(' ', '')
                        except Exception:
                            phone_number = "N/A"
                    print(f"Număr de telefon extras: {phone_number}")
                except Exception as e:
                    print("Nu am putut extrage numărul de telefon.", e)
                    phone_number = "N/A"

                writer.writerow([title, description, phone_number, tip, link])
                file.flush()
                print(f"✔️ Salvat: {title}")

                # Delay random între anunțuri (mai scurt)
                delay = random.uniform(1.5, 4)
                print(f"Aștept {delay:.1f} secunde înainte de următorul anunț...")
                time.sleep(delay)
            except Exception as e:
                print(f"❌ Eroare: {e}")
                continue

        # PAGINARE: caută linkul către pagina următoare
        soup = BeautifulSoup(driver.page_source, "html.parser")
        next_btn = soup.select_one('a[data-testid="pagination-forward"]')
        if next_btn and next_btn.get("href"):
            next_url = urljoin(url, next_btn["href"])
            print(f"Paginez către: {next_url}")
            current_url = next_url
            # Pauză mai lungă la fiecare 5 pagini (simulează comportament uman)
            if page_count % 5 == 0:
                print("[PAUZĂ] Mică pauză de om normal (10-20s)...")
                time.sleep(random.uniform(10, 20))
            else:
                time.sleep(random.uniform(2, 4))
        else:
            print("Nu mai există pagină următoare. Oprire scraping.")
            break

driver.quit()
log_file.close()
print("✅ Finalizat! CSV-ul conține titlu, descriere, telefon și link.")
