"""
Simple Cloudflare bypass implementation for nodriver
Based on nodriver-cf-bypass concepts
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

class CFBypass:
    def __init__(self, browser_tab, debug=False):
        self.browser_tab = browser_tab
        self.debug = debug
        
    async def _log(self, message):
        if self.debug:
            logger.info(f"[CFBypass] {message}")
    
    async def _detect_cloudflare(self):
        """Detect if Cloudflare challenge is present with enhanced Turnstile detection"""
        try:
            # Enhanced detection using JavaScript
            cf_detected = await self.browser_tab.evaluate("""
                (() => {
                    console.log('[CF-Bypass] Starting enhanced Cloudflare detection...');
                    
                    // Check for Cloudflare elements
                    const cfSelectors = [
                        '[data-cf]', '.cf-challenge', '.cloudflare', '#challenge-stage',
                        '.cf-wrapper', '.cf-loading', '.cf-browser-verification',
                        'iframe[src*="challenges.cloudflare.com"]',
                        'iframe[src*="turnstile"]',
                        '.cf-turnstile', '[data-sitekey]', '.cloudflare-turnstile'
                    ];
                    
                    for (const selector of cfSelectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            console.log(`[CF-Bypass] Cloudflare detected via selector: ${selector}`);
                            return {detected: true, method: 'selector', detail: selector};
                        }
                    }
                    
                    // Check page title
                    const title = document.title.toLowerCase();
                    const titleIndicators = ['cloudflare', 'checking', 'moment', 'please wait', 'just a moment'];
                    for (const indicator of titleIndicators) {
                        if (title.includes(indicator)) {
                            console.log(`[CF-Bypass] Cloudflare detected via title: ${indicator}`);
                            return {detected: true, method: 'title', detail: indicator};
                        }
                    }
                    
                    // Check page content
                    const bodyText = document.body ? document.body.innerText.toLowerCase() : '';
                    const contentIndicators = [
                        'checking your browser', 'please wait', 'cloudflare', 'turnstile',
                        'challenge', 'verifying you are human', 'completing the challenge'
                    ];
                    
                    for (const indicator of contentIndicators) {
                        if (bodyText.includes(indicator)) {
                            console.log(`[CF-Bypass] Cloudflare detected via content: ${indicator}`);
                            return {detected: true, method: 'content', detail: indicator};
                        }
                    }
                    
                    // Check for specific Turnstile JavaScript presence
                    const scripts = Array.from(document.scripts);
                    for (const script of scripts) {
                        if (script.src && (script.src.includes('turnstile') || script.src.includes('challenges.cloudflare.com'))) {
                            console.log('[CF-Bypass] Turnstile script detected');
                            return {detected: true, method: 'script', detail: 'turnstile-script'};
                        }
                    }
                    
                    // Check for meta tags
                    const metaTags = document.querySelectorAll('meta[name*="cloudflare"], meta[content*="cloudflare"]');
                    if (metaTags.length > 0) {
                        console.log('[CF-Bypass] Cloudflare meta tags detected');
                        return {detected: true, method: 'meta', detail: 'cloudflare-meta'};
                    }
                    
                    console.log('[CF-Bypass] No Cloudflare challenge detected');
                    return {detected: false, method: null, detail: null};
                })()
            """)
            
            if cf_detected['detected']:
                await self._log(f"Cloudflare detected via {cf_detected['method']}: {cf_detected['detail']}")
                return True
            else:
                return False
                
        except Exception as e:
            await self._log(f"Error detecting Cloudflare: {e}")
            return False
    
    async def _handle_turnstile(self):
        """Handle Cloudflare Turnstile challenge with enhanced methods"""
        try:
            await self._log("Looking for Turnstile challenge...")
            
            # Wait for Turnstile to load
            await asyncio.sleep(3)
            
            # Enhanced JavaScript-based Turnstile interaction
            turnstile_handled = await self.browser_tab.evaluate("""
                (() => {
                    console.log('[CF-Bypass] Starting Turnstile detection...');
                    
                    // Method 1: Look for Turnstile iframes
                    const iframes = document.querySelectorAll('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]');
                    console.log(`[CF-Bypass] Found ${iframes.length} potential turnstile iframes`);
                    
                    for (const iframe of iframes) {
                        try {
                            console.log('[CF-Bypass] Found turnstile iframe, simulating interaction...');
                            
                            // Get iframe position for natural interaction
                            const rect = iframe.getBoundingClientRect();
                            const centerX = rect.left + rect.width / 2;
                            const centerY = rect.top + rect.height / 2;
                            
                            // Simulate mouse events that Turnstile tracks
                            const mousemoveEvent = new MouseEvent('mousemove', {
                                clientX: centerX - 10,
                                clientY: centerY - 10,
                                bubbles: true,
                                view: window
                            });
                            iframe.dispatchEvent(mousemoveEvent);
                            
                            // Wait then move to center
                            setTimeout(() => {
                                const moveToCenter = new MouseEvent('mousemove', {
                                    clientX: centerX,
                                    clientY: centerY,
                                    bubbles: true,
                                    view: window
                                });
                                iframe.dispatchEvent(moveToCenter);
                                
                                // Finally click
                                setTimeout(() => {
                                    const clickEvent = new MouseEvent('click', {
                                        clientX: centerX,
                                        clientY: centerY,
                                        bubbles: true,
                                        view: window
                                    });
                                    iframe.dispatchEvent(clickEvent);
                                }, 200);
                            }, 300);
                            
                            return true;
                        } catch (e) {
                            console.log('[CF-Bypass] Error with iframe interaction:', e);
                        }
                    }
                    
                    // Method 2: Look for Turnstile containers
                    const turnstileContainers = document.querySelectorAll('.cf-turnstile, [data-sitekey], .cloudflare-turnstile, div[data-callback]');
                    console.log(`[CF-Bypass] Found ${turnstileContainers.length} turnstile containers`);
                    
                    for (const container of turnstileContainers) {
                        try {
                            console.log('[CF-Bypass] Attempting to interact with turnstile container');
                            
                            // Look for clickable elements inside
                            const clickables = container.querySelectorAll('input[type="checkbox"], button, [role="button"], div[tabindex]');
                            for (const clickable of clickables) {
                                try {
                                    console.log('[CF-Bypass] Clicking turnstile element');
                                    clickable.focus();
                                    clickable.click();
                                    return true;
                                } catch (e) {
                                    console.log('[CF-Bypass] Clickable element failed:', e);
                                }
                            }
                            
                            // If no clickables found, try clicking the container itself
                            container.click();
                            return true;
                        } catch (e) {
                            console.log('[CF-Bypass] Container interaction failed:', e);
                        }
                    }
                    
                    // Method 3: Generic challenge detection
                    const challengeElements = document.querySelectorAll(
                        '.challenge-form, .cf-challenge, #challenge-stage, [data-action="challenge"]'
                    );
                    
                    for (const element of challengeElements) {
                        try {
                            console.log('[CF-Bypass] Found challenge element, attempting click');
                            element.click();
                            return true;
                        } catch (e) {
                            console.log('[CF-Bypass] Challenge element click failed:', e);
                        }
                    }
                    
                    console.log('[CF-Bypass] No turnstile elements found or all interactions failed');
                    return false;
                })()
            """)
            
            if turnstile_handled:
                await self._log("Turnstile interaction completed, waiting for resolution...")
                await asyncio.sleep(5)
                return True
            else:
                await self._log("No Turnstile elements found or interaction failed")
                return False
            
        except Exception as e:
            await self._log(f"Error handling Turnstile: {e}")
            return False
    
    async def _wait_for_resolution(self, timeout=30):
        """Wait for Cloudflare challenge to be resolved"""
        await self._log(f"Waiting for challenge resolution (timeout: {timeout}s)")
        
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Check if challenge is still present
            if not await self._detect_cloudflare():
                await self._log("Challenge resolved!")
                return True
                
            await asyncio.sleep(1)
        
        await self._log("Timeout waiting for challenge resolution")
        return False
    
    async def bypass(self, max_retries=5, interval_between_retries=2, reload_page_after_n_retries=3):
        """Main bypass method"""
        await self._log("Starting Cloudflare bypass...")
        
        for attempt in range(max_retries):
            await self._log(f"Attempt {attempt + 1}/{max_retries}")
            
            # Check if Cloudflare is present
            if not await self._detect_cloudflare():
                await self._log("No Cloudflare challenge detected")
                return True
            
            # Try to handle the challenge
            await self._log("Handling Cloudflare challenge...")
            
            # Handle turnstile if present
            await self._handle_turnstile()
            
            # Wait for resolution
            if await self._wait_for_resolution():
                await self._log("Bypass successful!")
                return True
            
            # If we need to reload the page
            if reload_page_after_n_retries > 0 and (attempt + 1) % reload_page_after_n_retries == 0:
                await self._log("Reloading page...")
                await self.browser_tab.reload()
                await asyncio.sleep(3)
            
            if attempt < max_retries - 1:
                await self._log(f"Waiting {interval_between_retries}s before retry...")
                await asyncio.sleep(interval_between_retries)
        
        await self._log("Bypass failed after all attempts")
        return False