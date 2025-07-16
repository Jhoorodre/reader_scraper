"""
FlareSolverr client for Cloudflare bypass fallback
"""
import requests
import json
import logging
import time

logger = logging.getLogger(__name__)

class FlareSolverrClient:
    def __init__(self, base_url="http://localhost:8191/v1"):
        self.base_url = base_url
        self.session_id = None
        
    def _make_request(self, data, timeout=60):
        """Make request to FlareSolverr API"""
        try:
            response = requests.post(
                self.base_url,
                json=data,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"FlareSolverr request failed: {e}")
            return None
            
    def is_available(self):
        """Check if FlareSolverr is running and available"""
        try:
            data = {
                "cmd": "sessions.list"
            }
            result = self._make_request(data, timeout=5)
            return result is not None and result.get("status") == "ok"
        except:
            return False
            
    def create_session(self):
        """Create a persistent browser session"""
        try:
            data = {
                "cmd": "sessions.create"
            }
            result = self._make_request(data)
            
            if result and result.get("status") == "ok":
                self.session_id = result.get("session")
                logger.info(f"FlareSolverr session created: {self.session_id}")
                return True
            else:
                logger.error("Failed to create FlareSolverr session")
                return False
        except Exception as e:
            logger.error(f"Error creating FlareSolverr session: {e}")
            return False
            
    def destroy_session(self):
        """Destroy the current session"""
        if self.session_id:
            try:
                data = {
                    "cmd": "sessions.destroy",
                    "session": self.session_id
                }
                result = self._make_request(data)
                if result and result.get("status") == "ok":
                    logger.info(f"FlareSolverr session destroyed: {self.session_id}")
                    self.session_id = None
                    return True
            except Exception as e:
                logger.error(f"Error destroying FlareSolverr session: {e}")
            finally:
                self.session_id = None
        return False
                
    def get_page(self, url, max_timeout=60000, session=True):
        """Get page content through FlareSolverr"""
        try:
            data = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": max_timeout
            }
            
            # Use session if available and requested
            if session and self.session_id:
                data["session"] = self.session_id
            elif session and not self.session_id:
                # Try to create session first
                if not self.create_session():
                    logger.warning("Could not create session, making request without session")
                else:
                    data["session"] = self.session_id
                    
            logger.info(f"FlareSolverr getting page: {url}")
            result = self._make_request(data, timeout=max_timeout//1000 + 10)
            
            if result and result.get("status") == "ok":
                solution = result.get("solution", {})
                html = solution.get("response")
                url_final = solution.get("url", url)
                cookies = solution.get("cookies", [])
                
                logger.info(f"FlareSolverr success. Final URL: {url_final}")
                logger.info(f"FlareSolverr returned {len(html) if html else 0} bytes of HTML")
                logger.info(f"FlareSolverr returned {len(cookies)} cookies")
                
                return {
                    "success": True,
                    "html": html,
                    "url": url_final,
                    "cookies": cookies,
                    "user_agent": solution.get("userAgent")
                }
            else:
                error_msg = result.get("message", "Unknown error") if result else "No response"
                logger.error(f"FlareSolverr failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Error using FlareSolverr: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session"""
        self.destroy_session()