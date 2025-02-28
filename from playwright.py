import time
import re
import random
import csv
import requests
import os
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright
from datetime import datetime

class ProductParser:
    def __init__(self):
        self.output_file = f"products_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        self._init_csv()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        self.total_items = 0
        self.processed = 0
        self.start_time = None

    def _init_csv(self):
        """Инициализация CSV файла"""
        with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Название', 'Цена', 'Описание'])

    def _print_progress(self, index, title, exec_time):
        """Вывод информации о прогрессе"""
        print(f"\n[{index}/{self.total_items}] {title}")
        print(f"⏱ Время обработки: {exec_time:.1f} сек")
        print("✅ Успешно сохранено")

    def _random_delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(3, 7)
        print(f"⏳ Задержка: {delay:.1f} сек")
        time.sleep(delay)

    def _setup_browser(self, playwright):
        """Настройка браузера"""
        return playwright.chromium.launch(
            headless=True,
            args=[
                f'--user-agent={random.choice(self.user_agents)}',
                '--disable-blink-features=AutomationControlled'
            ],
            timeout=120000
        )

    def _get_element_text(self, page, selector, default="-"):
        """Универсальный метод получения текста"""
        try:
            element = page.query_selector(selector)
            return element.text_content().strip() if element else default
        except:
            return default

    def _get_price(self, page):
        """Извлечение цены с приоритетом скидки"""
        try:
            sale_price = self._get_element_text(page, '.price.sale, span.price-span.saled', '')
            if sale_price:
                return sale_price.replace('€', '').strip()
            
            regular_price = self._get_element_text(page, '.price.money, span.price-span.money, [itemprop="price"]', '')
            return regular_price.replace('€', '').strip() or "-"
        except:
            return "-"

    def _get_description(self, page):
        """Извлечение описания"""
        desc = self._get_element_text(
            page, 
            'div.product-data--description, .product-description, [itemprop="description"]',
            '-'
        )
        return desc[:500] + '...' if len(desc) > 500 else desc
    
    def _get_title(self, page):
        """Извлечение заголовка"""
        desc = self._get_element_text(
            page, 
            'div.product-data--title,[itemprop="title"]',
            '-'
        )
        return desc[:500] + '...' if len(desc) > 500 else desc

    def parse_product(self, page, url, index):
        """Парсинг одного товара"""
        self.page = page 
        start_time = time.time()
        result = {'Название': '-', 'Цена': '-', 'Описание': '-'}
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=90000)
            
            # Парсинг данных
            result['Название'] = self._get_element_text(page, 'h1.product-data--title, h1.product-name')
            result['Цена'] = self._get_price(page)
            result['Описание'] = self._get_description(page)
            
            # Сохранение изображения
            img_element = page.query_selector('img.single-product--image-img, img[itemprop="image"]')
            if img_element:
                img_url = img_element.get_attribute('src')
                self._save_image(img_url, url, page)

            # Запись в CSV
            with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([result['Название'], result['Цена'], result['Описание']])

            # Вывод прогресса
            exec_time = time.time() - start_time
            self._print_progress(index, result['Название'], exec_time)
            self.processed += 1

        except Exception as e:
            print(f"\n⚠️ Ошибка: {str(e)[:100]}...")
            with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["-", "-", "-"])
    
    def _save_image(self, url, base_url, page):
        "Сохранение изображения под названием товара"
        try:
            if not url:
                return

            # Получаем название товара из текущего контекста
            product_name = "-"
            try:
                product_name = self._get_element_text(self.page, 'h1.product-data--title, h1.product-name')
                product_name = re.sub(r'[\\/*?:"<>|]', '', product_name).strip().replace(' ', '_')[:50]
            except:
                pass

            # Скачиваем и сохраняем изображение
            img_data = requests.get(urljoin(base_url, url, page)).content
            os.makedirs('product_images', exist_ok=True)
            with open(f'product_images/{product_name}.jpg', 'wb') as img_file:
                img_file.write(img_data)
        except Exception as e:
            print(f"⚠️ Ошибка при сохранении изображения: {str(e)[:100]}...")
    
    def run(self, urls):
        """Запуск процесса парсинга"""
        self.total_items = len(urls)
        self.start_time = time.time()
        print(f"🚀 Начало парсинга {self.total_items} товаров...\n")

        with sync_playwright() as p:
            browser = self._setup_browser(p)
            context = browser.new_context()
            page = context.new_page()

            for index, url in enumerate(urls, 1):
                self.parse_product(page, url, index)
                if index < self.total_items:
                    self._random_delay()
                
                if index % 10 == 0:
                    context.close()
                    context = browser.new_context()
                    page = context.new_page()

            context.close()
            browser.close()

        total_time = time.time() - self.start_time
        print(f"\n{'='*50}")
        print(f"✅ Парсинг завершен!")
        print(f"⏱ Общее время: {total_time//60:.0f} мин {total_time%60:.0f} сек")
        print(f"📊 Успешно обработано: {self.processed}/{self.total_items}")
        print(f"💾 Результаты сохранены в: {self.output_file}")
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
    
    parser = ProductParser()
    parser.run(product_urls)