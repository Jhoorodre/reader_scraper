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
from flaresolverr_client import FlareSolverrClient

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables to store the driver instance and browser mode
driver = None
browser_mode_selected = None

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
            
            driver = await uc.start(
                headless=headless_mode,
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

async def handle_legacy_turnstile_challenge(page):
    """Handle Cloudflare Turnstile challenge specifically (versão original para fallback)"""
    logger.info("Attempting to handle Turnstile challenge (legacy)...")
    
    try:
        # Wait for turnstile elements to load
        await asyncio.sleep(3)
        
        # Enhanced Turnstile detection and interaction with checkbox focus
        turnstile_handled = await page.evaluate("""
            (() => {
                console.log('[Turnstile] Starting enhanced challenge detection...');
                
                // Function to simulate human-like click with proper events
                function simulateHumanClick(element) {
                    const rect = element.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    
                    // Sequence of events that mimic human interaction
                    const events = [
                        new MouseEvent('mouseenter', { clientX: centerX, clientY: centerY, bubbles: true }),
                        new MouseEvent('mouseover', { clientX: centerX, clientY: centerY, bubbles: true }),
                        new MouseEvent('mousemove', { clientX: centerX - 1, clientY: centerY - 1, bubbles: true }),
                        new MouseEvent('mousemove', { clientX: centerX, clientY: centerY, bubbles: true }),
                        new MouseEvent('mousedown', { clientX: centerX, clientY: centerY, bubbles: true, button: 0 }),
                        new MouseEvent('focus', { bubbles: true }),
                        new MouseEvent('mouseup', { clientX: centerX, clientY: centerY, bubbles: true, button: 0 }),
                        new MouseEvent('click', { clientX: centerX, clientY: centerY, bubbles: true, button: 0 })
                    ];
                    
                    // Dispatch events with small delays
                    events.forEach((event, index) => {
                        setTimeout(() => element.dispatchEvent(event), index * 50);
                    });
                }
                
                // Strategy 1: Look for Turnstile checkbox specifically
                const checkboxSelectors = [
                    'iframe[src*="challenges.cloudflare.com"] input[type="checkbox"]',
                    'iframe[src*="turnstile"] input[type="checkbox"]',
                    '.cf-turnstile input[type="checkbox"]',
                    '[data-sitekey] input[type="checkbox"]',
                    'input[type="checkbox"][data-cf]'
                ];
                
                for (const selector of checkboxSelectors) {
                    const checkboxes = document.querySelectorAll(selector);
                    if (checkboxes.length > 0) {
                        console.log(`[Turnstile] Found checkbox via: ${selector}`);
                        for (const checkbox of checkboxes) {
                            if (!checkbox.checked) {
                                console.log('[Turnstile] Clicking unchecked checkbox');
                                checkbox.focus();
                                simulateHumanClick(checkbox);
                                return true;
                            }
                        }
                    }
                }
                
                // Strategy 2: Look for Turnstile iframes and try to access their content
                const iframes = document.querySelectorAll('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]');
                console.log(`[Turnstile] Found ${iframes.length} potential turnstile iframes`);
                
                for (const iframe of iframes) {
                    try {
                        console.log('[Turnstile] Attempting to interact with iframe...');
                        
                        // Scroll iframe into view
                        iframe.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        
                        // Wait a bit for scroll
                        setTimeout(() => {
                            simulateHumanClick(iframe);
                        }, 200);
                        
                        // Try to access iframe content if possible
                        try {
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                            if (iframeDoc) {
                                const iframeCheckbox = iframeDoc.querySelector('input[type="checkbox"]');
                                if (iframeCheckbox && !iframeCheckbox.checked) {
                                    console.log('[Turnstile] Found checkbox inside iframe');
                                    iframeCheckbox.focus();
                                    simulateHumanClick(iframeCheckbox);
                                    return true;
                                }
                            }
                        } catch (e) {
                            console.log('[Turnstile] Cannot access iframe content (CORS):', e.message);
                        }
                        
                        return true;
                    } catch (e) {
                        console.log('[Turnstile] Error with iframe:', e);
                    }
                }
                
                // Strategy 3: Look for Turnstile containers
                const turnstileSelectors = [
                    '.cf-turnstile',
                    '[data-sitekey]',
                    '.cloudflare-turnstile',
                    'div[data-callback]',
                    '#turnstile-wrapper',
                    '.turnstile-container'
                ];
                
                for (const selector of turnstileSelectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        console.log(`[Turnstile] Found turnstile container: ${selector}`);
                        
                        for (const element of elements) {
                            // Scroll into view
                            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            
                            // Look for clickable elements
                            const clickables = element.querySelectorAll('input[type="checkbox"], button, [role="button"], div[tabindex], span[tabindex]');
                            for (const clickable of clickables) {
                                try {
                                    console.log('[Turnstile] Clicking turnstile element');
                                    clickable.focus();
                                    simulateHumanClick(clickable);
                                    return true;
                                } catch (e) {
                                    console.log('[Turnstile] Click failed:', e);
                                }
                            }
                            
                            // If no specific clickables, try the container itself
                            try {
                                console.log('[Turnstile] Clicking container itself');
                                simulateHumanClick(element);
                                return true;
                            } catch (e) {
                                console.log('[Turnstile] Container click failed:', e);
                            }
                        }
                    }
                }
                
                // Strategy 4: Generic challenge elements
                const challengeSelectors = [
                    '.challenge-form input[type="checkbox"]',
                    '.cf-challenge input[type="checkbox"]',
                    '#challenge-stage input[type="checkbox"]',
                    '.cf-wrapper input[type="checkbox"]',
                    '.cf-wrapper button',
                    'button[data-action*="challenge"]'
                ];
                
                for (const selector of challengeSelectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        console.log(`[Turnstile] Found challenge element: ${selector}`);
                        for (const element of elements) {
                            try {
                                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                element.focus();
                                simulateHumanClick(element);
                                return true;
                            } catch (e) {
                                console.log('[Turnstile] Challenge element click failed:', e);
                            }
                        }
                    }
                }
                
                console.log('[Turnstile] No turnstile elements found or all interactions failed');
                return false;
            })()
        """)
        
        if turnstile_handled:
            logger.info("Turnstile interaction completed, waiting for resolution...")
            await asyncio.sleep(12)  # Aguardar resolução (aumentado de 5 para 12)
            return True
        else:
            logger.info("No Turnstile elements found or interaction failed")
            return False
            
    except Exception as e:
        logger.error(f"Error handling Turnstile: {e}")
        return False

# Function to wait for Cloudflare
async def wait_for_cloudflare(page, max_wait=60):
    """Wait for Cloudflare challenge to complete with enhanced Turnstile support"""
    logger.info("Checking for Cloudflare challenge...")
    
    start_time = time.time()
    cf_detected = False
    turnstile_attempts = 0
    max_turnstile_attempts = 3
    
    while time.time() - start_time < max_wait:
        try:
            # Check page title
            title = await page.evaluate("document.title")
            
            # Check for Cloudflare indicators
            if any(indicator in title.lower() for indicator in ['just a moment', 'cloudflare', 'checking']):
                cf_detected = True
                logger.info(f"Cloudflare detected in title: {title}")
                
            # Check page content for Cloudflare and Turnstile
            content = await page.evaluate("document.body ? document.body.innerText : ''")
            if any(indicator in content.lower() for indicator in ['checking your browser', 'please wait', 'cloudflare', 'turnstile']):
                cf_detected = True
                logger.info("Cloudflare/Turnstile detected in content")
                
            # Check for Turnstile-specific elements
            has_turnstile = await page.evaluate("""
                (() => {
                    const turnstileSelectors = [
                        'iframe[src*="challenges.cloudflare.com"]',
                        'iframe[src*="turnstile"]',
                        '.cf-turnstile',
                        '[data-sitekey]'
                    ];
                    
                    for (const selector of turnstileSelectors) {
                        if (document.querySelector(selector)) {
                            return true;
                        }
                    }
                    return false;
                })()
            """)
            
            if has_turnstile and turnstile_attempts < max_turnstile_attempts:
                logger.info(f"Turnstile detected, attempting new interaction (attempt {turnstile_attempts + 1})")
                
                # Try new enhanced method first
                success = await handle_turnstile_challenge(page)
                if not success:
                    logger.info("Enhanced method failed, trying legacy method...")
                    success = await handle_legacy_turnstile_challenge(page)
                
                turnstile_attempts += 1
                cf_detected = True
                
            # If no Cloudflare detected and page has content, we're done
            if not cf_detected:
                body_html = await page.evaluate("document.body ? document.body.innerHTML.length : 0")
                if body_html > 1000:  # Page has substantial content
                    logger.info("Page loaded successfully, no Cloudflare detected")
                    return True
                    
            # If Cloudflare was detected, wait for it to clear
            if cf_detected:
                current_url = await page.evaluate("window.location.href")
                if 'challenge' not in current_url and 'cloudflare' not in title.lower():
                    # Check if page has real content now
                    body_html = await page.evaluate("document.body ? document.body.innerHTML.length : 0")
                    if body_html > 1000:
                        logger.info("Cloudflare challenge completed")
                        return True
                        
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.debug(f"Error checking Cloudflare status: {e}")
            await asyncio.sleep(2)
            
    logger.warning(f"Cloudflare wait timeout after {max_wait} seconds")
    return not cf_detected

# Async scraper function with FlareSolverr fallback
async def scraper(url, max_retries=3):
    global driver
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Ensure that the driver is started
            await start_driver()

            # Navigate to the URL
            logger.info(f"Navigating to: {url}")
            page = await driver.get(url)
            
            # Lidar com termos e Turnstile usando abordagem simplificada
            await handle_turnstile_and_terms(page, url)
            
            # Try to scroll to trigger lazy loading
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, 0)")
                logger.info("Scrolled page to trigger content loading")
            except:
                pass
            
            # Wait for specific content if on chapter page
            if '/capitulo/' in url:
                logger.info("Chapter page detected, waiting for images...")
                try:
                    # Wait for at least one image to load
                    await page.wait_for('img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]', timeout=20)  # Timeout aumentado de 10 para 20
                    logger.info("Images detected on page")
                except:
                    logger.warning("Timeout waiting for images")
                    # Aguardar mais um pouco mesmo se não encontrar imagens
                    await asyncio.sleep(5)
            
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
            
            # Reset driver after successful request to avoid session issues
            try:
                if driver:
                    await driver.stop()
                    driver = None
                    logger.info("Driver reset after successful request")
            except Exception as reset_error:
                logger.debug(f"Error resetting driver: {reset_error}")
                driver = None
            
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
                logger.info("Primary method failed completely, trying FlareSolverr fallback...")
                try:
                    fallback_result = await try_flaresolverr_fallback(url)
                    if fallback_result:
                        logger.info("FlareSolverr fallback successful!")
                        return fallback_result
                    else:
                        logger.error("FlareSolverr fallback also failed")
                except Exception as fallback_error:
                    logger.error(f"FlareSolverr fallback error: {fallback_error}")
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

# Helper function to run async functions in a thread
def run_async(func, *args):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(func(*args))
    except Exception as e:
        logger.error(f"Error in run_async: {str(e)}")
        raise

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        logger.info(f"Scraping URL: {url}")
        html_content = run_async(scraper, url)
        
        if html_content:
            return jsonify({
                "url": url, 
                "html": html_content,
                "length": len(html_content),
                "success": True
            })
        else:
            raise Exception("Scraper returned empty content")
            
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        return jsonify({
            "error": "Scraping failed",
            "details": str(e),
            "url": url,
            "success": False
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "driver": "active" if driver else "inactive"
    })

@app.route('/reset', methods=['POST'])
def reset_driver():
    """Reset the driver instance"""
    global driver
    try:
        if driver:
            run_async(driver.stop)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3333)