r"""
Tripo3D AI Entegrasyon Test Scripti
────────────────────────────────────
Bu script backend'i başlatmadan Tripo3D servisini doğrudan test eder.

Çalıştırmak için:
    cd d:\MODIFIAI\Backend
    python test_tripo.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

from app.services.tripo_service import (
    TripoService,
    OutputFormat,
    TaskStatus,
    TripoAPIError,
    TRIPO_MODE,
)


async def test_health_check():
    """Test 1: Bağlantı ve API key kontrolü."""
    print("\n" + "=" * 55)
    print("  TEST 1: Tripo3D AI Bağlantı Kontrolü")
    print("=" * 55)

    tripo = TripoService()
    result = await tripo.health_check()

    print(f"  Status  : {result['status']}")
    print(f"  Mode    : {result['mode']}")
    print(f"  API Key : {'Geçerli' if result['api_key_valid'] else 'Geçersiz/Test'}")
    msg = result['message'].encode('ascii', 'replace').decode('ascii')
    print(f"  Mesaj   : {msg}")

    if result.get("balance"):
        print(f"  Bakiye  : {result['balance']}")

    return result["status"] in ("ok", "warning")


async def test_image_to_3d():
    """Test 2: Image-to-3D task oluşturma."""
    print("\n" + "=" * 55)
    print("  TEST 2: Image-to-3D Task Oluşturma")
    print("=" * 55)

    tripo = TripoService()

    # Test için örnek bir araba görseli URL'i
    test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/2019_BMW_M340i_xDrive_Automatic_3.0.jpg/1280px-2019_BMW_M340i_xDrive_Automatic_3.0.jpg"

    try:
        task_id = await tripo.image_to_3d(
            image_url=test_image_url,
        )
        print(f"  Task ID : {task_id}")
        print(f"  Sonuç   : Task başarıyla oluşturuldu!")

        # Task durumunu kontrol et
        if task_id:
            print(f"\n  Task durumu kontrol ediliyor...")
            try:
                status = await tripo.get_task_status(task_id)
                print(f"  Durum   : {status.status.value}")
                print(f"  İlerleme: %{status.progress}")
            except TripoAPIError as e:
                print(f"  Durum sorgusu: {e.message}")

        return True

    except TripoAPIError as e:
        print(f"  API Hatası: [{e.code}] {e.message}")
        if TRIPO_MODE == "test":
            print("  (Test modunda normal olabilir)")
        return False
    except Exception as e:
        print(f"  Hata: {e}")
        return False


async def test_text_to_3d():
    """Test 3: Text-to-3D task oluşturma."""
    print("\n" + "=" * 55)
    print("  TEST 3: Text-to-3D Task Oluşturma")
    print("=" * 55)

    tripo = TripoService()

    try:
        task_id = await tripo.text_to_3d(
            prompt="a carbon fiber rear spoiler for a sports car",
        )
        print(f"  Task ID : {task_id}")
        print(f"  Sonuç   : Text-to-3D task başarıyla oluşturuldu!")
        return True

    except TripoAPIError as e:
        print(f"  API Hatası: [{e.code}] {e.message}")
        if TRIPO_MODE == "test":
            print("  (Test modunda normal olabilir)")
        return False
    except Exception as e:
        print(f"  Hata: {e}")
        return False


async def test_service_configuration():
    """Test 4: Servis yapılandırma kontrolü."""
    print("\n" + "=" * 55)
    print("  TEST 4: Servis Yapılandırma Kontrolü")
    print("=" * 55)

    tripo = TripoService()

    print(f"  Base URL  : {tripo._base_url}")
    print(f"  API Key   : {tripo._api_key[:15]}..." if tripo._api_key else "  API Key   : TANIMLANMAMIS")
    print(f"  Mode      : {TRIPO_MODE}")

    # Enum değerleri kontrol
    print(f"\n  Formatlar : {[f.value for f in OutputFormat]}")
    print(f"  Durumlar  : {[s.value for s in TaskStatus]}")

    return True


async def test_router_endpoints():
    """Test 5: Router endpoint'lerinin yüklenmesi."""
    print("\n" + "=" * 55)
    print("  TEST 5: Router Endpoint Kontrolü")
    print("=" * 55)

    from app.api.routers.tripo_router import router

    routes = []
    for route in router.routes:
        path = getattr(route, "path", "?")
        methods = getattr(route, "methods", set())
        routes.append((path, methods))
        print(f"  {', '.join(methods):6s} {path}")

    expected_count = 8
    actual_count = len(routes)
    print(f"\n  Toplam {actual_count}/{expected_count} endpoint kayıtlı")

    return actual_count == expected_count


async def test_full_app():
    """Test 6: Tam uygulama import kontrolü."""
    print("\n" + "=" * 55)
    print("  TEST 6: Tam Uygulama Import Kontrolü")
    print("=" * 55)

    from app.main import app

    tripo_routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if "/tripo" in path:
            tripo_routes.append(path)

    print(f"  Tripo3D route'ları ({len(tripo_routes)}):")
    for r in tripo_routes:
        print(f"    - {r}")

    # Meshy referansı kalmadığını kontrol et
    meshy_routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if "/meshy" in path:
            meshy_routes.append(path)

    if meshy_routes:
        print(f"\n  ⚠️  Meshy referansı hâlâ mevcut: {meshy_routes}")
        return False

    print(f"\n  [+] Meshy referansi kalmamis!")
    return len(tripo_routes) > 0


async def main():
    """Tüm testleri çalıştır."""
    print("\n")
    print("*" * 55)
    print("  MODIF-AI x Tripo3D AI - Entegrasyon Testleri")
    print("*" * 55)
    print(f"  Mod: {TRIPO_MODE.upper()}")

    results = {}

    # Test 4: Config (her zaman çalışır)
    results["config"] = await test_service_configuration()

    # Test 5: Router
    results["router"] = await test_router_endpoints()

    # Test 6: Full app
    results["full_app"] = await test_full_app()

    # Test 1: Health check (API çağrısı)
    results["health"] = await test_health_check()

    # Test 2: Image-to-3D (API çağrısı)
    results["image_to_3d"] = await test_image_to_3d()

    # Test 3: Text-to-3D (API çağrısı)
    results["text_to_3d"] = await test_text_to_3d()

    # Sonuç özeti
    print("\n" + "=" * 55)
    print("  SONUÇ ÖZETİ")
    print("=" * 55)

    for name, passed in results.items():
        status = "GEÇTİ" if passed else "KALDI/UYARI"
        icon = "[+]" if passed else "[-]"
        print(f"  {icon} {name:15s} : {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} test geçti")

    if TRIPO_MODE == "test":
        print("\n  NOT: Test modunda API çağrıları gerçek sonuç döndürmeyebilir.")
        print("  Gerçek test için:")
        print("    1. https://www.tripo3d.ai adresinden hesap oluşturun")
        print("    2. API key alın")
        print("    3. .env dosyasında:")
        print("       TRIPO_API_KEY = tsk_your_key_here")
        print("       TRIPO_MODE = live")

    print("")


if __name__ == "__main__":
    asyncio.run(main())
