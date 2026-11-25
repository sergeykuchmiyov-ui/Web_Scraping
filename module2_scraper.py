import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
 
import pandas as pd
from bs4 import BeautifulSoup, Tag
 
BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "module2_mock_catalog.html"
CSV_PATH = BASE_DIR / "catalog_scraped.csv"
 
BASE_URL = "http://localhost"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
 
COLUMNS = ["product_id", "title", "author", "price_uah",
           "stock_status", "relative_url"]
 
 
def check_robots_permission(
    robots_url: str, target_url: str, agent: str = "*"
) -> bool:
    """Перевіряє, чи дозволяє robots.txt сканувати target_url.
 
    Для локальних або офлайн-файлів (robots.txt недоступний) будь-який
    виняток перехоплюється, і функція безпечно повертає True.
 
    Args:
        robots_url: адреса файлу robots.txt.
        target_url: адреса сторінки, яку планується сканувати.
        agent: назва User-Agent (за замовчуванням '*').
 
    Returns:
        True, якщо сканування дозволене або перевірку неможливо виконати.
    """
    try:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.read()
        return parser.can_fetch(agent, target_url)
    except Exception as error:  # noqa: BLE001 - fallback за умовою ТЗ
        print(f"robots.txt недоступний ({type(error).__name__}), "
              "використано fallback: дозволено")
        return True
 
 
def parse_price(raw_text: str) -> float:
    """Перетворює текстову ціну на float.
 
    Args:
        raw_text: текст ціни, наприклад '1 200,50 грн' або '850.00'.
 
    Returns:
        Числове значення ціни; 0.0, якщо число не знайдено.
    """
    cleaned = raw_text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else 0.0
 
 
def extract_text(card: Tag, selector: str) -> str:
    """Повертає очищений текст першого елемента за CSS-селектором.
 
    Args:
        card: HTML-контейнер картки товару.
        selector: CSS-селектор шуканого елемента.
 
    Returns:
        Текст без зайвих пробілів або порожній рядок, якщо елемента немає.
    """
    element = card.select_one(selector)
    return element.get_text(strip=True) if element else ""
 
 
def parse_product(card: Tag) -> dict:
    """Вилучає 6 обов'язкових полів з однієї картки товару.
 
    Args:
        card: елемент з класом .product-card.
 
    Returns:
        Словник із полями product_id, title, author, price_uah,
        stock_status, relative_url.
    """
    link = card.select_one("a.product-link")
    return {
        "product_id": str(card.get("data-id", "")).strip(),
        "title": extract_text(card, ".product-title"),
        "author": extract_text(card, ".product-author"),
        "price_uah": parse_price(extract_text(card, ".price-value")),
        "stock_status": extract_text(card, ".stock-status"),
        "relative_url": str(link.get("href", "")).strip() if link else "",
    }
 
 
def collect_pagination(
    soup: BeautifulSoup, visited_urls: set[str], base_url: str = BASE_URL
) -> list[str]:
    """Знаходить посилання пагінації та додає нові до множини visited_urls.
 
    Повторні адреси пропускаються, що захищає від зациклення (Spider Trap).
 
    Args:
        soup: розібраний HTML-документ.
        visited_urls: множина вже виявлених адрес (змінюється на місці).
        base_url: базова адреса для перетворення відносних посилань.
 
    Returns:
        Список нових (унікальних) абсолютних адрес пагінації.
    """
    new_links: list[str] = []
    for anchor in soup.select(".pagination a.page-link"):
        href = str(anchor.get("href", "")).strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if full_url in visited_urls:
            print(f"Пропущено повторне посилання: {full_url}")
            continue
        visited_urls.add(full_url)
        new_links.append(full_url)
    return new_links
 
 
def main() -> None:
    """Виконує повний сценарій: robots -> парсинг -> пагінація -> CSV."""
    if not check_robots_permission(ROBOTS_URL, BASE_URL + "/catalog"):
        print("Сканування заборонене файлом robots.txt")
        return
 
    html = HTML_PATH.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
 
    cards = soup.select(".product-card")
    products = [parse_product(card) for card in cards]
 
    visited_urls: set[str] = set()
    pagination_links = collect_pagination(soup, visited_urls)
    # повторний прохід демонструє захист від циклічного обходу
    collect_pagination(soup, visited_urls)
 
    df = pd.DataFrame(products, columns=COLUMNS)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
 
    print("\n=== Звіт про збір даних ===")
    print(f"Зібрано позицій: {len(products)}")
    print(f"Виявлено посилань пагінації: {len(pagination_links)}")
    for link in pagination_links:
        print(f"  - {link}")
    print(f"Унікальних адрес у visited_urls: {len(visited_urls)}")
    print(f"Файл збережено: {CSV_PATH.name}")
    print("\n" + df.to_string(index=False))
 
 
if __name__ == "__main__":
    main()