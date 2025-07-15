#!/usr/bin/env python3
"""
Teste simples para o proxy Turnstile
"""
import requests
import time

def test_url(url):
    """Testa uma URL específica"""
    print(f"🧪 Testando: {url}")
    
    try:
        start_time = time.time()
        
        response = requests.get(
            "http://localhost:3333/scrape",
            params={"url": url},
            timeout=120
        )
        
        elapsed = time.time() - start_time
        print(f"⏱️ Tempo: {elapsed:.1f}s")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                length = data.get("length", 0)
                print(f"✅ Sucesso: {length} bytes")
                
                # Verificar qualidade do conteúdo
                if length > 50000:
                    print("🟢 Conteúdo excelente")
                elif length > 20000:
                    print("🟡 Conteúdo bom")
                elif length > 5000:
                    print("🟠 Conteúdo básico")
                else:
                    print("🔴 Conteúdo insuficiente (possível erro)")
                
                return True
            else:
                error = data.get("error", "Erro desconhecido")
                print(f"❌ Falhou: {error}")
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout - proxy pode estar travado")
    except requests.exceptions.ConnectionError:
        print("❌ Não conseguiu conectar - proxy não está rodando?")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    return False

def main():
    print("🔧 Teste Simples do Proxy Turnstile")
    print("=" * 50)
    
    # Verificar se proxy está rodando
    try:
        response = requests.get("http://localhost:3333/health", timeout=3)
        if response.status_code == 200:
            print("✅ Proxy está rodando")
        else:
            print("⚠️ Proxy respondeu mas com problemas")
    except:
        print("❌ Proxy não está rodando!")
        print("💡 Execute: python simple_proxy.py")
        return
    
    # URL de teste
    test_url_input = input("\nURL para testar (Enter = padrão): ").strip()
    if not test_url_input:
        test_url_input = "https://www.sussytoons.wtf/capitulo/275851"
    
    print(f"\n🎯 Testando: {test_url_input}")
    
    success = test_url(test_url_input)
    
    if success:
        print("\n🎉 Teste passou!")
    else:
        print("\n❌ Teste falhou!")
        print("\n🔍 Debug:")
        print("- Verifique os logs do proxy")
        print("- Tente uma URL diferente")
        print("- Reinicie o proxy se necessário")

if __name__ == "__main__":
    main()