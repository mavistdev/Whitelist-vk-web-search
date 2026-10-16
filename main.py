import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.upload import VkUpload
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import random
import re
import tempfile
from fake_useragent import UserAgent

# Ваш access token для бота VK (получите его через Implicit Flow или другой метод)
ACCESS_TOKEN = '...'

# ID группы (без минуса, только число)
GROUP_ID = '...'

# Шаблоны сообщений для естественного общения
SUCCESS_MESSAGES = [
    "Готово! Вот скриншот твоей страницы 😊",
    "Сфоткал сайт, держи!",
    "Вот страничка, как ты просил! 😎",
    "Скриншот готов, лови его 👇",
    "Сделал снимок сайта, смотри!"
]

NO_BUTTONS_MESSAGE = "Кнопок на странице не найдено, но вот скриншот! Используй @club... render [адрес] для другого сайта."

ERROR_MESSAGES = [
    "Ой, что-то пошло не так: {error}. Попробуй другую ссылку или кнопку!",
    "Не смог сделать: {error}. Может, адрес или кнопка недоступны?",
    "Упс, ошибка: {error}. Проверь, всё ли правильно.",
    "Что-то сломалось: {error}. Давай попробуем другой сайт или действие?"
]

ASK_URL_MESSAGE = "Пожалуйста, укажи сайт для работы с кнопками, используя команду @club... render [адрес]."

INTERACTION_MESSAGE = "Выберите действие с кнопками на странице:"

CANCEL_TEXT = "Отмена"

# Словарь для хранения сессий: chat_id -> {'driver': driver, 'url': url, 'buttons': list of elements, 'button_texts': list of str}
sessions = {}

# Функция для создания полного скриншота страницы
def make_full_screenshot(driver):
    width = driver.execute_script('return Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth);')
    height = driver.execute_script('return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);')
    
    driver.set_window_size(width, height)
    time.sleep(0.5)

    screenshot_path = f'screenshot_{random.randint(0, 9999999)}.png'
    driver.save_screenshot(screenshot_path)
    
    return screenshot_path

# Функция для поиска кликабельных элементов (кнопок)
def find_buttons(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//button | //input[@type="button" or @type="submit"] | //a[@role="button" or contains(@class, "button") or contains(@class, "btn")]'))
        )
        elements = driver.find_elements(By.XPATH, '//button | //input[@type="button" or @type="submit"] | //a[@role="button" or contains(@class, "button") or contains(@class, "btn")]')
        button_texts = []
        for elem in elements:
            if elem.is_displayed() and elem.is_enabled():
                text = elem.text.strip()
                if not text:
                    text = elem.get_attribute('value') or elem.get_attribute('aria-label') or elem.get_attribute('title') or ''
                if text:
                    button_texts.append(text)
        return elements[:10], button_texts[:10]
    except Exception:
        return [], []

# Функция для инициализации сессии с сайтом
def init_session(vk, upload, chat_id, url):
    try:
        if chat_id in sessions:
            sessions[chat_id]['driver'].quit()
            del sessions[chat_id]
        
        ua = UserAgent()
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument(f'--user-agent={ua.random}')
        options.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(random.uniform(2, 5))
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(0.5, 1.5))
        driver.execute_script("window.scrollTo(0, 0);")
        
        buttons, button_texts = find_buttons(driver)
        
        sessions[chat_id] = {
            'driver': driver,
            'url': url,
            'buttons': buttons,
            'button_texts': button_texts
        }
        
        screenshot_path = make_full_screenshot(driver)
        doc = upload.document_message(screenshot_path, peer_id=chat_id + 2000000000)['doc']
        attachment = f'doc{doc["owner_id"]}_{doc["id"]}'
        
        vk.messages.send(
            chat_id=chat_id,
            message=random.choice(SUCCESS_MESSAGES) if button_texts else NO_BUTTONS_MESSAGE,
            attachment=attachment,
            random_id=vk_api.utils.get_random_id()
        )
        
        os.remove(screenshot_path)
        
        if button_texts:
            keyboard = VkKeyboard(one_time=False, inline=False)
            for i, text in enumerate(button_texts):
                keyboard.add_button(f'Нажать {i+1}: {text[:30]}', color=VkKeyboardColor.PRIMARY)
                keyboard.add_line()
            keyboard.add_button(CANCEL_TEXT, color=VkKeyboardColor.NEGATIVE)
            
            vk.messages.send(
                chat_id=chat_id,
                message=INTERACTION_MESSAGE,
                keyboard=keyboard.get_keyboard(),
                random_id=vk_api.utils.get_random_id()
            )
        
        return driver, button_texts
    except Exception as e:
        vk.messages.send(
            chat_id=chat_id,
            message=random.choice(ERROR_MESSAGES).format(error=str(e)),
            random_id=vk_api.utils.get_random_id()
        )
        return None, None

# Функция для отправки скриншота и клавиатуры с кнопками
def send_screenshot_and_buttons(vk, upload, chat_id, driver, button_texts):
    screenshot_path = make_full_screenshot(driver)
    
    doc = upload.document_message(screenshot_path, peer_id=chat_id + 2000000000)['doc']
    attachment = f'doc{doc["owner_id"]}_{doc["id"]}'
    
    vk.messages.send(
        chat_id=chat_id,
        message=random.choice(SUCCESS_MESSAGES),
        attachment=attachment,
        random_id=vk_api.utils.get_random_id()
    )
    
    os.remove(screenshot_path)
    
    keyboard = VkKeyboard(one_time=False, inline=False)
    for i, text in enumerate(button_texts):
        keyboard.add_button(f'Нажать {i+1}: {text[:30]}', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
    keyboard.add_button(CANCEL_TEXT, color=VkKeyboardColor.NEGATIVE)
    
    vk.messages.send(
        chat_id=chat_id,
        message=INTERACTION_MESSAGE,
        keyboard=keyboard.get_keyboard(),
        random_id=vk_api.utils.get_random_id()
    )

# Основная функция бота
def main():
    vk_session = vk_api.VkApi(token=ACCESS_TOKEN)
    longpoll = VkLongPoll(vk_session, group_id=GROUP_ID)
    upload = VkUpload(vk_session)
    vk = vk_session.get_api()

    print("Бот запущен. Ожидание команд в чате...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.from_chat:
            message_text = event.text.strip()
            chat_id = event.chat_id
            
            # Удаляем упоминание группы (например, [club212802470|Название])
            cleaned_text = re.sub(r'\[club\d+\|[^\]]+\]\s*', '', message_text).strip()
            
            if cleaned_text.startswith('render '):
                url = cleaned_text.split(' ', 1)[1].strip()
                if not url.startswith('http'):
                    url = 'https://' + url
                
                init_session(vk, upload, chat_id, url)
            
            elif cleaned_text.startswith('Нажать '):
                if chat_id not in sessions:
                    vk.messages.send(
                        chat_id=chat_id,
                        message=ASK_URL_MESSAGE,
                        random_id=vk_api.utils.get_random_id()
                    )
                    continue
                
                try:
                    parts = cleaned_text.split(' ', 1)[1].split(':')
                    index = int(parts[0]) - 1
                    session = sessions[chat_id]
                    buttons = session['buttons']
                    
                    if 0 <= index < len(buttons):
                        button = buttons[index]
                        if not button.is_displayed() or not button.is_enabled():
                            raise Exception("Кнопка не видна или недоступна для нажатия.")
                        
                        driver = session['driver']
                        driver.execute_script("arguments[0].scrollIntoView(true);", button)
                        time.sleep(random.uniform(0.5, 1))
                        
                        try:
                            button.click()
                        except:
                            driver.execute_script("arguments[0].click();", button)
                        
                        time.sleep(random.uniform(2, 4))
                        
                        new_buttons, new_button_texts = find_buttons(driver)
                        session['buttons'] = new_buttons
                        session['button_texts'] = new_button_texts
                        
                        if not new_button_texts:
                            screenshot_path = make_full_screenshot(driver)
                            doc = upload.document_message(screenshot_path, peer_id=chat_id + 2000000000)['doc']
                            attachment = f'doc{doc["owner_id"]}_{doc["id"]}'

                            vk.messages.send(
                                chat_id=chat_id,
                                message=NO_BUTTONS_MESSAGE,
                                attachment=attachment,
                                random_id=vk_api.utils.get_random_id()
                            )
                            
                            os.remove(screenshot_path)
                        else:
                            send_screenshot_and_buttons(vk, upload, chat_id, driver, new_button_texts)
                    else:
                        raise Exception("Неверный номер кнопки.")
                except Exception as e:
                    vk.messages.send(
                        chat_id=chat_id,
                        message=random.choice(ERROR_MESSAGES).format(error=str(e)),
                        random_id=vk_api.utils.get_random_id()
                    )
            
            elif cleaned_text == CANCEL_TEXT and chat_id in sessions:
                sessions[chat_id]['driver'].quit()
                del sessions[chat_id]
                vk.messages.send(
                    chat_id=chat_id,
                    message="Сессия с сайтом закрыта. Чтобы начать заново, используйте команду @club... render [адрес].",
                    random_id=vk_api.utils.get_random_id()
                )

if __name__ == '__main__':
    main()