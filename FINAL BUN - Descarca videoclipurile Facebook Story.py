from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import requests
import re
import json
from urllib.parse import unquote, urlparse

def connect_to_existing_chrome():
    """Conectează la instanța Chrome deja deschisă cu remote debugging"""
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("✅ Conectat la Chrome cu succes!")
        return driver
    except Exception as e:
        print(f"❌ Eroare la conectare: {e}")
        return None

def get_current_profile_info(driver):
    """Extrage informații despre profilul curent din story"""
    try:
        profile_info = {
            'name': None,
            'profile_url': None,
            'timestamp': time.time()
        }

        # Salvează codul sursă pentru depanare
        try:
            with open("facebook_profile_check.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("💾 Codul sursă al paginii curente salvat în 'facebook_profile_check.html'")
        except:
            pass

        # Selector principal
        try:
            name_elements = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"))
            )
            if name_elements:
                profile_info['name'] = name_elements[0].text.strip()
                print(f"🔍 Nume profil detectat: {profile_info['name']}")
        except:
            print("⚠️ Selectorul principal CSS nu a găsit numele.")

        # Selector alternativ bazat pe structura HTML
        if not profile_info['name']:
            try:
                name_elements_alt = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[contains(@class, 'x9f619 x1ja2u2z x78zum5 x2lah0s x1n2onr6 x1nhvcw1')]//span[contains(@class, 'x1lliihq x6ikm8r x10wlt62 x1n2onr6 xlyipyv xuxw1ft')]")
                    )
                )
                if name_elements_alt:
                    profile_info['name'] = name_elements_alt[0].text.strip()
                    print(f"🔍 Nume profil detectat cu selector alternativ: {profile_info['name']}")
            except:
                print("⚠️ Selectorul alternativ XPath nu a găsit numele.")

        # Încearcă să găsească URL-ul profilului
        try:
            profile_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='facebook.com/']")
            for link in profile_links:
                href = link.get_attribute('href')
                if href and ('/stories/' not in href) and ('facebook.com/' in href):
                    profile_info['profile_url'] = href
                    break
        except:
            pass

        return profile_info

    except Exception as e:
        print(f"❌ Eroare la extragerea informațiilor profilului: {e}")
        return {'name': None, 'profile_url': None, 'timestamp': time.time()}

def is_same_profile(original_profile, current_profile):
    """Verifică dacă suntem încă pe același profil"""
    if not original_profile['name'] or not current_profile['name']:
        print("⚠️ Nume profil nedetectat. Nu pot verifica schimbarea profilului.")
        return False  # Oprim navigarea dacă nu putem verifica
    return original_profile['name'] == current_profile['name']

def extract_video_urls(driver):
    """Extrage URL-uri video din pagina curentă"""
    video_urls = []

    try:
        # 1. Elemente video directe
        video_elements = driver.find_elements(By.TAG_NAME, "video")
        for video in video_elements:
            try:
                video_url = video.get_attribute("src")
                if video_url and video_url not in video_urls:
                    video_urls.append(video_url)
                    print(f"✅ Video direct: {video_url[:80]}...")
            except:
                pass

        # 2. Analiză page source
        page_source = driver.page_source
        patterns = [
            r'src="(https://[^"]*\.mp4[^"]*)"',
            r'video_url":"([^"]+)"',
            r'hd_src":"([^"]+)"',
            r'sd_src":"([^"]+)"',
            r'contentUrl":"([^"]+)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, page_source)
            for match in matches:
                clean_url = unquote(match.replace('\\u0025', '%').replace('\\/', '/'))
                if clean_url not in video_urls and any(ext in clean_url for ext in ['.mp4', 'video']):
                    video_urls.append(clean_url)
                    print(f"✅ URL din source: {clean_url[:80]}...")

        # 3. JavaScript extraction
        try:
            js_script = """
            var videos = document.querySelectorAll('video');
            var urls = [];
            for (var i = 0; i < videos.length; i++) {
                if (videos[i].src) urls.push(videos[i].src);
            }
            return urls;
            """
            js_urls = driver.execute_script(js_script)
            for url in js_urls:
                if url and url not in video_urls:
                    video_urls.append(url)
                    print(f"✅ URL din JS: {url[:80]}...")
        except:
            pass

        # 4. Verifică iframe-urile
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    iframe_videos = driver.find_elements(By.TAG_NAME, "video")
                    for video in iframe_videos:
                        try:
                            video_url = video.get_attribute("src")
                            if video_url and video_url not in video_urls:
                                video_urls.append(video_url)
                                print(f"✅ Video din iframe: {video_url[:80]}...")
                        except:
                            pass
                    driver.switch_to.default_content()
                except:
                    driver.switch_to.default_content()
                    continue
        except:
            pass

    except Exception as e:
        print(f"❌ Eroare la extragerea video-urilor: {e}")

    return list(set(video_urls))

def download_video(url, folder_path, index):
    """Descarcă un videoclip de la URL-ul dat"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.facebook.com/',
            'Accept': 'video/*,*/*;q=0.8'
        }

        print(f"   ⬇️ Descarc videoclipul {index}...")

        response = requests.get(url, headers=headers, stream=True, timeout=30)

        if response.status_code == 200:
            filename = f"story_video_{index}.mp4"
            filepath = os.path.join(folder_path, filename)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"   ✅ Videoclip {index} descărcat: {filename} ({os.path.getsize(filepath)} bytes)")
                return True

        print(f"   ❌ Eroare la descărcarea videoclipului {index}")
        return False

    except Exception as e:
        print(f"   ❌ Eroare la descărcare: {e}")
        return False

def navigate_to_next_story(driver):
    """Încearcă să navigheze la următorul story"""
    try:
        next_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//svg[contains(@class, 'x14rh7hd') and contains(@class, 'x1lliihq')]//path[contains(@d, 'M9.209')]"))
        )
        ActionChains(driver).move_to_element(next_button).click().perform()
        print("✅ Navigat cu butonul 'Next'")
        time.sleep(2)
        return True
    except:
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            body.send_keys(Keys.ARROW_RIGHT)
            print("✅ Navigat cu săgeata dreapta")
            time.sleep(2)
            return True
        except:
            print("❌ Nu s-a putut naviga mai departe")
            return False

def save_profile_info(profile_info, filename="profiles_data.json"):
    """Salvează informațiile profilului în fișier JSON"""
    try:
        data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

        data.append(profile_info)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 Informații profil salvate în {filename}")
    except Exception as e:
        print(f"❌ Eroare la salvarea datelor profilului: {e}")

def main():
    story_url = "https://www.facebook.com/stories/2285180934855389/UzpfSVNDOjc4NjM2MjEyNzE5MjgwMA==/?bucket_count=9&source=story_tray"

    print("=" * 70)
    print("🎬 FACEBOOK STORY DOWNLOADER")
    print("📱 Cu detectare automată a schimbării profilului")
    print("=" * 70)

    # Conectează la Chrome
    driver = connect_to_existing_chrome()
    if not driver:
        return

    try:
        # Accesează URL-ul story-ului
        print(f"🌐 Accesez: {story_url}")
        driver.get(story_url)
        time.sleep(5)

        # Click pe „Click to view story”
        try:
            story_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'x1i10hfl') and @role='button']//span[contains(text(), 'Click to view story')]"))
            )
            ActionChains(driver).move_to_element(story_button).click().perform()
            print("✅ Am dat click pe 'Click to view story'...")
            time.sleep(3)
        except Exception as e:
            print(f"❌ Eroare la deschiderea story-ului: {e}")

        # Obține informațiile profilului inițial
        initial_profile = get_current_profile_info(driver)
        if not initial_profile['name']:
            print("❌ Nu s-a detectat numele profilului inițial. Verifică 'facebook_profile_check.html' pentru depanare.")
            return
        print(f"👤 Profil inițial detectat: {initial_profile['name']}")
        save_profile_info(initial_profile)

        # Parcurge story-urile
        all_video_urls = []
        max_frames = 10

        for frame in range(max_frames):
            print(f"\n📹 CADRU {frame + 1}/{max_frames}")
            print("=" * 50)

            # Verifică dacă suntem încă pe același profil
            current_profile = get_current_profile_info(driver)
            if not is_same_profile(initial_profile, current_profile):
                print(f"🚨 S-a detectat schimbare de profil!")
                print(f"   De la: {initial_profile['name']}")
                print(f"   La: {current_profile['name'] or 'Nedetectat'}")
                print("⏹️ Oprire pentru a evita descărcarea de la alte profile")
                break

            # Extrage URL-uri video
            frame_urls = extract_video_urls(driver)

            # Adaugă URL-uri noi
            new_urls = [url for url in frame_urls if url not in all_video_urls]
            all_video_urls.extend(new_urls)

            for url in new_urls:
                print(f"🎯 Video găsit: {url[:100]}...")

            if not new_urls:
                print("ℹ️ Nu s-au găsit video-uri noi în acest cadru")

            # Salvează screenshot și page source pentru referință
            try:
                driver.save_screenshot(f"story_frame_{frame + 1}.png")
                print(f"📸 Screenshot salvat: story_frame_{frame + 1}.png")
                with open(f"facebook_story_source_frame_{frame + 1}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"💾 Codul sursă al cadrului {frame + 1} salvat în 'facebook_story_source_frame_{frame + 1}.html'")
            except:
                pass

            # Navighează la următorul cadru (dacă nu suntem la ultimul)
            if frame < max_frames - 1:
                if not navigate_to_next_story(driver):
                    print("⏹️ Nu se poate naviga mai departe")
                    break
            else:
                print("⏹️ Am ajuns la limita maximă de cadre")

        # Descarcă video-urile găsite
        if all_video_urls:
            print(f"\n🎉 TOTAL: {len(all_video_urls)} VIDEO-URI GĂSITE!")

            download_folder = "facebook_story_videos"
            os.makedirs(download_folder, exist_ok=True)

            success_count = 0
            print(f"\n📥 DESCĂRCARE ÎN '{download_folder}'...")

            for i, url in enumerate(all_video_urls, 1):
                print(f"\n🔗 VIDEO {i}/{len(all_video_urls)}")
                if download_video(url, download_folder, i):
                    success_count += 1
                time.sleep(1)

            print(f"\n🎊 REZULTAT: {success_count}/{len(all_video_urls)} VIDEO-URI DESCĂRCATE!")
        else:
            print("\n❌ NU S-AU GĂSIT VIDEO-URI")
            print("\n💡 Sfaturi:")
            print("1. Verifică screenshot-urile salvate")
            print("2. Folosește Developer Tools (F12) → Network tab")
            print("3. Filtrează după 'mp4' pentru a găsi manual URL-uri")

    except Exception as e:
        print(f"❌ EROARE: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n✅ Browserul rămâne deschis")
        print("✨ Proces terminat!")

if __name__ == "__main__":
    main()