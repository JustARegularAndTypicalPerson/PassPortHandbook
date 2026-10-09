from typing import Any, Literal, Tuple
from flask import Response, abort, jsonify
from werkzeug.exceptions import HTTPException # Import HTTPException
from playwright.sync_api import Page, Locator, sync_playwright, BrowserContext
import regex # Используем модуль regex вместо re
from datetime import datetime
import os
import atexit
import logging

# Global Playwright objects
_playwright_instance = None
_browser_context: BrowserContext | None = None

# Define a directory for persistent context.
# This will be <project_root>/organizations_files/playwright_yandex_context/
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_persistent_context_dir = os.path.abspath(
    os.path.join(_project_root, "organizations_files")
)

# Setup logging
logger = logging.getLogger(__name__)
# Configure logging in your main application setup, e.g.:
# import logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class CaptchaRequired(Exception):
    """Custom exception to indicate a CAPTCHA challenge."""
    def __init__(self, captcha_url: str, message: str = "CAPTCHA challenge encountered. Please solve it at the provided URL and retry the request."):
        self.captcha_url = captcha_url
        self.message = message
        super().__init__(self.message)

def _close_playwright():
    """Closes the Playwright browser context and instance if they exist."""
    global _playwright_instance, _browser_context
    
    if _browser_context:
        try:
            _browser_context.close()
            logger.info("Playwright browser context closed.")
        except Exception as e:
            logger.warning(f"Error or already closed - closing browser context: {e}")
        finally:
            _browser_context = None # Critical to set to None
    
    if _playwright_instance:
        try:
            _playwright_instance.stop()
            logger.info("Playwright instance stopped.")
        except Exception as e:
            logger.error(f"Error stopping Playwright instance: {e}")
        finally:
            _playwright_instance = None # Critical to set to None

atexit.register(_close_playwright)

def _get_or_create_browser_context() -> BrowserContext:
    """
    Initializes and returns a persistent Playwright browser context.
    If the context exists and is valid, it's reused. Otherwise, a new one is created.
    """
    global _playwright_instance, _browser_context

    if _browser_context:
        try:
            if _browser_context.browser and _browser_context.browser.is_connected():
                logger.debug("Reusing existing Playwright browser context.")
                return _browser_context
            else:
                logger.warning("Existing browser context's browser is disconnected or missing. Re-initializing.")
                _close_playwright() 
        except Exception as e: 
            logger.warning(f"Error checking existing browser context ({e}). Re-initializing.")
            _close_playwright()

    logger.info("Initializing new Playwright browser context...")
    # Ensure _playwright_instance is initialized if it's None
    if _playwright_instance is None:
        logger.info("Playwright instance is None, attempting to start a new one.")
        try:
            _playwright_instance = sync_playwright().start()
            if _playwright_instance is None:
                # This case implies sync_playwright().start() returned None without raising an exception.
                # This is highly unexpected for Playwright's API.
                critical_msg = "Playwright initialization failed: sync_playwright().start() returned None."
                logger.critical(critical_msg)
                raise RuntimeError(critical_msg)
        except Exception as e:
            # This catches exceptions from start() or our RuntimeError if start() returned None.
            logger.error(f"Failed to start Playwright manager: {e}")
            _playwright_instance = None # Ensure it's None if start failed
            raise # Re-raise the exception to be caught by the caller

    # Safeguard: After attempting initialization, _playwright_instance must not be None.
    if _playwright_instance is None:
        # This should ideally be caught by the block above.
        # If reached, it indicates a severe logic error or an unhandled state.
        final_check_error_msg = "Critical error: Playwright instance is None after initialization attempt and before launching context."
        logger.critical(final_check_error_msg)
        raise RuntimeError(final_check_error_msg)

    if not os.path.exists(_persistent_context_dir):
        try:
            os.makedirs(_persistent_context_dir)
            logger.info(f"Created persistent context directory: {_persistent_context_dir}")
        except OSError as e:
            logger.error(f"Failed to create persistent context directory '{_persistent_context_dir}': {e}") # Log and raise
            raise # Re-raise to indicate failure
    
    try:
        _browser_context = _playwright_instance.chromium.launch_persistent_context(
            user_data_dir=_persistent_context_dir, headless=True
        )
        logger.info(f"Playwright persistent browser context initialized from: {_persistent_context_dir}")
    except Exception as e:
        # This is where the original 'NoneType' object has no attribute 'chromium' would be caught if _playwright_instance was None
        logger.error(f"Failed to launch persistent context. Playwright instance: {_playwright_instance}. Error: {e}")
        _close_playwright() # Attempt to clean up
        raise # Re-raise the exception
    
    if not _browser_context:
        raise RuntimeError("Browser context could not be initialized after launch attempt.")
        
    return _browser_context

def check_for_captcha(page: Page):
    """Checks if the current page is a CAPTCHA page and raises CaptchaRequired if so."""
    current_url = page.url.lower()
    # Basic check for "captcha" or "showcaptcha" in URL, common for Yandex
    if "captcha" in current_url or "showcaptcha" in current_url or "smartcaptcha" in current_url:
        raise CaptchaRequired(captcha_url=page.url)
    # More specific element checks can be added here if needed, e.g., for specific iframe titles or form elements
    # For example, Yandex SmartCaptcha often uses an iframe with title='SmartCaptcha'
    if page.locator("iframe[title='SmartCaptcha']").count() > 0:
        raise CaptchaRequired(captcha_url=page.url)
    if page.locator("img[src*='captcha']").count() > 0 and page.locator("input[name*='captcha']").count() > 0: # Common image + input pattern
        raise CaptchaRequired(captcha_url=page.url)

def locate_target_company(page: Page, id: int) -> Locator:
    id_as_str = str(id)
    selector = f'a[href][tabindex]'
    found_element_locator: Locator | None = None
    potential_elements = page.locator(selector).all()
    for element_locator in potential_elements:
        href_value = element_locator.get_attribute("href")
        if href_value and id_as_str in href_value:
            found_element_locator = element_locator
            break
    if not found_element_locator:
        check_for_captcha(page) # Check for CAPTCHA before concluding not found
        abort(404, description=f"Company link containing ID '{id_as_str}' not found on page: {page.url}")
    return found_element_locator


def get_first_digits(text: str)-> int | None:
    match = regex.search(r'\d+', text)
    if match:
        return int(match.group(0))
    else:
        return None 


def get_all_hrefs_from_current_page(page: Page) -> list[str]:
    """
    Извлекает все атрибуты 'href' со страницы.
    """
    hrefs = []
    all_links = page.locator("a").all()
    for link in all_links:
            href = link.get_attribute("href")
            if href:  # Убеждаемся, что атрибут 'href' существует
                hrefs.append(href)
    return hrefs

def get_child_texts(page: Page, parent_locator: Locator) -> list[str]:
    """
    Извлекает все отдельные текстовые узлы (не теги, а именно текстовое содержимое)
    из элемента, представленного локатором, и всех его потомков.
    Каждый уникальный, непустой фрагмент текста помещается в отдельный элемент списка.

    Args:
        parent_locator (Locator): Локатор элемента, из которого нужно извлечь тексты.
        page (Page): The Playwright page object, for CAPTCHA checks.

    Returns:
        list[str]: Список строк, где каждая строка - это отдельный текстовый фрагмент.
                   Пустые строки и строки, содержащие только пробелы, игнорируются.
    """
    
    # 1. Получаем ссылку на элемент в контексте браузера
    # Playwright's evaluate() требует, чтобы локатор указывал на один элемент.
    # .element_handle() возвращает Playwright ElementHandle, который можно передать в evaluate.
    element_handle = parent_locator.element_handle()
    
    if not element_handle:
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Target element for text extraction not found or locator is invalid. Locator: '{parent_locator}' on page: {page.url}")

    # 2. Выполняем JavaScript-функцию в контексте браузера
    # Эта функция будет рекурсивно проходить по DOM.
    extracted_texts = element_handle.evaluate("""(element) => {
        const texts = [];

        function collectTextNodes(node) {
            // Если это текстовый узел (Node.TEXT_NODE === 3)
            if (node.nodeType === 3) {
                const textContent = node.textContent.trim();
                if (textContent) { // Добавляем только непустые текстовые фрагменты
                    texts.push(textContent);
                }
            } else if (node.nodeType === 1) { // Если это элемент (Node.ELEMENT_NODE === 1)
                // Пропускаем некоторые элементы, которые обычно не содержат видимого текста
                // или содержат текст, который не нужен (например, скрипты, стили, скрытые инпуты)
                const tagName = node.tagName.toLowerCase();
                if (['script', 'style', 'noscript', 'img', 'video', 'audio', 'iframe'].includes(tagName)) {
                    return; // Пропускаем эти теги
                }
                if (node.offsetParent === null && tagName !== 'body' && tagName !== 'html') {
                    // Это может означать, что элемент скрыт (display: none, visibility: hidden, etc.)
                    // Можно пропустить, если нужны только видимые тексты.
                    // Для простоты, пока не будем это делать, если не было явно запрошено.
                }

                // Рекурсивно проходим по дочерним узлам элемента
                for (const child of node.childNodes) {
                    collectTextNodes(child);
                }
            }
        }

        collectTextNodes(element); // Начинаем сбор с корневого элемента
        return texts;
    }""")
    
    return extracted_texts

def fill_period(page: Page, period: str | None = None):
    """В параметре период нажно указать дату в формате dd.mm.yyyy - dd.mm.yyyy
    Именно так и никак иначе"""
    try:
        span_period_locator = page.get_by_text("Период", exact=True)
        span_period_locator.wait_for(state="visible", timeout=5000)
    except Exception as e:
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Element <span> with text 'Период' not found or not visible on page {page.url}. Error: {e}")
    
    parent_locator = span_period_locator.locator("..") # type: ignore[PossiblyUnboundVariable]
    grandparent_locator = parent_locator.locator("..")
    input_to_fill_locator = grandparent_locator.locator("input")
    today = datetime.now()
    today_formatted = today.strftime("%d.%m.%Y")
    full_date_string = f"{today_formatted} - {today_formatted}"
    if period:
        full_date_string = period
    input_to_fill_locator.fill(full_date_string)

def select_grouping(page: Page):
    """
    Находит элемент <span> с текстом "Группировка",
    поднимается на два уровня вверх к его прародителю.
    Если прародитель является кнопкой <button>, кликает по ней
    и ждет 2 секунды.

    Args:
        page (Page): Объект страницы Playwright.

    """
    grandparent_tag_name: str = "" # Initialize to prevent UnboundLocalError

    # 1. Находим элемент <span> с текстом "Группировка"
    try:
        span_grouping_locator = page.get_by_text("Группировка", exact=True)
        span_grouping_locator.wait_for(state="visible", timeout=5000)
    except Exception as e:
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Element <span> with text 'Группировка' not found or not visible on page {page.url}. Error: {e}")

    # 2. Переходим к родительскому элементу
    parent_locator = span_grouping_locator.locator("..") # type: ignore[PossiblyUnboundVariable]

    # 3. Переходим к родительскому элементу родителя (прародителю)
    grandparent_locator = parent_locator.locator("..")

    try:
        grandparent_locator.wait_for(state="attached", timeout=1000) 
        tag_name_eval = grandparent_locator.evaluate('el => el.tagName')
        if not isinstance(tag_name_eval, str):
             abort(500, description=f"Could not determine tag name for grandparent of 'Группировка' on page {page.url}.")
        grandparent_tag_name = tag_name_eval.lower()
    except Exception as e:
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Grandparent element of 'Группировка' span not found or structure is unexpected on page {page.url}. Error: {e}")

    # 4. Проверяем, является ли прародитель кнопкой <button>
    if grandparent_tag_name == "button":
        try:
            # Кликаем по кнопке
            grandparent_locator.click()
            page.wait_for_timeout(2000) # Consider using more specific waits
            menu_popup_selector = '.ui-popup.ui-popup_visible.select__popup'
            target_menu_item_selector = f'{menu_popup_selector} div[data-name="data-menu-item-1"]'
            target_menu_item_locator = page.locator(target_menu_item_selector)
            target_menu_item_locator.wait_for(state="visible", timeout=5000)
            target_menu_item_locator.locator("*:first-child").click()
            page.wait_for_timeout(2000) # Consider using more specific waits
        except Exception as e:
            check_for_captcha(page) # Check for CAPTCHA
            abort(500, description=f"Error clicking 'Группировка' button or selecting item on page {page.url}. Error: {e}")
    else:
        abort(404, description=f"Grandparent element (tag: '{grandparent_tag_name}') of 'Группировка' on page {page.url} is not a <button>. Click not performed.")

def get_all_digits_from_string(text: str) -> int | None:
    if not isinstance(text, str):
        abort(500, description=f"Invalid input to get_all_digits_from_string: expected str, got {type(text)}. Input text (first 100 chars): '{text[:100]}...'")
    digits_list = regex.findall(r'\d', text)
    if not digits_list:
        return None
    digits_str = ''.join(digits_list)
    return int(digits_str)

def get_all_letters_from_string(text: str) -> str:
    """
    Извлекает все буквенные символы (включая латинские, кириллические и т.д.) из строки
    с использованием модуля 'regex' для поддержки Unicode-свойств.

    Args:
        text (str): Входная строка.

    Returns:
        str: Строка, содержащая только буквенные символы.
             Возвращает пустую строку, если буквенных символов нет.
    """
    if not isinstance(text, str):
        raise TypeError("Входной аргумент должен быть строкой.")
        
    # r'\p{L}' - соответствует любому буквенному символу из любой категории Unicode.
    # regex.U (или regex.UNICODE) - обязателен для работы \p{L}.
    letters = regex.findall(r'\p{L}', text, regex.U) # Используем regex.findall и regex.U
    return ''.join(letters) 

def get_branch_statistic(page: Page, branch_id: int, period: str | None = None) -> list[Tuple[str, Any]]:
    """Get branch statistics for a specified period.

    Args:
        page (Page): Playwright page object
        branch_id (int): Branch ID to get statistics for
        period (str, optional): Period in format 'dd.mm.yyyy - dd.mm.yyyy'. 
                              If None, returns statistics for current day.
    
    Returns:
        list[Tuple[str, Any]]: List of tuples containing statistics parameters and their values
    """
    page.goto(f"https://yandex.ru/business/statistic/company/{branch_id}/audience")
    check_for_captcha(page)
    fill_period(page, period)
    check_for_captcha(page) # Check after potential page changes from fill_period
    select_grouping(page)
    check_for_captcha(page) # Check after potential page changes from select_grouping

    locator_to_tab_transitions_to_branch_profile = page.get_by_text("Переходы в профиль филиала").locator("..").locator("..").locator("..")
    stat_boxes_locator = locator_to_tab_transitions_to_branch_profile.locator('div.stat-box-kind')
    count_stat_boxes_locator = stat_boxes_locator.count()
    tab_transitions_to_branch_profile_dict = {}
    for i in range(count_stat_boxes_locator): # type: ignore
        current_div_locator = stat_boxes_locator.nth(i)
        inner_texts = get_child_texts(page, current_div_locator)
        name_of_param = get_all_letters_from_string(inner_texts[0])
        value_of_param = get_all_digits_from_string(inner_texts[-1])
        params_dict = {name_of_param : value_of_param}
        tab_transitions_to_branch_profile_dict.update(params_dict)
    locator_to_tab_transitions_to_branch_profile = page.get_by_text("Что делали в профиле филиала").locator("..").locator("..").locator("..")
    stat_boxes_locator = locator_to_tab_transitions_to_branch_profile.locator('div.stat-box-kind')
    count_stat_boxes_locator = stat_boxes_locator.count()
    for i in range(count_stat_boxes_locator): # type: ignore
        current_div_locator = stat_boxes_locator.nth(i)
        inner_texts = get_child_texts(page, current_div_locator)
        name_of_param = get_all_letters_from_string(inner_texts[0])
        value_of_param = get_all_digits_from_string(inner_texts[-1])
        params_dict = {name_of_param : value_of_param}
        tab_transitions_to_branch_profile_dict.update(params_dict)
    
    return_list = list(tab_transitions_to_branch_profile_dict.items())
    return return_list

def get_branch_competitors(page: Page, branch_id: int) -> list[Tuple[str, Any]]:
    page.goto(f"https://yandex.ru/business/competitors/company/{branch_id}")
    check_for_captcha(page)

    # Initialize all variables that might not be set
    rating: str | None = None
    number_of_ratings_str: str | None = None
    number_of_photo_str: str | None = None
    number_of_products_str: str | None = None
    number_of_actions_str: str | None = None
    
    requests_for_your_categories_pair: Tuple[str, int | None] | None = None
    total_similar_companies_nearby_pair: Tuple[str, int | None] | None = None
    discovery_transitions_to_these_companies_pair: Tuple[str, int | None] | None = None
    discovery_transitions_to_company_leader_pair: Tuple[str, int | None] | None = None
    discovery_transitions_to_your_company_pair: Tuple[str, int | None] | None = None
    percentage_of_all_pair: Tuple[str, int | None] | None = None
    percentage_of_lider_pair: Tuple[str, int | None] | None = None

    try:
        own_company_locator = page.locator('div.company-competitors-table__own-company')
        own_company_locator.wait_for(state="visible", timeout=10000)
        all_inner_texts = get_child_texts(page, own_company_locator)
    except Exception as e:
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Own company block ('div.company-competitors-table__own-company') not found on competitors page ({page.url}) for branch_id {branch_id}. Error: {e}")
    
    if not all_inner_texts or len(all_inner_texts) < 6:
        # Not necessarily a CAPTCHA, could be page structure change or missing data
        abort(404, description=f"Insufficient data found in own company block on competitors page ({page.url}) for branch_id {branch_id}. Expected at least 6 text items, found: {len(all_inner_texts) if all_inner_texts else 0}. Texts: {all_inner_texts}")

    position = all_inner_texts[0]    
    traffic_share = all_inner_texts[1]
    branch_name = all_inner_texts[4]
    type_of_business = all_inner_texts[5]

    for i in range(len(all_inner_texts)):
        current_text = all_inner_texts[i]
        if current_text == "оценок":
            if i > 1: rating = all_inner_texts[i-2]
            if i > 0: number_of_ratings_str = all_inner_texts[i-1]
        elif current_text == "фото":
            if i > 0: number_of_photo_str = all_inner_texts[i-1]
        elif "товар" in current_text:
            if i > 0: number_of_products_str = all_inner_texts[i-1]
        elif "акци" in current_text and current_text != "Нет акций":
            if i > 0: number_of_actions_str = all_inner_texts[i-1]

    return_list: list[Tuple[str, Any]] = []
    return_list.append(("Позиция", get_all_digits_from_string(position) if position else None))
    return_list.append(("Доля трафика", traffic_share)) # Assuming traffic_share is like "X%", might need parsing
    return_list.append(("Название филиала", branch_name))
    return_list.append(("Тип бизнеса", type_of_business))

    if rating:
        return_list.append(("Рейтинг", rating))
    if number_of_ratings_str:
        return_list.append(("Количество оценок", get_all_digits_from_string(number_of_ratings_str)))
    if number_of_photo_str:
        return_list.append(("Количество фото", get_all_digits_from_string(number_of_photo_str)))
    if number_of_products_str:
        return_list.append(("Количество товаров или услуг", get_all_digits_from_string(number_of_products_str)))
    if number_of_actions_str:
        return_list.append(("Количество акций", get_all_digits_from_string(number_of_actions_str)))
    
    try:
        label_competitors_statistic_digest_locator = page.get_by_text("Похожие компании").locator("..")
        label_competitors_statistic_digest_locator.wait_for(state="visible", timeout=5000)
        all_inner_texts_digest = get_child_texts(page, label_competitors_statistic_digest_locator)
    except Exception as e:
        # This section might be optional; consider logging a warning or returning partial data.
        # For now, aborting if not found.
        check_for_captcha(page) # Check for CAPTCHA
        abort(404, description=f"Competitors statistics digest block ('Похожие компании') not found on page {page.url} for branch_id {branch_id}. Error: {e}")

    if not all_inner_texts_digest:
         check_for_captcha(page) # Check if empty because of CAPTCHA
         abort(404, description=f"No text found in competitors statistics digest block ('Похожие компании') on page {page.url} for branch_id {branch_id}.")

    for i in range(len(all_inner_texts_digest)):
        text_item = all_inner_texts_digest[i]
        next_item = all_inner_texts_digest[i+1] if i+1 < len(all_inner_texts_digest) else None
        prev_item = all_inner_texts_digest[i-1] if i > 0 else None
        
        if "Запросов по вашим категориям" in text_item and next_item:
            requests_for_your_categories_pair = ("Запросов по вашим категориям", get_all_digits_from_string(next_item))
        elif "Всего похожих" in text_item and "компаний рядом" in text_item and next_item:
            total_similar_companies_nearby_pair = ("Всего похожих компаний рядом", get_all_digits_from_string(next_item))
        elif "Дискавери-переходов в эти компании" in text_item and next_item:
            discovery_transitions_to_these_companies_pair = ("Дискавери-переходов в эти компании", get_all_digits_from_string(next_item))
        elif "Из них" in text_item and i+2 < len(all_inner_texts_digest) and 'у компании-лидера' in all_inner_texts_digest[i+2] and next_item:
            discovery_transitions_to_company_leader_pair = ("Из них у компании лидера", get_all_digits_from_string(next_item))
        elif 'Дискавери-переходов в вашу компанию' in text_item and next_item:
            discovery_transitions_to_your_company_pair = ('Дискавери-переходов в вашу компанию', get_all_digits_from_string(next_item))
        elif '% от всех' in text_item and prev_item:
            percentage_of_all_pair = ("% от всех", get_all_digits_from_string(prev_item))
        elif "% от лидера" in text_item and prev_item:
            percentage_of_lider_pair = ("% от лидера", get_all_digits_from_string(prev_item))

    if requests_for_your_categories_pair: return_list.append(requests_for_your_categories_pair)
    if total_similar_companies_nearby_pair: return_list.append(total_similar_companies_nearby_pair)
    if discovery_transitions_to_these_companies_pair: return_list.append(discovery_transitions_to_these_companies_pair)
    if discovery_transitions_to_company_leader_pair: return_list.append(discovery_transitions_to_company_leader_pair)
    if discovery_transitions_to_your_company_pair: return_list.append(discovery_transitions_to_your_company_pair)
    if percentage_of_all_pair: return_list.append(percentage_of_all_pair)
    if percentage_of_lider_pair: return_list.append(percentage_of_lider_pair)
    
    return return_list

def run(branch_id: int, period:str = None, cookies: list | None = None) -> Tuple[Response, Literal[200, 400]]:
    """
    Orchestrator: uses a persistent Playwright browser context, creates a new page for the request,
    scrapes stats + competitors for `branch_id`,
    then returns a Flask-friendly (JSON, status) tuple.

    :param branch_id: Yandex Business branch ID
    :param period: Optional period string.
    :param cookies: Optional list of cookie objects to load into the context.
    :returns: (json_response, status_code)
    """
    page_url_on_error: str = "Page not initialized or URL not available before error"
    page: Page | None = None 

    try:
        context = _get_or_create_browser_context()
        
        if cookies:
            context.add_cookies(cookies)
            logger.info(f"Applied {len(cookies)} cookies to the context for branch_id: {branch_id}.")

        page = context.new_page()
        page_url_on_error = "about:blank (initial page)"
        logger.info(f"New page created for branch_id: {branch_id}, period: {period}")

        stats = get_branch_statistic(page, branch_id, period)
        page_url_on_error = page.url 

        competitors = get_branch_competitors(page, branch_id)
        page_url_on_error = page.url 

        payload = {
            "branch_id": branch_id,
            "statistics": stats,
            "competitors": competitors
        }
        return jsonify(payload), 200
    
    except CaptchaRequired as cr_exc:
        current_url = cr_exc.captcha_url
        logger.warning(f"CaptchaRequired at {current_url} for branch_id: {branch_id}, period: {period}.")
        raise # Re-raise it to be handled by Flask's error handler for CaptchaRequired
    except HTTPException: # Catch HTTPException specifically (raised by abort())
        raise # Re-raise it to be handled by Flask's error handlers
    except Exception as exc:
        logger.exception(f"Unhandled error in yandex_scraper.run for branch_id: {branch_id}, period: {period}")
        
        current_url_for_error_msg = page_url_on_error
        if page and not page.is_closed():
            try:
                current_url_for_error_msg = page.url
            except Exception:
                logger.warning("Could not retrieve URL from page object during error handling.")
        
        error_details = f"branch_id: {branch_id}, period: {period}, last_known_url: {current_url_for_error_msg}"
        abort(500, description=f"An unexpected error occurred in the yandex_scraper for {error_details}. Error: {str(exc)}")
    finally:
        if page and not page.is_closed():
            try:
                page.close()
                logger.info(f"Page for branch_id: {branch_id} closed successfully.")
            except Exception as e:
                logger.error(f"Error closing page for branch_id: {branch_id}: {e}")
