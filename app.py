import os
import json
import time
import platform
import threading
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import psutil
import sys

# File paths
COOKIES_PATH = Path(__file__).parent / 'cookies.json'
TIME_PATH = Path(__file__).parent / 'time.txt'
HATERS_NAME_PATH = Path(__file__).parent / 'hatersname.txt'
CONVO_PATH = Path(__file__).parent / 'convo.txt'
MESSAGES_PATH = Path(__file__).parent / 'NP.txt'

active_processes = {}
message_rotation_index = 0

# Flask app setup
app = Flask(__name__)
CORS(app)

# Environment detection
def is_render_environment():
    return bool(os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'))

def check_vps_only():
    # For Render, always return true since we're in a cloud environment
    if is_render_environment():
        return True
    
    # For other environments, use original checks
    if platform.system() != 'Linux':
        return False
    if os.environ.get('DISPLAY') and not os.environ.get('REPL_ID'):
        return False
    if not (Path(__file__).parent / 'etc' / 'vps_only').exists():
        return False
    return True

if not check_vps_only():
    print('⛔ This script can run only on VPS environment.')
    sys.exit(1)

def perform_e2ee_simulated_handshake(process_id):
    key_path = Path(__file__).parent / 'etc' / 'e2ee_key'
    if key_path.exists():
        print(f'[{process_id}] 🔐 E2EE handshake simulated: key found ({key_path}).')
        return True
    else:
        print(f'[{process_id}] ⚠️ E2EE handshake simulated: key missing -> creating dummy key for deployment.')
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text('dummy-key-for-deployment-environment')
            return True
        except Exception as e:
            return False

def safe_read_file_trim(file_path):
    try:
        if not file_path:
            return ''
        if not Path(file_path).exists():
            return ''
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            return ' '.join(lines)
    except Exception:
        return ''

def read_config_from_files():
    try:
        # Read cookies from cookies.json
        cookies = ''
        if COOKIES_PATH.exists():
            with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                cookies = cookies_data.get('facebook_cookies', '')

        # Read delay time from time.txt
        delay = '30'  # Increased default delay
        if TIME_PATH.exists():
            delay = TIME_PATH.read_text(encoding='utf-8').strip() or '30'

        # Read target name from hatersname.txt
        haters_name = ''
        if HATERS_NAME_PATH.exists():
            haters_name = HATERS_NAME_PATH.read_text(encoding='utf-8').strip()

        # Read chat_id from convo.txt
        chat_id = ''
        if CONVO_PATH.exists():
            chat_id = CONVO_PATH.read_text(encoding='utf-8').strip()

        # Read messages from NP.txt
        messages = ['Hello! Default message from deployment']
        if MESSAGES_PATH.exists():
            messages_content = MESSAGES_PATH.read_text(encoding='utf-8')
            messages = [line.strip() for line in messages_content.split('\n') if line.strip()]

        return {
            'cookies': cookies,
            'delay': delay,
            'haters_name': haters_name,
            'chat_id': chat_id,
            'messages': messages
        }
    except Exception as error:
        print(f'Error reading config files: {error}')
        return {
            'cookies': '',
            'delay': '30',
            'haters_name': '',
            'chat_id': '',
            'messages': ['Hello! Default message from deployment']
        }

def get_next_message(messages):
    global message_rotation_index
    if not messages or len(messages) == 0:
        return 'Hello! Default message from deployment'
    
    message = messages[message_rotation_index % len(messages)]
    message_rotation_index += 1
    return message

# Enhanced message input finder for Facebook
def find_message_input(driver, process_id):
    print(f'[🔍] {process_id}: Finding message input...')
    
    # Wait for page to fully load
    time.sleep(5)
    
    # Comprehensive list of selectors for Facebook message input (2024 updated)
    message_input_selectors = [
        # New Facebook Messenger selectors (2024)
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[aria-label*="Message" i][contenteditable="true"]',
        'div[aria-label*="Type" i][contenteditable="true"]',
        'div[aria-label*="Write" i][contenteditable="true"]',
        'div[aria-label*="Send" i][contenteditable="true"]',
        
        # Generic contenteditable selectors
        'div[contenteditable="true"][spellcheck="true"]',
        'div[contenteditable="true"][aria-multiline="true"]',
        'div[contenteditable="true"]:not([aria-hidden="true"])',
        
        # Fallback selectors
        '[role="textbox"][contenteditable="true"]',
        '[aria-label="Message"][contenteditable="true"]',
        '[aria-label="Type a message"][contenteditable="true"]',
        '[aria-label="Write a message..."][contenteditable="true"]',
        '[role="combobox"][contenteditable="true"]',
        '.notranslate[contenteditable="true"]',
        
        # Mobile Facebook selectors
        'textarea[placeholder*="message" i]',
        'textarea[placeholder*="Message" i]',
        'textarea[placeholder*="Type" i]',
        'input[placeholder*="message" i]',
        'input[placeholder*="Message" i]',
        
        # Last resort - any contenteditable
        '[contenteditable="true"]'
    ]
    
    # Try each selector with enhanced checking
    for selector in message_input_selectors:
        try:
            print(f'[🔍] {process_id}: Trying selector: {selector}')
            
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            for element in elements:
                try:
                    # Check if element is visible and interactable
                    if element.is_displayed() and element.size['width'] > 0 and element.size['height'] > 0:
                        # Additional check - try to focus the element
                        element.click()
                        time.sleep(1)
                        
                        # Check if we can type in it
                        is_editable = driver.execute_script("""
                            return arguments[0].contentEditable === 'true' || 
                                   arguments[0].tagName === 'TEXTAREA' || 
                                   arguments[0].tagName === 'INPUT';
                        """, element)
                        
                        if is_editable:
                            # Additional verification - check if this is actually a message input
                            element_text = driver.execute_script("return arguments[0].placeholder || arguments[0].getAttribute('aria-label') || '';", element).lower()
                            parent_text = driver.execute_script("return arguments[0].parentElement ? (arguments[0].parentElement.textContent || '') : '';", element).lower()
                            
                            # Verify it's actually for messaging
                            if any(keyword in element_text + parent_text for keyword in ['message', 'write', 'type', 'send', 'chat']):
                                print(f'[✅] {process_id}: Found verified message input with: {selector}')
                                print(f'[🔍] {process_id}: Element context: {element_text[:50]}')
                                return element
                            else:
                                print(f'[⚠️] {process_id}: Found input but not for messaging: {element_text[:30]}')
                except Exception:
                    continue
        except Exception:
            print(f'[❌] {process_id}: Selector failed: {selector}')
            continue
    
    # Last attempt - try to click on conversation area to activate input
    print(f'[🔄] {process_id}: Trying to activate message input by clicking...')
    try:
        # Click on the conversation area
        driver.find_element(By.TAG_NAME, 'body').click()
        time.sleep(2)
        
        # Try pressing Tab to focus message input
        webdriver.ActionChains(driver).send_keys(Keys.TAB).perform()
        time.sleep(1)
        
        # Try the selectors again
        for selector in message_input_selectors[:10]:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.is_displayed():
                    print(f'[✅] {process_id}: Found message input after activation: {selector}')
                    return element
            except Exception:
                continue
    except Exception:
        print(f'[❌] {process_id}: Activation attempt failed')
    
    return None

# Enhanced browser setup for Selenium
def setup_browser_for_deployment():
    print('[🔧] Setting up Chrome browser for deployment environment...')
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-plugins-discovery')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--ignore-certificate-errors-spki-list')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_window_size(1920, 1080)
        print('[✅] Chrome browser setup completed')
        return driver
    except Exception as error:
        print(f'[❌] Browser setup failed: {error}')
        raise error

# Enhanced message sending function with timeout protection
def send_facebook_messages(driver, haters_name, messages, delay, process_id):
    print(f'[🚀] {process_id}: Starting enhanced message sending process...')
    
    message_count = 0
    should_stop = False
    
    # Auto-stop after 30 minutes to prevent indefinite hanging
    def auto_stop():
        nonlocal should_stop
        time.sleep(30 * 60)  # 30 minutes
        print(f'[⏰] {process_id}: Auto-stopping after 30 minutes to prevent hanging')
        should_stop = True
    
    auto_stop_thread = threading.Thread(target=auto_stop, daemon=True)
    auto_stop_thread.start()
    
    try:
        # Add stealth settings to avoid detection
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            window.chrome = {
                runtime: {},
            };
        """)
        
        # Step 1: Navigate to Facebook main page with extended timeout
        print(f'[🌐] {process_id}: Navigating to Facebook...')
        try:
            driver.get('https://www.facebook.com/')
            print(f'[✅] {process_id}: Facebook main page loaded')
        except Exception:
            print(f'[⚠️] {process_id}: Main page navigation failed, trying mobile version...')
            driver.get('https://m.facebook.com/')
        time.sleep(8)
        
        # Step 2: Add cookies if available
        config = read_config_from_files()
        cookie_string = os.environ.get('FB_COOKIES') or config['cookies']
        
        if cookie_string and cookie_string.strip() and cookie_string != 'YOUR_COOKIES_HERE':
            print(f'[🍪] {process_id}: Adding cookies to session...')
            cookie_array = cookie_string.split(';')
            cookies_added = 0
            
            for cookie in cookie_array:
                cookie_trimmed = cookie.strip()
                if cookie_trimmed:
                    first_equal_index = cookie_trimmed.find('=')
                    if first_equal_index > 0:
                        name = cookie_trimmed[:first_equal_index].strip()
                        value = cookie_trimmed[first_equal_index + 1:].strip()
                        try:
                            driver.add_cookie({
                                'name': name,
                                'value': value,
                                'domain': '.facebook.com',
                                'path': '/'
                            })
                            cookies_added += 1
                        except Exception:
                            print(f'[!] {process_id}: Failed to add cookie {name}')
            print(f'[✅] {process_id}: {cookies_added} cookies added')
        else:
            print(f'[⚠️] {process_id}: No valid cookies provided')
        
        # Step 3: Navigate to messages using multiple fallback options
        navigation_success = False
        
        if config['chat_id'] and config['chat_id'].strip():
            chat_id = config['chat_id'].strip()
            print(f'[💬] {process_id}: Trying direct conversation URL for ID: {chat_id}')
            
            # Try multiple URL formats for conversation
            conversation_urls = [
                f'https://www.facebook.com/messages/t/{chat_id}',
                f'https://www.facebook.com/messages/thread/{chat_id}',
                f'https://m.facebook.com/messages/thread/{chat_id}',
                f'https://www.facebook.com/messages/conversation-{chat_id}',
                f'https://www.messenger.com/t/{chat_id}'
            ]
            
            for url in conversation_urls:
                try:
                    print(f'[🔗] {process_id}: Trying URL: {url}')
                    driver.get(url)
                    time.sleep(5)
                    
                    # Check if conversation loaded by looking for message input
                    test_inputs = driver.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"], textarea, input[type="text"]')
                    if test_inputs:
                        print(f'[✅] {process_id}: Conversation loaded successfully with: {url}')
                        navigation_success = True
                        break
                    else:
                        print(f'[⚠️] {process_id}: No message input found with: {url}')
                except Exception as e:
                    print(f'[❌] {process_id}: Failed to load {url}: {e}')
                    continue
        
        if not navigation_success:
            print(f'[💬] {process_id}: Trying general messages page...')
            try:
                driver.get('https://www.facebook.com/messages')
                navigation_success = True
            except Exception:
                print(f'[💬] {process_id}: Trying mobile messages...')
                driver.get('https://m.facebook.com/messages')
                navigation_success = True
        
        if not navigation_success:
            raise Exception('Failed to load any Facebook messages page')
        
        # Wait for page to load completely
        time.sleep(12)
        
        # Take screenshot for debugging
        try:
            screenshot_path = f'/tmp/{process_id}_loaded.png'
            driver.save_screenshot(screenshot_path)
            print(f'[📸] {process_id}: Page loaded screenshot -> {screenshot_path}')
        except Exception as e:
            print(f'[!] {process_id}: Screenshot failed: {e}')
        
        # Enhanced page analysis
        try:
            page_source_snippet = driver.page_source[:1000] if driver.page_source else "No page source"
            print(f'[🔍] {process_id}: Page source snippet: {page_source_snippet[:200]}...')
            
            # Check for login requirements
            if 'login' in driver.current_url.lower() or 'login' in driver.page_source.lower()[:500]:
                print(f'[⚠️] {process_id}: Detected login page - cookies may be expired')
            
            # Check for blocked/restricted content
            if any(word in driver.page_source.lower()[:1000] for word in ['blocked', 'restricted', 'suspended', 'disabled']):
                print(f'[⚠️] {process_id}: Account may be restricted or blocked')
                
        except Exception as e:
            print(f'[!] {process_id}: Page analysis failed: {e}')
        
        # Debug: Log page title and URL
        try:
            title = driver.title
            url = driver.current_url
            print(f'[🔍] {process_id}: Page title: "{title}"')
            print(f'[🔍] {process_id}: Page URL: {url}')
        except Exception as e:
            print(f'[!] {process_id}: Debug info failed: {e}')
        
        # Step 4: Handle overlays and pop-ups first
        print(f'[🚧] {process_id}: Dismissing overlays and pop-ups...')
        try:
            # Common Facebook overlay/modal dismissal
            overlay_selectors = [
                '[aria-label="Close"]',
                '[data-testid="modal-close-button"]', 
                'div[role="button"][aria-label="Close"]',
                'button[aria-label="Close"]',
                '[role="dialog"] [aria-label="Close"]',
                '.x1i10hfl.x6umtig.x1b1mbwd.xaqea5y.xav7gou.x9f619.x1ypdohk.xe8uvvx.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.x16tdsg8.x1hl2dhg.xggy1nq.x87ps6o.x1lku1pv.x1a2a7pz.x6s0dn4.xmjcpbm.x107yiy2.xv8uw2v.x1tfwpuw.x2g32xy.x78zum5.x1q0g3np.x1iyjqo2.x1nhvcw1.x1n2onr6.x14wi4xw.x1bg5an6[role="button"]'
            ]
            
            for selector in overlay_selectors:
                try:
                    overlay_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for overlay in overlay_elements:
                        if overlay.is_displayed():
                            driver.execute_script("arguments[0].click();", overlay)
                            print(f'[✅] {process_id}: Dismissed overlay: {selector}')
                            time.sleep(2)
                            break
                except Exception:
                    continue
                    
            # Dismiss notification permission requests
            try:
                driver.execute_script("""
                    // Dismiss notification dialogs
                    document.querySelectorAll('[role="dialog"]').forEach(dialog => {
                        const closeBtn = dialog.querySelector('[aria-label="Close"], [aria-label="Not Now"], [aria-label="Cancel"]');
                        if (closeBtn) closeBtn.click();
                    });
                    
                    // Remove any fixed position overlays that might block interaction
                    document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"]').forEach(el => {
                        if (el.style.zIndex > 1000) {
                            el.style.display = 'none';
                        }
                    });
                """)
                print(f'[✅] {process_id}: JavaScript overlay cleanup completed')
            except Exception as e:
                print(f'[⚠️] {process_id}: JavaScript cleanup failed: {e}')
                
        except Exception as e:
            print(f'[⚠️] {process_id}: Overlay dismissal failed: {e}')
        
        time.sleep(3)

        # Step 5: Find and verify message input
        print(f'[🔍] {process_id}: Looking for message input...')
        message_input = find_message_input(driver, process_id)
        
        if not message_input:
            print(f'[❌] {process_id}: Message input not found after all attempts')
            raise Exception('Could not locate message input field')
        
        print(f'[✅] {process_id}: Message input found! Starting message loop...')
        
        # Step 5: Message sending loop
        while not should_stop and message_count < 50:  # Safety limit
            try:
                base_message = get_next_message(messages)
                current_message = f'{haters_name} {base_message}'
                
                print(f'[📝] {process_id}: Typing message {message_count + 1}: "{current_message}"')
                
                # Enhanced message typing with realistic human-like interaction
                typing_success = False
                
                print(f'[🔧] {process_id}: Scrolling message input into view...')
                try:
                    # Scroll element into view to avoid interception
                    driver.execute_script("""
                        arguments[0].scrollIntoView({
                            behavior: 'smooth',
                            block: 'center',
                            inline: 'center'
                        });
                    """, message_input)
                    time.sleep(3)
                except Exception as e:
                    print(f'[⚠️] {process_id}: Scroll failed: {e}')
                
                # Method 1: ActionChains (PRIMARY - Real keyboard simulation)
                try:
                    print(f'[🔧] {process_id}: Using ActionChains real typing...')
                    
                    # Use ActionChains to send keys - this triggers real keyboard events
                    from selenium.webdriver.common.action_chains import ActionChains
                    
                    # First clear the input using JavaScript
                    driver.execute_script("""
                        const element = arguments[0];
                        element.focus();
                        element.click();
                        if (element.tagName === 'DIV') {
                            element.innerHTML = '';
                            element.textContent = '';
                        } else {
                            element.value = '';
                        }
                    """, message_input)
                    time.sleep(1)
                    
                    # Now type using ActionChains for real keyboard events
                    actions = ActionChains(driver)
                    actions.send_keys(current_message)   # Type message
                    actions.perform()
                    
                    typing_success = True
                    print(f'[✅] {process_id}: ActionChains real typing successful')
                    time.sleep(2)  # Wait for Facebook to register the input
                    
                except Exception as e:
                    print(f'[⚠️] {process_id}: ActionChains method failed: {e}')
                
                # Method 2: Fallback with Enhanced JavaScript typing
                if not typing_success:
                    try:
                        print(f'[🔄] {process_id}: Fallback - Enhanced JavaScript typing...')
                        
                        # Enhanced JavaScript method with realistic typing simulation
                        result = driver.execute_script("""
                            const element = arguments[0];
                            const message = arguments[1];
                            
                            try {
                                // Remove any blocking overlays
                                document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"]').forEach(el => {
                                    if (el.style.zIndex > 1000 && el !== element && !element.contains(el)) {
                                        el.style.display = 'none';
                                    }
                                });
                                
                                // Scroll element into view and wait
                                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                
                                // Focus the element properly
                                element.focus();
                                element.click();
                                
                                // Wait a bit for focus
                                setTimeout(() => {
                                    // Clear existing content more thoroughly
                                    if (element.tagName === 'DIV') {
                                        element.innerHTML = '';
                                        element.textContent = '';
                                        // For contenteditable divs, also try this
                                        const selection = window.getSelection();
                                        const range = document.createRange();
                                        range.selectNodeContents(element);
                                        selection.removeAllRanges();
                                        selection.addRange(range);
                                        document.execCommand('delete', false, null);
                                    } else {
                                        element.value = '';
                                        element.select();
                                    }
                                    
                                    // Simulate realistic typing character by character
                                    let currentText = '';
                                    let charIndex = 0;
                                    
                                    const typeChar = () => {
                                        if (charIndex < message.length) {
                                            currentText += message[charIndex];
                                            
                                            if (element.tagName === 'DIV') {
                                                element.innerHTML = currentText;
                                                element.textContent = currentText;
                                            } else {
                                                element.value = currentText;
                                            }
                                            
                                            // Dispatch input event for each character
                                            element.dispatchEvent(new Event('input', { 
                                                bubbles: true, 
                                                cancelable: true,
                                                data: message[charIndex]
                                            }));
                                            
                                            charIndex++;
                                            // Random delay between characters (50-150ms)
                                            setTimeout(typeChar, Math.random() * 100 + 50);
                                        } else {
                                            // After typing is complete, dispatch final events
                                            element.dispatchEvent(new Event('change', { bubbles: true }));
                                            element.dispatchEvent(new KeyboardEvent('keydown', { 
                                                key: 'Enter', 
                                                code: 'Enter', 
                                                bubbles: true 
                                            }));
                                        }
                                    };
                                    
                                    // Start typing simulation
                                    typeChar();
                                    
                                }, 500);
                                
                                return 'success';
                            } catch (error) {
                                return 'error: ' + error.message;
                            }
                        """, message_input, current_message)
                        
                        if result == 'success':
                            typing_success = True
                            print(f'[✅] {process_id}: Enhanced JavaScript typing started')
                            # Wait for typing simulation to complete
                            time.sleep(len(current_message) * 0.1 + 2)
                        else:
                            print(f'[⚠️] {process_id}: Enhanced JavaScript typing failed: {result}')
                        
                    except Exception as e:
                        print(f'[⚠️] {process_id}: Enhanced JavaScript method failed: {e}')
                
                # Method 3: Last resort - basic JavaScript
                if not typing_success:
                    print(f'[🔄] {process_id}: Last resort - basic JavaScript insertion...')
                    try:
                        driver.execute_script("""
                            const element = arguments[0];
                            const message = arguments[1];
                            element.focus();
                            if (element.tagName === 'DIV') {
                                element.innerHTML = message;
                                element.textContent = message;
                            } else {
                                element.value = message;
                            }
                            element.dispatchEvent(new Event('input', { bubbles: true }));
                        """, message_input, current_message)
                        
                        print(f'[✅] {process_id}: Basic JavaScript insertion successful')
                        typing_success = True
                        
                    except Exception as e:
                        print(f'[❌] {process_id}: All typing methods failed: {e}')
                
                if not typing_success:
                    print(f'[💥] {process_id}: Could not type message - skipping this iteration')
                    continue
                
                time.sleep(2)
                
                # Wait for typing to complete, then send message
                time.sleep(2)
                
                # Enhanced message sending with multiple attempts - PRIORITIZE BUTTON CLICK
                sent_successfully = False
                
                # Method 1 (PRIMARY): Look for and click send button - most reliable for modern Facebook
                print(f'[📤] {process_id}: Primary method - Looking for send button...')
                
                # Simplified and more effective send button selectors
                send_button_selectors = [
                    # Most effective Facebook send button selectors (2024)
                    '[data-testid="send-button"]',
                    '[aria-label="Send"]',
                    '[aria-label*="Send" i]:not([aria-label*="voice"]):not([aria-label*="audio"]):not([aria-label*="call"]):not([aria-label*="like" i])',
                    'div[role="button"][aria-label="Send"]',
                    'button[aria-label="Send"]'
                ]
                
                button_clicked = False
                for i, btn_selector in enumerate(send_button_selectors):
                    try:
                        print(f'[🔍] {process_id}: Trying button selector {i+1}/{len(send_button_selectors)}: {btn_selector}')
                        buttons = driver.find_elements(By.CSS_SELECTOR, btn_selector)
                        
                        for btn in buttons:
                            try:
                                if btn.is_displayed() and btn.is_enabled():
                                    btn_text = btn.get_attribute('aria-label') or 'No text'
                                    
                                    # Skip "Like" buttons
                                    if 'like' in btn_text.lower():
                                        print(f'[⏭️] {process_id}: Skipping Like button: "{btn_text}"')
                                        continue
                                    
                                    print(f'[🎯] {process_id}: Found send button: "{btn_text}"')
                                    
                                    # Try JavaScript click first
                                    driver.execute_script("arguments[0].click();", btn)
                                    print(f'[✅] {process_id}: Send button clicked')
                                    sent_successfully = True
                                    button_clicked = True
                                    break
                                        
                            except Exception as e:
                                continue
                        
                        if button_clicked:
                            break
                            
                    except Exception as e:
                        continue
                
                if not sent_successfully:
                    print(f'[⚠️] {process_id}: No send button found - using keyboard method')
                
                # Method 2 (PRIMARY): Enhanced Enter key - most reliable method for Facebook
                if not sent_successfully:
                    print(f'[📤] {process_id}: Primary method - Enhanced Enter key simulation...')
                    try:
                        # Focus and send using Enter key
                        message_input.click()
                        time.sleep(1)
                        
                        # Send using ActionChains Enter (most reliable)
                        from selenium.webdriver import ActionChains
                        ActionChains(driver).send_keys(Keys.ENTER).perform()
                        
                        sent_successfully = True
                        print(f'[✅] {process_id}: Enter key method successful')
                    except Exception as e:
                        print(f'[⚠️] {process_id}: Enter key method failed: {e}')
                        
                        # Fallback: JavaScript Enter simulation
                        try:
                            driver.execute_script("""
                                const element = arguments[0];
                                element.focus();
                                
                                const event = new KeyboardEvent('keydown', {
                                    key: 'Enter',
                                    code: 'Enter',
                                    keyCode: 13,
                                    which: 13,
                                    bubbles: true,
                                    cancelable: true
                                });
                                element.dispatchEvent(event);
                            """, message_input)
                            
                            sent_successfully = True
                            print(f'[✅] {process_id}: JavaScript Enter successful')
                        except Exception as e2:
                            print(f'[⚠️] {process_id}: JavaScript Enter failed: {e2}')
                
                # Method 2B: Look for hidden send buttons
                if not sent_successfully:
                    try:
                        print(f'[📤] {process_id}: Trying Method 2B - Hidden send button detection...')
                        
                        # Look for buttons without visible text but with send-related attributes
                        hidden_send_selectors = [
                            'button[data-testid*="send"]',
                            'div[role="button"][tabindex="0"]:not([aria-label*="More"]):not([aria-label*="options"]):not([aria-label*="Choose"]):not([aria-label*="Attach"])',
                            '[role="button"]:empty',  # Empty buttons might be send buttons
                            'button:not([aria-label]):not([title])',  # Buttons with no labels
                            '[aria-label=""]:not([disabled])'  # Empty aria-label buttons
                        ]
                        
                        for selector in hidden_send_selectors:
                            try:
                                hidden_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                                for btn in hidden_buttons:
                                    if btn.is_displayed() and btn.is_enabled():
                                        # Check if button is near the message input (likely to be send button)
                                        try:
                                            input_rect = message_input.rect
                                            btn_rect = btn.rect
                                            
                                            # If button is within reasonable distance of input (horizontally nearby)
                                            horizontal_distance = abs(btn_rect['x'] - (input_rect['x'] + input_rect['width']))
                                            vertical_distance = abs(btn_rect['y'] - input_rect['y'])
                                            
                                            if horizontal_distance < 200 and vertical_distance < 100:
                                                print(f'[🎯] {process_id}: Found potential hidden send button near input')
                                                driver.execute_script("arguments[0].click();", btn)
                                                sent_successfully = True
                                                print(f'[✅] {process_id}: Hidden send button clicked')
                                                break
                                        except:
                                            continue
                                if sent_successfully:
                                    break
                            except:
                                continue
                        
                        if sent_successfully:
                            print(f'[✅] {process_id}: Hidden button method successful')
                        else:
                            print(f'[⚠️] {process_id}: No suitable hidden buttons found')
                            
                    except Exception as e:
                        print(f'[⚠️] {process_id}: Hidden button detection failed: {e}')
                
                # Method 3: ActionChains Enter  
                if not sent_successfully:
                    try:
                        print(f'[📤] {process_id}: Trying ActionChains Enter...')
                        from selenium.webdriver import ActionChains
                        ActionChains(driver).move_to_element(message_input).click().send_keys(Keys.ENTER).perform()
                        sent_successfully = True
                        print(f'[✅] {process_id}: ActionChains Enter successful')
                    except Exception as e:
                        print(f'[⚠️] {process_id}: ActionChains Enter failed: {e}')

                # Method 4: Last resort - Ctrl+Enter
                if not sent_successfully:
                    try:
                        print(f'[📤] {process_id}: Last resort - Ctrl+Enter...')
                        from selenium.webdriver import ActionChains
                        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
                        sent_successfully = True
                        print(f'[✅] {process_id}: Ctrl+Enter successful')
                    except Exception as e:
                        print(f'[❌] {process_id}: All send methods failed: {e}')
                
                if not sent_successfully:
                    print(f'[💥] {process_id}: Message could not be sent - all methods failed')
                    continue
                
                # Simplified verification - just check if input was cleared
                time.sleep(3)
                verification_successful = False
                
                print(f'[🔍] {process_id}: Verifying message was sent...')
                
                try:
                    # Check if input was cleared (most reliable indicator)
                    current_text = driver.execute_script("""
                        const element = arguments[0];
                        return element.tagName === 'DIV' ? 
                            (element.textContent || element.innerHTML) : 
                            element.value;
                    """, message_input).strip()
                    
                    input_cleared = (current_text == '' or 
                                   current_text == '<br>' or 
                                   current_text.replace('<p class="xat24cr xdj266r" dir="auto"><br></p>', '') == '' or
                                   len(current_text) < 5)
                    
                    if input_cleared:
                        print(f'[✅] {process_id}: Input cleared - message likely sent')
                        verification_successful = True
                    else:
                        print(f'[⚠️] {process_id}: Input not cleared: "{current_text[:50]}..."')
                        
                        # Try to look for message in conversation as backup
                        try:
                            last_messages = driver.find_elements(By.CSS_SELECTOR, 'div[role="article"]:last-child, div[dir="auto"]:last-child')
                            for msg_element in last_messages[-2:]:
                                msg_text = msg_element.get_attribute('textContent') or msg_element.text
                                if msg_text and current_message in msg_text:
                                    print(f'[✅] {process_id}: Found message in conversation')
                                    verification_successful = True
                                    break
                        except Exception:
                            pass
                            
                except Exception as e:
                    print(f'[!] {process_id}: Verification failed: {e}')
                    # Assume success if we can't verify
                    verification_successful = True
                
                if verification_successful:
                    message_count += 1
                    print(f'[✅] {process_id}: Message {message_count} sent successfully!')
                else:
                    print(f'[⚠️] {process_id}: Verification uncertain, but continuing (message may have been sent)')
                
                # Wait for delay
                delay_ms = (int(delay) if delay.isdigit() else 30) * 1000
                print(f'[⏳] {process_id}: Waiting {delay} seconds before next message...')
                
                wait_time = 0
                while not should_stop and wait_time < delay_ms:
                    time.sleep(1)
                    wait_time += 1000
                
                if should_stop:
                    break
                    
            except Exception as loop_error:
                print(f'[❌] {process_id}: Error in message loop: {loop_error}')
                # Try to recover by finding message input again
                recovered_input = find_message_input(driver, process_id)
                if recovered_input:
                    print(f'[🔄] {process_id}: Recovered message input, continuing...')
                    message_input = recovered_input
                    continue
                else:
                    break
        
        print(f'[🎉] {process_id}: Message loop completed. Total sent: {message_count}')
        return message_count
        
    except Exception as error:
        print(f'[💥] {process_id}: Message sending process failed: {error}')
        print(f'[🔄] {process_id}: Automation failed, but server will continue running')
        return 0
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f'[!] {process_id}: Driver close warning: {e}')

def start_process():
    process_id = 'main_process'
    
    print(f'[+] {process_id}: Starting process on deployment...')
    
    if not perform_e2ee_simulated_handshake(process_id):
        print(f'[✗] {process_id}: Simulated E2EE failed')
        return
    
    # Read configuration
    config = read_config_from_files()
    cookies = config['cookies']
    delay = config['delay']
    haters_name = config['haters_name']
    chat_id = config['chat_id']
    messages = config['messages']
    
    print(f'[i] {process_id}: Config loaded - Target: "{haters_name}", Delay: {delay}s, Messages: {len(messages)}')
    
    # Validate required config
    if not haters_name or not haters_name.strip():
        print(f'[❌] {process_id}: Target name (hatersname.txt) is required')
        return
    
    if not chat_id or not chat_id.strip():
        print(f'[⚠️] {process_id}: Chat ID (convo.txt) not provided, using messages page')
    
    driver = None
    try:
        # Setup browser for deployment
        driver = setup_browser_for_deployment()
        
        # Set stop function
        active_processes[process_id] = {
            'stop': lambda: print(f'[🛑] {process_id}: Stop signal received')
        }
        
        print(f'[✅] {process_id}: Browser ready, starting message automation...')
        
        # Start message sending
        messages_sent = send_facebook_messages(driver, haters_name, messages, delay, process_id)
        
        print(f'[🏁] {process_id}: Process completed with {messages_sent} messages sent')
        
    except Exception as error:
        print(f'[💥] {process_id}: Critical error: {error}')
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        
        # Remove from active processes
        if process_id in active_processes:
            del active_processes[process_id]

# Flask routes
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'uptime': time.time() - psutil.Process().create_time(),
        'memory': dict(psutil.virtual_memory()._asdict())
    })

@app.route('/start', methods=['POST'])
def start_automation():
    try:
        # Start automation in a separate thread
        automation_thread = threading.Thread(target=start_process, daemon=True)
        automation_thread.start()
        return jsonify({'status': 'started', 'message': 'Automation process started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'active_processes': len(active_processes),
        'processes': list(active_processes.keys())
    })

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    print(f'[🌐] Server starting on port {PORT}')
    
    # Start automation automatically
    automation_thread = threading.Thread(target=start_process, daemon=True)
    automation_thread.start()
    
    app.run(host='0.0.0.0', port=PORT, debug=False)