#!/usr/bin/env python3
"""
Proxy simples focado apenas no bypass do Cloudflare Turnstile
"""
from flask import Flask, request, jsonify
import nodriver as uc
import asyncio
import logging
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
driver = None

async def start_driver():
    """Inicia o driver do Chrome"""
    global driver
    if driver is None:
        logger.info("Iniciando Chrome...")
        driver = await uc.start(headless=False)
        logger.info("Chrome iniciado com sucesso")

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
    """Lida com termos de serviço"""
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
    """Lida com Turnstile usando detecção avançada"""
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
            await asyncio.sleep(8)  # Aguardar resolução
            return True
        
        await asyncio.sleep(2)
    
    logger.warning("⚠️ Turnstile não encontrado/clicado")
    return False

async def handle_turnstile_and_terms(page, url):
    """Lida com termos de serviço e Turnstile com detecção avançada"""
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
    await asyncio.sleep(5)

async def scrape_page(url):
    """Scrape uma página lidando com Turnstile"""
    global driver
    
    try:
        await start_driver()
        
        logger.info(f"Navegando para: {url}")
        page = await driver.get(url)
        
        # Lidar com termos e Turnstile
        await handle_turnstile_and_terms(page, url)
        
        # Obter conteúdo final
        content = await page.get_content()
        
        logger.info(f"Página carregada: {len(content)} bytes")
        
        return content
        
    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        raise

@app.route('/scrape')
def scrape():
    """Endpoint para scraping"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL obrigatória"}), 400
    
    try:
        # Executar scraping
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        content = loop.run_until_complete(scrape_page(url))
        
        return jsonify({
            "success": True,
            "html": content,
            "length": len(content),
            "url": url
        })
        
    except Exception as e:
        logger.error(f"Erro: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "url": url
        }), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "ok", "driver": "active" if driver else "inactive"})

if __name__ == '__main__':
    print("🚀 Iniciando proxy simples para Turnstile...")
    print("📍 Acesse: http://localhost:3333/scrape?url=<URL>")

#!/usr/bin/env python3
"""
Proxy simples focado apenas no bypass do Cloudflare Turnstile
"""
from flask import Flask, request, jsonify
import nodriver as uc
import asyncio
import logging
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
driver = None

async def start_driver():
    """Inicia o driver do Chrome"""
    global driver
    if driver is None:
        logger.info("Iniciando Chrome...")
        driver = await uc.start(headless=False)
        logger.info("Chrome iniciado com sucesso")

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
    """Lida com termos de serviço"""
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
    """Lida com Turnstile usando detecção avançada"""
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
            await asyncio.sleep(8)  # Aguardar resolução
            return True
        
        await asyncio.sleep(2)
    
    logger.warning("⚠️ Turnstile não encontrado/clicado")
    return False

async def handle_turnstile_and_terms(page, url):
    """Lida com termos de serviço e Turnstile com detecção avançada"""
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
    await asyncio.sleep(5)

async def scrape_page(url):
    """Scrape uma página lidando com Turnstile"""
    global driver
    
    try:
        await start_driver()
        
        logger.info(f"Navegando para: {url}")
        page = await driver.get(url)
        
        # Lidar com termos e Turnstile
        await handle_turnstile_and_terms(page, url)
        
        # Obter conteúdo final
        content = await page.get_content()
        
        logger.info(f"Página carregada: {len(content)} bytes")
        
        return content
        
    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        raise

@app.route('/scrape')
def scrape():
    """Endpoint para scraping"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL obrigatória"}), 400
    
    try:
        # Executar scraping
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        content = loop.run_until_complete(scrape_page(url))
        
        return jsonify({
            "success": True,
            "html": content,
            "length": len(content),
            "url": url
        })
        
    except Exception as e:
        logger.error(f"Erro: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "url": url
        }), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "ok", "driver": "active" if driver else "inactive"})

if __name__ == '__main__':
    print("🚀 Iniciando proxy simples para Turnstile...")
    print("📍 Acesse: http://localhost:3333/scrape?url=<URL>")
    app.run(host='0.0.0.0', port=3333, debug=True)