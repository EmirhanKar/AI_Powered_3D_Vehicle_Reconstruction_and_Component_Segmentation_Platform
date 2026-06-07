"""
Meshy AI Entegrasyon Test Scripti
─────────────────────────────────
Bu script backend'i baslatmadan Meshy servisini dogrudan test eder.

Calistirmak icin:
    cd d:\MODIFIAI\modif-ai-backend\Backend
    python test_meshy.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

from app.services.meshy_service import (
    MeshyService,
    MeshyModel,
    OutputFormat,
    TaskStatus,
    MeshyAPIError,
    MESHY_MODE,
)


async def test_health_check():
    """Test 1: Baglanti ve API key kontrolu."""
    print("\n" + "=" * 55)
    print("  TEST 1: Meshy AI Baglanti Kontrolu")
    print("=" * 55)

    meshy = MeshyService()
    result = await meshy.health_check()

    print(f"  Status  : {result['status']}")
    print(f"  Mode    : {result['mode']}")
    print(f"  API Key : {'Gecerli' if result['api_key_valid'] else 'Gecersiz/Test'}")
    msg = result['message'].encode('ascii', 'replace').decode('ascii')
    print(f"  Mesaj   : {msg}")

    if result.get("balance"):
        print(f"  Bakiye  : {result['balance']}")

    return result["status"] in ("ok", "warning")


async def test_image_to_3d():
    """Test 2: Image-to-3D task olusturma (test mode)."""
    print("\n" + "=" * 55)
    print("  TEST 2: Image-to-3D Task Olusturma")
    print("=" * 55)

    meshy = MeshyService()

    # Test icin ornek bir araba gorseli URL'i
    test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/2019_BMW_M340i_xDrive_Automatic_3.0.jpg/1280px-2019_BMW_M340i_xDrive_Automatic_3.0.jpg"

    try:
        task_id = await meshy.image_to_3d(
            image_url=test_image_url,
            model=MeshyModel.MESHY_4,
            topology="quad",
            target_polycount=30000,
        )
        print(f"  Task ID : {task_id}")
        print(f"  Sonuc   : Task basariyla olusturuldu!")

        # Task durumunu kontrol et
        if task_id:
            print(f"\n  Task durumu kontrol ediliyor...")
            try:
                status = await meshy.get_task_status(task_id, "image-to-3d")
                print(f"  Durum   : {status.status.value}")
                print(f"  Ilerleme: %{status.progress}")
            except MeshyAPIError as e:
                print(f"  Durum sorgusu: {e.message}")
                # Test modunda status sorgusu calismayabilir

        return True

    except MeshyAPIError as e:
        print(f"  API Hatasi: [{e.status_code}] {e.message}")
        if MESHY_MODE == "test":
            print("  (Test modunda normal olabilir)")
        return False
    except Exception as e:
        print(f"  Hata: {e}")
        return False


async def test_text_to_3d():
    """Test 3: Text-to-3D task olusturma."""
    print("\n" + "=" * 55)
    print("  TEST 3: Text-to-3D Task Olusturma")
    print("=" * 55)

    meshy = MeshyService()

    try:
        task_id = await meshy.text_to_3d(
            prompt="a carbon fiber rear spoiler for a sports car",
            model=MeshyModel.MESHY_4,
            art_style="realistic",
        )
        print(f"  Task ID : {task_id}")
        print(f"  Sonuc   : Text-to-3D task basariyla olusturuldu!")
        return True

    except MeshyAPIError as e:
        print(f"  API Hatasi: [{e.status_code}] {e.message}")
        if MESHY_MODE == "test":
            print("  (Test modunda normal olabilir)")
        return False
    except Exception as e:
        print(f"  Hata: {e}")
        return False


async def test_service_configuration():
    """Test 4: Servis yapilandirma kontrolu."""
    print("\n" + "=" * 55)
    print("  TEST 4: Servis Yapilandirma Kontrolu")
    print("=" * 55)

    meshy = MeshyService()

    print(f"  Base URL  : {meshy._base_url}")
    print(f"  API Key   : {meshy._api_key[:15]}..." if meshy._api_key else "  API Key   : TANIMLANMAMIS")
    print(f"  Mode      : {MESHY_MODE}")
    print(f"  Test Key  : {'Evet' if 'dummy' in meshy._api_key else 'Hayir'}")

    # Enum degerleri kontrol
    print(f"\n  Modeller  : {[m.value for m in MeshyModel]}")
    print(f"  Formatlar : {[f.value for f in OutputFormat]}")
    print(f"  Durumlar  : {[s.value for s in TaskStatus]}")

    return True


async def test_router_endpoints():
    """Test 5: Router endpoint'lerinin yuklenmesi."""
    print("\n" + "=" * 55)
    print("  TEST 5: Router Endpoint Kontrolu")
    print("=" * 55)

    from app.api.routers.meshy_router import router

    routes = []
    for route in router.routes:
        path = getattr(route, "path", "?")
        methods = getattr(route, "methods", set())
        routes.append((path, methods))
        print(f"  {', '.join(methods):6s} {path}")

    expected_count = 9
    actual_count = len(routes)
    print(f"\n  Toplam {actual_count}/{expected_count} endpoint kayitli")

    return actual_count == expected_count


async def test_full_app():
    """Test 6: Tam uygulama import kontrolu."""
    print("\n" + "=" * 55)
    print("  TEST 6: Tam Uygulama Import Kontrolu")
    print("=" * 55)

    from app.main import app

    meshy_routes = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if "/meshy" in path:
            meshy_routes.append(path)

    print(f"  Meshy route'lari ({len(meshy_routes)}):")
    for r in meshy_routes:
        print(f"    - {r}")

    return len(meshy_routes) > 0


async def main():
    """Tum testleri calistir."""
    print("\n")
    print("*" * 55)
    print("  MODIF-AI x Meshy AI - Entegrasyon Testleri")
    print("*" * 55)
    print(f"  Mod: {MESHY_MODE.upper()}")

    results = {}

    # Test 4: Config (her zaman calisir)
    results["config"] = await test_service_configuration()

    # Test 5: Router
    results["router"] = await test_router_endpoints()

    # Test 6: Full app
    results["full_app"] = await test_full_app()

    # Test 1: Health check (API cagrisi)
    results["health"] = await test_health_check()

    # Test 2: Image-to-3D (API cagrisi)
    results["image_to_3d"] = await test_image_to_3d()

    # Test 3: Text-to-3D (API cagrisi)
    results["text_to_3d"] = await test_text_to_3d()

    # Sonuc ozeti
    print("\n" + "=" * 55)
    print("  SONUC OZETI")
    print("=" * 55)

    for name, passed in results.items():
        status = "GECTI" if passed else "KALDI/UYARI"
        icon = "[+]" if passed else "[-]"
        print(f"  {icon} {name:15s} : {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} test gecti")

    if MESHY_MODE == "test":
        print("\n  NOT: Test modunda API cagrilari gercek sonuc dondurmeyebilir.")
        print("  Gercek test icin:")
        print("    1. https://www.meshy.ai adresinden hesap olusturun")
        print("    2. Settings > API'den API key alin")
        print("    3. .env dosyasinda:")
        print("       MESHY_API_KEY = msy_your_key_here")
        print("       MESHY_MODE = live")

    print("")


if __name__ == "__main__":
    asyncio.run(main())
