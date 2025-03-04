import time
import re
import random
import csv
import requests
import os
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright
from datetime import datetime

# Глобальные переменные
output_file = f"products_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]
total_items = 0
processed = 0
start_time = None

def init_csv():
    """Инициализация CSV файла"""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Название', 'Цена', 'Описание'])

def print_progress(index, title, exec_time):
    """Вывод информации о прогрессе"""
    print(f"\n[{index}/{total_items}] {title}")
    print(f"⏱ Время обработки: {exec_time:.1f} сек")
    print("✅ Успешно сохранено")

def random_delay():
    """Случайная задержка между запросами"""
    delay = random.uniform(3, 7)
    print(f"⏳ Задержка: {delay:.1f} сек")
    time.sleep(delay)

def setup_browser(playwright):
    """Настройка браузера"""
    return playwright.chromium.launch(
        headless=True,
        args=[
            f'--user-agent={random.choice(user_agents)}',
            '--disable-blink-features=AutomationControlled'
        ],
        timeout=120000
    )

def get_element_text(page, selector, default="-"):
    """Универсальный метод получения текста"""
    try:
        element = page.query_selector(selector)
        return element.text_content().strip() if element else default
    except:
        return default

def get_price(page):
    """Извлечение цены с приоритетом скидки"""
    try:
        sale_price = get_element_text(page, '.price.sale, span.price-span.saled', '')
        if sale_price:
            return sale_price.replace('€', '').strip()
        
        regular_price = get_element_text(page, '.price.money, span.price-span.money, [itemprop="price"]', '')
        return regular_price.replace('€', '').strip() or "-"
    except:
        return "-"

def get_description(page):
    """Извлечение описания"""
    desc = get_element_text(
        page, 
        'div.product-data--description, .product-description, [itemprop="description"]',
        '-'
    )
    return desc[:500] + '...' if len(desc) > 500 else desc

def get_title(page):
    """Извлечение заголовка"""
    desc = get_element_text(
        page, 
        'div.product-data--title,[itemprop="title"]',
        '-'
    )
    return desc[:500] + '...' if len(desc) > 500 else desc

def save_image(img_url, base_url, page):
    """Сохранение изображения под названием товара"""
    try:
        if not img_url:
            return

        # Получаем название товара
        product_name = get_element_text(page, 'h1.product-data--title, h1.product-name')
        product_name = re.sub(r'[\\/*?:"<>|]', '', product_name).strip().replace(' ', '_')[:50]

        # Формируем абсолютный URL
        full_img_url = urljoin(base_url, img_url)

        # Скачиваем и сохраняем
        os.makedirs('product_images', exist_ok=True)
        response = requests.get(full_img_url, stream=True)
        if response.status_code == 200:
            with open(f'product_images/{product_name}.jpg', 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения изображения: {str(e)[:100]}...")

def parse_product(page, url, index):
    """Парсинг одного товара"""
    global processed
    start_time = time.time()
    result = {'Название': '-', 'Цена': '-', 'Описание': '-'}
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=90000)
        
        # Парсинг данных
        result['Название'] = get_element_text(page, 'h1.product-data--title, h1.product-name')
        result['Цена'] = get_price(page)
        result['Описание'] = get_description(page)
        
        # Сохранение изображения
        img_element = page.query_selector('img.single-product--image-img, img[itemprop="image"]')
        if img_element:
            img_url = img_element.get_attribute('src')
            save_image(img_url, url, page)

        # Запись в CSV
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([result['Название'], result['Цена'], result['Описание']])

        # Вывод прогресса
        exec_time = time.time() - start_time
        print_progress(index, result['Название'], exec_time)
        processed += 1

    except Exception as e:
        print(f"\n⚠️ Ошибка: {str(e)[:100]}...")
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["-", "-", "-"])

def run_parser(urls):
    """Запуск процесса парсинга"""
    global total_items, start_time
    total_items = len(urls)
    start_time = time.time()
    print(f"🚀 Начало парсинга {total_items} товаров...\n")

    with sync_playwright() as p:
        browser = setup_browser(p)
        context = browser.new_context()
        page = context.new_page()

        for index, url in enumerate(urls, 1):
            parse_product(page, url, index)
            if index < total_items:
                random_delay()
            
            if index % 10 == 0:
                context.close()
                context = browser.new_context()
                page = context.new_page()

        context.close()
        browser.close()

    total_time = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"✅ Парсинг завершен!")
    print(f"⏱ Общее время: {total_time//60:.0f} мин {total_time%60:.0f} сек")
    print(f"📊 Успешно обработано: {processed}/{total_items}")
    print(f"💾 Результаты сохранены в: {output_file}")
    print(f"🖼 Изображения в папке: product_images")
    print(f"{'='*50}")

if __name__ == "__main__":
    product_urls = [
        "https://nomennescio.fi/products/405-short-blouse",
        "https://nomennescio.fi/products/303a-basic-blazer",
        "https://nomennescio.fi/products/304a-minimal-blazer",
        "https://nomennescio.fi/products/206a-loose-trousers",
        "https://nomennescio.fi/products/120-worker-jacket",
        "https://nomennescio.fi/products/715-merino-pants",
        "https://nomennescio.fi/products/gift-card",
        "https://nomennescio.fi/products/518-woollen-hoodie",
        "https://nomennescio.fi/products/154b-loose-parka-coat",
        "https://nomennescio.fi/products/311-light-field-jacket",
        "https://nomennescio.fi/products/401-basic-jersey-ecovero",
        "https://nomennescio.fi/products/407-standard-t-shirt",
        "https://nomennescio.fi/products/416-boxy-shirt-ecovero",
        "https://nomennescio.fi/products/736-sweat-pants",
        "https://nomennescio.fi/products/227-woollen-pants",
        "https://nomennescio.fi/products/739-zipper-sweat-hoodie",
        "https://nomennescio.fi/products/448-woollen-jersey",
        "https://nomennescio.fi/products/520-long-woollen-hoodie",
        "https://nomennescio.fi/products/312-long-worker-jacket",
        "https://nomennescio.fi/products/163-woollen-robe-jacket",
        "https://nomennescio.fi/products/117h-long-zipper-jacket",
        "https://nomennescio.fi/products/152-belted-woollen-coat-pre-order",
        "https://nomennescio.fi/products/161-basic-woollen-coat",
        "https://nomennescio.fi/products/162-raglan-woollen-jacket-pre-order",
        "https://nomennescio.fi/products/242-wide-woollen-pants",
        "https://nomennescio.fi/products/237-loose-pants",
        "https://nomennescio.fi/products/239-slim-pants-kopio",
        "https://nomennescio.fi/products/701-sweat-shirt",
        "https://nomennescio.fi/products/110d-robe-coat",
        "https://nomennescio.fi/products/160-long-woollen-coat",
        "https://nomennescio.fi/products/408-basic-t-shirt",
        "https://nomennescio.fi/products/241-pocket-pants",
        "https://nomennescio.fi/products/260-slim-jeans",
        "https://nomennescio.fi/products/261-loose-jeans",
        "https://nomennescio.fi/products/262-basic-jeans",
        "https://nomennescio.fi/products/263-wide-jeans",
        "https://nomennescio.fi/products/320-denim-jacket",
        "https://nomennescio.fi/products/321-raglan-denim-jacket",
        "https://nomennescio.fi/products/322-basic-denim-blazer",
        "https://nomennescio.fi/products/323-basic-denim-jacket",
        "https://nomennescio.fi/products/614-light-merino-beanie"
    ]
    
    init_csv()
    run_parser(product_urls)