from flask import Flask, request, jsonify
import nodriver as uc
import asyncio
import threading
import logging
import time
import json
import os
import subprocess
import platform
import sys
import shutil
import tempfile
import glob
from flaresolverr_client import FlareSolverrClient

# Add test directory to path for cf_bypass import
sys.path.append(os.path.join(os.path.dirname(__file__), 'test'))
from cf_bypass import CFBypass

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables to store the driver instance and browser mode
driver = None
browser_mode_selected = None

# Global variables for chapter session tracking
last_chapter_url = None
chapter_session_count = 0
MAX_CHAPTER_SESSION = 3  # Reset driver after 3 chapters

# Health monitoring for hanging detection
last_successful_request = None
consecutive_timeouts = 0
MAX_CONSECUTIVE_TIMEOUTS = 3

# Concurrency control aprimorado
import threading
import queue
from datetime import datetime, timedelta

request_lock = threading.Lock()
active_requests = {}  # Track active requests by URL
request_queue = queue.Queue(maxsize=10)  # Limit queue size
max_concurrent_requests = 1  # Process one request at a time for stability

# Rate limiting melhorado
last_request_time = None
min_request_interval = 2.0  # Minimum 2 seconds between requests

# Health monitoring
server_start_time = datetime.now()
request_count = 0
error_count = 0

# Função para minimizar janela do Chrome automaticamente
async def minimize_chrome_window():
    """Minimiza todas as janelas do Chrome automaticamente"""
    try:
        if platform.system() == "Windows":
            # PowerShell para minimizar janelas do Chrome
            powershell_cmd = """
            Add-Type -AssemblyName System.Windows.Forms
            $chromeWindows = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -ne ""}
            foreach($window in $chromeWindows) {
                $handle = $window.MainWindowHandle
                [System.Windows.Forms.SendKeys]::SendWait("%{F9}")
            }
            """
            subprocess.run(["powershell", "-Command", powershell_cmd], capture_output=True)
            logger.info("🔽 Janelas do Chrome minimizadas automaticamente")
        else:
            # Linux/Mac - usar wmctrl se disponível
            subprocess.run(["wmctrl", "-a", "chrome", "-b", "add,minimized"], capture_output=True)
            logger.info("🔽 Janela do Chrome minimizada (Linux)")
    except Exception as e:
        logger.debug(f"Não foi possível minimizar automaticamente: {e}")
        # Não é crítico, continua funcionando

# Function to start the driver (only once)
async def start_driver():
    global driver, browser_mode_selected
    try:
        if driver is None:
            logger.info("Starting driver...")
            
            # ===== CONFIGURAÇÃO DE MODO =====
            # OPÇÃO 1: Janela normal (visível)
            # OPÇÃO 2: Janela minimizada automaticamente
            # OPÇÃO 3: Headless (pode não funcionar com Turnstile)
            
            # Só pedir seleção do modo se não foi selecionado ainda
            if browser_mode_selected is None:
                # Verificar se há modo definido no .env primeiro
                env_browser_mode = os.getenv('BROWSER_MODE')
                if env_browser_mode and env_browser_mode in ['1', '2', '3']:
                    browser_mode_selected = env_browser_mode
                    logger.info(f"💾 Modo carregado do .env: {browser_mode_selected}")
                else:
                    browser_mode_selected = input("Escolha o modo do navegador:\n1 - Normal (visível)\n2 - Minimizado automaticamente\n3 - Headless\nOpção (1-3): ").strip()
                    logger.info(f"💾 Modo selecionado: {browser_mode_selected} (será usado para todas as próximas requisições)")
            else:
                logger.info(f"🔄 Reutilizando modo selecionado: {browser_mode_selected}")
            
            if browser_mode_selected == "3":
                headless_mode = True
                auto_minimize = False
                logger.info("🔍 Modo HEADLESS ativado")
            elif browser_mode_selected == "2":
                headless_mode = False
                auto_minimize = True
                logger.info("🔽 Modo MINIMIZADO ativado")
            else:
                headless_mode = False
                auto_minimize = False
                logger.info("👁️ Modo NORMAL ativado")
            
            logger.info(f"Starting driver in {'headless' if headless_mode else 'visual'} mode...")
            
            # Configuração baseada no modo selecionado
            if auto_minimize:
                # Modo minimizado: janela pequena
                window_args = [
                    '--window-size=400,300',  # Janela pequena
                    '--window-position=0,0'   # Canto superior
                ]
            else:
                # Modo normal: tela completa
                window_args = [
                    '--start-maximized',      # Maximizado
                    '--window-size=1920,1080' # Tela cheia como fallback
                ]
            
            # Detectar Chrome automaticamente no Windows
            chrome_path = None
            if platform.system() == "Windows":
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
                ]
                
                for path in chrome_paths:
                    if os.path.exists(path):
                        chrome_path = path
                        logger.info(f"🔍 Chrome encontrado em: {chrome_path}")
                        break
                
                if not chrome_path:
                    logger.warning("⚠️ Chrome não encontrado nos caminhos padrão")
            
            driver = await uc.start(
                headless=headless_mode,
                browser_executable_path=chrome_path,
                browser_args=[
                    '--disable-blink-features=AutomationControlled',  # Anti-detecção BOT
                    '--no-sandbox',  # Necessário para VPS
                    '--disable-dev-shm-usage',  # Para containers/VPS
                    '--disable-extensions',  # Remove extensões
                    '--disable-infobars',  # Remove barras de info
                    '--disable-notifications',  # Remove notificações
                    '--disable-default-apps'  # Remove apps padrão
                ] + window_args
            )
            logger.info("Driver started successfully")
            
            # Minimizar janela automaticamente se selecionado
            if auto_minimize and not headless_mode:
                await asyncio.sleep(3)
                await minimize_chrome_window()
    except Exception as e:
        logger.error(f"Error starting driver: {str(e)}")
        raise

# Function to handle SussyToons terms modal
async def handle_sussytoons_terms(page):
    """Handle SussyToons terms of service modal with enhanced detection"""
    logger.info("Checking for SussyToons terms modal...")
    
    try:
        # Wait longer for modal to appear
        await asyncio.sleep(3)
        
        # Check if we're on sussytoons
        current_url = await page.evaluate("window.location.href")
        if 'sussytoons' not in current_url.lower():
            return False
        
        # Enhanced JavaScript approach with multiple strategies
        terms_handled = await page.evaluate("""
            (() => {
                console.log('[Terms] Starting terms detection...');
                
                // Strategy 1: Look for common terms/modal patterns
                const modalSelectors = [
                    '.chakra-modal__content',
                    '.modal',
                    '[role="dialog"]',
                    '.modal-content',
                    '.terms-modal',
                    '.modal-body'
                ];
                
                let foundModal = null;
                for (const selector of modalSelectors) {
                    const modals = document.querySelectorAll(selector);
                    if (modals.length > 0) {
                        console.log(`[Terms] Found modal via: ${selector}`);
                        foundModal = modals[0];
                        break;
                    }
                }
                
                // Strategy 2: Look for accept buttons by text (expanded list)
                const acceptTexts = [
                    'aceito os termos', 'aceitar', 'accept', 'ok', 'concordo', 
                    'entendi', 'continuar', 'continue', 'proceed', 'agree',
                    'aceito', 'sim', 'yes', 'confirmar', 'confirm'
                ];
                
                const allButtons = document.querySelectorAll('button, a[role="button"], div[role="button"], span[role="button"]');
                console.log(`[Terms] Found ${allButtons.length} potential buttons`);
                
                for (const button of allButtons) {
                    const text = button.textContent.toLowerCase().trim();
                    const isVisible = button.offsetParent !== null;
                    
                    for (const acceptText of acceptTexts) {
                        if (text.includes(acceptText) && isVisible) {
                            console.log(`[Terms] Clicking button with text: "${text}"`);
                            
                            // Scroll into view and click
                            button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            
                            // Simulate human click
                            const rect = button.getBoundingClientRect();
                            const clickEvent = new MouseEvent('click', {
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2,
                                bubbles: true
                            });
                            button.dispatchEvent(clickEvent);
                            
                            // Also try direct click
                            button.click();
                            
                            return true;
                        }
                    }
                }
                
                // Strategy 3: If modal found, click first visible button
                if (foundModal) {
                    const modalButtons = foundModal.querySelectorAll('button');
                    console.log(`[Terms] Found ${modalButtons.length} buttons in modal`);
                    
                    for (const button of modalButtons) {
                        if (button.offsetParent !== null) {
                            console.log('[Terms] Clicking first visible modal button');
                            button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            button.click();
                            return true;
                        }
                    }
                }
                
                // Strategy 4: Force close modals and set acceptance
                console.log('[Terms] Attempting to force close modals...');
                
                // Set various acceptance cookies and localStorage
                const acceptanceData = [
                    { type: 'cookie', key: 'sussytoons-terms-accepted', value: 'true' },
                    { type: 'cookie', key: 'terms-accepted', value: 'true' },
                    { type: 'cookie', key: 'modal-dismissed', value: 'true' },
                    { type: 'localStorage', key: 'termsAccepted', value: 'true' },
                    { type: 'localStorage', key: 'sussytoons-terms', value: 'accepted' },
                    { type: 'localStorage', key: 'modalDismissed', value: 'true' }
                ];
                
                acceptanceData.forEach(item => {
                    try {
                        if (item.type === 'cookie') {
                            document.cookie = `${item.key}=${item.value}; path=/; max-age=31536000`;
                        } else {
                            localStorage.setItem(item.key, item.value);
                        }
                    } catch (e) {
                        console.log(`[Terms] Error setting ${item.type}: ${e.message}`);
                    }
                });
                
                // Remove modal overlays
                const overlaySelectors = [
                    '.chakra-modal__overlay',
                    '.modal-overlay',
                    '[data-modal]',
                    '.modal-backdrop',
                    '.overlay'
                ];
                
                overlaySelectors.forEach(selector => {
                    const overlays = document.querySelectorAll(selector);
                    overlays.forEach(overlay => {
                        try {
                            overlay.remove();
                        } catch (e) {}
                    });
                });
                
                // Enable scrolling
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
                
                // Remove modal-open classes
                document.body.classList.remove('modal-open');
                document.documentElement.classList.remove('modal-open');
                
                console.log('[Terms] Force close completed');
                return true;
            })()
        """)
        
        if terms_handled:
            logger.info("Terms handling completed successfully")
            await asyncio.sleep(3)  # Wait for page to update
            return True
        else:
            logger.warning("No terms modal found or handling failed")
            return False
            
    except Exception as e:
        logger.error(f"Error handling SussyToons terms: {e}")
        return False

# Funções simplificadas baseadas no simple_proxy.py que funciona
async def detect_challenges(page):
    """Detecta desafios Cloudflare e termos"""
    detection = await page.evaluate("""
        (() => {
            const result = {
                hasTerms: false,
                hasTurnstile: false,
                hasCloudflare: false,
                details: []
            };
            
            // Detectar termos
            const termsTexts = ['aceito os termos', 'terms of service', 'aceitar', 'termos'];
            const bodyText = document.body.innerText.toLowerCase();
            
            for (const term of termsTexts) {
                if (bodyText.includes(term)) {
                    result.hasTerms = true;
                    result.details.push(`Termos detectados: ${term}`);
                    break;
                }
            }
            
            // Detectar Turnstile
            const turnstileSelectors = [
                'iframe[src*="turnstile"]',
                'iframe[src*="challenges.cloudflare.com"]',
                '.cf-turnstile',
                '[data-sitekey]'
            ];
            
            for (const selector of turnstileSelectors) {
                if (document.querySelector(selector)) {
                    result.hasTurnstile = true;
                    result.details.push(`Turnstile detectado: ${selector}`);
                    break;
                }
            }
            
            // Detectar Cloudflare geral
            const cfIndicators = ['cloudflare', 'checking your browser', 'just a moment'];
            for (const indicator of cfIndicators) {
                if (bodyText.includes(indicator)) {
                    result.hasCloudflare = true;
                    result.details.push(`Cloudflare detectado: ${indicator}`);
                    break;
                }
            }
            
            return result;
        })()
    """)
    
    # Verificar se detection é válido
    if detection and isinstance(detection, dict):
        for detail in detection.get('details', []):
            logger.info(f"🔍 {detail}")
        return detection
    else:
        logger.warning("⚠️ Erro na detecção, usando detecção padrão")
        # Tentar obter URL atual
        try:
            current_url = await page.evaluate("window.location.href")
            has_terms = 'sussytoons' in current_url.lower()
        except:
            has_terms = False
            
        return {
            'hasTerms': has_terms,
            'hasTurnstile': False,
            'hasCloudflare': False,
            'details': ['Detecção simples ativada']
        }

async def handle_terms(page):
    """Lida com termos de serviço (versão simplificada do simple_proxy)"""
    logger.info("🔧 Tratando termos de serviço...")
    
    success = await page.evaluate("""
        (() => {
            // Procurar botões de aceitar
            const acceptTexts = ['aceito', 'aceitar', 'ok', 'continuar', 'accept', 'agree'];
            const buttons = document.querySelectorAll('button, a[role="button"]');
            
            for (const btn of buttons) {
                const text = btn.textContent.toLowerCase().trim();
                for (const acceptText of acceptTexts) {
                    if (text.includes(acceptText) && btn.offsetParent !== null) {
                        console.log(`Clicando botão: ${text}`);
                        btn.click();
                        return true;
                    }
                }
            }
            
            // Forçar cookies e localStorage
            document.cookie = 'terms-accepted=true; path=/; max-age=31536000';
            localStorage.setItem('termsAccepted', 'true');
            localStorage.setItem('sussytoons-terms', 'accepted');
            
            // Remover modais
            const modals = document.querySelectorAll('.modal, [role="dialog"], .chakra-modal__overlay');
            modals.forEach(modal => modal.remove());
            
            return true;
        })()
    """)
    
    if success:
        logger.info("✅ Termos tratados")
        await asyncio.sleep(3)
    
    return success

async def handle_turnstile(page):
    """Lida com Turnstile usando detecção avançada (versão do simple_proxy)"""
    logger.info("🎯 Tratando Turnstile...")
    
    for tentativa in range(3):
        logger.info(f"Tentativa {tentativa + 1}/3...")
        
        clicked = await page.evaluate("""
            (() => {
                // Método 1: Procurar iframes do Turnstile
                const iframes = document.querySelectorAll('iframe[src*="turnstile"], iframe[src*="challenges.cloudflare.com"]');
                
                for (const iframe of iframes) {
                    if (iframe.offsetParent !== null) {
                        console.log('Clicando iframe Turnstile');
                        
                        // Simular eventos humanos
                        const rect = iframe.getBoundingClientRect();
                        const centerX = rect.left + rect.width / 2;
                        const centerY = rect.top + rect.height / 2;
                        
                        const events = [
                            new MouseEvent('mousemove', {clientX: centerX-5, clientY: centerY-5, bubbles: true}),
                            new MouseEvent('mousemove', {clientX: centerX, clientY: centerY, bubbles: true}),
                            new MouseEvent('mousedown', {clientX: centerX, clientY: centerY, bubbles: true}),
                            new MouseEvent('mouseup', {clientX: centerX, clientY: centerY, bubbles: true}),
                            new MouseEvent('click', {clientX: centerX, clientY: centerY, bubbles: true})
                        ];
                        
                        events.forEach((event, index) => {
                            setTimeout(() => iframe.dispatchEvent(event), index * 100);
                        });
                        
                        return true;
                    }
                }
                
                // Método 2: Procurar containers Turnstile
                const containers = document.querySelectorAll('.cf-turnstile, [data-sitekey]');
                for (const container of containers) {
                    const checkbox = container.querySelector('input[type="checkbox"]');
                    if (checkbox && !checkbox.checked && checkbox.offsetParent !== null) {
                        console.log('Clicando checkbox Turnstile');
                        checkbox.focus();
                        checkbox.click();
                        return true;
                    }
                }
                
                // Método 3: Procurar qualquer checkbox não marcado
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                for (const cb of checkboxes) {
                    if (!cb.checked && cb.offsetParent !== null) {
                        console.log('Clicando checkbox genérico');
                        cb.click();
                        return true;
                    }
                }
                
                return false;
            })()
        """)
        
        if clicked:
            logger.info(f"✅ Turnstile clicado na tentativa {tentativa + 1}")
            await asyncio.sleep(15)  # Aguardar resolução (aumentado)
            return True
        
        await asyncio.sleep(2)
    
    logger.warning("⚠️ Turnstile não encontrado/clicado")
    return False

async def handle_turnstile_and_terms(page, url):
    """Lida com termos de serviço e Turnstile com detecção avançada (como no simple_proxy)"""
    logger.info("🔍 Verificando desafios...")
    
    # Aguardar carregamento inicial
    await asyncio.sleep(3)
    
    # Detectar desafios
    challenges = await detect_challenges(page)
    
    # Tratar termos se detectados
    if challenges.get('hasTerms', False):
        await handle_terms(page)
        await asyncio.sleep(2)
        # Re-detectar após tratar termos
        challenges = await detect_challenges(page)
    
    # Tratar Turnstile se detectado
    if challenges.get('hasTurnstile', False):
        await handle_turnstile(page)
        await asyncio.sleep(3)
    elif challenges.get('hasCloudflare', False):
        logger.info("🔄 Cloudflare detectado, aguardando resolução...")
        await asyncio.sleep(10)
    
    # Aguardar carregamento final
    await asyncio.sleep(8)

# Enhanced Turnstile challenge handler using CFBypass
async def handle_turnstile_challenge(page):
    """Handle Turnstile challenge using CFBypass"""
    try:
        logger.info("Starting enhanced Turnstile challenge handling with CFBypass")
        
        # Create CFBypass instance
        cf_bypass = CFBypass(page, debug=True)
        
        # Run the bypass
        success = await cf_bypass.bypass(
            max_retries=3,
            interval_between_retries=2,
            reload_page_after_n_retries=2
        )
        
        if success:
            logger.info("CFBypass successfully handled Turnstile challenge")
            return True
        else:
            logger.warning("CFBypass failed to handle Turnstile challenge")
            return False
            
    except Exception as e:
        logger.error(f"Error in enhanced Turnstile handling: {e}")
        return False

# Legacy Turnstile challenge handler (fallback)
async def handle_legacy_turnstile_challenge(page):
    """Legacy Turnstile challenge handler as fallback"""
    try:
        logger.info("Starting legacy Turnstile challenge handling")
        
        # Wait for Turnstile to load
        await asyncio.sleep(2)
        
        # Try to click Turnstile elements
        turnstile_clicked = await page.evaluate("""
            (() => {
                const turnstileSelectors = [
                    'iframe[src*="challenges.cloudflare.com"]',
                    'iframe[src*="turnstile"]',
                    '.cf-turnstile',
                    '[data-sitekey]',
                    'input[type="checkbox"]'
                ];
                
                for (const selector of turnstileSelectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        try {
                            element.click();
                            return true;
                        } catch (e) {
                            console.log('Click failed for', selector, e);
                        }
                    }
                }
                return false;
            })()
        """)
        
        if turnstile_clicked:
            logger.info("Turnstile element clicked, waiting for resolution...")
            await asyncio.sleep(3)
            return True
        else:
            logger.info("No Turnstile elements found to click")
            return False
            
    except Exception as e:
        logger.error(f"Error in legacy Turnstile handling: {e}")
        return False

# Simplified Function to wait for Cloudflare - ANTI-HANGING VERSION
async def wait_for_cloudflare(page, max_wait=60):
    """Simplified Cloudflare wait to prevent hanging"""
    logger.info("Checking for Cloudflare challenge...")
    
    start_time = time.time()
    check_count = 0
    max_checks = max_wait // 3  # Max checks every 3 seconds
    
    while time.time() - start_time < max_wait and check_count < max_checks:
        try:
            check_count += 1
            logger.debug(f"Cloudflare check {check_count}/{max_checks}")
            
            # Simple checks with timeouts
            try:
                title = await asyncio.wait_for(page.evaluate("document.title"), timeout=3)
                content_length = await asyncio.wait_for(
                    page.evaluate("document.body ? document.body.innerHTML.length : 0"), 
                    timeout=3
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout checking page state - assuming not ready")
                await asyncio.sleep(3)
                continue
            
            # Simple detection logic
            is_cf_page = any(indicator in title.lower() for indicator in ['just a moment', 'cloudflare', 'checking'])
            has_content = content_length > 2000
            
            if is_cf_page:
                logger.info(f"Cloudflare detected: {title}")
                await asyncio.sleep(5)  # Wait longer for CF to resolve
                continue
            elif has_content:
                logger.info("Page has sufficient content - assuming ready")
                return True
            else:
                logger.debug(f"Page loading... (content: {content_length} chars)")
                await asyncio.sleep(3)
                
        except Exception as e:
            logger.warning(f"Error in Cloudflare check: {e}")
            await asyncio.sleep(3)
            
    logger.info(f"Cloudflare wait completed after {time.time() - start_time:.1f}s")
    return True  # Assume success to avoid hanging

# Function to detect chapter changes and manage session - OTIMIZADO
def should_reset_driver_for_chapter(url):
    """Reset driver only when necessary to balance performance and reliability."""
    global last_chapter_url, chapter_session_count
    
    # Only apply to chapter URLs
    if '/capitulo/' not in url:
        return False, "Not a chapter URL"
        
    # Use the full URL as the chapter identifier
    current_chapter_url = url
    
    if last_chapter_url is None:
        # First chapter request - reset for clean start
        last_chapter_url = current_chapter_url
        chapter_session_count = 1
        return True, "First chapter request - clean start"
    
    if current_chapter_url != last_chapter_url:
        logger.info(f"New chapter detected. Old: {last_chapter_url}, New: {current_chapter_url}")
        last_chapter_url = current_chapter_url
        chapter_session_count = 1
        return True, f"New chapter detected: {current_chapter_url}"
    
    # Para o mesmo capítulo, resetar apenas a cada N tentativas para otimizar performance
    chapter_session_count += 1
    if chapter_session_count >= MAX_CHAPTER_SESSION:
        logger.info(f"Session limit reached ({chapter_session_count}/{MAX_CHAPTER_SESSION}) - resetting for cleanup")
        chapter_session_count = 0
        return True, f"Session limit reached - cleanup reset"
    
    # Não resetar para mesma URL se ainda não atingiu o limite
    return False, f"Reusing session ({chapter_session_count}/{MAX_CHAPTER_SESSION})"

# Function to clear browser cache and cookies
async def clear_browser_session(page):
    """Clear browser cache, cookies, and localStorage for clean session"""
    try:
        logger.info("🧹 Cleaning browser session...")
        
        # Clear localStorage and sessionStorage
        await page.evaluate("""
            (() => {
                try {
                    localStorage.clear();
                    sessionStorage.clear();
                    console.log('Storage cleared');
                } catch (e) {
                    console.log('Error clearing storage:', e);
                }
            })()
        """)
        
        # Clear cookies via JavaScript
        await page.evaluate("""
            (() => {
                try {
                    document.cookie.split(";").forEach(c => {
                        const eqPos = c.indexOf("=");
                        const name = eqPos > -1 ? c.substr(0, eqPos) : c;
                        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
                    });
                    console.log('Cookies cleared via JavaScript');
                } catch (e) {
                    console.log('Error clearing cookies:', e);
                }
            })()
        """)
        
        # Clear browser cache if supported
        try:
            await page.evaluate("""
                (() => {
                    if ('caches' in window) {
                        caches.keys().then(names => {
                            names.forEach(name => {
                                caches.delete(name);
                            });
                        });
                        console.log('Cache cleared');
                    }
                })()
            """)
        except:
            pass
        
        logger.info("✅ Browser session cleaned")
        await asyncio.sleep(1)  # Small delay for cleanup to complete
        
    except Exception as e:
        logger.warning(f"⚠️ Error cleaning browser session: {e}")
        # Not critical, continue anyway

# Async scraper function with FlareSolverr fallback and chapter session management
async def scraper(url, max_retries=3):
    global driver
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Check if we need to reset the driver for a new chapter
            should_reset, reset_reason = should_reset_driver_for_chapter(url)
            if should_reset:
                logger.info(f"🔄 Resetting driver: {reset_reason}")
                if driver:
                    await driver.stop()
                driver = None
            
            # Ensure that the driver is started
            await start_driver()

            # Navigate to the URL with timeout
            logger.info(f"Navigating to: {url}")
            try:
                page = await asyncio.wait_for(driver.get(url), timeout=30)
                logger.info("✅ Navigation completed successfully")
            except asyncio.TimeoutError:
                logger.error("❌ Navigation timed out after 30s - forcing driver reset")
                if driver:
                    await driver.stop()
                driver = None
                raise Exception("Navigation timeout - browser stuck")
            
            # Clear session for new chapters (if not reset driver) - LESS FREQUENT
            if not should_reset and '/capitulo/' in url and chapter_session_count % 5 == 0:
                await clear_browser_session(page)
            
            # First, handle the SussyToons specific terms modal
            await handle_sussytoons_terms(page)

            # Wait for Cloudflare and handle challenges with timeout
            logger.info("🛡️ Waiting for Cloudflare and handling challenges...")
            try:
                await asyncio.wait_for(
                    wait_for_cloudflare(page, max_wait=60), 
                    timeout=70  # Timeout maior que max_wait interno
                )
                logger.info("✅ Cloudflare wait completed successfully")
            except asyncio.TimeoutError:
                logger.error("❌ Cloudflare wait timed out after 70s - possible infinite loop")
                # Continue anyway but flag as potential issue
                pass
            
            # ===== DELAY CRÍTICO: Aguardar página carregar completamente =====
            logger.info("⏳ Aguardando página carregar completamente após bypass...")
            await asyncio.sleep(2)  # Reduced delay for synchronization
            
            # Verificar se a página carregou o conteúdo (com timeout)
            try:
                content_loaded = await asyncio.wait_for(
                    page.evaluate("""
                        (() => {
                            try {
                                const images = document.querySelectorAll('img');
                                const bodyContent = document.body ? document.body.innerHTML.length : 0;
                                return {
                                    imageCount: images.length,
                                    bodyLength: bodyContent,
                                    hasContent: bodyContent > 5000
                                };
                            } catch (e) {
                                console.log('Erro na verificação de conteúdo:', e);
                                return {
                                    imageCount: 0,
                                    bodyLength: 0,
                                    hasContent: false
                                };
                            }
                        })()
                    """), 
                    timeout=10  # Timeout de 10s para JavaScript evaluation
                )
                
                # Verificar se content_loaded é válido
                if content_loaded and isinstance(content_loaded, dict):
                    logger.info(f"📊 Conteúdo carregado: {content_loaded.get('imageCount', 0)} imagens, {content_loaded.get('bodyLength', 0)} chars")
                    
                    # Se não carregou, aguardar mais
                    if not content_loaded.get('hasContent', False):
                        logger.info("⏳ Conteúdo insuficiente, aguardando mais 5s...")
                        await asyncio.sleep(5)
                else:
                    logger.warning("⚠️ content_loaded é None ou inválido, continuando com valores padrão")
                    content_loaded = {'hasContent': False, 'imageCount': 0, 'bodyLength': 0}
                    logger.info("⏳ Aguardando 5s por precaução...")
                    await asyncio.sleep(5)
            
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout na verificação de conteúdo (10s) - possível travamento JavaScript")
                content_loaded = {'hasContent': False, 'imageCount': 0, 'bodyLength': 0}
                logger.info("⏳ Aguardando 3s após timeout...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"🔴 Erro na verificação de conteúdo: {e}")
                content_loaded = {'hasContent': False, 'imageCount': 0, 'bodyLength': 0}
                logger.info("⏳ Aguardando 3s após erro...")
                await asyncio.sleep(3)
            
            # Scroll inteligente inspirado no TypeScript
            try:
                logger.info("📜 Iniciando scroll inteligente para carregamento lazy...")
                
                # Primeira verificação: quantas imagens já temos? (com timeout)
                try:
                    initial_images = await asyncio.wait_for(
                        page.evaluate("""
                            () => {
                                const images = document.querySelectorAll('img.chakra-image.css-8atqhb');
                                return images.length;
                            }
                        """), 
                        timeout=5
                    )
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Timeout ao verificar imagens iniciais")
                    initial_images = 0
                
                logger.info(f"🖼️ Imagens iniciais detectadas: {initial_images}")
                
                # Se já temos imagens, scroll suave
                if initial_images and initial_images > 0:
                    logger.info("✅ Imagens já carregadas, fazendo scroll suave...")
                    # Scroll suave para baixo
                    await page.evaluate("""
                        () => {
                            window.scrollTo({
                                top: document.body.scrollHeight,
                                behavior: 'smooth'
                            });
                        }
                    """)
                    await asyncio.sleep(2)  # Tempo para smooth scroll
                    
                    # Scroll suave para cima
                    await page.evaluate("""
                        () => {
                            window.scrollTo({
                                top: 0,
                                behavior: 'smooth'
                            });
                        }
                    """)
                    await asyncio.sleep(1)  # Tempo para estabilizar
                    
                else:
                    logger.info("⚠️ Nenhuma imagem inicial, fazendo scroll progressivo...")
                    # Scroll progressivo para forçar carregamento
                    
                    # Primeiro: scroll por etapas
                    steps = 5
                    for i in range(steps):
                        scroll_position = (i + 1) * (100 / steps)
                        await page.evaluate(f"""
                            () => {{
                                const maxScroll = document.body.scrollHeight;
                                const targetScroll = maxScroll * {scroll_position / 100};
                                window.scrollTo(0, targetScroll);
                            }}
                        """)
                        await asyncio.sleep(0.5)  # Pausa pequena entre etapas
                        
                        # Verificar se carregou imagens
                        current_images = await page.evaluate("""
                            () => {
                                const images = document.querySelectorAll('img.chakra-image.css-8atqhb');
                                return images.length;
                            }
                        """)
                        
                        if current_images > 0:
                            logger.info(f"🖼️ {current_images} imagens carregadas na etapa {i+1}")
                            break
                    
                    # Volta ao topo suavemente
                    await page.evaluate("""
                        () => {
                            window.scrollTo({
                                top: 0,
                                behavior: 'smooth'
                            });
                        }
                    """)
                    await asyncio.sleep(1)
                
                # Verificação final
                final_images = await page.evaluate("""
                    () => {
                        const images = document.querySelectorAll('img.chakra-image.css-8atqhb');
                        return images.length;
                    }
                """)
                
                logger.info(f"✅ Scroll concluído. Imagens finais: {final_images}")
                
            except Exception as e:
                logger.warning(f"⚠️ Erro no scroll inteligente: {e}")
                # Fallback para scroll simples
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    await page.evaluate("window.scrollTo(0, 0)")
                    await asyncio.sleep(1)
                    logger.info("✅ Fallback scroll simples executado")
                except:
                    logger.error("🔴 Falha completa no scroll")
                    pass
            
            # Wait for specific content if on chapter page
            if '/capitulo/' in url:
                logger.info("Chapter page detected, waiting for images...")
                try:
                    # Wait for at least one image to load (inspirado no app.py)
                    await page.wait_for('img[src*=".jpg"], img[src*=".png"], img[src*=".webp"], img.chakra-image', timeout=20)
                    logger.info("Images detected on page")
                    
                    # Aguardar um pouco mais para garantir que todas as imagens carregaram
                    await asyncio.sleep(2)
                    
                    # Verificar quantas imagens temos agora
                    image_count = await page.evaluate("""
                        () => {
                            const images = document.querySelectorAll('img.chakra-image.css-8atqhb, img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]');
                            return images.length;
                        }
                    """)
                    
                    logger.info(f"📸 Total de imagens detectadas: {image_count}")
                    
                except:
                    logger.warning("Timeout waiting for images")
                    # Aguardar mais um pouco mesmo se não encontrar imagens
                    await asyncio.sleep(5)
                    
                    # Fazer uma verificação final
                    try:
                        final_count = await page.evaluate("""
                            () => {
                                const images = document.querySelectorAll('img.chakra-image.css-8atqhb, img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]');
                                return images.length;
                            }
                        """)
                        logger.info(f"🔍 Verificação final: {final_count} imagens encontradas")
                    except:
                        logger.warning("Erro na verificação final de imagens")
            
            # Get the full-page HTML    
            html_content = await page.get_content()
            
            # Validate content
            if len(html_content) < 1000:
                raise Exception(f"Page content too small: {len(html_content)} bytes")
                
            # Check if it's still a Cloudflare page
            if 'cloudflare' in html_content.lower() and len(html_content) < 5000:
                raise Exception("Still on Cloudflare challenge page")
            
            logger.info(f"Successfully retrieved {len(html_content)} bytes of content")
            
            # Debug: Save last successful scrape
            try:
                with open('last_successful_scrape.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
            except:
                pass
            
            # Don't reset driver after successful request anymore - let chapter management handle it
            # Reset driver after successful request to avoid session issues
            # try:
            #     if driver:
            #         await driver.stop()
            #         driver = None
            #         logger.info("Driver reset after successful request")
            # except Exception as reset_error:
            #     logger.debug(f"Error resetting driver: {reset_error}")
            #     driver = None
            
            return html_content
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Primary scraping method failed (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                logger.info(f"Retrying in {2 * retry_count} seconds...")
                await asyncio.sleep(2 * retry_count)
                
                # Reset driver on error
                try:
                    if driver:
                        await driver.stop()
                except:
                    pass
                driver = None
            else:
                # Try FlareSolverr as fallback if primary method fails completely
                logger.info("Primary method failed completamente, tentando fallback do FlareSolverr...")
                try:
                    fallback_result = await try_flaresolverr_fallback(url)
                    if fallback_result:
                        logger.info("Fallback do FlareSolverr bem-sucedido!")
                        return fallback_result
                    else:
                        logger.error("Fallback do FlareSolverr também falhou")
                except Exception as fallback_error:
                    logger.error(f"Erro no fallback do FlareSolverr: {fallback_error}")
                raise

# FlareSolverr fallback function
async def try_flaresolverr_fallback(url):
    """Try to use FlareSolverr as fallback when primary method fails"""
    try:
        with FlareSolverrClient() as flare_client:
            # Check if FlareSolverr is available
            if not flare_client.is_available():
                logger.warning("FlareSolverr is not available")
                return None
            
            logger.info("Using FlareSolverr to bypass Cloudflare...")
            
            # Get page using FlareSolverr
            result = flare_client.get_page(url, max_timeout=60000)
            
            if result.get("success"):
                html = result.get("html")
                if html and len(html) > 1000:
                    logger.info(f"FlareSolverr returned {len(html)} bytes of content")
                    
                    # Save successful FlareSolverr result
                    try:
                        with open('last_successful_scrape.html', 'w', encoding='utf-8') as f:
                            f.write(html)
                    except:
                        pass
                    
                    return html
                else:
                    logger.warning("FlareSolverr returned insufficient content")
                    return None
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"FlareSolverr failed: {error_msg}")
                return None
                
    except Exception as e:
        logger.error(f"Error in FlareSolverr fallback: {e}")
        return None

# Helper function to run async functions in a thread with timeout
def run_async(func, *args, timeout=30):
    """Run async function with timeout to prevent hanging"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Add timeout to prevent hanging
        future = asyncio.ensure_future(func(*args), loop=loop)
        return loop.run_until_complete(asyncio.wait_for(future, timeout=timeout))
    except asyncio.TimeoutError:
        logger.error(f"Timeout after {timeout}s in run_async for {func.__name__}")
        raise Exception(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error in run_async: {str(e)}")
        raise

@app.route('/scrape', methods=['GET'])
def scrape():
    global last_request_time, request_count, error_count, last_successful_request, consecutive_timeouts
    
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Rate limiting - força intervalo mínimo entre requests
    current_time = datetime.now()
    if last_request_time:
        time_since_last = (current_time - last_request_time).total_seconds()
        if time_since_last < min_request_interval:
            sleep_time = min_request_interval - time_since_last
            logger.info(f"⏳ Rate limiting: aguardando {sleep_time:.1f}s")
            time.sleep(sleep_time)
    
    last_request_time = datetime.now()
    request_count += 1

    # Concurrency control to ensure one request at a time
    with request_lock:
        # Check if this URL is already being processed
        if url in active_requests:
            return jsonify({
                "error": "Request already in progress",
                "details": f"URL {url} is being processed",
                "url": url,
                "success": False
            }), 429
        
        # Check concurrent request limit
        if len(active_requests) >= max_concurrent_requests:
            return jsonify({
                "error": "Too many concurrent requests",
                "details": f"Maximum {max_concurrent_requests} concurrent requests allowed",
                "url": url,
                "success": False
            }), 429
        
        # Mark this URL as active
        active_requests[url] = True

    try:
        logger.info(f"Scraping URL: {url} (Active: {len(active_requests)})")
        # Use timeout mais longo para scraping completo mas detecta travamento
        html_content = run_async(scraper, url, timeout=120)  # 2 minutos timeout
        
        if html_content:
            # Reset timeout counter on success
            consecutive_timeouts = 0
            last_successful_request = datetime.now()
            
            # Limpeza automática após scraping bem-sucedido
            try:
                cleanup_temp_files_internal()
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Erro na limpeza automática: {cleanup_error}")
            
            return jsonify({
                "url": url, 
                "html": html_content,
                "length": len(html_content),
                "success": True
            })
        else:
            raise Exception("Scraper returned empty content")
            
    except Exception as e:
        error_count += 1
        logger.error(f"Scraping failed: {str(e)}")
        
        # Track consecutive timeouts for hanging detection
        if "timeout" in str(e).lower():
            consecutive_timeouts += 1
            logger.warning(f"⏰ Consecutive timeouts: {consecutive_timeouts}/{MAX_CONSECUTIVE_TIMEOUTS}")
            
            # Force emergency restart if too many consecutive timeouts
            if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                logger.error("🚨 Too many consecutive timeouts - forcing emergency restart!")
                try:
                    # Emergency restart internally
                    emergency_restart()
                    consecutive_timeouts = 0  # Reset counter
                except Exception as restart_error:
                    logger.error(f"Emergency restart failed: {restart_error}")
        
        # Force reset driver on critical errors
        if "nodriver" in str(e).lower() or "chrome" in str(e).lower():
            logger.warning("🔄 Critical driver error detected, forcing reset...")
            try:
                if driver:
                    run_async(driver.stop, timeout=5)
                driver = None
            except:
                pass
        
        return jsonify({
            "error": "Scraping failed",
            "details": str(e),
            "url": url,
            "success": False,
            "error_count": error_count
        }), 500
    finally:
        # Always remove from active requests
        with request_lock:
            if url in active_requests:
                del active_requests[url]

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint com monitoramento avançado incluindo storage"""
    uptime = datetime.now() - server_start_time
    
    # Remover informações de storage para simplificar
    storage_info = None
        
    # Obter informações de temp directory
    temp_info = None
    try:
        temp_dir = tempfile.gettempdir()
        temp_files = len([f for f in os.listdir(temp_dir) 
                         if any(pattern in f.lower() for pattern in 
                               ['chrome', 'nodriver', 'cap', 'arquiteto', 'download_'])])
        temp_info = {
            "temp_dir": temp_dir,
            "suspicious_files": temp_files
        }
    except Exception as e:
        logger.debug(f"Erro ao obter info de temp: {e}")
    
    return jsonify({
        "status": "healthy",
        "driver": "active" if driver else "inactive",
        "uptime_seconds": int(uptime.total_seconds()),
        "total_requests": request_count,
        "error_count": error_count,
        "success_rate": f"{((request_count - error_count) / max(request_count, 1) * 100):.1f}%",
        "active_requests": len(active_requests),
        "queue_size": request_queue.qsize() if hasattr(request_queue, 'qsize') else 0,
        "memory_usage": "monitoring_available",
        "last_request": last_request_time.isoformat() if last_request_time else None,
        "storage": storage_info,
        "temp_files": temp_info
    })

@app.route('/reset', methods=['POST'])
def reset_driver():
    """Reset the driver instance"""
    global driver
    try:
        if driver is not None:
            try:
                run_async(driver.stop, timeout=10)  # ✅ CORRIGIDO - com timeout de 10s
            except Exception as stop_error:
                logger.warning(f"Erro ao parar driver: {stop_error}")
        driver = None
        return jsonify({"status": "Driver reset successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset-mode', methods=['POST'])
def reset_browser_mode():
    """Reset the browser mode selection"""
    global browser_mode_selected
    try:
        browser_mode_selected = None
        return jsonify({"status": "Browser mode selection reset - will prompt again on next driver start"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/session-status', methods=['GET'])
def session_status():
    """Get current session status"""
    global last_chapter_url, chapter_session_count, MAX_CHAPTER_SESSION
    return jsonify({
        "last_chapter_url": last_chapter_url,
        "chapter_session_count": chapter_session_count,
        "max_chapter_session": MAX_CHAPTER_SESSION,
        "driver_active": driver is not None
    })

@app.route('/reset-session', methods=['POST'])
def reset_session():
    """Reset chapter session tracking"""
    global last_chapter_url, chapter_session_count
    try:
        last_chapter_url = None
        chapter_session_count = 0
        return jsonify({"status": "Chapter session tracking reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/force-reset', methods=['POST'])
def force_reset_driver():
    """Force reset the driver for retry attempts"""
    global driver, last_chapter_url
    try:
        logger.info("🔄 Force resetting driver for retry...")
        if driver is not None:
            try:
                run_async(driver.stop, timeout=10)  # ✅ CORRIGIDO - com timeout de 10s
            except Exception as stop_error:
                logger.warning(f"Erro ao parar driver durante force reset: {stop_error}")
        driver = None
        last_chapter_url = None  # Reset chapter tracking
        
        return jsonify({
            "status": "Driver force reset successfully",
            "message": "Browser instance restarted for clean retry",
            "success": True
        })
    except Exception as e:
        logger.error(f"Error force resetting driver: {str(e)}")
        return jsonify({
            "error": f"Failed to force reset driver: {str(e)}",
            "success": False
        }), 500

# Endpoint para emergency restart
@app.route('/emergency-restart', methods=['POST'])
def emergency_restart():
    """Emergency restart - força reset completo do driver"""
    global driver, browser_mode_selected, last_chapter_url, chapter_session_count, error_count
    try:
        logger.warning("🚨 EMERGENCY RESTART - Resetando tudo...")
        
        # Force kill any hanging Chrome processes first
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if 'chrome' in proc.info['name'].lower():
                    try:
                        proc.kill()
                        logger.info(f"🔪 Killed hanging Chrome process: {proc.info['pid']}")
                    except:
                        pass
        except ImportError:
            # psutil not available, try system commands
            try:
                if platform.system() == "Windows":
                    subprocess.run("taskkill /f /im chrome.exe", shell=True, capture_output=True)
                    logger.info("🔪 Killed Chrome processes via taskkill")
                else:
                    subprocess.run("pkill -f chrome", shell=True, capture_output=True)
                    logger.info("🔪 Killed Chrome processes via pkill")
            except:
                logger.debug("Couldn't kill Chrome processes")
        
        # Reset driver with force timeout
        if driver is not None:
            try:
                run_async(driver.stop, timeout=5)  # Reduced timeout for emergency
            except Exception as stop_error:
                logger.warning(f"Erro ao parar driver durante emergency restart: {stop_error}")
                # Force None anyway
        driver = None
        
        # Reset session state  
        browser_mode_selected = None
        last_chapter_url = None
        chapter_session_count = 0
        error_count = 0
        
        # Clear active requests
        with request_lock:
            active_requests.clear()
            
        logger.info("✅ Emergency restart concluído")
        return jsonify({
            "status": "Emergency restart completed",
            "driver": "reset",
            "session": "cleared"
        })
        
    except Exception as e:
        logger.error(f"Error in emergency restart: {str(e)}")
        return jsonify({
            "error": f"Emergency restart failed: {str(e)}"
        }), 500

# Função interna de limpeza (sem endpoint)
def cleanup_temp_files_internal():
    """Limpeza automática interna após cada scraping"""
    try:
        # Detectar diretório temp correto para WSL/Windows
        def get_correct_temp_dir():
            import platform
            if platform.system() == 'Linux' and os.environ.get('WSL_DISTRO_NAME'):
                # WSL - tentar usar temp do Windows
                windows_temp_paths = [
                    '/mnt/c/Users/Admin/AppData/Local/Temp',
                    '/mnt/c/Windows/Temp'
                ]
                for temp_path in windows_temp_paths:
                    if os.path.exists(temp_path):
                        return temp_path
            return tempfile.gettempdir()
        
        temp_dir = get_correct_temp_dir()
        cleaned_count = 0
        total_size = 0
        
        # Padrões críticos para limpeza rápida após scraping
        critical_patterns = [
            'uc_*',           # Chrome undetected instances (maior problema)
            'nodriver_*',     # nodriver temporários
            'chrome_*',       # Chrome temporários  
            '*.tmp'           # Arquivos .tmp genéricos
        ]
        
        for pattern in critical_patterns:
            matching_files = glob.glob(os.path.join(temp_dir, pattern))
            
            for file_path in matching_files:
                try:
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        os.unlink(file_path)
                        total_size += file_size
                        cleaned_count += 1
                    elif os.path.isdir(file_path):
                        # Para diretórios uc_*, remover completamente
                        if os.path.basename(file_path).startswith('uc_'):
                            shutil.rmtree(file_path, ignore_errors=True)
                            cleaned_count += 1
                except Exception:
                    # Ignorar arquivos em uso silenciosamente
                    pass
        
        if cleaned_count > 0:
            size_mb = total_size / (1024 * 1024)
            logger.info(f"🧹 [AUTO-CLEANUP] Limpeza automática: {cleaned_count} itens ({size_mb:.1f}MB)")
        
        return cleaned_count, total_size
    except Exception:
        # Limpeza silenciosa - não interromper scraping por erro de limpeza
        return 0, 0

# Endpoint para limpeza de arquivos temporários MELHORADO
@app.route('/cleanup-temp', methods=['POST'])
def cleanup_temp_files():
    """Limpa arquivos temporários do Python e coordena com TypeScript"""
    try:
        logger.info("🧹 [PYTHON] Iniciando limpeza de arquivos temporários...")
        
        # Detectar diretório temp correto para WSL/Windows
        def get_correct_temp_dir():
            import platform
            if platform.system() == 'Linux' and os.environ.get('WSL_DISTRO_NAME'):
                # WSL - tentar usar temp do Windows
                windows_temp_paths = [
                    '/mnt/c/Users/Admin/AppData/Local/Temp',
                    '/mnt/c/Windows/Temp'
                ]
                for temp_path in windows_temp_paths:
                    if os.path.exists(temp_path):
                        return temp_path
            return tempfile.gettempdir()
        
        temp_dir = get_correct_temp_dir()
        cleaned_count = 0
        total_size = 0
        
        # Padrões expandidos e mais agressivos
        patterns = [
            'nodriver_*',
            'chrome_*', 
            'chromium*',
            'tmp*Cap*',
            '*Arquiteto*',
            '*.png',
            '*.jpg',
            '*.jpeg', 
            '*.webp',
            'download_*.jpg',
            'download_*.png', 
            'download_*.jpeg',
            'download_*.webp',
            '*cache*',
            '*Cache*',
            'scoped_dir*',
            'chrome-driver*',
            '*guid*.tmp',
            '*uuid*.tmp'
        ]
        
        # Primeiro, listar o que encontramos
        logger.info(f"🔍 [PYTHON] Verificando diretório: {temp_dir}")
        all_items = os.listdir(temp_dir)
        logger.info(f"📁 [PYTHON] Total de itens no temp: {len(all_items)}")
        
        for pattern in patterns:
            matching_files = glob.glob(os.path.join(temp_dir, pattern))
            logger.info(f"🎯 [PYTHON] Pattern '{pattern}': {len(matching_files)} matches")
            
            for file_path in matching_files:
                try:
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        os.unlink(file_path)
                        total_size += file_size
                        cleaned_count += 1
                    elif os.path.isdir(file_path):
                        # Calcular tamanho do diretório antes de remover
                        dir_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                     for dirpath, dirnames, filenames in os.walk(file_path)
                                     for filename in filenames)
                        shutil.rmtree(file_path, ignore_errors=True)
                        total_size += dir_size
                        cleaned_count += 1
                        
                except Exception as e:
                    if not (str(e).find('being used by another process') != -1 or 
                           str(e).find('EBUSY') != -1):
                        logger.warning(f"⚠️ [PYTHON] Não foi possível limpar {file_path}: {e}")
        
        size_mb = total_size / (1024 * 1024)
        logger.info(f"✅ [PYTHON] Limpeza concluída: {cleaned_count} itens ({size_mb:.2f}MB)")
        
        # Coordenação melhorada com TypeScript
        typescript_result = {"success": False, "details": "Not attempted"}
        try:
            logger.info("🔗 [PYTHON] Coordenando com TypeScript...")
            
            # Tentar múltiplas estratégias de coordenação
            strategies = [
                # Estratégia 1: Chamar diretamente a função
                ['npx', 'ts-node', '--transpileOnly', '-e', 
                 'import { cleanTempFiles, getCleanupStats } from "./src/utils/folder"; cleanTempFiles(); console.log("Cleanup stats:", JSON.stringify(getCleanupStats()));'],
                
                # Estratégia 2: Fallback simples
                ['npx', 'ts-node', '--transpileOnly', '-e', 
                 'const { cleanTempFiles } = require("./src/utils/folder"); cleanTempFiles();']
            ]
            
            for i, cmd in enumerate(strategies):
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, 
                                          timeout=45, cwd=os.path.dirname(__file__))
                    
                    if result.returncode == 0:
                        logger.info(f"✅ [PYTHON] Coordenação TypeScript (estratégia {i+1}) bem-sucedida")
                        if result.stdout:
                            logger.info(f"📊 [TYPESCRIPT] Output: {result.stdout.strip()}")
                        typescript_result = {"success": True, "strategy": i+1, "output": result.stdout}
                        break
                    else:
                        logger.warning(f"⚠️ [PYTHON] Estratégia {i+1} falhou: {result.stderr.strip()}")
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"⏰ [PYTHON] Estratégia {i+1} timeout")
                except Exception as strategy_error:
                    logger.warning(f"⚠️ [PYTHON] Estratégia {i+1} erro: {strategy_error}")
                    
        except Exception as coord_error:
            logger.warning(f"⚠️ [PYTHON] Falha geral na coordenação: {coord_error}")
        
        # Retornar estatísticas detalhadas
        return jsonify({
            "status": "Cleanup completed", 
            "python": {
                "cleaned": cleaned_count,
                "size_mb": round(size_mb, 2),
                "temp_dir": temp_dir,
                "patterns_checked": len(patterns)
            },
            "typescript": typescript_result,
            "success": True,
            "total_freed_mb": round(size_mb, 2)
        })
        
    except Exception as e:
        logger.error(f"💥 [PYTHON] Error in cleanup: {str(e)}")
        return jsonify({
            "error": f"Cleanup failed: {str(e)}",
            "success": False
        }), 500

@app.route('/scrape_lazy', methods=['GET'])
def scrape_lazy():
    """Endpoint para scraping com simulação de scroll para lazy loading"""
    url = request.args.get('url')
    scroll_count = int(request.args.get('scroll_count', 5))
    wait_time = int(request.args.get('wait_time', 2000))
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    logger.info(f"🔄 [LAZY] Iniciando scraping com lazy loading: {url}")
    logger.info(f"📜 [LAZY] Parâmetros: scroll_count={scroll_count}, wait_time={wait_time}ms")
    
    def run_lazy_scrape():
        try:
            with app.app_context():  # Adicionar contexto da aplicação Flask
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(scrape_with_lazy_loading(url, scroll_count, wait_time))
        except Exception as e:
            logger.error(f"❌ [LAZY] Erro no scraping: {str(e)}")
            return None
        finally:
            try:
                loop.close()
            except:
                pass
    
    # Executar em thread separada para evitar bloqueio
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            future = executor.submit(run_lazy_scrape)
            result = future.result(timeout=120)  # 2 minutos timeout
            
            if result is None:
                return jsonify({"error": "Failed to scrape content"}), 500
                
            return result
            
        except concurrent.futures.TimeoutError:
            logger.error("⏰ [LAZY] Timeout no scraping lazy")
            return jsonify({"error": "Scraping timeout"}), 504
        except Exception as e:
            logger.error(f"❌ [LAZY] Erro na execução: {str(e)}")
            return jsonify({"error": f"Execution error: {str(e)}"}), 500

async def scrape_with_lazy_loading(url, scroll_count=5, wait_time=2000):
    """Implementa scraping com scroll simulado para carregar lazy loading"""
    global driver, browser_mode_selected
    
    logger.info(f"🚀 [LAZY] Carregando página com lazy loading: {url}")
    
    try:
        # Garantir que temos um driver
        if driver is None:
            logger.info("🔧 [LAZY] Criando novo driver...")
            await start_driver()
        
        # Abrir nova aba ou reutilizar
        page = await driver.get(url, new_tab=True)
        logger.info(f"✅ [LAZY] Página carregada: {url}")
        
        # Aguardar carregamento inicial
        await asyncio.sleep(3)
        
        # Verificar se precisa lidar com proteções
        protection_status = await detect_protection(page)
        if protection_status.get('hasTerms') or protection_status.get('hasTurnstile'):
            logger.info("🛡️ [LAZY] Detectada proteção, tratando...")
            
            if protection_status.get('hasTerms'):
                await handle_terms(page)
            
            if protection_status.get('hasTurnstile'):
                await handle_turnstile(page)
                
            # Aguardar após tratar proteções
            await asyncio.sleep(3)
        
        # SCROLL INTELIGENTE PARA LAZY LOADING - vai até o final real da página
        logger.info(f"📜 [LAZY] Iniciando scroll inteligente ({scroll_count} tentativas, {wait_time}ms cada)")
        
        previous_height = 0
        for scroll_num in range(scroll_count):
            try:
                # Obter altura atual da página
                current_height = await page.evaluate("() => document.body.scrollHeight")
                
                # Se a altura não mudou nas últimas 3 tentativas, provavelmente chegamos ao fim
                if scroll_num > 3 and current_height == previous_height:
                    logger.info(f"📊 [LAZY] Página estável na altura {current_height}px após {scroll_num} scrolls")
                    # Fazer um último scroll forçado para garantir
                    await page.evaluate(f"() => window.scrollTo(0, {current_height})")
                    await asyncio.sleep(wait_time / 1000.0)
                    break
                
                # Scroll até o final ATUAL da página (que pode expandir)
                await page.evaluate(f"""
                    (() => {{
                        const currentScrollHeight = document.body.scrollHeight;
                        const windowHeight = window.innerHeight;
                        const scrollStep = Math.max(windowHeight, 500); // Pelo menos 500px por vez
                        const currentScroll = window.pageYOffset;
                        
                        // Scroll incremental para baixo
                        const newPosition = Math.min(currentScroll + scrollStep, currentScrollHeight);
                        
                        window.scrollTo({{
                            top: newPosition,
                            behavior: 'smooth'
                        }});
                        
                        // Se chegou no final, tentar scroll até o fim absoluto
                        if (newPosition >= currentScrollHeight - windowHeight) {{
                            setTimeout(() => {{
                                window.scrollTo(0, document.body.scrollHeight);
                            }}, 500);
                        }}
                        
                        // Disparar eventos de scroll
                        window.dispatchEvent(new Event('scroll'));
                        document.dispatchEvent(new Event('scroll'));
                        
                        console.log(`Scroll {scroll_num + 1}: {{currentScroll}} → {{newPosition}} (altura: {{currentScrollHeight}})`);
                        
                        return {{
                            currentScroll: currentScroll,
                            newPosition: newPosition,
                            scrollHeight: currentScrollHeight,
                            atBottom: newPosition >= currentScrollHeight - windowHeight
                        }};
                    }})()
                """)
                
                previous_height = current_height
                
                # Aguardar o carregamento
                await asyncio.sleep(wait_time / 1000.0)
                
                # Verificar quantas imagens foram carregadas
                try:
                    image_count = await page.evaluate("""
                        () => {
                            const images = document.querySelectorAll('img[src], img[data-src]');
                            const loaded = Array.from(images).filter(img => 
                                img.src && !img.src.includes('data:image') && 
                                (img.complete || img.naturalHeight > 0)
                            );
                            return {
                                total: images.length,
                                loaded: loaded.length
                            };
                        }
                    """)
                    
                    if image_count:
                        logger.info(f"📊 [LAZY] Scroll {scroll_num + 1}: {image_count['loaded']}/{image_count['total']} imagens carregadas")
                
                except Exception as e:
                    logger.warning(f"⚠️ [LAZY] Erro ao verificar imagens no scroll {scroll_num + 1}: {e}")
                
            except Exception as scroll_error:
                logger.warning(f"⚠️ [LAZY] Erro no scroll {scroll_num + 1}: {scroll_error}")
                continue
        
        # Scroll final garantido até o final absoluto da página
        logger.info("🔄 [LAZY] Fazendo scroll final até o final absoluto...")
        await page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    // Scroll para o final absoluto múltiplas vezes
                    let attempts = 0;
                    const maxAttempts = 5;
                    
                    function scrollToEnd() {
                        const currentHeight = document.body.scrollHeight;
                        window.scrollTo(0, currentHeight);
                        window.dispatchEvent(new Event('scroll'));
                        
                        attempts++;
                        console.log(`Scroll final ${attempts}/${maxAttempts}: altura ${currentHeight}px`);
                        
                        if (attempts < maxAttempts) {
                            setTimeout(scrollToEnd, 800);
                        } else {
                            // Um último scroll com delay para garantir
                            setTimeout(() => {
                                window.scrollTo(0, document.body.scrollHeight);
                                resolve();
                            }, 1000);
                        }
                    }
                    
                    scrollToEnd();
                });
            }
        """)
        
        # Aguardar processamento final
        await asyncio.sleep(2)
        
        # Obter HTML final com todas as imagens carregadas
        html_content = await page.get_content()
        
        # Estatísticas finais
        try:
            final_stats = await page.evaluate("""
                () => {
                    const allImages = document.querySelectorAll('img');
                    const loadedImages = Array.from(allImages).filter(img => 
                        img.src && !img.src.includes('data:image') && 
                        (img.complete || img.naturalHeight > 0)
                    );
                    
                    const lazyImages = document.querySelectorAll('img[data-src], img[data-lazy-src]');
                    
                    return {
                        totalImages: allImages.length,
                        loadedImages: loadedImages.length,
                        lazyImages: lazyImages.length,
                        bodyLength: document.body.innerHTML.length
                    };
                }
            """)
            
            logger.info(f"📊 [LAZY] Resultado final: {final_stats['loadedImages']}/{final_stats['totalImages']} imagens carregadas")
            logger.info(f"📊 [LAZY] Lazy images detectadas: {final_stats['lazyImages']}")
            
        except Exception as e:
            logger.warning(f"⚠️ [LAZY] Erro ao obter estatísticas finais: {e}")
            final_stats = {"totalImages": 0, "loadedImages": 0, "lazyImages": 0, "bodyLength": len(html_content)}
        
        # Fechar aba
        await page.close()
        
        logger.info(f"✅ [LAZY] Scraping com lazy loading concluído para: {url}")
        
        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
    except Exception as e:
        logger.error(f"❌ [LAZY] Erro no scraping com lazy loading: {str(e)}")
        try:
            if page:
                await page.close()
        except:
            pass
        
        # Tentar fallback sem lazy loading
        try:
            logger.info("🔄 [LAZY] Tentando fallback sem lazy loading...")
            simple_page = await driver.get(url, new_tab=True)
            await asyncio.sleep(5)
            fallback_content = await simple_page.get_content()
            await simple_page.close()
            return fallback_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        except Exception as fallback_error:
            logger.error(f"❌ [LAZY] Fallback também falhou: {fallback_error}")
            return jsonify({"error": f"Lazy loading failed: {str(e)}"}), 500

if __name__ == '__main__':
    try:
        logger.info("🚀 Iniciando servidor com melhorias anti-travamento...")
        app.run(debug=True, host='0.0.0.0', port=3333, threaded=True)
    except KeyboardInterrupt:
        logger.info("🛑 Servidor interrompido pelo usuário")
    except Exception as e:
        logger.error(f"💥 Erro crítico no servidor: {str(e)}")